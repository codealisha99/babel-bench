"""Write and fix tiers: same six algorithms; fix tasks carry a bug-injected twin."""

from __future__ import annotations

from functools import partial

from . import algorithms as alg
from .base import Task

_SPECS = {
    "sum_to": (
        "Define solve(n) returning 1 + 2 + ... + n for a non-negative integer n (0 when n is 0).",
        ((5,), (0,), (1,), (10,), (25,), (2,)),
        lambda n: n * (n + 1) // 2,
    ),
    "count_digits": (
        "Define solve(n) returning how many decimal digits the non-negative integer n has (0 has one digit).",
        ((7,), (10,), (0,), (99,), (12345,), (100,)),
        lambda n: len(str(n)),
    ),
    "max_of": (
        "Define solve(xs) returning the largest element of the non-empty list xs. Lists may contain negative numbers.",
        (((3, 1, 4),), ((-3, -7),), ((5,),), ((2, 9, 9, 1),), ((-1, -5, -2),), ((0,),)),
        lambda xs: max(xs),
    ),
    "is_prime": (
        "Define solve(n) returning true if the non-negative integer n is prime, otherwise false. 0 and 1 are not prime.",
        ((4,), (0,), (1,), (2,), (9,), (97,), (21,)),
        lambda n: n >= 2 and all(n % d for d in range(2, int(n ** 0.5) + 1)),
    ),
    "bsearch": (
        "Define solve(xs, t). xs is a list of distinct integers sorted ascending. Return the 0-based position of t "
        "in xs, or -1 if t is absent. The answer is always 0-based, whatever the language's index base.",
        (((1, 3, 5, 7), 5), ((1, 3, 5, 7), 1), ((1, 3, 5, 7), 7), ((1, 3, 5, 7), 4),
         ((2,), 2), ((), 3), ((1, 3, 5, 7), 0)),
        lambda xs, t: list(xs).index(t) if t in xs else -1,
    ),
    "reverse": (
        "Define solve(xs) returning a new list holding the elements of xs in reverse order.",
        (((1, 2, 3),), ((),), ((7,),), ((4, -2, 9, 0),)),
        lambda xs: tuple(reversed(xs)),
    ),
}
_BUILDERS = {
    "sum_to": alg.sum_to, "count_digits": alg.count_digits, "max_of": alg.max_of,
    "is_prime": alg.is_prime, "bsearch": alg.bsearch, "reverse": alg.reverse,
}


def _write_tasks() -> tuple:
    out = []
    for key, (statement, inputs, ref) in _SPECS.items():
        builder = _BUILDERS[key]
        out.append(Task(
            id=f"write.{key}", tier="write", title=key.replace("_", " "),
            statement=statement, build=partial(builder, bug=False),
            inputs=inputs, py_ref=ref,
        ))
    return tuple(out)


def _fix_tasks() -> tuple:
    out = []
    for key, (statement, inputs, ref) in _SPECS.items():
        builder = _BUILDERS[key]
        out.append(Task(
            id=f"fix.{key}", tier="fix", title=key.replace("_", " "),
            statement=statement + " The program shown below was meant to do this but has one bug; "
                      "reply with the complete corrected program.",
            build=partial(builder, bug=False), inputs=inputs, py_ref=ref,
            buggy=partial(builder, bug=True),
        ))
    return tuple(out)


WRITE_TASKS = _write_tasks()
FIX_TASKS = _fix_tasks()
