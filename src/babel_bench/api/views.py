"""Public views of a generated language and its tasks. Reference answers and hidden tests never leave here."""

from __future__ import annotations

from functools import lru_cache

from ..manual import build_manual
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
