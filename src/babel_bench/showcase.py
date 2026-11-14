"""Precomputed showcase for the landing page: one program in many generated languages.

Every source line and output comes from the generator, printer and interpreter the benchmark uses,
so the page never shows a hand-written example. Run from the repository root:

    uv run python -m babel_bench.showcase site/data

writes showcase.json (hero and rules matrix) and playground.json (seed 1 preloaded in the playground).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .api import views
from .core import Unary
from .interp import run_program
from .printer import to_source
from .spec import LanguageSpec, generate
from .tasks import ALL_TASKS, TaskBroken, instantiate
from .tasks.dsl import at, if_, lst, n, op, prog, show, text

SHOWCASE_TASK = "predict.squares"
SEEDS = tuple(range(1, 13))
FEATURE_SEEDS = (1, 2, 3)  # the side-by-side comparison on the landing page


def _probes(spec: LanguageSpec) -> list:
    """Small probe programs, each built from the same AST. The output is what the interpreter printed."""
    base = spec.semantics.index_base
    return [
        ("division", "Integer division of -7 by 2", show(op("/", Unary("neg", n(7)), n(2)))),
        ("modulo", "Modulo of -7 by 3", show(op("%", Unary("neg", n(7)), n(3)))),
        ("index", "First item of a two-item list", show(at(base, lst(text("first"), text("second")), n(0)))),
        ("zero", "Is 0 true or false?", if_(n(0), show(text("true")), orelse=(show(text("false")),))),
        ("logic", "0 or 5", show(op("or", n(0), n(5)))),
        ("precedence", "2 + 3 * 4, as printed", show(op("+", n(2), op("*", n(3), n(4))))),
    ]


def _run(program, spec: LanguageSpec) -> str:
    result = run_program(program, spec.semantics)
    if result.error:
        raise RuntimeError(f"probe failed in {spec.name}: {result.error}")
    return result.text.rstrip()


def _probe_rows(spec: LanguageSpec) -> list:
    return [
        {"id": pid, "label": label, "source": to_source(prog(stmt), spec), "output": _run(prog(stmt), spec)}
        for pid, label, stmt in _probes(spec)
    ]


def _language(seed: int) -> dict | None:
    spec = generate(seed)
    task = next(t for t in ALL_TASKS if t.id == SHOWCASE_TASK)
    try:
        inst = instantiate(task, spec)
    except TaskBroken:
        return None
    return {
        "seed": seed, "name": spec.name, "features": spec.features(),
        "program": inst.shown, "output": inst.expected_output.rstrip(), "probes": _probe_rows(spec),
    }


def build() -> dict:
    languages = [lang for lang in (_language(s) for s in SEEDS) if lang is not None]
    statement = instantiate(next(t for t in ALL_TASKS if t.id == SHOWCASE_TASK), generate(SEEDS[0])).statement
    return {
        "task": {"id": SHOWCASE_TASK, "statement": statement},
        "feature_seeds": list(FEATURE_SEEDS),
        "languages": languages,
    }


PLAYGROUND_SEED = 1


def playground_bundle(seed: int = PLAYGROUND_SEED) -> dict:
    """What the playground shows on page load: the manual, the task list, and each task's starter.

    Built from the same views the API serves, so it matches /api/languages/{seed} exactly.
    """
    lang = views.language(seed)
    listing = views.tasks(seed)
    starters = {t["id"]: views.starter(seed, t["id"]) for t in listing["tasks"] if t["tier"] != "predict"}
    return {"seed": seed, "name": lang["name"], "manual": lang["manual"], "tasks": listing["tasks"], "starters": starters}


def main(argv: list | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m babel_bench.showcase OUT_DIR", file=sys.stderr)
        return 2
    out = Path(args[0])
    out.mkdir(parents=True, exist_ok=True)
    (out / "showcase.json").write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "playground.json").write_text(json.dumps(playground_bundle(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out / 'showcase.json'} and {out / 'playground.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
