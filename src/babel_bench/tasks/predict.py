"""Predict tier: the program is given in the language; reply with what it prints."""

from __future__ import annotations

from ..core import IntLit, Program, Unary
from .base import Task
from .dsl import at, boolean, call, fn, if_, lst, n, op, prog, ret, set_, show, text, v, while_

STATEMENT = ("The program below is written in the language. Work out exactly what it prints and reply with "
             "its output, one line per printed value, and nothing else.")


def _squares(base: int) -> Program:
    return prog(set_("i", n(1)),
                while_(op("<=", v("i"), n(4)), show(op("*", v("i"), v("i"))), set_("i", op("+", v("i"), n(1)))))


def _division(base: int) -> Program:
    return prog(show(op("/", Unary("neg", IntLit(7)), IntLit(2))),
                show(op("%", Unary("neg", IntLit(7)), IntLit(3))),
                show(op("/", IntLit(7), Unary("neg", IntLit(2)))),
                show(op("%", IntLit(7), Unary("neg", IntLit(3)))))


def _truthiness(base: int) -> Program:
    return prog(if_(n(0), show(text("A")), orelse=(show(text("B")),)),
                if_(lst(), show(text("C")), orelse=(show(text("D")),)),
                if_(text(""), show(text("E")), orelse=(show(text("F")),)))


def _indexing(base: int) -> Program:
    xs = lst(n(10), n(20), n(30))
    return prog(set_("xs", xs), show(at(base, v("xs"), n(0))),
                show(at(base, v("xs"), n(2))), show(at(base, v("xs"), n(1))))


def _logic(base: int) -> Program:
    return prog(show(op("or", n(0), n(5))), show(op("and", boolean(True), n(0))),
                show(op("and", n(1), n(2))), show(op("or", boolean(False), boolean(False))))


def _recursion(base: int) -> Program:
    return prog(fn("fact", ("k",),
                   if_(op("<=", v("k"), n(1)), ret(n(1))),
                   ret(op("*", v("k"), call("fact", op("-", v("k"), n(1)))))),
                show(call("fact", n(5))))


_CASES = (
    ("squares", _squares), ("division", _division), ("truthiness", _truthiness),
    ("indexing", _indexing), ("logic", _logic), ("recursion", _recursion),
)

PREDICT_TASKS = tuple(
    Task(id=f"predict.{key}", tier="read", title=key, statement=STATEMENT, build=builder)
    for key, builder in _CASES
)
