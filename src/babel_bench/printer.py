"""Pretty-printer: core AST -> surface source for a LanguageSpec.

Parentheses are inserted from the spec's precedence table, so parse(print(ast))
returns the same AST. `to_python` is a separate emitter used only by the naive
baseline, which answers in Python syntax.
"""

from __future__ import annotations

from .core import (
    Assign, Binary, BoolLit, Call, ExprStmt, FunDef, If, Index, IntLit, ListLit,
    Program, Return, StrLit, Unary, Var, While,
)
from .spec import LanguageSpec

Tokens = tuple
Line = tuple  # (depth, tokens)


def _needs_space(prev: str, nxt: str) -> bool:
    if prev[-1] in "([" or nxt[0] in ")],":
        return False
    if nxt in ("(", "[") and (prev[-1].isalnum() or prev[-1] == "_"):
        return False
    return True


def _join(tokens: Tokens) -> str:
    out = ""
    for tok in tokens:
        out = tok if not out else out + (" " if _needs_space(out, tok) else "") + tok
    return out


class _ExprPrinter:
    def __init__(self, spec: LanguageSpec) -> None:
        self.sx = spec.syntax
        self.level_of = {op: i for i, group in enumerate(self.sx.levels) for op in group}
        self.atom_level = len(self.sx.levels)

    def level(self, e) -> int:
        return self.level_of[e.op] if isinstance(e, Binary) else self.atom_level

    def wrap(self, e, needs: bool) -> Tokens:
        toks = self.expr(e)
        return ("(",) + toks + (")",) if needs else toks

    def args(self, items) -> Tokens:
        out: Tokens = ()
        for i, a in enumerate(items):
            out += (("," ,) if i else ()) + self.expr(a)
        return out

    def expr(self, e) -> Tokens:
        sx = self.sx
        if isinstance(e, IntLit):
            return (str(e.value),)
        if isinstance(e, BoolLit):
            return (sx.keywords["true" if e.value else "false"],)
        if isinstance(e, StrLit):
            return (f'"{e.value}"',)
        if isinstance(e, ListLit):
            return ("[",) + self.args(e.items) + ("]",)
        if isinstance(e, Var):
            return (e.name,)
        if isinstance(e, Call):
            name = sx.builtins.get(e.name, e.name)
            if sx.call_style == "postfix":
                return ("(",) + self.args(e.args) + (")", name)
            return (name, "(") + self.args(e.args) + (")",)
        if isinstance(e, Unary):
            return (sx.ops[e.op],) + self.wrap(e.operand, isinstance(e.operand, Binary))
        if isinstance(e, Binary):
            lvl = self.level_of[e.op]
            left = self.wrap(e.left, self.level(e.left) < lvl)
            right = self.wrap(e.right, self.level(e.right) <= lvl)
            return left + (sx.ops[e.op],) + right
        if isinstance(e, Index):
            target = self.wrap(e.target, isinstance(e.target, (Binary, Unary)))
            return target + ("[",) + self.expr(e.index) + ("]",)
        raise TypeError(f"not an expression: {e!r}")


class _StmtPrinter:
    def __init__(self, spec: LanguageSpec) -> None:
        self.spec = spec
        self.sx = spec.syntax
        self.ex = _ExprPrinter(spec)
        self.open, self.close = self.sx.block
        self.kw = self.sx.keywords

    def term(self) -> Tokens:
        return () if self.spec.newline_mode else (self.sx.terminator,)

    def block(self, stmts, depth: int) -> list:
        out: list = []
        for s in stmts:
            out += self.stmt(s, depth)
        return out

    def stmt(self, s, depth: int) -> list:
        kw, term = self.kw, self.term()
        if isinstance(s, Assign):
            return [(depth, (s.name, self.sx.assign) + self.ex.expr(s.value) + term)]
        if isinstance(s, ExprStmt):
            return [(depth, self.ex.expr(s.expr) + term)]
        if isinstance(s, Return):
            value = self.ex.expr(s.value) if s.value is not None else ()
            return [(depth, (kw["return"],) + value + term)]
        if isinstance(s, While):
            head = (kw["while"],) + self.ex.expr(s.cond) + (self.open,)
            return [(depth, head)] + self.block(s.body, depth + 1) + [(depth, (self.close,))]
        if isinstance(s, If):
            head = (kw["if"],) + self.ex.expr(s.cond) + (self.open,)
            lines = [(depth, head)] + self.block(s.then, depth + 1)
            if not s.orelse:
                return lines + [(depth, (self.close,))]
            lines.append((depth, (self.close, kw["else"], self.open)))
            return lines + self.block(s.orelse, depth + 1) + [(depth, (self.close,))]
        if isinstance(s, FunDef):
            params: Tokens = ()
            for i, p in enumerate(s.params):
                params += ((",",) if i else ()) + (p,)
            head = (kw["fn"], s.name, "(") + params + (")", self.open)
            return [(depth, head)] + self.block(s.body, depth + 1) + [(depth, (self.close,))]
        raise TypeError(f"not a statement: {s!r}")


def to_source(program: Program, spec: LanguageSpec) -> str:
    """Render a program in `spec`'s surface syntax, indented by block depth."""
    printer = _StmtPrinter(spec)
    lines = printer.block(program.body, 0)
    return "\n".join("  " * depth + _join(toks) for depth, toks in lines) + "\n"


# Naive-baseline emitter: plain Python syntax for the same AST. -----------------

_PY_OPS = {"and": "and", "or": "or", "/": "//", "neg": "-", "not": "not "}


def _py_expr(e) -> str:
    if isinstance(e, IntLit):
        return str(e.value)
    if isinstance(e, BoolLit):
        return "True" if e.value else "False"
    if isinstance(e, StrLit):
        return repr(e.value)
    if isinstance(e, ListLit):
        return "[" + ", ".join(_py_expr(i) for i in e.items) + "]"
    if isinstance(e, Var):
        return e.name
    if isinstance(e, Call):
        if e.name == "append":
            return f"{_py_expr(e.args[0])} + [{_py_expr(e.args[1])}]"
        return f"{e.name}(" + ", ".join(_py_expr(a) for a in e.args) + ")"
    if isinstance(e, Unary):
        return f"({_PY_OPS.get(e.op, e.op)}{_py_expr(e.operand)})"
    if isinstance(e, Binary):
        return f"({_py_expr(e.left)} {_PY_OPS.get(e.op, e.op)} {_py_expr(e.right)})"
    if isinstance(e, Index):
        return f"{_py_expr(e.target)}[{_py_expr(e.index)}]"
    raise TypeError(f"not an expression: {e!r}")


def _py_block(stmts, depth: int) -> list[str]:
    pad = "    " * depth
    out: list[str] = []
    for s in stmts:
        if isinstance(s, Assign):
            out.append(f"{pad}{s.name} = {_py_expr(s.value)}")
        elif isinstance(s, ExprStmt):
            out.append(f"{pad}{_py_expr(s.expr)}")
        elif isinstance(s, Return):
            out.append(f"{pad}return" + (f" {_py_expr(s.value)}" if s.value is not None else ""))
        elif isinstance(s, While):
            out.append(f"{pad}while {_py_expr(s.cond)}:")
            out += _py_block(s.body, depth + 1) or [pad + "    pass"]
        elif isinstance(s, If):
            out.append(f"{pad}if {_py_expr(s.cond)}:")
            out += _py_block(s.then, depth + 1) or [pad + "    pass"]
            if s.orelse:
                out.append(f"{pad}else:")
                out += _py_block(s.orelse, depth + 1)
        elif isinstance(s, FunDef):
            out.append(f"{pad}def {s.name}({', '.join(s.params)}):")
            out += _py_block(s.body, depth + 1) or [pad + "    pass"]
    return out


def to_python(program: Program) -> str:
    return "\n".join(_py_block(program.body, 0)) + "\n"
