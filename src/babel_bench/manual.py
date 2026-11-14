"""Auto-generated plain-English reference manual for one language.

Every example is built as a core AST, printed in the language, then executed.
The manual states the output the interpreter actually produced, so the
examples and the rules they illustrate cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from .core import (
    Assign, Binary, BoolLit, Call, ExprStmt, FunDef, If, Index, IntLit, ListLit,
    Program, Return, StrLit, Unary, Var, While,
)
from .interp import run_program
from .printer import to_source
from .spec import LanguageSpec


@dataclass(frozen=True)
class Example:
    title: str
    source: str
    output: str


@dataclass(frozen=True)
class Manual:
    text: str
    examples: tuple


def _show(e) -> ExprStmt:
    return ExprStmt(Call("print", (e,)))


def _neg(n: int):
    return Unary("neg", IntLit(n))


def _at(base: int, target, logical: int):
    return Index(target, IntLit(logical + base))


def _evaluate(spec: LanguageSpec, expr) -> str:
    result = run_program(Program((_show(expr),)), spec.semantics)
    if result.error:
        raise RuntimeError(f"manual example failed: {result.error}")
    return result.text


def _examples(spec: LanguageSpec) -> tuple:
    base = spec.semantics.index_base
    xs = ListLit((IntLit(10), IntLit(20), IntLit(30)))
    add = FunDef("add", ("a", "b"), (Return(Binary("+", Var("a"), Var("b"))),))
    cases = [
        ("Integer division and modulo", (
            _show(Binary("/", _neg(7), IntLit(2))),
            _show(Binary("%", _neg(7), IntLit(3))),
            _show(Binary("/", IntLit(7), _neg(2))),
            _show(Binary("%", IntLit(7), _neg(3))),
        )),
        ("Operator precedence", (
            _show(Binary("+", IntLit(2), Binary("*", IntLit(3), IntLit(4)))),
            _show(Binary("==", IntLit(1), Binary("+", IntLit(0), IntLit(1)))),
        )),
        ("Truthiness in conditions", (
            If(IntLit(0), (_show(StrLit("zero is true")),), (_show(StrLit("zero is false")),)),
            If(ListLit(()), (_show(StrLit("empty list is true")),), (_show(StrLit("empty list is false")),)),
        )),
        ("Indexing", (
            Assign("xs", xs),
            _show(_at(base, Var("xs"), 0)),
            _show(_at(base, Var("xs"), 2)),
        )),
        ("and / or", (
            _show(Binary("or", IntLit(0), IntLit(5))),
            _show(Binary("and", BoolLit(True), IntLit(0))),
        )),
        ("Functions, loops and calls", (
            add,
            Assign("acc", IntLit(0)),
            Assign("i", IntLit(1)),
            While(Binary("<=", Var("i"), IntLit(3)), (
                Assign("acc", Binary("+", Var("acc"), Var("i"))),
                Assign("i", Binary("+", Var("i"), IntLit(1))),
            )),
            _show(Var("acc")),
            _show(Call("add", (IntLit(2), IntLit(3)))),
        )),
    ]
    out = []
    for title, body in cases:
        program = Program(tuple(body))
        result = run_program(program, spec.semantics)
        if result.error:
            raise RuntimeError(f"manual example '{title}' failed: {result.error}")
        out.append(Example(title, to_source(program, spec), result.text))
    return tuple(out)


def _ops_text(spec: LanguageSpec, group: tuple) -> str:
    return ", ".join(f"`{spec.syntax.ops[op]}`" for op in group)


def build_manual(spec: LanguageSpec) -> Manual:
    sx, sem, name = spec.syntax, spec.semantics, spec.name
    kw, bi = sx.keywords, sx.builtins
    open_tok, close_tok = sx.block
    def ev(e) -> str:
        return _evaluate(spec, e)
    end = ("a statement ends at the end of its line" if spec.newline_mode
           else f"each simple statement ends with `{sx.terminator}`")
    call = ("a call is written `name(arg, ...)`" if sx.call_style == "prefix"
            else "a call is written `(arg, ...) name`, with the arguments first and the name last")
    prec = "\n".join(
        f"{i + 1}. {_ops_text(spec, group)}" for i, group in enumerate(sx.levels)
    )
    lines = [
        f"# {name} reference manual",
        "",
        f"{name} is a small imperative language. A program is a list of statements. "
        "The grader calls the function `" + sx.keywords["fn"] + " solve(...)` "
        "with arguments and prints the value it returns.",
        "",
        "## Words and values",
        f"- Function definition: `{kw['fn']}`. Conditionals: `{kw['if']}` / `{kw['else']}`. "
        f"Loops: `{kw['while']}`. Return: `{kw['return']}`.",
        f"- Booleans: `{kw['true']}` and `{kw['false']}`. Integers: `0`, `42` (negative numbers use the "
        f"prefix negation operator `{sx.ops['neg']}`). Strings: double quotes, e.g. \"hi\".",
        "- Lists are written `[a, b, c]`. Values are immutable: `append` returns a new list.",
        "- A function that does not return a value yields `none`.",
        "- Printed values: integers as digits, booleans as `true`/`false`, strings as-is, lists as `[a, b]`. "
        "Strings inside a list are in double quotes, e.g. `[\"a\", 1]`.",
        "",
        "## Statements",
        f"- Assignment: `name {sx.assign} expression`. The first assignment inside a function creates the variable.",
        f"- Blocks start with `{open_tok}` and end with `{close_tok}`. Statements inside a block follow the same rules.",
        f"- Statement endings: {end}.",
        *([f"- In a newline-ended language a block opener must be on the same line as its statement, and "
           f"`{kw['else']}` must be on the same line as the `{close_tok}` that closes the `if` block."]
          if spec.newline_mode else []),
        "- Identifiers are plain letters, digits and underscores (not starting with a digit).",
        "",
        "## Operators and precedence",
        f"- Negation: `{sx.ops['neg']}x`. Logical not: `{sx.ops['not']}x`. Both bind tighter than any binary operator.",
        "- Binary operators, lowest binding first (same line = same precedence, grouped left to right):",
        prec,
        "- Calls and indexing bind tightest of all.",
        "- Parentheses group as usual.",
        "",
        "## Calls",
        f"- {call[0].upper() + call[1:]}. Built-in and user-defined functions use the same form.",
        "",
        "## Indexing",
        f"- `xs[i]` reads an element. Indices start at **{sem.index_base}**: the first element is "
        f"`xs[{sem.index_base}]`, the last is `xs[{sem.index_base} + len(xs) - 1]`.",
        "- Indexing outside the valid range is a runtime error.",
        "",
        "## Truthiness",
        f"- `{kw['false']}`, `{kw['true']}`: as written. `none`: false.",
        f"- The integer 0 is {'false' if sem.zero_is_false else 'true'}. "
        f"An empty list or empty string is {'false' if sem.empty_is_false else 'true'}. "
        "Any other integer is true.",
        "",
        "## Integer arithmetic",
        f"- `/` on integers rounds {'toward negative infinity' if sem.int_div == 'floor' else 'toward zero'}: "
        f"`-7 / 2` evaluates to {ev(Binary('/', _neg(7), IntLit(2)))}.",
        f"- `%` takes the sign of the {'divisor' if sem.int_mod == 'floor' else 'dividend'}: "
        f"`-7 % 3` evaluates to {ev(Binary('%', _neg(7), IntLit(3)))}, "
        f"and `7 % -3` evaluates to {ev(Binary('%', IntLit(7), _neg(3)))}.",
        "- Division or modulo by zero is a runtime error. `+` also joins two strings.",
        "",
        "## and / or",
        f"- `and` and `or` short-circuit. They return {'the operand that decided the result' if sem.logic_returns_operand else 'a boolean'}: "
        f"`0 or 5` evaluates to {ev(Binary('or', IntLit(0), IntLit(5)))}, "
        f"`{kw['true']} and 0` evaluates to {ev(Binary('and', BoolLit(True), IntLit(0)))}.",
        "",
        "## Built-in functions",
        f"- `{bi['len']}(x)`: number of items in a list or characters in a string.",
        f"- `{bi['append']}(xs, v)`: a new list with `v` added at the end.",
        f"- `{bi['str']}(x)`: the printed form of `x` as a string.",
        f"- `{bi['print']}(x)`: prints `x` on its own line.",
        "",
        "## Limits",
        "- Programs get a bounded number of steps, a bounded call depth and bounded list and string sizes. "
        "Exceeding a limit (for example an infinite loop) is an error.",
        "",
        "## Worked examples (executed when this manual was generated)",
    ]
    examples = _examples(spec)
    for ex in examples:
        lines += ["", f"### {ex.title}", "```", ex.source.rstrip("\n"), "```", "Output:", "```", ex.output, "```"]
    text = "\n".join(lines) + "\n"
    return Manual(text=text, examples=examples)
