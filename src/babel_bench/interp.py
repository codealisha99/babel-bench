"""Interpreter for the core AST under a language's Semantics, with hard limits.

Programs are data: there is no host access, no imports, no file or network
I/O. The only effect is `print`. Limits bound steps, call depth, collection
sizes, string sizes, output lines, and wall-clock time, so a model's program
cannot hang or exhaust memory in the grader.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .core import (
    Assign, Binary, BoolLit, Call, ExprStmt, FunDef, If, Index, IntLit, ListLit,
    Program, Return, StrLit, Unary, Var, While, BUILTINS,
)
from .spec import Semantics

INT_LIMIT = 2**63


@dataclass(frozen=True)
class Limits:
    max_steps: int = 200_000
    max_depth: int = 100
    max_items: int = 10_000
    max_string: int = 100_000
    max_output_lines: int = 1_000
    max_seconds: float = 2.0


class LangError(Exception):
    """A runtime error. kind is 'runtime' (the program's fault) or 'limit' (a bound was hit)."""

    def __init__(self, message: str, line: int = 0, kind: str = "runtime") -> None:
        where = f"line {line}: " if line else ""
        super().__init__(f"{where}{message}")
        self.message = message
        self.line = line
        self.kind = kind


class _Return(Exception):
    def __init__(self, value) -> None:
        super().__init__()
        self.value = value


@dataclass(frozen=True)
class RunResult:
    output: tuple
    error: LangError | None

    @property
    def text(self) -> str:
        return "\n".join(self.output)


def format_value(v) -> str:
    """Canonical rendering used by print and by expected outputs."""
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return v
    return "[" + ", ".join(f'"{x}"' if isinstance(x, str) else format_value(x) for x in v) + "]"


def _trunc_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _kind(v) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, str):
        return "string"
    return "list"


class Interpreter:
    def __init__(self, sem: Semantics, limits: Limits = Limits()) -> None:
        self.sem = sem
        self.limits = limits
        self.steps = 0
        self.depth = 0
        self.line = 0
        self.functions: dict = {}
        self.output: list[str] = []
        self.started = time.monotonic()

    # bookkeeping ---------------------------------------------------------
    def fail(self, message: str) -> LangError:
        return LangError(message, self.line)

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.limits.max_steps:
            raise LangError(f"step limit of {self.limits.max_steps} exceeded (infinite loop?)", self.line, "limit")
        if self.steps % 4096 == 0 and time.monotonic() - self.started > self.limits.max_seconds:
            raise LangError("time limit exceeded", self.line, "limit")

    def check_items(self, n: int) -> None:
        if n > self.limits.max_items:
            raise LangError(f"list longer than {self.limits.max_items} items", self.line, "limit")

    def check_int(self, n: int) -> int:
        if abs(n) >= INT_LIMIT:
            raise self.fail("integer overflow")
        return n

    # values --------------------------------------------------------------
    def truthy(self, v) -> bool:
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return not (self.sem.zero_is_false and v == 0)
        if self.sem.empty_is_false and len(v) == 0:
            return False
        return True

    def int_div(self, a: int, b: int) -> int:
        if b == 0:
            raise self.fail("division by zero")
        if self.sem.int_div == "floor":
            return a // b
        return _trunc_div(a, b)

    def int_mod(self, a: int, b: int) -> int:
        if b == 0:
            raise self.fail("modulo by zero")
        if self.sem.int_mod == "floor":
            return a % b
        return a - b * _trunc_div(a, b)

    # expressions ---------------------------------------------------------
    def eval(self, e, env: dict):
        self.tick()
        if isinstance(e, IntLit):
            return e.value
        if isinstance(e, BoolLit):
            return e.value
        if isinstance(e, StrLit):
            return e.value
        if isinstance(e, ListLit):
            items = tuple(self.eval(x, env) for x in e.items)
            self.check_items(len(items))
            return items
        if isinstance(e, Var):
            if e.name not in env:
                raise self.fail(f"undefined variable '{e.name}'")
            return env[e.name]
        if isinstance(e, Unary):
            return self.unary(e, env)
        if isinstance(e, Binary):
            return self.binary(e, env)
        if isinstance(e, Index):
            return self.index(e, env)
        if isinstance(e, Call):
            return self.call(e, env)
        raise self.fail(f"cannot evaluate {type(e).__name__}")

    def unary(self, e: Unary, env: dict):
        v = self.eval(e.operand, env)
        if e.op == "not":
            return not self.truthy(v)
        if not isinstance(v, int) or isinstance(v, bool):
            raise self.fail(f"'-' expects an int, got {_kind(v)}")
        return -v

    def binary(self, e: Binary, env: dict):
        op = e.op
        if op in ("and", "or"):
            left = self.eval(e.left, env)
            if self.truthy(left) == (op == "or"):
                return left if self.sem.logic_returns_operand else self.truthy(left)
            right = self.eval(e.right, env)
            return right if self.sem.logic_returns_operand else self.truthy(right)
        a = self.eval(e.left, env)
        b = self.eval(e.right, env)
        if op in ("==", "!="):
            if _kind(a) != _kind(b):
                raise self.fail(f"cannot compare {_kind(a)} with {_kind(b)}")
            return (a == b) == (op == "==")
        if op in ("<", "<=", ">", ">="):
            if _kind(a) != _kind(b) or _kind(a) not in ("int", "string"):
                raise self.fail(f"'{op}' needs two ints or two strings, got {_kind(a)} and {_kind(b)}")
            return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
        if op == "+" and _kind(a) == "string" and _kind(b) == "string":
            if len(a) + len(b) > self.limits.max_string:
                raise self.fail("string longer than the limit")
            return a + b
        if _kind(a) != "int" or _kind(b) != "int":
            raise self.fail(f"'{op}' needs two ints, got {_kind(a)} and {_kind(b)}")
        if op == "+":
            return self.check_int(a + b)
        if op == "-":
            return self.check_int(a - b)
        if op == "*":
            return self.check_int(a * b)
        if op == "/":
            return self.int_div(a, b)
        return self.int_mod(a, b)

    def index(self, e: Index, env: dict):
        target = self.eval(e.target, env)
        i = self.eval(e.index, env)
        if _kind(target) not in ("list", "string"):
            raise self.fail(f"cannot index a {_kind(target)}")
        if _kind(i) != "int":
            raise self.fail(f"index must be an int, got {_kind(i)}")
        pos = i - self.sem.index_base
        if not 0 <= pos < len(target):
            valid = f"{self.sem.index_base}..{len(target) - 1 + self.sem.index_base}"
            raise self.fail(f"index {i} out of range (valid indices: {valid}, length {len(target)})")
        return target[pos]

    def call(self, e: Call, env: dict):
        args = tuple(self.eval(a, env) for a in e.args)
        if e.name in BUILTINS:
            return self.builtin(e.name, args)
        fn = self.functions.get(e.name)
        if fn is None:
            raise self.fail(f"undefined function '{e.name}'")
        if len(args) != len(fn.params):
            raise self.fail(f"'{e.name}' expects {len(fn.params)} arguments, got {len(args)}")
        self.depth += 1
        if self.depth > self.limits.max_depth:
            raise LangError(f"recursion limit of {self.limits.max_depth} exceeded", self.line, "limit")
        local = dict(zip(fn.params, args, strict=True))
        try:
            self.run_block(fn.body, local)
        except _Return as ret:
            return ret.value
        finally:
            self.depth -= 1
        return None

    def builtin(self, name: str, args: tuple):
        if len(args) != BUILTINS[name]:
            raise self.fail(f"'{name}' expects {BUILTINS[name]} argument(s), got {len(args)}")
        if name == "len":
            if _kind(args[0]) not in ("list", "string"):
                raise self.fail(f"len() needs a list or string, got {_kind(args[0])}")
            return len(args[0])
        if name == "append":
            if _kind(args[0]) != "list":
                raise self.fail(f"append() needs a list, got {_kind(args[0])}")
            self.check_items(len(args[0]) + 1)
            return args[0] + (args[1],)
        if name == "str":
            return format_value(args[0])
        self.emit(format_value(args[0]))
        return None

    def emit(self, line: str) -> None:
        if len(self.output) >= self.limits.max_output_lines:
            raise LangError("output limit exceeded", self.line, "limit")
        self.output.append(line)

    # statements ----------------------------------------------------------
    def run_block(self, stmts: tuple, env: dict) -> None:
        for s in stmts:
            self.exec(s, env)

    def exec(self, s, env: dict) -> None:
        self.tick()
        if getattr(s, "line", 0):
            self.line = s.line
        if isinstance(s, Assign):
            env[s.name] = self.eval(s.value, env)
        elif isinstance(s, ExprStmt):
            self.eval(s.expr, env)
        elif isinstance(s, Return):
            raise _Return(None if s.value is None else self.eval(s.value, env))
        elif isinstance(s, If):
            branch = s.then if self.truthy(self.eval(s.cond, env)) else s.orelse
            self.run_block(branch, env)
        elif isinstance(s, While):
            while self.truthy(self.eval(s.cond, env)):
                self.run_block(s.body, env)
        elif isinstance(s, FunDef):
            self.functions[s.name] = s
        else:
            raise self.fail(f"cannot execute {type(s).__name__}")

    def run(self, program: Program) -> tuple:
        for s in program.body:
            if isinstance(s, FunDef):
                self.functions[s.name] = s
        env: dict = {}
        try:
            self.run_block(program.body, env)
        except _Return:
            pass  # a top-level return simply ends the program
        return tuple(self.output)


def run_program(program: Program, sem: Semantics, limits: Limits = Limits()) -> RunResult:
    """Run to completion or to the first error; never raises for program faults."""
    interp = Interpreter(sem, limits)
    try:
        return RunResult(interp.run(program), None)
    except LangError as err:
        return RunResult(tuple(interp.output), err)
    except RecursionError:
        err = LangError("recursion limit exceeded", interp.line, "limit")
        return RunResult(tuple(interp.output), err)
