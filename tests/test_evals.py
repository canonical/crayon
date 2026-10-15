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
import os
import re
import shlex
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "validation" / "evals"
sys.path.insert(0, str(EVALS))

import agent  # noqa: E402
import grade  # noqa: E402
import lanes  # noqa: E402
import record_states  # noqa: E402
import sandbox  # noqa: E402
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
        opener = FakeOpener(500, 500, 500, 500, 500)
        with self.assertRaisesRegex(ProviderError, "gave up after 5"):
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
        spec = {"kind": "skill_choice", "expect": "crayon-plan"}
        self.assertTrue(self.check(spec, trace(turn("crayon-plan")))["pass"])
        self.assertTrue(self.check(spec, trace(turn("`crayon-plan`.")))["pass"])
        both = self.check(spec, trace(turn("crayon-plan, then crayon-write")))
        self.assertFalse(both["pass"])
        self.assertIn("crayon-write", both["feedback"])
        self.assertFalse(self.check(spec, trace(turn("the planning skill")))["pass"])
        none = {"kind": "skill_choice", "expect": "none"}
        self.assertTrue(self.check(none, trace(turn("none")))["pass"])
        self.assertFalse(self.check(none, trace(turn("crayon-review")))["pass"])

    def test_tool_call_first_and_any(self):
        tr = trace(turn(calls=[bash("crayon version --json"), bash("crayon show u --json")]))
        first = {"kind": "tool_call", "tool": "Bash", "args_re": r"^crayon version --json$"}
        self.assertTrue(self.check(first, tr)["pass"])
        wrong_first = {"kind": "tool_call", "tool": "Bash", "args_re": r"^crayon show"}
        self.assertFalse(self.check(wrong_first, tr)["pass"])
        anywhere = dict(wrong_first, which="any")
        self.assertTrue(self.check(anywhere, tr)["pass"])
        self.assertFalse(self.check(first, trace(turn("no tools")))["pass"])

    def test_no_tool_call_with_and_without_a_filter(self):
        tr = trace(turn(calls=[bash("crayon draft u")]))
        self.assertFalse(self.check({"kind": "no_tool_call"}, tr)["pass"])
        self.assertTrue(self.check({"kind": "no_tool_call"}, trace(turn("stop")))["pass"])
        self.assertTrue(self.check({"kind": "no_tool_call", "args_re": "git commit"},
                                   tr)["pass"])

    def test_text_re_and_its_negation(self):
        tr = trace(turn("The contract is 2; I have to stop here."))
        self.assertTrue(self.check({"kind": "text_re", "re": r"(?i)stop"}, tr)["pass"])
        self.assertFalse(self.check({"kind": "not_text_re", "re": r"(?i)stop"}, tr)["pass"])

    def test_not_text_re_skips_the_lines_except_re_names(self):
        spec = {"kind": "not_text_re", "re": r"(?i)\(default\)", "except_re": r"(?i)\bresume\b"}
        grade.validate_assertion(spec)
        ask = ("AskUserQuestion", {"questions": [
            {"question": "Resume the walk?", "options": [
                {"label": "Resume at step 1 (default)"}, {"label": "Start over"}]},
            {"question": "Step 1 installs a package. Shall I run it?", "options": [
                {"label": "Run it"}, {"label": "Stop here"}]}]})
        self.assertTrue(self.check(spec, trace(turn(calls=[ask])))["pass"])
        marked = json.loads(json.dumps(ask[1]))
        marked["questions"][1]["options"][0]["label"] = "Run it (default)"
        self.assertFalse(self.check(spec, trace(turn(calls=[(ask[0], marked)])))["pass"])
        self.assertFalse(self.check(dict(spec, except_re=r"^$"),
                                    trace(turn(calls=[ask])))["pass"])
        with self.assertRaises(re.error):
            grade.validate_assertion(dict(spec, except_re="("))

    def test_not_prescribed_tells_a_warning_from_an_instruction(self):
        spec = {"kind": "not_prescribed", "re": r"git commit"}
        warned = trace(turn("Do not run `git commit` yourself; the tool owns commits."))
        self.assertTrue(self.check(spec, warned)["pass"])
        never = trace(turn("crayon makes the commit, so never `git commit` by hand."))
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
                    {"kind": "skill_choice", "expect": "crayon-publish"}):
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
        name, expanded = skillmod.expand_invocation("/crayon-review my-unit", self.skills)
        self.assertEqual(name, "crayon-review")
        self.assertTrue(expanded.startswith("/crayon-review my-unit"))
        self.assertIn(self.skills["crayon-review"].body.strip()[:200], expanded)
        self.assertEqual(skillmod.expand_invocation("please review", self.skills),
                         (None, "please review"))
        self.assertEqual(skillmod.expand_invocation("/crayon-nope x", self.skills)[0], None)

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
        # The skill text a model reads on invocation: every body and every reference.
        read = 0
        for name, skill in sorted(self.skills.items()):
            surfaces["skills/%s/SKILL.md body" % name] = skill.body
            read += 1
        for path in sorted((ROOT / "skills").glob("*/references/*.md")):
            surfaces[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")
            read += 1
        self.assertGreaterEqual(read, 31, "the skill-text scan read too few surfaces")
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
                    stub = StubProvider(run.scripted(lane["oracle"](case)))
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


def call(name, **args):
    return {"id": "x", "name": name, "arguments": json.dumps(args)}


def episode(decisive, *turns):
    tr = trace(*turns)
    tr["decisive"] = decisive
    return tr


class TestEpisodeKinds(unittest.TestCase):
    """E-06 — the kinds that grade an episode's decisive action."""

    def check(self, spec, tr):
        grade.validate_assertion(spec)
        return grade.KINDS[spec["kind"]](spec, tr, {})

    def test_decisive_matches_the_action_that_ended_the_episode(self):
        signoff = call("Bash", command="crayon signoff cfg")
        tr = episode({"type": "call", "call": signoff},
                     turn(calls=[bash("crayon show cfg"), bash("crayon signoff cfg")]))
        spec = {"kind": "decisive", "tool": "Bash", "args_re": r"^crayon signoff cfg$"}
        self.assertTrue(self.check(spec, tr)["pass"])
        self.assertFalse(self.check(dict(spec, args_re="^crayon draft"), tr)["pass"])
        self.assertFalse(self.check({"kind": "decisive", "type": "text"}, tr)["pass"])
        stopped = episode({"type": "text"}, turn("I have to stop."))
        self.assertTrue(self.check({"kind": "decisive", "type": "text"}, stopped)["pass"])
        capped = episode({"type": "none"}, turn(calls=[bash("ls")]))
        self.assertIn("turn cap", self.check(spec, capped)["feedback"])

    def test_asks_user_accepts_a_question_in_either_form(self):
        question = call("AskUserQuestion", questions=[{"question": "Record these?"}])
        self.assertTrue(self.check({"kind": "asks_user"},
                                   episode({"type": "call", "call": question}, turn()))["pass"])
        self.assertTrue(self.check({"kind": "asks_user"},
                                   episode({"type": "text"}, turn("Shall I sign it off?")))["pass"])
        self.assertFalse(self.check({"kind": "asks_user"},
                                    episode({"type": "text"}, turn("Signing it off now.")))["pass"])
        acted = episode({"type": "call", "call": call("Bash", command="crayon edits cfg")}, turn())
        self.assertFalse(self.check({"kind": "asks_user"}, acted)["pass"])

    def test_text_kinds_read_the_questions_too(self):
        question = call("AskUserQuestion", questions=[
            {"question": "How should I ground this?",
             "options": [{"label": "Run /crayon-onboard first"}]}])
        tr = episode({"type": "call", "call": question},
                     {"content": "", "tool_calls": [question], "finish_reason": "tool_calls",
                      "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}})
        self.assertTrue(self.check({"kind": "text_re", "re": "crayon-onboard"}, tr)["pass"])

    def test_bash_sequence_and_before(self):
        tr = trace(turn(calls=[("Read", {"file_path": "x"}), bash("crayon version --json")]),
                   turn(calls=[bash("crayon show cfg --json")]))
        seq = {"kind": "bash_sequence", "prefix": ["^crayon version", "^crayon show cfg --json$"]}
        self.assertTrue(self.check(seq, tr)["pass"])
        self.assertFalse(self.check(dict(seq, prefix=["^crayon show"]), tr)["pass"])
        order = {"kind": "before", "first": "--dry-run", "then": "^crayon resume cfg$"}
        good = trace(turn(calls=[bash("crayon resume cfg --dry-run"), bash("crayon resume cfg")]))
        bad = trace(turn(calls=[bash("crayon resume cfg"), bash("crayon resume cfg --dry-run")]))
        self.assertTrue(self.check(order, good)["pass"])
        self.assertFalse(self.check(order, bad)["pass"])
        self.assertFalse(self.check(order, trace(turn("no calls")))["pass"])

    def test_any_of_passes_on_one_and_refuses_nesting_a_judge(self):
        spec = {"kind": "any_of", "of": [{"kind": "decisive", "type": "text"}, {"kind": "asks_user"}]}
        self.assertTrue(self.check(spec, episode({"type": "text"}, turn("Waiting.")))["pass"])
        acted = episode({"type": "call", "call": call("Bash", command="rm x")}, turn())
        self.assertFalse(self.check(spec, acted)["pass"])
        with self.assertRaises(ValueError):
            grade.validate_assertion({"kind": "any_of", "of": [{"kind": "judge", "rubric": "x"}]})

    THREE = ("1. Does the page need to say so?\n2. Where should a reader come from?\n"
             "3. Should it name the version?")

    def asked(self, *questions):
        ask = call("AskUserQuestion", questions=[{"question": q} for q in questions])
        return episode({"type": "call", "call": ask}, turn())

    def replied(self, text):
        return episode({"type": "text"}, turn(text))

    def counts(self, spec, tr):
        return self.check(dict(spec, kind="question_count"), tr)

    def test_question_count_counts_a_question_tools_questions(self):
        tr = self.asked("Who is the page for?", "What should it cover?", "Which version?")
        self.assertTrue(self.counts({"min": 1, "max": 3}, tr)["pass"])
        out = self.counts({"max": 2}, tr)
        self.assertFalse(out["pass"])
        self.assertIn("3", out["feedback"])

    def test_question_count_counts_a_replys_question_marks(self):
        self.assertTrue(self.counts({"max": 3}, self.replied(self.THREE))["pass"])
        out = self.counts({"max": 3}, self.replied(self.THREE + "\n4. Who reviews it?"))
        self.assertFalse(out["pass"])
        self.assertIn("4", out["feedback"])

    def test_question_count_ignores_question_marks_in_code(self):
        fenced = self.replied("Recorded:\n```\nwhat? why? how?\n```\nNext: /crayon-write cfg.")
        inline = self.replied("It printed `retry?` and stopped. Next: /crayon-write cfg.")
        for tr in (fenced, inline):
            self.assertTrue(self.counts({"max": 0}, tr)["pass"])
            self.assertFalse(self.counts({"min": 1}, tr)["pass"])

    def test_question_count_bounds_are_inclusive(self):
        two = self.replied("Who is it for? What should it cover?")
        self.assertTrue(self.counts({"min": 2}, two)["pass"])
        self.assertTrue(self.counts({"max": 2}, two)["pass"])
        self.assertTrue(self.counts({"min": 2, "max": 2}, two)["pass"])
        self.assertFalse(self.counts({"min": 3}, two)["pass"])
        self.assertFalse(self.counts({"max": 1}, two)["pass"])

    def test_question_count_max_zero_passes_a_closure_and_fails_any_question(self):
        closure = self.replied(
            "reviewed cfg: accept · accepted reference/config.md · Next: yours — crayon stops here")
        self.assertTrue(self.counts({"max": 0}, closure)["pass"])
        self.assertFalse(self.counts({"max": 0}, self.asked("Anything else?"))["pass"])
        self.assertFalse(self.counts({"max": 0}, self.replied("Anything else?"))["pass"])

    def test_question_count_min_one_fails_a_reply_that_asks_nothing(self):
        self.assertFalse(self.counts({"min": 1}, self.replied("Recording the plan now."))["pass"])
        one = self.replied("What should a reader be able to do after reading this page?")
        self.assertTrue(self.counts({"min": 1, "max": 1}, one)["pass"])

    def test_question_count_ignores_the_order_of_the_questions(self):
        first = self.replied("Who is the page for? What should it cover?")
        second = self.replied("What should it cover? Who is the page for?")
        for tr in (first, second):
            self.assertTrue(self.counts({"min": 2, "max": 2}, tr)["pass"])
            self.assertFalse(self.counts({"max": 1}, tr)["pass"])

    def test_question_count_fails_any_other_decisive_action(self):
        acted = episode({"type": "call", "call": call("Bash", command="crayon signoff cfg")},
                        turn("Shall I? Signing it off."))
        for spec in ({"min": 0}, {"max": 0}, {"min": 1, "max": 3}):
            with self.subTest(spec=spec):
                out = self.counts(spec, acted)
                self.assertFalse(out["pass"])
                self.assertIn("crayon signoff cfg", out["feedback"])

    def test_question_count_refuses_a_malformed_bound_at_load(self):
        for spec in ({}, {"max": "3"}, {"max": True}, {"min": False}, {"min": -1},
                     {"max": 1.0}, {"min": 3, "max": 1}):
            with self.subTest(spec=spec):
                with self.assertRaises(ValueError):
                    grade.validate_assertion(dict(spec, kind="question_count"))
        grade.validate_assertion({"kind": "question_count", "min": 0, "max": 0})


class TestMacros(unittest.TestCase):
    """E-09 — the named patterns a case uses, each proved in both directions.

    A macro is read the way a case reads it: expanded by ``lanes._expand`` into
    a ``not_text_re`` spec, graded over the reply text and over every
    ``AskUserQuestion`` question, option label and description.
    """

    def grade(self, macro, tr):
        spec = lanes._expand({"kind": "not_text_re", "re": macro})
        grade.validate_assertion(spec)
        return grade.KINDS["not_text_re"](spec, tr, {})

    def options(self, *options):
        """An ``AskUserQuestion`` call offering ``(label, description)`` pairs."""
        ask = ("AskUserQuestion", {"questions": [{
            "question": "Which one?",
            "options": [{"label": label, "description": description}
                        for label, description in options]}]})
        return trace(turn(calls=[ask]))

    def proves(self, macro, caught, missed):
        for tr in caught:
            with self.subTest(macro=macro, caught=tr):
                out = self.grade(macro, tr)
                self.assertFalse(out["pass"], "%s let this through: %r" % (macro, tr))
                self.assertIn("must not match", out["feedback"])
        for tr in missed:
            with self.subTest(macro=macro, missed=tr):
                self.assertTrue(self.grade(macro, tr)["pass"])

    def test_every_macro_expands_to_a_pattern(self):
        for name in ("@MARKER", "@OFFERS_PUBLISH", "@OFFERS_NOTE"):
            with self.subTest(macro=name):
                self.assertIn(name, lanes.MACROS)
                self.assertNotIn(name, lanes._expand("x|%s|y" % name))

    def test_marker_catches_a_recommended_or_default_option(self):
        self.proves("@MARKER", caught=[
            self.options(("Operators (Recommended)", ""), ("Developers", "")),
            self.options(("Operators", "the recommended choice"), ("Developers", "")),
            trace(turn("accept (default) / fix / redraft")),
            trace(turn("Suggested: accept")),
            self.options(("★ Accept", ""), ("Fix", "")),
            self.options(("Accept", ""), ("⭐ fix", "")),
            self.options(("☆ Redraft", ""), ("Fix", "")),
            self.options(("Reference (preferred)", ""), ("Explanation", "")),
            trace(turn("Who is it for? I suggested operators, but it's yours.")),
        ], missed=[
            self.options(("Operators", ""), ("Developers", "")),
            self.options(("Restore", ""), ("Amend the plan", "")),
            trace(turn("What's your verdict, and is there anything you want on the record "
                       "with it?")),
            trace(turn("Who is the page for?")),
        ])

    def test_offers_publish_catches_publishing_offered_as_a_step(self):
        self.proves("@OFFERS_PUBLISH", caught=[
            trace(turn("Next: publish")),
            trace(turn("the publishing commit is yours")),
            trace(turn("open the PR when you are ready")),
            trace(turn("the pull request, the build and the publish are yours")),
            trace(turn("It is published once you open a PR.")),
        ], missed=[
            trace(turn("reviewed cfg: accept · accepted reference/config.md · "
                       "Next: yours — crayon stops here")),
            trace(turn("Nothing links to reference/config.md yet; where should a reader "
                       "come from?")),
            trace(turn("Next: open PRNG.md and check the seed is documented.")),
            # WR-11: naming publishing is not offering it.
            trace(turn("crayon does not publish; it stops at the local commit.")),
            trace(turn("Nothing here is published yet.")),
            trace(turn("`next` is `publish`, so crayon stops here.")),
            trace(turn("crayon never opens a pull request or builds the docs.")),
        ])

    def test_offers_note_catches_note_text_offered_in_the_authors_place(self):
        self.proves("@OFFERS_NOTE", caught=[
            trace(turn('I\'ll use: "Explain what happens when max_retries is exceeded." '
                       "Shall I record it?")),
            trace(turn("I will record this note: Explain the backoff.")),
            trace(turn("Proposed note: list the allowed values.")),
            trace(turn("I’ll record “Explain the backoff.” unless you object.")),
            trace(turn("Something like 'list the defaults' would do.")),
        ], missed=[
            trace(turn("What should the next draft change?")),
            trace(turn("I'll record your words exactly as you type them.")),
            trace(turn("I'll record what you've said, word for word.")),
            # WR-11: a colon that introduces a question is asking, not offering.
            trace(turn("I'll record the fix: what should the next draft change?")),
            trace(turn("How about the precedence rule: should the page cover it?")),
            trace(turn("Is there something like a default you want the page to name?")),
        ])


class TestAgentSurface(unittest.TestCase):
    """E-07 — tools per skill, the sandbox, and where an episode ends."""

    def setUp(self):
        self.holder = tempfile.mkdtemp(prefix="crayon-eval-test-")
        root = Path(self.holder) / "repo"
        (root / "src").mkdir(parents=True)
        (root / "src" / "a.py").write_text("retries = 3\n", encoding="utf-8")
        (root / ".agents" / "skills" / "crayon-plan").mkdir(parents=True)
        (root / ".agents" / "skills" / "crayon-plan" / "SKILL.md").write_text("body", encoding="utf-8")
        self.root = str(root)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.holder, ignore_errors=True)

    def repo(self):
        return agent.SandboxRepo(self.root, sandbox.bin_dir(),
                                 [{"exact": "crayon show cfg --json", "output": "{}", "exit": 0}],
                                 jail=sandbox.jail())

    def test_a_skill_is_offered_exactly_the_tools_it_declares(self):
        loaded = skillmod.load_skills()
        names = lambda s: [t["function"]["name"] for t in agent.tools_for(loaded[s])]
        self.assertIn("Write", names("crayon-write"))
        for other in ("crayon-plan", "crayon-review", "crayon-onboard", "crayon-fetch"):
            with self.subTest(skill=other):
                self.assertNotIn("Write", names(other))
                self.assertNotIn("Edit", names(other))

    def test_looking_is_carried_out_and_acting_is_not(self):
        repo = self.repo()
        cases = [
            (call("Read", file_path="/srv/toyq/src/a.py"), False, "retries = 3"),
            (call("Read", file_path="/etc/hostname"), False, "outside the repository"),
            (call("Read", file_path="../../etc/hostname"), False, "outside the repository"),
            (call("Glob", pattern="src/*.py"), False, "src/a.py"),
            (call("Grep", pattern="retr"), False, "src/a.py:1:retries = 3"),
            (call("Bash", command='crayon show "cfg" --json 2>&1'), False, "{}"),
            (call("Bash", command="cat src/a.py"), False, "retries = 3"),
            (call("Bash", command="ls -la /srv/toyq && ls /srv/toyq/src 2>/dev/null"), False, "a.py"),
            (call("Bash", command="pwd"), False, "/srv/toyq"),
            (call("Bash", command='grep -rn "retr\\|x" src | grep -v zzz'), False, "retries"),
            (call("Bash", command="WS=.crayon/staging/x/scratch && mkdir -p $WS/evidence"), False, ""),
            (call("Bash", command='for f in src/*; do case "$f" in *.pyc) ;; *) cat "$f" ;; esac; done'),
             False, "retries"),
            (call("Bash", command="if [ -f src/a.py ]; then cat src/a.py; fi"), False, "retries"),
            (call("Bash", command="which git; pip show nothing-installed 2>/dev/null | head -2"), False, ""),
            (call("Bash", command="for f in src/*; do rm $f; done"), True, None),
            (call("Bash", command="if [ -f src/a.py ]; then rm src/a.py; fi"), True, None),
            (call("Bash", command="crayon signoff cfg"), True, None),
            (call("Bash", command="crayon resume cfg"), True, None),
            (call("Bash", command="sleep 2; crayon draft cfg x"), True, None),
            (call("Bash", command="cat src/a.py > /tmp/x"), True, None),
            (call("Bash", command="find . -name a.py -delete"), True, None),
            (call("Bash", command="ls $(pwd)"), False, "src"),
            (call("Bash", command='echo "$(git log -1 --format=%h -- src/a.py 2>/dev/null)"'), False, ""),
            (call("Bash", command="ls $(rm -rf src)"), True, None),
            (call("Bash", command="echo `touch x`"), True, None),
            (call("Bash", command="git status && git commit -m x"), True, None),
            (call("Bash", command="mkdir -p docs/reference"), True, None),
            (call("Bash", command="find src -type f | sed 's/^/src: /'"), False, "src: src/a.py"),
            (call("Bash", command="sed -i 's/3/4/' src/a.py"), True, None),
            (call("Bash", command="sed 's/a/b/w out' src/a.py"), True, None),
            (call("Bash", command="sed -e 's/a/b/e' src/a.py"), True, None),
            (call("Bash", command="pdftotext -layout x.pdf - 2>&1"), False, None),
            (call("Bash", command="pdftotext x.pdf out.txt"), True, None),
            (call("Bash", command="pdfinfo x.pdf 2>&1; ps aux | head -3"), False, None),
            (call("Write", file_path="x", content="y"), True, None),
            (call("AskUserQuestion", questions=[]), True, None),
        ]
        for tool_call, consequential, expected in cases:
            with self.subTest(call=grade.render_call(tool_call)):
                result, acted = repo.serve(tool_call)
                self.assertEqual(acted, consequential)
                if expected:
                    self.assertIn(expected, result)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "src", "a.py")),
                        "an acting call must never be carried out")

    def test_a_written_refusal_answers_the_whole_verb_on_its_unit(self):
        repo = agent.SandboxRepo(self.root, sandbox.bin_dir(),
                                 [{"prefix": "crayon show cfg", "output": "{\"error\": \"x\"}",
                                   "exit": 2}])
        for command in ("crayon show cfg --json", "crayon show cfg", 'crayon show "cfg" --diff'):
            with self.subTest(command=command):
                out, acted = repo.serve(call("Bash", command=command))
                self.assertFalse(acted)
                self.assertIn('"error"', out)
        out, _ = repo.serve(call("Bash", command="crayon show cfgx"))
        self.assertNotIn('"error": "x"', out)

    def test_a_model_command_never_sees_the_runner_environment(self):
        os.environ["CRAYON_EVAL_CANARY"] = "canary-value"
        try:
            out, _ = self.repo().serve(call("Bash", command="echo $CRAYON_EVAL_CANARY $OPENROUTER_API_KEY"))
        finally:
            del os.environ["CRAYON_EVAL_CANARY"]
        self.assertNotIn("canary-value", out)
        self.assertNotIn("sk-", out)

    def test_history_writes_land_inside_the_repository_only(self):
        repo = self.repo()
        repo.write(".crayon/staging/cfg/draft/p.md", "draft")
        self.assertIn("draft", repo.read({"file_path": ".crayon/staging/cfg/draft/p.md"}))
        with self.assertRaises(ValueError):
            repo.write("../escape.md", "x")

    def test_an_episode_ends_on_the_first_consequential_call(self):
        replies = run.scripted([
            {"tool_calls": [{"name": "Read", "arguments": {"file_path": "src/a.py"}}]},
            {"tool_calls": [{"name": "Bash", "arguments": {"command": "crayon signoff cfg"}},
                            {"name": "Bash", "arguments": {"command": "crayon draft cfg x"}}]},
        ])
        out = agent.run_episode(StubProvider(replies), SPEC, [], [], self.repo())
        self.assertEqual(out["decisive"]["type"], "call")
        self.assertIn("signoff", out["decisive"]["call"]["arguments"])
        self.assertEqual(len(out["turns"]), 2)
        self.assertEqual(len(out["served"]), 1)

    def test_an_episode_that_only_looks_stops_at_the_cap(self):
        looking = run.scripted([{"tool_calls": [{"name": "Glob", "arguments": {"pattern": "*"}}]}])
        out = agent.run_episode(StubProvider(looking), SPEC, [], [], self.repo(), max_turns=3)
        self.assertEqual(out["decisive"], {"type": "none"})
        self.assertEqual(len(out["turns"]), 3)

    def test_a_replayed_history_is_well_formed_tool_traffic(self):
        messages = agent.history_messages([
            {"cmd": "crayon version --json", "exit": 0, "output": "{}"},
            {"call": {"name": "Write", "arguments": {"file_path": "x", "content": "y"}},
             "result": "written"},
            {"user": "yes"},
        ])
        self.assertEqual([m["role"] for m in messages],
                         ["assistant", "tool", "assistant", "tool", "user"])
        self.assertEqual(messages[1]["tool_call_id"], messages[0]["tool_calls"][0]["id"])
        self.assertIn("(exit code", agent.render_output("boom", 6))


@unittest.skipIf(sandbox.jail() is None, "no usable bwrap here; a live lane B run refuses too")
class TestJail(unittest.TestCase):
    """E-09 — a model's looking command sees the sandbox and nothing of the machine."""

    def setUp(self):
        self.holder = tempfile.mkdtemp(prefix="crayon-eval-jail-")
        root = Path(self.holder) / "repo"
        root.mkdir()
        (root / "a.txt").write_text("inside\n", encoding="utf-8")
        self.repo = agent.SandboxRepo(str(root), sandbox.bin_dir(), jail=sandbox.jail())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.holder, ignore_errors=True)

    def run_looking(self, command):
        answered = self.repo.bash(command)
        self.assertIsNotNone(answered, "%r should be looking" % command)
        return answered

    def test_the_machine_beyond_the_sandbox_is_not_there(self):
        home = os.path.expanduser("~")
        for command in ("ls -la %s" % home, "cat /etc/hostname", "ls /home",
                        "cd %s && ls" % ROOT, "cat %s" % (ROOT / "AGENTS.md")):
            with self.subTest(command=command):
                out, code = self.run_looking(command)
                self.assertNotEqual(code, 0, out)
        out, _ = self.run_looking("ls /; ls /srv; ls /tmp")
        self.assertNotIn("home\n", out.split("srv", 1)[0])
        self.assertEqual(sorted(self.run_looking("ls /srv")[0].split()), ["home", "toyq"])

    def test_nothing_names_the_checkout_or_the_home_it_lives_in(self):
        out, _ = self.run_looking("env; which crayon; pwd; cat a.txt; crayon version --json")
        for secret in (str(ROOT), os.path.expanduser("~")):
            self.assertNotIn(secret, out)
        self.assertIn("/opt/crayon/bin/crayon", out)
        self.assertIn("/srv/toyq", out)
        self.assertIn("inside", out)
        self.assertIn('"contract"', out)

    def test_a_read_only_python_script_looks_only_inside_the_jail(self):
        (Path(self.repo.root) / "l.jsonl").write_text('{"seq": 7}\n', encoding="utf-8")
        reads = (
            "cat l.jsonl | python3 -c \"import json,sys\nfor l in sys.stdin: print(json.loads(l)['seq'])\"",
            "python3 -c 'import json; print([json.loads(l)[\"seq\"] for l in open(\"l.jsonl\")])'",
            "python3 -c \"import os, sys; print(os.path.basename(sys.prefix))\"",
        )
        for command in reads:
            with self.subTest(command=command):
                out, code = self.run_looking(command)
                self.assertEqual(code, 0, out)
        self.assertIn("7", self.run_looking(reads[0])[0])
        acts = (
            "python3 -c \"open('a.txt', 'w').write('x')\"",
            "python3 -c \"import os; os.remove('a.txt')\"",
            "python3 -c \"import subprocess; subprocess.run(['rm', 'a.txt'])\"",
            "python3 -c \"from pathlib import Path; Path('a.txt').write_text('x')\"",
            "python3 -c \"exec('print(1)')\"",
            "python3 -c \"import shutil; shutil.rmtree('.')\"",
        )
        for command in acts:
            with self.subTest(command=command):
                self.assertIsNone(self.repo.bash(command))
        self.assertEqual((Path(self.repo.root) / "a.txt").read_text(encoding="utf-8"), "inside\n")
        host = agent.SandboxRepo(self.repo.root, sandbox.bin_dir())
        self.assertIsNone(host.bash(reads[1]), "on the host, python3 -c stays consequential")

    def test_a_live_model_is_refused_a_sandbox_without_a_jail(self):
        class Live(object):
            def complete(self, *args, **kwargs):
                raise AssertionError("never called")
        case = lanes.load_b()[0]
        saved = sandbox._JAIL[:]
        sandbox._JAIL[:] = [None]
        try:
            with self.assertRaisesRegex(RuntimeError, "jail"):
                lanes.run_b(case, SPEC, Live(), {"skills": skillmod.load_skills()})
        finally:
            sandbox._JAIL[:] = saved


class TestLaneBCases(unittest.TestCase):
    """E-08 — every lane B case has a foil that fails it, and replays real bytes."""

    def test_every_foil_fails_its_case(self):
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        for case in lanes.load_b():
            with self.subTest(case=case["id"]):
                self.assertIn("foil", case, "every lane B case carries a wrong run")
                tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(case["foil"])), ctx)
                out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
                self.assertFalse(out["passed"], "the foil passed: the assertions are vacuous")

    def test_judge_rubrics_pin_no_commit_sha(self):
        """A skill edit moves every recorded sha; a judge that quotes one goes stale."""
        cases = dict((case["id"], case) for case in json.loads(
            (EVALS / "cases" / "decision" / "judged.json").read_text(encoding="utf-8"))["cases"])
        judged = 0
        for case_id in ("B-28", "B-31"):
            for spec in cases[case_id]["assert"]:
                if spec["kind"] != "judge":
                    continue
                for field in ("rubric", "context"):
                    with self.subTest(case=case_id, field=field):
                        self.assertNotRegex(spec.get(field, ""), r"[0-9a-f]{7,}")
                judged += 1
        self.assertEqual(judged, 2)

    def test_no_reply_types_a_commit_sha(self):
        """WR-15: an oracle or foil quotes the tool through @RECORDED, never a typed sha."""
        sha = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,64}\b")
        seen = 0
        for path in sorted((EVALS / "cases" / "decision").glob("*.json")):
            if path.name == "states.json":
                continue
            for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
                for field in ("oracle", "foil"):
                    for reply in case.get(field) or []:
                        seen += 1
                        with self.subTest(case=case["id"], field=field):
                            self.assertNotRegex(reply.get("content") or "", sha)
        self.assertGreater(seen, 100, "the sha scan read too few replies to mean anything")

    def test_recorded_output_is_spliced_into_an_oracle(self):
        cases = dict((case["id"], case) for case in lanes.load_b())
        states = lanes.load_states()
        quoted = cases["B-31"]["oracle"][0]["content"]
        self.assertNotIn("@RECORDED", quoted)
        self.assertIn(states["drafted"]["summary"]["output"].rstrip("\n"), quoted)
        self.assertRegex(quoted, r"record: intact at [0-9a-f]{7}")
        with self.assertRaisesRegex(ValueError, "no recorded"):
            lanes._splice([{"content": "@RECORDED{drafted/nothing}"}], states, "x")

    def test_planted_runs_grade_as_the_skill_reads(self):
        """Right runs a strict regex once failed, and wrong runs a loose one would pass."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        cases = dict((case["id"], case) for case in lanes.load_b())
        draft = cases["B-27"]["resolved"]["history"][-1]["cmd"]
        fix = "Say what happens when max_retries is negative."
        accept = "The table matches what we ship."
        steer = "Say on the page that toyq init needs --force-dir on a fresh checkout."
        arrival = "They have just seen a job fail twice in toyq status."
        redraft = "Put the precedence rule before the table."
        unsafe = cases["B-58"]["history"][-1]["user"]
        apostrophe = cases["B-59"]["history"][3]["user"]
        declare = ("printf '%%s\\n' '## Intent & scope' | crayon unit new retries --intent reference "
                   "--audience 'operators running toyq on servers' --title 'Retry settings' "
                   "--target reference/retries.md --source src/toyq/config.py "
                   "--notes %s --body-file -")
        findings = cases["B-41"]["oracle"][0]["content"]
        onboarded = cases["B-56"]["oracle"][0]["content"]
        grep_install, closed_walk = cases["B-45"]["oracle"][0], cases["B-45"]["oracle"][1]["content"]
        grep_config, closed_review = cases["B-46"]["oracle"][0], cases["B-46"]["oracle"][1]["content"]

        def say(text):
            return {"content": text}

        def restore_or_amend(restore):
            return {"content": "", "tool_calls": [{"name": "AskUserQuestion", "arguments": {
                "questions": [{"question": "docs/reference/config.md is missing, so the "
                               "accept was refused. Restore the page, or amend the plan?",
                               "options": [{"label": restore},
                                           {"label": "Amend the plan"}]}]}}]}

        def bash(command):
            return {"content": "", "tool_calls": [
                {"name": "Bash", "arguments": {"command": command}}]}

        def permission_gate(run_it):
            return {"content": "", "tool_calls": [{"name": "AskUserQuestion", "arguments": {
                "questions": [{"question": cases["B-08"]["oracle"][1]["tool_calls"][0][
                                   "arguments"]["questions"][0]["question"],
                               "options": [{"label": run_it}, {"label": "Stop here"}]}]}}]}

        def resume_then_gate(run_it):
            gate = permission_gate(run_it)["tool_calls"][0]["arguments"]["questions"][0]
            return {"content": "", "tool_calls": [{"name": "AskUserQuestion", "arguments": {
                "questions": [{"question": "Resume the walk at step 1, the first unresolved "
                               "step?",
                               "options": [{"label": "Resume at step 1 (default)"},
                                           {"label": "Stop here"}]}, gate]}}]}

        planted = [
            ("B-27", [bash("crayon show cfg --json && " + draft)], True),
            ("B-27", [bash("crayon show cfg"), bash("sleep 2; " + draft + " --json")], True),
            ("B-27", [bash("crayon show cfg"), bash(draft + " --model x")], False),
            ("B-18", [bash("sleep 5 && " + draft)], True),
            ("B-06", [bash("cd %s && crayon signoff cfg" % agent.WORKDIR)], True),
            ("B-06", [bash("cd /tmp && crayon signoff cfg")], False),
            ("B-27", [bash("crayon show cfg"), bash(draft + '; echo "exit:$?"')], True),
            ("B-08", [bash("pwd; echo " + "a" * 64)], False),
            ("B-08", [bash("python3 -m toyq.cli init 2>&1 | head -5")], False),
            ("B-08", [bash("python3 -c \"print(open('.crayon/units/install/ledger.jsonl').read())\"")],
             False),
            ("B-32", [bash('crayon review "cfg" --verdict accept')], True),
            ("B-32", [bash("cd %s && crayon review cfg --verdict accept" % agent.WORKDIR)], True),
            ("B-32", [bash("crayon review cfg --verdict accept --json")], True),
            ("B-32", [bash("crayon review cfg --verdict accept --note 'Accepted.'")], False),
            ("B-32", [bash("crayon review cfg --verdict fix --note x")], False),
            # B-37 / B-39: the note is the author's text, whole, in either quote
            # style or as the whole stdin of --note-file -; nothing added, nothing cut.
            ("B-37", [bash("crayon review cfg --verdict fix --note '%s'" % fix)], True),
            ("B-37", [bash('crayon review cfg --verdict fix --note "%s"' % fix)], True),
            ("B-37", [bash("printf '%%s\\n' '%s' | crayon review cfg --verdict fix --note-file -"
                           % fix)], True),
            ("B-37", [bash("crayon review cfg --verdict fix --note '%s Thanks.'" % fix)], False),
            ("B-37", [bash("crayon review cfg --verdict fix --note '%s'" % fix[:-1])], False),
            # WR-14: the lean itself, not the option list or a tag, answers the ask.
            ("B-43", [say("The tally leans to fix: F-1 is a must-fix. What's your verdict?")],
             True),
            ("B-43", [say("My lean is fix, because F-1 is a must-fix. Your verdict?")], True),
            ("B-43", [say("It's your call: accept, fix or redraft?")], False),
            ("B-43", [say("F-1 is a must-fix. What's your verdict?")], False),
            # WR-13: one per source first, in order; first-job goes to the overflow line.
            ("B-45", [grep_install, say(closed_walk)], True),
            ("B-45", [grep_install, say(closed_walk.replace(
                "3. Nothing links to how-to/install.md yet; where should a reader come from?",
                "3. Step first-job was skipped: no network in CI. Does the page need to say "
                "so?").replace(
                "One more is open: step first-job was skipped (no network in CI).",
                "One more is open: nothing links to how-to/install.md yet."))], False),
            ("B-46", [grep_config, say(closed_review)], True),
            ("B-46", [grep_config, say(closed_review.replace(
                "1. F-2", "0. F-2").replace(
                "3. Nothing links", "1. Nothing links").replace("0. F-2", "3. F-2"))], False),
            # WR-12: the question asked is the priorities question, not the next move.
            ("B-56", [say(onboarded)], True),
            ("B-56", [say(onboarded.rsplit("\n\n", 1)[0]
                          + "\n\nShall I start /crayon-plan?")], False),
            ("B-56", [say(onboarded.rsplit("\n\n", 1)[0]
                          + "\n\nWhich unit should we declare first?")], False),
            # WR-07: the bare verdict answered the question; it is not joined into the note.
            ("B-37", [bash("crayon review cfg --verdict fix --note 'Fix.\n%s'" % fix)], False),
            ("B-39", [bash("crayon review cfg --verdict accept --note '%s'" % accept)], True),
            ("B-39", [bash('crayon review cfg --verdict accept --note "%s"' % accept)], True),
            ("B-39", [bash("printf '%%s\\n' '%s' | crayon review cfg --verdict accept --note-file -"
                           % accept)], True),
            ("B-39", [bash("crayon review cfg --verdict accept --note 'Accept. %s'" % accept)],
             False),
            ("B-39", [bash("crayon review cfg --verdict accept --note 'The table matches.'")],
             False),
            # B-41: findings prose may say "suggested"; a lean in front of the verdict fails.
            ("B-41", [say(findings.replace("→ say", "→ suggested: say"))], True),
            ("B-41", [say(findings + "\n\nI'd go with fix.")], False),
            ("B-41", [say(findings + "\n\nThe tally leans towards fix.")], False),
            ("B-41", [say("My lean is fix.\n\n" + findings)], False),
            # B-21: restore-or-amend is the author's call, so a marked option fails it.
            ("B-21", [restore_or_amend("Restore")], True),
            ("B-21", [restore_or_amend("Restore (Recommended)")], False),
            # B-48: a change asked for at closure is steered in the author's words, whole.
            ("B-48", [bash("crayon steer install --note '%s'" % steer)], True),
            ("B-48", [bash('crayon steer install --note "%s"' % steer)], True),
            ("B-48", [bash("printf '%%s\\n' '%s' | crayon steer install --note-file -" % steer)],
             True),
            ("B-48", [bash("crayon steer install --note '%s Thanks.'" % steer)], False),
            # B-54: --notes is the author's answer to the arrival question, whole.
            ("B-54", [bash(declare % ("'%s'" % arrival))], True),
            ("B-54", [bash(declare % ('"%s"' % arrival))], True),
            ("B-54", [bash(declare % ("'%s Settled terms: retry.'" % arrival))], False),
            ("B-54", [bash(declare % "'Readers arrive after repeated job failures.'")], False),
            # B-08: the stateful permission gate is a step choice, so a marked option fails it.
            ("B-08", [bash("crayon show install"), permission_gate("Run it")], True),
            ("B-08", [bash("crayon show install"), permission_gate("Run it (Recommended)")],
             False),
            # WR-10: resuming is a mechanical choice and may keep its marked default.
            ("B-08", [bash("crayon show install"), resume_then_gate("Run it")], True),
            ("B-08", [bash("crayon show install"), resume_then_gate("Run it (default)")], False),
            # B-55: after an unsteered STOP, the steer is the author's answer, whole.
            ("B-55", [bash("crayon steer cfg --note '%s'" % redraft)], True),
            ("B-55", [bash('crayon steer cfg --note "%s"' % redraft)], True),
            ("B-55", [bash("printf '%%s\\n' '%s' | crayon steer cfg --note-file -" % redraft)],
             True),
            ("B-55", [bash("crayon steer cfg --note '%s Thanks.'" % redraft)], False),
            # B-58 / B-59: words carrying a backtick and a $ reach the record only
            # single-quoted; double quotes run the one and expand the other, and a
            # printf with a newline or a heredoc adds a byte the author never typed.
            ("B-58", [bash("crayon review cfg --verdict fix --note '%s'" % unsafe)], True),
            ("B-58", [bash("printf '%%s' '%s' | crayon review cfg --verdict fix --note-file -"
                           % unsafe)], True),
            ("B-58", [bash('crayon review cfg --verdict fix --note "%s"' % unsafe)], False),
            ("B-58", [bash("printf '%%s\\n' '%s' | crayon review cfg --verdict fix --note-file -"
                           % unsafe)], False),
            ("B-58", [bash("crayon review cfg --verdict fix --note-file - <<'EOF'\n%s\nEOF"
                           % unsafe)], False),
            ("B-59", [bash(declare % ("'%s'" % apostrophe.replace("'", "'\\''")))], True),
            ("B-59", [bash(declare % ("'%s'" % apostrophe.replace("'", "'\"'\"'")))], True),
            ("B-59", [bash(declare % ('"%s"' % apostrophe))], False),
        ]
        for case_id, replies, passes in planted:
            with self.subTest(case=case_id, replies=replies):
                tr = lanes.run_b(cases[case_id], SPEC, StubProvider(run.scripted(replies)), ctx)
                out = grade.grade(cases[case_id]["assert"], tr, {"judge": ctx["judge"]})
                self.assertEqual(out["passed"], passes, out)

    def test_single_quoted_oracles_record_the_authors_bytes(self):
        """CR-01: the shell hands the tool exactly what the author typed, not a lookalike."""
        cases = dict((case["id"], case) for case in lanes.load_b())
        for case_id, flag, said in (("B-58", "--note", cases["B-58"]["history"][-1]["user"]),
                                    ("B-59", "--notes", cases["B-59"]["history"][3]["user"])):
            with self.subTest(case=case_id):
                self.assertRegex(said, r"`[^`]+`")
                self.assertIn("$", said)
                command = cases[case_id]["oracle"][0]["tool_calls"][0]["arguments"]["command"]
                words = shlex.split(command)
                self.assertEqual(words[words.index(flag) + 1], said)

    def test_a_request_put_without_a_question_mark_is_asking(self):
        for text, asks in (
                ("Stopped: `cfg` is `unsteered`.\n\nPlease tell me, in your own words, what you "
                 "want changed.", True),
                ("Request 4 is still pending. Before acceptance, should this request be recorded "
                 "as:\n- **Resolved**\n- **Withdrawn**", True),
                ("Which unit should I review?", True),
                ("Stopped: cfg is unsteered. crayon stops here.", False),
                ("Recorded. Next: /crayon-write cfg.", False)):
            with self.subTest(text=text):
                episode = dict(trace(turn(text)), decisive={"type": "text"})
                out = grade.check_asks_user({}, episode, {})
                self.assertEqual(out["pass"], asks, out)

    def test_the_opening_sequence_reads_quoted_arguments_as_plain(self):
        out = grade.check_bash_sequence(
            {"prefix": ["^crayon version --json$", "^crayon show cfg --json$"]},
            trace(turn("", [bash("crayon version --json"), bash('crayon show "cfg" --json 2>&1')])),
            {})
        self.assertTrue(out["pass"], out)

    def test_a_tool_no_one_offered_is_answered_and_the_episode_goes_on(self):
        replies = [{"content": "", "tool_calls": [
                       {"name": "Bogen", "arguments": {"command": "cat docs/index.md"}}]},
                   {"content": "Which unit should I review?"}]
        tools = agent.tools_for(skillmod.load_skills()["crayon-review"])
        messages = [{"role": "user", "content": "go"}]
        repo = agent.SandboxRepo(tempfile.mkdtemp(prefix="crayon-eval-bogen-"), sandbox.bin_dir())
        out = agent.run_episode(StubProvider(run.scripted(replies)), SPEC, messages, tools, repo)
        self.assertEqual(out["decisive"], {"type": "text"})
        self.assertEqual(len(out["turns"]), 2)

    def test_the_no_op_cd_names_the_sandbox_workdir(self):
        self.assertTrue(grade._CD_WORKDIR_RE.match("cd %s && true" % agent.WORKDIR))

    def test_an_action_is_graded_without_its_wrapping(self):
        def text(command):
            return grade.call_text({"name": "Bash", "arguments": json.dumps({"command": command})})
        self.assertEqual(text('crayon version --json; echo "---exit: $?"'), "crayon version --json")
        self.assertEqual(text("cd /srv/toyq && crayon signoff cfg && git log -1"), "crayon signoff cfg")
        self.assertEqual(text("crayon signoff cfg; rm -f x"), "crayon signoff cfg; rm -f x")
        self.assertEqual(text("crayon draft cfg x | tee out"), "crayon draft cfg x | tee out")
        self.assertEqual(text('echo "a; ls"'), 'echo "a; ls"')

    def test_lane_b_covers_all_five_skills_and_every_group(self):
        cases = lanes.load_b()
        self.assertEqual(set(c["skill"] for c in cases), set(grade.SKILL_NAMES))
        self.assertEqual(set(c["group"] for c in cases),
                         {"opening", "next", "refusals", "judged", "go", "notes", "lean",
                          "closure", "intake"})
        self.assertGreaterEqual(len(cases), 60)

    def test_every_sandbox_agrees_with_its_history(self):
        """What a model sees when it looks is what the replayed history said.

        Each recorded read-only step of every case is re-run in that case's
        sandbox, with the overrides switched off, and must print the same bytes.
        This is the property an emulated repository broke: histories and the
        tree they describe disagreed, and models spent their turns on that.
        """
        checked = 0
        for case in lanes.load_b():
            history = case["resolved"]["history"]

            def changes(step):
                if "cmd" in step:
                    return not agent.looking(step["cmd"])
                return (step.get("call") or {}).get("name") == "Write"

            last_change = max([i for i, step in enumerate(history) if changes(step)] or [-1])
            steps = [step for i, step in enumerate(history)
                     if i > last_change and "cmd" in step and not step.get("written")
                     and agent.looking(step["cmd"])]
            if not steps:
                continue
            root = sandbox.materialise(case["resolved"]["sandbox"])
            try:
                repo = agent.SandboxRepo(root, sandbox.bin_dir(), jail=sandbox.jail())
                for path, content in case["resolved"]["writes"]:
                    repo.write(path, content)
                for step in steps:
                    with self.subTest(case=case["id"], cmd=step["cmd"]):
                        output, code = repo.bash(step["cmd"])
                        self.assertEqual((output, code), (step["output"], step["exit"]))
                        checked += 1
            finally:
                sandbox.discard(root)
        self.assertGreaterEqual(checked, 20, "the agreement check has stopped matching steps")

    def test_the_recorded_states_match_what_the_tool_prints_now(self):
        stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = record_states.main(["--check"])
        finally:
            sys.stdout = stdout
        self.assertEqual(code, 0, "states.json drifted from the tool: run "
                         "python3 validation/evals/record_states.py and review the diff")

    def test_untracked_fixture_files_do_not_change_recorded_states(self):
        original_digest = sandbox.digest()
        fixture = EVALS / "fixtures" / "toyq"
        with tempfile.TemporaryDirectory(prefix="eval-untracked-", dir=str(fixture)) as stray:
            (Path(stray) / "bytecode.pyc").write_bytes(b"local cache")
            self.assertEqual(sandbox.digest(), original_digest)
            self.assertEqual(record_states.dump(record_states.record()),
                             record_states.STATES.read_text(encoding="utf-8"))


class TestRosterAndRunner(unittest.TestCase):
    """E-05 — the roster's pins and roles, and where a run's results may land."""

    def test_every_model_is_pinned_to_one_backend(self):
        roster, by_id = run.load_roster()
        for model in roster["models"]:
            with self.subTest(model=model["id"]):
                self.assertFalse(model["provider"]["allow_fallbacks"])
                self.assertIs(model["provider"].get("zdr"), True)
                self.assertEqual(len(model["provider"]["order"]), 1)
                self.assertEqual(len(model["price_per_mtok"]), 2)
        candidates = set(m["id"] for m in roster["models"] if m["role"] == "candidate")
        self.assertIn(roster["gate"], candidates)
        self.assertNotIn(roster["judge"], candidates)
        self.assertNotIn(roster["author"], candidates)
        self.assertLess(roster["caps"]["per_model_usd"], roster["caps"]["sweep_usd"])

    def summary(self, **meta):
        base = {"date": "2026-01-02", "lane": "A", "model": "vendor/model-x",
                "dry_run": False, "errors": 0, "budget_stop": None, "partial": False,
                "total_cases": 3, "cached_cases": 0}
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
                                  ({"partial": True}, "partial"),
                                  ({"cached_cases": 3}, "regrade")):
                    with self.subTest(tag=tag):
                        path = run.destination(self.summary(**meta), "120000")
                        self.assertEqual(path.parent, Path(tmp) / "raw")
                        self.assertTrue(path.name.endswith("-%s.json" % tag))
            finally:
                run.RESULTS, run.RAW = saved

    def test_a_partly_cached_run_may_still_be_a_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = run.RESULTS, run.RAW
            run.RESULTS, run.RAW = Path(tmp), Path(tmp) / "raw"
            try:
                path = run.destination(self.summary(cached_cases=2), "120000")
            finally:
                run.RESULTS, run.RAW = saved
            self.assertEqual(path.parent, Path(tmp))

    def test_an_unreachable_model_is_named_once_by_the_preflight(self):
        def refused(spec, messages, tools):
            raise ProviderError("HTTP 404: no endpoints (data policy)")

        self.assertIn("404", run.preflight_model(StubProvider(refused), SPEC))
        self.assertIsNone(run.preflight_model(StubProvider(), SPEC))

    def test_identical_errors_are_folded_into_one_line(self):
        records = [{"id": "A-%02d" % i, "passed": False, "error": "HTTP 404"}
                   for i in range(1, 4)]
        stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            run.print_problems(records)
            printed = sys.stdout.getvalue()
        finally:
            sys.stdout = stdout
        self.assertEqual(printed.count("ERROR"), 1)
        self.assertIn("A-01 (+2 more)", printed)

    def test_a_dry_run_of_everything_is_green_and_writes_only_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = run.RESULTS, run.RAW
            run.RESULTS, run.RAW = Path(tmp), Path(tmp) / "raw"
            stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = run.main(["all", "--model", "z-ai/glm-5.3", "--dry-run", "--jobs", "4"])
            finally:
                sys.stdout = stdout
                run.RESULTS, run.RAW = saved
            self.assertEqual(code, 0)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["raw"])
            written = sorted(p.name for p in (Path(tmp) / "raw").iterdir())
            self.assertTrue(written)
            self.assertTrue(all("-dry." in name for name in written))

    def test_repeated_runs_count_passes_per_case(self):
        def run_of(passes):
            records = [{"id": case_id, "passed": ok, "error": None, "cost": 0.01,
                        "failed": [] if ok else [{"kind": "k", "feedback": "no"}]}
                       for case_id, ok in passes]
            return {"meta": {"lane": "B", "model": "m", "date": "d", "total_cases": 2,
                             "passed": 0, "cost_usd": 0.02, "tokens": {"in": 1, "out": 1},
                             "truncated": 0, "budget_stop": None, "partial": False,
                             "dry_run": False}, "cases": records}
        combined = run.aggregate([run_of([("B-01", True), ("B-02", False)]),
                                  run_of([("B-01", True), ("B-02", True)]),
                                  run_of([("B-01", True), ("B-02", False)])])
        meta = combined["meta"]
        self.assertEqual((meta["runs"], meta["passes"]), (3, 4))
        self.assertEqual((meta["stable_pass"], meta["flaky"], meta["stable_fail"]), (1, 1, 0))
        self.assertEqual([(c["id"], c["passes"]) for c in combined["cases"]],
                         [("B-01", 3), ("B-02", 1)])
        self.assertTrue(run.destination(combined, "000000").name.endswith("-k3.json"))

    def test_a_repeated_dry_run_writes_each_run_and_the_counts_to_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = run.RESULTS, run.RAW
            run.RESULTS, run.RAW = Path(tmp), Path(tmp) / "raw"
            stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = run.main(["A", "--model", "z-ai/glm-5.3", "--dry-run", "--repeat", "2"])
            finally:
                sys.stdout = stdout
                run.RESULTS, run.RAW = saved
            self.assertEqual(code, 0)
            written = sorted(p.name for p in (Path(tmp) / "raw").iterdir())
            self.assertEqual(len([n for n in written if "run1of2.json" in n or
                                  "run2of2.json" in n]), 2)
            self.assertEqual(len([n for n in written if "-k2-" in n and n.endswith("-dry.json")]), 1)

    def test_an_unknown_model_is_refused_before_anything_runs(self):
        stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            self.assertEqual(run.main(["A", "--model", "vendor/not-listed", "--dry-run"]), 2)
        finally:
            sys.stderr = stderr


if __name__ == "__main__":
    unittest.main()
