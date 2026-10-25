#!/usr/bin/env python3
"""Run crayon's model evals through promptfoo, and record what they decide.

The evals answer one question: can an author rely on crayon, with the model they
use, to keep them in control and keep the record true? The answer drives two
decisions, and every result file carries both in its ``decision`` block:

1. Ship: a skill change ships only if no case that passed three out of three
   times on the gate model now passes fewer times.
2. Supported models: ``docs/evals.md`` lists a model as supported only if it
   passes every critical case three out of three times, on the current skills.

Dev-time evaluation material: never part of the product gate, never run in CI.
Paid runs are started by hand with ``OPENROUTER_API_KEY`` in the environment::

    python3 validation/evals/run.py B --model anthropic/claude-haiku-5.5
    python3 validation/evals/run.py all --roster
    python3 validation/evals/run.py all --roster --dry-run
    python3 validation/evals/run.py --table --write

promptfoo runs the cases (``pf_provider.py``) and grades them (``pf_assert.py``);
``promptfoo view`` shows every run. ``--dry-run`` answers every case with its own
known-good reply: no network, no key, no cost.

A clean, complete, paid run writes one result file per lane and model to
``results/<date>-<lane>-<model>-k<K>-<split>.json`` (never overwriting). Anything
else (a dry run, a ``--filter``, an error, a budget stop) goes to the
gitignored ``results/raw/``, so a partial run can never stand in for a baseline.
Every run also keeps promptfoo's output and one record per call, with the
request's messages and the full trace, under ``results/raw/<stamp>/``.

Exit codes, as every checker in this repository: 0 every case passed every run;
1 at least one case failed a run; 2 a run-level error (API error, empty answer,
sandbox error, budget reached, nothing ran). Branch on 2 before reading a pass
rate.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lanes  # noqa: E402
import sandbox  # noqa: E402
import skills as skillmod  # noqa: E402
from openrouter import BudgetExceeded, FileBudget, OpenRouter, ProviderError  # noqa: E402
from pf_assert import GRADE_ERROR  # noqa: E402

RESULTS = HERE / "results"
RAW = RESULTS / "raw"
ROSTER = HERE / "models.json"
HOLDOUT = HERE / "cases" / "holdout.json"
DOCS = skillmod.REPO / "docs" / "evals.md"
PROMPTFOO = "promptfoo@0.124.1"
#: What every result's figures measure, stated in its meta.
MEASURES = "skill-following"
#: The opening sentence of every promptfoo configuration and both READMEs.
PURPOSE = ("can an author rely on crayon, with the model they use, to keep them in "
           "control and keep the record true?")
#: Runs per case a decision needs.
DECISION_RUNS = 3
#: Every file whose change alters what a case sees or how it is graded.
KIT_FILES = ("agent.py", "digest.py", "grade.py", "lanes.py", "pf_assert.py", "pf_provider.py",
             "sandbox.py", "skills.py", "fixtures/states.sh")
KIT_TREES = ("cases", "workshop", "fixtures/toyq", "fixtures/tidewatch")
TABLE_BEGIN = "<!-- supported-models:begin -->"
TABLE_END = "<!-- supported-models:end -->"


def load_roster(path=ROSTER):
    roster = json.loads(Path(path).read_text(encoding="utf-8"))
    by_id = dict((model["id"], model) for model in roster["models"])
    if roster["gate"] not in by_id:
        raise ValueError("models.json: gate %r is not in models" % roster["gate"])
    return roster, by_id


def model_slug(model_id):
    return re.sub(r"[^A-Za-z0-9._-]+", "__", model_id)


def crayon_version():
    try:
        out = subprocess.run(
            [sys.executable, str(skillmod.REPO / "crayon.py"), "version", "--json"],
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


def kit_sha256(root=HERE):
    """One digest over the kit: the cases (not the recorded states), the graders,
    the agent surface, the sandbox and the fixture.

    A skill edit re-records ``states.json``, so the recorded states are left out:
    two runs on different skills but the same kit can be compared, and two runs
    on different kits cannot.
    """
    root = Path(root)
    paths = [root / name for name in KIT_FILES]
    for tree in KIT_TREES:
        paths.extend(path for path in sorted((root / tree).rglob("*"))
                     if path.is_file() and "__pycache__" not in path.parts
                     and path.name != "states.json")
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def holdout_ids(path=HOLDOUT):
    return set(json.loads(Path(path).read_text(encoding="utf-8"))["ids"])


def select(lane_name, split, pattern=None):
    """The lane's cases for ``split`` (dev, holdout or all), then ``--filter``."""
    cases = lanes.LANES[lane_name]["load"]()
    if lane_name == "B" and split != "all":
        held = holdout_ids()
        cases = [c for c in cases if (c["id"] in held) == (split == "holdout")]
    if pattern:
        cases = [c for c in cases if re.search(pattern, c["id"])]
    return cases


# --- promptfoo ------------------------------------------------------------------


def promptfoo_config(lane_name, cases, model_id, mode, run_dir, jobs, budget_path):
    """The promptfoo configuration for one lane on one model, as a dict."""
    tests = [{
        "description": "%s %s" % (case["id"], case.get("why", "")[:120]),
        "vars": {"lane": lane_name, "case_id": case["id"]},
        "metadata": {"protects": case["protects"], "critical": case["critical"],
                     "group": case.get("group", "selection")},
        "assert": [{"type": "python", "value": "file://%s" % (HERE / "pf_assert.py"),
                    "metric": lanes.metric(case)}],
    } for case in cases]
    return {
        "description": "crayon evals, lane %s (%s), %s: %s" % (
            lane_name, lanes.LANES[lane_name]["title"], model_id, PURPOSE),
        "prompts": ["{{case_id}}"],
        "providers": [{
            "id": "file://%s" % (HERE / "pf_provider.py"),
            "label": model_id,
            "config": {"model": model_id, "mode": mode, "run": str(run_dir),
                       "budget": str(budget_path), "pool": jobs, "workers": jobs},
        }],
        "tracing": {"enabled": True, "otlp": {"http": {}}},
        "tests": tests,
    }


def run_promptfoo(config, directory, repeat, jobs):
    """Write the configuration, run ``promptfoo eval``, return its output as a dict."""
    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / "promptfooconfig.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    out_path = directory / "promptfoo-output.json"
    env = dict(os.environ, PROMPTFOO_DISABLE_TELEMETRY="1", PROMPTFOO_DISABLE_UPDATE="1",
               PROMPTFOO_PYTHON=sys.executable)
    done = subprocess.run(
        ["npx", "-y", PROMPTFOO, "eval", "-c", str(config_path), "--no-cache",
         "--repeat", str(repeat), "-j", str(jobs), "-o", str(out_path)],
        cwd=str(directory), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (directory / "promptfoo.log").write_bytes(done.stdout)
    # promptfoo exits 100 when a test failed; anything else non-zero is its own error.
    if done.returncode not in (0, 100) or not out_path.is_file():
        raise RuntimeError("promptfoo eval exited %d; see %s" % (done.returncode,
                                                                 directory / "promptfoo.log"))
    return json.loads(out_path.read_text(encoding="utf-8"))


def rows(output):
    """promptfoo's result rows as ``(case_id, outcome, reason)``.

    ``outcome`` is ``pass``, ``fail`` or ``error``: a provider error or a check
    that could not be evaluated is an error, never a failure.
    """
    found = []
    for row in output["results"]["results"]:
        case_id = row["vars"]["case_id"]
        grading = row.get("gradingResult") or {}
        reason = grading.get("reason") or row.get("error") or ""
        if row.get("error") and not grading:
            outcome = "error"
        elif reason.startswith(GRADE_ERROR):
            outcome = "error"
        elif row.get("success"):
            outcome = "pass"
        else:
            outcome = "fail"
        found.append((case_id, outcome, row.get("error") or reason))
    return found


def read_records(run_dir, model_id):
    """The provider's per-call records for one model, grouped by case id."""
    grouped = {}
    for path in sorted((Path(run_dir) / "records").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["model"] == model_id:
            grouped.setdefault(record["id"], []).append(record)
    return grouped


# --- results and decisions -------------------------------------------------------


def summarise(lane_name, spec, cases, found, records, meta_base, repeat):
    """One lane on one model, K runs -> its result: meta, decision and per-case counts."""
    entries = []
    for case in cases:
        outcomes = [(outcome, reason) for case_id, outcome, reason in found
                    if case_id == case["id"]]
        calls = records.get(case["id"], [])
        entry = {
            "id": case["id"],
            "protects": case["protects"],
            "critical": case["critical"],
            "runs": len(outcomes),
            "passes": sum(1 for outcome, _ in outcomes if outcome == "pass"),
            "errors": sum(1 for outcome, _ in outcomes if outcome == "error"),
            "cost": round(sum(call["cost"] for call in calls), 6),
        }
        failed = [reason[:300] for outcome, reason in outcomes if outcome != "pass"]
        if failed:
            entry["failed"] = failed
        entries.append(entry)
    calls = [call for group in records.values() for call in group]
    runs = repeat
    passes = sum(entry["passes"] for entry in entries)
    meta = dict(meta_base)
    meta.update(
        lane=lane_name,
        lane_title=lanes.LANES[lane_name]["title"],
        model=spec["id"],
        why=spec.get("why"),
        provider_pin=spec.get("provider"),
        runs=runs,
        total_cases=len(entries),
        critical_cases=sum(1 for entry in entries if entry["critical"]),
        passes=passes,
        pass_rate=round(passes / float(runs * len(entries) or 1), 4),
        stable_pass=sum(1 for e in entries if e["runs"] and e["passes"] == e["runs"] == runs),
        stable_fail=sum(1 for e in entries if e["passes"] == 0 and not e["errors"]),
        flaky=sum(1 for e in entries if 0 < e["passes"] < e["runs"]),
        errors=sum(entry["errors"] for entry in entries),
        cost_usd=round(sum(call["cost"] for call in calls), 6),
        tokens={"in": sum(call["tokens"]["in"] for call in calls),
                "out": sum(call["tokens"]["out"] for call in calls)},
        truncated=sum(1 for call in calls if call.get("truncated")),
        retries=sum(call.get("retries", 0) for call in calls),
        budget_stop=next((call["error"] for call in calls if call.get("budget_stop")), None),
    )
    return {"meta": meta, "decision": {}, "cases": entries}


def decidable(meta):
    """Why a result cannot decide anything, or None when it can."""
    if meta["dry_run"]:
        return "a dry run answers with known-good replies; it observes no model"
    if meta["partial"]:
        return "a --filter run covers part of the lane"
    if meta["errors"] or meta["budget_stop"]:
        return "the run had run-level errors"
    if meta["runs"] < DECISION_RUNS:
        return "a decision needs %d runs per case; this run has %d" % (DECISION_RUNS, meta["runs"])
    return None


def decide_supported(summary):
    """Does this result support the model: every critical case passed every run?"""
    meta = summary["meta"]
    blocked = decidable(meta)
    if blocked:
        return {"verdict": "undecided", "reason": blocked}
    if meta["split"] != "all":
        return {"verdict": "undecided",
                "reason": "support is decided on every case; this run covers the %s split"
                          % meta["split"]}
    failing = [entry["id"] for entry in summary["cases"]
               if entry["critical"] and entry["passes"] < entry["runs"]]
    if failing:
        return {"verdict": "not supported", "critical_failing": failing,
                "reason": "%d critical case(s) did not pass every run" % len(failing)}
    return {"verdict": "supported",
            "reason": "every critical case (%d) passed every run" % meta["critical_cases"]}


def committed(results=RESULTS):
    """Every committed result file, oldest first, as ``(path, result)``."""
    found = []
    for path in sorted(Path(results).glob("*.json")):
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(result, dict) and "decision" in result:
            found.append((path, result))
    return found


def decide_ship(summary, results=RESULTS):
    """For the gate model: no case that passed every run in the baseline now passes fewer.

    The baseline is the latest committed result for the same lane, model and
    split, run on the same kit (``kit_sha256``): a comparison across kits
    compares different tests and is refused.
    """
    meta = summary["meta"]
    blocked = decidable(meta)
    if blocked:
        return {"verdict": "undecided", "reason": blocked}
    baseline = None
    for path, result in committed(results):
        other = result["meta"]
        if (other["lane"], other["model"], other["split"]) == (meta["lane"], meta["model"],
                                                              meta["split"]):
            if other["kit_sha256"] != meta["kit_sha256"]:
                continue
            baseline = (path, result)
    if baseline is None:
        return {"verdict": "undecided",
                "reason": "no committed baseline on this kit; this result becomes the baseline"}
    path, result = baseline
    before = dict((entry["id"], entry) for entry in result["cases"])
    regressions = [entry["id"] for entry in summary["cases"]
                   if entry["id"] in before
                   and before[entry["id"]]["passes"] == before[entry["id"]]["runs"]
                   and entry["passes"] < entry["runs"]]
    verdict = "hold" if regressions else "ship"
    return {"verdict": verdict, "baseline": path.name, "regressions": regressions,
            "reason": ("%d case(s) that passed every run in the baseline now fail a run"
                       % len(regressions)) if regressions
            else "no case that passed every run in the baseline fails a run"}


def destination(summary, stamp):
    meta = summary["meta"]
    stem = "%s-%s-%s-k%d-%s" % (meta["date"], meta["lane"], model_slug(meta["model"]),
                                meta["runs"], meta["split"])
    tag = None
    if meta["dry_run"]:
        tag = "dry"
    elif meta["errors"] or meta["budget_stop"]:
        tag = "errored"
    elif meta["partial"]:
        tag = "partial"
    if tag:
        return RAW / stamp / ("%s-%s.json" % (stem, tag))
    path = RESULTS / ("%s.json" % stem)
    suffix = 2
    while path.exists():
        path = RESULTS / ("%s-%d.json" % (stem, suffix))
        suffix += 1
    return path


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# --- the supported-models table ---------------------------------------------------


def supported_table(results=RESULTS, roster_path=ROSTER):
    """The table ``docs/evals.md`` carries: one row per certified model."""
    roster, _ = load_roster(roster_path)
    current = skillmod.bundle_sha256()
    lines = ["| Model | Backend | Critical cases | Standard cases | Status |",
             "|---|---|---|---|---|"]
    for model in roster["models"]:
        latest = None
        for path, result in committed(results):
            meta = result["meta"]
            if meta["model"] == model["id"] and meta["lane"] == "B" and meta["split"] == "all":
                latest = (path, result)
        backend = ", ".join(model["provider"]["order"])
        name = model["id"] + (" (gate)" if model["id"] == roster["gate"] else "")
        if latest is None:
            lines.append("| %s | %s | no result | no result | not yet run |" % (name, backend))
            continue
        path, result = latest
        cases = result["cases"]
        critical = [c for c in cases if c["critical"]]
        standard = [c for c in cases if not c["critical"]]
        ok = lambda group: sum(1 for c in group if c["passes"] == c["runs"])  # noqa: E731
        verdict = result["decision"]["supported"]
        if result["meta"]["skills_sha256"] != current:
            status = "stale: the skills changed since %s; re-run" % path.name
        elif verdict["verdict"] == "supported":
            status = "supported (%s)" % path.name
        elif verdict["verdict"] == "not supported":
            status = "not supported: %s (%s)" % (", ".join(verdict["critical_failing"]),
                                                path.name)
        else:
            status = "undecided: %s" % verdict["reason"]
        lines.append("| %s | %s | %d of %d passed every run | %d of %d passed every run | %s |"
                     % (name, backend, ok(critical), len(critical), ok(standard), len(standard),
                        status))
    return "\n".join(lines) + "\n"


def write_table(docs=DOCS, table=None):
    text = docs.read_text(encoding="utf-8")
    begin, end = text.index(TABLE_BEGIN) + len(TABLE_BEGIN), text.index(TABLE_END)
    table = supported_table() if table is None else table
    docs.write_text(text[:begin] + "\n" + table + text[end:], encoding="utf-8")


# --- the run ----------------------------------------------------------------------


def preflight(spec, budget_path):
    """One tiny call: is this model reachable on its pinned backend? Charged to the run."""
    try:
        OpenRouter(FileBudget(budget_path)).complete(
            dict(spec, max_tokens=256),
            [{"role": "user", "content": "Reply with the single word: ok"}],
            scope=spec["id"])
    except ProviderError as exc:
        return str(exc)
    return None


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("lane", nargs="?", choices=sorted(lanes.LANES) + ["all"])
    who = parser.add_mutually_exclusive_group()
    who.add_argument("--model", action="append", help="a roster model id (repeatable)")
    who.add_argument("--roster", action="store_true", help="every model in models.json")
    parser.add_argument("--split", choices=("all", "dev", "holdout"), default="all",
                        help="lane B cases: every case, the dev split, or the held-out "
                             "split (default all)")
    parser.add_argument("--filter", help="only cases whose id matches this regex")
    parser.add_argument("--dry-run", action="store_true",
                        help="answer every case with its known-good reply; no network, no cost")
    parser.add_argument("--jobs", type=int, default=4,
                        help="cases in flight, one workshop each (default 4)")
    parser.add_argument("--budget", type=float, help="override the sweep cap in USD")
    parser.add_argument("--repeat", type=int, default=DECISION_RUNS, metavar="K",
                        help="runs per case (default %d, what a decision needs)" % DECISION_RUNS)
    parser.add_argument("--table", action="store_true",
                        help="print the supported-models table from the committed results")
    parser.add_argument("--write", action="store_true",
                        help="with --table: write it into docs/evals.md")
    args = parser.parse_args(argv)
    if not args.table and (args.lane is None or not (args.model or args.roster)):
        parser.error("a lane and --model or --roster are required")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        import opentelemetry.sdk  # noqa: F401 - the provider's dependency, checked here once
    except ImportError:
        print("run the evals in their environment: uv run --project validation/evals "
              "python validation/evals/run.py ...", file=sys.stderr)
        return 2
    if args.table:
        table = supported_table()
        if args.write:
            write_table(table=table)
        sys.stdout.write(table)
        return 0
    if args.repeat < 1 or args.jobs < 1:
        print("--repeat and --jobs take a count of 1 or more", file=sys.stderr)
        return 2
    roster, by_id = load_roster()
    if args.roster:
        models = list(roster["models"])
    else:
        unknown = [m for m in args.model if m not in by_id]
        if unknown:
            print("not in models.json: %s" % ", ".join(unknown), file=sys.stderr)
            return 2
        models = [by_id[m] for m in args.model]
    lane_names = sorted(lanes.LANES) if args.lane == "all" else [args.lane]
    loaded = dict((name, select(name, args.split, args.filter)) for name in lane_names)
    if not any(loaded.values()):
        print("no case matched; nothing ran", file=sys.stderr)
        return 2
    now = datetime.datetime.now()
    stamp = now.strftime("%Y-%m-%d-%H%M%S")
    run_dir = RAW / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    budget_path = run_dir / "budget.json"
    mode = "dry" if args.dry_run else "live"
    if loaded.get("B"):
        sandbox.ensure()
    if not args.dry_run:
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("OPENROUTER_API_KEY is not set", file=sys.stderr)
            return 2
        caps = roster["caps"]
        FileBudget(budget_path, args.budget if args.budget is not None else caps["sweep_usd"],
                   caps["per_model_usd"] * args.repeat)
        if loaded.get("B"):
            try:
                sandbox.workers(args.jobs)
            except sandbox.SandboxError as exc:
                print("lane B needs its workshops: %s" % exc, file=sys.stderr)
                return 2
    meta_base = {
        "measures": MEASURES,
        "engine": PROMPTFOO,
        "date": now.strftime("%Y-%m-%d"),
        "crayon_version": crayon_version(),
        "repo_head": git_head(),
        "skills_sha256": skillmod.bundle_sha256(),
        "kit_sha256": kit_sha256(),
        "split": args.split,
        "partial": bool(args.filter),
        "dry_run": args.dry_run,
    }
    worst = 0
    for spec in models:
        gate = spec["id"] == roster["gate"]
        if not args.dry_run:
            try:
                problem = preflight(spec, budget_path)
            except BudgetExceeded as exc:
                print("budget stop at the preflight of %s: %s" % (spec["id"], exc),
                      file=sys.stderr)
                return 2
            if problem:
                print("-- %-30s SKIPPED: unreachable on its pinned backend: %s"
                      % (spec["id"], problem[:400]))
                worst = 2
                continue
        for name in lane_names:
            cases = loaded[name]
            if not cases:
                continue
            directory = run_dir / ("%s-%s" % (name, model_slug(spec["id"])))
            config = promptfoo_config(name, cases, spec["id"], mode, directory, args.jobs,
                                      budget_path)
            try:
                output = run_promptfoo(config, directory, args.repeat, args.jobs)
            except RuntimeError as exc:
                print("%-2s %-30s ERROR: %s" % (name, spec["id"], exc), file=sys.stderr)
                worst = 2
                continue
            summary = summarise(name, spec, cases, rows(output),
                                read_records(directory, spec["id"]),
                                dict(meta_base, gate_model=gate), args.repeat)
            summary["decision"]["supported"] = decide_supported(summary)
            if gate:
                summary["decision"]["ship"] = decide_ship(summary)
            path = destination(summary, stamp)
            write_json(path, summary)
            meta = summary["meta"]
            print("%-2s %-30s %3d/%-3d passes (k=%d)  settled pass %d  flaky %d  settled fail %d"
                  "  %d error  $%.4f  -> %s"
                  % (name, spec["id"], meta["passes"], meta["runs"] * meta["total_cases"],
                     meta["runs"], meta["stable_pass"], meta["flaky"], meta["stable_fail"],
                     meta["errors"], meta["cost_usd"], path.relative_to(skillmod.REPO)))
            for key in ("supported", "ship"):
                if key in summary["decision"]:
                    verdict = summary["decision"][key]
                    print("   %s: %s - %s" % (key, verdict["verdict"], verdict["reason"]))
            for entry in summary["cases"]:
                if entry["passes"] < entry["runs"] or entry["runs"] < meta["runs"]:
                    label = "FLAKY" if entry["passes"] else "FAIL "
                    print("   %s %s %d/%d  %s" % (label, entry["id"], entry["passes"],
                                                 entry["runs"],
                                                 (entry.get("failed") or ["(not run)"])[0][:200]))
            if meta["errors"] or meta["budget_stop"]:
                worst = 2
            elif meta["passes"] < meta["runs"] * meta["total_cases"] and worst < 1:
                worst = 1
            if meta["budget_stop"]:
                print("budget stop: %s" % meta["budget_stop"], file=sys.stderr)
                return 2
    if not args.dry_run:
        state = FileBudget(budget_path).state()
        print("spent $%.4f of $%.2f" % (state["spent"], state["cap"]))
    return worst


if __name__ == "__main__":
    sys.exit(main())
