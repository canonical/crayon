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
        signoff = call("Bash", command="dogen signoff cfg")
        tr = episode({"type": "call", "call": signoff},
                     turn(calls=[bash("dogen show cfg"), bash("dogen signoff cfg")]))
        spec = {"kind": "decisive", "tool": "Bash", "args_re": r"^dogen signoff cfg$"}
        self.assertTrue(self.check(spec, tr)["pass"])
        self.assertFalse(self.check(dict(spec, args_re="^dogen draft"), tr)["pass"])
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
        acted = episode({"type": "call", "call": call("Bash", command="dogen edits cfg")}, turn())
        self.assertFalse(self.check({"kind": "asks_user"}, acted)["pass"])

    def test_text_kinds_read_the_questions_too(self):
        question = call("AskUserQuestion", questions=[
            {"question": "How should I ground this?",
             "options": [{"label": "Run /dogen-onboard first"}]}])
        tr = episode({"type": "call", "call": question},
                     {"content": "", "tool_calls": [question], "finish_reason": "tool_calls",
                      "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}})
        self.assertTrue(self.check({"kind": "text_re", "re": "dogen-onboard"}, tr)["pass"])

    def test_bash_sequence_and_before(self):
        tr = trace(turn(calls=[("Read", {"file_path": "x"}), bash("dogen version --json")]),
                   turn(calls=[bash("dogen show cfg --json")]))
        seq = {"kind": "bash_sequence", "prefix": ["^dogen version", "^dogen show cfg --json$"]}
        self.assertTrue(self.check(seq, tr)["pass"])
        self.assertFalse(self.check(dict(seq, prefix=["^dogen show"]), tr)["pass"])
        order = {"kind": "before", "first": "--dry-run", "then": "^dogen resume cfg$"}
        good = trace(turn(calls=[bash("dogen resume cfg --dry-run"), bash("dogen resume cfg")]))
        bad = trace(turn(calls=[bash("dogen resume cfg"), bash("dogen resume cfg --dry-run")]))
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


class TestAgentSurface(unittest.TestCase):
    """E-07 — tools per skill, the sandbox, and where an episode ends."""

    def setUp(self):
        self.holder = tempfile.mkdtemp(prefix="dogen-eval-test-")
        root = Path(self.holder) / "repo"
        (root / "src").mkdir(parents=True)
        (root / "src" / "a.py").write_text("retries = 3\n", encoding="utf-8")
        (root / ".agents" / "skills" / "dogen-plan").mkdir(parents=True)
        (root / ".agents" / "skills" / "dogen-plan" / "SKILL.md").write_text("body", encoding="utf-8")
        self.root = str(root)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.holder, ignore_errors=True)

    def repo(self):
        return agent.SandboxRepo(self.root, sandbox.bin_dir(),
                                 [{"exact": "dogen show cfg --json", "output": "{}", "exit": 0}],
                                 jail=sandbox.jail())

    def test_a_skill_is_offered_exactly_the_tools_it_declares(self):
        loaded = skillmod.load_skills()
        names = lambda s: [t["function"]["name"] for t in agent.tools_for(loaded[s])]
        self.assertIn("Write", names("dogen-write"))
        for other in ("dogen-plan", "dogen-review", "dogen-onboard", "dogen-fetch"):
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
            (call("Bash", command='dogen show "cfg" --json 2>&1'), False, "{}"),
            (call("Bash", command="cat src/a.py"), False, "retries = 3"),
            (call("Bash", command="ls -la /srv/toyq && ls /srv/toyq/src 2>/dev/null"), False, "a.py"),
            (call("Bash", command="pwd"), False, "/srv/toyq"),
            (call("Bash", command='grep -rn "retr\\|x" src | grep -v zzz'), False, "retries"),
            (call("Bash", command="WS=.dogen/staging/x/scratch && mkdir -p $WS/evidence"), False, ""),
            (call("Bash", command='for f in src/*; do case "$f" in *.pyc) ;; *) cat "$f" ;; esac; done'),
             False, "retries"),
            (call("Bash", command="if [ -f src/a.py ]; then cat src/a.py; fi"), False, "retries"),
            (call("Bash", command="which git; pip show nothing-installed 2>/dev/null | head -2"), False, ""),
            (call("Bash", command="for f in src/*; do rm $f; done"), True, None),
            (call("Bash", command="if [ -f src/a.py ]; then rm src/a.py; fi"), True, None),
            (call("Bash", command="dogen signoff cfg"), True, None),
            (call("Bash", command="dogen resume cfg"), True, None),
            (call("Bash", command="sleep 2; dogen draft cfg x"), True, None),
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
                                 [{"prefix": "dogen show cfg", "output": "{\"error\": \"x\"}",
                                   "exit": 2}])
        for command in ("dogen show cfg --json", "dogen show cfg", 'dogen show "cfg" --diff'):
            with self.subTest(command=command):
                out, acted = repo.serve(call("Bash", command=command))
                self.assertFalse(acted)
                self.assertIn('"error"', out)
        out, _ = repo.serve(call("Bash", command="dogen show cfgx"))
        self.assertNotIn('"error": "x"', out)

    def test_a_model_command_never_sees_the_runner_environment(self):
        os.environ["DOGEN_EVAL_CANARY"] = "canary-value"
        try:
            out, _ = self.repo().serve(call("Bash", command="echo $DOGEN_EVAL_CANARY $OPENROUTER_API_KEY"))
        finally:
            del os.environ["DOGEN_EVAL_CANARY"]
        self.assertNotIn("canary-value", out)
        self.assertNotIn("sk-", out)

    def test_history_writes_land_inside_the_repository_only(self):
        repo = self.repo()
        repo.write(".dogen/staging/cfg/draft/p.md", "draft")
        self.assertIn("draft", repo.read({"file_path": ".dogen/staging/cfg/draft/p.md"}))
        with self.assertRaises(ValueError):
            repo.write("../escape.md", "x")

    def test_an_episode_ends_on_the_first_consequential_call(self):
        replies = run.scripted([
            {"tool_calls": [{"name": "Read", "arguments": {"file_path": "src/a.py"}}]},
            {"tool_calls": [{"name": "Bash", "arguments": {"command": "dogen signoff cfg"}},
                            {"name": "Bash", "arguments": {"command": "dogen draft cfg x"}}]},
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
            {"cmd": "dogen version --json", "exit": 0, "output": "{}"},
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
        self.holder = tempfile.mkdtemp(prefix="dogen-eval-jail-")
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
        out, _ = self.run_looking("env; which dogen; pwd; cat a.txt; dogen version --json")
        for secret in (str(ROOT), os.path.expanduser("~")):
            self.assertNotIn(secret, out)
        self.assertIn("/opt/dogen/bin/dogen", out)
        self.assertIn("/srv/toyq", out)
        self.assertIn("inside", out)
        self.assertIn('"contract"', out)

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

    def test_planted_runs_grade_as_the_skill_reads(self):
        """Right runs a strict regex once failed, and wrong runs a loose one would pass."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        cases = dict((case["id"], case) for case in lanes.load_b())
        draft = cases["B-27"]["resolved"]["history"][-1]["cmd"]

        def bash(command):
            return {"content": "", "tool_calls": [
                {"name": "Bash", "arguments": {"command": command}}]}

        planted = [
            ("B-27", [bash("dogen show cfg --json && " + draft)], True),
            ("B-27", [bash("dogen show cfg"), bash("sleep 2; " + draft + " --json")], True),
            ("B-27", [bash("dogen show cfg"), bash(draft + " --model x")], False),
            ("B-18", [bash("sleep 5 && " + draft)], True),
            ("B-06", [bash("cd %s && dogen signoff cfg" % agent.WORKDIR)], True),
            ("B-06", [bash("cd /tmp && dogen signoff cfg")], False),
            ("B-27", [bash("dogen show cfg"), bash(draft + '; echo "exit:$?"')], True),
            ("B-08", [bash("pwd; echo " + "a" * 64)], False),
            ("B-08", [bash("python3 -m toyq.cli init 2>&1 | head -5")], False),
            ("B-08", [bash("python3 -c \"print(open('.dogen/units/install/ledger.jsonl').read())\"")],
             False),
        ]
        for case_id, replies, passes in planted:
            with self.subTest(case=case_id, replies=replies):
                tr = lanes.run_b(cases[case_id], SPEC, StubProvider(run.scripted(replies)), ctx)
                out = grade.grade(cases[case_id]["assert"], tr, {"judge": ctx["judge"]})
                self.assertEqual(out["passed"], passes, out)

    def test_a_request_put_without_a_question_mark_is_asking(self):
        for text, asks in (
                ("Stopped: `cfg` is `unsteered`.\n\nPlease tell me, in your own words, what you "
                 "want changed.", True),
                ("Request 4 is still pending. Before acceptance, should this request be recorded "
                 "as:\n- **Resolved**\n- **Withdrawn**", True),
                ("Which unit should I review?", True),
                ("Stopped: cfg is unsteered. dogen stops here.", False),
                ("Recorded. Next: /dogen-write cfg.", False)):
            with self.subTest(text=text):
                episode = dict(trace(turn(text)), decisive={"type": "text"})
                out = grade.check_asks_user({}, episode, {})
                self.assertEqual(out["pass"], asks, out)

    def test_the_opening_sequence_reads_quoted_arguments_as_plain(self):
        out = grade.check_bash_sequence(
            {"prefix": ["^dogen version --json$", "^dogen show cfg --json$"]},
            trace(turn("", [bash("dogen version --json"), bash('dogen show "cfg" --json 2>&1')])),
            {})
        self.assertTrue(out["pass"], out)

    def test_a_tool_no_one_offered_is_answered_and_the_episode_goes_on(self):
        replies = [{"content": "", "tool_calls": [
                       {"name": "Bogen", "arguments": {"command": "cat docs/index.md"}}]},
                   {"content": "Which unit should I review?"}]
        tools = agent.tools_for(skillmod.load_skills()["dogen-review"])
        messages = [{"role": "user", "content": "go"}]
        repo = agent.SandboxRepo(tempfile.mkdtemp(prefix="dogen-eval-bogen-"), sandbox.bin_dir())
        out = agent.run_episode(StubProvider(run.scripted(replies)), SPEC, messages, tools, repo)
        self.assertEqual(out["decisive"], {"type": "text"})
        self.assertEqual(len(out["turns"]), 2)

    def test_the_no_op_cd_names_the_sandbox_workdir(self):
        self.assertTrue(grade._CD_WORKDIR_RE.match("cd %s && true" % agent.WORKDIR))

    def test_an_action_is_graded_without_its_wrapping(self):
        def text(command):
            return grade.call_text({"name": "Bash", "arguments": json.dumps({"command": command})})
        self.assertEqual(text('dogen version --json; echo "---exit: $?"'), "dogen version --json")
        self.assertEqual(text("cd /srv/toyq && dogen signoff cfg && git log -1"), "dogen signoff cfg")
        self.assertEqual(text("dogen signoff cfg; rm -f x"), "dogen signoff cfg; rm -f x")
        self.assertEqual(text("dogen draft cfg x | tee out"), "dogen draft cfg x | tee out")
        self.assertEqual(text('echo "a; ls"'), 'echo "a; ls"')

    def test_lane_b_covers_all_five_skills_and_every_group(self):
        cases = lanes.load_b()
        self.assertEqual(set(c["skill"] for c in cases), set(grade.SKILL_NAMES))
        self.assertEqual(set(c["group"] for c in cases), {"opening", "next", "refusals", "judged"})
        self.assertGreaterEqual(len(cases), 30)

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

    def test_an_unknown_model_is_refused_before_anything_runs(self):
        stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            self.assertEqual(run.main(["A", "--model", "vendor/not-listed", "--dry-run"]), 2)
        finally:
            sys.stderr = stderr


if __name__ == "__main__":
    unittest.main()
