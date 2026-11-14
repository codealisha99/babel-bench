"""Grading: extract the answer, run hidden tests in the reference interpreter."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .core import Call, ExprStmt, Program
from .interp import run_program
from .spec import LanguageSpec
from .syntax import ParseError, parse
from .tasks import Instance, py_format
from .tasks.base import value_to_expr

_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Grade:
    passed: bool
    tests_passed: int
    tests_total: int
    feedback: str
    error: str | None
    output: str


def extract_code(answer: str) -> str:
    """The last fenced block if there is one, otherwise the whole answer."""
    blocks = _FENCE.findall(answer)
    return (blocks[-1] if blocks else answer).strip("\n")


def _lines(text: str) -> list:
    return [line.rstrip() for line in text.strip().splitlines()]


def _grade_predict(inst: Instance, answer: str) -> Grade:
    passed = _lines(extract_code(answer)) == _lines(inst.expected_output)
    feedback = "" if passed else "Your reply was not the exact printed output. Reply with only the printed lines."
    return Grade(passed, int(passed), 1, feedback, None, "")


def _args_text(args: tuple) -> str:
    return ", ".join(py_format(a) for a in args)


def _describe_failure(idx: int, visible: int, args: tuple, error: str | None, got: str, expected: str) -> str:
    if idx < visible:
        if error:
            return f"solve({_args_text(args)}) failed: {error}"
        return f"solve({_args_text(args)}) returned {got} but should return {expected}."
    if error:
        return f"A hidden test failed: {error}"
    return f"A hidden test returned {got}, which is wrong."


def _grade_code(spec: LanguageSpec, inst: Instance, answer: str) -> Grade:
    try:
        program = parse(extract_code(answer), spec)
    except ParseError as exc:
        return Grade(False, 0, len(inst.tests), f"Your program has a syntax error: {exc}", str(exc), "")
    passed_count = 0
    first_failure = None
    for idx, test in enumerate(inst.tests):
        call = ExprStmt(Call("print", (Call("solve", tuple(value_to_expr(a) for a in test.args)),)))
        result = run_program(Program(program.body + (call,)), spec.semantics)
        if result.error is None and result.text.rstrip() == test.expected.rstrip():
            passed_count += 1
        elif first_failure is None:
            first_failure = (idx, test, result)
    if first_failure is None:
        return Grade(True, passed_count, len(inst.tests), "", None, "")
    idx, test, result = first_failure
    error = str(result.error) if result.error else None
    feedback = _describe_failure(idx, len(inst.visible), test.args, error, result.text, test.expected)
    return Grade(False, passed_count, len(inst.tests), feedback, error, result.text)


def grade_answer(spec: LanguageSpec, inst: Instance, answer: str) -> Grade:
    if inst.kind == "predict":
        return _grade_predict(inst, answer)
    return _grade_code(spec, inst, answer)
