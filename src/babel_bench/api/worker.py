"""Grading worker: one visitor program, graded in a fresh process that the API can kill.

Reads one JSON request on stdin ({"seed", "task_id", "program"}) and writes one JSON result on
stdout. The only code it runs is the generated interpreter, which has no host access (see
interp.py). Memory is capped here; wall-clock time is enforced by the parent with a kill.
"""

from __future__ import annotations

import json
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
    """What the program prints by itself, without calling solve."""
    try:
        tree = parse(extract_code(program), spec)
    except ParseError:
        return "", None
    result = run_program(tree, spec.semantics, PLAY_LIMITS)
    return result.text, (str(result.error) if result.error else None)


def grade(request: dict) -> dict:
    spec = generate(request["seed"])
    inst = instantiate(select((request["task_id"],))[0], spec)
    program = request["program"]
    try:
        grade_result = grade_answer(spec, inst, program)
    except RecursionError:
        return {"passed": False, "tests_passed": 0, "tests_total": len(inst.tests),
                "feedback": "Your program is nested too deeply to parse.", "output": "", "error": "nesting"}
    output, error = _output_of_program(program, spec)
    return {
        "passed": grade_result.passed, "tests_passed": grade_result.tests_passed,
        "tests_total": grade_result.tests_total, "feedback": _clip(grade_result.feedback),
        "output": _clip(output), "error": error,
    }


def main() -> int:
    _limit_memory()
    request = json.load(sys.stdin)
    sys.stdout.write(json.dumps(grade(request)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
