"""Static, self-contained HTML report built from results JSONL records.

Uses one sequential blue ramp plus neutral text/grid tokens from the dataviz
reference palette (sequential hue only, so no categorical validation is needed).
No scripts, no external requests: the file opens offline.
"""

from __future__ import annotations

import html
import math
from collections import defaultdict
from datetime import datetime, timezone

Z95 = 1.959963984540054

CSS = """
:root { color-scheme: light; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --blue:#2a78d6; --blue-soft:#cde2fb; --blue-deep:#104281; --track:#efeee9; }
@media (prefers-color-scheme: dark) { :root { color-scheme: dark; --surface:#1a1a19; --ink:#f0efec;
  --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835; --blue:#3987e5; --blue-soft:#1c5cab;
  --blue-deep:#9ec5f4; --track:#252523; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--surface); color:var(--ink);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 40px 24px 80px; }
h1 { font-size: 30px; margin: 0 0 6px; letter-spacing: -0.02em; }
h2 { font-size: 19px; margin: 44px 0 12px; padding-top: 18px; border-top: 1px solid var(--grid); }
p.lede, .meta { color: var(--ink2); margin: 0; }
.meta { font-size: 13px; color: var(--muted); }
table { width: 100%; border-collapse: collapse; font-size: 14px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--grid); vertical-align: top; }
th { font-weight: 600; color: var(--ink2); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
td.num, th.num { text-align: right; }
.cell { display:inline-block; min-width: 54px; text-align:center; border-radius: 4px; padding: 2px 6px; }
.ci { color: var(--muted); font-size: 12px; }
.pass { color: var(--blue-deep); font-weight: 600; } .fail { color: var(--ink2); }
details { border-bottom: 1px solid var(--grid); padding: 8px 0; }
summary { cursor: pointer; font-variant-numeric: tabular-nums; }
pre { background: rgba(0,0,0,0.04); padding: 10px 12px; border-radius: 6px; overflow-x: auto;
  font: 12.5px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; }
.note { color: var(--ink2); font-size: 13px; }
svg text { font: 13px -apple-system, Helvetica, Arial, sans-serif; fill: var(--ink2); }
svg rect.track { fill: var(--track); } svg rect.bar { fill: var(--blue); }
svg line.whisker { stroke: var(--ink); stroke-width: 1.5; } svg line.gridline { stroke: var(--grid); }
svg text.ink { fill: var(--ink); } svg text.muted { fill: var(--muted); font-size: 12px; }
"""


def wilson_interval(passes: int, total: int, z: float = Z95) -> tuple:
    """95% Wilson score interval for a proportion, as (low, high) fractions."""
    if total == 0:
        return (0.0, 0.0)
    p = passes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _esc(value) -> str:
    return html.escape(str(value))


def _rate_cell(passes: int, total: int) -> str:
    if total == 0:
        return '<span class="fail">-</span>'
    alpha = 0.12 + 0.6 * (passes / total)
    return (f'<span class="cell" style="background:rgba(42,120,214,{alpha:.2f})">'
            f"{passes}/{total} &middot; {_pct(passes / total)}</span>")


def _summarise(records: list) -> dict:
    """model -> {passes, total, tokens, cost, estimated, by_tier, by_language}."""
    out: dict = {}
    for r in records:
        m = out.setdefault(r["model"], {"passes": 0, "total": 0, "in": 0, "out": 0,
                                         "cost": 0.0, "cost_known": True, "estimated": False,
                                         "tier": defaultdict(lambda: [0, 0])})
        m["total"] += 1
        m["passes"] += int(r["passed"])
        m["in"] += r["input_tokens"]
        m["out"] += r["output_tokens"]
        if r.get("cost_usd") is None:
            m["cost_known"] = False
        else:
            m["cost"] += r["cost_usd"]
        m["estimated"] = m["estimated"] or bool(r.get("estimated"))
        m["tier"][r["tier"]][0] += int(r["passed"])
        m["tier"][r["tier"]][1] += 1
    return out


def _bar_chart(summary: dict) -> str:
    """Pass rate per model: one ink-free blue bar per row, direct value labels, 95% interval whisker."""
    width, row, top, bar = 760, 40, 8, 18
    left, right = 170, 170
    scale = width - left - right
    axis_y = top + row * len(summary) + 4
    height = axis_y + 46
    marks = []
    for i, (model, s) in enumerate(summary.items()):
        y = top + i * row
        mid = y + bar / 2
        rate = s["passes"] / s["total"] if s["total"] else 0
        lo, hi = wilson_interval(s["passes"], s["total"])
        marks.append(
            f'<text class="ink" x="{left - 12}" y="{mid}" text-anchor="end" dominant-baseline="middle">{_esc(model)}</text>'
            f'<rect x="{left}" y="{y}" width="{scale}" height="{bar}" class="track" rx="2"/>'
            f'<rect x="{left}" y="{y}" width="{rate * scale:.1f}" height="{bar}" class="bar" rx="2"/>'
            f'<line x1="{left + lo * scale:.1f}" x2="{left + hi * scale:.1f}" y1="{mid}" y2="{mid}" '
            f'class="whisker"/>'
            f'<line x1="{left + lo * scale:.1f}" x2="{left + lo * scale:.1f}" y1="{mid - 6}" y2="{mid + 6}" class="whisker"/>'
            f'<line x1="{left + hi * scale:.1f}" x2="{left + hi * scale:.1f}" y1="{mid - 6}" y2="{mid + 6}" class="whisker"/>'
            f'<text class="ink" x="{left + scale + 12}" y="{mid}" dominant-baseline="middle">'
            f'<tspan font-weight="600">{_pct(rate)}</tspan>'
            f'<tspan class="muted" x="{left + scale + 12}" dy="15">{_pct(lo)} to {_pct(hi)}</tspan></text>'
        )
    ticks = "".join(
        f'<line x1="{left + t * scale / 4:.1f}" x2="{left + t * scale / 4:.1f}" y1="{top}" y2="{axis_y}" class="gridline"/>'
        f'<text class="muted" x="{left + t * scale / 4:.1f}" y="{axis_y + 16}" text-anchor="middle">{t * 25}%</text>'
        for t in range(5)
    )
    title = (f'<text class="ink" x="{left + scale / 2:.1f}" y="{axis_y + 36}" text-anchor="middle">'
             "Share of cells passed. Whiskers: 95% Wilson interval</text>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
            f'role="img" aria-label="Pass rate per model with 95% Wilson intervals">{ticks}{"".join(marks)}{title}</svg>')


def _leaderboard(summary: dict) -> str:
    body = []
    for model, s in summary.items():
        lo, hi = wilson_interval(s["passes"], s["total"])
        cost = (f"${s['cost']:.4f}" if s["cost_known"] and s["cost"] else "n/a")
        tokens = f"{s['in'] + s['out']:,}" + (" (est.)" if s["estimated"] else "")
        body.append(
            f"<tr><td>{_esc(model)}</td><td class='num'>{s['passes']}/{s['total']}</td>"
            f"<td class='num'><strong>{_pct(s['passes'] / s['total'])}</strong> "
            f"<span class='ci'>[{_pct(lo)}, {_pct(hi)}]</span></td>"
            f"<td class='num'>{tokens}</td><td class='num'>{cost}</td></tr>"
        )
    return ("<table><thead><tr><th>Model</th><th class='num'>Passed</th>"
            "<th class='num'>Score (95% CI)</th><th class='num'>Tokens</th><th class='num'>Cost</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>")


def _tier_table(summary: dict) -> str:
    tiers = ("predict", "translate", "write", "fix")
    labels = {"predict": "Predict output", "translate": "Translate", "write": "Write", "fix": "Fix"}
    head = "".join(f"<th class='num'>{_esc(m)}</th>" for m in summary)
    rows = []
    for tier in tiers:
        cells = "".join(
            f"<td class='num'>{_rate_cell(*s['tier'].get(tier, [0, 0]))}</td>" for s in summary.values()
        )
        rows.append(f"<tr><td>{labels[tier]}</td>{cells}</tr>")
    return f"<table><thead><tr><th>Tier</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _feature_table(records: list) -> str:
    models = list(dict.fromkeys(r["model"] for r in records))
    counts: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in records:
        for feat, value in r["features"].items():
            counts[(feat, value)][r["model"]][0] += int(r["passed"])
            counts[(feat, value)][r["model"]][1] += 1
    head = "".join(f"<th class='num'>{_esc(m)}</th>" for m in models)
    rows = []
    for (feat, value), per_model in sorted(counts.items()):
        cells = "".join(f"<td class='num'>{_rate_cell(*per_model.get(m, [0, 0]))}</td>" for m in models)
        rows.append(f"<tr><td>{_esc(feat)}</td><td>{_esc(value)}</td>{cells}</tr>")
    return ("<table><thead><tr><th>Feature</th><th>Value</th>" + head + "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def _language_table(records: list) -> str:
    models = list(dict.fromkeys(r["model"] for r in records))
    langs: dict = {}
    for r in records:
        langs.setdefault((r["seed"], r["language"]), {})
        langs[(r["seed"], r["language"])].setdefault(r["model"], [0, 0])
        langs[(r["seed"], r["language"])][r["model"]][0] += int(r["passed"])
        langs[(r["seed"], r["language"])][r["model"]][1] += 1
    head = "".join(f"<th class='num'>{_esc(m)}</th>" for m in models)
    rows = []
    for (seed, name), per_model in sorted(langs.items()):
        cells = "".join(f"<td class='num'>{_rate_cell(*per_model.get(m, [0, 0]))}</td>" for m in models)
        rows.append(f"<tr><td>{_esc(name)} <span class='meta'>seed {seed}</span></td>{cells}</tr>")
    return ("<table><thead><tr><th>Language</th>" + head + "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def _attempt_html(attempt: dict) -> str:
    verdict = "passed" if attempt["passed"] else "failed"
    parts = [
        f"<p class='note'>Attempt {attempt['attempt']}: {verdict}, "
        f"{attempt['tests_passed']}/{attempt['tests_total']} tests, "
        f"{attempt['input_tokens']} in / {attempt['output_tokens']} out tokens</p>",
        "<p class='note'>Model answer</p>", f"<pre>{_esc(attempt['answer'])}</pre>",
    ]
    if attempt["feedback"]:
        parts += ["<p class='note'>Grader feedback</p>", f"<pre>{_esc(attempt['feedback'])}</pre>"]
    if attempt["output"]:
        parts += ["<p class='note'>Interpreter output</p>", f"<pre>{_esc(attempt['output'])}</pre>"]
    return "".join(parts)


def _drilldown(records: list) -> str:
    items = []
    for r in sorted(records, key=lambda x: (x["task_id"], x["seed"], x["model"])):
        status = "pass" if r["passed"] else "fail"
        head = (f"<summary><span class='{status}'>{'PASS' if r['passed'] else 'FAIL'}</span> "
                f"{_esc(r['task_id'])} &middot; {_esc(r['language'])} (seed {r['seed']}) &middot; "
                f"{_esc(r['model'])} &middot; {r['attempts_used']} attempt(s)</summary>")
        if r.get("errored"):  # no attempts were made: show the unexpected error instead
            body = f"<p class='note'>Errored cell: {_esc(r['errored'])}</p>"
        else:
            first = r["attempts"][0]
            prompt = f"<p class='note'>Prompt (attempt 1)</p><pre>{_esc(first['prompt'])}</pre>"
            body = prompt + "".join(_attempt_html(a) for a in r["attempts"])
        items.append(f"<details>{head}{body}</details>")
    return "".join(items)


def _task_matrix(records: list) -> str:
    models = list(dict.fromkeys(r["model"] for r in records))
    tasks: dict = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in records:
        tasks[(r["tier"], r["task_id"], r["title"])][r["model"]][0] += int(r["passed"])
        tasks[(r["tier"], r["task_id"], r["title"])][r["model"]][1] += 1
    head = "".join(f"<th class='num'>{_esc(m)}</th>" for m in models)
    rows = []
    for (_tier, task_id, title), per_model in sorted(tasks.items()):
        cells = "".join(f"<td class='num'>{_rate_cell(*per_model.get(m, [0, 0]))}</td>" for m in models)
        rows.append(f"<tr><td>{_esc(task_id)} <span class='meta'>{_esc(title)}</span></td>{cells}</tr>")
    return ("<table><thead><tr><th>Task</th>" + head + "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def render_report(records: list) -> str:
    summary = _summarise(records)
    languages = {r["seed"] for r in records}
    tasks = {r["task_id"] for r in records}
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>babel-bench report</title><style>{CSS}</style></head>
<body><main>
<h1>babel-bench</h1>
<p class="lede">Models write and fix programs in programming languages they have never seen, using only a
generated reference manual. Each language is derived from a seed, so no model has trained on it.</p>
<p class="meta">{len(languages)} generated language(s) &middot; {len(tasks)} task(s) &middot;
{len(records)} cell(s) &middot; generated {generated}</p>

<h2>Leaderboard</h2>
{_leaderboard(summary)}
<p class="note">Score = share of cells passed (any attempt). Intervals are 95% Wilson intervals over cells.
Cells are not independent across tasks within a language, so treat small differences with care.</p>
{_bar_chart(summary)}

<h2>By tier</h2>
{_tier_table(summary)}

<h2>By language feature</h2>
<p class="note">Each generated language differs in these features. Rates show how much each choice moves
difficulty.</p>
{_feature_table(records)}

<h2>By language</h2>
{_language_table(records)}

<h2>By task</h2>
{_task_matrix(records)}

<h2>Drill-down</h2>
<p class="note">Every cell: the prompt sent, the model answer, the grader feedback and the interpreter output.</p>
{_drilldown(records)}
</main></body></html>
"""
