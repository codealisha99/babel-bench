"""Prompt construction: the manual is the only source of truth about the language."""

from __future__ import annotations

from .tasks import Instance, py_format

SYSTEM = (
    "You are an expert programmer. You will work in a programming language you have never seen. "
    "Its complete reference manual is given. Use only the manual; do not assume the syntax or "
    "semantics of any other language."
)

_SHOWN_HEADINGS = {
    "fix": "Buggy program",
    "translate": "Python function to translate",
    "write": "",
    "predict": "Program",
}


def _examples(inst: Instance) -> str:
    lines = [f"- solve({', '.join(py_format(a) for a in t.args)}) returns {t.expected}" for t in inst.visible]
    return "\n".join(lines)


def build_prompt(language: str, manual: str, inst: Instance, feedback: str | None) -> str:
    parts = [f"# {language}: reference manual", manual.strip(), "", f"# Task: {inst.title}", inst.statement]
    if inst.kind == "predict":
        parts += ["", "## Program", f"```\n{inst.shown.rstrip()}\n```", "",
                  "## Answer format",
                  "Reply with one fenced code block containing only the printed output."]
    else:
        heading = _SHOWN_HEADINGS.get(inst.tier, "")
        if inst.shown and heading:
            parts += ["", f"## {heading}", f"```\n{inst.shown.rstrip()}\n```"]
        if inst.visible:
            parts += ["", "## Visible examples", _examples(inst)]
        parts += ["", "## Answer format",
                  "Define a function named `solve` with the parameters described above. Reply with one fenced code "
                  "block containing the complete program (top-level statements are allowed). Do not explain."]
    if feedback:
        parts += ["", "## Feedback on your previous attempt", feedback, "Revise the program and reply again."]
    return "\n".join(parts) + "\n"
