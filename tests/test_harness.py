"""Harness behaviour with a scripted model: feedback, resume, cost, errors, report."""

import json

import pytest

from babel_bench.models import ModelError, Request, cost_usd, Completion, scripted, parse_model
from babel_bench.report import wilson_interval, render_report
from babel_bench.runner import build_cells, run_cells

from babel_bench.models import oracle

CELLS_SEEDS = (1, 2)
TASKS = ("write", "translate.gcd")


def _cells():
    return build_cells(CELLS_SEEDS, TASKS)


def test_feedback_is_given_to_the_next_attempt(tmp_path):
    seen = []

    def fn(req: Request) -> str:
        if "## Feedback on your previous attempt" in req.prompt:
            seen.append(req.prompt)
            return req.oracle_answer
        return "this is not a program at all ((("

    summary = run_cells(scripted("retry", fn), _cells(), 2, tmp_path / "r.jsonl", 2)
    assert summary.recorded == len(_cells())
    records = [json.loads(line) for line in (tmp_path / "r.jsonl").read_text().splitlines()]
    assert all(r["passed"] and r["attempts_used"] == 2 for r in records)
    assert all("syntax error" in r["attempts"][0]["feedback"] for r in records if r["kind"] == "code")
    assert len(seen) == len(records)


def test_resume_skips_finished_cells_without_calling_the_model(tmp_path):
    out = tmp_path / "r.jsonl"
    run_cells(oracle(), _cells(), 1, out, 2)
    calls = []

    def fn(req: Request) -> str:
        calls.append(1)
        return req.oracle_answer

    summary = run_cells(scripted("oracle", fn), _cells(), 1, out, 2)
    assert summary.recorded == 0 and summary.skipped == len(_cells())
    assert calls == []


def test_model_errors_leave_cells_unrecorded_so_rerun_retries(tmp_path):
    out = tmp_path / "r.jsonl"
    flaky = {"fail": True}

    def fn(req: Request) -> str:
        if flaky["fail"] and "gcd" in req.prompt:
            raise ModelError("rate limited")
        return req.oracle_answer

    model = scripted("flaky", fn)
    summary = run_cells(model, _cells(), 1, out, 1)
    assert any("rate limited" in e for e in summary.errors)
    assert summary.recorded < len(_cells())
    flaky["fail"] = False
    retry = run_cells(model, _cells(), 1, out, 1)
    assert retry.recorded == len(_cells()) - summary.recorded


def test_token_cost_uses_prices():
    comp = Completion("x", input_tokens=1_000_000, output_tokens=500_000)
    assert cost_usd(comp, (2.0, 10.0)) == pytest.approx(7.0)
    assert cost_usd(comp, None) is None


def test_model_spec_parsing():
    assert parse_model("oracle").label == "oracle"
    assert parse_model("command:claude -p --model haiku").label.startswith("command:")
    with pytest.raises(ValueError):
        parse_model("nonsense")


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and 0.25 < hi < 0.31
    lo, hi = wilson_interval(10, 10)
    assert 0.69 < lo < 0.75 and hi == pytest.approx(1.0)


def test_report_is_self_contained_and_escapes_answers(tmp_path):
    out = tmp_path / "r.jsonl"
    run_cells(oracle(), _cells(), 1, out, 2)
    records = [json.loads(line) for line in out.read_text().splitlines()]
    records[0]["attempts"][0]["answer"] = "<script>alert(1)</script>"
    html = render_report(records)
    assert "<html" in html and "oracle" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "http://" not in html.replace("http://www.w3.org/2000/svg", "")
