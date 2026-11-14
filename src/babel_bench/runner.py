"""Harness: run a model over (language x task) cells with attempts, feedback,
concurrency, and a resumable JSONL results file (one record per finished cell)."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .grade import grade_answer
from .manual import build_manual
from .models import Model, ModelError, Request, cost_usd
from .prompt import SYSTEM, build_prompt
from .spec import LanguageSpec, generate
from .tasks import Instance, instantiate, select


@dataclass(frozen=True)
class Cell:
    spec: LanguageSpec
    manual: str
    instance: Instance


@dataclass(frozen=True)
class RunSummary:
    recorded: int
    skipped: int
    errors: tuple


def build_cells(seeds: tuple, task_ids: tuple | None) -> tuple:
    cells = []
    tasks = select(task_ids)
    for seed in seeds:
        spec = generate(seed)
        manual = build_manual(spec).text
        cells += [Cell(spec, manual, instantiate(task, spec)) for task in tasks]
    return tuple(cells)


def load_done(path: Path) -> set:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            done.add((rec["model"], rec["seed"], rec["task_id"]))
    return done


def _attempt_record(number: int, prompt: str, comp, grade, cost, latency: float) -> dict:
    return {
        "attempt": number, "prompt": prompt, "answer": comp.text,
        "passed": grade.passed, "tests_passed": grade.tests_passed, "tests_total": grade.tests_total,
        "feedback": grade.feedback, "error": grade.error, "output": grade.output,
        "input_tokens": comp.input_tokens, "output_tokens": comp.output_tokens,
        "cost_usd": cost, "estimated": comp.estimated, "latency_s": round(latency, 3),
    }


def evaluate(model: Model, cell: Cell, attempts: int) -> dict:
    """Run up to `attempts` tries; each failed try's feedback goes into the next prompt."""
    inst = cell.instance
    log: list = []
    feedback = None
    for number in range(1, attempts + 1):
        prompt = build_prompt(cell.spec.name, cell.manual, inst, feedback)
        req = Request(SYSTEM, prompt, inst.oracle_answer, inst.naive_answer)
        started = time.monotonic()
        comp = model.complete(req)  # ModelError propagates; the cell is then left unrecorded
        latency = time.monotonic() - started
        grade = grade_answer(cell.spec, inst, comp.text)
        log.append(_attempt_record(number, prompt, comp, grade, cost_usd(comp, model.prices), latency))
        if grade.passed:
            break
        feedback = grade.feedback
    return _cell_record(model, cell, log)


def _cell_record(model: Model, cell: Cell, log: list) -> dict:
    costs = [a["cost_usd"] for a in log]
    return {
        "model": model.label, "seed": cell.spec.seed, "language": cell.spec.name,
        "features": cell.spec.features(), "task_id": cell.instance.task_id,
        "tier": cell.instance.tier, "kind": cell.instance.kind, "title": cell.instance.title,
        "passed": any(a["passed"] for a in log), "attempts_used": len(log), "attempts": log,
        "input_tokens": sum(a["input_tokens"] for a in log),
        "output_tokens": sum(a["output_tokens"] for a in log),
        "cost_usd": None if any(c is None for c in costs) else round(sum(costs), 6),
        "estimated": any(a["estimated"] for a in log),
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def run_cells(model: Model, cells: tuple, attempts: int, out_path: Path, concurrency: int = 4) -> RunSummary:
    done = load_done(out_path)
    todo = [c for c in cells if (model.label, c.spec.seed, c.instance.task_id) not in done]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    recorded, errors = 0, []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool, \
            out_path.open("a", encoding="utf-8") as fh:
        futures = {pool.submit(evaluate, model, c, attempts): c for c in todo}
        for fut in as_completed(futures):
            cell = futures[fut]
            try:
                record = fut.result()
            except ModelError as exc:
                errors.append(f"{cell.spec.name} {cell.instance.task_id}: {exc}")
                continue
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            recorded += 1
    return RunSummary(recorded, len(cells) - len(todo), tuple(errors))
