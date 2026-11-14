"""Command line: run models, build the report, inspect languages and tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .manual import build_manual
from .models import parse_model
from .report import render_report
from .runner import build_cells, run_cells
from .spec import generate
from .tasks import ALL_TASKS, instantiate, select


def parse_seeds(text: str) -> tuple:
    seeds: list[int] = []
    for part in text.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            seeds += list(range(int(lo), int(hi) + 1))
        elif part.strip():
            seeds.append(int(part))
    if not seeds:
        raise argparse.ArgumentTypeError("no seeds given")
    return tuple(dict.fromkeys(seeds))


def _prices(args) -> tuple | None:
    if args.price_in is None or args.price_out is None:
        return None
    return (args.price_in, args.price_out)


def _summary(path: Path) -> str:
    recs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    per: dict = {}
    for r in recs:
        p = per.setdefault(r["model"], [0, 0])
        p[0] += int(r["passed"])
        p[1] += 1
    return "\n".join(f"  {m:<40} {p}/{t} passed" for m, (p, t) in per.items())


def cmd_run(args) -> int:
    cells = build_cells(args.seeds, tuple(args.tasks) if args.tasks else None)
    print(f"{len(cells)} cells ({len(args.seeds)} languages x {len(cells) // len(args.seeds)} tasks)")
    out = Path(args.out)
    for spec_text in args.models:
        model = parse_model(spec_text, _prices(args))
        summary = run_cells(model, cells, args.attempts, out, args.concurrency)
        print(f"{model.label}: recorded {summary.recorded}, already done {summary.skipped}, "
              f"errors {len(summary.errors)}")
        for err in summary.errors[:5]:
            print(f"  error: {err}", file=sys.stderr)
    print(f"results: {out}")
    return 0


def cmd_report(args) -> int:
    records = []
    for path in args.inputs:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    if not records:
        print("no records found", file=sys.stderr)
        return 1
    Path(args.out).write_text(render_report(records), encoding="utf-8")
    print(f"wrote {args.out} from {len(records)} records")
    return 0


def cmd_demo(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = out_dir / "results.jsonl"
    if results.exists():
        results.unlink()  # the demo always starts fresh
    run_args = argparse.Namespace(
        seeds=parse_seeds("1-3"), models=["oracle", "naive"], tasks=None, attempts=1,
        concurrency=4, out=str(results), price_in=None, price_out=None,
    )
    cmd_run(run_args)
    cmd_report(argparse.Namespace(inputs=[results], out=str(out_dir / "report.html")))
    print(_summary(results))
    print(f"open {out_dir / 'report.html'}")
    return 0


def cmd_show(args) -> int:
    spec = generate(args.seed)
    print(f"# {spec.name} (seed {spec.seed})")
    print(json.dumps(spec.features(), indent=2))
    if args.manual:
        print(build_manual(spec).text)
    if args.task:
        task = select((args.task,))[0]
        inst = instantiate(task, spec)
        print(f"\n## {inst.task_id}: {inst.statement}\n{inst.shown}\nreference:\n{inst.oracle_answer}")
    return 0


def cmd_tasks(_args) -> int:
    for t in ALL_TASKS:
        print(f"{t.id:<24} {t.tier:<10} {t.title}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="babel-bench", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run models over generated languages and tasks")
    run.add_argument("--seeds", type=parse_seeds, default=parse_seeds("1-3"), help="e.g. 1-3 or 4,9")
    run.add_argument("--model", dest="models", action="append", required=True,
                     help="oracle | naive | anthropic[:id] | openai:<url>|<model> | command:<shell>")
    run.add_argument("--task", dest="tasks", action="append", help="task id or tier (repeatable)")
    run.add_argument("--attempts", type=int, default=1)
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument("--out", default="runs/results.jsonl")
    run.add_argument("--price-in", type=float, help="USD per million input tokens")
    run.add_argument("--price-out", type=float, help="USD per million output tokens")
    run.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="render a static HTML report from results JSONL")
    rep.add_argument("inputs", nargs="+")
    rep.add_argument("--out", default="runs/report.html")
    rep.set_defaults(func=cmd_report)

    demo = sub.add_parser("demo", help="keyless demo: 3 languages, oracle and naive baselines, report")
    demo.add_argument("--out-dir", default="runs/demo")
    demo.set_defaults(func=cmd_demo)

    show = sub.add_parser("show", help="print a generated language's manual and a sample task")
    show.add_argument("--seed", type=int, required=True)
    show.add_argument("--manual", action="store_true")
    show.add_argument("--task")
    show.set_defaults(func=cmd_show)

    tasks = sub.add_parser("tasks", help="list task templates")
    tasks.set_defaults(func=cmd_tasks)
    return p


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
