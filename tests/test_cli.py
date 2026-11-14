"""Command line argument validation."""

import pytest

from babel_bench.cli import main


@pytest.mark.parametrize("value", ["0", "-1"])
def test_attempts_must_be_at_least_one(value, capsys):
    with pytest.raises(SystemExit) as info:
        main(["run", "--seeds", "1", "--model", "oracle", "--attempts", value])
    assert info.value.code == 2
    assert "attempts must be at least 1" in capsys.readouterr().err


def test_unknown_model_is_a_clean_error(tmp_path, capsys):
    code = main(["run", "--seeds", "1", "--model", "nope", "--out", str(tmp_path / "r.jsonl")])
    err = capsys.readouterr().err
    assert code == 2
    assert "unknown model spec: nope" in err and "Traceback" not in err
    assert not (tmp_path / "r.jsonl").exists()


def test_old_tier_name_is_a_clean_error(tmp_path, capsys):
    code = main(["run", "--seeds", "1", "--model", "oracle", "--task", "read", "--out", str(tmp_path / "r.jsonl")])
    assert code == 2
    assert "unknown task or tier: ['read']" in capsys.readouterr().err


def test_missing_report_input_is_a_clean_error(tmp_path, capsys):
    code = main(["report", str(tmp_path / "missing.jsonl"), "--out", str(tmp_path / "r.html")])
    assert code == 2
    assert "Traceback" not in capsys.readouterr().err


def test_anthropic_without_key_is_a_clean_error(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code = main(["run", "--seeds", "1", "--model", "anthropic", "--out", str(tmp_path / "r.jsonl")])
    assert code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
