"""Grading worker: one visitor program, graded in a fresh process that the API can kill.

Reads one JSON request on stdin ({"seed", "task_id", "program"}) and writes one JSON result on
stdout. The only code it runs is the generated interpreter, which has no host access (see
interp.py). Memory is capped here; wall-clock time is enforced by the parent with a kill.
"""

from __future__ import annotations

import dataclasses
import json
import re
import resource
import sys

from ..grade import extract_code, grade_answer
from ..interp import Limits, run_program
from ..spec import generate
from ..syntax import ParseError, parse
from ..tasks import instantiate, select

MEMORY_BYTES = 1 << 30
MAX_TEXT_CHARS = 2_000
PLAY_LIMITS = Limits(max_seconds=1.0)  # per run; the parent's timeout covers the whole request


def _limit_memory() -> None:
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    except (ValueError, OSError):  # some platforms do not enforce it; the parent timeout still applies
        pass


def _clip(text: str) -> str:
    return text if len(text) <= MAX_TEXT_CHARS else text[:MAX_TEXT_CHARS] + "...(truncated)"


def _output_of_program(program: str, spec) -> tuple:
    """What the program prints by itself, without calling solve: (output, error text, error line)."""
    try:
        tree = parse(extract_code(program), spec)
    except ParseError:
        return "", None, None
    result = run_program(tree, spec.semantics, PLAY_LIMITS)
    line = getattr(result.error, "line", 0) or None
    return result.text, (str(result.error) if result.error else None), line


_LINE_PREFIX = re.compile(r"line \d+: ")  # the line is returned separately as error_line


def _without_line(text: str | None) -> str | None:
    return _LINE_PREFIX.sub("", text) if text else text


def _line_in_program(program: str, line: int | None) -> int | None:
    """Map a line of the extracted answer onto the program as the visitor typed it (fences add lines)."""
    if not line:
        return None
    start = program.rfind(extract_code(program))
    return line + program[:start].count("\n") if start > 0 else line


def _test_row(outcome, program: str) -> dict:
    row = dataclasses.asdict(outcome)
    row["line"] = _line_in_program(program, row["line"])
    row["got"], row["expected"] = _clip(row["got"]), _clip(row["expected"])
    row["error"] = _clip(_without_line(row["error"])) if row["error"] else None
    return row


def grade(request: dict) -> dict:
    spec = generate(request["seed"])
    inst = instantiate(select((request["task_id"],))[0], spec)
    program = request["program"]
    try:
        grade_result = grade_answer(spec, inst, program)
    except RecursionError:
        return {"passed": False, "tests_passed": 0, "tests_total": len(inst.tests),
                "feedback": "Your program is nested too deeply to parse.", "output": "", "error": "nesting",
                "error_line": None, "tests": []}
    output, error, output_line = _output_of_program(program, spec)
    error_line = _line_in_program(program, grade_result.error_line or output_line)
    return {
        "passed": grade_result.passed, "tests_passed": grade_result.tests_passed,
        "tests_total": grade_result.tests_total, "feedback": _clip(_without_line(grade_result.feedback)),
        "output": _clip(output), "error": _without_line(error), "error_line": error_line,
        "tests": [_test_row(o, program) for o in grade_result.outcomes],
    }


def main() -> int:
    _limit_memory()
    request = json.load(sys.stdin)
    sys.stdout.write(json.dumps(grade(request)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
