"""Predict tasks must depend on the generated language, so the manual is needed to answer them."""

import dataclasses

import pytest

from babel_bench.interp import run_program
from babel_bench.spec import generate
from babel_bench.tasks import ALL_TASKS
from babel_bench.tasks.base import instantiate

from conftest import CANONICAL

PREDICT = [t for t in ALL_TASKS if t.tier == "predict"]
FLIPS = {
    "index_base": lambda v: 1 - v,
    "int_div": lambda v: "trunc" if v == "floor" else "floor",
    "int_mod": lambda v: "trunc" if v == "floor" else "floor",
    "zero_is_false": lambda v: not v,
    "empty_is_false": lambda v: not v,
    "logic_returns_operand": lambda v: not v,
}


def _output(task, sem):
    result = run_program(task.build(sem.index_base), sem)
    assert result.error is None, (task.id, result.error)
    return result.text


@pytest.mark.parametrize("task", PREDICT, ids=[t.id for t in PREDICT])
def test_predict_output_changes_when_a_randomised_semantic_changes(task):
    base = _output(task, CANONICAL)
    changed = [
        field for field, flip in FLIPS.items()
        if _output(task, dataclasses.replace(CANONICAL, **{field: flip(getattr(CANONICAL, field))})) != base
    ]
    assert changed, f"{task.id} prints the same under every semantic, so the manual is not needed"


@pytest.mark.parametrize("task", PREDICT, ids=[t.id for t in PREDICT])
def test_predict_expected_output_differs_across_seeds(task):
    outputs = {instantiate(task, generate(seed)).expected_output for seed in range(40)}
    assert len(outputs) > 1, f"{task.id} has the same expected output for every seed"
