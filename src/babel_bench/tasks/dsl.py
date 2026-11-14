"""Small builders so task templates read like the programs they describe."""

from __future__ import annotations

from ..core import (
    Assign, Binary, BoolLit, Call, ExprStmt, FunDef, If, Index, IntLit, ListLit,
    Program, Return, StrLit, Unary, Var, While,
)


def n(value: int):
    return IntLit(value) if value >= 0 else Unary("neg", IntLit(-value))


def v(name: str) -> Var:
    return Var(name)


def op(symbol: str, left, right) -> Binary:
    return Binary(symbol, left, right)


def at(base: int, target, index):
    """Element at a 0-based logical index, written in surface terms for `base`."""
    if base == 0:
        return Index(target, index)
    if isinstance(index, IntLit):
        return Index(target, IntLit(index.value + base))
    return Index(target, Binary("+", index, IntLit(base)))


def call(name: str, *args) -> Call:
    return Call(name, tuple(args))


def lst(*items) -> ListLit:
    return ListLit(tuple(items))


def set_(name: str, value) -> Assign:
    return Assign(name, value)


def ret(value=None) -> Return:
    return Return(value)


def if_(cond, *then, orelse=()) -> If:
    return If(cond, tuple(then), tuple(orelse))


def while_(cond, *body) -> While:
    return While(cond, tuple(body))


def show(expr) -> ExprStmt:
    return ExprStmt(Call("print", (expr,)))


def fn(name: str, params: tuple, *body) -> FunDef:
    return FunDef(name, tuple(params), tuple(body))


def prog(*stmts) -> Program:
    return Program(tuple(stmts))


def text(value: str) -> StrLit:
    return StrLit(value)


def boolean(value: bool) -> BoolLit:
    return BoolLit(value)
