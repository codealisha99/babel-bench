"""The shared core AST. Every generated language parses into it and prints from it.

Index values are *surface* values: `Index(xs, 1)` means "the value the program
writes as 1", so a language whose index base is 1 reads it as the second element.
Reference solutions are built with a base-aware helper (see tasks/common.py).
Line numbers are carried for error messages but ignored by equality, so
parse(print(ast)) == ast holds structurally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

UNARY_OPS = ("neg", "not")
BINARY_OPS = ("or", "and", "==", "!=", "<", "<=", ">", ">=", "+", "-", "*", "/", "%")
BUILTINS = {"len": 1, "append": 2, "str": 1, "print": 1}


@dataclass(frozen=True)
class IntLit:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("IntLit must be non-negative; write negatives as Unary('neg', ...)")


@dataclass(frozen=True)
class BoolLit:
    value: bool


@dataclass(frozen=True)
class StrLit:
    value: str

    def __post_init__(self) -> None:
        if '"' in self.value or "\n" in self.value:
            raise ValueError("StrLit may not contain quotes or newlines")


@dataclass(frozen=True)
class ListLit:
    items: tuple


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Unary:
    op: str
    operand: object


@dataclass(frozen=True)
class Binary:
    op: str
    left: object
    right: object


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple


@dataclass(frozen=True)
class Index:
    target: object
    index: object


def _line():
    return field(default=0, compare=False)


@dataclass(frozen=True)
class Assign:
    name: str
    value: object
    line: int = _line()


@dataclass(frozen=True)
class If:
    cond: object
    then: tuple
    orelse: tuple = ()
    line: int = _line()


@dataclass(frozen=True)
class While:
    cond: object
    body: tuple
    line: int = _line()


@dataclass(frozen=True)
class Return:
    value: object
    line: int = _line()


@dataclass(frozen=True)
class ExprStmt:
    expr: object
    line: int = _line()


@dataclass(frozen=True)
class FunDef:
    name: str
    params: tuple
    body: tuple
    line: int = _line()


@dataclass(frozen=True)
class Program:
    body: tuple
