"""Every task: oracle solves it, naive fails it, templates agree with plain Python."""

import pytest

from babel_bench.grade import grade_answer
from babel_bench.interp import run_program
from babel_bench.core import Call, ExprStmt, Program
from babel_bench.printer import to_python, to_source
from babel_bench.spec import generate
from babel_bench.tasks import ALL_TASKS, instantiate, py_format
from babel_bench.tasks.base import value_to_expr
from babel_bench.tasks.write import _SPECS
from babel_bench.tasks.translate import _CASES as TRANSLATE_CASES

from conftest import CANONICAL

SEEDS = range(40)


def test_suite_has_at_least_twenty_templates_across_tiers():
    ids = [t.id for t in ALL_TASKS]
    assert len(ids) == len(set(ids)) >= 20
    assert {t.tier for t in ALL_TASKS} == {"predict", "translate", "write", "fix"}


@pytest.mark.parametrize("seed", SEEDS)
def test_oracle_scores_every_task(seed):
    spec = generate(seed)
    for task in ALL_TASKS:
        inst = instantiate(task, spec)
        grade = grade_answer(spec, inst, inst.oracle_answer)
        assert grade.passed, (task.id, grade.feedback)


@pytest.mark.parametrize("seed", range(12))
def test_naive_python_answers_fail_every_code_task(seed):
    spec = generate(seed)
    for task in ALL_TASKS:
        inst = instantiate(task, spec)
        assert not grade_answer(spec, inst, inst.naive_answer).passed, task.id


@pytest.mark.parametrize("seed", SEEDS)
def test_fix_tasks_ship_a_program_that_fails_hidden_tests(seed):
    spec = generate(seed)
    for task in ALL_TASKS:
        if task.tier != "fix":
            continue
        inst = instantiate(task, spec)
        buggy = task.buggy(spec.semantics.index_base)
        grade = grade_answer(spec, inst, to_source(buggy, spec))
        assert not grade.passed, task.id


def _canonical_result(program, args):
    call = ExprStmt(Call("print", (Call("solve", tuple(value_to_expr(a) for a in args)),)))
    result = run_program(Program(program.body + (call,)), CANONICAL)
    assert result.error is None, result.error
    return result.text


@pytest.mark.parametrize("key", list(_SPECS))
def test_write_templates_agree_with_plain_python(key):
    statement, inputs, py_ref = _SPECS[key]
    task = next(t for t in ALL_TASKS if t.id == f"write.{key}")
    program = task.build(0)
    for args in inputs:
        assert _canonical_result(program, args) == py_format(py_ref(*args)), (key, args)


@pytest.mark.parametrize("key,_b,src,inputs", TRANSLATE_CASES, ids=[c[0] for c in TRANSLATE_CASES])
def test_translate_python_snippets_match_reference(key, _b, src, inputs):
    namespace: dict = {}
    exec(src, namespace)  # trusted template text, not model output
    task = next(t for t in ALL_TASKS if t.id == f"translate.{key}")
    program = task.build(0)
    for args in inputs:
        assert _canonical_result(program, args) == py_format(namespace["solve"](*args)), (key, args)


@pytest.mark.parametrize("seed", range(5))
def test_naive_emitter_produces_python_for_reference_programs(seed):
    for task in ALL_TASKS:
        if task.tier == "predict":
            continue
        compile(to_python(task.build(0)), "<naive>", "exec")
