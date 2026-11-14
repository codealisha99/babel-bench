"""Landing-page showcase: every printed value is what the interpreter produces, and no hidden test leaks."""

from babel_bench.api import views
from babel_bench.api.app import create_app
from babel_bench.api.config import Settings
from babel_bench.api.worker import grade
from babel_bench.showcase import build
from babel_bench.spec import generate
from babel_bench.syntax import parse
from babel_bench.tasks import ALL_TASKS, instantiate
from fastapi.testclient import TestClient


def test_showcase_outputs_match_the_interpreter():
    data = build()
    assert len(data["languages"]) >= 10
    for lang in data["languages"]:
        spec = generate(lang["seed"])
        inst = instantiate(next(t for t in ALL_TASKS if t.id == "predict.squares"), spec)
        assert lang["output"] == inst.expected_output.rstrip()
        assert lang["program"] == inst.shown
        assert {p["id"] for p in lang["probes"]} >= {"division", "modulo", "index", "zero", "logic"}


def test_hidden_tests_do_not_expose_arguments_or_expectations():
    task_id = "write.sum_to"
    bad = "budru solve(n) poutrai\n  kezvai 0 .\nteevu"
    outcomes = grade({"seed": 1, "task_id": task_id, "program": bad})["tests"]
    visible = [t for t in outcomes if t["visible"]]
    hidden = [t for t in outcomes if not t["visible"]]
    assert visible and hidden
    for t in hidden:
        assert t["got"] == "" and t["expected"] == "" and t["label"].startswith("hidden test ")


def test_error_line_points_into_the_program_even_inside_a_fence():
    program = "```\nbudru solve(n) poutrai\n  kezvai n + zz .\nteevu\n```"
    result = grade({"seed": 1, "task_id": "write.sum_to", "program": program})
    assert result["error_line"] == 3
    assert "line " not in result["feedback"]


def test_starter_parses_and_is_not_the_solution():
    for task in ALL_TASKS:
        if task.tier == "predict":
            continue
        for seed in (1, 2):
            program = views.starter(seed, task.id)
            parse(program, generate(seed))  # syntactically valid
            if task.tier != "fix":
                oracle = instantiate(task, generate(seed)).oracle_answer
                assert program.strip() != oracle.strip("`\n").strip()


def test_starter_endpoint():
    client = TestClient(create_app(Settings(allowed_origins=("https://landing.example",))))
    ok = client.get("/api/languages/1/tasks/write.sum_to/starter")
    assert ok.status_code == 200 and ok.json()["program"]
    assert client.get("/api/languages/1/tasks/predict.squares/starter").status_code == 400
    assert client.get("/api/languages/1/tasks/nope/starter").status_code == 404
