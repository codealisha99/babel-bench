"""Spec-driven lexer and parser: generated surface syntax -> core AST."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .core import (
    Assign, Binary, BoolLit, Call, ExprStmt, FunDef, If, Index, IntLit, ListLit,
    Program, Return, StrLit, Unary, Var, While,
)
from .spec import LanguageSpec

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUM = re.compile(r"[0-9]+")
_STR = re.compile(r'"([^"\n]*)"')


class ParseError(Exception):
    def __init__(self, detail: str, line: int) -> None:
        super().__init__(f"line {line}: {detail}")
        self.detail = detail
        self.line = line


@dataclass(frozen=True)
class Tok:
    kind: str  # WORD, SYM, NUM, STR, NL, EOF
    text: str
    line: int


def tokenize(source: str, spec: LanguageSpec) -> tuple:
    symbols = sorted(spec.symbols(), key=len, reverse=True)
    toks: list[Tok] = []
    i, line, n = 0, 1, len(source)
    while i < n:
        c = source[i]
        if c == "\n":
            if spec.newline_mode:
                toks.append(Tok("NL", "\n", line))
            line += 1
            i += 1
        elif c in " \t\r":
            i += 1
        elif c == '"':
            m = _STR.match(source, i)
            if not m:
                raise ParseError("unterminated string literal", line)
            toks.append(Tok("STR", m.group(1), line))
            i = m.end()
        elif m := _NUM.match(source, i):
            toks.append(Tok("NUM", m.group(0), line))
            i = m.end()
        elif m := _WORD.match(source, i):
            toks.append(Tok("WORD", m.group(0), line))
            i = m.end()
        else:
            sym = next((s for s in symbols if source.startswith(s, i)), None)
            if sym is None:
                raise ParseError(f"unexpected character {c!r}", line)
            toks.append(Tok("SYM", sym, line))
            i += len(sym)
    toks.append(Tok("EOF", "", line))
    return tuple(toks)


def _describe(t: Tok) -> str:
    if t.kind == "EOF":
        return "end of input"
    if t.kind == "NL":
        return "end of line"
    return f"'{t.text}'"


class _Parser:
    def __init__(self, spec: LanguageSpec, toks: tuple) -> None:
        self.spec = spec
        self.sx = spec.syntax
        self.toks = toks
        self.pos = 0
        self.reserved = spec.reserved_words()
        self.builtin_of = {s: c for c, s in self.sx.builtins.items()}
        self.open_tok, self.close_tok = self.sx.block

    # token helpers -------------------------------------------------------
    def peek(self, k: int = 0) -> Tok:
        return self.toks[min(self.pos + k, len(self.toks) - 1)]

    def advance(self) -> Tok:
        t = self.peek()
        self.pos += 1
        return t

    def at(self, text: str) -> bool:
        t = self.peek()
        return t.kind in ("WORD", "SYM") and t.text == text

    def expect(self, text: str, what: str) -> Tok:
        if not self.at(text):
            t = self.peek()
            raise ParseError(f"expected {what} but found {_describe(t)}", t.line)
        return self.advance()

    def is_kw(self, t: Tok, canon: str) -> bool:
        return t.kind == "WORD" and t.text == self.sx.keywords[canon]

    def is_ident(self, t: Tok) -> bool:
        return t.kind == "WORD" and t.text not in self.reserved

    def is_callable(self, t: Tok) -> bool:
        return t.kind == "WORD" and (t.text in self.builtin_of or self.is_ident(t))

    def is_closer(self, t: Tok) -> bool:
        return t.kind in ("WORD", "SYM") and t.text == self.close_tok

    def skip_newlines(self) -> None:
        while self.peek().kind == "NL":
            self.advance()

    # statements ----------------------------------------------------------
    def parse_program(self) -> Program:
        body = self.parse_stmts(closer=False)
        t = self.peek()
        if t.kind != "EOF":
            raise ParseError(f"unexpected {_describe(t)}", t.line)
        return Program(body)

    def parse_stmts(self, closer: bool) -> tuple:
        out = []
        while True:
            self.skip_newlines()
            t = self.peek()
            if t.kind == "EOF" or (closer and self.is_closer(t)):
                return tuple(out)
            out.append(self.parse_stmt())

    def parse_block(self) -> tuple:
        self.expect(self.open_tok, f"'{self.open_tok}' to open a block")
        body = self.parse_stmts(closer=True)
        self.expect(self.close_tok, f"'{self.close_tok}' to close the block")
        return body

    def end_simple(self) -> None:
        if self.sx.terminator == "newline":
            t = self.peek()
            if t.kind == "NL":
                self.advance()
            elif not (t.kind == "EOF" or self.is_closer(t)):
                raise ParseError(f"expected end of line but found {_describe(t)}", t.line)
        else:
            self.expect(self.sx.terminator, f"'{self.sx.terminator}' to end the statement")

    def at_stmt_end(self) -> bool:
        t = self.peek()
        if t.kind in ("NL", "EOF") or self.is_closer(t):
            return True
        return self.sx.terminator != "newline" and self.at(self.sx.terminator)

    def parse_stmt(self):
        t = self.peek()
        line = t.line
        if self.is_kw(t, "fn"):
            return self.parse_fundef()
        if self.is_kw(t, "if"):
            return self.parse_if()
        if self.is_kw(t, "while"):
            self.advance()
            cond = self.parse_expr()
            return While(cond, self.parse_block(), line=line)
        if self.is_kw(t, "return"):
            self.advance()
            value = None if self.at_stmt_end() else self.parse_expr()
            self.end_simple()
            return Return(value, line=line)
        nxt = self.peek(1)
        if self.is_ident(t) and nxt.kind == "SYM" and nxt.text == self.sx.assign:
            self.advance()
            self.advance()
            value = self.parse_expr()
            self.end_simple()
            return Assign(t.text, value, line=line)
        expr = self.parse_expr()
        self.end_simple()
        return ExprStmt(expr, line=line)

    def parse_if(self):
        line = self.advance().line
        cond = self.parse_expr()
        then = self.parse_block()
        orelse = ()
        if self.is_kw(self.peek(), "else"):
            self.advance()
            orelse = self.parse_block()
        return If(cond, then, orelse, line=line)

    def parse_fundef(self):
        line = self.advance().line
        name_tok = self.peek()
        if not self.is_ident(name_tok):
            raise ParseError(f"expected a function name but found {_describe(name_tok)}", name_tok.line)
        self.advance()
        self.expect("(", "'(' after the function name")
        params: list[str] = []
        while not self.at(")"):
            p = self.peek()
            if not self.is_ident(p):
                raise ParseError(f"expected a parameter name but found {_describe(p)}", p.line)
            params.append(self.advance().text)
            if not self.at(","):
                break
            self.advance()
        self.expect(")", "')' after parameters")
        return FunDef(name_tok.text, tuple(params), self.parse_block(), line=line)

    # expressions ---------------------------------------------------------
    def parse_expr(self):
        return self.parse_level(0)

    def parse_level(self, i: int):
        if i == len(self.sx.levels):
            return self.parse_unary()
        left = self.parse_level(i + 1)
        while True:
            op = self.match_binary(self.sx.levels[i])
            if op is None:
                return left
            left = Binary(op, left, self.parse_level(i + 1))

    def match_binary(self, group: tuple):
        for canon in group:
            if self.at(self.sx.ops[canon]):
                self.advance()
                return canon
        return None

    def parse_unary(self):
        for canon in ("not", "neg"):
            if self.at(self.sx.ops[canon]):
                self.advance()
                return Unary(canon, self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self):
        e = self.parse_primary()
        while self.at("["):
            self.advance()
            idx = self.parse_expr()
            self.expect("]", "']' to close the index")
            e = Index(e, idx)
        return e

    def parse_arglist(self, close: str) -> tuple:
        items = []
        if self.at(close):
            self.advance()
            return tuple(items)
        while True:
            items.append(self.parse_expr())
            if self.at(","):
                self.advance()
                continue
            self.expect(close, f"'{close}'")
            return tuple(items)

    def callee_name(self, t: Tok) -> str:
        return self.builtin_of.get(t.text, t.text)

    def parse_primary(self):
        t = self.peek()
        if t.kind == "NUM":
            self.advance()
            return IntLit(int(t.text))
        if t.kind == "STR":
            self.advance()
            return StrLit(t.text)
        if self.is_kw(t, "true") or self.is_kw(t, "false"):
            self.advance()
            return BoolLit(self.is_kw(t, "true"))
        if self.at("["):
            self.advance()
            return ListLit(self.parse_arglist("]"))
        if self.at("("):
            self.advance()
            items = self.parse_arglist(")")
            if self.sx.call_style == "postfix" and self.is_callable(self.peek()):
                name = self.callee_name(self.advance())
                return Call(name, items)
            if len(items) != 1:
                raise ParseError("expected one expression inside parentheses", t.line)
            return items[0]
        if self.is_callable(t):
            name = self.callee_name(t)
            if self.sx.call_style == "prefix" and self.peek(1).text == "(" and self.peek(1).kind == "SYM":
                self.advance()
                self.advance()
                return Call(name, self.parse_arglist(")"))
            if t.text in self.builtin_of:
                raise ParseError(f"built-in '{name}' must be called with arguments", t.line)
            self.advance()
            return Var(name)
        raise ParseError(f"expected an expression but found {_describe(t)}", t.line)


def parse(source: str, spec: LanguageSpec) -> Program:
    """Parse source written in `spec`'s language. Raises ParseError with a line number."""
    try:
        return _Parser(spec, tokenize(source, spec)).parse_program()
    except RecursionError as exc:
        raise ParseError("expression is nested too deeply", 0) from exc
