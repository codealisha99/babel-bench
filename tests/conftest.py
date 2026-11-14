"""Shared helpers for property tests: a canonical semantics and a random expression generator."""

from __future__ import annotations

import random

from babel_bench.core import (
    BINARY_OPS, BoolLit, Binary, Call, IntLit, ListLit, StrLit, Unary, Var, Index,
)
from babel_bench.spec import Semantics

# Python-like behaviour: the semantics the translate tasks' Python snippets assume.
CANONICAL = Semantics(index_base=0, int_div="floor", int_mod="floor",
                      zero_is_false=True, empty_is_false=True, logic_returns_operand=False)


def random_expr(rng: random.Random, depth: int = 0):
    if depth >= 3 or rng.random() < 0.3:
        choice = rng.randrange(5)
        if choice == 0:
            return IntLit(rng.randrange(0, 50))
        if choice == 1:
            return BoolLit(rng.random() < 0.5)
        if choice == 2:
            return StrLit("ab c")
        if choice == 3:
            return Var(rng.choice(["x", "xs", "acc"]))
        return ListLit(tuple(IntLit(rng.randrange(5)) for _ in range(rng.randrange(3))))
    kind = rng.randrange(4)
    if kind == 0:
        return Unary(rng.choice(["neg", "not"]), random_expr(rng, depth + 1))
    if kind == 1:
        return Index(random_expr(rng, depth + 1), random_expr(rng, depth + 1))
    if kind == 2:
        return Call(rng.choice(["len", "str"]), (random_expr(rng, depth + 1),))
    return Binary(rng.choice(BINARY_OPS), random_expr(rng, depth + 1), random_expr(rng, depth + 1))
