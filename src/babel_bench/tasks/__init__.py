"""The task suite: 24 templates across four tiers, instantiated per language."""

from __future__ import annotations

from .base import Instance, Task, TaskBroken, instantiate, py_format
from .predict import PREDICT_TASKS
from .translate import TRANSLATE_TASKS
from .write import FIX_TASKS, WRITE_TASKS

ALL_TASKS: tuple = PREDICT_TASKS + TRANSLATE_TASKS + WRITE_TASKS + FIX_TASKS


def select(ids: tuple | None) -> tuple:
    """All tasks, or the subset named by `ids` (ids may be a tier name too)."""
    if not ids:
        return ALL_TASKS
    wanted = set(ids)
    chosen = tuple(t for t in ALL_TASKS if t.id in wanted or t.tier in wanted)
    missing = wanted - {t.id for t in chosen} - {t.tier for t in chosen}
    if missing:
        raise KeyError(f"unknown task or tier: {sorted(missing)}")
    return chosen


__all__ = ["ALL_TASKS", "Instance", "Task", "TaskBroken", "instantiate", "py_format", "select"]
