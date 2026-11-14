"""Reference algorithms for the write and fix tiers. Each takes (base, bug)."""

from __future__ import annotations

from ..core import BoolLit, Program
from .dsl import at, call, fn, if_, lst, n, op, prog, ret, set_, v, while_


def sum_to(base: int, bug: bool = False) -> Program:
    cmp = "<" if bug else "<="
    return prog(fn("solve", ("n",),
        set_("acc", n(0)), set_("i", n(1)),
        while_(op(cmp, v("i"), v("n")),
               set_("acc", op("+", v("acc"), v("i"))),
               set_("i", op("+", v("i"), n(1)))),
        ret(v("acc"))))


def count_digits(base: int, bug: bool = False) -> Program:
    cmp = ">" if bug else ">="
    return prog(fn("solve", ("n",),
        set_("count", n(1)), set_("m", v("n")),
        while_(op(cmp, v("m"), n(10)),
               set_("m", op("/", v("m"), n(10))),
               set_("count", op("+", v("count"), n(1)))),
        ret(v("count"))))


def max_of(base: int, bug: bool = False) -> Program:
    start = n(0) if bug else at(base, v("xs"), n(0))
    return prog(fn("solve", ("xs",),
        set_("best", start), set_("i", n(1)),
        while_(op("<", v("i"), call("len", v("xs"))),
               if_(op(">", at(base, v("xs"), v("i")), v("best")),
                   set_("best", at(base, v("xs"), v("i")))),
               set_("i", op("+", v("i"), n(1)))),
        ret(v("best"))))


def is_prime(base: int, bug: bool = False) -> Program:
    cmp = "<" if bug else "<="
    return prog(fn("solve", ("n",),
        if_(op("<", v("n"), n(2)), ret(_false())),
        set_("d", n(2)),
        while_(op(cmp, op("*", v("d"), v("d")), v("n")),
               if_(op("==", op("%", v("n"), v("d")), n(0)), ret(_false())),
               set_("d", op("+", v("d"), n(1)))),
        ret(_true())))


def bsearch(base: int, bug: bool = False) -> Program:
    else_hi = v("mid") if bug else op("-", v("mid"), n(1))
    return prog(fn("solve", ("xs", "t"),
        set_("lo", n(0)), set_("hi", op("-", call("len", v("xs")), n(1))),
        while_(op("<=", v("lo"), v("hi")),
               set_("mid", op("/", op("+", v("lo"), v("hi")), n(2))),
               set_("x", at(base, v("xs"), v("mid"))),
               if_(op("==", v("x"), v("t")), ret(v("mid"))),
               if_(op("<", v("x"), v("t")),
                   set_("lo", op("+", v("mid"), n(1))),
                   orelse=(set_("hi", else_hi),))),
        ret(n(-1))))


def reverse(base: int, bug: bool = False) -> Program:
    start = call("len", v("xs")) if bug else op("-", call("len", v("xs")), n(1))
    return prog(fn("solve", ("xs",),
        set_("out", lst()), set_("i", start),
        while_(op(">=", v("i"), n(0)),
               set_("out", call("append", v("out"), at(base, v("xs"), v("i")))),
               set_("i", op("-", v("i"), n(1)))),
        ret(v("out"))))


def _true() -> BoolLit:
    return BoolLit(True)


def _false() -> BoolLit:
    return BoolLit(False)
