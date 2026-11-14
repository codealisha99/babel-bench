"""Language generation, printing and parsing: round trips and syntax errors."""

import random

import pytest

from babel_bench.core import ExprStmt, Program
from babel_bench.printer import to_source
from babel_bench.spec import RESERVED_IDENTIFIERS, generate
from babel_bench.syntax import ParseError, parse
from babel_bench.tasks import ALL_TASKS

from conftest import random_expr

SEEDS = range(40)


def test_generation_is_deterministic():
    assert generate(7) == generate(7)
    assert generate(7) != generate(8)


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_surface_words_never_shadow_identifiers(seed):
    spec = generate(seed)
    words = spec.reserved_words()
    assert not (words & RESERVED_IDENTIFIERS)
    assert len(set(spec.syntax.keywords.values())) == len(spec.syntax.keywords)


@pytest.mark.parametrize("seed", SEEDS)
def test_reference_programs_round_trip(seed):
    spec = generate(seed)
    for task in ALL_TASKS:
        program = task.build(spec.semantics.index_base)
        assert parse(to_source(program, spec), spec) == program, task.id
        if task.buggy is not None:
            buggy = task.buggy(spec.semantics.index_base)
            assert parse(to_source(buggy, spec), spec) == buggy, task.id


@pytest.mark.parametrize("seed", range(10))
def test_random_expressions_round_trip(seed):
    spec = generate(seed)
    rng = random.Random(seed)
    for _ in range(150):
        program = Program((ExprStmt(random_expr(rng)),))
        assert parse(to_source(program, spec), spec) == program


def test_huge_integer_literal_is_a_parse_error_not_a_crash():
    spec = generate(3)
    with pytest.raises(ParseError) as info:
        parse("9" * 5000, spec)
    assert info.value.line == 1


def test_syntax_error_reports_line_number():
    spec = generate(3)
    with pytest.raises(ParseError) as info:
        parse("\n\n" + spec.syntax.keywords["fn"] + " 5(", spec)
    assert info.value.line == 3
    assert "expected" in info.value.detail
