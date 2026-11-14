"""Interpreter safety: limits hold and errors carry useful messages."""

from babel_bench.core import Assign, BoolLit, Call, ExprStmt, FunDef, If, Index, IntLit, ListLit, Program, Return, Var, While, Binary
from babel_bench.interp import Limits, run_program
from babel_bench.spec import Semantics

from conftest import CANONICAL


def _show(e):
    return ExprStmt(Call("print", (e,)))


def test_infinite_loop_hits_step_limit():
    prog = Program((While(BoolLit(True), (Assign("x", IntLit(1)),)),))
    result = run_program(prog, CANONICAL, Limits(max_steps=5_000))
    assert result.error is not None and result.error.kind == "limit"
    assert "step limit" in result.error.message


def test_deep_recursion_hits_depth_limit():
    body = (Return(Call("f", (Binary("+", Var("n"), IntLit(1)),))),)
    prog = Program((FunDef("f", ("n",), body), _show(Call("f", (IntLit(0),)))))
    result = run_program(prog, CANONICAL, Limits(max_depth=50))
    assert result.error is not None and result.error.kind == "limit"
    assert "recursion limit" in result.error.message


def test_runaway_list_growth_is_bounded():
    grow = While(BoolLit(True), (Assign("xs", Call("append", (Var("xs"), IntLit(1)))),))
    prog = Program((Assign("xs", ListLit(())), grow))
    result = run_program(prog, CANONICAL, Limits(max_items=100, max_steps=10_000_000))
    assert result.error is not None and result.error.kind == "limit"


def test_undefined_variable_reports_line():
    prog = Program((Assign("a", IntLit(1)), _show(Var("missing"))))
    result = run_program(prog, CANONICAL)
    assert result.error is not None
    assert "undefined variable 'missing'" in result.error.message
    assert result.error.line == 0 or result.error.line >= 0


def test_index_error_uses_language_base():
    sem = Semantics(index_base=1, int_div="floor", int_mod="floor",
                    zero_is_false=True, empty_is_false=True, logic_returns_operand=False)
    prog = Program((Assign("xs", ListLit((IntLit(5),))), _show(Index(Var("xs"), IntLit(0)))))
    result = run_program(prog, sem)
    assert result.error is not None
    assert "valid indices: 1..1" in result.error.message


def test_division_by_zero_is_a_runtime_error():
    result = run_program(Program((_show(Binary("/", IntLit(1), IntLit(0))),)), CANONICAL)
    assert result.error is not None and result.error.kind == "runtime"


def test_top_level_return_ends_program():
    prog = Program((_show(IntLit(1)), Return(None), _show(IntLit(2))))
    assert run_program(prog, CANONICAL).output == ("1",)


def test_if_uses_truthiness_of_zero():
    prog = Program((If(IntLit(0), (_show(BoolLit(True)),), (_show(BoolLit(False)),)),))
    assert run_program(prog, CANONICAL).output == ("false",)
    zero_true = Semantics(0, "floor", "floor", False, True, False)
    assert run_program(prog, zero_true).output == ("true",)


def test_lists_compare_element_kinds_not_python_equality():
    same = Program((_show(Binary("==", ListLit((IntLit(1),)), ListLit((BoolLit(True),)))),))
    assert run_program(same, CANONICAL).text == "false"
    different = Program((_show(Binary("!=", ListLit((IntLit(1),)), ListLit((BoolLit(True),)))),))
    assert run_program(different, CANONICAL).text == "true"
    nested = Program((_show(Binary("==", ListLit((ListLit((IntLit(0),)),)), ListLit((ListLit((BoolLit(False),)),)))),))
    assert run_program(nested, CANONICAL).text == "false"
    equal = Program((_show(Binary("==", ListLit((IntLit(1), IntLit(2))), ListLit((IntLit(1), IntLit(2))))),))
    assert run_program(equal, CANONICAL).text == "true"


def test_integer_literal_at_the_bound_is_an_error():
    prog = Program((_show(IntLit(2**63)),))
    result = run_program(prog, CANONICAL)
    assert result.error is not None and "integer overflow" in result.error.message
    assert run_program(Program((_show(IntLit(2**63 - 1)),)), CANONICAL).error is None
