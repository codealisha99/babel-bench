"""Task templates (language-independent) and their per-language instances.

A Task is a template: a builder that produces the reference program for a given
index base, plus hidden test inputs. `instantiate` binds it to one language:
it prints the reference in that language, runs it on every test input to get the
expected outputs, and records the oracle and naive baseline answers. A task
whose reference fails to run in some language raises TaskBroken, so broken
tasks cannot silently enter a run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..core import BoolLit, Call, ExprStmt, IntLit, ListLit, Program, StrLit, Unary
from ..interp import run_program
from ..printer import to_python, to_source
from ..spec import LanguageSpec

VISIBLE_EXAMPLES = 2


class TaskBroken(RuntimeError):
    """The reference solution does not run cleanly in a generated language."""


@dataclass(frozen=True)
class Task:
    id: str
    tier: str  # predict, translate, write, fix
    title: str
    statement: str
    build: Callable[[int], Program]  # base -> reference program
    inputs: tuple = ()  # argument tuples for solve(...); empty for predict tasks
    py_ref: Callable | None = None  # plain-Python ground truth for the correct behaviour
    buggy: Callable[[int], Program] | None = None  # fix tasks: the broken program
    python_src: str | None = None  # translate tasks: the Python to translate


@dataclass(frozen=True)
class Test:
    args: tuple
    expected: str


@dataclass(frozen=True)
class Instance:
    task_id: str
    tier: str
    title: str
    statement: str
    kind: str  # "predict" or "code"
    shown: str  # program or Python text shown to the model ("" if none)
    visible: tuple
    tests: tuple
    expected_output: str
    oracle_answer: str
    naive_answer: str


def value_to_expr(value):
    if isinstance(value, bool):
        return BoolLit(value)
    if isinstance(value, int):
        return IntLit(value) if value >= 0 else Unary("neg", IntLit(-value))
    if isinstance(value, str):
        return StrLit(value)
    return ListLit(tuple(value_to_expr(x) for x in value))


def _fenced(code: str, tag: str = "") -> str:
    return f"```{tag}\n{code.rstrip()}\n```"


def instantiate(task: Task, spec: LanguageSpec) -> Instance:
    base, sem = spec.semantics.index_base, spec.semantics
    ref = task.build(base)
    if task.tier == "predict":
        result = run_program(ref, sem)
        if result.error:
            raise TaskBroken(f"{task.id} in {spec.name}: {result.error}")
        return Instance(
            task.id, task.tier, task.title, task.statement, "predict",
            shown=to_source(ref, spec), visible=(), tests=(),
            expected_output=result.text, oracle_answer=_fenced(result.text),
            naive_answer="",
        )
    tests = []
    for args in task.inputs:
        call = ExprStmt(Call("print", (Call("solve", tuple(value_to_expr(a) for a in args)),)))
        result = run_program(Program(ref.body + (call,)), sem)
        if result.error:
            raise TaskBroken(f"{task.id} on {args} in {spec.name}: {result.error}")
        tests.append(Test(args, result.text))
    if task.buggy is not None:
        shown = to_source(task.buggy(base), spec)
    else:
        shown = task.python_src or ""
    naive = task.python_src if task.python_src else to_python(task.build(0))
    return Instance(
        task.id, task.tier, task.title, task.statement, "code",
        shown=shown, visible=tuple(tests[:VISIBLE_EXAMPLES]), tests=tuple(tests),
        expected_output="", oracle_answer=_fenced(to_source(ref, spec)),
        naive_answer=_fenced(naive, "python"),
    )


def py_format(value) -> str:
    """Python value -> canonical language rendering (used to check templates)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    return "[" + ", ".join(f'"{x}"' if isinstance(x, str) else py_format(x) for x in value) + "]"
