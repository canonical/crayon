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
import shutil
import sys
import tempfile
import time
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

#: WR-04: the record words the plain-words rule names and the check fails, one
#: typed form each, so the rule (``skills/README.md``), the grader
#: (``grade.LEDGER_WORDS_RE``) and the eval README are each read against it.
RECORD_WORDS = ("sealed", "basis", "seq", "plan_hash", "hash", "sha256", "digest",
                "event 7", "ledger line 7")

#: B-61's foil proves the always-on plain-words check end to end, so it is the
#: one case allowed to fail on that check alone; any other foil that fails only
#: it would hide a case whose own assertions are vacuous (Pitfall 2).
PLAIN_WORDS_ONLY_FOILS = {
    "B-61": "its foil names request 4 and its record number too; only the "
            "always-on check can fail it",
}


#: CR-01: the one-line notice after a step answer that asks for a page change,
#: typed once: it is not recorded until the verdict, and a fix or redraft
#: verdict with those words records it. B-65 and B-75 each carry both (IN-01).
NOTICE_RES = (
    "(?i)\\b(not|nothing|isn['\u2019]t)\\b[^\\n]{0,60}\\brecorded\\b",
    "(?i)\\b(fix|redraft)\\b[^\\n]{0,80}\\brecords?\\b|\\brecord(s|ed)?\\b[^\\n.?]{0,40}?"
    "\\b(if|when|once|with)\\s+(a\\s+|your\\s+|you\\s+give\\s+a\\s+)?(verdict\\s+is\\s+a\\s+)?"
    "(fix|redraft)\\b",
)

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


def conversation_key(case):
    """One lane B conversation: the skill, the ask, the sandbox, and the
    resolved prelude and history replayed into it (P-22-36). Two cases with the
    same key put the model in the same place, so a reply cannot be right in one
    and wrong in the other."""
    resolved = case["resolved"]
    return (case["skill"], case.get("ask", ""), resolved["sandbox"],
            json.dumps(resolved["prelude"], sort_keys=True),
            json.dumps(resolved["history"], sort_keys=True))


def conversations(cases):
    """Lane B cases grouped by ``conversation_key``, in load order."""
    groups = {}
    for case in cases:
        groups.setdefault(conversation_key(case), []).append(case)
    return list(groups.values())


def oracles_failing_a_sibling(cases, ctx):
    """Every (oracle case id, sibling case id) pair in one conversation where
    the oracle, run once and graded offline with ``ctx``'s judge, fails the
    sibling's assertions (WR-06). One state, one right answer: an oracle that
    fails a sibling would be right in one case and wrong in the other. Foils are
    not graded against siblings; a foil need only fail its own case."""
    found = []
    for group in conversations(cases):
        if len(group) < 2:
            continue
        for good in group:
            tr = lanes.run_b(good, SPEC, StubProvider(run.scripted(good["oracle"])), ctx)
            for other in group:
                if other is not good and not grade.grade(
                        other["assert"], tr, {"judge": ctx["judge"]})["passed"]:
                    found.append((good["id"], other["id"]))
    return sorted(found)


_FENCE_RE = re.compile(r"(?m)^(?:```|~~~)")


def known_good_splices(case):
    """(where, text) for each known-good reply in a raw case: every oracle
    turn's content, and every ``assistant`` string replayed in its history or
    prelude. Foils are not here: a foil may break a rule on purpose."""
    texts = [("oracle[%d]" % i, reply.get("content"))
             for i, reply in enumerate(case.get("oracle") or [])]
    for field in ("prelude", "history"):
        texts += [("%s[%d]" % (field, i), step.get("assistant"))
                  for i, step in enumerate(case.get(field) or []) if isinstance(step, dict)]
    return [(where, text) for where, text in texts if isinstance(text, str)]


def unfenced_splices(case):
    """Each ``@RECORDED{…}`` in a known-good reply of a raw case, before
    splicing, that sits outside a fenced block (WR-07): an even count of fence
    openings, three backticks or three tildes, before it."""
    found = []
    for where, text in known_good_splices(case):
        for match in lanes._RECORDED_RE.finditer(text):
            if len(_FENCE_RE.findall(text[:match.start()])) % 2 == 0:
                found.append((where, match.group(0)))
    return found


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

    def test_plain_words_flags_a_record_word_and_names_it(self):
        spec = {"kind": "plain_words"}
        said = self.check(spec, trace(turn("Seq 4 is still pending.")))
        self.assertFalse(said["pass"])
        self.assertIn("'Seq'", said["feedback"])
        ran = turn("Request 4 is still pending; I ran "
                   "`crayon review cfg --verdict accept --resolves 4`")
        self.assertTrue(self.check(spec, trace(ran))["pass"])
        fenced = turn("The tool printed:\n\n```\nthe basis at seq 3 was already accepted\n```\n"
                      "\nRequest 3 is accepted.")
        self.assertTrue(self.check(spec, trace(fenced))["pass"])
        asked = ("AskUserQuestion", {"questions": [{
            "question": "Is seq 4 resolved?",
            "options": [{"label": "Yes"}, {"label": "No"}]}]})
        self.assertFalse(self.check(spec, trace(turn(calls=[asked])))["pass"])
        described = ("AskUserQuestion", {"questions": [{
            "question": "Accept request 4?",
            "options": [{"label": "Accept", "description": "Seals it"},
                        {"label": "Not yet"}]}]})
        self.assertFalse(self.check(spec, trace(turn(calls=[described])))["pass"])

    def test_plain_words_strips_code_in_each_part_alone(self):
        # Joined, the reply's unclosed fence would pair with the option's fence
        # and swallow the question between them: the check would fail open.
        ask = ("AskUserQuestion", {"questions": [{
            "question": "The basis is sealed.",
            "options": [{"label": "Fine", "description": "```\nok\n```"}]}]})
        tr = trace(turn("Here is what it printed:\n```\nrequest 4 is pending", calls=[ask]))
        out = self.check({"kind": "plain_words"}, tr)
        self.assertFalse(out["pass"], out)
        self.assertIn("'basis'", out["feedback"])

    def said_everywhere(self, text):
        """``text`` said in reply prose, a question, an option label and a description."""
        def asked(question="Which one?", label="Go on", description=""):
            return trace(turn(calls=[("AskUserQuestion", {"questions": [{
                "question": question,
                "options": [{"label": label, "description": description}]}]})]))
        return {"prose": trace(turn(text)), "question": asked(question=text),
                "label": asked(label=text), "description": asked(description=text)}

    def test_plain_words_reads_every_token_everywhere_the_author_reads(self):
        spec = {"kind": "plain_words"}
        for token in ("seal", "seals", "sealed", "SEALED", "basis", "seq", "Seq", "seqs",
                      "plan_hash", "plan hash", "Plan Hash", "hash", "hashes", "sha256",
                      "SHA-256", "digest", "digests", "event 7", "ledger line 7"):
            for where, tr in self.said_everywhere("Here %s is said." % token).items():
                with self.subTest(token=token, where=where):
                    out = self.check(spec, tr)
                    self.assertFalse(out["pass"], out)
                    self.assertIn(repr(token), out["feedback"])
            for form, text in (("inline code", "Here `%s` is quoted." % token),
                               ("fenced block", "Quoted:\n```\n%s 4\n```\nDone." % token),
                               ("tilde fence", "Quoted:\n~~~\n%s 4\n~~~\nDone." % token)):
                for where, tr in self.said_everywhere(text).items():
                    with self.subTest(token=token, form=form, where=where):
                        out = self.check(spec, tr)
                        self.assertTrue(out["pass"], out)

    def test_plain_words_passes_plain_forms_and_flags_idioms(self):
        spec = {"kind": "plain_words"}
        for text in ("cfg is accepted.", "These are the pages as accepted.",
                     "Request 7 is still open.", "Run the sequence of steps again.",
                     "Sealing it is the author's call.",
                     "Line 13 of the page carries two clauses.", "The events are listed.",
                     "Add a hashtag.", "The base page links here."):
            with self.subTest(text=text):
                self.assertTrue(self.check(spec, trace(turn(text)))["pass"])
        # WR-04: the set is the plain-words rule's own forms, exactly these, so
        # "sealing" passes and a page's "line 13" is not a ledger line. The rule
        # bans the words even as an English idiom, and a flag outside a code span
        # is prose. Pitfall 6: an rST double-backtick literal is not stripped;
        # single backticks are the inline code form, so ``seq`` reads as prose.
        for text in ("The queue drains on a daily basis.", "Pass --steps-seq 3 to the tool.",
                     "Add a Crayon-Seq trailer.", "The ``seq`` field is 4."):
            with self.subTest(text=text):
                self.assertFalse(self.check(spec, trace(turn(text)))["pass"])

    def test_plain_words_on_an_empty_trace_is_an_error(self):
        spec = {"kind": "plain_words"}
        with self.assertRaises(grade.GradeError):
            self.check(spec, trace())
        for text in ("", "~~~\n~~~", "~~~\nthe basis at seq 3\n~~~",
                     "```\nplan_hash sha256\n```"):
            with self.subTest(text=text):
                self.assertTrue(self.check(spec, trace(turn(text)))["pass"])

    def test_plain_words_reads_an_indented_block_as_prose(self):
        # Only a fence or an inline span is code to the grader; an indented block
        # is prose, so tool output shown that way fails (the eval README says so).
        out = self.check({"kind": "plain_words"},
                         trace(turn("The tool printed:\n\n    the basis at seq 3\n\nDone.")))
        self.assertFalse(out["pass"], out)
        self.assertIn("'basis'", out["feedback"])

    def test_plain_words_has_no_runaway_backtracking(self):
        text = ("event ledger line sha plan hash " * 1600)[:50000]
        start = time.monotonic()
        grade.LEDGER_WORDS_RE.search(text)
        grade.LEDGER_WORDS_RE.findall(text)
        self.assertLess(time.monotonic() - start, 1.0)

    def test_said_is_its_parts_joined(self):
        ask = ("AskUserQuestion", {"questions": [{
            "question": "Which request first?",
            "options": [{"label": "Request 4", "description": "the retries table"},
                        {"label": "Request 7"}]}]})
        tr = trace(turn("Two requests are open."), turn(calls=[ask]))
        self.assertEqual(grade._said(tr), "\n".join(grade._said_parts(tr)))
        self.assertEqual(len(grade._said_parts(tr)), 4)

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

    #: D-12: every hand-typed case count in the docs, and the pattern that reads
    #: it. The loader is the one definition site; each pattern must match exactly
    #: once per lane, so a reworded document cannot pass vacuously.
    COUNT_SITES = (
        ("docs/evals.md", r"^\| (A|B) \|[^\n]*\| built, (\d+) cases \|$"),
        ("validation/evals/README.md", r"^\| (A|B) \|[^\n]*\| built, (\d+) cases \|$"),
        ("CHANGELOG.md", r"Lane (A|B) checks [^()]*?\((\d+) cases\)"),
    )

    def test_every_documented_case_count_is_the_loaders(self):
        """D-12: a case added or removed without fixing a typed count goes red."""
        cases_b = lanes.load_b()
        expected = {"A": len(lanes.load_a()), "B": len(cases_b)}
        for relative, pattern in self.COUNT_SITES:
            found = re.findall(pattern, (ROOT / relative).read_text(encoding="utf-8"),
                               re.MULTILINE)
            with self.subTest(document=relative):
                # Vacuous-pass guard: a pattern that stopped matching proves nothing.
                self.assertEqual(sorted(lane for lane, _ in found), ["A", "B"],
                                 "%s: the count pattern matched %r" % (relative, found))
                for lane, count in found:
                    self.assertEqual(int(count), expected[lane],
                                     "%s says lane %s has %s cases; the loader has %d"
                                     % (relative, lane, count, expected[lane]))
        relative = "validation/evals/README.md"
        judged = re.findall(r"that action, the calls on the way, (\d+) judged",
                            (ROOT / relative).read_text(encoding="utf-8"))
        loaded = sum(1 for case in cases_b
                     if any(spec["kind"] == "judge" for spec in case["assert"]))
        with self.subTest(document=relative, count="judged"):
            self.assertEqual(len(judged), 1,
                             "%s: the judged pattern matched %r" % (relative, judged))
            self.assertEqual(int(judged[0]), loaded,
                             "%s says lane B has %s judged cases; the loader has %d"
                             % (relative, judged[0], loaded))


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

    def test_question_count_ignores_question_marks_in_a_tilde_fence(self):
        fenced = self.replied("Recorded:\n~~~\nwhat? why? how?\n~~~\nNext: /crayon-write cfg.")
        self.assertTrue(self.counts({"max": 0}, fenced)["pass"])
        self.assertFalse(self.counts({"min": 1}, fenced)["pass"])

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
        for name in ("@MARKER", "@OFFERS_PUBLISH", "@OFFERS_NOTE", "@HEDGE"):
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

    def test_offers_publish_reads_the_routed_token_in_code_as_a_mention(self):
        """23-03, B-47: the replies glm-5.3 and qwen3.8-27b gave in the first sweep quote the
        routed token in inline code, which the macro's own comment calls a mention. The
        bare token, or the token half-quoted, is still an offer."""
        self.proves("@OFFERS_PUBLISH", caught=[
            trace(turn("Next: publish")),
            trace(turn("Next: publish`")),
            trace(turn("`Next: publish")),
            trace(turn("The page is accepted. Next: open a PR.")),
        ], missed=[
            trace(turn("The opening checks pass: tool `0.2.0`, contract `1`, and "
                       "`crayon show cfg --json` routes on `next: publish` \u2014 the unit is "
                       "accepted with its page current, nothing recorded since.")),
            trace(turn("The tool pairs fine (tool 0.2.0, contract 1). Let me check the routing "
                       "row for `next: publish`.")),
            trace(turn("The unit is accepted and current (`next: publish` \u2014 crayon stops "
                       "here).")),
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

    def test_hedge_catches_a_blanket_disclaimer_and_misses_a_grounded_line(self):
        self.proves("@HEDGE", caught=[
            trace(turn("Please double-check the page before publishing.")),
            trace(turn("This page may contain errors.")),
            trace(turn("I might have made mistakes.")),
            trace(turn("What I'm not sure of:\n- the retry order")),
            trace(turn("Please verify everything before you accept.")),
            self.options(("Accept", "Please double-check everything first"), ("Fix", "")),
            # WR-03: a negated blanket disclaimer names no thing; it is a hedge.
            trace(turn("I couldn't verify everything.")),
            trace(turn("I could not verify all of it.")),
            trace(turn("I didn't verify the page.")),
            trace(turn("Some details may be inaccurate.")),
            trace(turn("I might be wrong about the defaults.")),
            trace(turn("I couldn\u2019t verify everything else.")),
            # WR-01: can / cannot / can not, an -ly adverb, could be wrong and
            # there may be errors are blanket too.
            trace(turn("I can't verify everything.")),
            trace(turn("I can\u2019t verify everything.")),
            trace(turn("I cannot verify all of it.")),
            trace(turn("I can not verify the page.")),
            trace(turn("I have not fully verified everything.")),
            trace(turn("This could be wrong.")),
            trace(turn("There may be errors.")),
        ], missed=[
            trace(turn("I didn't run `toyq migrate`; the page describes it from cli.py.")),
            trace(turn("I found no source listing the accepted log_level values.")),
            trace(turn("I inferred the retry order from queue.py.")),
            trace(turn("I could not verify the page's log_level default against any source.")),
            # D-09: the self-review line names its grounds; it is not a disclaimer.
            trace(turn("I drafted this page, so this is a self-review; I'm likely to miss "
                       "what I got wrong the first time. Weigh these findings with that "
                       "in mind.")),
            trace(turn("Run `crayon verify cfg` to check the record.")),
            trace(turn("I double-checked the defaults against config.py.")),
            # WR-02: a line that names its thing is grounded, not blanket; the page
            # and the details are blanket only at the end of a clause, and "may be
            # wrong" only after a generic or first-person subject.
            trace(turn("I couldn't verify the details of log_level: no source lists its "
                       "accepted values, so the page gives only the default.")),
            trace(turn("F-1 [must-fix] \"max_retries must be 0 or more.\" "
                       "(reference/config.md:13) may be wrong: it states the rule but not "
                       "what breaking it does.")),
            trace(turn("F-1: the page states a default that may be wrong "
                       "(reference/config.md:13).")),
            trace(turn("There may be errors in the retry table at reference/config.md:13; "
                       "config.py lists four values.")),
            trace(turn("I cannot verify the page against a running toyq: the walk never "
                       "ran first-job.")),
        ])

    def test_hedge_has_no_runaway_backtracking(self):
        pattern = lanes._expand("@HEDGE")
        for text in (("please may might could I verify " * 1600)[:50000],
                     ("I can not fully verified the some of " * 1400)[:50000]):
            with self.subTest(text=text[:40]):
                start = time.monotonic()
                re.search(pattern, text)
                self.assertLess(time.monotonic() - start, 1.0)


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

    def test_the_looks_the_first_sweep_misgraded_are_looking(self):
        """23-03's kit faults: each read-only look below, as a model typed it in the
        2026-10-11 sweep, ended its episode as the graded action. Each is looking now,
        and the acting command beside it that shares its shape still is not."""
        looks = [
            # 23-03: B-07 glm-5.3 run 1
            'find /srv/toyq -name "*.py" -not -path "*/.git/*" | xargs ls -la; cat /srv/toyq/pyproject.toml',
            # 23-03: B-07 glm-5.3 run 3
            'python3 -c "import subprocess, inspect; print(inspect.getsource(subprocess.call))"',
            # 23-03: B-47 gpt-5.6-luna run 1
            "find docs -type f -maxdepth 6 -print 2>/dev/null | sort; grep -RInE 'reference/config|\\{doc\\}`?reference/config|:doc:`reference/config|toctree|config\\.md' docs 2>/dev/null || true",
            # 23-03: B-56 qwen3.8-27b run 1
            "git ls-tree -r --name-only 1d10b75 2>/dev/null | grep -E '^docs/' ; echo ---; git ls-tree -r --name-only HEAD | grep -E '^docs/'",
            # 23-03: B-44 qwen3.8-27b run 3
            "grep -rn -E 'reference/config|:doc:`config`|\\{doc\\}.*config|`config`' docs/ 2>/dev/null; ls docs docs/reference 2>/dev/null",
            # 23-03: B-41 deepseek-v4.1-flash run 1
            'cd /srv/toyq && ls -la .crayon/staging/cfg/draft/reference/ && find .crayon/staging/cfg -type f | xargs ls -la',
            # 23-03: B-17 deepseek-v4.1-flash run 1
            'cd /srv/toyq && grep -rn "reference/config\\|{doc}\\`config\\|:doc:\\`config\\|config" docs --include=*.md --include=*.rst --include=*.txt --include=*.py | head -60',
            # 23-03: B-19 deepseek-v4.1-flash run 1
            'cd /srv/toyq && git log --all --oneline -- .crayon/staging/cfg/draft/reference/config.md; echo "--- ignored? ---"; git check-ignore -v .crayon/staging/cfg/draft/reference/config.md; echo "---"; wc -c .crayon/staging/cfg/draft/reference/config.md docs/reference/config.md',
            # 23-03: B-22 deepseek-v4.1-flash run 1
            'cd /srv/toyq && cat .gitignore 2>/dev/null; echo "--- ignored:"; git check-ignore -v .crayon/staging/cfg/draft/reference/config.md .crayon/staging/lock 2>&1; echo ---; ls -la .crayon/staging/cfg/draft/reference/; echo ---; cat .crayon/staging/lock 2>/dev/null',
            # 23-03: B-56 deepseek-v4.1-flash run 2
            'cd /srv/toyq && echo "=== files in d4ab5df (parent) ==="; git ls-tree -r d4ab5df --name-only | head -50; echo; echo "=== was .crayon/context tracked before? ==="; git ls-tree -r d4ab5df --name-only | grep crayon',
            # 23-03: B-41 deepseek-v4.1-flash run 2
            "cd /srv/toyq && awk '/## Findings layout/,0' .agents/skills/crayon-review/references/review-rubric.md",
            # 23-03: B-17 deepseek-v4.1-flash run 2
            'cd /srv/toyq && git reflog --date=iso | head -20 && echo "=== log with dates ===" && git log --format=\'%h %cI %ci %s\' -6 && echo "=== now ===" && date -Is && echo "=== ls ===" && ls -la --time-style=full-iso .crayon/units/cfg/ && ls -la --time-style=full-iso .crayon/staging 2>/dev/null',
            # 23-03: B-60 deepseek-v4.1-flash run 3
            'ls docs 2>/dev/null; echo ---; grep -rn "reference/config\\|{doc}\\`config\\|:doc:\\`config\\|config" docs --include=*.md --include=*.rst -l 2>/dev/null | head -50',
            # 23-03: B-46 deepseek-v4.1-flash run 3
            'cd /srv/toyq && ls docs && grep -rn "config" docs --include=* -l; echo ---; grep -rn "reference/config\\|{doc}\\`config\\|:doc:\\`config\\|config$\\|config\\b" docs | head -50',
            # 23-03: B-63 deepseek-v4.1-flash run 3
            'cd /srv/toyq; pwd; echo "== force-dir / force_dir =="; grep -rn "force.dir\\|force_dir" . --include=\'*\' -I 2>/dev/null | grep -v \'^./.git/\' | grep -v \'^./.crayon/\'; echo "hits:$?"; echo "== \'once\' in src =="; grep -rn "once" src/ | head; echo "== README install lines =="; grep -n "pip install\\|toyq init\\|toyq run\\|toyq add\\|working directory" README.md; echo "== console/backtick style in page =="; grep -c \'```\' docs/how-to/install.md',
            # 23-03: B-17 deepseek-v4.1-flash run 3
            'cd /srv/toyq && grep -rn "config" docs/ --include=*.md --include=*.rst -l; echo "---"; ls docs; echo "---"; grep -rn "reference/config\\|{doc}\\`config\\|:doc:\\`config\\|config\\`\\|config$" docs/ 2>/dev/null | head -50',
            # 23-03: B-22 deepseek-v4.1-flash run 3
            'cat .crayon/staging/cfg/draft/reference/config.md; echo "=== docs file ==="; cat docs/reference/config.md; echo "=== baseline tree ==="; git ls-tree -r --name-only HEAD; echo "=== d4ab5df ==="; git ls-tree -r --name-only d4ab5df | head -50',
            # P-23-12: a pager switched off before a reading verb.
            "git --no-pager log -1",
            "git --no-pager diff --stat",
            "git -C /srv/toyq --no-pager show HEAD:docs/index.md",
        ]
        acting = [
            "git --no-pager commit -m x",
            "git --no-pager push",
            "git reflog expire --expire=now --all",
            "git reflog delete HEAD@{1}",
            "find . -name '*.py' | xargs rm",
            "find . -name '*.py' | xargs -I{} sh -c 'rm {}'",
            "awk '{print > \"out.txt\"}' src/a.py",
            "awk 'BEGIN { system(\"rm src/a.py\") }'",
            "awk '{print | \"sh\"}' src/a.py",
            "awk -i inplace '{print}' src/a.py",
            "python3 -c \"import subprocess; subprocess.run(['rm', 'a.txt'])\"",
            "python3 -c \"import subprocess, inspect; subprocess.call('rm a.txt', shell=True)\"",
            "python3 -c \"import subprocess as s; s.call(['rm', 'a.txt'])\"",
            "python3 -c \"from subprocess import run; run(['rm', 'a.txt'])\"",
            "python3 -c \"import subprocess; list(map(subprocess.call, [['rm', 'a.txt']]))\"",
            "grep -rn 'x' `rm -rf src`",
            "grep -rn \"$(rm -rf src)\" docs",
            "echo \"`touch x`\"",
        ]
        for command in looks:
            with self.subTest(looking=command):
                self.assertTrue(agent.looking(command, python=True))
        for command in acting:
            with self.subTest(acting=command):
                self.assertFalse(agent.looking(command, python=True))

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
        steps = [{"cmd": "crayon version --json", "exit": 0, "output": "{}"},
                 {"cmd": "crayon show cfg", "exit": 0, "output": "x"}]

        def ids(messages):
            return [m["tool_calls"][0]["id"] for m in messages if m.get("tool_calls")]

        self.assertEqual(ids(agent.history_messages(steps)), ["h0", "h1"])
        self.assertEqual(ids(agent.history_messages(steps, prefix="p")), ["p0", "p1"])


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
                failing = set(item["kind"] for item in out["results"] if not item["pass"])
                if case["id"] in PLAIN_WORDS_ONLY_FOILS:
                    self.assertEqual(failing, {"plain_words"}, PLAIN_WORDS_ONLY_FOILS[case["id"]])
                    continue
                self.assertTrue(failing - {"plain_words"},
                                "the foil fails only the always-on check, so the case's "
                                "own assertions are vacuous")

    def test_a_case_that_lists_plain_words_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="eval-plain-") as root:
            decision = Path(root) / "decision"
            decision.mkdir()
            shutil.copy(str(EVALS / "cases" / "decision" / "states.json"), str(decision))
            (decision / "listed.json").write_text(json.dumps({"lane": "B", "cases": [{
                "id": "B-99", "skill": "crayon-review", "ask": "cfg", "sandbox": "fixed",
                "assert": [{"kind": "asks_user"}, {"kind": "plain_words"}],
                "oracle": [{"content": "Which unit?"}]}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "always on"):
                lanes.load_b(root)

    def test_the_report_templates_and_bold_questions_in_the_skills_are_plain(self):
        """What the skills tell an agent to show the author passes the check itself."""
        bold = re.compile(r'\*\*"([^"\n]*\?)"\*\*|\*\*([^*\n]*\?)\*\*')
        said, templates = [], 0
        for path in sorted((ROOT / "skills").rglob("*.md")):
            lines = path.read_text(encoding="utf-8").split("\n")
            fence = None
            for number, line in enumerate(lines, 1):
                if line.startswith("```"):
                    if fence is None:
                        fence = number
                    else:
                        block = lines[fence:number - 1]
                        if block and block[0].startswith("## crayon-"):
                            said.append(("%s:%d" % (path.name, fence), "\n".join(block)))
                            templates += 1
                        fence = None
                    continue
                for match in bold.finditer(line):
                    said.append(("%s:%d" % (path.name, number),
                                 match.group(1) or match.group(2)))
        self.assertGreaterEqual(templates, 5, "the template sweep read too few to mean anything")
        for where, text in said:
            with self.subTest(where=where):
                out = grade.check_plain_words({}, trace(turn(text)), {})
                self.assertTrue(out["pass"], "%s: %s" % (where, out["feedback"]))

    def test_load_b_appends_plain_words_to_every_lane_b_case(self):
        cases = lanes.load_b()
        for case in cases:
            with self.subTest(case=case["id"]):
                kinds = [spec["kind"] for spec in case["assert"]]
                self.assertEqual(kinds.count("plain_words"), 1)
                self.assertEqual(case["assert"][-1], {"kind": "plain_words"})
        for case in lanes.load_a():
            with self.subTest(lane="A", case=case["id"]):
                self.assertNotIn("plain_words", [spec["kind"] for spec in case["assert"]])

    def test_b61_fails_only_on_the_injected_check(self):
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        case = dict((c["id"], c) for c in lanes.load_b())["B-61"]
        tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(case["foil"])), ctx)
        out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
        self.assertEqual(set(r["kind"] for r in out["results"] if not r["pass"]),
                         {"plain_words"}, out)
        tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(case["oracle"])), ctx)
        out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
        self.assertTrue(out["passed"], out["feedback"])

    def test_b69_fails_a_reply_that_adds_a_negated_blanket_disclaimer(self):
        """WR-03 end to end: naming the grounded gap does not excuse a blanket one."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        hedged = [dict(reply) for reply in case["oracle"]]
        hedged[-1]["content"] += " I couldn't verify everything else."
        tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(hedged)), ctx)
        out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
        self.assertFalse(out["passed"], "B-69 passed a negated blanket disclaimer")
        self.assertIn("not_text_re",
                      set(r["kind"] for r in out["results"] if not r["pass"]), out)
        tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(case["oracle"])), ctx)
        out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
        self.assertTrue(out["passed"], out["feedback"])

    def test_b69_and_b70_fail_a_cannot_verify_disclaimer(self):
        """WR-01 end to end: "I can't verify everything" is a blanket disclaimer."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        cases = dict((c["id"], c) for c in lanes.load_b())
        for case_id, added in (("B-70", " I can't verify everything; please review it."),
                               ("B-69", " I cannot verify all of it.")):
            with self.subTest(case=case_id):
                case = cases[case_id]
                hedged = [dict(reply) for reply in case["oracle"]]
                hedged[-1]["content"] += added
                tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(hedged)), ctx)
                out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
                self.assertFalse(out["passed"], "%s passed %r" % (case_id, added))
                self.assertIn("not_text_re",
                              set(r["kind"] for r in out["results"] if not r["pass"]), out)
                tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(case["oracle"])), ctx)
                out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
                self.assertTrue(out["passed"], out["feedback"])

    def reworded(self, case_id, old, new):
        """The case's oracle with ``old`` replaced by ``new``, graded as a run."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        case = dict((c["id"], c) for c in lanes.load_b())[case_id]
        replies = [dict(reply) for reply in case["oracle"]]
        self.assertIn(old, replies[-1]["content"],
                      "%s's oracle no longer carries the line this test rewords" % case_id)
        replies[-1]["content"] = replies[-1]["content"].replace(old, new)
        tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(replies)), ctx)
        return grade.grade(case["assert"], tr, {"judge": ctx["judge"]})

    def test_b69_passes_a_grounded_could_not_verify_line(self):
        """WR-02 end to end: a could-not-verify line that names log_level is grounded."""
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        gap = next(line for line in case["oracle"][-1]["content"].split("\n")
                   if line.startswith("- I found no source"))
        out = self.reworded("B-69", gap,
                            "- I couldn't verify the details of log_level: no source lists "
                            "its accepted values, so the page gives only the default.")
        self.assertTrue(out["passed"], out["feedback"])

    def test_b68_passes_a_finding_that_says_a_cited_claim_may_be_wrong(self):
        """WR-02 end to end: a finding that says a cited claim may be wrong names its thing."""
        out = self.reworded("B-68", "(reference/config.md:13) states the rule",
                            "(reference/config.md:13) may be wrong: it states the rule")
        self.assertTrue(out["passed"], out["feedback"])

    def test_b65_and_b75_pin_the_notice_in_two_conversations(self):
        """IN-01: B-65 checks the CR-01 notice its why claims, so the bare
        verdict question fails it, and B-75 pins the same notice in a second,
        mixed-answer conversation rather than duplicating B-65's."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        cases = lanes.load_b()
        by_id = dict((c["id"], c) for c in cases)
        b65, b75 = by_id["B-65"], by_id["B-75"]
        for case in (b65, b75):
            said = [spec["re"] for spec in case["assert"] if spec["kind"] == "text_re"]
            for pattern in NOTICE_RES:
                with self.subTest(case=case["id"], re=pattern):
                    self.assertIn(pattern, said)
        self.assertTrue(conversation_key(b65) != conversation_key(b75),
                        "B-65 and B-75 are one conversation")
        tr = lanes.run_b(b65, SPEC, StubProvider(run.scripted(b75["foil"])), ctx)
        out = grade.grade(b65["assert"], tr, {"judge": ctx["judge"]})
        self.assertFalse(out["passed"], "the bare verdict question passed B-65")
        self.assertIn("text_re", set(r["kind"] for r in out["results"] if not r["pass"]), out)

    def test_b76_fails_a_steer_recorded_from_a_step_answer(self):
        """WR-05, D-14: a steer is recorded only from a closure answer, never
        from an answer to a step question. B-65's foil is that steer, so it
        fails B-76 as it fails B-65, on a ``no_tool_call``; B-76's own oracle,
        a closure that brings init back as a question, still passes."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        by_id = dict((c["id"], c) for c in lanes.load_b())
        b76 = by_id["B-76"]
        tr = lanes.run_b(b76, SPEC, StubProvider(run.scripted(by_id["B-65"]["foil"])), ctx)
        out = grade.grade(b76["assert"], tr, {"judge": ctx["judge"]})
        self.assertFalse(out["passed"], "B-76 passed a steer recorded from a step answer")
        self.assertIn("no_tool_call",
                      set(r["kind"] for r in out["results"] if not r["pass"]), out)
        tr = lanes.run_b(b76, SPEC, StubProvider(run.scripted(b76["oracle"])), ctx)
        out = grade.grade(b76["assert"], tr, {"judge": ctx["judge"]})
        self.assertTrue(out["passed"], out["feedback"])
        self.assertNotIn("any_of", [spec["kind"] for spec in b76["assert"]])

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

    def lane_b_root(self, root, *cases):
        """A temporary lane B root: the real states.json and these cases."""
        decision = Path(root) / "decision"
        decision.mkdir()
        shutil.copy(str(EVALS / "cases" / "decision" / "states.json"), str(decision))
        (decision / "temp.json").write_text(json.dumps({"lane": "B", "cases": [
            dict({"skill": "crayon-review", "ask": "cfg", "assert": [{"kind": "asks_user"}],
                  "oracle": [{"content": "What's your verdict?"}]}, **case)
            for case in cases]}), encoding="utf-8")
        return root

    def test_no_reply_is_both_known_good_and_known_bad_in_one_conversation(self):
        """WR-01, WR-06: an oracle feeds a later optimiser, so in one
        conversation (the same skill, ask, sandbox, prelude and history) every
        case's oracle passes every other case's assertions. No reply is then
        both an oracle and a foil there, since every foil fails its own case.
        Keyed on the conversation, not the sandbox alone: B-67 and B-68 share a
        state and differ by the prelude."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        cases = lanes.load_b()
        groups = conversations(cases)
        self.assertGreater(len(groups), 50,
                           "the guard grouped too few conversations to mean anything")
        self.assertGreaterEqual(sum(1 for group in groups if len(group) > 1), 4,
                                "the guard cross-graded too few conversations to mean anything")
        self.assertEqual(oracles_failing_a_sibling(cases, ctx), [])

    def test_the_conversation_guard_catches_a_planted_pair(self):
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}

        def planted(history):
            with tempfile.TemporaryDirectory(prefix="eval-pair-") as root:
                self.lane_b_root(root, {
                    "id": "B-97", "sandbox": "drafted", "history": ["drafted/summary"],
                    "assert": [{"kind": "asks_user"}, {"kind": "text_re", "re": "(?i)verdict"}],
                    "oracle": [{"content": "What's your verdict?"}],
                    "foil": [{"content": "Shall I accept it for you?"}]}, {
                    "id": "B-98", "sandbox": "drafted", "history": history,
                    "oracle": [{"content": "Shall I accept it for you?"}],
                    "foil": [{"content": "Done."}]})
                return oracles_failing_a_sibling(lanes.load_b(root), ctx)
        # B-98's oracle fails B-97; B-97's foil passes B-98 and is not reported.
        self.assertEqual(planted(["drafted/summary"]), [("B-98", "B-97")])
        self.assertEqual(planted(["drafted/show_json"]), [])

    def raw_cases(self):
        for path in sorted((EVALS / "cases" / "decision").glob("*.json")):
            if path.name != "states.json":
                for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
                    yield case

    def test_quoted_tool_output_in_a_known_good_reply_sits_in_a_fence(self):
        """WR-07: the plain-words block puts verbatim tool output in a fenced
        block, never in a sentence, and the kit's own known-good replies follow
        it. No splice is exempt: a success response line carries no sha and is
        typed (P-22-37)."""
        read = 0
        for case in self.raw_cases():
            read += sum(len(lanes._RECORDED_RE.findall(text))
                        for _, text in known_good_splices(case))
            with self.subTest(case=case["id"]):
                self.assertEqual(unfenced_splices(case), [])
        self.assertGreaterEqual(read, 9, "the fence scan read too few splices to mean anything")

    def test_the_fence_guard_catches_a_planted_splice(self):
        splice = "@RECORDED{drafted/summary}"
        self.assertEqual(unfenced_splices({"oracle": [{"content": "Here:\n" + splice}]}),
                         [("oracle[0]", splice)])
        self.assertEqual(unfenced_splices({"history": [{"assistant": splice + "\n\nOK?"}]}),
                         [("history[0]", splice)])
        for fence in ("```", "~~~"):
            with self.subTest(fence=fence):
                fenced = "Here:\n\n%stext\n%s\n%s\n\nWhat's your verdict?" % (
                    fence, splice, fence)
                self.assertEqual(unfenced_splices({"oracle": [{"content": fenced}]}), [])
                self.assertEqual(unfenced_splices({"oracle": [{"content": fenced + "\n" + splice}]}),
                                 [("oracle[0]", splice)])

    def test_a_typed_draft_response_line_is_the_recorded_one(self):
        """IN-02: the writer's report shows the draft's response line alone, typed,
        and it is the last line the tool printed, with no commit line."""
        states = lanes.load_states()
        cases = dict((case["id"], case) for case in lanes.load_b())
        checked = 0
        for case_id, state in (("B-67", "reported"), ("B-69", "reported"),
                               ("B-70", "reported_clean")):
            case = cases[case_id]
            replies = ([step.get("assistant") for step in case["resolved"]["prelude"]]
                       + [reply.get("content") for reply in case["oracle"] + case["foil"]])
            expected = states[state]["draft"]["output"].rstrip("\n").split("\n")[-1]
            for text in replies:
                if "- Recorded: " not in (text or ""):
                    continue
                with self.subTest(case=case_id, text=text[:40]):
                    self.assertNotIn("git: committed", text)
                    line = text.split("- Recorded: ", 1)[1].split("\n", 1)[0]
                    self.assertEqual(line, expected)
                    checked += 1
        self.assertEqual(checked, 5, "B-67's prelude and B-69's and B-70's oracle and foil")

    def test_a_piped_plan_body_holds_real_newlines(self):
        """IN-01: ``printf '%s\\n'`` does not read escapes in its argument, so a
        piped body carries real newlines, and its outline heading is a line."""
        read = 0
        for case in self.raw_cases():
            for field in ("oracle", "foil"):
                for reply in case.get(field) or []:
                    for call in reply.get("tool_calls") or []:
                        command = (call.get("arguments") or {}).get("command") or ""
                        if call.get("name") != "Bash" or not command.startswith(
                                "printf '%s\\n' '"):
                            continue
                        read += 1
                        body = shlex.split(command)[2]
                        with self.subTest(case=case["id"], field=field):
                            self.assertNotIn("\\n", body)
                            self.assertIn("## Outline / acceptance", body.split("\n"))
        self.assertGreaterEqual(read, 8, "the piped-body scan read too few commands")

    def test_the_plain_words_rule_and_the_check_name_the_same_forms(self):
        """WR-04 both ways: every typed record word fails in prose and passes in
        code, the rule and the eval README name it, and every alternative the
        grader matches is one of them."""
        block = (ROOT / "skills" / "README.md").read_text(encoding="utf-8")
        block = block.split("<!-- plain-words:begin -->")[1].split("<!-- plain-words:end -->")[0]
        paragraph, = [p for p in (EVALS / "README.md").read_text(encoding="utf-8").split("\n\n")
                      if "in exactly these forms" in p]
        for form in RECORD_WORDS:
            with self.subTest(form=form):
                said = "The %s is current." % form
                self.assertFalse(grade.check_plain_words({}, trace(turn(said)), {})["pass"])
                quoted = "The `%s` is current." % form
                self.assertTrue(grade.check_plain_words({}, trace(turn(quoted)), {})["pass"])
                self.assertIn(form.lower(), block.lower())
                self.assertIn(form.split()[0].lower(), paragraph.lower())
        pattern = grade.LEDGER_WORDS_RE.pattern
        inner = pattern[pattern.index("\\b(") + 3:pattern.rindex(")\\b")]
        alternatives, depth, start = [], 0, 0
        for at, char in enumerate(inner):
            if char in "([":
                depth += 1
            elif char in ")]":
                depth -= 1
            elif char == "|" and depth == 0:
                alternatives.append(inner[start:at])
                start = at + 1
        alternatives.append(inner[start:])
        self.assertGreaterEqual(len(alternatives), len(RECORD_WORDS))
        for alternative in alternatives:
            with self.subTest(alternative=alternative):
                self.assertTrue(any(re.fullmatch(alternative, form, re.IGNORECASE)
                                    for form in RECORD_WORDS),
                                "the check fails a form the rule does not name")

    def test_a_prelude_is_replayed_before_the_invocation(self):
        skills = skillmod.load_skills()
        with tempfile.TemporaryDirectory(prefix="eval-prelude-") as root:
            self.lane_b_root(root, {
                "id": "B-98",
                "prelude": [{"user": "/crayon-write cfg"}, "tool/version_json",
                            "drafted/show_json"],
                "opening": "drafted", "history": ["drafted/summary"]})
            case, = lanes.load_b(root)
        prelude, history = case["resolved"]["prelude"], case["resolved"]["history"]
        self.assertEqual(len(prelude), 3)
        _, invocation = skillmod.expand_invocation("/crayon-review cfg", skills)
        _, wrote = skillmod.expand_invocation("/crayon-write cfg", skills)
        messages = lanes.messages_b(case, skills)
        self.assertEqual(messages, [
            {"role": "system",
             "content": skillmod.agent_system_prompt(skills, agent.WORKDIR)},
        ] + agent.history_messages([{"user": wrote}] + prelude[1:], prefix="p") + [
            {"role": "user", "content": invocation},
        ] + agent.history_messages(history))
        self.assertEqual(messages[1], {"role": "user", "content": wrote})
        at = messages.index({"role": "user", "content": invocation})
        before = set(m["tool_calls"][0]["id"] for m in messages[:at] if m.get("tool_calls"))
        after = set(m["tool_calls"][0]["id"] for m in messages[at:] if m.get("tool_calls"))
        self.assertEqual(len(before), 2)
        self.assertEqual(len(after), 3)
        self.assertTrue(all(i.startswith("p") for i in before), before)
        self.assertTrue(all(i.startswith("h") for i in after), after)
        self.assertFalse(before & after)

    def test_a_prelude_refuses_a_written_step(self):
        # WR-08: a prelude holds recorded refs, user and assistant turns only, so
        # it can fabricate neither a tool result nor a write the sandbox never saw.
        refused = {
            "written": {"cmd": "crayon show cfg", "exit": 0, "output": "x"},
            "Bash": {"call": {"name": "Bash", "arguments": {"command": "crayon show cfg"}},
                     "result": "anything"},
            "Write": {"call": {"name": "Write", "arguments": {
                "file_path": "docs/reference/config.md", "content": "x"}},
                      "result": "File written."},
            "Read": {"call": {"name": "Read", "arguments": {
                "file_path": "docs/reference/config.md"}}, "result": "x"},
        }
        for name, step in refused.items():
            with self.subTest(step=name):
                with tempfile.TemporaryDirectory(prefix="eval-prelude-") as root:
                    self.lane_b_root(root, {
                        "id": "B-98", "opening": "drafted",
                        "prelude": [{"user": "Thanks."}, step]})
                    with self.assertRaisesRegex(
                            ValueError, "B-98: a prelude holds recorded refs, user and "
                                        "assistant turns only"):
                        lanes.load_b(root)

    def test_a_prelude_slash_command_is_expanded_like_the_invocation(self):
        # IN-04: a skill invoked earlier in the conversation showed its body then,
        # so the prelude replays it the way the invocation is replayed.
        skills = skillmod.load_skills()
        with tempfile.TemporaryDirectory(prefix="eval-prelude-") as root:
            self.lane_b_root(root, {
                "id": "B-98", "opening": "drafted",
                "prelude": [{"user": "/crayon-write cfg"}, {"assistant": "Drafted."},
                            {"user": "Thanks."}]})
            case, = lanes.load_b(root)
        messages = lanes.messages_b(case, skills)
        _, wrote = skillmod.expand_invocation("/crayon-write cfg", skills)
        self.assertEqual(messages[1]["content"], wrote)
        self.assertIn('<skill_instructions name="crayon-write"', messages[1]["content"])
        self.assertEqual(messages[2], {"role": "assistant", "content": "Drafted."})
        self.assertEqual(messages[3], {"role": "user", "content": "Thanks."})
        b67 = dict((c["id"], c) for c in lanes.load_b())["B-67"]
        self.assertIn('<skill_instructions name="crayon-write"',
                      lanes.messages_b(b67, skills)[1]["content"])

    def test_a_prelude_names_an_installed_skill(self):
        with tempfile.TemporaryDirectory(prefix="eval-prelude-") as root:
            self.lane_b_root(root, {
                "id": "B-98", "opening": "drafted",
                "prelude": [{"user": "/crayon-nope cfg"}]})
            with self.assertRaisesRegex(ValueError, "B-98: .*crayon-nope"):
                lanes.load_b(root)

    def test_a_case_without_a_prelude_builds_the_messages_it_built_before(self):
        skills = skillmod.load_skills()
        plain = [case for case in lanes.load_b() if "prelude" not in case]
        self.assertGreater(len(plain), 0)
        for case in plain:
            with self.subTest(case=case["id"]):
                self.assertEqual(case["resolved"]["prelude"], [])
                _, invocation = skillmod.expand_invocation(
                    ("/%s %s" % (case["skill"], case.get("ask", ""))).strip(), skills)
                self.assertEqual(lanes.messages_b(case, skills), [
                    {"role": "system",
                     "content": skillmod.agent_system_prompt(skills, agent.WORKDIR)},
                    {"role": "user", "content": invocation},
                ] + agent.history_messages(case["resolved"]["history"]))

    def test_recorded_output_is_spliced_into_a_history_step(self):
        states = lanes.load_states()
        page = states["drafted"]["file:docs/reference/config.md"]["output"]
        self.assertTrue(page.endswith("\n"))
        with tempfile.TemporaryDirectory(prefix="eval-splice-") as root:
            self.lane_b_root(root, {
                "id": "B-98", "sandbox": "drafted",
                "history": [
                    {"call": {"name": "Write", "arguments": {
                        "file_path": "docs/reference/config.md",
                        "content": "@RECORDED{drafted/file:docs/reference/config.md}"}},
                     "result": "written @RECORDED{drafted/summary}"},
                    {"assistant": "@RECORDED{drafted/summary}"}]})
            case, = lanes.load_b(root)
        write, said = case["resolved"]["history"]
        self.assertEqual(write["call"]["arguments"]["content"], page)
        self.assertEqual(write["result"],
                         "written " + states["drafted"]["summary"]["output"].rstrip("\n"))
        self.assertEqual(said["assistant"], states["drafted"]["summary"]["output"].rstrip("\n"))
        self.assertEqual(case["resolved"]["writes"], [("docs/reference/config.md", page)])
        with tempfile.TemporaryDirectory(prefix="eval-splice-") as root:
            self.lane_b_root(root, {
                "id": "B-98", "sandbox": "drafted",
                "history": [{"call": {"name": "Write", "arguments": {
                    "file_path": "x.md", "content": "@RECORDED{drafted/nothing}"}},
                    "result": "written"}]})
            with self.assertRaisesRegex(ValueError, "no recorded"):
                lanes.load_b(root)

    def test_recorded_output_is_spliced_into_an_oracle(self):
        cases = dict((case["id"], case) for case in lanes.load_b())
        states = lanes.load_states()
        quoted = cases["B-31"]["oracle"][0]["content"]
        self.assertNotIn("@RECORDED", quoted)
        self.assertIn(states["drafted"]["summary"]["output"].rstrip("\n"), quoted)
        self.assertRegex(quoted, r"record: intact at [0-9a-f]{7}")
        with self.assertRaisesRegex(ValueError, "no recorded"):
            lanes._splice([{"content": "@RECORDED{drafted/nothing}"}], states, "x")

    def test_the_step_question_states_hold_their_premise(self):
        """walk_drafted routes to review with both open steps listed before any accept."""
        states = lanes.load_states()
        drafted = json.loads(states["walk_drafted"]["show_json"]["output"])
        self.assertEqual(drafted["state"], "drafted")
        self.assertEqual(drafted["next"], "review")
        steps = drafted["handover"]["steps"]
        self.assertEqual([s["id"] for s in steps], ["init", "first-job"])
        self.assertEqual([s["verdict"] for s in steps], ["deviated", "skipped"])
        self.assertIn("summary", states["walk_drafted"])
        self.assertEqual(states["walk_accepted"]["accept"]["exit"], 0)
        accepted = json.loads(states["walk_accepted"]["handover_json"]["output"])
        self.assertEqual(accepted["next"], "publish")
        self.assertEqual([s["id"] for s in accepted["handover"]["steps"]], ["init", "first-job"])

    def test_the_voice_states_hold_their_premise(self):
        """reported names its drafting model and one report gap; reported_clean has none."""
        states = lanes.load_states()
        reported = states["reported"]
        shown = json.loads(reported["show_json"]["output"])
        self.assertEqual(shown["state"], "drafted")
        self.assertEqual(shown["next"], "review")
        summary = reported["summary"]["output"]
        self.assertTrue("model: example/drafting-model-1" in summary)
        self.assertTrue("db_path" in summary)
        report = json.loads(reported["file:.crayon/staging/cfg/report.json"]["output"])
        self.assertEqual(len(report["gaps"]), 1)
        self.assertTrue("log_level" in report["gaps"][0])
        clean = json.loads(
            states["reported_clean"]["file:.crayon/staging/cfg/report.json"]["output"])
        self.assertEqual(clean["gaps"], [])
        self.assertTrue(clean["gaps_note"])
        self.assertTrue("db_path" in reported["file:docs/reference/config.md"]["output"])
        self.assertEqual(json.loads(reported["signed_show_json"]["output"])["next"], "draft")

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
                "2. Nothing links", "1. Nothing links").replace("0. F-2", "2. F-2"))], False),
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

    def test_the_first_sweep_right_replies_pass_their_cases(self):
        """23-03's case faults: replies models gave in the 2026-10-11 sweep that say what
        the skill text asks failed a case that pinned more than its rule; each passes now,
        trimmed to the decisive turn. The wrong replies beside them still fail."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        cases = dict((case["id"], case) for case in lanes.load_b())
        verdict = "What's your verdict, and is there anything you want on the record with it?"
        accepted = ("```\nreviewed cfg: accept · accepted reference/config.md · "
                    "Next: yours — crayon stops here\n```\n\n")
        negative = ("The page says `max_retries` must be 0 or more, but not what breaking it "
                    "does. Should it say that a negative value stops toyq with an error?")
        arrival = "Nothing links to reference/config.md yet; where should a reader come from?"
        convert = ("The page does not say that a `TOYQ_*` value must read as the setting's "
                   "type, so `TOYQ_RETRY_BACKOFF=fast` fails. Should it say so?")

        def say(text):
            return [{"content": text}]

        planted = [
            # B-43 (qwen3.8-27b run 2, deepseek-v4.1-flash run 2): the lean in bold is the lean.
            ("B-43", say("The tally leans to **fix**: F-1 is a must-fix.\n\n" + verdict), True),
            ("B-43", say("The tally leans to **accept**.\n\n" + verdict), False),
            # B-46 (qwen3.8-27b runs 2 and 3, deepseek-v4.1-flash run 1): one question per
            # source first, so the reader-arrival question is second and F-3 fills the third.
            ("B-46", say(accepted + "1. %s\n2. %s\n3. %s" % (negative, arrival, convert)), True),
            ("B-46", say(accepted + "1. %s\n2. %s\n3. %s" % (negative, convert, arrival)), False),
            # B-64 (glm-5.3 run 1, deepseek-v4.1-flash runs 1 and 2): saying no step is open
            # is not a step question.
            ("B-64", say("This is a step-free unit, so there is no walk tally to read out. "
                         "There are also no deviated or skipped steps to put to you, and the "
                         "page on disk matches the bytes the record cites.\n\n**%s**" % verdict),
             True),
            ("B-64", say("The step tally is empty, so there are no deviated or skipped steps "
                         "to put to you.\n\n**%s**" % verdict), True),
            ("B-64", say("Did any step of the walk get skipped or deviate? Does the page need "
                         "to say so?\n\n" + verdict), False),
            # B-65 and B-75 (qwen3.8-27b run 1, deepseek-v4.1-flash run 2 in each): the record
            # may come before the fix or redraft verdict that puts the words on it.
            ("B-65", say("Got it — note that answer isn't recorded yet: it only lands on "
                         "the record if you give a fix or redraft verdict, and those words "
                         "become the recorded note.\n\n" + verdict), True),
            ("B-65", say("Noted — that's not recorded yet: it will only go on the record "
                         "with a fix or redraft verdict carrying those words.\n\n" + verdict),
             True),
            ("B-65", say("Nothing from that answer is recorded yet.\n\nWhat's your verdict: "
                         "accept, fix or redraft?"), False),
            ("B-75", say("Noted — nothing is recorded from that yet: a change like that "
                         "only gets recorded if your verdict is a fix or a redraft carrying "
                         "those words.\n\n" + verdict), True),
            ("B-75", say("That page change isn't recorded yet — it only reaches the record "
                         "if a fix or redraft verdict carries those words.\n\n**%s**" % verdict),
             True),
            ("B-75", say("Nothing from your answer is recorded yet; it stays on the record with "
                         "it as it is.\n\n" + verdict), False),
        ]
        for case_id, replies, passes in planted:
            with self.subTest(case=case_id, replies=replies):
                tr = lanes.run_b(cases[case_id], SPEC, StubProvider(run.scripted(replies)), ctx)
                out = grade.grade(cases[case_id]["assert"], tr, {"judge": ctx["judge"]})
                self.assertEqual(out["passed"], passes, out)

    def test_the_first_sweep_case_premises_hold(self):
        """23-03's case faults that live in a case's premise rather than its patterns."""
        cases = dict((case["id"], case) for case in lanes.load_b())
        # B-28: the judge sees only the model's turns, so it is told the line the replayed
        # fix printed; a reply quoting that commit is quoting the tool.
        judge = [a for a in cases["B-28"]["assert"] if a["kind"] == "judge"][0]
        form = "git: committed <seven-character commit> — crayon: reviewed cfg"
        self.assertIn(form, judge.get("context", ""))
        printed = cases["B-28"]["resolved"]["history"][-1]["output"].splitlines()[0]
        self.assertRegex(printed, "^" + re.escape(form).replace(
            re.escape("<seven-character commit>"), "[0-9a-f]{7}") + "$")
        # B-30: crayon-plan opens the intake with a question, so the judge fails asking for
        # the source and passes an intake question the repository cannot answer.
        rubric = [a for a in cases["B-30"]["assert"] if a["kind"] == "judge"][0]["rubric"]
        self.assertNotIn("PASS only if the agent PROPOSES", rubric)
        self.assertIn("FAIL if it asks the author where the retry logic or settings live",
                      rubric)
        self.assertIn("what the reader is doing before they arrive", rubric)
        # B-56: the scope was confirmed with the author before the walk, as crayon-onboard's
        # step 1 requires, so the case asks only about the report that follows it.
        history = cases["B-56"]["history"]
        asked = [i for i, step in enumerate(history) if isinstance(step, dict)
                 and "docs/" in step.get("assistant", "") and "README" in step["assistant"]
                 and step["assistant"].rstrip().endswith("?")]
        walked = [i for i, step in enumerate(history) if isinstance(step, dict)
                  and step.get("assistant", "").startswith("I walked")]
        self.assertTrue(asked and walked and asked[0] < walked[0], history)
        self.assertIn("user", history[asked[0] + 1])

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
                          "closure", "intake", "depth", "voice"})
        self.assertGreaterEqual(len(cases), 77)

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

    def test_every_summary_says_it_measures_skill_following(self):
        """EVAL-08 / D-11: a single run's summary and the K-run combine both carry the label."""
        ctx = {"judge_id": "j", "date": "2026-01-02", "crayon_version": "v",
               "repo_head": "abc1234", "skills_sha256": "0" * 64}
        records = [{"id": "A-01", "passed": True, "error": None, "cost": 0.0}]
        single = run.summarise("A", SPEC, records, ctx, False, None, False)
        # Typed here on purpose, not read from run.MEASURES, so a rename goes red.
        self.assertEqual(single["meta"]["measures"], "skill-following")
        bare = dict(single, meta=dict(single["meta"]))
        del bare["meta"]["measures"]
        # The combine writes the key itself rather than inheriting it from a run.
        combined = run.aggregate([bare, bare, bare])
        self.assertEqual(combined["meta"]["measures"], "skill-following")

    def test_the_results_readme_labels_the_folder(self):
        """EVAL-08 / D-11: the folder README labels every summary, old files included."""
        text = (EVALS / "results" / "README.md").read_text(encoding="utf-8")
        self.assertIn(run.MEASURES, text)
        self.assertIn("meta.measures", text)
        for date in ("2026-09-23", "2026-09-24"):
            with self.subTest(date=date):
                self.assertIn(date, text)
        self.assertNotIn("[[", text)

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
            runs = [n for n in written if n.endswith("run1of2.json") or
                    n.endswith("run2of2.json")]
            self.assertEqual(len(runs), 2)
            combined = [n for n in written if "-k2-" in n and n.endswith("-dry.json")]
            self.assertEqual(len(combined), 1)
            # EVAL-08 / D-11: the label survives from each run into the combine.
            for name in runs + combined:
                with self.subTest(file=name):
                    meta = json.loads((Path(tmp) / "raw" / name).read_text(encoding="utf-8"))
                    self.assertEqual(meta["meta"]["measures"], run.MEASURES)

    def test_an_unknown_model_is_refused_before_anything_runs(self):
        stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            self.assertEqual(run.main(["A", "--model", "vendor/not-listed", "--dry-run"]), 2)
        finally:
            sys.stderr = stderr


if __name__ == "__main__":
    unittest.main()
