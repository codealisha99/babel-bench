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
class TestOutcome:
    """One hidden or visible test. Hidden tests carry no arguments, expectation or output."""

    label: str  # "solve(5)" for a visible test, "hidden test 3" otherwise
    visible: bool
    passed: bool
    got: str = ""
    expected: str = ""
    error: str | None = None
    line: int | None = None  # 1-based line in the answer where a runtime error was raised


@dataclass(frozen=True)
class Grade:
    passed: bool
    tests_passed: int
    tests_total: int
    feedback: str
    error: str | None
    output: str
    outcomes: tuple = ()
    error_line: int | None = None  # 1-based line in the answer for a parse or runtime error


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


def _error_line(result) -> int | None:
    return getattr(result.error, "line", 0) or None


def _outcome(idx: int, visible: bool, test, result) -> TestOutcome:
    passed = result.error is None and result.text.rstrip() == test.expected.rstrip()
    if not visible:
        return TestOutcome(f"hidden test {idx + 1}", False, passed, error=_error_text(result), line=_error_line(result))
    return TestOutcome(
        f"solve({_args_text(test.args)})", True, passed, got=result.text.rstrip(),
        expected=test.expected.rstrip(), error=_error_text(result), line=_error_line(result),
    )


def _error_text(result) -> str | None:
    return str(result.error) if result.error else None


def _grade_code(spec: LanguageSpec, inst: Instance, answer: str) -> Grade:
    try:
        program = parse(extract_code(answer), spec)
    except ParseError as exc:
        return Grade(False, 0, len(inst.tests), f"Your program has a syntax error: {exc}", str(exc), "",
                     error_line=exc.line or None)
    outcomes = []
    first_failure = None
    for idx, test in enumerate(inst.tests):
        call = ExprStmt(Call("print", (Call("solve", tuple(value_to_expr(a) for a in test.args)),)))
        result = run_program(Program(program.body + (call,)), spec.semantics)
        outcome = _outcome(idx, idx < len(inst.visible), test, result)
        outcomes.append(outcome)
        if not outcome.passed and first_failure is None:
            first_failure = (idx, test, result)
    passed_count = sum(o.passed for o in outcomes)
    if first_failure is None:
        return Grade(True, passed_count, len(inst.tests), "", None, "", outcomes=tuple(outcomes))
    idx, test, result = first_failure
    error = _error_text(result)
    feedback = _describe_failure(idx, len(inst.visible), test.args, error, result.text, test.expected)
    return Grade(False, passed_count, len(inst.tests), feedback, error, result.text,
                 outcomes=tuple(outcomes), error_line=_error_line(result))


def grade_answer(spec: LanguageSpec, inst: Instance, answer: str) -> Grade:
    if inst.kind == "predict":
        return _grade_predict(inst, answer)
    return _grade_code(spec, inst, answer)
