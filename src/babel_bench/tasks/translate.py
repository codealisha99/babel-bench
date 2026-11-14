"""Translate tier: a Python function is given; reproduce its behaviour in the language.

The Python snippets use only non-negative inputs where integer division or
modulo could differ between languages, and explicit comparisons instead of
truthiness, so the Python text is a complete specification.
"""

from __future__ import annotations

from ..core import Program
from .base import Task
from .dsl import at, call, fn, if_, n, op, prog, ret, set_, v, while_


def _gcd(base: int) -> Program:
    return prog(fn("solve", ("a", "b"),
        while_(op("!=", v("b"), n(0)),
               set_("t", v("b")), set_("b", op("%", v("a"), v("b"))), set_("a", v("t"))),
        ret(v("a"))))


def _power(base: int) -> Program:
    return prog(fn("solve", ("b", "e"),
        set_("r", n(1)), set_("i", n(0)),
        while_(op("<", v("i"), v("e")),
               set_("r", op("*", v("r"), v("b"))), set_("i", op("+", v("i"), n(1)))),
        ret(v("r"))))


def _sum_digits(base: int) -> Program:
    return prog(fn("solve", ("n",),
        set_("s", n(0)),
        while_(op("!=", v("n"), n(0)),
               set_("s", op("+", v("s"), op("%", v("n"), n(10)))),
               set_("n", op("/", v("n"), n(10)))),
        ret(v("s"))))


def _sum_list(base: int) -> Program:
    return prog(fn("solve", ("xs",),
        set_("total", n(0)), set_("i", n(0)),
        while_(op("<", v("i"), call("len", v("xs"))),
               set_("total", op("+", v("total"), at(base, v("xs"), v("i")))),
               set_("i", op("+", v("i"), n(1)))),
        ret(v("total"))))


def _clamp(base: int) -> Program:
    return prog(fn("solve", ("x", "lo", "hi"),
        if_(op("<", v("x"), v("lo")), ret(v("lo"))),
        if_(op(">", v("x"), v("hi")), ret(v("hi"))),
        ret(v("x"))))


def _collatz(base: int) -> Program:
    return prog(fn("solve", ("n",),
        set_("steps", n(0)),
        while_(op("!=", v("n"), n(1)),
               if_(op("==", op("%", v("n"), n(2)), n(0)),
                   set_("n", op("/", v("n"), n(2))),
                   orelse=(set_("n", op("+", op("*", n(3), v("n")), n(1))),)),
               set_("steps", op("+", v("steps"), n(1)))),
        ret(v("steps"))))


_CASES = (
    ("gcd", _gcd, """def solve(a, b):
    while b != 0:
        t = b
        b = a % b
        a = t
    return a
""", ((12, 18), (7, 0), (0, 5), (17, 5), (100, 75))),
    ("power", _power, """def solve(b, e):
    r = 1
    i = 0
    while i < e:
        r = r * b
        i = i + 1
    return r
""", ((2, 10), (3, 0), (5, 3), (0, 4), (-2, 3), (10, 2))),
    ("sum_digits", _sum_digits, """def solve(n):
    s = 0
    while n != 0:
        s = s + n % 10
        n = n // 10
    return s
""", ((1234,), (0,), (7,), (9099,), (100,))),
    ("sum_list", _sum_list, """def solve(xs):
    total = 0
    i = 0
    while i < len(xs):
        total = total + xs[i]
        i = i + 1
    return total
""", (((1, 2, 3),), ((),), ((-4, 10),), ((7,),))),
    ("clamp", _clamp, """def solve(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
""", ((-5, 0, 10), (3, 0, 10), (15, 0, 10), (0, 0, 0))),
    ("collatz_steps", _collatz, """def solve(n):
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps = steps + 1
    return steps
""", ((1,), (6,), (7,), (27,), (2,))),
)

TRANSLATE_TASKS = tuple(
    Task(
        id=f"translate.{key}", tier="translate", title=key.replace("_", " "),
        statement=("Rewrite the Python function below in the language so that it behaves identically. "
                   "Use only the language's own constructs and conventions."),
        build=builder, inputs=inputs, python_src=src,
    )
    for key, builder, src, inputs in _CASES
)
