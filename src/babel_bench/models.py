"""Model adapters. Each turns a Request into a Completion; baselines read hints from the request."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import Callable

PRICES_PER_MTOK = {  # (input, output) USD per million tokens, Anthropic first-party list prices
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.0, 20.0),
}
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"


class ModelError(RuntimeError):
    """A model call failed. The runner leaves such cells unrecorded so a rerun retries them."""


@dataclass(frozen=True)
class Request:
    system: str
    prompt: str
    oracle_answer: str  # only the oracle baseline reads this
    naive_answer: str  # only the naive baseline reads this


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    estimated: bool = False


@dataclass(frozen=True)
class Model:
    label: str
    answer: Callable[[Request], Completion]
    prices: tuple | None = None  # (input, output) USD per million tokens

    def complete(self, req: Request) -> Completion:
        return self.answer(req)


def cost_usd(comp: Completion, prices: tuple | None) -> float | None:
    if prices is None:
        return None
    return (comp.input_tokens * prices[0] + comp.output_tokens * prices[1]) / 1_000_000


def _estimate(text_in: str, text_out: str) -> tuple:
    return max(1, len(text_in) // 4), max(1, len(text_out) // 4)


def oracle() -> Model:
    return Model("oracle", lambda req: Completion(req.oracle_answer, 0, 0))


def naive() -> Model:
    return Model("naive", lambda req: Completion(req.naive_answer, 0, 0))


def scripted(label: str, fn: Callable[[Request], str]) -> Model:
    """Deterministic model for tests: fn sees the request and returns the answer text."""
    def answer(req: Request) -> Completion:
        text = fn(req)
        est_in, est_out = _estimate(req.system + req.prompt, text)
        return Completion(text, est_in, est_out, estimated=True)
    return Model(label, answer)


def anthropic(model_id: str | None = None, prices: tuple | None = None) -> Model:
    name = model_id or os.environ.get("BABEL_ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    client_holder: list = []

    def answer(req: Request) -> Completion:
        import anthropic as sdk  # imported lazily: only this adapter needs the SDK

        if not client_holder:
            try:
                client_holder.append(sdk.Anthropic())
            except sdk.AnthropicError as exc:  # e.g. no API key: a model error, not a crash
                raise ModelError(f"anthropic client could not start: {exc}") from exc
        try:
            resp = client_holder[0].messages.create(
                model=name, max_tokens=8000, system=req.system,
                messages=[{"role": "user", "content": req.prompt}],
            )
        except sdk.APIError as exc:
            raise ModelError(f"anthropic call failed: {exc}") from exc
        text = "".join(b.text for b in resp.content if b.type == "text")
        return Completion(text, resp.usage.input_tokens, resp.usage.output_tokens)

    return Model(f"anthropic:{name}", answer, prices or PRICES_PER_MTOK.get(name))


def openai_compatible(base_url: str, model_id: str, prices: tuple | None = None) -> Model:
    def answer(req: Request) -> Completion:
        body = json.dumps({
            "model": model_id,
            "messages": [{"role": "system", "content": req.system}, {"role": "user", "content": req.prompt}],
        }).encode()
        headers = {"Content-Type": "application/json"}
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        request = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", body, headers)
        try:
            with urllib.request.urlopen(request, timeout=600) as fh:  # noqa: S310 - user-chosen endpoint
                data = json.load(fh)
        except OSError as exc:
            raise ModelError(f"openai-compatible call failed: {exc}") from exc
        except ValueError as exc:  # body is not JSON
            raise ModelError(f"openai-compatible reply is not JSON: {exc}") from exc
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError(f"openai-compatible reply has no message content: {exc}") from exc
        usage = data.get("usage") or {}
        return Completion(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    return Model(f"openai:{model_id}", answer, prices)


def command(shell_cmd: str, prices: tuple | None = None) -> Model:
    """Pipe system+prompt to any shell command on stdin; the answer is its stdout."""
    def answer(req: Request) -> Completion:
        stdin = req.system + "\n\n" + req.prompt
        try:
            proc = subprocess.run(shell_cmd, shell=True, input=stdin, capture_output=True,
                                  text=True, timeout=900, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ModelError(f"command timed out after {exc.timeout}s") from exc
        if proc.returncode != 0:
            raise ModelError(f"command exited {proc.returncode}: {proc.stderr.strip()[:500]}")
        est_in, est_out = _estimate(stdin, proc.stdout)
        return Completion(proc.stdout, est_in, est_out, estimated=True)

    return Model(f"command:{shell_cmd}", answer, prices)


def parse_model(spec: str, prices: tuple | None = None) -> Model:
    """'oracle' | 'naive' | 'anthropic[:model]' | 'openai:<base_url>|<model>' | 'command:<shell>'."""
    if spec == "oracle":
        return oracle()
    if spec == "naive":
        return naive()
    if spec == "anthropic" or spec.startswith("anthropic:"):
        return anthropic(spec.partition(":")[2] or None, prices)
    if spec.startswith("openai:"):
        base_url, sep, model_id = spec[len("openai:"):].partition("|")
        if not sep or not base_url or not model_id:
            raise ValueError("use openai:<base_url>|<model>")
        return openai_compatible(base_url, model_id, prices)
    if spec.startswith("command:"):
        return command(spec[len("command:"):], prices)
    raise ValueError(f"unknown model spec: {spec}")
