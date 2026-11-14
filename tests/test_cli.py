"""Command line argument validation."""

import pytest

from babel_bench.cli import main


@pytest.mark.parametrize("value", ["0", "-1"])
def test_attempts_must_be_at_least_one(value, capsys):
    with pytest.raises(SystemExit) as info:
        main(["run", "--seeds", "1", "--model", "oracle", "--attempts", value])
    assert info.value.code == 2
    assert "attempts must be at least 1" in capsys.readouterr().err
