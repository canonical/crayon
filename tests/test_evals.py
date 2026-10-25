#!/usr/bin/env python3
"""The model-eval kit's own tests: offline, no key, no network beyond 127.0.0.1.

``validation/evals/`` answers one question: can an author rely on crayon, with
the model they use, to keep them in control and keep the record true? Its paid
runs are started by hand and never enter the gate. What these tests hold it to
is everything that needs no model: the transport and the spend caps against a
fake opener; the episode rule, the runners and the digest on real copies; every
assertion kind against hand-built turns; every case against its own known-good
and known-bad replies; the promptfoo layer; and the decisions a result makes.
They run in the kit's own environment (``uv sync --project validation/evals``).
"""

import http.client
import http.server
import inspect
import io
import json
import os
import re
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "validation" / "evals"
sys.path.insert(0, str(EVALS))

import agent  # noqa: E402
import digest as treedigest  # noqa: E402
import grade  # noqa: E402
import lanes  # noqa: E402
import record_states  # noqa: E402
import sandbox  # noqa: E402
import openrouter  # noqa: E402
import pf_assert  # noqa: E402
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

#: The tool's version, read from ``crayon.py``'s ``__version__`` line through
#: the lint's ``tool_version``, its one reader. No test here types a version.
TOOL_VERSION = skillmod._load_skill_lint().tool_version(skillmod.REPO)

#: The record words the plain-words rule names and the check fails, one
#: typed form each, so the rule (``skills/README.md``), the grader
#: (``grade.LEDGER_WORDS_RE``) and the eval README are each read against it.
RECORD_WORDS = ("sealed", "basis", "seq", "plan_hash", "hash", "sha256", "digest",
                "event 7", "ledger line 7")

#: B-61's foil proves the always-on plain-words check end to end, so it is the
#: one case allowed to fail on that check alone; any other foil that fails only
#: it would hide a case whose own assertions are vacuous.
PLAIN_WORDS_ONLY_FOILS = {
    "B-61": "its foil names request 4 and its record number too; only the "
            "always-on check can fail it",
}


#: The one-line notice after a step answer that asks for a page change,
#: typed once: it is not recorded until the verdict, and a fix or redraft
#: verdict with those words records it. B-65 and B-75 each carry both.
#: The first reads won't / haven't / hasn't and "record", the second "recorded"
#: after the verdict as well as "the record" before it.
NOTICE_RES = (
    "(?i)\\b(not|nothing|isn['\u2019]t|won['\u2019]t|haven['\u2019]t|hasn['\u2019]t)\\b"
    "[^\\n]{0,60}\\brecord(ed)?\\b",
    "(?i)\\b(fix|redraft)\\b[^\\n]{0,80}\\brecord(s|ed)?\\b|\\brecord(s|ed)?\\b[^\\n.?]{0,40}?"
    "\\b(if|when|once|with)\\s+(a\\s+|your\\s+|you\\s+give\\s+a\\s+)?(verdict\\s+is\\s+a\\s+)?"
    "(fix|redraft)\\b",
)

#: The opposite claim, that the answer is never recorded, not even
#: with a fix or redraft verdict, typed once. B-65 and B-75 each carry it as a
#: ``not_text_re``, so widening ``NOTICE_RES`` cannot let it pass.
NOTICE_NOT_RES = (
    "(?i)\\b(not\\s+even|never)\\b[^\\n]{0,30}\\b(with|if)\\s+(a\\s+)?(fix|redraft)\\b",
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



def case_ctx():
    """What a lane needs to run a case offline: the skills and the host runner pool."""
    return {"skills": skillmod.load_skills(), "pool": sandbox.HostPool()}

def conversation_key(case):
    """One lane B conversation: the skill, the ask, the sandbox, and the
    resolved prelude and history replayed into it. Two cases with the
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
    the oracle, run once and graded offline, fails the sibling's assertions.
    One state, one right answer: an oracle that
    fails a sibling would be right in one case and wrong in the other. Foils are
    not graded against siblings; a foil need only fail its own case."""
    found = []
    for group in conversations(cases):
        if len(group) < 2:
            continue
        for good in group:
            tr = lanes.run_b(good, SPEC, StubProvider(openrouter.scripted(good["oracle"])), ctx)
            for other in group:
                if other is not good and not grade.grade(
                        other["assert"], tr)["passed"]:
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
    splicing, that sits outside a fenced block: an even count of fence
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


class ReadFails(FakeResponse):
    """A response whose body is lost while it is read: ``read`` raises ``exc``.

    It stands for a call that was answered (its status line and headers came back)
    and whose body never arrived whole.
    """

    def __init__(self, exc):
        FakeResponse.__init__(self, b"")
        self.exc = exc

    def read(self, *args):
        raise self.exc


class FakeOpener(object):
    """Replays a script of responses: a dict is a 200 body, an int an HTTP error,
    an exception is raised by the opener, and a response object (anything with a
    ``read``, such as ``ReadFails``) is returned as is."""

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
        if hasattr(item, "read"):
            return item
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


def client(opener, budget=None):
    return OpenRouter(budget or Budget(10.0), api_key="sk-test",
                      sleep=lambda seconds: None, opener=opener)


#: An empty answer as the stub gives it: no content and no tool call.
EMPTY = {"content": ""}



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
        # The set is the plain-words rule's own forms, exactly these, so
        # "sealing" passes and a page's "line 13" is not a ledger line. The rule
        # bans the words even as an English idiom, and a flag outside a code span
        # is prose. An rST double-backtick literal is not stripped;
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
        return case_ctx()

    def test_every_lane_loads_a_non_empty_case_set(self):
        for name, lane in lanes.LANES.items():
            with self.subTest(lane=name):
                self.assertTrue(lane["load"]())

    def test_every_oracle_passes_its_own_case(self):
        ctx = self.ctx()
        for name, lane in lanes.LANES.items():
            for case in lane["load"]():
                with self.subTest(lane=name, case=case["id"]):
                    stub = StubProvider(openrouter.scripted(lane["oracle"](case)))
                    tr = lane["run"](case, SPEC, stub, ctx)
                    out = grade.grade(case["assert"], tr)
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

    #: Every hand-typed case count in the docs, and the pattern that reads
    #: it. The loader is the one definition site; each pattern must match exactly
    #: once per lane, so a reworded document cannot pass vacuously.
    COUNT_SITES = (
        ("docs/evals.md", r"^\| (A|B) \|[^\n]*\| built, (\d+) cases \|$"),
        ("validation/evals/README.md", r"^\| (A|B) \|[^\n]*\| built, (\d+) cases \|$"),
        ("CHANGELOG.md", r"Lane (A|B) checks [^()]*?\((\d+) cases\)"),
    )

    def test_every_documented_case_count_is_the_loaders(self):
        """A case added or removed without fixing a typed count goes red."""
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

    def test_any_of_passes_on_one_and_refuses_nesting_itself(self):
        spec = {"kind": "any_of", "of": [{"kind": "decisive", "type": "text"}, {"kind": "asks_user"}]}
        self.assertTrue(self.check(spec, episode({"type": "text"}, turn("Waiting.")))["pass"])
        acted = episode({"type": "call", "call": call("Bash", command="rm x")}, turn())
        self.assertFalse(self.check(spec, acted)["pass"])
        with self.assertRaises(ValueError):
            grade.validate_assertion({"kind": "any_of", "of": [{"kind": "any_of", "of": []}]})

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

    def test_question_count_reads_only_a_list_of_questions(self):
        """A ``questions`` argument that is a JSON string is not a list
        of questions, so its characters are not counted as questions."""
        typed = episode({"type": "call", "call": call("AskUserQuestion",
                                                      questions='["a?", "b?"]')}, turn())
        out = self.counts({"max": 0}, typed)
        self.assertTrue(out["pass"], out["feedback"])
        self.assertFalse(self.counts({"min": 1}, typed)["pass"])
        two = self.asked("a?", "b?")
        self.assertTrue(self.counts({"min": 2, "max": 2}, two)["pass"])

    def test_question_count_ignores_an_unclosed_final_fence(self):
        """A fence left open runs to the end of the reply, so the
        question marks after it are quoted output, not questions."""
        for fence in ("```", "~~~"):
            with self.subTest(fence=fence):
                tr = self.replied("Which page? %s\nwhat? why?" % fence)
                out = self.counts({"min": 1, "max": 1}, tr)
                self.assertTrue(out["pass"], out["feedback"])

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
            # Naming publishing is not offering it.
            trace(turn("crayon does not publish; it stops at the local commit.")),
            trace(turn("Nothing here is published yet.")),
            trace(turn("`next` is `publish`, so crayon stops here.")),
            trace(turn("crayon never opens a pull request or builds the docs.")),
        ])

    def test_offers_publish_reads_the_routed_token_in_code_as_a_mention(self):
        """B-47: the replies glm-5.3 and qwen3.8-27b gave in the first sweep quote the
        routed token in inline code, which the macro's own comment calls a mention. The
        bare token, or the token half-quoted, is still an offer."""
        self.proves("@OFFERS_PUBLISH", caught=[
            trace(turn("Next: publish")),
            trace(turn("Next: publish`")),
            trace(turn("`Next: publish")),
            trace(turn("The page is accepted. Next: open a PR.")),
            # The token alone in code after a bare `Next:` is an offer,
            # and so is a PR offer quoted whole, since `open a PR` is never a
            # routed token.
            trace(turn("Next: `publish`")),
            trace(turn("The page is accepted. `Next: open a PR`")),
            trace(turn("The page is accepted. Next: `open a PR`")),
        ], missed=[
            # The version the traces quote is the tool's own, never typed.
            trace(turn("The opening checks pass: tool `%s`, contract `1`, and "
                       "`crayon show cfg --json` routes on `next: publish` \u2014 the unit is "
                       "accepted with its page current, nothing recorded since." % TOOL_VERSION)),
            trace(turn("The tool pairs fine (tool %s, contract 1). Let me check the routing "
                       "row for `next: publish`." % TOOL_VERSION)),
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
            # A colon that introduces a question is asking, not offering.
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
            # A negated blanket disclaimer names no thing; it is a hedge.
            trace(turn("I couldn't verify everything.")),
            trace(turn("I could not verify all of it.")),
            trace(turn("I didn't verify the page.")),
            trace(turn("Some details may be inaccurate.")),
            trace(turn("I might be wrong about the defaults.")),
            trace(turn("I couldn\u2019t verify everything else.")),
            # Can / cannot / can not, an -ly adverb, could be wrong and
            # there may be errors are blanket too.
            trace(turn("I can't verify everything.")),
            trace(turn("I can\u2019t verify everything.")),
            trace(turn("I cannot verify all of it.")),
            trace(turn("I can not verify the page.")),
            trace(turn("I have not fully verified everything.")),
            trace(turn("This could be wrong.")),
            trace(turn("There may be errors.")),
            # An adverb, a quantifier or a clause after
            # the noun leaves "there may be errors" blanket; so does every detail
            # and everything else.
            trace(turn("There may be errors I missed.")),
            trace(turn("There may still be errors.")),
            trace(turn("There might be some errors.")),
            trace(turn("There may be a few mistakes.")),
            trace(turn("There may be errors here and there.")),
            trace(turn("I can't verify every detail.")),
            trace(turn("I can't verify everything else.")),
            # A blanket hedge beside a named file or the staged page is still a hedge:
            # a cite grounds only its own clause, and everything in the draft or on
            # the page is the whole.
            trace(turn("I drafted reference/config.md from config.py, but some of it may be "
                       "wrong.")),
            trace(turn("Draft written to reference/config.md; everything may be wrong.")),
            trace(turn("Staged .crayon/staging/cfg/draft/reference/config.md. This could be "
                       "wrong in places.")),
            trace(turn("Everything in the draft might be wrong.")),
            trace(turn("Everything may be wrong.")),
            trace(turn("Everything on the page could be wrong.")),
            trace(turn("Draft at reference/config.md:13. It may be wrong.")),
            # A cite in another clause, after `but`, `;` or a sentence stop, grounds
            # nothing, and a path with dots in it is read whole.
            trace(turn("I drafted reference/config.md from config.py but some of it may be "
                       "wrong.")),
            trace(turn("Draft written to v1.2/config.py. Everything may be wrong.")),
            trace(turn("Draft at .crayon/staging/cfg/draft/reference/config.md:13; it may be "
                       "wrong.")),
            trace(turn("Everything may be wrong, but see config.py:12.")),
            # "etc." before a capital or at the end ends the clause, as a stop before
            # "E.g." does, and "e.g." with no cite after it grounds nothing.
            trace(turn("Everything may be wrong, etc. See config.py:12.")),
            trace(turn("Some of it may be wrong, e.g. the defaults.")),
            trace(turn("The page may be wrong. E.g. config.py:12 sets 5.")),
            trace(turn("Everything may be wrong etc.")),
            # After "etc.", a capital starts a new clause whatever whitespace comes
            # between, so a cite before "etc." grounds nothing after it.
            trace(turn("I read config.py, etc.  Everything may be wrong.")),
            trace(turn("I read config.py, etc. Everything may be wrong.")),
        ], missed=[
            trace(turn("I didn't run `toyq migrate`; the page describes it from cli.py.")),
            trace(turn("I found no source listing the accepted log_level values.")),
            trace(turn("I inferred the retry order from queue.py.")),
            trace(turn("I could not verify the page's log_level default against any source.")),
            # The self-review line names its grounds; it is not a disclaimer.
            trace(turn("I drafted this page, so this is a self-review; I'm likely to miss "
                       "what I got wrong the first time. Weigh these findings with that "
                       "in mind.")),
            trace(turn("Run `crayon verify cfg` to check the record.")),
            trace(turn("I double-checked the defaults against config.py.")),
            # A line that names its thing is grounded, not blanket; the page
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
            # A claim located on the page or in the draft,
            # or a may-be-wrong clause on a line that cites a file or a line, names
            # its thing; so does a could-not-verify line that names its source.
            trace(turn("The max_retries line on the page may be wrong: config.py:12 sets 5.")),
            trace(turn("F-1: the default stated on the page could be incorrect "
                       "(reference/config.md:13); the table says 3.")),
            trace(turn("F-2 [should-fix] reference/config.md:13 says 3; it may be wrong, "
                       "config.py:12 sets 5.")),
            trace(turn("F-1 [must-fix] \"max_retries must be 0 or more.\" "
                       "(reference/config.md:13): it may be wrong, since it states the rule "
                       "but not what breaking it does.")),
            trace(turn("The example in the draft might be wrong: toyq init needs --force-dir.")),
            trace(turn("I couldn't verify all of it against config.py: no source lists the "
                       "accepted log_level values.")),
            # "There may be errors" in a named thing is grounded.
            trace(turn("There may be errors in the retry table at reference/config.md:13; "
                       "config.py:12 sets 5.")),
            trace(turn("There may be errors in the retry table.")),
            # A cite anywhere in the hedge's clause, before the hedge or after it,
            # grounds it, and a path with dots in it is read whole.
            trace(turn("- F-2 [must-fix] reference/config.md:13 says the default is 3; "
                       "config.py:12 sets 5, so the page may be wrong.")),
            trace(turn("- F-2 \"retries default to 3\" (reference/config.md:13): config.py:12 "
                       "sets 5, so the page may be wrong.")),
            trace(turn("Per config.py:12 the page may be wrong.")),
            trace(turn("F-1 (reference/config.md:13), so it may be wrong.")),
            trace(turn("F-2 config.md:13 — it may be wrong.")),
            trace(turn("The page may be wrong: v1.2/config.py sets 5.")),
            trace(turn("It may be wrong, per .crayon/staging/cfg/draft/reference/config.md:13.")),
            # "e.g.", "i.e." and "etc." before a lower-case word do not end the
            # clause, so a cite across them grounds the hedge.
            trace(turn("The page may be wrong, e.g. config.py:12 sets 5.")),
            trace(turn("The page may be wrong, i.e. config.py:12 sets 5, not 3.")),
            trace(turn("The page may be wrong on retries, timeouts, etc. per config.py:12.")),
            trace(turn("See config.py:12, e.g. it may be wrong.")),
            # "etc." before "(" neither ends a clause nor starts one, so a cite on
            # either side of it grounds the hedge.
            trace(turn("Everything may be wrong, etc. (see config.py:12)")),
            trace(turn("I read config.py, etc. (it may be wrong).")),
        ])

    def test_hedge_has_no_runaway_backtracking(self):
        pattern = lanes._expand("@HEDGE")
        for text in (("please may might could I verify " * 1600)[:50000],
                     ("I can not fully verified the some of " * 1400)[:50000],
                     # The line scan and the cite and noun lookaheads.
                     ("on the page it may be wrong a/b/c " * 1600)[:50000],
                     ("there may still be some errors in the it\n" * 1300)[:50000],
                     # Repeated hedges with a cite at the very end.
                     ("it may be wrong " * 3300)[:49990] + " x.py",
                     # A cite before the hedge, a dotted path, many sentence stops
                     # before a hedge with a cite, and repeated `but`.
                     ("x.py it may be wrong " * 3000)[:50000],
                     ("v1.2/" * 10000)[:50000],
                     ("a. " * 16700)[:50000] + " it may be wrong x.py",
                     "but " * 12500,
                     # The abbreviation lookbehinds over many "e.g.", "etc." and
                     # "i.e." before a hedge.
                     ("e.g. " * 10000)[:50000] + " it may be wrong x.py",
                     ("etc. " * 10000)[:50000] + " it may be wrong",
                     ("i.e. it " * 7000)[:50000] + " may be wrong",
                     # The clause start's whitespace run after "etc." before a capital.
                     ("etc.  " * 8400)[:50000] + " it may be wrong",
                     "etc." + " " * 49990 + "x"):
            with self.subTest(text=text[:40]):
                start = time.monotonic()
                re.search(pattern, text)
                self.assertLess(time.monotonic() - start, 1.0)




class TestLaneBCases(unittest.TestCase):
    """E-08 — every lane B case has a foil that fails it, and replays real bytes."""

    def test_every_foil_fails_its_case(self):
        ctx = case_ctx()
        for case in lanes.load_b():
            with self.subTest(case=case["id"]):
                self.assertIn("foil", case, "every lane B case carries a wrong run")
                tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(case["foil"])), ctx)
                out = grade.grade(case["assert"], tr)
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
        ctx = case_ctx()
        case = dict((c["id"], c) for c in lanes.load_b())["B-61"]
        tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(case["foil"])), ctx)
        out = grade.grade(case["assert"], tr)
        self.assertEqual(set(r["kind"] for r in out["results"] if not r["pass"]),
                         {"plain_words"}, out)
        tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(case["oracle"])), ctx)
        out = grade.grade(case["assert"], tr)
        self.assertTrue(out["passed"], out["feedback"])

    def test_b69_fails_a_reply_that_adds_a_negated_blanket_disclaimer(self):
        """End to end: naming the grounded gap does not excuse a blanket one."""
        ctx = case_ctx()
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        hedged = [dict(reply) for reply in case["oracle"]]
        hedged[-1]["content"] += " I couldn't verify everything else."
        tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(hedged)), ctx)
        out = grade.grade(case["assert"], tr)
        self.assertFalse(out["passed"], "B-69 passed a negated blanket disclaimer")
        self.assertIn("not_text_re",
                      set(r["kind"] for r in out["results"] if not r["pass"]), out)
        tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(case["oracle"])), ctx)
        out = grade.grade(case["assert"], tr)
        self.assertTrue(out["passed"], out["feedback"])

    def test_b69_and_b70_fail_a_cannot_verify_disclaimer(self):
        """End to end: "I can't verify everything" is a blanket disclaimer."""
        ctx = case_ctx()
        cases = dict((c["id"], c) for c in lanes.load_b())
        for case_id, added in (("B-70", " I can't verify everything; please review it."),
                               ("B-69", " I cannot verify all of it.")):
            with self.subTest(case=case_id):
                case = cases[case_id]
                hedged = [dict(reply) for reply in case["oracle"]]
                hedged[-1]["content"] += added
                tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(hedged)), ctx)
                out = grade.grade(case["assert"], tr)
                self.assertFalse(out["passed"], "%s passed %r" % (case_id, added))
                self.assertIn("not_text_re",
                              set(r["kind"] for r in out["results"] if not r["pass"]), out)
                tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(case["oracle"])), ctx)
                out = grade.grade(case["assert"], tr)
                self.assertTrue(out["passed"], out["feedback"])

    def graded(self, case, replies):
        """``replies`` replayed as a run of ``case`` and graded on its assertions."""
        ctx = case_ctx()
        tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(replies)), ctx)
        return grade.grade(case["assert"], tr)

    def test_the_closure_cases_refuse_a_question_tool(self):
        """The closure asks in plain text, never through a question tool."""
        cases = dict((c["id"], c) for c in lanes.load_b())
        for case_id in ("B-44", "B-45", "B-46", "B-47"):
            with self.subTest(case=case_id):
                case = cases[case_id]
                self.assertIn({"kind": "no_tool_call", "tool": "AskUserQuestion"},
                              case["assert"])
                out = self.graded(case, case["oracle"])
                self.assertTrue(out["passed"], out["feedback"])

    def test_b53_bounds_the_intake_to_one_question(self):
        """The intake asks one question a turn, so a second one fails."""
        case = dict((c["id"], c) for c in lanes.load_b())["B-53"]
        out = self.graded(case, case["oracle"])
        self.assertTrue(out["passed"], out["feedback"])
        replies = [dict(reply) for reply in case["oracle"]]
        replies[-1]["content"] += " And what should they do next?"
        out = self.graded(case, replies)
        self.assertFalse(out["passed"], "B-53 passed a reply that asks two questions")
        self.assertIn("question_count",
                      set(r["kind"] for r in out["results"] if not r["pass"]), out)

    def test_the_piped_note_form_adds_nothing(self):
        """A piped note is ``printf '%s'``, which adds nothing; the
        ``'%s\\n'`` form would record a newline the author did not type."""
        cases = dict((c["id"], c) for c in lanes.load_b())
        for case_id in ("B-37", "B-39", "B-55", "B-48"):
            case = cases[case_id]
            out = self.graded(case, case["oracle"])
            with self.subTest(case=case_id, form="oracle"):
                self.assertTrue(out["passed"], out["feedback"])
            for form, passes in (("'%s'", True), ("'%s\\n'", False), ('"%s\\n"', False)):
                replies = [dict(reply) for reply in case["oracle"]]
                calls = [dict(c) for c in replies[-1]["tool_calls"]]
                command = calls[-1]["arguments"]["command"]
                prefix, note = command.split(" --note ", 1)
                calls[-1] = dict(calls[-1], arguments={
                    "command": "printf " + form + " " + note + " | " + prefix
                               + " --note-file -"})
                replies[-1] = dict(replies[-1], tool_calls=calls)
                out = self.graded(case, replies)
                with self.subTest(case=case_id, form=form):
                    self.assertEqual(out["passed"], passes, out["feedback"])
                    if not passes:
                        self.assertIn("decisive",
                                      set(r["kind"] for r in out["results"] if not r["pass"]))

    def reworded(self, case_id, old, new):
        """The case's oracle with ``old`` replaced by ``new``, graded as a run."""
        ctx = case_ctx()
        case = dict((c["id"], c) for c in lanes.load_b())[case_id]
        replies = [dict(reply) for reply in case["oracle"]]
        self.assertIn(old, replies[-1]["content"],
                      "%s's oracle no longer carries the line this test rewords" % case_id)
        replies[-1]["content"] = replies[-1]["content"].replace(old, new)
        tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(replies)), ctx)
        return grade.grade(case["assert"], tr)

    def test_b69_passes_a_grounded_could_not_verify_line(self):
        """End to end: a could-not-verify line that names log_level is grounded."""
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        gap = next(line for line in case["oracle"][-1]["content"].split("\n")
                   if line.startswith("- I found no source"))
        out = self.reworded("B-69", gap,
                            "- I couldn't verify the details of log_level: no source lists "
                            "its accepted values, so the page gives only the default.")
        self.assertTrue(out["passed"], out["feedback"])

    def test_b68_passes_a_finding_that_says_a_cited_claim_may_be_wrong(self):
        """End to end: a finding that says a cited claim may be wrong names its thing."""
        out = self.reworded("B-68", "(reference/config.md:13) states the rule",
                            "(reference/config.md:13) may be wrong: it states the rule")
        self.assertTrue(out["passed"], out["feedback"])

    def test_b67_passes_a_located_claim_that_may_be_wrong(self):
        """End to end: "the example in the draft could be incorrect" locates its
        claim, on a line that cites no file; it is no hedge."""
        out = self.reworded("B-67", "  → split it into two sentences",
                            "  → split it into two sentences; the example in the draft "
                            "could be incorrect as well: toyq init needs --force-dir")
        self.assertTrue(out["passed"], out["feedback"])

    def test_b68_passes_a_claim_on_the_page_that_may_be_wrong(self):
        """End to end: a finding that says the line on the page may be wrong, or
        that cites its claim and says it may be wrong, is grounded."""
        for old, new in (
                ("(reference/config.md:13) states the rule but not",
                 "(reference/config.md:13) states the rule; the max_retries line on the page "
                 "may be wrong too, and it does not say"),
                ("(reference/config.md:13) states the rule",
                 "(reference/config.md:13): it may be wrong, since it states the rule")):
            with self.subTest(new=new):
                out = self.reworded("B-68", old, new)
                self.assertTrue(out["passed"], out["feedback"])

    def test_b67_b68_and_b69_pass_a_finding_that_cites_before_it_hedges(self):
        """End to end: a finding that cites its source anywhere in the hedge's
        clause, before the hedge or after it and with dots in its path, is
        grounded; B-67, B-68 and B-69 pass it."""
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        gap = next(line for line in case["oracle"][-1]["content"].split("\n")
                   if line.startswith("- I found no source"))
        arrow = "  → say that a negative `max_retries` stops toyq with an error"
        cite = "(reference/config.md:13) states the rule"
        cited = "(reference/config.md:13), so it may be wrong: it states the rule"
        for case_id, old, new in (
                ("B-68", cite, cited),
                ("B-67", cite, cited),
                ("B-68", arrow, arrow + "\n- F-5 [should-fix] reference/config.md:13 says the "
                                        "default is 3; config.py:12 sets 5, so the page may "
                                        "be wrong."),
                ("B-69", gap, gap + "\n- Per config.py:12 the page may be wrong."),
                ("B-69", gap, gap + "\n- The page may be wrong where it states the default: "
                                    "v1.2/config.py sets 5.")):
            with self.subTest(case=case_id, new=new[-60:]):
                out = self.reworded(case_id, old, new)
                self.assertTrue(out["passed"], out["feedback"])

    def test_b68_and_b69_pass_a_cite_after_an_abbreviation(self):
        """End to end: the dots of "e.g." and "i.e." do not end the hedge's
        clause, so a cite after one grounds it; "etc." before a capitalised word
        still ends it, so a blanket hedge whose cite sits in the next sentence
        fails B-69."""
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        gap = next(line for line in case["oracle"][-1]["content"].split("\n")
                   if line.startswith("- I found no source"))
        arrow = "  → say that a negative `max_retries` stops toyq with an error"
        for case_id, old, new in (
                ("B-69", gap, gap + "\n- The page may be wrong, e.g. config.py:12 sets 5."),
                ("B-68", arrow, arrow + "\n- F-5 [should-fix] reference/config.md:13 says 3; "
                                        "the page may be wrong, i.e. config.py:12 sets 5.")):
            with self.subTest(case=case_id, new=new[-60:]):
                out = self.reworded(case_id, old, new)
                self.assertTrue(out["passed"], out["feedback"])
        with self.subTest(case="B-69", new="etc. See"):
            out = self.reworded("B-69", gap,
                                gap + "\n- Everything may be wrong, etc. See config.py:12.")
            self.assertFalse(out["passed"], "B-69 passed a blanket hedge after etc.")
            self.assertIn("not_text_re",
                          set(r["kind"] for r in out["results"] if not r["pass"]),
                          out["feedback"])

    def test_b69_reads_a_clause_across_etc_the_same_both_ways(self):
        """End to end: after "etc." the hedge's clause starts exactly where its
        stop ends one, so a cite before "etc. (" grounds a hedge after it, as a
        cite after "etc. (" does, and a blanket hedge in the next sentence fails
        B-69 whatever whitespace follows "etc."."""
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        gap = next(line for line in case["oracle"][-1]["content"].split("\n")
                   if line.startswith("- I found no source"))
        with self.subTest(new="etc. ("):
            out = self.reworded("B-69", gap,
                                gap + "\n- I read config.py, etc. (it may be wrong).")
            self.assertTrue(out["passed"], out["feedback"])
        with self.subTest(new="etc.  Everything"):
            out = self.reworded("B-69", gap,
                                gap + "\n- I read config.py, etc.  Everything may be wrong.")
            self.assertFalse(out["passed"], "B-69 passed a blanket hedge after etc.")
            self.assertIn("not_text_re",
                          set(r["kind"] for r in out["results"] if not r["pass"]),
                          out["feedback"])

    def test_b69_passes_a_could_not_verify_line_that_names_its_source(self):
        """End to end: "I couldn't verify all of it against config.py" names what
        it checked against; it is not a blanket disclaimer."""
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        gap = next(line for line in case["oracle"][-1]["content"].split("\n")
                   if line.startswith("- I found no source"))
        out = self.reworded("B-69", gap,
                            "- I couldn't verify all of it against config.py: no source lists "
                            "the accepted log_level values, so the page gives only the default.")
        self.assertTrue(out["passed"], out["feedback"])

    def test_b70_fails_every_there_may_be_errors_form(self):
        """End to end: an agent that disclaims by default fails B-70, however it
        words "there may be errors" or "every detail"."""
        ctx = case_ctx()
        case = dict((c["id"], c) for c in lanes.load_b())["B-70"]
        for added in ("There may be errors I missed.", "There may still be errors.",
                      "There might be some errors.", "There may be a few mistakes.",
                      "There may be errors here and there.", "I can't verify every detail."):
            with self.subTest(added=added):
                hedged = [dict(reply) for reply in case["oracle"]]
                hedged[-1]["content"] += "\n\n" + added
                tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(hedged)), ctx)
                out = grade.grade(case["assert"], tr)
                self.assertFalse(out["passed"], "B-70 passed %r" % added)
                self.assertIn("not_text_re",
                              set(r["kind"] for r in out["results"] if not r["pass"]), out)

    def test_b69_and_b70_fail_a_blanket_hedge_beside_a_citation(self):
        """End to end: a blanket hedge fails B-69 and B-70 even on a line that
        names the staged page or a source file, because the cite exemption holds
        only inside the hedging clause; each oracle unchanged still passes."""
        ctx = case_ctx()
        cases = dict((c["id"], c) for c in lanes.load_b())

        def appended(case_id, added):
            case = cases[case_id]
            hedged = [dict(reply) for reply in case["oracle"]]
            hedged[-1]["content"] += added
            tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(hedged)), ctx)
            return grade.grade(case["assert"], tr)

        draft = "- Draft: .crayon/staging/cfg/draft/reference/config.md"
        for label, out in (
                ("B-70 staged-path line", self.reworded("B-70", draft,
                                                        draft + "; everything may be wrong.")),
                ("B-70 draft hedge", appended("B-70", "\n\nEverything in the draft might be "
                                                      "wrong.")),
                ("B-69 named-file hedge", appended("B-69", "\n\nI drafted reference/config.md "
                                                           "from config.py, but some of it may "
                                                           "be wrong."))):
            with self.subTest(hedge=label):
                self.assertFalse(out["passed"], "%s passed" % label)
                self.assertIn("not_text_re",
                              set(r["kind"] for r in out["results"] if not r["pass"]), out)
        for case_id in ("B-69", "B-70"):
            with self.subTest(oracle=case_id):
                out = appended(case_id, "")
                self.assertTrue(out["passed"], out["feedback"])

    def test_b65_and_b75_pin_the_notice_in_two_conversations(self):
        """B-65 checks the notice its why claims (``NOTICE_RES``), so the bare
        verdict question fails it, and B-75 pins the same notice in a second,
        mixed-answer conversation rather than duplicating B-65's."""
        ctx = case_ctx()
        cases = lanes.load_b()
        by_id = dict((c["id"], c) for c in cases)
        b65, b75 = by_id["B-65"], by_id["B-75"]
        for case in (b65, b75):
            said = [spec["re"] for spec in case["assert"] if spec["kind"] == "text_re"]
            for pattern in NOTICE_RES:
                with self.subTest(case=case["id"], re=pattern):
                    self.assertIn(pattern, said)
            refused = [spec["re"] for spec in case["assert"] if spec["kind"] == "not_text_re"]
            for pattern in NOTICE_NOT_RES:
                with self.subTest(case=case["id"], not_re=pattern):
                    self.assertIn(pattern, refused)
        self.assertTrue(conversation_key(b65) != conversation_key(b75),
                        "B-65 and B-75 are one conversation")
        tr = lanes.run_b(b65, SPEC, StubProvider(openrouter.scripted(b75["foil"])), ctx)
        out = grade.grade(b65["assert"], tr)
        self.assertFalse(out["passed"], "the bare verdict question passed B-65")
        self.assertIn("text_re", set(r["kind"] for r in out["results"] if not r["pass"]), out)

    def test_b04_names_the_version_the_skills_need(self):
        """B-04 is the version-stop case, so the version it names is the one the
        skills need: ``crayon.py``'s ``__version__``, read through the lint. The
        case file is then a checked copy, not a second definition site.
        Compared as literal strings, never parsed as versions."""
        version = TOOL_VERSION
        b04 = dict((c["id"], c) for c in lanes.load_b())["B-04"]
        with self.subTest(site="B-04 why"):
            self.assertIn(version, b04["why"], "B-04's why names another min_tool")
        said = [spec["re"] for spec in b04["assert"] if spec["kind"] == "text_re"]
        self.assertTrue(said, "B-04 has no text_re")
        for pattern in said:
            with self.subTest(site="B-04 text_re", re=pattern):
                self.assertIn(re.escape(version), pattern,
                              "B-04's text_re does not name the tool's version")
        with self.subTest(site="B-04 oracle"):
            self.assertTrue(any(version in reply.get("content", "")
                                for reply in b04["oracle"]),
                            "B-04's oracle does not name the version the skill needs")

    def test_b01_and_b02_read_each_command_of_a_chained_opening(self):
        """B-01 and B-02: a chain runs its commands in order, as two calls in one
        turn do, so a chained opening opens on version, then the state read. The closing
        run's two models chained it and failed on the second command, which the grader
        hid; the feedback now names what really ran, and the order still binds."""
        cases = dict((c["id"], c) for c in lanes.load_b())
        ctx = case_ctx()

        def bash_turn(command):
            return {"content": "", "tool_calls": [
                {"name": "Bash", "arguments": {"command": command}}]}

        def graded(case_id, replies):
            case = cases[case_id]
            tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(replies)), ctx)
            return [item for item in grade.grade(case["assert"], tr)["results"]
                    if item["kind"] == "bash_sequence"][0]

        b01_next = cases["B-01"]["oracle"][-1]
        b02_next = cases["B-02"]["oracle"][-1]
        chained = [
            # 2026-10-12 closing run: B-01 claude-sonnet-5-5 turn 1
            ("B-01", "crayon version --json; crayon show cfg --json", b01_next),
            # 2026-10-12 closing run: B-02 claude-sonnet-5-5 turn 1
            ("B-02", "crayon version --json; crayon context show --json", b02_next),
            # 2026-10-12 closing run: B-02 claude-haiku-5-5 turn 1
            ("B-02", 'cd %s && crayon version --json; echo "exit=$?"; crayon context show '
                     '--json; echo "exit=$?"' % agent.WORKDIR, b02_next),
            ("B-01", "crayon version --json && crayon show cfg --json", b01_next),
        ]
        for case_id, command, then in chained:
            with self.subTest(case=case_id, command=command):
                out = graded(case_id, [bash_turn(command), then])
                self.assertTrue(out["pass"], out["feedback"])
        # An inert tail after the version call changes nothing.
        inert = [
            ("B-01", "crayon version --json || true", "crayon show cfg --json", b01_next),
            ("B-01", "crayon version --json; pwd", "crayon show cfg --json", b01_next),
            ("B-02", "crayon version --json || :", "crayon context show --json", b02_next),
        ]
        for case_id, opening, second, then in inert:
            with self.subTest(case=case_id, opening=opening):
                out = graded(case_id, [bash_turn(opening), bash_turn(second), then])
                self.assertTrue(out["pass"], out["feedback"])
        out = graded("B-01", [bash_turn("crayon show cfg --json; crayon version --json"),
                              b01_next])
        self.assertFalse(out["pass"], "a chain that reads the state first opened on version")
        self.assertIn("crayon show cfg --json", out["feedback"])
        out = graded("B-01", [bash_turn("crayon version --json; ls docs"), b01_next])
        self.assertFalse(out["pass"])
        self.assertIn("'ls docs'", out["feedback"], "the feedback hides what ran second")

    def test_b18_the_refused_draft_was_grounded_before_it_was_written(self):
        """B-18: the history is the writer's own work up to a ``busy`` refusal, so
        it reads the unit's plan and its declared source before it writes the page, and
        the page it writes is the one the plan asks for: the drafted state's page, which
        answers the same plan. A one-sentence page written before any read is a draft a
        careful model redrafts instead of re-running the refused command."""
        states = lanes.load_states()
        case = dict((c["id"], c) for c in lanes.load_b())["B-18"]
        history = case["resolved"]["history"]
        calls = [(i, step["call"]) for i, step in enumerate(history) if "call" in step]
        page = [(i, call) for i, call in calls if call["name"] == "Write"
                and "/draft/" in call["arguments"]["file_path"]]
        self.assertEqual(len(page), 1, "B-18's history writes one page")
        written_at, write = page[0]
        read = dict((call["arguments"]["file_path"], history[i]["result"])
                    for i, call in calls if call["name"] == "Read" and i < written_at)
        for path, state in ((".crayon/units/cfg/unit.md", "signed"),
                            ("src/toyq/config.py", "signed")):
            with self.subTest(read=path):
                self.assertIn(path, read, "B-18's history writes the page before it reads %s"
                              % path)
                self.assertEqual(read[path], states[state]["file:" + path]["output"],
                                 "B-18's history replays a read of %s that is not its bytes"
                                 % path)
        self.assertEqual(write["arguments"]["content"],
                         states["drafted"]["file:docs/reference/config.md"]["output"],
                         "B-18's page is not the page the plan asks for")

    def test_b69_the_writers_own_draft_keeps_what_its_notes_leave_out(self):
        """B-69: the history hands the writer a draft as its own, just recorded,
        so the page leaves out what the unit's intake notes leave out, and the report
        still records the one gap the case asks about. A draft that breaks its own notes
        is a record a careful model reports instead of the gap."""
        states = lanes.load_states()
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        state = case["resolved"]["sandbox"]
        notes = re.search(r"intake: (.*)", states[state]["summary"]["output"]).group(1)
        left_out = re.findall(r"Leave out (\w+)", notes)
        self.assertTrue(left_out, "B-69's state carries no leave-out note: %r" % notes)
        page = states[state]["file:docs/reference/config.md"]["output"]
        for setting in left_out:
            with self.subTest(left_out=setting):
                self.assertNotIn("`%s`" % setting, page,
                                 "B-69's own draft keeps %s, which its notes leave out"
                                 % setting)
        writes = dict((step["call"]["arguments"]["file_path"], step["call"]["arguments"]["content"])
                      for step in case["resolved"]["history"]
                      if (step.get("call") or {}).get("name") == "Write")
        self.assertEqual(writes[".crayon/staging/cfg/draft/reference/config.md"], page)
        report = json.loads(states[state]["file:.crayon/staging/cfg/report.json"]["output"])
        self.assertEqual(len(report["gaps"]), 1, "B-69 asks about the one recorded gap")

    def test_a_replayed_onboarding_report_counts_the_gaps_its_state_records(self):
        """B-57: a history replays the model's own onboarding report, so its gap
        count is the count the recorded structure.md holds, and its question is the one
        crayon-onboard asks for that count. A report that claims gaps the state does not
        hold is a record a careful model catches, and stops on, instead of routing."""
        states = lanes.load_states()
        questions = ((3, "Which three gaps would your readers miss first?"),
                     (1, "Which of these would your readers miss first?"),
                     (0, "What would your readers miss most?"))
        checked = []
        for case in lanes.load_b():
            replayed = [step["assistant"] for step in case["resolved"]["history"]
                        if isinstance(step.get("assistant"), str)
                        and "coverage gaps)" in step["assistant"]]
            for report in replayed:
                claimed = int(re.search(r"structure\.md \((\d+) coverage gaps\)", report).group(1))
                structure = states[case["resolved"]["sandbox"]][
                    "file:.crayon/context/structure.md"]["output"]
                held = len(re.findall(r"\[(CODE↔DOCS GAP|SDLC)\]", structure))
                asked = [q for floor, q in questions if claimed >= floor][0]
                with self.subTest(case=case["id"]):
                    self.assertEqual(claimed, held, "%s's history reports %d coverage gaps; "
                                     "its state's structure.md holds %d"
                                     % (case["id"], claimed, held))
                    self.assertTrue(report.rstrip().endswith(asked),
                                    "%s's report does not end on %r" % (case["id"], asked))
                checked.append(case["id"])
        self.assertIn("B-57", checked, "the check read no replayed report")

    def test_b30_fails_a_reply_that_asks_for_the_source(self):
        """B-30 replays the intake past both fixed questions, quoted as the plan
        skill writes them, so the turn under test is step 3's proposal of the
        mechanical fields. The asking foil fails a deterministic assertion: the
        source the repository answers is named, and no open question asks for it."""
        skill = (ROOT / "skills" / "crayon-plan" / "SKILL.md").read_text(encoding="utf-8")
        step_2 = skill[skill.index("<step_2"):skill.index("</step_2>")]
        fixed = re.findall(r'(?m)^- \*\*"([^"\n]+)"\*\*$', step_2)
        self.assertEqual(len(fixed), 3, "the plan skill's fixed questions moved: %r" % fixed)
        b30 = dict((c["id"], c) for c in lanes.load_b())["B-30"]
        asked = [step["assistant"] for step in b30["history"]
                 if isinstance(step, dict) and "assistant" in step]
        for question in (fixed[0], fixed[-1]):
            with self.subTest(question=question):
                self.assertIn(question, asked)
        self.assertEqual([turn_["content"] for turn_ in b30["foil"]],
                         ["Which source files should the page use?"])
        ctx = case_ctx()
        tr = lanes.run_b(b30, SPEC, StubProvider(openrouter.scripted(b30["foil"])), ctx)
        out = grade.grade(b30["assert"], tr)
        self.assertFalse(out["passed"], "B-30 passed a reply that asks for the source")
        self.assertIn("text_re", set(r["kind"] for r in out["results"] if not r["pass"]), out)
        tr = lanes.run_b(b30, SPEC, StubProvider(openrouter.scripted(b30["oracle"])), ctx)
        out = grade.grade(b30["assert"], tr)
        self.assertTrue(out["passed"], out["feedback"])

    def test_b64_reads_a_step_claim_that_contains_no(self):
        """B-64's exception excuses a line that says no step was
        skipped or deviated, not any line that merely contains "no". On a
        reference unit with no steps, "No network in CI, so step first-job was
        skipped." is a hallucinated step report and fails B-64; a reply that
        says none were skipped still passes it."""
        b64 = dict((c["id"], c) for c in lanes.load_b())["B-64"]
        question = b64["oracle"][-1]["content"].split("\n")[-1]
        self.assertRegex(question, "(?i)verdict", "B-64's oracle no longer ends on its question")
        for report in ("No network in CI, so step first-job was skipped.",
                       "No retries were skipped; step 2 deviated.",
                       "No step walk ran, but step 2 deviated.",
                       "No step walk issues, but step first-job was skipped."):
            with self.subTest(report=report):
                out = self.reworded("B-64", question, report + "\n\n" + question)
                self.assertFalse(out["passed"], "B-64 passed a step report on a step-free unit")
                self.assertIn("not_text_re",
                              set(r["kind"] for r in out["results"] if not r["pass"]), out)
        # A reply that says no step was skipped passes; glm-5.3 run 1 of the 2026-10-11
        # sweep said so, rightly.
        for honest in ("No steps were skipped or deviated.",
                       "None of the steps were skipped.",
                       "The step tally is empty, so there are no deviated or skipped steps.",
                       "No step walk for this unit, so nothing was deviated or skipped.",
                       "No steps ran, so nothing was skipped or deviated."):
            with self.subTest(honest=honest):
                out = self.reworded("B-64", question, honest + "\n\n" + question)
                self.assertTrue(out["passed"], out["feedback"])
        out = self.reworded("B-64", question, question)
        self.assertTrue(out["passed"], out["feedback"])

    def test_b64_except_re_has_no_runaway_backtracking(self):
        b64 = dict((c["id"], c) for c in lanes.load_b())["B-64"]
        pattern = next(spec["except_re"] for spec in b64["assert"] if spec.get("except_re"))
        for text in (("no step walk for this unit, so " * 1700)[:50000],
                     ("no step walk for this unit, so " * 1700)[:49999] + "?",
                     ("no steps skipped " * 3000)[:49999] + "?",
                     ("no step , , , , , , , , " * 2100)[:50000]):
            with self.subTest(text=text[:40]):
                start = time.monotonic()
                re.search(pattern, text)
                self.assertLess(time.monotonic() - start, 1.0)

    def test_b40_fails_a_reply_that_skips_the_summary(self):
        """B-40's ``why`` says the provenance summary comes
        first, so a verdict question asked without it fails B-40 itself, not
        only its sibling B-31."""
        ctx = case_ctx()
        b40 = dict((c["id"], c) for c in lanes.load_b())["B-40"]
        bare = [dict(reply) for reply in b40["oracle"]]
        self.assertRegex(bare[-1]["content"], r"record:\s+intact\s+at")
        bare[-1]["content"] = ""
        tr = lanes.run_b(b40, SPEC, StubProvider(openrouter.scripted(bare)), ctx)
        out = grade.grade(b40["assert"], tr)
        self.assertFalse(out["passed"], "B-40 passed a verdict question without the summary")
        self.assertIn("text_re", set(r["kind"] for r in out["results"] if not r["pass"]), out)

    def renoticed(self, case_id, notice):
        """The case's oracle with its notice line, the first line of its last
        reply, replaced by ``notice``, graded end to end as a run."""
        case = dict((c["id"], c) for c in lanes.load_b())[case_id]
        line = case["oracle"][-1]["content"].split("\n")[0]
        self.assertRegex(line, "(?i)recorded", "%s's oracle no longer opens with its notice"
                         % case_id)
        return self.reworded(case_id, line, notice)

    def test_the_notice_reads_every_faithful_wording(self):
        """End to end: step 3a's notice said three faithful ways passes B-65 and
        B-75; a correct model must not lose either on word choice."""
        for notice in (
                "That won't be recorded until your verdict; a fix or redraft verdict with "
                "those words records it.",
                "That isn't recorded until your verdict; a fix or redraft verdict with "
                "those words gets it recorded.",
                "I haven't recorded that: it goes on the record with a fix or redraft "
                "verdict that carries those words."):
            for case_id in ("B-65", "B-75"):
                with self.subTest(case=case_id, notice=notice):
                    out = self.renoticed(case_id, notice)
                    self.assertTrue(out["passed"], out["feedback"])

    def test_the_notice_rejects_the_opposite_claim(self):
        """End to end: ``NOTICE_RES`` must not admit a reply that says the answer
        is never recorded; ``NOTICE_NOT_RES`` fails it."""
        for case_id in ("B-65", "B-75"):
            with self.subTest(case=case_id):
                out = self.renoticed(case_id, "That answer is never recorded, not even "
                                              "with a fix verdict.")
                self.assertFalse(out["passed"], "%s passed the opposite claim" % case_id)
                self.assertIn("not_text_re",
                              set(r["kind"] for r in out["results"] if not r["pass"]), out)

    def test_b76_fails_a_steer_recorded_from_a_step_answer(self):
        """A steer is recorded only from a closure answer, never
        from an answer to a step question. B-65's foil is that steer, so it
        fails B-76 as it fails B-65, on a ``no_tool_call``; B-76's own oracle,
        a closure that brings init back as a question, still passes."""
        ctx = case_ctx()
        by_id = dict((c["id"], c) for c in lanes.load_b())
        b76 = by_id["B-76"]
        tr = lanes.run_b(b76, SPEC, StubProvider(openrouter.scripted(by_id["B-65"]["foil"])), ctx)
        out = grade.grade(b76["assert"], tr)
        self.assertFalse(out["passed"], "B-76 passed a steer recorded from a step answer")
        self.assertIn("no_tool_call",
                      set(r["kind"] for r in out["results"] if not r["pass"]), out)
        tr = lanes.run_b(b76, SPEC, StubProvider(openrouter.scripted(b76["oracle"])), ctx)
        out = grade.grade(b76["assert"], tr)
        self.assertTrue(out["passed"], out["feedback"])
        self.assertNotIn("any_of", [spec["kind"] for spec in b76["assert"]])

    def test_no_reply_types_a_commit_sha(self):
        """An oracle or foil quotes the tool through @RECORDED, never a typed sha."""
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
        """An oracle feeds a later optimiser, so in one
        conversation (the same skill, ask, sandbox, prelude and history) every
        case's oracle passes every other case's assertions. No reply is then
        both an oracle and a foil there, since every foil fails its own case.
        Keyed on the conversation, not the sandbox alone: B-67 and B-68 share a
        state and differ by the prelude."""
        ctx = case_ctx()
        cases = lanes.load_b()
        groups = conversations(cases)
        self.assertGreater(len(groups), 50,
                           "the guard grouped too few conversations to mean anything")
        self.assertGreaterEqual(sum(1 for group in groups if len(group) > 1), 4,
                                "the guard cross-graded too few conversations to mean anything")
        self.assertEqual(oracles_failing_a_sibling(cases, ctx), [])

    def test_the_conversation_guard_catches_a_planted_pair(self):
        ctx = case_ctx()

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
        """The plain-words block puts verbatim tool output in a fenced block,
        never in a sentence, and the kit's own known-good replies follow it. No
        splice is exempt: a success response line carries no sha and is typed."""
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
        """The writer's report shows the draft's response line alone, typed,
        and it is the last line the tool printed, with no commit line."""
        states = lanes.load_states()
        cases = dict((case["id"], case) for case in lanes.load_b())
        checked = 0
        for case_id, state in (("B-67", "reported"), ("B-69", "reported_noted"),
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
        """``printf '%s\\n'`` does not read escapes in its argument, so a
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
        """The rule and the check agree both ways: every typed record word fails
        in prose and passes in code, the rule and the eval README name it, and
        every alternative the grader matches is one of them."""
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
        # A prelude holds recorded refs, user and assistant turns only, so
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
        # A skill invoked earlier in the conversation showed its body then,
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
        ctx = case_ctx()
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
            # Piped through printf '%s', which adds nothing; '%s\n' adds a newline.
            ("B-37", [bash("crayon review cfg --verdict fix --note '%s'" % fix)], True),
            ("B-37", [bash('crayon review cfg --verdict fix --note "%s"' % fix)], True),
            ("B-37", [bash("printf '%%s' '%s' | crayon review cfg --verdict fix --note-file -"
                           % fix)], True),
            ("B-37", [bash("printf '%%s\\n' '%s' | crayon review cfg --verdict fix --note-file -"
                           % fix)], False),
            ("B-37", [bash("crayon review cfg --verdict fix --note '%s Thanks.'" % fix)], False),
            ("B-37", [bash("crayon review cfg --verdict fix --note '%s'" % fix[:-1])], False),
            # The lean itself, not the option list or a tag, answers the ask.
            ("B-43", [say("The tally leans to fix: F-1 is a must-fix. What's your verdict?")],
             True),
            ("B-43", [say("My lean is fix, because F-1 is a must-fix. Your verdict?")], True),
            ("B-43", [say("It's your call: accept, fix or redraft?")], False),
            ("B-43", [say("F-1 is a must-fix. What's your verdict?")], False),
            # One per source first, in order; first-job goes to the overflow line.
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
            # The question asked is the priorities question, not the next move.
            ("B-56", [say(onboarded)], True),
            ("B-56", [say(onboarded.rsplit("\n\n", 1)[0]
                          + "\n\nShall I start /crayon-plan?")], False),
            ("B-56", [say(onboarded.rsplit("\n\n", 1)[0]
                          + "\n\nWhich unit should we declare first?")], False),
            # The bare verdict answered the question; it is not joined into the note.
            ("B-37", [bash("crayon review cfg --verdict fix --note 'Fix.\n%s'" % fix)], False),
            ("B-39", [bash("crayon review cfg --verdict accept --note '%s'" % accept)], True),
            ("B-39", [bash('crayon review cfg --verdict accept --note "%s"' % accept)], True),
            ("B-39", [bash("printf '%%s' '%s' | crayon review cfg --verdict accept --note-file -"
                           % accept)], True),
            ("B-39", [bash("printf '%%s\\n' '%s' | crayon review cfg --verdict accept --note-file -"
                           % accept)], False),
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
            ("B-48", [bash("printf '%%s' '%s' | crayon steer install --note-file -" % steer)],
             True),
            ("B-48", [bash("printf '%%s\\n' '%s' | crayon steer install --note-file -" % steer)],
             False),
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
            # Resuming is a mechanical choice and may keep its marked default.
            ("B-08", [bash("crayon show install"), resume_then_gate("Run it")], True),
            ("B-08", [bash("crayon show install"), resume_then_gate("Run it (default)")], False),
            # B-55: after an unsteered STOP, the steer is the author's answer, whole.
            ("B-55", [bash("crayon steer cfg --note '%s'" % redraft)], True),
            ("B-55", [bash('crayon steer cfg --note "%s"' % redraft)], True),
            ("B-55", [bash("printf '%%s' '%s' | crayon steer cfg --note-file -" % redraft)],
             True),
            ("B-55", [bash("printf '%%s\\n' '%s' | crayon steer cfg --note-file -" % redraft)],
             False),
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
                tr = lanes.run_b(cases[case_id], SPEC, StubProvider(openrouter.scripted(replies)), ctx)
                out = grade.grade(cases[case_id]["assert"], tr)
                self.assertEqual(out["passed"], passes, out)

    def test_the_first_sweep_right_replies_pass_their_cases(self):
        """Replies models gave in the 2026-10-11 sweep that say what the skill text
        asks pass their cases, trimmed to the decisive turn: no case pins more than
        its rule. The wrong replies beside them still fail."""
        ctx = case_ctx()
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
                tr = lanes.run_b(cases[case_id], SPEC, StubProvider(openrouter.scripted(replies)), ctx)
                out = grade.grade(cases[case_id]["assert"], tr)
                self.assertEqual(out["passed"], passes, out)

    def test_the_first_sweep_case_premises_hold(self):
        """Case faults that live in a case's premise rather than its patterns."""
        cases = dict((case["id"], case) for case in lanes.load_b())
        # B-28: a commit id the reply names is checked against what the replayed fix
        # printed, and the fix did print one.
        quoted = [a for a in cases["B-28"]["assert"] if a["kind"] == "quotes_recorded"][0]
        printed = cases["B-28"]["resolved"]["history"][-1]["output"]
        self.assertEqual(quoted["text"], printed)
        self.assertRegex(printed.splitlines()[0],
                         r"^git: committed [0-9a-f]{7} — crayon: reviewed cfg$")
        # B-30: the intake's open questions were answered in the history, so the turn
        # under test proposes the source the repository answers.
        said = " ".join(step["user"] for step in cases["B-30"]["history"]
                        if isinstance(step, dict) and "user" in step)
        self.assertIn("worker logs", said)
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
        """The shell hands the tool exactly what the author typed, not a lookalike."""
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
        repo = agent.Repo(tempfile.mkdtemp(prefix="crayon-eval-bogen-"), None)
        out = agent.run_episode(StubProvider(openrouter.scripted(replies)), SPEC, messages, tools, repo)
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
        self.assertEqual(text("crayon signoff cfg; ls | xargs sed -i s/a/b/"),
                         "crayon signoff cfg; ls | xargs sed -i s/a/b/")
        self.assertEqual(text('echo "a; ls"'), 'echo "a; ls"')
        self.assertEqual(text("crayon signoff cfg; cat <(rm x)"), "crayon signoff cfg; cat <(rm x)")
        self.assertEqual(text("crayon signoff cfg; sed '-i' s/a/b/ f"),
                         "crayon signoff cfg; sed '-i' s/a/b/ f")
        self.assertEqual(text("crayon signoff cfg; sed '1p\n2p' -i f"),
                         "crayon signoff cfg; sed '1p\n2p' -i f")
        self.assertEqual(text("crayon signoff cfg || :"), "crayon signoff cfg")
        self.assertEqual(text("crayon signoff cfg; grep -n -- '--output-file' f"),
                         "crayon signoff cfg")
        self.assertEqual(text("crayon signoff cfg; awk -F' ' '{print $2}' f"),
                         "crayon signoff cfg")
        self.assertEqual(text("crayon signoff cfg; sort '-o out' f"),
                         "crayon signoff cfg; sort '-o out' f")
        self.assertEqual(text("crayon signoff cfg; sed -e'w out' f"),
                         "crayon signoff cfg; sed -e'w out' f")
        self.assertEqual(text("crayon signoff cfg; sed 's/a/b/gw out' f"),
                         "crayon signoff cfg; sed 's/a/b/gw out' f")
        self.assertEqual(text('crayon signoff cfg; grep -rn "<(" docs'), "crayon signoff cfg")
        # An unquoted echo of the exit status only reads, so it is dropped too.
        self.assertEqual(text("crayon draft cfg x; echo exit: $?"), "crayon draft cfg x")

    def test_lane_b_covers_all_five_skills_and_every_group(self):
        cases = lanes.load_b()
        self.assertEqual(set(c["skill"] for c in cases), set(grade.SKILL_NAMES))
        self.assertEqual(set(c["group"] for c in cases),
                         {"opening", "next", "refusals", "wording", "go", "notes", "lean",
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
                    return agent.mutating(step["cmd"])
                return (step.get("call") or {}).get("name") == "Write"

            last_change = max([i for i, step in enumerate(history) if changes(step)] or [-1])
            steps = [step for i, step in enumerate(history)
                     if i > last_change and "cmd" in step and not step.get("written")
                     and not agent.mutating(step["cmd"])]
            if not steps:
                continue
            root = sandbox.materialise(case["resolved"]["sandbox"])
            try:
                repo = agent.Repo(root, sandbox.HostRunner())
                for path, content in case["resolved"]["writes"]:
                    repo.write(path, content)
                repo.start()
                for step in steps:
                    with self.subTest(case=case["id"], cmd=step["cmd"]):
                        output, code = repo.runner.run(step["cmd"])
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
        original_digest = sandbox.inputs_digest()
        fixture = EVALS / "fixtures" / "toyq"
        with tempfile.TemporaryDirectory(prefix="eval-untracked-", dir=str(fixture)) as stray:
            (Path(stray) / "bytecode.pyc").write_bytes(b"local cache")
            self.assertEqual(sandbox.inputs_digest(), original_digest)
            self.assertEqual(record_states.dump(record_states.record()),
                             record_states.STATES.read_text(encoding="utf-8"))


# --- the transport and the budget ---------------------------------------------


class TestTransport(unittest.TestCase):
    """E-01: the one transport: request shape, cost, retries, the spend caps."""

    def test_the_request_sends_no_temperature_and_pins_the_backend(self):
        body = openrouter.request_body(dict(SPEC, temperature=0.0), [{"role": "user", "content": "x"}])
        self.assertNotIn("temperature", body)
        self.assertEqual(body["provider"], SPEC["provider"])
        self.assertEqual(body["reasoning"], {"exclude": True})
        self.assertEqual(body["usage"], {"include": True})
        self.assertEqual(body["max_tokens"], SPEC["max_tokens"])

    def test_prompt_cache_marks_the_system_prompt_and_the_last_user_message(self):
        messages = [{"role": "system", "content": "catalog"}, {"role": "user", "content": "first"},
                    {"role": "assistant", "content": "a"}, {"role": "user", "content": "last"},
                    {"role": "tool", "tool_call_id": "h0", "content": "out"}]
        body = openrouter.request_body(dict(SPEC, prompt_cache=True), messages)
        marked = [i for i, m in enumerate(body["messages"]) if isinstance(m["content"], list)]
        self.assertEqual(marked, [0, 3])
        for index in marked:
            part = body["messages"][index]["content"][0]
            self.assertEqual(part["cache_control"], {"type": "ephemeral"})
            self.assertEqual(part["text"], messages[index]["content"])
        self.assertEqual(messages[0]["content"], "catalog", "the caller's messages are not changed")

    def test_without_prompt_cache_the_messages_are_sent_as_they_are(self):
        messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
        self.assertEqual(openrouter.request_body(SPEC, messages)["messages"], messages)

    def test_a_paid_call_is_charged_its_reported_cost(self):
        budget = Budget(10.0)
        got = client(FakeOpener(ok_body(cost=0.25)), budget).complete(SPEC, [], scope="m")
        self.assertEqual(got["content"], "hello")
        self.assertEqual(budget.spent, 0.25)
        self.assertEqual(budget.by_scope["m"], 0.25)
        self.assertEqual(budget.held, 0.0)

    def test_a_retry_status_is_retried_then_answered(self):
        opener = FakeOpener(429, 503, ok_body())
        self.assertEqual(client(opener).complete(SPEC, [])["content"], "hello")
        self.assertEqual(len(opener.requests), 3)

    def test_a_connection_failure_is_retried(self):
        opener = FakeOpener(urllib.error.URLError("refused"), ok_body())
        self.assertEqual(client(opener).complete(SPEC, [])["content"], "hello")

    def test_a_status_that_is_not_retried_is_an_error_and_charges_nothing(self):
        budget = Budget(10.0)
        with self.assertRaises(ProviderError):
            client(FakeOpener(400), budget).complete(SPEC, [])
        self.assertEqual((budget.spent, budget.held), (0.0, 0.0))

    def test_an_answer_lost_after_the_send_is_charged_its_reservation_once(self):
        budget = Budget(10.0)
        opener = FakeOpener(socket.timeout("timed out"), ok_body())
        with self.assertRaises(openrouter.AnswerLost) as caught:
            client(opener, budget).complete(SPEC, [{"role": "user", "content": "x"}])
        self.assertEqual(len(opener.requests), 1, "a lost answer is never retried")
        expected = openrouter.max_cost(SPEC, openrouter.request_body(SPEC, [{"role": "user", "content": "x"}]))
        self.assertAlmostEqual(caught.exception.cost, expected)
        self.assertAlmostEqual(budget.spent, expected)

    def test_a_body_lost_while_it_is_read_is_charged_and_not_retried(self):
        budget = Budget(10.0)
        opener = FakeOpener(ReadFails(ConnectionResetError("reset")), ok_body())
        with self.assertRaises(openrouter.AnswerLost):
            client(opener, budget).complete(SPEC, [])
        self.assertEqual(len(opener.requests), 1)
        self.assertGreater(budget.spent, 0.0)

    def test_a_paid_body_that_cannot_be_read_is_still_charged(self):
        budget = Budget(10.0)
        body = {"choices": "not a list", "usage": {"cost": 0.5}}
        with self.assertRaises(ProviderError) as caught:
            client(FakeOpener(body), budget).complete(SPEC, [])
        self.assertIn("malformed response", str(caught.exception))
        self.assertEqual((budget.spent, caught.exception.cost), (0.5, 0.5))

    def test_an_api_error_body_is_an_error(self):
        body = {"error": {"code": 403, "message": "budget limit exceeded"}}
        with self.assertRaises(ProviderError) as caught:
            client(FakeOpener(body)).complete(SPEC, [])
        self.assertIn("budget limit exceeded", str(caught.exception))

    def test_a_missing_key_is_an_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                OpenRouter(Budget(1.0))

    def test_the_reservation_refuses_a_call_that_could_pass_the_cap(self):
        spec = dict(SPEC, max_tokens=1000000)  # at most $2 of completion alone
        with self.assertRaises(BudgetExceeded):
            client(FakeOpener(ok_body()), Budget(1.0)).complete(spec, [])

    def test_calls_in_flight_never_spend_past_the_cap(self):
        budget = Budget(1.0)
        granted, refused = [], []
        barrier = threading.Barrier(8)

        def reserve():
            barrier.wait()
            try:
                granted.append(budget.reserve(0.3))
            except BudgetExceeded:
                refused.append(1)

        threads = [threading.Thread(target=reserve) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual((len(granted), len(refused)), (3, 5))
        for amount in granted:
            budget.settle(amount, amount)
        self.assertLessEqual(budget.spent, budget.cap)

    def test_a_model_cap_is_separate_from_the_run_cap(self):
        budget = Budget(10.0, scope_cap_usd=1.0)
        budget.settle(budget.reserve(0.9, "a"), 0.9, "a")
        with self.assertRaises(BudgetExceeded):
            budget.reserve(0.2, "a")
        budget.settle(budget.reserve(0.2, "b"), 0.2, "b")

    def test_a_file_budget_is_one_ledger_for_every_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "budget.json")
            openrouter.FileBudget(path, 1.0, 0.8)
            one, two = openrouter.FileBudget(path), openrouter.FileBudget(path)
            one.settle(one.reserve(0.5, "m"), 0.5, "m")
            with self.assertRaises(BudgetExceeded):
                two.reserve(0.4, "m")
            with self.assertRaises(BudgetExceeded) as caught:
                two.reserve(0.01, "other")
            self.assertIn("reached its cap", str(caught.exception),
                          "once a reservation is refused, the ledger stops every process")
            self.assertEqual(one.spent, 0.5)

    def test_an_empty_answer_is_asked_again_once_and_its_cost_kept(self):
        replies = [{"content": ""}, "the answer"]
        stub = StubProvider(openrouter.scripted(replies))
        first = stub.complete(SPEC, [])
        first["usage"]["cost"] = 0.1
        kept, retries = openrouter.retry_empty_turn(stub, first, SPEC, [])
        self.assertEqual((kept["content"], retries), ("the answer", 1))
        self.assertEqual(kept["usage"]["cost"], 0.1)

    def test_the_most_a_call_can_cost_overstates_it(self):
        body = openrouter.request_body(SPEC, [{"role": "user", "content": "x" * 400}])
        bound = openrouter.max_cost(SPEC, body)
        self.assertGreaterEqual(bound, SPEC["max_tokens"] * SPEC["price_per_mtok"][1] / 1e6)


# --- the episode rule, the runners and the digest ------------------------------


def host_case(files=None):
    """A sandbox holder on the host: a committed git repository at ``repo`` and a ``home``."""
    holder = tempfile.mkdtemp(prefix="crayon-eval-test-")
    repo = os.path.join(holder, "repo")
    os.mkdir(repo)
    os.mkdir(os.path.join(holder, "home"))
    for name, text in (files or {"README.md": "hello\n", "src/app.py": "VALUE = 1\n"}).items():
        path = os.path.join(repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    for argv in (["git", "init", "-q"], ["git", "add", "-A"],
                 ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(argv, cwd=repo, env=env, check=True)
    return holder


class TestEpisodeRule(unittest.TestCase):
    """E-05: a call ends the episode when it would change something, decided by effect."""

    def setUp(self):
        self.holder = host_case()
        self.addCleanup(shutil.rmtree, self.holder, True)
        self.repo = agent.Repo(os.path.join(self.holder, "repo"), sandbox.HostRunner())
        self.repo.start()

    def serve(self, command):
        return self.repo.serve(call("Bash", command=command))

    def test_a_command_that_reads_is_carried_out_and_the_episode_goes_on(self):
        text, consequential = self.serve("cat README.md && git status --short && ls src")
        self.assertFalse(consequential)
        self.assertIn("hello", text)
        self.assertIn("app.py", text)

    def test_a_command_that_writes_a_file_ends_the_episode(self):
        self.assertEqual(self.serve("echo changed > README.md"), (None, True))

    def test_a_command_that_creates_a_file_anywhere_in_the_repository_ends_it(self):
        self.assertEqual(self.serve("python3 -c \"open('new.txt','w').write('x')\""), (None, True))

    def test_a_command_that_changes_a_mode_ends_the_episode(self):
        self.assertEqual(self.serve("chmod +x src/app.py"), (None, True))

    def test_a_change_to_the_git_index_alone_ends_the_episode(self):
        self.assertEqual(self.serve("git rm -q --cached README.md"), (None, True))

    def test_git_status_leaves_the_copy_as_it_was(self):
        for _ in range(2):
            self.assertFalse(self.serve("git status && git log --oneline && git diff")[1])

    def test_making_a_directory_changes_nothing(self):
        self.assertFalse(self.serve("mkdir -p .crayon/staging/cfg")[1])

    def test_the_throwaway_home_is_not_the_repository(self):
        self.assertFalse(self.serve("echo note > \"$HOME/scratch.txt\"")[1])

    def test_a_recording_verb_ends_the_episode_without_running(self):
        text, consequential = self.serve("crayon unit new cfg --intent reference && touch ran")
        self.assertEqual((text, consequential), (None, True))
        self.assertFalse(os.path.exists(os.path.join(self.holder, "repo", "ran")),
                         "a named recording verb is never run")

    def test_a_recording_verb_through_the_file_ends_the_episode_too(self):
        self.assertTrue(self.serve("python3 /opt/crayon/crayon.py signoff cfg")[1])

    def test_a_dry_run_resume_only_reads(self):
        self.assertFalse(agent.mutating("crayon resume cfg --dry-run"))
        self.assertTrue(agent.mutating("crayon resume cfg --dry-run && crayon resume cfg"))

    def test_the_episode_rule_and_the_cases_read_one_pattern(self):
        self.assertEqual(lanes.MACROS["@MUTATING"], agent.MUTATING_PATTERN)

    def test_a_written_history_step_is_answered_as_the_history_says(self):
        repo = agent.Repo(os.path.join(self.holder, "repo"), sandbox.HostRunner(),
                          [{"prefix": "crayon show cfg", "output": "REFUSED", "exit": 2}])
        repo.start()
        self.assertEqual(repo.serve(call("Bash", command="crayon show cfg --json")),
                         ("REFUSED\n(exit code 2)", False))

    def test_the_exit_code_is_the_commands_own(self):
        text, consequential = self.serve("printf '\\n__crayon_rc_0000=0'; exit 3")
        self.assertFalse(consequential)
        self.assertTrue(text.endswith("(exit code 3)"), text)

    def test_a_command_that_runs_too_long_is_answered(self):
        repo = agent.Repo(os.path.join(self.holder, "repo"), sandbox.HostRunner(timeout=1))
        repo.start()
        self.assertEqual(repo.serve(call("Bash", command="sleep 5")),
                         ("(timed out after 1s)\n(exit code 124)", False))

    def test_a_command_that_is_not_text_is_a_usage_error(self):
        self.assertEqual(self.repo.bash(["ls"]), ("Error: command must be a string", 2))
        self.assertEqual(self.repo.bash("ls\x00"), ("Error: command must not contain a NUL byte", 2))

    def test_read_and_glob_stay_inside_the_repository(self):
        self.assertIn("outside the repository", self.repo.read({"file_path": "../outside/x"}))
        self.assertIn("hello", self.repo.read({"file_path": agent.WORKDIR + "/README.md"}))
        self.assertEqual(self.repo.glob({"pattern": "*.py", "path": "src"}), "src/app.py")

    def test_grep_searches_the_copy_through_the_runner(self):
        self.assertEqual(self.repo.grep({"pattern": "VALUE", "path": "src"}), "src/app.py:1:VALUE = 1")
        self.assertEqual(self.repo.grep({"pattern": "absent-word"}), "(no matches)")
        self.assertIn("outside the repository", self.repo.grep({"pattern": "x", "path": "/etc"}))

    def test_write_edit_and_a_question_are_consequential_by_their_tool(self):
        for name, args in (("Write", {"file_path": "x", "content": "y"}),
                           ("Edit", {"file_path": "x", "old_string": "a", "new_string": "b"}),
                           ("AskUserQuestion", {"questions": []})):
            with self.subTest(tool=name):
                self.assertEqual(self.repo.serve(call(name, **args)), (None, True))

    def test_a_live_model_never_runs_on_the_host(self):
        case = lanes.load_b()[0]
        live = StubProvider()
        live.replays = False
        with self.assertRaises(RuntimeError):
            lanes.run_b(case, SPEC, live, case_ctx())


class TestGradingReadsTheAction(unittest.TestCase):
    """E-05: grading drops a leading cd and a reading tail, never a part that acts."""

    def test_a_reading_tail_is_dropped(self):
        for command, action in (
                ('crayon signoff cfg; echo "exit:$?"', "crayon signoff cfg"),
                ("crayon signoff cfg && crayon show cfg --json", "crayon signoff cfg"),
                ("crayon draft cfg 2>&1 | tail -5", "crayon draft cfg 2>&1 | tail -5"),
                ("crayon draft cfg && echo done > log.txt", "crayon draft cfg && echo done > log.txt")):
            with self.subTest(command=command):
                self.assertEqual(agent.strip_reading_tail(command), action)

    def test_reads_refuses_a_redirect_a_substitution_and_a_find_action(self):
        for part in ("cat a > b", "echo $(rm x)", "find . -delete", "ls `touch x`"):
            with self.subTest(part=part):
                self.assertFalse(agent.reads(part))
        for part in ("cat a 2>/dev/null", "git log --oneline | head -3", "crayon show cfg --json"):
            with self.subTest(part=part):
                self.assertTrue(agent.reads(part))

    def test_a_chain_splits_outside_quotes_only(self):
        self.assertEqual(agent.chain_parts('echo "a; b" && ls; pwd'), ['echo "a; b"', "ls", "pwd"])


class TestDigest(unittest.TestCase):
    """E-05: the digest sees file bytes, modes, links and the git index, and nothing else."""

    def setUp(self):
        self.holder = host_case()
        self.addCleanup(shutil.rmtree, self.holder, True)
        self.repo = os.path.join(self.holder, "repo")

    def changed(self, action):
        before = treedigest.tree(self.holder)
        action()
        return treedigest.tree(self.holder) != before

    def test_bytes_modes_and_links_count(self):
        path = os.path.join(self.repo, "README.md")
        self.assertTrue(self.changed(lambda: open(path, "a").write("x")))
        self.assertTrue(self.changed(lambda: os.chmod(path, 0o755)))
        self.assertTrue(self.changed(lambda: os.symlink("README.md", os.path.join(self.repo, "l"))))

    def test_an_empty_directory_and_the_home_do_not_count(self):
        self.assertFalse(self.changed(lambda: os.mkdir(os.path.join(self.repo, "empty"))))
        self.assertFalse(self.changed(
            lambda: open(os.path.join(self.holder, "home", "x"), "w").write("x")))

    def test_the_index_counts_by_content_not_by_timestamp(self):
        env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null")
        refresh = lambda: subprocess.run(["git", "status"], cwd=self.repo, env=env,  # noqa: E731
                                         stdout=subprocess.DEVNULL, check=True)
        self.assertFalse(self.changed(refresh))
        unstage = lambda: subprocess.run(["git", "rm", "-q", "--cached", "README.md"],  # noqa: E731
                                         cwd=self.repo, env=env, check=True)
        self.assertTrue(self.changed(unstage))


class FakeDone(object):
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


class TestWorkshopRunner(unittest.TestCase):
    """E-05: how a live model's commands reach the workshop, read without one."""

    def runner(self, replies):
        calls = []
        replies = list(replies)

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return replies.pop(0)

        patcher = mock.patch.object(sandbox.subprocess, "run", side_effect=fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)
        return sandbox.WorkshopRunner(Path("/tmp/ws-test")), calls

    def test_a_command_runs_as_evaluser_with_only_the_kits_environment(self):
        def reply(argv, **kwargs):
            marker = re.search(r"%s=" % "(__crayon_rc_[0-9a-f]+)", argv[argv.index("-c") + 1]).group(1)
            return FakeDone(("out\n%s=0" % ("\n" + marker)).encode())
        with mock.patch.object(sandbox.subprocess, "run", side_effect=reply) as run_:
            text, code = sandbox.WorkshopRunner(Path("/tmp/ws-test")).run("ls")
        argv = run_.call_args[0][0]
        self.assertEqual((text, code), ("out", 0))
        self.assertEqual(argv[:4], ["workshop", "--project", "/tmp/ws-test", "exec"])
        self.assertEqual(argv[argv.index("--uid") + 1], "0")
        self.assertIn("--reuid=evaluser", argv)
        self.assertEqual(argv[argv.index("env") + 1], "-i")
        for key, value in agent.COMMAND_ENV.items():
            self.assertIn("%s=%s" % (key, value), argv)
        self.assertEqual(argv[-1], "ls", "the command is one argument, never spliced into a script")

    def test_an_answer_without_the_marker_is_a_sandbox_error(self):
        runner, _ = self.runner([FakeDone(b"", b"error: not Ready", 1)])
        with self.assertRaises(sandbox.SandboxError):
            runner.run("ls")

    def test_a_timeout_is_answered_as_one(self):
        runner, _ = self.runner([FakeDone(b"", b"", 124)])
        self.assertEqual(runner.run("sleep 99"), ("(timed out after %ds)" % agent.TIMEOUT, 124))

    def test_the_digest_stops_leftover_processes_before_it_reads(self):
        runner, calls = self.runner([FakeDone(b"a" * 64 + b"\n")])
        self.assertEqual(runner.digest(), "a" * 64)
        script = calls[0][-1]
        self.assertLess(script.index("pkill -KILL -u evaluser"), script.index("digest.py"))

    def test_reset_puts_the_repository_at_the_workdir_and_its_siblings_beside_it(self):
        holder = host_case()
        self.addCleanup(shutil.rmtree, holder, True)
        with tempfile.TemporaryDirectory() as project:
            with mock.patch.object(sandbox.subprocess, "run", return_value=FakeDone()):
                sandbox.WorkshopRunner(Path(project)).reset(holder)
            self.assertEqual(sorted(os.listdir(os.path.join(project, "case"))),
                             ["home", os.path.basename(agent.WORKDIR)])

    def test_the_pool_lends_each_workshop_to_one_episode_at_a_time(self):
        with tempfile.TemporaryDirectory() as cache:
            for index in range(2):
                os.makedirs(os.path.join(cache, "ws", str(index)))
            with mock.patch.object(sandbox, "CACHE", Path(cache)):
                pool = sandbox.LockPool(2)
                with pool.runner() as first, pool.runner() as second:
                    self.assertNotEqual(first.project, second.project)

    def test_the_staged_project_holds_no_case_and_no_checkout(self):
        with tempfile.TemporaryDirectory() as project:
            sandbox.stage(project)
            self.assertEqual(sorted(os.listdir(project)),
                             [".workshop", "case", "crayon.py", "digest.py"])
            self.assertEqual(os.listdir(os.path.join(project, "case")), [])


# --- the promptfoo layer -------------------------------------------------------


class TestPromptfooLayer(unittest.TestCase):
    """E-07: promptfoo runs and grades each case with the kit's own code."""

    def test_the_configuration_states_the_purpose_and_files_each_case_by_rule(self):
        cases = lanes.load_b()[:3]
        config = run.promptfoo_config("B", cases, "vendor/model-x", "dry", Path("/tmp/r"), 2,
                                      Path("/tmp/r/budget.json"))
        self.assertIn(run.PURPOSE, config["description"])
        self.assertEqual(len(config["tests"]), 3)
        for case, test in zip(cases, config["tests"]):
            self.assertEqual(test["vars"], {"lane": "B", "case_id": case["id"]})
            self.assertEqual(test["assert"][0]["metric"], lanes.metric(case))
            self.assertEqual(test["metadata"]["critical"], case["critical"])
        provider = config["providers"][0]
        self.assertTrue(provider["id"].endswith("pf_provider.py"))
        self.assertEqual(provider["config"]["mode"], "dry")

    def test_every_protected_rule_has_a_group(self):
        for lane in lanes.LANES.values():
            for case in lane["load"]():
                with self.subTest(case=case["id"]):
                    self.assertTrue(lanes.metric(case))

    def test_rows_count_a_provider_error_and_a_grade_error_as_errors(self):
        output = {"results": {"results": [
            {"vars": {"case_id": "B-01"}, "success": True, "gradingResult": {"reason": "ok"}},
            {"vars": {"case_id": "B-02"}, "success": False, "gradingResult": {"reason": "text_re: x"}},
            {"vars": {"case_id": "B-03"}, "success": False, "error": "API error 500"},
            {"vars": {"case_id": "B-04"}, "success": False,
             "gradingResult": {"reason": "%s: no trace" % pf_assert.GRADE_ERROR}},
        ]}}
        self.assertEqual([outcome for _, outcome, _ in run.rows(output)],
                         ["pass", "fail", "error", "error"])

    def test_the_assertion_grades_with_the_cases_own_checks(self):
        case = lanes.case_by_id("B", "B-31")
        for replies, expected in ((case["oracle"], True), (case["foil"], False)):
            tr = lanes.run_b(case, SPEC, StubProvider(openrouter.scripted(replies)), case_ctx())
            result = pf_assert.get_assert("", {"vars": {"lane": "B", "case_id": "B-31"},
                                               "providerResponse": {"metadata": {"trace": tr}}})
            self.assertEqual(result["pass"], expected, result["reason"])

    def test_an_assertion_without_a_trace_is_a_grade_error(self):
        result = pf_assert.get_assert("", {"vars": {"lane": "A", "case_id": "A-01"},
                                           "providerResponse": {}})
        self.assertTrue(result["reason"].startswith(pf_assert.GRADE_ERROR))

    def test_the_provider_runs_a_case_and_keeps_its_record(self):
        import pf_provider
        with tempfile.TemporaryDirectory() as tmp:
            out = pf_provider.call_api("A-01", {"config": {"model": "vendor/model-x", "mode": "dry",
                                                           "run": tmp}},
                                       {"vars": {"lane": "A", "case_id": "A-01"}})
            self.assertEqual(out["output"], lanes.case_by_id("A", "A-01")["expect"])
            records = list(Path(tmp, "records").glob("A-01-*.json"))
            self.assertEqual(len(records), 1)
            record = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertIsNone(record["error"])
            self.assertEqual(record["messages"][0]["role"], "system")
            self.assertEqual(record["trace"]["turns"][0]["content"], out["output"])

    def test_the_provider_reports_a_run_error_as_an_error(self):
        import pf_provider
        failing = dict(lanes.LANES["A"], run=mock.Mock(side_effect=ProviderError("API error 502")))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(lanes.LANES, {"A": failing}):
            out = pf_provider.call_api("A-01", {"config": {"model": "vendor/model-x", "mode": "dry",
                                                           "run": tmp}},
                                       {"vars": {"lane": "A", "case_id": "A-01"}})
        self.assertEqual(out["error"], "API error 502")

    def test_a_dry_run_of_lane_a_passes_every_case_through_promptfoo(self):
        """The whole path: promptfoo, the provider, the assertion and the result file."""
        with mock.patch("sys.stdout", new_callable=io.StringIO) as printed:
            code = run.main(["A", "--model", "anthropic/claude-haiku-5.5", "--dry-run",
                             "--repeat", "1", "--jobs", "2"])
        self.assertEqual(code, 0, printed.getvalue())
        self.assertRegex(printed.getvalue(), r"A\s+anthropic/claude-haiku-5\.5\s+15/15 ")


# --- results and decisions -------------------------------------------------------


def result(lane="B", model="vendor/model-x", split="all", runs=3, cases=(), **meta):
    base = {"lane": lane, "model": model, "split": split, "runs": runs, "dry_run": False,
            "partial": False, "errors": 0, "budget_stop": None, "kit_sha256": "k",
            "skills_sha256": skillmod.bundle_sha256(), "critical_cases": 0}
    base.update(meta)
    entries = [{"id": i, "critical": c, "runs": runs, "passes": p, "errors": 0,
                "protects": "S-16"} for i, c, p in cases]
    base["critical_cases"] = sum(1 for _, c, _ in cases if c)
    return {"meta": base, "decision": {}, "cases": entries}


class TestDecisions(unittest.TestCase):
    """E-08: what a result decides, and when it may not decide."""

    def test_a_result_that_observed_no_model_or_too_few_runs_decides_nothing(self):
        for meta in ({"dry_run": True}, {"partial": True}, {"errors": 1},
                     {"budget_stop": "cap"}, {"runs": 2}):
            with self.subTest(meta=meta):
                summary = result(cases=[("B-01", True, 3)], **meta)
                if "runs" in meta:
                    summary["cases"][0].update(runs=2, passes=2)
                self.assertEqual(run.decide_supported(summary)["verdict"], "undecided")
                self.assertEqual(run.decide_ship(summary, Path("/nonexistent"))["verdict"],
                                 "undecided")

    def test_support_needs_every_case(self):
        summary = result(split="dev", cases=[("B-01", True, 3)])
        self.assertEqual(run.decide_supported(summary)["verdict"], "undecided")

    def test_a_critical_case_that_failed_a_run_withholds_support(self):
        summary = result(cases=[("B-01", True, 3), ("B-02", True, 2), ("B-03", False, 0)])
        verdict = run.decide_supported(summary)
        self.assertEqual((verdict["verdict"], verdict["critical_failing"]),
                         ("not supported", ["B-02"]))

    def test_a_standard_case_does_not_withhold_support(self):
        summary = result(cases=[("B-01", True, 3), ("B-03", False, 0)])
        self.assertEqual(run.decide_supported(summary)["verdict"], "supported")

    def test_the_ship_decision_compares_with_the_baseline_on_the_same_kit(self):
        with tempfile.TemporaryDirectory() as results:
            baseline = result(cases=[("B-01", True, 3), ("B-02", False, 3), ("B-03", False, 1)])
            run.write_json(Path(results, "2026-01-01-B-x-k3-all.json"), baseline)
            other_kit = result(cases=[("B-01", True, 0)], kit_sha256="other")
            run.write_json(Path(results, "2026-01-02-B-x-k3-all.json"), other_kit)
            now = result(cases=[("B-01", True, 3), ("B-02", False, 2), ("B-03", False, 0)])
            verdict = run.decide_ship(now, Path(results))
            self.assertEqual((verdict["verdict"], verdict["regressions"], verdict["baseline"]),
                             ("hold", ["B-02"], "2026-01-01-B-x-k3-all.json"))
            now["cases"][1]["passes"] = 3
            self.assertEqual(run.decide_ship(now, Path(results))["verdict"], "ship")

    def test_without_a_baseline_on_this_kit_the_result_becomes_one(self):
        with tempfile.TemporaryDirectory() as results:
            verdict = run.decide_ship(result(cases=[("B-01", True, 3)]), Path(results))
            self.assertEqual(verdict["verdict"], "undecided")
            self.assertIn("baseline", verdict["reason"])

    def test_only_a_clean_complete_run_is_committed(self):
        self.assertEqual(run.destination(result(date="2026-01-01"), "s").parent, run.RESULTS)
        for meta in ({"dry_run": True}, {"partial": True}, {"errors": 1}):
            with self.subTest(meta=meta):
                path = run.destination(result(date="2026-01-01", **meta), "s")
                self.assertEqual(path.parent, run.RAW / "s")

    def test_the_kit_digest_leaves_out_the_recorded_states_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp, "kit")
            shutil.copytree(str(EVALS), str(kit), ignore=shutil.ignore_patterns(
                ".venv", ".cache", "results", "__pycache__"))
            first = run.kit_sha256(kit)
            states = kit / "cases" / "decision" / "states.json"
            states.write_text(states.read_text(encoding="utf-8") + " ", encoding="utf-8")
            self.assertEqual(run.kit_sha256(kit), first)
            case = kit / "cases" / "selection.json"
            case.write_text(case.read_text(encoding="utf-8") + " ", encoding="utf-8")
            self.assertNotEqual(run.kit_sha256(kit), first)

    def test_the_splits_divide_lane_b(self):
        dev = set(c["id"] for c in run.select("B", "dev"))
        held = set(c["id"] for c in run.select("B", "holdout"))
        every = set(c["id"] for c in run.select("B", "all"))
        self.assertEqual(dev & held, set())
        self.assertEqual(dev | held, every)
        self.assertEqual(held, run.holdout_ids())

    def test_the_table_marks_a_result_on_older_skills_stale(self):
        with tempfile.TemporaryDirectory() as results:
            roster = Path(results, "models.json")
            roster.write_text(json.dumps({"gate": "vendor/model-x", "caps": {}, "models": [
                {"id": "vendor/model-x", "provider": {"order": ["v"]}},
                {"id": "vendor/model-y", "provider": {"order": ["v"]}}]}), encoding="utf-8")
            summary = result(cases=[("B-01", True, 3)])
            summary["decision"]["supported"] = run.decide_supported(summary)
            run.write_json(Path(results, "2026-01-01-B-x-k3-all.json"), summary)
            table = run.supported_table(Path(results), roster)
            self.assertIn("| vendor/model-x (gate) | v | 1 of 1 passed every run", table)
            self.assertIn("supported (2026-01-01-B-x-k3-all.json)", table)
            self.assertIn("| vendor/model-y | v | no result | no result | not yet run |", table)
            summary["meta"]["skills_sha256"] = "older"
            run.write_json(Path(results, "2026-01-01-B-x-k3-all.json"), summary)
            self.assertIn("stale", run.supported_table(Path(results), roster))

    def test_the_documented_table_is_the_one_the_results_give(self):
        text = (ROOT / "docs" / "evals.md").read_text(encoding="utf-8")
        begin = text.index(run.TABLE_BEGIN) + len(run.TABLE_BEGIN)
        self.assertEqual(text[begin:text.index(run.TABLE_END)].strip("\n"),
                         run.supported_table().strip("\n"),
                         "docs/evals.md is stale: run.py --table --write")


# --- traceability, the held-out split and the roster -----------------------------


#: The skill rules a model can break at run time, which the tool cannot enforce:
#: each must be protected by at least one case. Every other rule in the
#: skill-text catalogue is about the text itself, with the reason here.
BEHAVIOURAL = ("S-01", "S-03", "S-04", "S-05", "S-08", "S-09", "S-11", "S-13", "S-15", "S-16",
               "S-17", "S-18", "S-19", "S-20", "S-21", "S-22", "S-23", "S-24")
TEXT_ONLY = {
    "S-02": "only crayon-write declares a write tool: frontmatter, checked by skill_lint",
    "S-06": "the evidence verbs: the tool computes and checks every digest itself",
    "S-07": "the honesty guards are words the skills must not contain",
    "S-10": "the references tree names only flags and fields the tool has",
    "S-12": "the walk's two refusal lists are complete: text against the tool",
    "S-14": "context work goes through the context verbs: text against the tool",
    "S-25": "the rules the first sweep found too weak, pinned as text",
    "S-26": "no skill names an eval fixture",
    "S-27": "the rules the first sweep found too weak, pinned as text",
}


def skill_text_rules():
    text = (ROOT / "tests" / "test_skill_text.py").read_text(encoding="utf-8")
    return set(re.findall(r"\bS-\d\d\b", text))


class TestTraceability(unittest.TestCase):
    """E-09: every case protects a named rule, and every rule a model can break has a case."""

    def cases(self):
        return lanes.load_a() + lanes.load_b()

    def test_every_case_names_its_rule_and_whether_it_is_critical(self):
        rules = skill_text_rules() | {"catalog"}
        for case in self.cases():
            with self.subTest(case=case["id"]):
                self.assertIn(case.get("protects"), rules)
                self.assertIsInstance(case.get("critical"), bool)

    def test_every_rule_a_model_can_break_has_a_case(self):
        protected = set(case["protects"] for case in self.cases())
        for rule in BEHAVIOURAL:
            with self.subTest(rule=rule):
                self.assertIn(rule, protected)

    def test_every_skill_text_rule_is_either_behavioural_or_text(self):
        rules = skill_text_rules()
        self.assertGreaterEqual(len(rules), 20, "vacuous: the catalogue did not parse")
        self.assertEqual(rules, set(BEHAVIOURAL) | set(TEXT_ONLY))

    def test_lane_a_protects_the_catalog_and_is_never_critical(self):
        for case in lanes.load_a():
            self.assertEqual((case["protects"], case["critical"]), ("catalog", False))

    def test_the_held_out_split_spans_every_case_file(self):
        held = run.holdout_ids()
        cases = lanes.load_b()
        self.assertLessEqual(held, set(c["id"] for c in cases))
        for group in sorted(set(c["group"] for c in cases)):
            members = [c["id"] for c in cases if c["group"] == group]
            with self.subTest(group=group):
                self.assertTrue(set(members) & held, "no held-out case")
                self.assertTrue(set(members) - held, "no dev case")
        share = len(held) / float(len(cases))
        self.assertTrue(0.2 <= share <= 0.35, share)
        self.assertTrue(any(c["critical"] for c in cases if c["id"] in held))
        self.assertTrue(any(not c["critical"] for c in cases if c["id"] in held))


class TestRoster(unittest.TestCase):
    """E-10: the certified models, each pinned and each with its reason."""

    def test_every_model_is_pinned_to_one_zero_retention_backend(self):
        roster, by_id = run.load_roster()
        self.assertIn(roster["gate"], by_id)
        self.assertLess(roster["caps"]["per_model_usd"], roster["caps"]["sweep_usd"])
        for model in roster["models"]:
            with self.subTest(model=model["id"]):
                self.assertTrue(model["why"])
                self.assertEqual(len(model["provider"]["order"]), 1)
                self.assertIs(model["provider"]["allow_fallbacks"], False)
                self.assertIs(model["provider"]["zdr"], True)
                self.assertEqual(len(model["price_per_mtok"]), 2)
                self.assertNotIn("temperature", model)
                self.assertNotIn("role", model)
        self.assertEqual(set(roster) - {"_comment", "caps", "gate", "models"}, set())


class TestDispositions(unittest.TestCase):
    """E-11: every case a certified model did not pass every run has a recorded decision."""

    KINDS = ("skill-fix", "case-fix", "limitation")

    def load(self):
        return json.loads((EVALS / "dispositions.json").read_text(encoding="utf-8"))["dispositions"]

    def test_every_record_is_well_formed(self):
        known = set(case["id"] for case in lanes.load_a() + lanes.load_b())
        roster = set(model["id"] for model in run.load_roster()[0]["models"])
        for record in self.load():
            with self.subTest(record=record):
                self.assertIn(record["id"], known)
                self.assertIn(record["model"], roster)
                self.assertIn(record["kind"], self.KINDS)
                self.assertTrue(record["note"].strip())
                self.assertTrue(record["ref"].strip())

    def test_every_failing_case_in_the_latest_results_has_a_record(self):
        latest = {}
        for path, result in run.committed():
            meta = result["meta"]
            latest[(meta["lane"], meta["model"], meta["split"])] = (path, result)
        recorded = set((r["id"], r["model"]) for r in self.load())
        for (lane, model, split), (path, result) in sorted(latest.items()):
            for entry in result["cases"]:
                if entry["passes"] < entry["runs"]:
                    with self.subTest(result=path.name, case=entry["id"]):
                        self.assertIn((entry["id"], model), recorded,
                                      "%s: %s passed %d of %d runs and has no disposition"
                                      % (path.name, entry["id"], entry["passes"], entry["runs"]))

    def test_a_limitation_on_a_critical_case_withholds_support(self):
        limits = set((r["id"], r["model"]) for r in self.load() if r["kind"] == "limitation")
        for path, result in run.committed():
            critical = set(e["id"] for e in result["cases"] if e["critical"])
            hit = [case for case, model in limits
                   if model == result["meta"]["model"] and case in critical]
            if hit and result["decision"]["supported"]["verdict"] == "supported":
                self.fail("%s says supported, but %s is a recorded limitation"
                          % (path.name, ", ".join(hit)))


if __name__ == "__main__":
    unittest.main()
