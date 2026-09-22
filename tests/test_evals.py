#!/usr/bin/env python3
"""The model-eval kit's own tests: offline, stdlib only, no key, no network.

``validation/evals/`` is dev-time evaluation material: its paid runs are started
by hand and never enter the gate. What the gate CAN hold it to is everything
that does not need a model — the transport's request shape, retries, cache and
spend cap against a fake opener; every assertion kind against hand-built turns;
and every case file against its own oracle, so a broken expectation is caught
here rather than blamed on a model in a paid run.
"""

import io
import json
import re
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "validation" / "evals"
sys.path.insert(0, str(EVALS))

import grade  # noqa: E402
import lanes  # noqa: E402
import openrouter  # noqa: E402
import run  # noqa: E402
import skills as skillmod  # noqa: E402
from openrouter import (  # noqa: E402
    Budget,
    BudgetExceeded,
    OpenRouter,
    ProviderError,
    StubProvider,
)

SPEC = {
    "id": "vendor/model-x",
    "max_tokens": 512,
    "provider": {"order": ["vendor"], "allow_fallbacks": False},
    "price_per_mtok": [1.0, 2.0],
}


def turn(content="", calls=(), finish="stop"):
    return {
        "content": content,
        "tool_calls": [
            {"id": "c%d" % i, "name": name, "arguments": json.dumps(args)}
            for i, (name, args) in enumerate(calls)
        ],
        "finish_reason": finish,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0},
        "cached": False,
        "served_by": "test",
    }


def trace(*turns):
    return {"turns": list(turns)}


def bash(command):
    return ("Bash", {"command": command})


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener(object):
    """Replays a script of responses: a dict is a 200 body, an int an HTTP error."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        item = self.script.pop(0)
        if isinstance(item, int):
            raise urllib.error.HTTPError(
                request.full_url, item, "status %d" % item, {}, io.BytesIO(b"{}")
            )
        if isinstance(item, Exception):
            raise item
        return FakeResponse(json.dumps(item).encode("utf-8"))


def ok_body(content="hello", calls=None, cost=0.0123, usage=True):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    body = {"choices": [{"message": message, "finish_reason": "stop"}],
            "provider": "Vendor"}
    if usage:
        body["usage"] = {"prompt_tokens": 1000, "completion_tokens": 100, "cost": cost}
    return body


def client(opener, budget=None, cache_dir=None):
    return OpenRouter(budget or Budget(10.0), cache_dir=cache_dir, api_key="sk-test",
                      sleep=lambda seconds: None, opener=opener)


class TestTransport(unittest.TestCase):
    """E-01 — the one transport: request shape, cost, retries, cache, budget."""

    def test_request_body_pins_the_backend_and_hides_reasoning(self):
        opener = FakeOpener(ok_body())
        client(opener).complete(SPEC, [{"role": "user", "content": "hi"}],
                                tools=[{"type": "function"}], cache=False)
        body = json.loads(opener.requests[0].data.decode("utf-8"))
        self.assertEqual(body["model"], "vendor/model-x")
        self.assertEqual(body["provider"], {"order": ["vendor"], "allow_fallbacks": False})
        self.assertEqual(body["reasoning"], {"exclude": True})
        self.assertEqual(body["usage"], {"include": True})
        self.assertEqual(body["temperature"], 0.0)
        self.assertEqual(body["tool_choice"], "auto")
        self.assertEqual(opener.requests[0].get_header("Authorization"), "Bearer sk-test")

    def test_a_turn_is_normalised_with_tool_calls_and_real_cost(self):
        calls = [{"id": "x1", "type": "function",
                  "function": {"name": "Bash", "arguments": "{\"command\": \"ls\"}"}}]
        out = client(FakeOpener(ok_body(content=None, calls=calls))).complete(
            SPEC, [], cache=False)
        self.assertEqual(out["content"], "")
        self.assertEqual(out["tool_calls"], [{"id": "x1", "name": "Bash",
                                              "arguments": "{\"command\": \"ls\"}"}])
        self.assertAlmostEqual(out["usage"]["cost"], 0.0123)
        self.assertEqual(out["served_by"], "Vendor")

    def test_missing_cost_falls_back_to_the_roster_price(self):
        body = ok_body()
        del body["usage"]["cost"]
        out = client(FakeOpener(body)).complete(SPEC, [], cache=False)
        self.assertAlmostEqual(out["usage"]["cost"], (1000 * 1.0 + 100 * 2.0) / 1e6)

    def test_retries_429_and_5xx_then_succeeds(self):
        opener = FakeOpener(429, 503, ok_body())
        out = client(opener).complete(SPEC, [], cache=False)
        self.assertEqual(out["content"], "hello")
        self.assertEqual(len(opener.requests), 3)

    def test_a_client_error_is_not_retried(self):
        opener = FakeOpener(400, ok_body())
        with self.assertRaises(ProviderError):
            client(opener).complete(SPEC, [], cache=False)
        self.assertEqual(len(opener.requests), 1)

    def test_an_error_body_with_status_200_is_an_error(self):
        opener = FakeOpener({"error": {"code": 402, "message": "insufficient credits"}})
        with self.assertRaisesRegex(ProviderError, "402"):
            client(opener).complete(SPEC, [], cache=False)

    def test_gives_up_after_the_retry_budget(self):
        opener = FakeOpener(500, 500, 500, 500)
        with self.assertRaisesRegex(ProviderError, "gave up after 4"):
            client(opener).complete(SPEC, [], cache=False)

    def test_no_key_is_an_error_not_an_unauthenticated_call(self):
        saved = openrouter.os.environ.pop(openrouter.KEY_ENV, None)
        try:
            with self.assertRaises(ProviderError):
                OpenRouter(Budget(1.0))
        finally:
            if saved is not None:
                openrouter.os.environ[openrouter.KEY_ENV] = saved

    def test_the_cache_answers_a_repeat_for_free_and_keys_on_the_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            opener = FakeOpener(ok_body("first"), ok_body("second"))
            budget = Budget(10.0)
            paid = client(opener, budget, cache_dir=tmp)
            messages = [{"role": "user", "content": "same"}]
            first = paid.complete(SPEC, messages)
            again = paid.complete(SPEC, messages)
            self.assertEqual(again["content"], "first")
            self.assertTrue(again["cached"])
            self.assertEqual(again["usage"]["cost"], 0.0)
            self.assertFalse(first["cached"])
            changed = paid.complete(SPEC, [{"role": "user", "content": "different"}])
            self.assertEqual(changed["content"], "second")
            self.assertEqual(len(opener.requests), 2)
            self.assertAlmostEqual(budget.spent, 2 * 0.0123)

    def test_the_budget_stops_the_call_before_it_is_sent(self):
        opener = FakeOpener(ok_body(cost=1.5), ok_body())
        paid = client(opener, Budget(1.0))
        paid.complete(SPEC, [], cache=False)
        with self.assertRaises(BudgetExceeded):
            paid.complete(SPEC, [], cache=False)
        self.assertEqual(len(opener.requests), 1)

    def test_a_scope_cap_stops_one_model_and_not_another(self):
        budget = Budget(10.0, scope_cap_usd=1.0)
        budget.charge(1.0, scope="a")
        with self.assertRaises(BudgetExceeded):
            budget.check("a")
        budget.check("b")


class TestAssertionKinds(unittest.TestCase):
    """E-02 — every assertion kind passes the right turn and fails the wrong one."""

    def check(self, spec, tr, ctx=None):
        grade.validate_assertion(spec)
        return grade.KINDS[spec["kind"]](spec, tr, ctx or {})

    def test_skill_choice_needs_exactly_the_expected_name(self):
        spec = {"kind": "skill_choice", "expect": "dogen-plan"}
        self.assertTrue(self.check(spec, trace(turn("dogen-plan")))["pass"])
        self.assertTrue(self.check(spec, trace(turn("`dogen-plan`.")))["pass"])
        both = self.check(spec, trace(turn("dogen-plan, then dogen-write")))
        self.assertFalse(both["pass"])
        self.assertIn("dogen-write", both["feedback"])
        self.assertFalse(self.check(spec, trace(turn("the planning skill")))["pass"])
        none = {"kind": "skill_choice", "expect": "none"}
        self.assertTrue(self.check(none, trace(turn("none")))["pass"])
        self.assertFalse(self.check(none, trace(turn("dogen-review")))["pass"])

    def test_tool_call_first_and_any(self):
        tr = trace(turn(calls=[bash("dogen version --json"), bash("dogen show u --json")]))
        first = {"kind": "tool_call", "tool": "Bash", "args_re": r"^dogen version --json$"}
        self.assertTrue(self.check(first, tr)["pass"])
        wrong_first = {"kind": "tool_call", "tool": "Bash", "args_re": r"^dogen show"}
        self.assertFalse(self.check(wrong_first, tr)["pass"])
        anywhere = dict(wrong_first, which="any")
        self.assertTrue(self.check(anywhere, tr)["pass"])
        self.assertFalse(self.check(first, trace(turn("no tools")))["pass"])

    def test_no_tool_call_with_and_without_a_filter(self):
        tr = trace(turn(calls=[bash("dogen draft u")]))
        self.assertFalse(self.check({"kind": "no_tool_call"}, tr)["pass"])
        self.assertTrue(self.check({"kind": "no_tool_call"}, trace(turn("stop")))["pass"])
        self.assertTrue(self.check({"kind": "no_tool_call", "args_re": "git commit"},
                                   tr)["pass"])

    def test_text_re_and_its_negation(self):
        tr = trace(turn("The contract is 2; I have to stop here."))
        self.assertTrue(self.check({"kind": "text_re", "re": r"(?i)stop"}, tr)["pass"])
        self.assertFalse(self.check({"kind": "not_text_re", "re": r"(?i)stop"}, tr)["pass"])

    def test_not_prescribed_tells_a_warning_from_an_instruction(self):
        spec = {"kind": "not_prescribed", "re": r"git commit"}
        warned = trace(turn("Do not run `git commit` yourself; the tool owns commits."))
        self.assertTrue(self.check(spec, warned)["pass"])
        never = trace(turn("dogen makes the commit, so never `git commit` by hand."))
        self.assertTrue(self.check(spec, never)["pass"])
        told = trace(turn("Next, run `git commit -am wip` to save your work."))
        self.assertFalse(self.check(spec, told)["pass"])
        ran = trace(turn(calls=[bash("git add -A && git commit -m x")]))
        self.assertFalse(self.check(spec, ran)["pass"])

    def test_judge_reads_a_verdict_and_scores_it(self):
        verdict = '{"reason": "one question", "pass": true, "score": 4}'
        ctx = {"judge": (StubProvider(lambda s, m, t: "Sure. " + verdict), SPEC)}
        out = self.check({"kind": "judge", "rubric": "asks one question"},
                         trace(turn("Who reads this page?")), ctx)
        self.assertTrue(out["pass"])
        self.assertAlmostEqual(out["score"], 0.8)
        judge_stub = ctx["judge"][0]
        self.assertIn("Who reads this page?", judge_stub.calls[0]["messages"][0]["content"])

    def test_a_judge_that_cannot_answer_is_an_error_not_a_failure(self):
        for reply in ("no json here", '{"pass": "yes", "score": 3}',
                      '{"pass": true, "score": 9}'):
            ctx = {"judge": (StubProvider(lambda s, m, t, r=reply: r), SPEC)}
            with self.assertRaises(grade.GradeError):
                self.check({"kind": "judge", "rubric": "x"}, trace(turn("a")), ctx)

        def broken(spec, messages, tools):
            raise ProviderError("HTTP 402")

        ctx = {"judge": (StubProvider(broken), SPEC)}
        with self.assertRaisesRegex(grade.GradeError, "judge API error"):
            self.check({"kind": "judge", "rubric": "x"}, trace(turn("a")), ctx)

    def test_a_malformed_assertion_is_rejected_before_any_call(self):
        for bad in ({"kind": "nope"}, {"kind": "text_re"},
                    {"kind": "tool_call", "args_re": "("},
                    {"kind": "skill_choice", "expect": "dogen-publish"}):
            with self.assertRaises((ValueError, re.error)):
                grade.validate_assertion(bad)

    def test_run_level_defects_are_errors(self):
        self.assertIsNotNone(grade.turn_error(turn("")))
        self.assertIsNone(grade.turn_error(turn("", calls=[bash("ls")])))
        loop = "the same sentence over and over. " * 400
        self.assertIn("degenerate", grade.turn_error(turn(loop)))
        varied = " ".join("sentence number %d says something new." % i for i in range(400))
        self.assertIsNone(grade.turn_error(turn(varied)))

    def test_grade_aggregates_and_names_every_failure(self):
        out = grade.grade(
            [{"kind": "text_re", "re": "yes"}, {"kind": "text_re", "re": "no"},
             {"kind": "text_re", "re": "maybe"}],
            trace(turn("yes")),
        )
        self.assertFalse(out["passed"])
        self.assertAlmostEqual(out["score"], 1 / 3.0)
        self.assertIn("'no'", out["feedback"])
        self.assertIn("'maybe'", out["feedback"])


class TestSkillsReachTheModelNeutrally(unittest.TestCase):
    """E-03 — the catalog and invocation shape, and no harness named anywhere."""

    HARNESS_RE = re.compile(
        r"(?i)claude[ -]?code|\bcodex\b|copilot|cursor|opencode|windsurf|\baider\b|"
        r"gemini[ -]cli|\.claude/|\.github/skills"
    )

    def setUp(self):
        self.skills = skillmod.load_skills()

    def test_the_catalog_lists_all_five_with_their_installed_location(self):
        self.assertEqual(sorted(self.skills), sorted(grade.SKILL_NAMES))
        text = skillmod.catalog(self.skills)
        for name, skill in self.skills.items():
            self.assertIn("<name>%s</name>" % name, text)
            self.assertIn(skill.description, text)
            self.assertIn(".agents/skills/%s/SKILL.md" % name, text)

    def test_invocation_appends_the_body_and_nothing_else_does(self):
        name, expanded = skillmod.expand_invocation("/dogen-review my-unit", self.skills)
        self.assertEqual(name, "dogen-review")
        self.assertTrue(expanded.startswith("/dogen-review my-unit"))
        self.assertIn(self.skills["dogen-review"].body.strip()[:200], expanded)
        self.assertEqual(skillmod.expand_invocation("please review", self.skills),
                         (None, "please review"))
        self.assertEqual(skillmod.expand_invocation("/dogen-nope x", self.skills)[0], None)

    def test_no_prompt_and_no_kit_file_names_a_harness(self):
        surfaces = {
            "selection prompt": skillmod.selection_system_prompt(self.skills),
            "agent prompt": skillmod.agent_system_prompt(self.skills, "/tmp/repo"),
            "judge prompt": grade.JUDGE_INSTRUCTIONS,
        }
        for path in sorted(EVALS.rglob("*")):
            if path.suffix in (".py", ".json", ".md", ".sh") and "results" not in path.parts \
                    and ".cache" not in path.parts:
                surfaces[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")
        for where, text in surfaces.items():
            with self.subTest(surface=where):
                self.assertIsNone(self.HARNESS_RE.search(text))

    def test_the_bundle_digest_is_stable(self):
        self.assertEqual(skillmod.bundle_sha256(), skillmod.bundle_sha256())
        self.assertRegex(skillmod.bundle_sha256(), r"^[0-9a-f]{64}$")


class TestCaseFilesAgainstTheirOracles(unittest.TestCase):
    """E-04 — every case loads, and its own known-good answer passes it."""

    def ctx(self):
        return {"skills": skillmod.load_skills(), "cache": False,
                "judge": (StubProvider(run.stub_judge), SPEC)}

    def test_every_lane_loads_a_non_empty_case_set(self):
        for name, lane in lanes.LANES.items():
            with self.subTest(lane=name):
                self.assertTrue(lane["load"]())

    def test_every_oracle_passes_its_own_case(self):
        ctx = self.ctx()
        for name, lane in lanes.LANES.items():
            for case in lane["load"]():
                with self.subTest(lane=name, case=case["id"]):
                    stub = StubProvider(lambda s, m, t, c=case: lane["oracle"](c))
                    tr = lane["run"](case, SPEC, stub, ctx)
                    out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
                    self.assertTrue(out["passed"], out["feedback"])

    def test_every_selection_case_fails_on_any_other_skill(self):
        ctx = self.ctx()
        choices = grade.SKILL_NAMES + ("none",)
        for case in lanes.load_a():
            for foil in choices:
                if foil == case["expect"]:
                    continue
                with self.subTest(case=case["id"], foil=foil):
                    tr = lanes.run_a(case, SPEC, StubProvider(lambda s, m, t, f=foil: f), ctx)
                    self.assertFalse(grade.grade(case["assert"], tr)["passed"])

    def test_selection_covers_every_skill_and_none(self):
        expected = set(case["expect"] for case in lanes.load_a())
        self.assertEqual(expected, set(grade.SKILL_NAMES) | {"none"})


class TestRosterAndRunner(unittest.TestCase):
    """E-05 — the roster's pins and roles, and where a run's results may land."""

    def test_every_model_is_pinned_to_one_backend(self):
        roster, by_id = run.load_roster()
        for model in roster["models"]:
            with self.subTest(model=model["id"]):
                self.assertFalse(model["provider"]["allow_fallbacks"])
                self.assertEqual(len(model["provider"]["order"]), 1)
                self.assertEqual(len(model["price_per_mtok"]), 2)
        candidates = set(m["id"] for m in roster["models"] if m["role"] == "candidate")
        self.assertIn(roster["gate"], candidates)
        self.assertNotIn(roster["judge"], candidates)
        self.assertNotIn(roster["author"], candidates)
        self.assertLess(roster["caps"]["per_model_usd"], roster["caps"]["sweep_usd"])

    def summary(self, **meta):
        base = {"date": "2026-01-02", "lane": "A", "model": "vendor/model-x",
                "dry_run": False, "errors": 0, "budget_stop": None, "partial": False}
        base.update(meta)
        return {"meta": base, "cases": []}

    def test_only_a_clean_complete_paid_run_is_a_baseline_and_none_is_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = run.RESULTS, run.RAW
            run.RESULTS, run.RAW = Path(tmp), Path(tmp) / "raw"
            try:
                clean = run.destination(self.summary(), "120000")
                self.assertEqual(clean, Path(tmp) / "2026-01-02-A-vendor__model-x.json")
                clean.write_text("{}")
                self.assertEqual(run.destination(self.summary(), "120000").name,
                                 "2026-01-02-A-vendor__model-x-2.json")
                for meta, tag in (({"dry_run": True}, "dry"), ({"errors": 1}, "errored"),
                                  ({"budget_stop": "cap"}, "errored"),
                                  ({"partial": True}, "partial")):
                    with self.subTest(tag=tag):
                        path = run.destination(self.summary(**meta), "120000")
                        self.assertEqual(path.parent, Path(tmp) / "raw")
                        self.assertTrue(path.name.endswith("-%s.json" % tag))
            finally:
                run.RESULTS, run.RAW = saved

    def test_a_dry_run_of_everything_is_green_and_writes_only_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = run.RESULTS, run.RAW
            run.RESULTS, run.RAW = Path(tmp), Path(tmp) / "raw"
            stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = run.main(["all", "--roster", "--dry-run", "--jobs", "2"])
            finally:
                sys.stdout = stdout
                run.RESULTS, run.RAW = saved
            self.assertEqual(code, 0)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["raw"])
            written = sorted(p.name for p in (Path(tmp) / "raw").iterdir())
            self.assertTrue(written)
            self.assertTrue(all("-dry." in name for name in written))

    def test_an_unknown_model_is_refused_before_anything_runs(self):
        stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            self.assertEqual(run.main(["A", "--model", "vendor/not-listed", "--dry-run"]), 2)
        finally:
            sys.stderr = stderr


if __name__ == "__main__":
    unittest.main()
