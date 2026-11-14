"""Predict tier: the program is given in the language; reply with what it prints."""

from __future__ import annotations

from ..core import Index, IntLit, Program, Unary
from .base import Task
from .dsl import boolean, call, fn, if_, lst, n, op, prog, ret, set_, show, text, v, while_

STATEMENT = ("The program below is written in the language. Work out exactly what it prints and reply with "
             "its output, one line per printed value, and nothing else.")


def _squares(base: int) -> Program:
    # Negated squares divided by 3: the quotient rounds by the language's division rule.
    return prog(set_("i", n(1)),
                while_(op("<=", v("i"), n(4)),
                       show(op("/", Unary("neg", op("*", v("i"), v("i"))), IntLit(3))),
                       set_("i", op("+", v("i"), n(1)))))


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
    # The program writes surface indices 1 and 2: they name different elements under base 0 and base 1.
    xs = lst(n(10), n(20), n(30))
    return prog(set_("xs", xs), show(Index(v("xs"), IntLit(1))),
                show(Index(v("xs"), IntLit(2))), show(Index(v("xs"), IntLit(1))))


def _logic(base: int) -> Program:
    return prog(show(op("or", n(0), n(5))), show(op("and", boolean(True), n(0))),
                show(op("and", n(1), n(2))), show(op("or", boolean(False), boolean(False))))


def _recursion(base: int) -> Program:
    # Each step adds (-k) / 2 (rounding rule) and recurses on k - 3; g(7) is -7 or -5 depending on the language.
    return prog(fn("g", ("k",),
                   if_(op("<=", v("k"), n(0)), ret(n(0))),
                   ret(op("+", op("/", Unary("neg", v("k")), IntLit(2)), call("g", op("-", v("k"), n(3)))))),
                show(call("g", n(7))))


_CASES = (
    ("squares", _squares), ("division", _division), ("truthiness", _truthiness),
    ("indexing", _indexing), ("logic", _logic), ("recursion", _recursion),
)

PREDICT_TASKS = tuple(
    Task(id=f"predict.{key}", tier="predict", title=key, statement=STATEMENT, build=builder)
    for key, builder in _CASES
)
