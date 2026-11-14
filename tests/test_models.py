"""Model adapters: failures from the model side become ModelError, so one bad reply cannot abort a run."""

import io
import subprocess

import pytest

from babel_bench import models
from babel_bench.models import ModelError, Request, command, openai_compatible

REQ = Request("system", "prompt", "oracle", "naive")


def test_command_timeout_is_a_model_error(monkeypatch):
    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="x", timeout=900)

    monkeypatch.setattr(models.subprocess, "run", slow)
    with pytest.raises(ModelError):
        command("true").complete(REQ)


@pytest.mark.parametrize("body", [b"not json", b'{"choices": []}', b'{"choices": [{"message": 3}]}'])
def test_malformed_openai_reply_is_a_model_error(monkeypatch, body):
    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(models.urllib.request, "urlopen", lambda *a, **k: FakeResponse(body))
    with pytest.raises(ModelError):
        openai_compatible("http://localhost:1/v1", "m").complete(REQ)
