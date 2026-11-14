"""Language specs: everything that makes one generated language different.

A LanguageSpec is derived deterministically from an integer seed. It has two
halves: `Syntax` (how programs are spelled and grouped; drives the parser and
printer) and `Semantics` (how values behave; drives the interpreter).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .core import BINARY_OPS, BUILTINS, UNARY_OPS

KEYWORDS = ("fn", "if", "else", "while", "return", "true", "false")
# Default precedence groups, lowest first. A generated language may permute them.
DEFAULT_LEVELS = (("or",), ("and",), ("==", "!=", "<", "<=", ">", ">="), ("+", "-"), ("*", "/", "%"))
# Identifiers used by task templates. Generated surface words never equal these.
RESERVED_IDENTIFIERS = frozenset({
    "solve", "xs", "ys", "n", "m", "i", "j", "d", "b", "e", "a", "x", "lo", "hi", "mid",
    "acc", "best", "count", "result", "total", "value", "item", "out", "prev", "cur", "tmp",
    "steps", "sum", "t", "s", "r", "v", "k", "c", "w", "p", "q", "f", "g", "h", "u",
})
# Surface spellings a word-form operator may take. "WORD" means "generate a fresh word".
_OP_CHOICES = {
    "or": ["||", "|", "WORD"],
    "and": ["&&", "&", "WORD"],
    "not": ["!", "WORD"],
    "==": ["==", "==="],
    "!=": ["!=", "/=", "<>", "~="],
    "<": ["<"],
    "<=": ["<=", "=<"],
    ">": [">"],
    ">=": [">=", "=>"],
    "+": ["+"],
    "-": ["-"],
    "*": ["*"],
    "/": ["/"],
    "%": ["%", "WORD"],
    "neg": ["-", "~"],
}
_SYLLABLE_ONSETS = list("bdfgklmnprstvz") + ["br", "kr", "tr", "dr", "gl", "pl", "sk", "fr", "zv"]
_SYLLABLE_VOWELS = list("aeiou") + ["ai", "ou", "ee"]
_PUNCT = ("(", ")", "[", "]", ",")


@dataclass(frozen=True)
class Semantics:
    index_base: int
    int_div: str  # "floor" (toward -inf) or "trunc" (toward zero)
    int_mod: str  # "floor" (sign of divisor) or "trunc" (sign of dividend)
    zero_is_false: bool
    empty_is_false: bool
    logic_returns_operand: bool


@dataclass(frozen=True)
class Syntax:
    keywords: dict  # canonical keyword -> surface word
    ops: dict  # canonical operator (incl. "neg") -> surface token
    builtins: dict  # canonical builtin -> surface word
    levels: tuple  # binary precedence groups, lowest first
    block: tuple  # (open, close) surface tokens
    terminator: str  # "newline" or a symbol such as ";"
    call_style: str  # "prefix" -> f(a, b); "postfix" -> (a, b) f
    assign: str  # assignment token


@dataclass(frozen=True)
class LanguageSpec:
    seed: int
    name: str
    syntax: Syntax
    semantics: Semantics

    @property
    def newline_mode(self) -> bool:
        return self.syntax.terminator == "newline"

    def reserved_words(self) -> frozenset:
        """Every word-shaped surface token that is not a free identifier."""
        sx = self.syntax
        words = set(sx.keywords.values()) | set(sx.builtins.values())
        words |= {t for t in sx.ops.values() if t.isalpha()}
        words |= {t for t in sx.block if t.isalpha()}
        return frozenset(words)

    def symbols(self) -> frozenset:
        """Every non-word surface token the lexer must recognise."""
        sx = self.syntax
        syms = {t for t in sx.ops.values() if not t.isalpha()}
        syms |= {t for t in sx.block if not t.isalpha()}
        syms |= {sx.assign, *_PUNCT}
        if not self.newline_mode:
            syms.add(sx.terminator)
        return frozenset(syms)

    def features(self) -> dict:
        """Coarse feature labels used to break results down in the report."""
        sem, sx = self.semantics, self.syntax
        return {
            "index base": f"{sem.index_base}-based",
            "terminator": "newline" if self.newline_mode else "semicolon-style",
            "blocks": "keyword pair" if sx.block[0].isalpha() else "braces",
            "call style": sx.call_style,
            "integer division": "rounds down" if sem.int_div == "floor" else "rounds toward zero",
            "modulo sign": "follows divisor" if sem.int_mod == "floor" else "follows dividend",
            "zero is": "false" if sem.zero_is_false else "true",
            "empty collection is": "false" if sem.empty_is_false else "true",
            "and/or result": "operand" if sem.logic_returns_operand else "boolean",
            "precedence": "canonical" if sx.levels == DEFAULT_LEVELS else "permuted",
        }


def _word(rng: random.Random) -> str:
    syllables = rng.randint(2, 3)
    parts = [rng.choice(_SYLLABLE_ONSETS) + rng.choice(_SYLLABLE_VOWELS) for _ in range(syllables)]
    word = "".join(parts)
    return word + rng.choice(["", "n", "r", "k"]) if len(word) < 5 else word


def _pick_surfaces(rng: random.Random, fresh) -> dict:
    ops = {}
    for role, choices in _OP_CHOICES.items():
        pick = rng.choice(choices)
        ops[role] = fresh() if pick == "WORD" else pick
    return ops


def _symbol_clash(ops: dict, block: tuple, assign: str, term: str) -> bool:
    """True if two distinct symbolic roles would share a surface token.

    Binary "-" and unary neg may share "-": the parser knows the position.
    """
    core = [t for r, t in ops.items() if r not in ("neg", "-") and not t.isalpha()]
    core += [t for t in block if not t.isalpha()] + [assign]
    if term != "newline":
        core.append(term)
    if len(set(core)) != len(core):
        return True
    return ops["-"] in core or (ops["neg"] != ops["-"] and ops["neg"] in core)


def generate(seed: int) -> LanguageSpec:
    """Derive a language from `seed`. Same seed, same language, forever."""
    rng = random.Random(f"babel-bench:{seed}")
    taken = set(RESERVED_IDENTIFIERS)

    def fresh() -> str:
        while True:
            w = _word(rng)
            if w not in taken and w not in KEYWORDS and len(w) >= 4:
                taken.add(w)
                return w

    while True:
        snapshot = set(taken)
        keywords = {k: fresh() for k in KEYWORDS}
        builtins = {b: fresh() for b in BUILTINS}
        ops = _pick_surfaces(rng, fresh)
        block = ("{", "}") if rng.random() < 0.5 else (fresh(), fresh())
        term = rng.choice(["newline", ";", ".", "$"])
        assign = rng.choice(["=", ":=", "<-"])
        if not _symbol_clash(ops, block, assign, term):
            break
        taken.clear()
        taken.update(snapshot)
    groups = list(DEFAULT_LEVELS)
    if rng.random() < 0.6:
        rng.shuffle(groups)
    semantics = Semantics(
        index_base=rng.choice([0, 1]),
        int_div=rng.choice(["floor", "trunc"]),
        int_mod=rng.choice(["floor", "trunc"]),
        zero_is_false=rng.random() < 0.5,
        empty_is_false=rng.random() < 0.5,
        logic_returns_operand=rng.random() < 0.5,
    )
    syntax = Syntax(
        keywords=keywords,
        ops=ops,
        builtins=builtins,
        levels=tuple(groups),
        block=block,
        terminator=term,
        call_style=rng.choice(["prefix", "postfix"]),
        assign=assign,
    )
    name = _word(rng).capitalize()
    spec = LanguageSpec(seed=seed, name=name, syntax=syntax, semantics=semantics)
    assert set(BINARY_OPS) | set(UNARY_OPS) <= set(ops), "every canonical operator needs a spelling"
    return spec
