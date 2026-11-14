"""Public views of a generated language and its tasks. Reference answers and hidden tests never leave here."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

from ..core import FunDef, IntLit, Program, Return
from ..manual import build_manual
from ..printer import to_source
from ..spec import generate
from ..tasks import ALL_TASKS, instantiate, py_format


@lru_cache(maxsize=512)
def language(seed: int) -> dict:
    spec = generate(seed)
    return {"seed": seed, "name": spec.name, "features": spec.features(), "manual": build_manual(spec).text}


def _visible(inst) -> list:
    return [{"args": [py_format(a) for a in t.args], "expected": t.expected} for t in inst.visible]


@lru_cache(maxsize=512)
def tasks(seed: int) -> dict:
    spec = generate(seed)
    listed = []
    for task in ALL_TASKS:
        inst = instantiate(task, spec)
        listed.append({
            "id": inst.task_id, "tier": inst.tier, "title": inst.title, "statement": inst.statement,
            "kind": inst.kind, "runnable": inst.kind == "code", "shown": inst.shown,
            "visible": _visible(inst), "hidden_tests": len(inst.tests) - len(inst.visible),
        })
    return {"seed": seed, "name": spec.name, "tasks": listed}


def find_task(task_id: str):
    matches = [t for t in ALL_TASKS if t.id == task_id]
    return matches[0] if matches else None


def _stub(program: Program) -> Program:
    """Same function headers, every body replaced by `return 0`: parses, does not solve the task."""
    body = tuple(replace(s, body=(Return(IntLit(0)),)) if isinstance(s, FunDef) else s for s in program.body)
    return Program(body)


def starter(seed: int, task_id: str) -> str:
    """A skeleton to start from. For fix tasks it is the buggy program, which the task asks to repair."""
    spec = generate(seed)
    task = find_task(task_id)
    if task.tier == "fix":
        return instantiate(task, spec).shown
    return to_source(_stub(task.build(spec.semantics.index_base)), spec)
