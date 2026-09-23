#!/usr/bin/env python3
"""Run the dogen model evals against one model or the whole roster.

Dev-time evaluation material: never part of the gate, never run in CI. The
gate runs this kit's offline self-tests (``tests/test_evals.py``); paid runs are
started by hand, one at a time, with ``OPENROUTER_API_KEY`` in the environment.

    python3 validation/evals/run.py A --model z-ai/glm-5.3
    python3 validation/evals/run.py A --roster
    python3 validation/evals/run.py all --roster --dry-run

``--dry-run`` answers every case with its own oracle through the stub provider:
no network, no key, no cost. It proves the plumbing and the case files, not a
model.

Results. A clean, complete, paid run writes one slim summary to
``results/<date>-<lane>-<model>.json`` (never overwriting: a second run the
same day gets a ``-2`` suffix). Anything else — a dry run, a ``--filter``, an
error, a budget stop — goes to the gitignored ``results/raw/`` with the reason
in its name, so a partial run can never stand in for a baseline. Every run also
writes the full turns of every case to ``results/raw/`` as JSON lines.

Exit codes, as every checker in this repository: 0 every case passed; 1 at
least one case failed; 2 a run-level error (API error, empty answer, judge
error, budget reached, nothing ran). Branch on 2 before reading a pass rate.
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import grade  # noqa: E402
import lanes  # noqa: E402
import skills as skillmod  # noqa: E402
from openrouter import (  # noqa: E402
    Budget,
    BudgetExceeded,
    OpenRouter,
    ProviderError,
    StubProvider,
)

RESULTS = HERE / "results"
RAW = RESULTS / "raw"
CACHE = HERE / ".cache"
ROSTER = HERE / "models.json"
EXCERPT = 1500


def load_roster(path=ROSTER):
    roster = json.loads(Path(path).read_text(encoding="utf-8"))
    by_id = {model["id"]: model for model in roster["models"]}
    for role in ("gate", "judge", "author"):
        if roster[role] not in by_id:
            raise ValueError("models.json: %s %r is not in models" % (role, roster[role]))
    return roster, by_id


def model_slug(model_id):
    return re.sub(r"[^A-Za-z0-9._-]+", "__", model_id)


def dogen_version():
    try:
        out = subprocess.run(
            [sys.executable, str(skillmod.REPO / "dogen.py"), "version", "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
        ).stdout
        return json.loads(out.decode("utf-8")).get("tool", "unknown")
    except (OSError, ValueError, subprocess.CalledProcessError):
        return "unknown"


def git_head():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(skillmod.REPO),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
        ).stdout.decode("utf-8").strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def scripted(replies):
    """A stub responder that gives ``replies`` in order, then repeats the last."""
    replies = list(replies)
    state = {"next": 0}

    def respond(spec, messages, tools):
        reply = replies[min(state["next"], len(replies) - 1)]
        state["next"] += 1
        return reply

    return respond


def stub_judge(spec, messages, tools):
    return '{"reason": "dry-run stub judge", "pass": true, "score": 5}'


def run_one(lane, case, spec, provider, ctx):
    """One case -> one record. Errors are recorded, never raised (but budget)."""
    started = time.time()
    record = {"id": case["id"], "passed": False, "error": None, "score": 0.0,
              "cost": 0.0, "cached": False}
    trace = None
    try:
        trace = lane["run"](case, spec, provider, ctx)
        for turn in trace["turns"]:
            problem = grade.turn_error(turn)
            if problem:
                raise ProviderError(problem)
        case_ctx = {"judge": ctx.get("judge")}
        graded = grade.grade(case["assert"], trace, case_ctx)
        record.update(passed=graded["passed"], score=round(graded["score"], 3))
        failed = [{"kind": item["kind"], "feedback": item["feedback"]}
                  for item in graded["results"] if not item["pass"]]
        if failed:
            record["failed"] = failed
        record["cost"] += case_ctx.get("judge_cost", 0.0)
    except (ProviderError, grade.GradeError) as exc:
        record["error"] = str(exc)
    if trace is not None:
        turns = trace["turns"]
        record["cost"] += sum(turn["usage"]["cost"] for turn in turns)
        record["cached"] = all(turn.get("cached") for turn in turns)
        record["served_by"] = sorted(set(t.get("served_by", "") for t in turns) - {""})
        record["tokens"] = {
            "in": sum(t["usage"]["prompt_tokens"] for t in turns),
            "out": sum(t["usage"]["completion_tokens"] for t in turns),
        }
        record["truncated"] = any(t.get("finish_reason") == "length" for t in turns)
        if not record["passed"]:
            record["answer"] = grade.render_turns(trace)[:EXCERPT]
    record["cost"] = round(record["cost"], 6)
    record["latency_ms"] = int((time.time() - started) * 1000)
    return record, trace


def run_lane(lane_name, cases, spec, provider_for, ctx, jobs):
    lane = lanes.LANES[lane_name]
    records, traces, stopped = [], {}, None

    def task(case):
        return run_one(lane, case, spec, provider_for(case), ctx)

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [(case, pool.submit(task, case)) for case in cases]
        for case, future in futures:
            try:
                record, trace = future.result()
            except BudgetExceeded as exc:
                stopped = str(exc)
                records.append({"id": case["id"], "passed": False,
                                "error": "not run: %s" % exc, "score": 0.0, "cost": 0.0})
                continue
            records.append(record)
            traces[case["id"]] = trace
    return records, traces, stopped


def summarise(lane_name, spec, records, ctx, partial, stopped, dry_run):
    errors = sum(1 for r in records if r["error"])
    passed = sum(1 for r in records if r["passed"])
    return {
        "meta": {
            "lane": lane_name,
            "lane_title": lanes.LANES[lane_name]["title"],
            "model": spec["id"],
            "provider_pin": spec.get("provider"),
            "judge": ctx["judge_id"],
            "date": ctx["date"],
            "dogen_version": ctx["dogen_version"],
            "repo_head": ctx["repo_head"],
            "skills_sha256": ctx["skills_sha256"],
            "total_cases": len(records),
            "passed": passed,
            "failed": len(records) - passed - errors,
            "errors": errors,
            "pass_rate": round(passed / float(len(records) or 1), 4),
            "cost_usd": round(sum(r.get("cost", 0.0) for r in records), 6),
            "tokens": {
                "in": sum(r.get("tokens", {}).get("in", 0) for r in records),
                "out": sum(r.get("tokens", {}).get("out", 0) for r in records),
            },
            "truncated": sum(1 for r in records if r.get("truncated")),
            "cached_cases": sum(1 for r in records if r.get("cached")),
            "partial": partial,
            "dry_run": dry_run,
            "budget_stop": stopped,
        },
        "cases": records,
    }


def destination(summary, stamp):
    meta = summary["meta"]
    stem = "%s-%s-%s" % (meta["date"], meta["lane"], model_slug(meta["model"]))
    tag = None
    if meta["dry_run"]:
        tag = "dry"
    elif meta["errors"] or meta["budget_stop"]:
        tag = "errored"
    elif meta["partial"]:
        tag = "partial"
    elif meta["total_cases"] and meta["cached_cases"] == meta["total_cases"]:
        # Every answer came from the cache: a re-grade of an earlier run, not a
        # new observation of the model, so it may not stand as a baseline.
        tag = "regrade"
    if tag:
        return RAW / ("%s-%s-%s.json" % (stem, stamp, tag))
    path = RESULTS / ("%s.json" % stem)
    suffix = 2
    while path.exists():
        path = RESULTS / ("%s-%d.json" % (stem, suffix))
        suffix += 1
    return path


def _shown(path):
    try:
        return path.relative_to(skillmod.REPO)
    except ValueError:
        return path


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_traces(path, traces):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for case_id, trace in traces.items():
            if trace is not None:
                handle.write(json.dumps({"id": case_id, "trace": trace}) + "\n")


def preflight_model(provider, spec):
    """One tiny uncached call: is this model reachable on its pinned backend?

    A model the account cannot route to (a data-policy filter, a withdrawn
    backend) fails here once, instead of once per case.
    """
    try:
        provider.complete(
            dict(spec, max_tokens=256),
            [{"role": "user", "content": "Reply with the single word: ok"}],
            cache=False, scope=spec["id"],
        )
    except ProviderError as exc:
        return str(exc)
    return None


def print_problems(records):
    """Failures one per line; identical errors folded into one line with a count."""
    errors = {}
    for record in records:
        if record["error"]:
            errors.setdefault(record["error"], []).append(record["id"])
        elif not record["passed"]:
            for item in record.get("failed", []):
                print("   FAIL  %s [%s] %s" % (record["id"], item["kind"], item["feedback"]))
    for message, ids in errors.items():
        where = ids[0] if len(ids) == 1 else "%s (+%d more)" % (ids[0], len(ids) - 1)
        print("   ERROR %s: %s" % (where, message[:400]))


def preflight_judge(provider, judge_spec):
    """A real call through the pinned judge, parsed as a verdict, before a run."""
    try:
        turn = provider.complete(
            judge_spec,
            [{"role": "user", "content": grade.JUDGE_INSTRUCTIONS.format(
                rubric="The response says hello.", response="hello")}],
            cache=False, scope="judge",
        )
        grade.parse_verdict(turn["content"])
    except (ProviderError, grade.GradeError) as exc:
        raise SystemExit("judge preflight failed (%s): %s" % (judge_spec["id"], exc))


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("lane", choices=sorted(lanes.LANES) + ["all"])
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--model", action="append", help="a roster model id (repeatable)")
    who.add_argument("--roster", action="store_true", help="every candidate in models.json")
    parser.add_argument("--filter", help="only cases whose id matches this regex")
    parser.add_argument("--dry-run", action="store_true",
                        help="answer every case with its oracle; no network, no cost")
    parser.add_argument("--jobs", type=int, default=4, help="cases in flight (default 4)")
    parser.add_argument("--budget", type=float, help="override the sweep cap in USD")
    parser.add_argument("--no-cache", action="store_true", help="bypass the response cache")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    roster, by_id = load_roster()
    if args.roster:
        models = [m for m in roster["models"] if m["role"] == "candidate"]
    else:
        unknown = [m for m in args.model if m not in by_id]
        if unknown:
            print("not in models.json: %s" % ", ".join(unknown), file=sys.stderr)
            return 2
        models = [by_id[m] for m in args.model]
    lane_names = sorted(lanes.LANES) if args.lane == "all" else [args.lane]
    loaded = {}
    for name in lane_names:
        cases = lanes.LANES[name]["load"]()
        if args.filter:
            cases = [c for c in cases if re.search(args.filter, c["id"])]
        loaded[name] = cases
    if not any(loaded.values()):
        print("no case matched; nothing ran", file=sys.stderr)
        return 2

    caps = roster["caps"]
    budget = Budget(args.budget if args.budget is not None else caps["sweep_usd"],
                    caps["per_model_usd"])
    judge_spec = by_id[roster["judge"]]
    needs_judge = any(spec["kind"] == "judge" for cases in loaded.values()
                      for case in cases for spec in case["assert"])
    if args.dry_run:
        judge = (StubProvider(stub_judge), judge_spec)
    else:
        try:
            paid = OpenRouter(budget, cache_dir=None if args.no_cache else CACHE)
        except ProviderError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        judge = (paid, judge_spec)
        if needs_judge:
            preflight_judge(paid, judge_spec)

    now = datetime.datetime.now()
    ctx = {
        "skills": skillmod.load_skills(),
        "skills_sha256": skillmod.bundle_sha256(),
        "dogen_version": dogen_version(),
        "repo_head": git_head(),
        "judge": judge,
        "judge_id": judge_spec["id"],
        "author_spec": by_id[roster["author"]],
        "date": now.strftime("%Y-%m-%d"),
        "cache": not args.no_cache,
    }
    stamp = now.strftime("%H%M%S")
    worst = 0
    for spec in models:
        if not args.dry_run:
            problem = preflight_model(paid, spec)
            if problem:
                print("-- %-30s SKIPPED: unreachable on its pinned backend: %s"
                      % (spec["id"], problem[:400]))
                worst = 2
                continue
        for name in lane_names:
            cases = loaded[name]
            if not cases:
                continue
            oracle = lanes.LANES[name]["oracle"]
            if args.dry_run:
                def provider_for(case, oracle=oracle):
                    return StubProvider(scripted(oracle(case)))
            else:
                def provider_for(case, paid=paid):
                    return paid
            records, traces, stopped = run_lane(name, cases, spec, provider_for, ctx,
                                                args.jobs)
            summary = summarise(name, spec, records, ctx, bool(args.filter), stopped,
                                args.dry_run)
            path = destination(summary, stamp)
            write_json(path, summary)
            write_traces(RAW / ("%s.turns.jsonl" % path.stem), traces)
            meta = summary["meta"]
            print("%-2s %-30s %2d/%-2d pass  %d fail  %d error  $%.4f  -> %s"
                  % (name, spec["id"], meta["passed"], meta["total_cases"],
                     meta["failed"], meta["errors"], meta["cost_usd"],
                     _shown(path)))
            print_problems(records)
            if meta["errors"] or stopped:
                worst = 2
            elif meta["failed"] and worst < 1:
                worst = 1
            if stopped:
                print("budget stop: %s" % stopped, file=sys.stderr)
                return 2
    if not args.dry_run:
        print("spent $%.4f of $%.2f" % (budget.spent, budget.cap))
    return worst


if __name__ == "__main__":
    sys.exit(main())
