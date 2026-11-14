"""Playground API: guards (size, rate, concurrency, timeout), CORS, and no reference answers exposed."""

import json

import pytest
from fastapi.testclient import TestClient

from babel_bench.api import views
from babel_bench.api.app import create_app
from babel_bench.api.config import Settings
from babel_bench.api.guard import Busy, ConcurrencyGate, RateLimiter, client_ip
from babel_bench.api.sandbox import SandboxTimeout, run_grade
from babel_bench.spec import generate
from babel_bench.tasks import ALL_TASKS, instantiate

ORIGIN = "https://landing.example"


def _client(**overrides):
    return TestClient(create_app(Settings(allowed_origins=(ORIGIN,), **overrides)))


def _oracle(seed, task_id):
    task = next(t for t in ALL_TASKS if t.id == task_id)
    return instantiate(task, generate(seed)).oracle_answer


def test_oracle_program_passes_through_the_api():
    r = _client().post("/api/run", json={"seed": 1, "task_id": "write.sum_to", "program": _oracle(1, "write.sum_to")})
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] and body["tests_passed"] == body["tests_total"]


def test_wrong_and_malformed_programs_get_feedback_not_errors():
    client = _client()
    r = client.post("/api/run", json={"seed": 1, "task_id": "write.sum_to", "program": "((((("})
    assert r.status_code == 200 and not r.json()["passed"]
    assert "syntax error" in r.json()["feedback"]


def test_predict_tasks_are_not_graded_here():
    r = _client().post("/api/run", json={"seed": 1, "task_id": "predict.squares", "program": "1"})
    assert r.status_code == 400


def test_unknown_task_and_extra_fields_are_rejected():
    client = _client()
    assert client.post("/api/run", json={"seed": 1, "task_id": "nope", "program": "x"}).status_code == 404
    assert client.post("/api/run", json={"seed": 1, "task_id": "write.sum_to", "program": "x", "x": 1}).status_code == 422


def test_seed_out_of_range_is_rejected():
    client = _client()
    assert client.get("/api/languages/100000").status_code == 422
    assert client.get("/api/languages/-1").status_code == 422


def test_body_over_limit_is_refused_before_parsing():
    client = _client(max_body_bytes=200)
    big = json.dumps({"seed": 1, "task_id": "write.sum_to", "program": "x" * 500})
    assert client.post("/api/run", content=big, headers={"Content-Type": "application/json"}).status_code == 413


def test_chunked_body_without_length_is_refused():
    def chunks():
        yield b'{"seed": 1}'

    r = _client().post("/api/run", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 411


def test_program_over_limit_is_refused():
    client = _client(max_program_chars=50)
    r = client.post("/api/run", json={"seed": 1, "task_id": "write.sum_to", "program": "x" * 60})
    assert r.status_code == 413


def test_rate_limit_returns_429_per_client():
    client = _client(runs_per_minute=2)
    body = {"seed": 1, "task_id": "write.sum_to", "program": "x"}
    codes = [client.post("/api/run", json=body, headers={"X-Forwarded-For": "1.2.3.4"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert client.post("/api/run", json=body, headers={"X-Forwarded-For": "5.6.7.8"}).status_code == 200


def test_gate_refuses_when_all_slots_are_taken():
    gate = ConcurrencyGate(1)
    with gate.slot():
        with pytest.raises(Busy):
            with gate.slot():
                pass


def test_worker_is_killed_when_it_exceeds_the_wall_clock_limit():
    request = {"seed": 1, "task_id": "write.sum_to", "program": _oracle(1, "write.sum_to")}
    with pytest.raises(SandboxTimeout):
        run_grade(request, timeout_s=0.001)


def test_infinite_loop_is_stopped_by_the_interpreter_inside_the_worker():
    from babel_bench.core import Assign, BoolLit, IntLit, Program, While
    from babel_bench.printer import to_source

    spec = generate(1)
    loop = Program((While(BoolLit(True), (Assign("x", IntLit(1)),)),))
    result = run_grade({"seed": 1, "task_id": "write.sum_to", "program": to_source(loop, spec)}, timeout_s=20)
    assert result["passed"] is False
    assert result["error"] and "limit" in result["error"]


def test_cors_allows_only_the_landing_origin():
    client = _client()
    ok = client.post("/api/run", json={"seed": 1, "task_id": "write.sum_to", "program": "x"}, headers={"Origin": ORIGIN})
    assert ok.headers.get("access-control-allow-origin") == ORIGIN
    other = client.post("/api/run", json={"seed": 1, "task_id": "write.sum_to", "program": "x"},
                        headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_task_listing_never_contains_reference_answers(seed):
    listing = views.tasks(seed)
    text = json.dumps(listing)
    spec = generate(seed)
    for task in ALL_TASKS:
        inst = instantiate(task, spec)
        if inst.kind == "code":
            assert inst.oracle_answer not in text
    assert all("oracle_answer" not in t and "tests" not in t for t in listing["tasks"])
    for entry in listing["tasks"]:
        inst = next(i for i in (instantiate(t, spec) for t in ALL_TASKS) if i.task_id == entry["id"])
        assert [v["expected"] for v in entry["visible"]] == [t.expected for t in inst.visible]


def test_client_ip_uses_the_last_forwarded_entry():
    assert client_ip({"x-forwarded-for": "9.9.9.9, 1.2.3.4"}, "10.0.0.1") == "1.2.3.4"
    assert client_ip({}, "10.0.0.1") == "10.0.0.1"


def test_rate_limiter_window_slides():
    now = [0.0]
    limiter = RateLimiter(1, window=10, clock=lambda: now[0])
    assert limiter.allow("a") and not limiter.allow("a")
    now[0] = 10.0
    assert limiter.allow("a")


def test_on_vercel_the_platform_ip_header_is_used():
    headers = {"x-vercel-forwarded-for": "7.7.7.7", "x-forwarded-for": "1.1.1.1"}
    assert client_ip(headers, "10.0.0.1", on_vercel=True) == "7.7.7.7"


def test_platform_ip_header_is_ignored_off_vercel():
    headers = {"x-vercel-forwarded-for": "7.7.7.7", "x-forwarded-for": "1.1.1.1"}
    assert client_ip(headers, "10.0.0.1", on_vercel=False) == "1.1.1.1"
