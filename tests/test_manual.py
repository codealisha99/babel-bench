"""The manual's examples are executed when it is generated; re-check them here."""

import pytest

from babel_bench.core import Binary, Call, ExprStmt, IntLit, Program, Unary
from babel_bench.interp import format_value, run_program
from babel_bench.manual import build_manual
from babel_bench.spec import generate
from babel_bench.syntax import parse


@pytest.mark.parametrize("seed", range(60))
def test_manual_examples_execute_to_their_stated_output(seed):
    spec = generate(seed)
    manual = build_manual(spec)
    assert len(manual.examples) >= 6
    for ex in manual.examples:
        result = run_program(parse(ex.source, spec), spec.semantics)
        assert result.error is None, ex.title
        assert result.text == ex.output, ex.title
        assert ex.output in manual.text


@pytest.mark.parametrize("seed", range(60))
def test_division_rule_in_manual_matches_interpreter(seed):
    spec = generate(seed)
    manual = build_manual(spec)
    expr = Binary("/", Unary("neg", IntLit(7)), IntLit(2))
    result = run_program(Program((ExprStmt(Call("print", (expr,))),)), spec.semantics)
    assert result.error is None
    assert f"evaluates to {result.text}" in manual.text
    assert result.text == ("-4" if spec.semantics.int_div == "floor" else "-3")


@pytest.mark.parametrize("seed", range(60))
def test_manual_states_how_strings_print_inside_lists(seed):
    spec = generate(seed)
    assert format_value(("a", 1)) == '["a", 1]'
    assert '`["a", 1]`' in build_manual(spec).text


NEWLINE_SEEDS = [s for s in range(60) if generate(s).newline_mode]


@pytest.mark.parametrize("seed", NEWLINE_SEEDS)
def test_newline_languages_say_where_else_and_block_openers_go(seed):
    spec = generate(seed)
    text = build_manual(spec).text
    assert f"`{spec.syntax.keywords['else']}` must be on the same line" in text
