#!/usr/bin/env python3
"""The model-eval kit's own tests: offline, stdlib only, no key, no network beyond 127.0.0.1.

``validation/evals/`` is dev-time evaluation material: its paid runs are started
by hand and never enter the gate. What the gate CAN hold it to is everything
that does not need a model — the transport's request shape, retries, cache and
spend cap against a fake opener (and one loopback stub server, for what only
urllib can show); every assertion kind against hand-built turns; and every case
file against its own oracle, so a broken expectation is caught here rather than
blamed on a model in a paid run.
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

#: D-07: the tool's version, read from ``crayon.py``'s ``__version__`` line through
#: the lint's ``tool_version``, its one reader. No test here types a version.
TOOL_VERSION = skillmod._load_skill_lint().tool_version(skillmod.REPO)

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
#: The first reads won't / haven't / hasn't and "record", the second "recorded"
#: after the verdict as well as "the record" before it (22 WR-03).
NOTICE_RES = (
    "(?i)\\b(not|nothing|isn['\u2019]t|won['\u2019]t|haven['\u2019]t|hasn['\u2019]t)\\b"
    "[^\\n]{0,60}\\brecord(ed)?\\b",
    "(?i)\\b(fix|redraft)\\b[^\\n]{0,80}\\brecord(s|ed)?\\b|\\brecord(s|ed)?\\b[^\\n.?]{0,40}?"
    "\\b(if|when|once|with)\\s+(a\\s+|your\\s+|you\\s+give\\s+a\\s+)?(verdict\\s+is\\s+a\\s+)?"
    "(fix|redraft)\\b",
)

#: 23 IN-02: the opposite claim, that the answer is never recorded, not even
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


class ReadFails(FakeResponse):
    """A response whose body is lost while it is read: ``read`` raises ``exc``.

    It stands for a call that was answered (its status line and headers came back)
    and whose body never arrived whole (24-36: WR-25 of the review at 5fdfe1b).
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


def client(opener, budget=None, cache_dir=None):
    return OpenRouter(budget or Budget(10.0), cache_dir=cache_dir, api_key="sk-test",
                      sleep=lambda seconds: None, opener=opener)


#: D-24: an empty answer as the stub gives it: no content and no tool call.
EMPTY = {"content": ""}


class CacheRecordingStub(StubProvider):
    """The stub provider, recording each call's ``cache`` argument (D-24)."""

    def __init__(self, responder=None):
        StubProvider.__init__(self, responder)
        self.caches = []

    def complete(self, spec, messages, tools=None, cache=True, scope=None):
        self.caches.append(cache)
        return StubProvider.complete(self, spec, messages, tools=tools, cache=cache,
                                     scope=scope)


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

    def test_an_empty_turn_is_never_cached(self):
        """D-24: an empty turn is re-sent, not replayed, and no later run replays it."""
        with tempfile.TemporaryDirectory() as tmp:
            opener = FakeOpener(ok_body(content=""), ok_body("good"), ok_body("fresh"))
            budget = Budget(10.0)
            paid = OpenRouter(budget, cache_dir=tmp, api_key="test",
                              sleep=lambda seconds: None, opener=opener)
            messages = [{"role": "user", "content": "same"}]
            trace = agent.run_episode(paid, SPEC, messages, None, None, cache=True)
            self.assertEqual(len(opener.requests), 2)
            self.assertEqual(trace.get("retries"), 1)
            self.assertEqual(trace["turns"][-1]["content"], "good")
            for path in Path(tmp).glob("*.json"):
                with self.subTest(cached=path.name):
                    kept = json.loads(path.read_text(encoding="utf-8"))
                    self.assertFalse(openrouter.empty_turn(kept))
            again = paid.complete(SPEC, messages)
            self.assertEqual(again["content"], "fresh")
            self.assertFalse(again["cached"])
            self.assertEqual(len(opener.requests), 3)
            self.assertAlmostEqual(budget.spent, 3 * 0.0123)

    def judge_messages(self, graded):
        """The messages ``grade.check_judge`` sends for rubric ``x`` over ``graded``."""
        prompt = grade.JUDGE_INSTRUCTIONS.format(
            rubric="x", context="", response=grade.render_turns(graded))
        return [{"role": "user", "content": prompt}]

    def assert_cached_verdict(self, tmp):
        entries = list(Path(tmp).glob("*.json"))
        self.assertEqual(len(entries), 1, "the cache holds %d judge entries" % len(entries))
        kept = json.loads(entries[0].read_text(encoding="utf-8"))
        try:
            grade.parse_verdict(kept["content"])
        except grade.GradeError:
            self.fail("the cached judge reply is not the graded one: %r" % kept["content"])

    def test_an_unparsable_judge_reply_is_not_cached(self):
        """24-17, WR-04: the retried reply that is graded is cached, not the unparsable
        one, so a later cached run replays the graded verdict with no call and no retry."""
        verdict = run.stub_judge(None, None, None)
        spec, graded = {"kind": "judge", "rubric": "x"}, trace(turn("hello"))
        with tempfile.TemporaryDirectory() as tmp:
            opener = FakeOpener(ok_body("not json"), ok_body(verdict), ok_body(verdict))
            paid = client(opener, Budget(10.0), cache_dir=tmp)
            ctx = {"judge": (paid, SPEC)}
            first = grade.check_judge(spec, graded, ctx)
            self.assertTrue(first["pass"], first["feedback"])
            self.assertEqual(ctx["judge_retries"], 1)
            self.assertEqual(len(opener.requests), 2)
            self.assert_cached_verdict(tmp)
            again_ctx = {"judge": (paid, SPEC)}
            again = grade.check_judge(spec, graded, again_ctx)
            self.assertEqual(len(opener.requests), 2, "a cached judge verdict made a call")
            self.assertNotIn("judge_retries", again_ctx)
            self.assertEqual((again["pass"], again["score"]), (first["pass"], first["score"]))

    def test_a_cached_unparsable_judge_reply_is_replaced_by_the_graded_one(self):
        """24-17, WR-04: an unparsable reply already in the cache, as the kit left one
        before this fix, is re-asked once and replaced by the graded verdict."""
        verdict = run.stub_judge(None, None, None)
        spec, graded = {"kind": "judge", "rubric": "x"}, trace(turn("hello"))
        with tempfile.TemporaryDirectory() as tmp:
            opener = FakeOpener(ok_body("not json"), ok_body(verdict), ok_body(verdict))
            paid = client(opener, Budget(10.0), cache_dir=tmp)
            stale = paid.complete(SPEC, self.judge_messages(graded))
            self.assertEqual(stale["content"], "not json")
            ctx = {"judge": (paid, SPEC)}
            out = grade.check_judge(spec, graded, ctx)
            self.assertTrue(out["pass"], out["feedback"])
            self.assertEqual(ctx["judge_retries"], 1)
            self.assertEqual(len(opener.requests), 2)
            self.assert_cached_verdict(tmp)
            again_ctx = {"judge": (paid, SPEC)}
            grade.check_judge(spec, graded, again_ctx)
            self.assertEqual(len(opener.requests), 2, "the stale entry was re-asked again")
            self.assertNotIn("judge_retries", again_ctx)

    def test_a_judge_reply_unparsable_twice_leaves_no_cache_entry(self):
        """24-17, WR-04: two unparsable replies are the run-level error, and neither is
        left in the cache for a later run to replay."""
        spec, graded = {"kind": "judge", "rubric": "x"}, trace(turn("hello"))
        with tempfile.TemporaryDirectory() as tmp:
            opener = FakeOpener(ok_body("not json"), ok_body("still not json"))
            paid = client(opener, Budget(10.0), cache_dir=tmp)
            with self.assertRaisesRegex(grade.GradeError, "judge returned no JSON object"):
                grade.check_judge(spec, graded, {"judge": (paid, SPEC)})
            self.assertEqual(len(opener.requests), 2)
            self.assertEqual(list(Path(tmp).glob("*.json")), [],
                             "an unparsable judge reply was left in the cache")

    def test_a_cache_that_cannot_be_written_or_dropped_is_a_provider_error(self):
        """24-20, IN-03: a cache entry that cannot be written or dropped is a
        ``ProviderError`` naming the cache, so the runner records it as a run-level
        error instead of an ``OSError`` stopping the sweep."""
        msgs = [{"role": "user", "content": "same"}]
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "cache"
            blocker.write_text("", encoding="utf-8")
            paid = client(FakeOpener(ok_body("x")), Budget(10.0), cache_dir=str(blocker))
            for label, call in (
                    ("remember", lambda: paid.remember(SPEC, msgs, {"content": "y",
                                                                    "tool_calls": []})),
                    ("forget", lambda: paid.forget(SPEC, msgs)),
                    ("complete", lambda: paid.complete(SPEC, msgs))):
                with self.subTest(call=label):
                    raised = None
                    try:
                        call()
                    except Exception as exc:  # the type is the assertion
                        raised = exc
                    self.assertIsInstance(raised, ProviderError,
                                          "%s raised %r" % (label, raised))
                    self.assertIn("cache", str(raised))

    def test_a_cache_entry_is_written_whole_or_not_at_all(self):
        """24-23, WR-02 (329fa95): a write that fails part way leaves neither an entry
        nor a temporary file; the failure is a ``ProviderError`` naming the cache."""
        msgs = [{"role": "user", "content": "same"}]
        with tempfile.TemporaryDirectory() as tmp:
            paid = client(FakeOpener(), Budget(10.0), cache_dir=tmp)
            with mock.patch.object(openrouter.os, "replace",
                                   side_effect=OSError("disk full")):
                with self.assertRaises(ProviderError) as raised:
                    paid.remember(SPEC, msgs, {"content": "y", "tool_calls": [],
                                               "usage": {"cost": 0.0}})
            self.assertIn("cache", str(raised.exception))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [],
                             "a failed cache write left a file behind")

    def test_an_unreadable_cache_entry_is_a_miss(self):
        """24-23, WR-02 (329fa95): an entry that does not read as a turn, truncated,
        not an object, or with no usage, is a miss: the call is made, its turn
        replaces the entry, and the next identical call is served from the cache.
        24-27, WR-12 (aac605a): so is an entry that is not a whole turn, or holds an
        empty one, which a run would otherwise crash on or re-pay as a retry.
        24-30, WR-14 (1ba4892): and so is one whose ``served_by`` or ``finish_reason``
        is not a string, or whose token count is not finite, which ``run_one`` would
        crash on or write into a summary that is not strict JSON.
        24-33, WR-20 (802e0e3): and so is one whose token count is not an integer
        below the cap, a 400-digit one or a fraction, which raised or was served."""
        msgs = [{"role": "user", "content": "same"}]
        for label, body in (("truncated", '{"content": "x"'), ("a list", "[]"),
                            ("no usage", '{"content": "x"}'),
                            # 24-27: WR-12 (aac605a)
                            ("usage with no token counts",
                             '{"content": "crayon-plan", "usage": {}}'),
                            # 24-27: WR-12 (aac605a)
                            ("an empty turn",
                             '{"content": "", "tool_calls": [], "usage": '
                             '{"prompt_tokens": 1, "completion_tokens": 0}}'),
                            # 24-27: WR-12 (aac605a)
                            ("no tool_calls",
                             '{"content": "x", "usage": '
                             '{"prompt_tokens": 1, "completion_tokens": 1}}'),
                            # 24-27: WR-12 (aac605a)
                            ("a call that is not an object",
                             '{"content": "x", "tool_calls": [1], "usage": '
                             '{"prompt_tokens": 1, "completion_tokens": 1}}'),
                            # 24-30: WR-14 (1ba4892)
                            ("served_by that is a list",
                             '{"content": "x", "tool_calls": [], "finish_reason": "stop", '
                             '"served_by": ["a"], "usage": '
                             '{"prompt_tokens": 1, "completion_tokens": 1}}'),
                            # 24-30: WR-14 (1ba4892)
                            ("finish_reason that is not a string",
                             '{"content": "x", "tool_calls": [], "finish_reason": 1, '
                             '"served_by": "a", "usage": '
                             '{"prompt_tokens": 1, "completion_tokens": 1}}'),
                            # 24-30: WR-14 (1ba4892)
                            ("prompt_tokens that is NaN",
                             '{"content": "x", "tool_calls": [], "finish_reason": "stop", '
                             '"served_by": "a", "usage": '
                             '{"prompt_tokens": NaN, "completion_tokens": 1}}'),
                            # 24-30: WR-14 (1ba4892)
                            ("completion_tokens that is Infinity",
                             '{"content": "x", "tool_calls": [], "finish_reason": "stop", '
                             '"served_by": "a", "usage": '
                             '{"prompt_tokens": 1, "completion_tokens": Infinity}}'),
                            # 24-33: WR-20 (802e0e3)
                            ("prompt_tokens of 400 digits",
                             '{"content": "x", "tool_calls": [], "finish_reason": "stop", '
                             '"served_by": "a", "usage": '
                             '{"prompt_tokens": ' + "9" * 400 + ', "completion_tokens": 1}}'),
                            # 24-33: WR-20 (802e0e3)
                            ("completion_tokens that is fractional",
                             '{"content": "x", "tool_calls": [], "finish_reason": "stop", '
                             '"served_by": "a", "usage": '
                             '{"prompt_tokens": 1, "completion_tokens": 1.5}}')):
            with self.subTest(entry=label), tempfile.TemporaryDirectory() as tmp:
                opener = FakeOpener(ok_body("fresh"))
                paid = client(opener, Budget(10.0), cache_dir=tmp)
                paid._cache_path(SPEC, msgs).write_text(body, encoding="utf-8")
                out = paid.complete(SPEC, msgs)
                self.assertEqual(out["content"], "fresh")
                self.assertFalse(out["cached"])
                self.assertEqual(len(opener.requests), 1)
                again = paid.complete(SPEC, msgs)
                self.assertEqual(again["content"], "fresh")
                self.assertTrue(again["cached"])
                self.assertEqual(len(opener.requests), 1, "the replaced entry was not served")

    def test_a_paid_turn_whose_cache_write_fails_keeps_its_cost(self):
        """24-23, WR-02 (329fa95): a paid call whose cache entry cannot be written
        raises a ``ProviderError`` that carries what was spent and is on no record
        yet: the call itself, the turns an episode already holds, and an empty turn
        the retry discarded (D-24)."""
        msgs = [{"role": "user", "content": "same"}]
        with self.subTest(path="complete"), tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "cache"
            blocker.write_text("", encoding="utf-8")
            budget = Budget(10.0)
            paid = client(FakeOpener(ok_body("x")), budget, cache_dir=str(blocker))
            with self.assertRaises(ProviderError) as raised:
                paid.complete(SPEC, msgs)
            self.assertIn("cache", str(raised.exception))
            self.assertAlmostEqual(raised.exception.cost, 0.0123)
            self.assertAlmostEqual(budget.spent, 0.0123)
        with self.subTest(path="a mid-episode write"), tempfile.TemporaryDirectory() as tmp:
            bogen = [{"id": "b1", "type": "function",
                      "function": {"name": "Bogen", "arguments": "{}"}}]
            paid = client(FakeOpener(ok_body(content=None, calls=bogen), ok_body("done")),
                          Budget(10.0), cache_dir=tmp)
            with mock.patch.object(paid, "remember",
                                   side_effect=[None, ProviderError("cache: disk full")]):
                with self.assertRaises(ProviderError) as raised:
                    agent.run_episode(paid, SPEC, msgs, None, None, cache=True)
            self.assertAlmostEqual(raised.exception.cost, 2 * 0.0123)
        with self.subTest(path="the empty-answer retry"):
            paid = client(FakeOpener(ok_body(content=""), 500, 500, 500, 500, 500),
                          Budget(10.0))
            with self.assertRaises(ProviderError) as raised:
                agent.run_episode(paid, SPEC, msgs, None, None, cache=False)
            self.assertIn("gave up", str(raised.exception))
            self.assertAlmostEqual(raised.exception.cost, 0.0123)

    def test_a_malformed_paid_body_is_charged_then_refused(self):
        """24-33, WR-18 and WR-19 of the review at 802e0e3: a paid response is charged
        before anything reads its shape, so a body the kit cannot read is a
        ``ProviderError`` that starts ``malformed response`` and carries the charge,
        never an ``AttributeError``, ``ValueError`` or ``TypeError`` with the spend on
        no record; ``budget.spent`` moves by the same amount and nothing is cached.
        The charge is the body's readable ``usage.cost``, else ``estimate_cost`` from
        the readable token counts."""
        msgs = [{"role": "user", "content": "same"}]
        estimate = openrouter.estimate_cost(
            SPEC, {"prompt_tokens": 1000, "completion_tokens": 100})

        def choices(body):
            body["choices"] = ["x"]

        def message(body):
            body["choices"][0]["message"] = "hi"

        def cost(body):
            body["usage"]["cost"] = "0.5$"

        def prompt_tokens(body):
            body["usage"]["prompt_tokens"] = "12k"

        def provider(body):
            body["provider"] = ["Vendor"]

        def finish_reason(body):
            body["choices"][0]["finish_reason"] = 1

        def arguments(body):
            body["choices"][0]["message"]["tool_calls"] = [
                {"id": "x1", "type": "function",
                 "function": {"name": "Bash", "arguments": {"command": "ls"}}}]

        def content(body):
            body["choices"][0]["message"]["content"] = ["x"]

        for label, change, charge in (
                ("choices of strings", choices, 0.0123),  # 24-33: WR-19 (802e0e3)
                ("a string message", message, 0.0123),  # 24-33: WR-19 (802e0e3)
                ("a cost of '0.5$'", cost, estimate),  # 24-33: WR-19 (802e0e3)
                ("prompt_tokens of '12k'", prompt_tokens, 0.0123),  # 24-33: WR-19 (802e0e3)
                ("a list provider", provider, 0.0123),  # 24-33: WR-18 (802e0e3)
                ("a numeric finish_reason", finish_reason, 0.0123),  # 24-33: WR-18 (802e0e3)
                ("object arguments", arguments, 0.0123),  # 24-33: WR-18 (802e0e3)
                ("list content", content, 0.0123)):  # 24-33: WR-18 (802e0e3)
            with self.subTest(body=label), tempfile.TemporaryDirectory() as tmp:
                body = ok_body("x")
                change(body)
                budget = Budget(10.0)
                paid = client(FakeOpener(body), budget, cache_dir=tmp)
                try:
                    turn = paid.complete(SPEC, msgs)
                except ProviderError as exc:
                    raised = exc
                except Exception as exc:  # noqa: BLE001 - any other type is the bug
                    self.fail("%s raised %r, not a ProviderError (budget.spent %r)"
                              % (label, exc, budget.spent))
                else:
                    self.fail("%s was read as a turn: %r" % (label, turn))
                self.assertTrue(str(raised).startswith("malformed response"), str(raised))
                self.assertAlmostEqual(raised.cost, charge, delta=1e-9)
                self.assertAlmostEqual(budget.spent, charge, delta=1e-9)
                self.assertEqual(sorted(Path(tmp).glob("*.json")), [],
                                 "a malformed body was cached")

    def test_a_lost_answer_is_charged_once_and_never_retried(self):
        """24-36: WR-25 of the review at 5fdfe1b. A call whose status line came back
        and whose body is lost while it is read was answered and may be billed: it
        is an ``AnswerLost`` (a ``ProviderError`` starting ``transport:`` and naming
        the exception's type) after exactly one request, never retried, and charged
        ``lost_answer_cost`` on the cap and on the error, with nothing cached. A
        ``URLError`` from the opener (the connection or the send failed, so the
        provider never held the whole request) is still retried (24-38: CR-13 of the
        review at fe0d6a0). The three answered arms the module docstring names as
        uncharged stay at 0.0 after one request."""
        msgs = [{"role": "user", "content": "same"}]

        def estimate(request):
            # SPEC's price over the bytes sent as prompt and max_tokens as completion.
            return (len(request.data) * 1.0 + 512 * 2.0) / 1e6

        def raised_by(label, paid):
            try:
                turn = paid.complete(SPEC, msgs)
            except ProviderError as exc:
                return exc
            except Exception as exc:  # noqa: BLE001 - any other type is the bug
                self.fail("%s escaped as %s: %r, not a ProviderError"
                          % (label, type(exc).__name__, exc))
            self.fail("%s was retried into a turn: %r" % (label, turn))

        for exc in (http.client.IncompleteRead(b"{", 10),  # 24-36: WR-25 (5fdfe1b)
                    socket.timeout("timed out"),  # 24-36: WR-25 (5fdfe1b)
                    ConnectionResetError("reset"),  # 24-36: WR-25 (5fdfe1b)
                    ssl.SSLError("bad record mac")):  # 24-36: WR-25 (5fdfe1b)
            label = type(exc).__name__
            with self.subTest(read_fails=label), tempfile.TemporaryDirectory() as tmp:
                budget = Budget(10.0)
                opener = FakeOpener(ReadFails(exc), ok_body("x"))
                raised = raised_by(label, client(opener, budget, cache_dir=tmp))
                self.assertTrue(str(raised).startswith("transport:"), str(raised))
                self.assertIn(label, str(raised))
                self.assertEqual(len(opener.requests), 1, "a lost answer was retried")
                charge = estimate(opener.requests[0])
                self.assertAlmostEqual(raised.cost, charge, delta=1e-9)
                self.assertAlmostEqual(budget.spent, charge, delta=1e-9)
                self.assertAlmostEqual(
                    openrouter.lost_answer_cost(SPEC, json.loads(opener.requests[0].data)),
                    charge, delta=1e-9)
                self.assertEqual(sorted(Path(tmp).glob("*.json")), [],
                                 "a lost answer was cached")
        for exc in (
                urllib.error.URLError("refused"),  # 24-36: WR-25 (5fdfe1b) guard
                urllib.error.URLError(socket.timeout("timed out")),  # 24-38: CR-13 (fe0d6a0) guard
        ):
            with self.subTest(opener_raises=type(exc).__name__):
                budget = Budget(10.0)
                opener = FakeOpener(exc, ok_body("x"))
                turn = client(opener, budget).complete(SPEC, msgs, cache=False)
                self.assertEqual(turn["content"], "x")
                self.assertEqual(len(opener.requests), 2)
                self.assertAlmostEqual(budget.spent, 0.0123, delta=1e-9)
        for label, first in (
                ("a non-2xx status", 400),  # 24-36: WR-25 (5fdfe1b) uncharged guard
                ("a 2xx body that is not JSON",  # 24-36: WR-25 (5fdfe1b) uncharged guard
                 FakeResponse(b"<html>bad gateway</html>")),
                ("an API error body",  # 24-36: WR-25 (5fdfe1b) uncharged guard
                 {"error": {"code": 402, "message": "insufficient credits"}})):
            with self.subTest(uncharged=label):
                budget = Budget(10.0)
                opener = FakeOpener(first, ok_body("x"))
                raised = raised_by(label, client(opener, budget))
                self.assertEqual(len(opener.requests), 1)
                self.assertEqual(raised.cost, 0.0)
                self.assertEqual(budget.spent, 0.0)

    def test_a_failure_after_the_request_is_sent_is_an_answer_lost(self):
        """24-38: CR-13 of the review at fe0d6a0. urllib sends the whole request and
        then waits for the status line, and only a failure of the connection or the
        send is wrapped as a ``URLError``. Any other ``OSError`` or ``HTTPException``
        from the opener comes after the provider holds the whole request, which may
        run and be billed. So it is an ``AnswerLost`` (a ``ProviderError`` starting
        ``transport:`` that names the exception's type) after exactly one request,
        never retried, and charged ``lost_answer_cost`` on the cap and on the error,
        with nothing cached. The last subtest shows that urllib itself delivers a
        status-line timeout that way, through a loopback stub server on 127.0.0.1."""
        msgs = [{"role": "user", "content": "same"}]

        def raised_by(label, paid):
            try:
                turn = paid.complete(SPEC, msgs)
            except ProviderError as exc:
                return exc
            except Exception as exc:  # noqa: BLE001 - any other type is the bug
                self.fail("%s escaped as %s: %r, not a ProviderError"
                          % (label, type(exc).__name__, exc))
            self.fail("%s was retried into a turn: %r" % (label, turn))

        for exc in (socket.timeout("timed out"),  # 24-38: CR-13 (fe0d6a0)
                    ConnectionResetError("reset"),  # 24-38: CR-13 (fe0d6a0)
                    http.client.RemoteDisconnected(  # 24-38: CR-13 (fe0d6a0)
                        "Remote end closed connection without response"),
                    http.client.BadStatusLine("garbled")):  # 24-38: CR-13 (fe0d6a0)
            label = type(exc).__name__
            with self.subTest(opener_raises=label), tempfile.TemporaryDirectory() as tmp:
                budget = Budget(10.0)
                opener = FakeOpener(exc, ok_body("x"))
                raised = raised_by(label, client(opener, budget, cache_dir=tmp))
                self.assertIsInstance(raised, openrouter.AnswerLost)
                self.assertTrue(str(raised).startswith("transport:"), str(raised))
                self.assertIn(label, str(raised))
                self.assertEqual(len(opener.requests), 1, "a call sent whole was retried")
                charge = (len(opener.requests[0].data) * 1.0 + 512 * 2.0) / 1e6
                self.assertAlmostEqual(raised.cost, charge, delta=1e-9)
                self.assertAlmostEqual(budget.spent, charge, delta=1e-9)
                self.assertAlmostEqual(
                    openrouter.lost_answer_cost(SPEC, json.loads(opener.requests[0].data)),
                    charge, delta=1e-9)
                self.assertEqual(sorted(Path(tmp).glob("*.json")), [],
                                 "a lost answer was cached")

        # 24-38: CR-13 (fe0d6a0) loopback
        with self.subTest(through="a loopback stub server"):
            served = []
            received = threading.Event()
            release = threading.Event()

            class Stub(http.server.BaseHTTPRequestHandler):
                """Reads the whole request, counts it and never answers."""

                def do_POST(self):
                    served.append(self.rfile.read(int(self.headers["Content-Length"])))
                    received.set()
                    release.wait(30)

                def log_message(self, *args):
                    pass

            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True).start()
            # Cleanups run last in, first out: release, then shutdown, then close.
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            self.addCleanup(release.set)
            budget = Budget(10.0)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
            paid = OpenRouter(budget, api_key="sk-test", retries=2, timeout=0.5,
                              sleep=lambda seconds: None, opener=opener)
            url = "http://127.0.0.1:%d/api/v1/chat/completions" % server.server_port
            with mock.patch.object(openrouter, "API_URL", url):
                raised = raised_by("a status-line timeout", paid)
            self.assertIsInstance(raised, openrouter.AnswerLost)
            self.assertTrue(received.wait(5), "the stub server was never reached")
            self.assertEqual(len(served), 1, "a call sent whole was retried")
            charge = openrouter.lost_answer_cost(SPEC, json.loads(served[0]))
            self.assertAlmostEqual(raised.cost, charge, delta=1e-9)
            self.assertAlmostEqual(budget.spent, charge, delta=1e-9)

    def test_an_api_error_body_of_any_shape_is_a_provider_error(self):
        """24-36: WR-24 of the review at 5fdfe1b. An API error body (``error`` with no
        ``choices``) is a ``ProviderError`` starting ``API error`` whatever the shape
        of its ``error`` or its ``code``, never an ``AttributeError`` or a
        ``TypeError`` with the case's paid turns on no record; only an integer
        ``code`` in the retry statuses is retried."""
        msgs = [{"role": "user", "content": "same"}]
        for label, body in (
                ("a string error", {"error": "overloaded"}),  # 24-36: WR-24 (5fdfe1b)
                ("a list error", {"error": ["x"]}),  # 24-36: WR-24 (5fdfe1b)
                ("a list code",  # 24-36: WR-24 (5fdfe1b)
                 {"error": {"code": [429], "message": "x"}}),
                ("a bool code",  # 24-36: WR-24 (5fdfe1b)
                 {"error": {"code": True, "message": "x"}})):
            with self.subTest(body=label):
                budget = Budget(10.0)
                opener = FakeOpener(body, ok_body("x"))
                try:
                    turn = client(opener, budget).complete(SPEC, msgs)
                except ProviderError as exc:
                    raised = exc
                except Exception as exc:  # noqa: BLE001 - any other type is the bug
                    self.fail("%s raised %s: %r, not a ProviderError"
                              % (label, type(exc).__name__, exc))
                else:
                    self.fail("%s was read as a turn: %r" % (label, turn))
                self.assertTrue(str(raised).startswith("API error"), str(raised))
                self.assertEqual(len(opener.requests), 1)
                self.assertEqual(budget.spent, 0.0)
        with self.subTest(guard="an integer code in the retry statuses"):
            opener = FakeOpener({"error": {"code": 429, "message": "busy"}}, ok_body("x"))
            turn = client(opener).complete(SPEC, msgs, cache=False)
            self.assertEqual(turn["content"], "x")
            self.assertEqual(len(opener.requests), 2)

    def test_a_budget_stop_mid_case_keeps_its_cost(self):
        """24-27, WR-11 (aac605a): a ``BudgetExceeded`` that stops a case after a paid
        call carries that call's cost, as a ``ProviderError`` does: the turn an episode
        already holds, and the empty turn whose retry the cap refused (D-24)."""
        msgs = [{"role": "user", "content": "same"}]
        with self.subTest(path="a mid-episode stop"):
            bogen = [{"id": "b1", "type": "function",
                      "function": {"name": "Bogen", "arguments": "{}"}}]
            budget = Budget(0.01)
            opener = FakeOpener(ok_body(content=None, calls=bogen), ok_body("done"))
            paid = client(opener, budget)
            with self.assertRaises(BudgetExceeded) as raised:
                agent.run_episode(paid, SPEC, msgs, None, None, cache=False)
            self.assertAlmostEqual(raised.exception.cost, 0.0123)
            self.assertAlmostEqual(budget.spent, 0.0123)
            self.assertEqual(len(opener.requests), 1)
        with self.subTest(path="the empty-answer retry"):
            paid = client(FakeOpener(ok_body(content=""), ok_body("x")), Budget(0.01))
            with self.assertRaises(BudgetExceeded) as raised:
                agent.run_episode(paid, SPEC, msgs, None, None, cache=False)
            self.assertAlmostEqual(raised.exception.cost, 0.0123)

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

    def test_question_count_reads_only_a_list_of_questions(self):
        """21 IN-03: a ``questions`` argument that is a JSON string is not a list
        of questions, so its characters are not counted as questions."""
        typed = episode({"type": "call", "call": call("AskUserQuestion",
                                                      questions='["a?", "b?"]')}, turn())
        out = self.counts({"max": 0}, typed)
        self.assertTrue(out["pass"], out["feedback"])
        self.assertFalse(self.counts({"min": 1}, typed)["pass"])
        two = self.asked("a?", "b?")
        self.assertTrue(self.counts({"min": 2, "max": 2}, two)["pass"])

    def test_question_count_ignores_an_unclosed_final_fence(self):
        """21 IN-03: a fence left open runs to the end of the reply, so the
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
            # 23 IN-03: the token alone in code after a bare `Next:` is an offer,
            # and so is a PR offer quoted whole, since `open a PR` is never a
            # routed token.
            trace(turn("Next: `publish`")),
            trace(turn("The page is accepted. `Next: open a PR`")),
            trace(turn("The page is accepted. Next: `open a PR`")),
        ], missed=[
            # D-07: the version the traces quote is the tool's own, never typed.
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
            # 22 WR-02 (third review): an adverb, a quantifier or a clause after
            # the noun leaves "there may be errors" blanket; so does every detail
            # and everything else.
            trace(turn("There may be errors I missed.")),
            trace(turn("There may still be errors.")),
            trace(turn("There might be some errors.")),
            trace(turn("There may be a few mistakes.")),
            trace(turn("There may be errors here and there.")),
            trace(turn("I can't verify every detail.")),
            trace(turn("I can't verify everything else.")),
            # 24-17: WR-03 probe
            trace(turn("I drafted reference/config.md from config.py, but some of it may be "
                       "wrong.")),
            # 24-17: WR-03 probe
            trace(turn("Draft written to reference/config.md; everything may be wrong.")),
            # 24-17: WR-03 probe
            trace(turn("Staged .crayon/staging/cfg/draft/reference/config.md. This could be "
                       "wrong in places.")),
            # 24-17: WR-03 probe
            trace(turn("Everything in the draft might be wrong.")),
            # 24-17: WR-03 probe
            trace(turn("Everything may be wrong.")),
            # 24-17: WR-03 probe
            trace(turn("Everything on the page could be wrong.")),
            # 24-17: WR-03 probe
            trace(turn("Draft at reference/config.md:13. It may be wrong.")),
            # 24-20: WR-01 probe
            trace(turn("I drafted reference/config.md from config.py but some of it may be "
                       "wrong.")),
            # 24-20: WR-01 probe
            trace(turn("Draft written to v1.2/config.py. Everything may be wrong.")),
            # 24-20: WR-01 probe
            trace(turn("Draft at .crayon/staging/cfg/draft/reference/config.md:13; it may be "
                       "wrong.")),
            # 24-20: WR-01 probe
            trace(turn("Everything may be wrong, but see config.py:12.")),
            # 24-23: IN-01 (329fa95) probe
            trace(turn("Everything may be wrong, etc. See config.py:12.")),
            # 24-23: IN-01 (329fa95) probe
            trace(turn("Some of it may be wrong, e.g. the defaults.")),
            # 24-23: IN-01 (329fa95) probe
            trace(turn("The page may be wrong. E.g. config.py:12 sets 5.")),
            # 24-23: IN-01 (329fa95) probe
            trace(turn("Everything may be wrong etc.")),
            # 24-26: P-24-73 guard
            trace(turn("I read config.py, etc.  Everything may be wrong.")),
            # 24-26: P-24-73 guard
            trace(turn("I read config.py, etc. Everything may be wrong.")),
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
            # 22 WR-01 (third review): a claim located on the page or in the draft,
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
            # 22 WR-02 (third review): there may be errors in a named thing is grounded.
            trace(turn("There may be errors in the retry table at reference/config.md:13; "
                       "config.py:12 sets 5.")),
            trace(turn("There may be errors in the retry table.")),
            # 24-20: WR-01 keep
            trace(turn("- F-2 [must-fix] reference/config.md:13 says the default is 3; "
                       "config.py:12 sets 5, so the page may be wrong.")),
            # 24-20: WR-01 keep
            trace(turn("- F-2 \"retries default to 3\" (reference/config.md:13): config.py:12 "
                       "sets 5, so the page may be wrong.")),
            # 24-20: WR-01 keep
            trace(turn("Per config.py:12 the page may be wrong.")),
            # 24-20: WR-01 keep
            trace(turn("F-1 (reference/config.md:13), so it may be wrong.")),
            # 24-20: WR-01 keep
            trace(turn("F-2 config.md:13 — it may be wrong.")),
            # 24-20: WR-01 keep
            trace(turn("The page may be wrong: v1.2/config.py sets 5.")),
            # 24-20: WR-01 keep
            trace(turn("It may be wrong, per .crayon/staging/cfg/draft/reference/config.md:13.")),
            # 24-23: IN-01 (329fa95) keep
            trace(turn("The page may be wrong, e.g. config.py:12 sets 5.")),
            # 24-23: IN-01 (329fa95) keep
            trace(turn("The page may be wrong, i.e. config.py:12 sets 5, not 3.")),
            # 24-23: IN-01 (329fa95) keep
            trace(turn("The page may be wrong on retries, timeouts, etc. per config.py:12.")),
            # 24-23: IN-01 (329fa95) keep
            trace(turn("See config.py:12, e.g. it may be wrong.")),
            # 24-26: IN-09 (aac605a) keep
            trace(turn("Everything may be wrong, etc. (see config.py:12)")),
            # 24-26: IN-09 (aac605a) probe
            trace(turn("I read config.py, etc. (it may be wrong).")),
        ])

    def test_hedge_has_no_runaway_backtracking(self):
        pattern = lanes._expand("@HEDGE")
        for text in (("please may might could I verify " * 1600)[:50000],
                     ("I can not fully verified the some of " * 1400)[:50000],
                     # 22 WR-01, WR-02: the line scan and the cite and noun lookaheads.
                     ("on the page it may be wrong a/b/c " * 1600)[:50000],
                     ("there may still be some errors in the it\n" * 1300)[:50000],
                     # 24-17: WR-03, repeated hedges with a cite at the very end.
                     ("it may be wrong " * 3300)[:49990] + " x.py",
                     # 24-20: WR-01, a cite before the hedge, a dotted path, many
                     # sentence stops before a hedge with a cite, and repeated `but`.
                     ("x.py it may be wrong " * 3000)[:50000],
                     ("v1.2/" * 10000)[:50000],
                     ("a. " * 16700)[:50000] + " it may be wrong x.py",
                     "but " * 12500,
                     # 24-23: IN-01 (329fa95), the abbreviation lookbehinds over
                     # many "e.g.", "etc." and "i.e." before a hedge.
                     ("e.g. " * 10000)[:50000] + " it may be wrong x.py",
                     ("etc. " * 10000)[:50000] + " it may be wrong",
                     ("i.e. it " * 7000)[:50000] + " may be wrong",
                     # 24-26: IN-09 (aac605a), the clause start's whitespace run
                     # after "etc." before a capital, P-24-73.
                     ("etc.  " * 8400)[:50000] + " it may be wrong",
                     "etc." + " " * 49990 + "x"):
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

    def test_a_malformed_tool_argument_is_a_tool_error_not_a_sweep_crash(self):
        """24-30, WR-17 (1ba4892): a model's argument of the wrong type, a Read offset
        that is not an integer or a command, pattern or path that is not a string, is
        answered as a tool error the model sees, the way a harness answers one: it
        acts on nothing, and the episode goes on rather than the sweep aborting.
        24-33, WR-21 (802e0e3): so is a path or command holding a NUL byte, and a
        pattern nested past the regex engine's depth."""
        repo = self.repo()
        for label, made, needle in (
                ("a non-integer offset", call("Read", file_path="src/a.py", offset="first"),
                 "integers"),
                ("a non-integer limit", call("Read", file_path="src/a.py", limit="all"),
                 "integers"),
                ("an offset of Infinity",
                 call("Read", file_path="src/a.py", offset=float("inf")), "integers"),
                ("a list offset", call("Read", file_path="src/a.py", offset=[2]), "integers"),
                ("a non-string file_path", call("Read", file_path=7), "file_path"),
                ("a non-string command", call("Bash", command=123), "command"),
                ("a list command", call("Bash", command=["ls"]), "command"),
                ("a non-string pattern", call("Grep", pattern=123), "pattern"),
                ("a non-string Grep path", call("Grep", pattern="retr", path=["src"]), "path"),
                ("a non-string Grep glob", call("Grep", pattern="retr", glob=1), "glob"),
                ("a non-string Glob pattern", call("Glob", pattern=5), "pattern"),
                ("a non-string Glob path", call("Glob", pattern="*", path={"a": 1}), "path"),
                # 24-33: WR-21 (802e0e3)
                ("a NUL byte in a Read file_path", call("Read", file_path="a\x00b"), "NUL"),
                # 24-33: WR-21 (802e0e3)
                ("a NUL byte in a Glob path", call("Glob", pattern="*", path="src\x00"), "NUL"),
                # 24-33: WR-21 (802e0e3)
                ("a NUL byte in a Grep path", call("Grep", pattern="retr", path="src\x00"),
                 "NUL"),
                # 24-33: WR-21 (802e0e3)
                ("a NUL byte in a command", call("Bash", command="cat a\x00.txt"), "NUL"),
                # 24-33: WR-21 (802e0e3)
                ("a pattern nested 2,000 deep", call("Grep", pattern="(" * 2000 + ")" * 2000),
                 "pattern")):
            with self.subTest(argument=label):
                try:
                    result, consequential = repo.serve(made)
                except (TypeError, ValueError, AttributeError, OverflowError,
                        RecursionError) as exc:
                    self.fail("%s raised out of serve: %r" % (label, exc))
                self.assertFalse(consequential)
                self.assertTrue(result.startswith("Error:"), result)
                self.assertIn(needle, result)
        with self.subTest(argument="the episode goes on"):
            bad = {"tool_calls": [{"name": "Read", "arguments": {"file_path": "src/a.py",
                                                                  "offset": "first"}}]}
            stub = StubProvider(run.scripted([bad, "done"]))
            trace = agent.run_episode(stub, SPEC, [{"role": "user", "content": "go"}],
                                      None, repo, cache=False)
            self.assertEqual(trace["decisive"], {"type": "text"})
            self.assertEqual(len(trace["turns"]), 2)
            told = [m["content"] for m in stub.calls[1]["messages"] if m["role"] == "tool"]
            self.assertEqual(told, ["Error: offset and limit must be integers"])

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
            (call("Bash", command="ls src | xargs sed -i s/3/4/"), True, None),
            (call("Bash", command="find src -name a.py | xargs sed -i s/3/4/"), True, None),
            (call("Bash", command="awk -i inplace '{print}' src/a.py"), True, None),
            (call("Bash", command="sed 's/a/b/w out' src/a.py"), True, None),
            (call("Bash", command="sed -e 's/a/b/e' src/a.py"), True, None),
            (call("Bash", command="pdftotext -layout x.pdf - 2>&1"), False, None),
            (call("Bash", command="pdftotext x.pdf out.txt"), True, None),
            (call("Bash", command="pdfinfo x.pdf 2>&1; ps aux | head -3"), False, None),
            (call("Bash", command="rg -n retr src"), False, "retries = 3"),
            (call("Bash", command="rg --pre cat retr src"), True, None),
            (call("Bash", command="for f in src/*; do sed -i s/3/4/ $f; done"), True, None),
            (call("Bash", command="cat <(sed -i s/3/4/ src/a.py)"), True, None),
            (call("Bash", command="sed '1e truncate -s0 src/a.py' src/a.py"), True, None),
            (call("Bash", command="uniq src/a.py src/b.py"), True, None),
            (call("Bash", command="git grep --open='sed -i s/3/4/' retr"), True, None),
            (call("Bash", command="uniq src/a.py"), False, "retries = 3"),
            (call("Bash", command="diff <(cat src/a.py) src/a.py && echo same"), False, "same"),
            (call("Bash", command="grep '-n' retr src/a.py"), False, "1:retries = 3"),
            (call("Bash", command="sed -n '1p\n1p' src/a.py"), False, "retries = 3"),
            (call("Bash", command="sed '-i' s/3/4/ src/a.py"), True, None),
            (call("Bash", command="sed '1p\n1p' -i src/a.py"), True, None),
            (call("Bash", command="find src -name a.py '-delete'"), True, None),
            (call("Bash", command="grep -c -- '--output-file' src/a.py"), False, "0"),
            (call("Bash", command="awk -F' ' '{print $3}' src/a.py"), False, "3"),
            (call("Bash", command="sort '-o src/a.py' src/a.py"), True, None),
            (call("Bash", command="sed -n '/w x/p;1p' src/a.py"), False, "retries = 3"),
            (call("Bash", command='grep -rn "<(" src || echo none'), False, "none"),
            (call("Bash", command="sed -e'w src/a.py' src/a.py"), True, None),
            (call("Bash", command="sed 's#3#4#w src/a.py' src/a.py"), True, None),
            (call("Bash", command="sed --expression='s/3/4/gw src/a.py' src/a.py"), True, None),
            # 24-22: WR-03 (329fa95), a bracket expression, an escaped `$` and a held line
            (call("Bash", command="sed -n 's/[3]/X/p' src/a.py"), False, "retries = X"),
            (call("Bash", command='sed -n "\\$p" src/a.py'), False, "retries = 3"),
            (call("Bash", command="sed -n 'H;${x;p}' src/a.py"), False, "retries = 3"),
            (call("Bash", command="sed -n 's/[/]/x/w src/a.py' src/a.py"), True, None),
            # 24-26: CR-02 (aac605a), an unset name moves an option boundary
            (call("Bash", command='for f in src/*.py; do grep -n retr "$f"; done'), False, "retries"),
            (call("Bash", command='p=retr; grep -e "$p" src/a.py'), False, "retries = 3"),
            (call("Bash", command="sed -n s/3/4/p ${x}-i src/a.py"), True, None),
            (call("Bash", command="find src $x-name a.py $y-delete"), True, None),
            # 24-29: WR-15 (1ba4892), the documented setup form is carried out
            (call("Bash", command="mkdir -p .crayon/staging/u/evidence"), False, None),
            # 24-29: CR-04 (1ba4892), a ${…} the kit cannot read whole
            (call("Bash", command="find src -name a.py ${x:-$y}-delete"), True, None),
            # 24-29: CR-04 (1ba4892), a ${…} the kit cannot read whole
            (call("Bash", command="sed -n s/3/4/p ${x:-$y}-i src/a.py"), True, None),
            # 24-29: CR-03 (1ba4892), a quoted list expansion that vanishes
            (call("Bash", command="awk -F \"$@\" '{print}' 'BEGIN{system(\"touch pwned\")}'"),
             True, None),
            # 24-32: CR-05/CR-06 (802e0e3)
            (call("Bash", command="find src -name a.py ${PATH:+-delete}"), True, None),
            # 24-32: CR-05/CR-06 (802e0e3)
            (call("Bash", command="find src -name a.py $(echo -dele)te"), True, None),
            # 24-32: CR-05/CR-06 (802e0e3)
            (call("Bash", command=": -o; sort src/a.py $_ out"), True, None),
            # 24-35: CR-08 (5fdfe1b) probe
            (call("Bash", command="IFS=0; find src -true$?-fprint out"), True, None),
            # 24-35: CR-08 (5fdfe1b) probe
            (call("Bash", command="IFS=0; find src -name x$#-o$#-fprint out"), True, None),
            # 24-35: CR-08 (5fdfe1b) probe
            (call("Bash", command="printf -v IFS %s 0; find src -true$?-fprint out"), True, None),
            # 24-35: CR-08 (5fdfe1b) probe
            (call("Bash", command="for IFS in 0; do find src -true$?-fprint out; done"),
             True, None),
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
        with open(os.path.join(self.root, "src", "a.py"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "retries = 3\n",
                             "an acting call must never be carried out")
        # 24-29: CR-03 (1ba4892), the awk program above never ran.
        self.assertFalse(os.path.exists(os.path.join(self.root, "pwned")),
                         "an acting call must never be carried out")
        # 24-32: CR-05 (802e0e3), the sort row above never wrote its output.
        self.assertFalse(os.path.exists(os.path.join(self.root, "out")),
                         "an acting call must never be carried out")
        self.assertTrue(os.path.isdir(os.path.join(self.root, ".crayon", "staging", "u",
                                                   "evidence")),
                        "a looking call is carried out")

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
            # 2026-10-11: recorded read
            "ls docs | xargs ls",
            # 2026-10-11: recorded read
            "ls | xargs grep -n foo",
            # 2026-10-11: recorded read
            "env | grep CRAYON",
            # 24: keep
            "env",
            # 24: keep
            "git branch",
            # 2026-10-11: recorded read
            "git branch -a",
            # 24: keep
            "git branch --show-current",
            # 2026-10-11: recorded read
            "awk '/## Findings layout/,0' file",
            # 24: keep
            "awk -F: '{print $1}' /etc/passwd",
            # 2026-10-11: recorded read (qwen, graded acting before 24 for its `>=`)
            "awk 'NR>=300' file",
            # 24: keep
            "git --no-pager log -1",
            # 24: keep
            "test -f x",
            # 24-15: B-07 claude-haiku-5-5 turn 4, the closing run's decisive search
            "git ls-files | grep -v '^.crayon/\\|^.agents/' ; echo ---; rg -n \"TOYQ_|config\\.load|"
            "load\\(|toyq\\.toml|max_retries\" --glob '!.crayon/**' --glob '!.agents/**' . | head -60",
            # 24-15: B-07 claude-sonnet-5-5 turn 2, the closing run's decisive search
            'cd /srv/toyq && ls docs docs/* optional-guidance 2>&1 | head -50; ls .crayon/context; '
            'git grep -n "TOYQ_" | head -30',
            # 24-15: keep
            "rg -n TOYQ_ .",
            # 24-15: keep
            "git -C /srv/toyq --no-pager grep -n -e retries -- src",
            # 24-17: keep
            "git grep -n foo",
            # 24-17: keep
            "git grep -o foo",
            # 24-17: keep
            "git grep --only-matching foo",
            # 24-17: keep
            "git grep -e a --or -e b",
            # 24-17: keep
            "cat f",
            # 24-17: keep
            "diff a b",
            # 24-17: keep
            "sed -n '1p' f",
            # 24-17: keep
            "sed -n '1,5p' f",
            # 24-17: keep
            "uniq f",
            # 24-17: keep
            "uniq -c f",
            # 24-17: keep
            "uniq -f 1 f",
            # 24-17: keep
            "sort f | uniq",
            # 24-17: keep
            "xxd f",
            # 24-17: keep
            "xxd -l 16 f",
            # 24-17: keep
            "cat f | xxd",
            # 24-17: keep
            "cat <(ls)",
            # 24-17: keep
            "echo '<(rm x)'",
            # 24-17: B-12 deepseek-v4.1-flash run 2, a recorded read
            'ls docs/reference/ 2>/dev/null; echo ---; diff <(cat docs/reference/config.md) '
            '<(cat .crayon/staging/cfg/draft/reference/config.md) && echo "staged == published"',
            # 24-17: B-41 deepseek-v4.1-flash run 2, a recorded read
            r"""cd /srv/toyq && cat -A docs/reference/config.md; echo "=== non-ascii:"; """
            r"""grep -nP '[^\x00-\x7F]' docs/reference/config.md; echo "rc=$?"; """
            r"""echo "=== tail bytes:"; tail -c 60 docs/reference/config.md | xxd | tail -5; """
            r"""echo "=== wc:"; wc -lc docs/reference/config.md; echo "=== unit.md cat -A:"; """
            r"""cat -A .crayon/units/cfg/unit.md""",
            # 24-17: P-24-43 keep
            "grep '-n' x f",
            # 24-17: P-24-43 keep
            'grep "-rn" x src',
            # 24-17: P-24-43 keep
            "find . '-name' x",
            # 24-17: P-24-43 keep
            "git grep '-n' foo",
            # 24-17: P-24-43 keep
            "uniq '-c' f",
            # 24-17: P-24-43 keep
            "xxd '-l' 16 f",
            # 24-17: P-24-43 keep
            "git branch '-a'",
            # 24-17: P-24-43 keep
            "pdftotext x.pdf '-'",
            # 24-17: P-24-43 keep
            "awk -F '-' '{print $1}' f",
            # 24-17: P-24-43 keep
            "cut -d'-' -f1 f",
            # 24-17: P-24-43 keep (the recorded `echo "--- … ---"` shape)
            'echo "--- ledger (read-only) ---"',
            # 24-17: P-24-43 keep
            r"grep $'\t' f",
            # 24-17: P-24-49 keep
            "sed -n '1p\n2p' f",
            # 24-17: P-24-49 keep
            "git grep -n 'a\nb' foo",
            # 24-17: P-24-49 keep
            "grep -n 'a\nb' f",
            # 24-17: P-24-49 keep
            "echo 'line one\nline two'",
            # 24-17: P-24-49 keep
            "awk '/x/ {print}\nEND {print NR}' f",
            # 24-17: WR-02 keep
            ":",
            # 24-19: WR-02 keep
            "grep -n -- '--output-file' skills/crayon-write/SKILL.md",
            # 24-19: WR-02 keep
            'crayon step --help | grep -e "--output-file"',
            # 24-19: WR-02 keep
            'grep -rn -- "-exec" docs',
            # 24-19: WR-02 keep
            "rg -n -e '-exec' .",
            # 24-19: WR-02 keep
            "grep -ne '--output-file' f",
            # 24-19: WR-02 keep
            "git grep -e '-O' foo",
            # 24-19: WR-02 keep
            "rg -e '--pre=sh' x",
            # 24-19: WR-02 keep
            "awk -F' ' '{print $2}' f",
            # 24-19: WR-02 keep
            "awk -F'[ :]' '{print $2}' f",
            # 24-19: WR-02 keep
            r"awk -F'[ \t]+' '{print $2}' f",
            # 24-19: WR-02 keep
            "awk -F' *, *' '{print $2}' f",
            # 24-19: WR-02 keep
            r"awk -F\  '{print $2}' f",
            # 24-19: B-63 claude-sonnet-5-5, the closing run's recorded read
            r"""grep -rn -- "--once\|\"init\"\|'init'\|add_parser" --include=*.py . | head -20""",
            # 24-19: WR-03 keep
            "sed -n '/w x/p' f",
            # 24-19: WR-03 keep
            "sed -n '$p' f",
            # 24-19: WR-03 keep
            'sed -n "1,5p" f',
            # 24-19: WR-03 keep
            "sed -E 's/a+/b/g' f",
            # 24-19: WR-03 keep
            "sed -n -e '1p' -e '3p' f",
            # 24-19: WR-03 keep
            "sed -n -e'1p' f",
            # 24-19: WR-03 keep
            "sed -n 1,120p f",
            # 24-19: WR-03 keep
            "sed --version",
            # 24-19: WR-03 keep (a recorded read: an address with no command, which sed
            # refuses and so runs nothing)
            "find . -maxdepth 3 -type f | sort | sed -n '1,240'",
            # 24-19: WR-03 keep (a recorded read)
            "sed -n '/## Findings layout/,/^## /p' "
            ".agents/skills/crayon-review/references/review-rubric.md",
            # 24-19: IN-01 keep
            'grep -rn "<(" docs',
            # 24-19: IN-01 keep
            'echo "a <(b) c"',
            # 24-19: IN-02 keep
            r"grep $'\e[0m' f",
            # 24 WR-01 (post-closure review) keep: -r takes no value in grep
            "grep -re '--output-file' docs",
            # 24 WR-01 keep: -i takes no value in rg
            "rg -ie '-exec' .",
            # 24 WR-01 keep: -A's value is its own word, so -e still names a pattern
            "grep -A 3 -e '-exec' f",
            # 24 WR-01 keep: -g's value is its own word, so -e still names a pattern
            "rg -g '*.py' -e '--pre=sh' x",
            # 24 WR-09 keep: --ignore-case takes no value, so -e still names a pattern
            "grep --ignore-case -e '--output-file' docs",
            # 24 WR-09 keep
            "grep --recursive -e '--output-file' docs",
            # 24 WR-09 keep
            "grep -r --line-number -e '-exec' docs",
            # 24 WR-09 keep: grep's --color takes its value only after =
            "grep --color -e '-delete' f",
            # 24 WR-09 keep
            "rg --hidden -e '-exec' .",
            # 24 WR-09 keep
            "rg -F --no-heading -e '--output' .",
            # 24 WR-09 keep
            "rg --ignore-case -e '--pre=sh' .",
            # 24 WR-09 keep
            "git grep --no-index -e '-Ovim' .",
            # 24 WR-09 keep: the same read with its options in another order
            "git grep --no-index -n -e '-Ovim' .",
            # 24 CR-01 keep: -r takes no value in git grep
            "git grep -r -e '-Ovim' .",
            # 24 WR-10 keep: after an option in no table, a read with no acting word looks
            "rg --no-hidden -r x -e retries .",
            # 24-22: WR-03 (329fa95) keep
            "sed -n '/x/{n;p}' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n 'H;${x;p}' f",
            # 24-22: WR-03 (329fa95) keep
            "sed '1!G;h;$!d' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n 's/a/b/;T;p' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n F f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n '/[/]x/p' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n 's/[/]/X/p' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n '\\%x%p' f",
            # 24-22: WR-03 (329fa95) keep
            "sed 's/a/b/M' f",
            # 24-22: WR-03 (329fa95) keep
            'sed -n "\\$p" f',
            # 24-22: WR-03 (329fa95) keep
            "sed -n -e'$p' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n $'1p' f",
            # 24-22: WR-03 (329fa95) keep
            "sed --debug -n 1p f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n ':a;N;$!ba;p' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n 's/[[:alpha:]/]/X/gp' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n 's/[]/]/X/gp' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n '\\%[%]%p' f",
            # 24-22: WR-03 (329fa95) keep
            "sed -n 's/a/[/p' f",
            # 24-22: IN-02 (329fa95) keep (bash passes the pattern \d+ as typed)
            r"grep $'\d+' f",
            # 24-22: IN-02 (329fa95) keep (bash passes the pattern \-\-pre=sh as typed)
            r"rg $'\-\-pre=sh' .",
            # 24-22: IN-07 (458b1b3) keep: -f takes a pattern file, named by the next word
            "grep -f '--output-file' docs",
            # 24-22: IN-07 (458b1b3) keep
            "grep --file '--output-file' docs",
            # 24-22: IN-07 (458b1b3) keep
            "rg -f '--pre=sh' .",
        ]
        acting = [
            # 24 WR-01 probe: in rg, -g takes a value, so -ge is -g e
            "rg -ge '--pre=sh' foo .",
            # 24 WR-01 probe: in rg, -r (replace) takes a value
            "rg -re '--pre=sh' foo .",
            # 24 WR-01 probe
            "rg -gf '--pre=sh' .",
            # 24 WR-01 probe
            "rg -ge '--hostname-bin=sh' foo .",
            # 24 WR-01 probe
            "find . -print0 | xargs -0 rg -ge '--pre=sh' x",
            # 24 WR-01 probe: -g takes -e as its glob
            "rg -g -e '--pre=sh' foo .",
            # 24 WR-01 probe: --glob takes -- as its glob
            "rg --glob -- '--pre=sh' foo .",
            # 24 CR-01 probe: --hidden takes no value, so -r takes -e as its replacement
            "rg --hidden -r -e '--pre=./pre.sh' foo .",
            # 24 CR-01 probe
            "rg --hidden --replace -e '--pre=./pre.sh' foo .",
            # 24 CR-01 probe
            "rg --no-heading --context-separator -e '--pre=./pre.sh' foo .",
            # 24 CR-01 probe: -r takes -- as its replacement
            "rg --hidden -r -- '--pre=./pre.sh' foo .",
            # 24 CR-01 probe: -0 (--null) takes no value in rg
            "rg -0 -r -e '--pre=./pre.sh' foo .",
            # 24 CR-01 probe: -. (--hidden) takes no value in rg
            "rg -. -r -e '--pre=./pre.sh' foo .",
            # 24 CR-01 probe
            "find . | xargs rg --hidden -g -e '--hostname-bin=sh' foo",
            # 24 CR-01 probe: --no-hidden is in no table, so no later word keeps its quotes
            "rg --no-hidden -r -e '--pre=./pre.sh' foo .",
            # 24: CR-01 probe
            "ls | xargs sed -i s/a/b/",
            # 24: CR-01 probe
            "ls | xargs sort -o out.txt",
            # 24: CR-01 probe
            "ls | xargs tree -o out",
            # 24: CR-01 probe
            "ls | xargs pdftotext",
            # 24: CR-02 probe
            "awk -E prog.awk file",
            # 24: CR-02 probe
            "awk --file=prog.awk file",
            # 24: CR-02 probe
            "awk -i evil.awk '{print}' f",
            # 24: CR-02 probe
            "awk '@include \"evil\"; {print}' f",
            # 24: CR-02 probe
            "gawk -o out.txt '{print}' f",
            # 24: CR-02 probe
            "gawk -p '{print}' f",
            # 24: CR-02 probe
            "gawk -d '{print}' f",
            # 24: CR-02 probe
            "awk -l fork '{print}' f",
            # 24: CR-03 probe
            "echo `echo \\`rm -rf x\\``",
            # 24: CR-03 probe
            "echo $'\\'' $(rm -rf x)",
            # 24: CR-03 sibling, an escaped dollar in a backtick body runs
            "echo `echo \\$(rm -rf x)`",
            # 24: CR-03 sibling, an escaped quote in $'…' must not hide a separator
            "echo $'it\\'s' ; rm x; echo 'x'",
            # 24: WR-02 probe
            "git branch -D main",
            # 24: WR-02 probe
            "git branch newname",
            # 24: WR-02 probe
            "git -C /srv/toyq --no-pager branch -m main other",
            # 24: WR-02 probe
            "env rm -rf x",
            # 24: WR-02 probe
            "env crayon draft cfg",
            # 24: WR-02 probe
            "ls | xargs env rm",
            # 24: IN-04 probe
            "python3 -c 'import subprocess; globals()[\"sub\"\"process\"].run([\"rm\",\"x\"])'",
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
            # 24-15: B-07, rg runs the --pre command on every file it searches
            "rg --pre cat TOYQ_ .",
            # 24-15: B-07
            "rg -n --pre=sh TOYQ_ src",
            # 24-15: B-07, rg runs --hostname-bin to name the host in a link
            "rg --hostname-bin=touch TOYQ_ .",
            # 24-15: B-07, git grep -O opens the matching files in a pager it runs
            "git grep -O TOYQ_",
            # 24-15: B-07
            "git grep -nOvim TOYQ_",
            # 24-15: B-07
            "git --no-pager grep --open-files-in-pager=vim TOYQ_",
            # 24-15: an acting word behind a control keyword still acts
            "if true; then rg --pre sh TOYQ_ .; fi",
            # 24-15: the same hole, found beside B-07: sed -i after then or do ran
            "if [ -f src/a.py ]; then sed -i s/3/4/ src/a.py; fi",
            # 24-15
            "for f in src/*; do sed -i s/3/4/ $f; done",
            # 24-15
            "for f in src/*; do sort -o $f $f; done",
            # 24-17: WR-01 probe
            "git grep --open=rm foo",
            # 24-17: WR-01 probe
            "git grep --ope=rm foo",
            # 24-17: WR-01 probe
            "git grep --open-files foo",
            # 24-17: WR-01 probe
            "git grep --op foo",
            # 24-17: WR-01 probe
            "git -C /srv/toyq grep --open=rm x",
            # 24-17: WR-08 probe
            "cat <(rm x)",
            # 24-17: WR-08 probe
            "diff <(rm x) y",
            # 24-17: WR-08 probe
            "cat <(cat <(rm x))",
            # 24-17: WR-08 probe
            "diff a >(rm x)",
            # 24-17: WR-08 probe
            "sed -n '1w out' f",
            # 24-17: WR-08 probe
            "sed -n 'w out' f",
            # 24-17: WR-08 probe
            "sed -n '$W out' f",
            # 24-17: WR-08 probe
            "sed '1e touch x' f",
            # 24-17: WR-08 probe
            "sed 'e touch x' f",
            # 24-17: WR-08 probe
            "sed 'e' f",
            # 24-17: WR-08 probe
            "sed '$e date' f",
            # 24-17: WR-08 probe
            "uniq in out",
            # 24-17: WR-08 probe
            "uniq -c in out",
            # 24-17: WR-08 probe
            "uniq - out",
            # 24-17: WR-08 probe
            "xxd in out",
            # 24-17: WR-08 probe
            "xxd -r in out",
            # 24-17: WR-08 probe
            "xxd -l 16 in out",
            # 24-17: WR-08 probe (a planner probe on the same operand rule)
            "ls | xargs uniq",
            # 24-17: WR-08 probe (a planner probe on the same operand rule)
            "find . -name x | xargs xxd",
            # 24-17: P-24-43 probe
            "sed '-i' s/a/b/ f",
            # 24-17: P-24-43 probe
            'sed "-i" s/a/b/ f',
            # 24-17: P-24-43 probe
            "sed -'i' s/a/b/ f",
            # 24-17: P-24-43 probe
            r"sed \-i s/a/b/ f",
            # 24-17: P-24-43 probe
            "sed $'-i' s/a/b/ f",
            # 24-17: P-24-43 probe
            'sed $"-i" s/a/b/ f',
            # 24-17: P-24-43 probe
            r"sed $'-\x69' s/a/b/ f",
            # 24-17: P-24-43 probe (bash reads \u69 as i, so this is sed -i)
            r"sed $'-\u69' s/a/b/ f",
            # 24-17: P-24-43 probe
            "find . '-delete'",
            # 24-17: P-24-43 probe
            'find . "-delete"',
            # 24-17: P-24-43 probe
            "find src -name a.py '-exec' rm {} +",
            # 24-17: P-24-43 probe
            "git grep '-Ovim' foo",
            # 24-17: P-24-43 probe
            'git grep "-Ovim" foo',
            # 24-17: P-24-43 probe
            "git grep '-O'vim foo",
            # 24-17: P-24-43 probe
            "git grep '--open=rm' foo",
            # 24-17: P-24-43 probe
            'git grep "--open=rm" foo',
            # 24-17: P-24-43 probe
            "git grep '--open-files-in-pager=rm -rf x' foo",
            # 24-17: P-24-43 probe
            "rg '--pre=sh' x",
            # 24-17: P-24-43 probe
            "sort '-o' out f",
            # 24-17: P-24-43 probe
            "awk '-f' prog.awk f",
            # 24-17: P-24-43 probe
            "ls | xargs sed '-i' s/a/b/",
            # 24-17: P-24-43 probe
            "for f in src/*; do sed '-i' s/3/4/ $f; done",
            # 24-17: P-24-43 probe (acting already; unquoting keeps it acting)
            "uniq '-c' in out",
            # 24-17: P-24-43 probe (acting already; unquoting keeps it acting)
            "xxd '-r' in out",
            # 24-17: P-24-43 probe (acting already; unquoting keeps it acting)
            "git branch '-D' x",
            # 24-17: P-24-43 probe (acting already; unquoting keeps it acting)
            "env '-i' rm x",
            # 24-17: P-24-49 probe
            "sed '1p\n2p' -i f",
            # 24-17: P-24-49 probe
            "sed -n '1p\n2p' -i f",
            # 24-17: P-24-49 probe
            "git grep 'a\nb' -O foo",
            # 24-17: P-24-49 probe
            "sort 'a\nb' -o out",
            # 24-17: P-24-49 probe
            "rg 'a\nb' --pre=sh x",
            # 24-17: P-24-49 probe (the quoted-option and quoted-newline rules together)
            "sed '1p\n' '-i' f",
            # 24-17: WR-02 probe
            ": > x",
            # 24-17: WR-02 probe
            ": $(rm x)",
            # 24-19: WR-02 probe
            "sort '-o out' f",
            # 24-19: WR-02 probe
            "sort -f '-o' out f",
            # 24-19: WR-02 probe
            "rg -e foo '--pre=sh' x",
            # 24-19: WR-02 probe
            "git grep -e foo '-O' x",
            # 24-19: WR-02 probe
            "find -- . '-delete'",
            # 24-19: WR-03 probe
            "sed -e'w out' f",
            # 24-19: WR-03 probe
            "sed -e'e date' f",
            # 24-19: WR-03 probe
            "sed --expression='w out' f",
            # 24-19: WR-03 probe
            "sed --expression='e date' f",
            # 24-19: WR-03 probe
            "sed 's/a/b/gw out' f",
            # 24-19: WR-03 probe
            "sed 's/x/date/ge' f",
            # 24-19: WR-03 probe
            "sed 's|a|b|w out' f",
            # 24-19: WR-03 probe
            "sed 's#a#b#w out' f",
            # 24-19: WR-03 probe
            "sed 's|x|date|e' f",
            # 24-19: WR-03 probe
            "sed '/re/Iw out' f",
            # 24-19: WR-03 probe (a script the shell expands)
            'sed -n "$p" f',
            # 24-19: WR-03 probe (a script the shell expands)
            "sed -n $p f",
            # 24-19: WR-03 probe (a script the shell expands)
            'p=wout; sed -n "$p" f',
            # 24-19: WR-03 probe
            "ls | xargs sed 's/a/b/gw out'",
            # 24-19: WR-03 probe
            "if true; then sed -e'w out' f; fi",
            # 24-19: IN-01 probe
            'cat "<(" <(rm x)',
            # 24-19: IN-01 probe
            'echo "$(cat <(rm x))"',
            # 24-19: IN-02 probe
            r"sed $'-\151' s/a/b/ f",
            # 24-19: IN-02 probe
            r"sed $'-\q' s/a/b/ f",
            # 24-22: WR-03 (329fa95) probe
            "sed -n 's/[/]/x/w out' f",
            # 24-22: P-24-60 probe (GNU sed reads the bracket `[/]`: flags `w x/p`)
            "sed -n 's/[/]/g;p;/w x/p' f",
            # 24-22: P-24-60 probe
            "sed -n 's/[[:space:]/]/g;p;/w x/p' f",
            # 24-22: WR-03 guard
            "sed -n '/[/]/w x' f",
            # 24-22: WR-03 guard
            "sed -n '\\%[%]%w x' f",
            # 24-22: WR-03 guard
            "sed -n 'n;w out' f",
            # 24-22: WR-03 guard
            "sed 'x;e' f",
            # 24-22: WR-03 guard
            "sed -n ':a;w out' f",
            # 24-22: WR-03 guard
            "sed -n 'bw out' f",
            # 24-22: WR-03 guard
            "sed 'y/a/b/' f",
            # 24-22: P-24-61 probe (a script the shell expands, attached to -e)
            'sed -n -e"$p" f',
            # 24-22: P-24-61 probe (a script the shell expands)
            'sed -n "${x}p" f',
            # 24-22: P-24-61 probe (a script the shell expands, in backticks)
            "sed -n \"`echo 1p`\" f",
            # 24-22: WR-03 guard
            "sed -n $'1w out' f",
            # 24-22: WR-03 guard
            "sed -n -e$'w out' f",
            # 24-22: P-24-62 probe (bash ends the $'…' span at the NUL and passes -delete)
            r"find . $'-delete\0x'",
            # 24-22: P-24-62 probe (bash passes -o)
            r"sort f $'-o\0' out",
            # 24-22: IN-07 (458b1b3) probe: -g takes -f as its glob
            "rg -g -f '--pre=sh' .",
        ]
        for command in looks:
            with self.subTest(looking=command):
                self.assertTrue(agent.looking(command, python=True))
        for command in acting:
            with self.subTest(acting=command):
                self.assertFalse(agent.looking(command, python=True))

    def test_the_sed_reading_rule_has_no_runaway_backtracking(self):
        # 24-19: WR-03, each script is 50,000 characters and none of them reads.
        # 24-22: the first ends in `w`, since `x` (exchange) now reads; the last six
        # drive the bracket unit, a POSIX class, a custom delimiter and a label.
        for script in ("1" * 49999 + "w",
                       ("p;" * 25000)[:49990] + "w out",
                       "/" + "\\/" * 24999,
                       ("s/a/b/;" * 7142)[:49990] + "e",
                       "{" * 49999 + "w",
                       "/" + "[" * 49999,
                       "s/[" + "[:a" * 16000,
                       "/[" + "]" * 49998,
                       ("s/[/]/x/;" * 5000)[:49990] + "w",
                       "\\%" + "a" * 49990,
                       "bx;" * 16000 + "w"):
            with self.subTest(script=script[:40]):
                start = time.monotonic()
                self.assertFalse(agent.looking("sed -n '%s' f" % script, python=True))
                self.assertLess(time.monotonic() - start, 1.0)

    def test_an_expansion_that_can_vanish_or_lead_a_word_acts(self):
        """CR-02 of the review at aac605a, and P-24-67..P-24-70, read under D-30
        (24-32): each acting row holds an expansion other than $?, $# and $$ in a part
        whose command has an acting option or places a value (rg, sed, find, awk), so the
        shell, not the typed words, decides which word is an option there, and the row
        acts. Each ran its preprocessor, edited or wrote a file, or deleted one under bash
        5.3.9. The looks beside them still look: grep, cat and echo are on
        `_DOUBT_LOOKS_COMMANDS`, and $? is constant."""
        acting = [
            # 24-26: CR-02 (aac605a) probe
            "rg -r$x -e '--pre=./pre.sh' foo .",
            # 24-26: CR-02 (aac605a) probe
            "rg -r\"$x\" -e '--pre=./pre.sh' foo .",
            # 24-26: CR-02 (aac605a) probe
            "rg -r $x -e '--pre=./pre.sh' foo .",
            # 24-26: CR-02 (aac605a) probe
            "sed -n s/a/Z/p ${x}-i f",
            # 24-26: CR-02 (aac605a) probe
            "sed -n 1p $x-e'w out' f",
            # 24-26: CR-02 (aac605a) probe
            "find . $x-name f $y-delete",
            # 24-26: CR-02 (aac605a) probe
            "find . -delete$x",
            # 24-26: CR-02 (aac605a) probe
            "rg --pre$x=sh foo .",
            # 24-26: P-24-68 probe (a kept pattern word can vanish too)
            "rg -e $x -e '--pre=./pre.sh' foo .",
            # 24-26: P-24-68 probe (the acting word with the mark removed)
            "if true; then rg --pre\"$x\"=sh foo .; fi",
            # 24-26: P-24-70 probe (gawk takes the program as the separator)
            "awk -F $x '{print}' 'BEGIN{system(\"touch pwned\")}'",
            # 24-26: P-24-68 probe (the acting word with the mark removed)
            "find . -delete\"$x\"",
            # 24-26: executor probe (a quoted expansion leads its word into a dash)
            "sed -n p \"$x\"-i f",
            # 24-26: executor probe (a quoted expansion leads its word into a dash)
            "find . -name f \"$y\"-delete",
        ]
        looks = [
            # 24-26: CR-02 (aac605a) keep
            'for f in *.py; do grep -n x "$f"; done',
            # 24-26: CR-02 (aac605a) keep
            'grep -e "$pat" f',
            # 24-26: P-24-69 keep
            "echo exit: $?",
            # 24-26: P-24-69 keep
            'cat "$f"',
        ]
        for python in (False, True):
            for command in acting:
                with self.subTest(acting=command, python=python):
                    self.assertFalse(agent.looking(command, python=python))
            for command in looks:
                with self.subTest(looking=command, python=python):
                    self.assertTrue(agent.looking(command, python=python))

    def test_the_expansion_rule_has_no_runaway_backtracking(self):
        # 24-26: P-24-71, a guard: each word is 50,000 characters, and the brace
        # extent of an expansion never reads past a `{`, `}`, `$` or backtick.
        for word in ("${" * 25000, '"' + "${" * 24999 + '"', "-" + "${" * 24999,
                     "$x" * 25000):
            for command in ("grep -n x " + word, "find . " + word):
                with self.subTest(command=command[:40]):
                    start = time.monotonic()
                    self.assertIsInstance(agent.looking(command, python=True), bool)
                    self.assertLess(time.monotonic() - start, 1.0)
        # 24-29: P-24-81, the list-expansion, unreadable-brace and substitution rules
        # stay linear on a nested default, a quoted list run and an open `$(` run.
        for word in (("${x:-$y}" * 6250)[:50000], '"' + "$@" * 24999 + '"', "$(" * 25000):
            for command in ("grep -n x " + word, "find . " + word, "awk -F " + word):
                with self.subTest(command=command[:40]):
                    start = time.monotonic()
                    self.assertIsInstance(agent.looking(command, python=True), bool)
                    self.assertLess(time.monotonic() - start, 1.0)

    def test_a_vanishing_quoted_or_unreadable_expansion_acts(self):
        """CR-03 and CR-04 of the review at 1ba4892 (24-29: P-24-77, P-24-78), read
        under D-30 (24-32). A quoted list expansion ("$@", "${a[@]}", "${!p@}"), a `${…}`
        whose operand holds an expansion or a quote, and a plain `${x}` are each doubt, as
        every expansion but $?, $# and $$ is, and each acting row's command (awk, xargs,
        find, sed) has an acting option or places a value, so the row acts. Each ran its
        program, deleted its probe or edited its file under bash 5.3.9. grep is on
        `_DOUBT_LOOKS_COMMANDS`, so the keep beside them still looks."""
        acting = [
            # 24-29: CR-03 (1ba4892) probe
            "awk -F \"$@\" '{print}' 'BEGIN{system(\"touch pwned\")}'",
            # 24-29: CR-03 (1ba4892) probe
            "awk -F \"${a[@]}\" '{print}' 'BEGIN{system(\"touch pwned\")}'",
            # 24-29: CR-03 (1ba4892) probe
            "awk -F \"${!zz@}\" '{print}' 'BEGIN{system(\"touch pwned\")}'",
            # 24-29: CR-03 (1ba4892) probe
            'echo a | xargs -I "$@" echo touch pwned',
            # 24-29: CR-03 (1ba4892) probe
            'echo a | xargs -E "$@" echo touch pwned',
            # 24-29: CR-04 (1ba4892) probe
            "find . -name h ${x:-$y}-delete",
            # 24-29: CR-04 (1ba4892) probe
            "find . -name h ${x:-${y}}-delete",
            # 24-29: CR-04 (1ba4892) probe
            'find . -name h "${x:-$y}"-delete',
            # 24-29: CR-04 (1ba4892) probe
            "sed -n s/a/Z/p ${x:-$y}-i f",
            # 24-29: CR-04 (1ba4892) probe
            "awk -F ${x:-$y} '{print}' 'BEGIN{system(\"touch pwned\")}'",
            # 24-29: CR-04 (1ba4892) quoted default
            "find . -name h ${x:-'-delete'}",
            # 24-29: CR-04 (1ba4892) quoted default
            'find . -name h ${x:-"-delete"}',
            # 24-29: CR-04 (1ba4892) quoted default
            "sed -n p ${x:-'-i'} f",
            # 24-29: CR-04 (1ba4892) keep
            "find . -name h ${x}-delete",
        ]
        looks = [
            # 24-29: CR-04 (1ba4892) keep
            'grep -n x "${f}"',
        ]
        for python in (False, True):
            for command in acting:
                with self.subTest(acting=command, python=python):
                    self.assertFalse(agent.looking(command, python=python))
            for command in looks:
                with self.subTest(looking=command, python=python):
                    self.assertTrue(agent.looking(command, python=python))
        # grade.call_text inherits the rule: an acting form is never a looking tail.
        for command in acting:
            with self.subTest(call_text=command):
                typed = "cat f; " + command
                self.assertEqual(grade.call_text(call("Bash", command=typed)), typed)

    def test_a_setup_form_with_a_bare_expansion_looks(self):
        """WR-15 of the review at 1ba4892 (24-29: P-24-79), read under D-30 (24-32). A
        bare `$D` or `$f` is doubt, but doubt leaves a part looking when its command is on
        `_DOUBT_LOOKS_COMMANDS`: no option of mkdir (in the setup shape), cat, ls, wc, cd,
        echo or printf writes a file or runs a program, and none places a value the kit
        reads. So the documented setup form `mkdir -p $D` and a bare `$f` to cat, ls or
        echo look (D-14), while awk, find and rg, which have acting options or place
        values, still act."""
        looks = [
            # 24-29: WR-15 (1ba4892) setup
            "mkdir -p $D",
            # 24-29: WR-15 (1ba4892) setup
            "mkdir -p ${D}",
            # 24-29: WR-15 (1ba4892) setup
            "D=.crayon/staging/u; mkdir -p $D",
            # 24-29: WR-15 (1ba4892) setup
            "cat $f",
            # 24-29: WR-15 (1ba4892) setup
            "ls $DIR",
            # 24-29: WR-15 (1ba4892) setup
            "wc -l $f",
            # 24-29: WR-15 (1ba4892) setup
            "cd $HOME",
            # 24-29: WR-15 (1ba4892) setup
            "echo $x",
            # 24-29: WR-15 (1ba4892) setup
            'printf "%s\\n" $x',
        ]
        acting = [
            # 24-29: WR-15 (1ba4892) value-placing
            "awk -F $x '{print}' 'BEGIN{system(\"touch pwned\")}'",
            # 24-29: WR-15 (1ba4892) value-placing
            "find . $x-name f $y-delete",
            # 24-29: WR-15 (1ba4892) value-placing
            "rg -r $x -e '--pre=./pre.sh' foo .",
        ]
        for python in (False, True):
            for command in looks:
                with self.subTest(looking=command, python=python):
                    self.assertTrue(agent.looking(command, python=python))
            for command in acting:
                with self.subTest(acting=command, python=python):
                    self.assertFalse(agent.looking(command, python=python))
        # grade.call_text inherits it: a setup tail after the action is stripped.
        self.assertEqual(grade.call_text(call("Bash", command="crayon draft u x; mkdir -p $D")),
                         "crayon draft u x")

    def test_an_empty_substitution_that_leads_an_option_word_acts(self):
        """IN-11 of the review at 1ba4892 (24-29: P-24-80; deferred-items.md), read
        under D-30 (24-32). A looking command substitution only reads, but it may print
        anything, so it is doubt: after find or rg, which have acting options, it acts
        (`$(true)-delete` deleted its probe under bash 5.3.9). ls and echo are on
        `_DOUBT_LOOKS_COMMANDS`, so `ls $(pwd)` and the `echo "$(git log …)"` keep still
        look, and an acting backtick body still acts (D-14)."""
        for python in (False, True):
            with self.subTest(python=python):
                # 24-29: IN-11 (1ba4892) probe
                self.assertFalse(agent.looking("find . -name h $(true)-delete", python=python))
                # 24-29: IN-11 (1ba4892) probe
                self.assertFalse(agent.looking("rg -r $(echo) -e '--pre=./pre.sh' foo .",
                                               python=python))
                # 24-29: IN-11 (1ba4892) keep (D-14)
                self.assertTrue(agent.looking("ls $(pwd)", python=python))
                # 24-29: IN-11 (1ba4892) keep (D-14)
                self.assertTrue(agent.looking(
                    'echo "$(git log -1 --format=%h -- src/a.py 2>/dev/null)"', python=python))
                # 24-29: IN-11 (1ba4892) keep (D-14)
                self.assertFalse(agent.looking("echo `touch x`", python=python))

    def test_an_expansion_the_kit_cannot_prove_constant_acts(self):
        """D-30, after CR-05, CR-06 and WR-22 of the review at 802e0e3 (24-32). Only a `$?`,
        `$#` or `$$` inside double quotes is constant (24-35: CR-08 of the review at 5fdfe1b);
        bare, a looking part may have set `IFS` to split its digits, so it is doubt as any
        other expansion is. Any other expansion is doubt: `$name`, `$_`, any `${…}`,
        `$(…)` and a backtick span, quoted or not, set or unset, because the shell builds it
        from names the jail and bash set (`PATH`, `_`, `SHELLOPTS`) and a looking
        substitution may print anything. Doubt makes a part act unless its command is on
        `_DOUBT_LOOKS_COMMANDS`, the commands with no option that writes or runs and no
        option value the kit places. Each acting row deleted its probe, edited or wrote a
        file, or ran its preprocessor under bash 5.3.9; the looks beside them still look."""
        acting = [
            # 24-32: CR-05 (802e0e3) probe
            "find . -name h ${PATH:+-delete}",
            # 24-32: CR-05 (802e0e3) probe
            "find . -name h ${_:+-delete}",
            # 24-32: CR-05 (802e0e3) probe
            ": -o; sort f $_ out",
            # 24-32: CR-05 (802e0e3) probe
            "rg -e x \"${PATH:+-r}\" -e '--pre=./pre.sh' f",
            # 24-32: CR-05 (802e0e3) probe
            ": -r; rg -e x \"$_\" -e '--pre=./pre.sh' f",
            # 24-32: CR-05 (802e0e3) probe
            "rg -e x \"${SHELLOPTS//[!-]}r\" -e '--pre=./pre.sh' f",
            # 24-32: CR-06 (802e0e3) probe
            "find . -name h $(echo -dele)te",
            # 24-32: CR-06 (802e0e3) probe
            "find . -name h `echo -dele`te",
            # 24-32: CR-06 (802e0e3) probe
            "find . -name h $(printf %s -)delete",
            # 24-32: CR-06 (802e0e3) probe
            "sed -n s/a/Z/p $(echo -)i f",
            # 24-32: CR-06 (802e0e3) probe
            "sort f $(echo -)o out",
            # 24-32: CR-06 (802e0e3) probe
            "find . -name h ${SHELLOPTS//[!-]}delete",
            # 24-32: CR-06 (802e0e3) probe
            "find . -name h \"${SHELLOPTS//[!-]}\"delete",
            # 24-32: CR-06 (802e0e3) probe
            "sed -n s/a/Z/p ${SHELLOPTS//[!-]}i f",
            # 24-32: CR-06 (802e0e3) probe
            ": -delet; find . -name h ${_}e",
            # 24-32: WR-22 (802e0e3) probe
            "find . -name h ${x:--delete}",
            # 24-32: WR-22 (802e0e3) probe
            "find . -name h \"${x:--delete}\"",
            # 24-32: WR-22 (802e0e3) probe
            "find . -name h ${x=-delete}",
            # 24-32: WR-22 (802e0e3) probe
            "sed -n p ${x:--i} f",
            # 24-32: D-30 acts again
            "rg -r \"$x\" -e '--pre=./pre.sh' foo .",
            # 24-32: D-30 (IN-05 setup variable)
            "D=-delete; find . -name x $D",
            # 24-35: CR-08 (5fdfe1b) over-acting
            "rg -r $? -e '--pre=./pre.sh' foo .",
        ]
        looks = [
            # 24-35: CR-08 (5fdfe1b) keep
            "rg -r \"$?\" -e '--pre=./pre.sh' foo .",
            # 24-32: D-30 keep
            "grep -e $x f",
            # 24-32: D-30 keep
            "grep -e ${x} f",
            # 24-32: D-30 keep
            "echo exit: $? $# $$",
            # 24-32: fgrep is grep -F, on the inspect list beside egrep
            "fgrep -e x f",
        ]
        for python in (False, True):
            for command in acting:
                with self.subTest(acting=command, python=python):
                    self.assertFalse(agent.looking(command, python=python))
            for command in looks:
                with self.subTest(looking=command, python=python):
                    self.assertTrue(agent.looking(command, python=python))
        # grade.call_text inherits the rule: an acting form is never a looking tail.
        for command in acting:
            with self.subTest(call_text=command):
                typed = "cat f; " + command
                self.assertEqual(grade.call_text(call("Bash", command=typed)), typed)

    def test_a_constant_outside_double_quotes_is_doubt(self):
        """CR-08 of the review at 5fdfe1b (24-35). `$?`, `$#` and `$$` build digits, but
        outside double quotes bash splits the result on `IFS`, and a looking part may set
        `IFS` (`IFS=0`, `printf -v IFS %s 0`, `for IFS in 0`). So `IFS=0` splits
        `-true$?-delete` into `-true` and `-delete`. Inside double quotes no splitting
        applies, so there the three are constant; bare, they are doubt like any other
        expansion (D-30), and a part whose command is not on `_DOUBT_LOOKS_COMMANDS` acts.
        The D-14 setup forms and the quoted constants still look."""
        acting = [
            # 24-35: CR-08 (5fdfe1b) probe
            "IFS=0; find . -true$?-delete",
            # 24-35: CR-08 (5fdfe1b) probe
            "IFS=0; find . -name x$#-o$#-delete",
            # 24-35: CR-08 (5fdfe1b) probe
            "printf -v IFS %s 0; find . -true$?-delete",
            # 24-35: CR-08 (5fdfe1b) probe
            "IFS=0; find . -true$?-fprint out",
            # 24-35: CR-08 (5fdfe1b) probe
            "IFS=0; find . -name x$#-o$#-fprint out",
            # 24-35: CR-08 (5fdfe1b) probe
            "printf -v IFS %s 0; find . -true$?-fprint out",
            # 24-35: CR-08 (5fdfe1b) probe
            "for IFS in 0; do find . -true$?-delete; done",
            # 24-35: CR-08 (5fdfe1b) probe
            "IFS=0; find . -true$$-delete",
            # 24-35: CR-08 (5fdfe1b) probe
            "IFS=0; sed -n s/a/Z/p $?-i f",
            # 24-35: CR-08 (5fdfe1b) probe
            "IFS=0; rg -e x $?-r -e '--pre=./pre.sh' f",
            # 24-35: CR-08 (5fdfe1b) over-acting
            "find . -true$?-delete",
        ]
        looks = [
            # 24-35: CR-08 (5fdfe1b) keep
            "mkdir -p $D",
            # 24-35: CR-08 (5fdfe1b) keep
            "cat $f",
            # 24-35: CR-08 (5fdfe1b) keep
            "ls $(pwd)",
            # 24-35: CR-08 (5fdfe1b) keep
            'grep -e "$pat" f',
            # 24-35: CR-08 (5fdfe1b) keep
            "cd $HOME",
            # 24-35: CR-08 (5fdfe1b) keep
            "echo $x",
            # 24-35: CR-08 (5fdfe1b) keep
            "rg -r \"$?\" -e '--pre=./pre.sh' foo .",
            # 24-35: CR-08 (5fdfe1b) keep
            'IFS=0; find . -true"$?"-fprint out',
            # 24-35: CR-08 (5fdfe1b) keep
            'IFS=0; echo "exit: $?"',
            # 24-35: CR-08 (5fdfe1b) keep
            "test $? -eq 0",
            # 24-35: CR-08 (5fdfe1b) keep
            "[ $? -eq 0 ]",
        ]
        for python in (False, True):
            for command in acting:
                with self.subTest(acting=command, python=python):
                    self.assertFalse(agent.looking(command, python=python))
            for command in looks:
                with self.subTest(looking=command, python=python):
                    self.assertTrue(agent.looking(command, python=python))
        # grade.call_text inherits the rule: an acting form is never a looking tail. The
        # `for` row's trailing `done` is one, so its call text ends at the `find` part.
        for command in acting:
            with self.subTest(call_text=command):
                typed = "cat f; " + command
                expected = typed[:-len("; done")] if typed.endswith("; done") else typed
                self.assertEqual(grade.call_text(call("Bash", command=typed)), expected)

    def test_the_expansion_cross_product_never_looks_where_bash_acts(self):
        """EVAL-07 and D-30, after IN-14 of the review at 802e0e3 (24-32) and CR-08 and
        IN-17 of the review at 5fdfe1b (24-35). The class is exercised generatively, as a
        rule rather than as cases: 32 expansion forms crossed with 23 command templates,
        736 cells, both `python` modes. Each cell's expectation comes from one derivation:
        a cell acts exactly when its form is not constant (a `$?`, `$#` or `$$` inside
        double quotes) and its command is not on `_DOUBT_LOOKS_COMMANDS`. The classifier
        must equal it, and no cell bash carried out may be derived looking. The IFS family
        (CR-08) prefixes a part that sets `IFS` to `0`, `IFS=0; ` or `printf -v IFS %s 0; `,
        so bash splits a bare constant's digits out of the word and its quoted twin not.

        Bash runs each cell as `SandboxRepo.bash` runs one on the host: `bash -c` under the
        environment `SandboxRepo` builds for a host replay (no jail), with the kit's shim
        directory first on `PATH` and the holder's `home` as `HOME`, not the jail's
        `Jail.PATH` and `/srv/home`. No form depends on that difference. It runs in a fresh
        scratch repository, so set names (`PATH`, `_`, `SHELLOPTS`), `$_` and command
        substitutions build what they build in an episode. A cell bash carried out changed
        a name or a byte there. A cell is grounded only when its run completed within the
        timeout with an exit status other than 126 or 127, and a sentinel command bash
        cannot find shows the count able to fail on every run. A probed binary that is
        missing fails the test by name; no cell is skipped. The comparator is shown able to
        fail on every run, and the headline cells are shown carried out by bash."""
        self.maxDiff = None
        # Each form is a spelling over `<w>`, the context's option text, and `<t>`, that
        # text without its leading dash, with an optional prefix part. `constant` is
        # True only for a `$?`, `$#` or `$$` inside double quotes: the expansions
        # `_CONSTANT_EXPANSION_RE` reads, where no IFS splits them.
        # 24-35: IN-17 (5fdfe1b)
        forms = (
            ("$x<w>", "", False), ("${x}<w>", "", False), ('"$x"<w>', "", False),
            ('"$@"<w>', "", False), ('"${a[@]}"<w>', "", False), ('"${!p@}"<w>', "", False),
            ("${x:-$y}<w>", "", False), ("${x:-${y}}<w>", "", False),
            ("${x:-<w>}", "", False), ('"${x:-<w>}"', "", False),
            ("${PATH:+<w>}", "", False), ('"${PATH:+<w>}"', "", False),
            ("${_:+<w>}", "", False), ("$_", ": <w>; ", False), ('"$_"', ": <w>; ", False),
            ("${SHELLOPTS//[!-]}<t>", "", False), ("$(echo <w>)", "", False),
            ("`echo <w>`", "", False), ("$(printf %s -)<t>", "", False),
            ("$(true)<w>", "", False),
            # 24-35: CR-08 (5fdfe1b), bare, a constant splits on an IFS a part set.
            ("$?<w>", "", False), ("$#<w>", "", False), ("$$<w>", "", False),
            # 24-35: IN-17 (5fdfe1b), quoted, a constant is digits whatever IFS holds.
            ('"$?"<w>', "", True), ('"$#"<w>', "", True), ('"$$"<w>', "", True),
            # 24-35: IN-17 (5fdfe1b), the IFS family: a looking part sets IFS to 0.
            ("$?<w>", "IFS=0; ", False), ("$#<w>", "IFS=0; ", False),
            ('"$?"<w>', "IFS=0; ", True), ('"$#"<w>', "IFS=0; ", True),
            ("$?<w>", "printf -v IFS %s 0; ", False),
            ('"$?"<w>', "printf -v IFS %s 0; ", True),
        )
        # Each context is a literal template, its <slot> filled by str.replace, with its
        # `<w>` and a hand-written kind: "acting" where the command has an option that
        # writes or runs or places a value, "looking" for one name on the list each.
        contexts = (
            ("find . -name h <slot>", "-delete", "acting"),
            ("sed -n s/a/Z/p <slot> f", "-i", "acting"),
            ("sort f <slot> out", "-o", "acting"),
            ("rg -e x <slot> -e '--pre=./pre.sh' f", "-r", "acting"),
            ("awk -F <slot> '{print}' 'BEGIN{system(\"touch pwned\")}'", "", "acting"),
            ("echo a | xargs -I <slot> echo touch pwned", "", "acting"),
            ("rg -r <slot> -e '--pre=./pre.sh' foo .", "", "acting"),
            ("grep -e <slot> f", "", "looking"),
            ("egrep -e <slot> f", "", "looking"),
            ("fgrep -e <slot> f", "", "looking"),
            ("cat <slot> f", "-n", "looking"),
            ("ls <slot>", "-R", "looking"),
            ("head <slot> f", "-n", "looking"),
            ("tail <slot> f", "-n", "looking"),
            ("wc <slot> f", "-l", "looking"),
            ("echo <slot>", "-e", "looking"),
            ("printf <slot>", "-v", "looking"),
            ("cd <slot>", "-P", "looking"),
            ("pwd <slot>", "-P", "looking"),
            ("test <slot>", "-e", "looking"),
            ("[ <slot> ]", "-e", "looking"),
            ("true <slot>", "-x", "looking"),
            (": <slot>", "-x", "looking"),
        )
        self.assertEqual((len(forms), len(contexts)), (32, 23))  # 24-35: IN-17 (5fdfe1b)
        # The list grows only with a grounded context (D-30): every name on it but mkdir,
        # whose admission is the setup rule and its D-14 rows, has a looking context here.
        self.assertEqual({c[0].split()[0] for c in contexts if c[2] == "looking"},
                         set(agent._DOUBT_LOOKS_COMMANDS) - {"mkdir"})

        def derive(form, context):
            """The one derivation: True when the cell acts."""
            return not form[2] and context[2] == "acting"

        def command(form, context):
            word = context[1]
            slot = form[0].replace("<w>", word).replace("<t>", word[1:])
            return form[1].replace("<w>", word) + context[0].replace("<slot>", slot)

        def key(form):
            """A form's key, its prefix plus its spelling: an IFS form reuses a plain
            spelling, so the spelling alone collides. # 24-35: IN-17 (5fdfe1b)"""
            return form[1] + form[0]

        cells = [(form, context) for context in contexts for form in forms]
        self.assertEqual(len(cells), 736)  # 24-35: IN-17 (5fdfe1b)
        by_key = {(key(form), context[0]): (form, context) for form, context in cells}
        self.assertEqual(len(by_key), len(cells))
        self.assertEqual(len(by_key), 736)

        def snapshot(root):
            """Every name under ``root`` with its bytes (a directory's are None)."""
            seen = {}
            for dirpath, dirnames, filenames in os.walk(root):
                for name in dirnames:
                    seen[os.path.relpath(os.path.join(dirpath, name), root)] = None
                for name in filenames:
                    path = os.path.join(dirpath, name)
                    with open(path, "rb") as handle:
                        seen[os.path.relpath(path, root)] = handle.read()
            return seen

        def scratch():
            """A fresh holder with a seeded `repo` in it, and the environment `SandboxRepo`
            builds for a host replay (no jail). # 24-35: IN-17 (5fdfe1b)"""
            holder = tempfile.mkdtemp(prefix="crayon-eval-cross-")
            repo = os.path.join(holder, "repo")
            os.mkdir(repo)
            for name, body in (("h", ""), ("f", "a\n"), ("foo", "x\n"),
                               ("pre.sh", "#!/bin/sh\ntouch pwned\ncat \"$1\"\n")):
                with open(os.path.join(repo, name), "w", encoding="utf-8") as handle:
                    handle.write(body)
            os.chmod(os.path.join(repo, "pre.sh"), 0o755)
            return holder, repo, agent.SandboxRepo(repo, sandbox.bin_dir()).env

        # IN-14: a missing tool fails loudly, by name, before any cell runs.
        holder, _, env = scratch()
        shutil.rmtree(holder, ignore_errors=True)
        missing = [name for name in ("bash", "find", "sed", "sort", "rg", "awk", "xargs",
                                     "grep", "egrep", "fgrep", "cat", "ls", "head", "tail",
                                     "wc", "touch", "sh")
                   if shutil.which(name, path=env["PATH"]) is None]
        if missing:
            self.fail("the cross product cannot ground its cells: %s not on the host "
                      "replay's PATH %s; install it, never skip a cell" % (
                          ", ".join(missing), env["PATH"]))

        def bash_acts(typed):
            """``(acted, ran)``: whether `bash -c` under the host-replay environment changed
            the repository, and whether the run completed within the timeout with an exit
            status other than 126 or 127. # 24-35: IN-17 (5fdfe1b)"""
            holder, repo, env = scratch()
            try:
                before = snapshot(repo)
                try:
                    status = subprocess.run(["bash", "-c", typed], cwd=repo, env=env,
                                            stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, timeout=20).returncode
                except subprocess.TimeoutExpired:
                    status = None
                return snapshot(repo) != before, status not in (None, 126, 127)
            finally:
                shutil.rmtree(holder, ignore_errors=True)

        # 24-35: IN-17 (5fdfe1b), the grounded count can fail: a command bash cannot find
        # is not grounded, on every run.
        self.assertEqual(bash_acts("no-such-tool-24-35 -x"), (False, False))

        # The observations, collected once: the classifier per cell and mode, and bash.
        observed, grounded, ungrounded = {}, 0, []
        for form, context in cells:
            typed = command(form, context)
            for python in (False, True):
                observed[(key(form), context[0], "python=%s" % python)] = not agent.looking(
                    typed, python=python)
            acts, ran = bash_acts(typed)
            observed[(key(form), context[0], "bash")] = acts
            if ran:
                grounded += 1
            else:
                ungrounded.append(typed)
        acted = sorted(key[:2] for key, value in observed.items()
                       if key[2] == "bash" and value)
        over = sorted(key[:2] for key, value in observed.items()
                      if key[2] == "bash" and not value and derive(*by_key[key[:2]]))
        counts = "%d cells, %d grounded, %d carried out by bash, %d over-acting" % (
            len(cells), grounded, len(acted), len(over))
        self.assertEqual(ungrounded, [], counts)  # 24-35: IN-17 (5fdfe1b)
        self.assertEqual(grounded, len(cells), counts)
        self.assertEqual(grounded, 736, counts)

        def compare(derivation):
            """The cells, by observer, where ``derivation`` disagrees with the classifier,
            or calls looking a cell bash carried out."""
            out = []
            for key, value in observed.items():
                derived = derivation(*by_key[key[:2]])
                if (key[2] == "bash" and value and not derived) or (
                        key[2] != "bash" and value != derived):
                    out.append(key)
            return sorted(out)

        self.assertEqual(compare(derive), [], counts)
        # The table can fail: flip one cell's expectation and exactly that cell is reported,
        # by both classifier modes and by bash.
        find, sed, sort, rg = contexts[0][0], contexts[1][0], contexts[2][0], contexts[3][0]
        flipped_cell = ("${PATH:+<w>}", find)

        def flipped(form, context):
            acts = derive(form, context)
            # 24-35: IN-17 (5fdfe1b), keyed by prefix plus spelling.
            return not acts if (key(form), context[0]) == flipped_cell else acts

        reported = compare(flipped)
        self.assertEqual(reported, sorted(flipped_cell + (observer,) for observer in
                                          ("python=False", "python=True", "bash")), counts)
        # The table has teeth: bash carried out each headline cell of CR-05, CR-06, WR-22.
        # 24-35: IN-17 (5fdfe1b), and CR-08's IFS family. Cells are keyed by prefix plus
        # spelling.
        headline = (("${PATH:+<w>}", find), ("${_:+<w>}", find), (": <w>; $_", sort),
                    ('"${PATH:+<w>}"', rg), ("${SHELLOPTS//[!-]}<t>", find),
                    ("$(printf %s -)<t>", find), ("$(echo <w>)", sort),
                    ("${x:-<w>}", find), ('"${x:-<w>}"', find),
                    ("IFS=0; $?<w>", sed), ("IFS=0; $?<w>", rg),
                    ("printf -v IFS %s 0; $?<w>", sed))
        self.assertEqual(len(headline), 12)
        self.assertEqual([cell for cell in headline if not observed[cell + ("bash",)]], [],
                         counts)
        # 24-35: IN-17 (5fdfe1b), no split: bash carried out no quoted constant under an
        # IFS prefix, so inside double quotes the list is constant whatever IFS holds.
        split = sorted(cell for cell, (form, context) in by_key.items()
                       if form[2] and "IFS" in form[1] and observed[cell + ("bash",)])
        self.assertEqual(split, [], "bash split a quoted constant: %s" % split)
        # D-14: a cell that is a row pinned by hand (24-26, 24-29, 24-32) agrees with it.
        pinned = {
            # 24-32: test_an_expansion_the_kit_cannot_prove_constant_acts
            "find . -name h ${PATH:+-delete}": True,
            "find . -name h ${_:+-delete}": True,
            ": -o; sort f $_ out": True,
            "rg -e x \"${PATH:+-r}\" -e '--pre=./pre.sh' f": True,
            ": -r; rg -e x \"$_\" -e '--pre=./pre.sh' f": True,
            "find . -name h $(printf %s -)delete": True,
            "find . -name h ${SHELLOPTS//[!-]}delete": True,
            "sed -n s/a/Z/p ${SHELLOPTS//[!-]}i f": True,
            "find . -name h ${x:--delete}": True,
            "find . -name h \"${x:--delete}\"": True,
            "rg -r \"$x\" -e '--pre=./pre.sh' foo .": True,
            # 24-35: CR-08 (5fdfe1b), test_a_constant_outside_double_quotes_is_doubt
            "rg -r $? -e '--pre=./pre.sh' foo .": True,
            # 24-35: IN-17 (5fdfe1b), test_a_constant_outside_double_quotes_is_doubt
            "IFS=0; sed -n s/a/Z/p $?-i f": True,
            "IFS=0; rg -e x $?-r -e '--pre=./pre.sh' f": True,
            "rg -r \"$?\" -e '--pre=./pre.sh' foo .": False,
            "grep -e $x f": False,
            "grep -e ${x} f": False,
            # 24-26: test_an_expansion_that_can_vanish_or_lead_a_word_acts
            "rg -r $x -e '--pre=./pre.sh' foo .": True,
            "awk -F $x '{print}' 'BEGIN{system(\"touch pwned\")}'": True,
            "sed -n s/a/Z/p ${x}-i f": True,
            # 24-29: test_a_vanishing_quoted_or_unreadable_expansion_acts
            "awk -F \"$@\" '{print}' 'BEGIN{system(\"touch pwned\")}'": True,
            "awk -F \"${a[@]}\" '{print}' 'BEGIN{system(\"touch pwned\")}'": True,
            'echo a | xargs -I "$@" echo touch pwned': True,
            "find . -name h ${x:-$y}-delete": True,
            "find . -name h ${x:-${y}}-delete": True,
            "find . -name h ${x}-delete": True,
            "sed -n s/a/Z/p ${x:-$y}-i f": True,
            "awk -F ${x:-$y} '{print}' 'BEGIN{system(\"touch pwned\")}'": True,
            # 24-29: test_an_empty_substitution_that_leads_an_option_word_acts
            "find . -name h $(true)-delete": True,
        }
        met = {command(f, c): derive(f, c) for f, c in cells if command(f, c) in pinned}
        self.assertEqual(len(met), len(pinned))
        self.assertEqual(met, pinned)

    def test_looking_never_swaps_the_warning_filters(self):
        # 24-19: IN-02, looking() runs on the --jobs thread pool, so it holds no
        # process-wide warning state.
        with mock.patch.object(warnings, "catch_warnings", side_effect=AssertionError(
                "looking() swapped the process-wide warning filters")):
            self.assertTrue(agent.looking(r"grep $'\t' f", python=True))

    def test_ansi_c_decodes_as_bash_does(self):
        # 24-22: IN-02 (329fa95) and P-24-62, each checked against bash 5.3.9. An
        # escape outside bash's table is kept as typed, and a decoded NUL ends the
        # $'…' span; a code point past U+10FFFF still cannot be read.
        for body, decoded in ((r"\d+", r"\d+"), (r"\x", r"\x"), (r"\u", r"\u"),
                              (r"\q", r"\q"), (r"\c", r"\c"), (r"a\0b", "a"),
                              (r"\c@x", ""), (r"\x0z", ""), (r"-\x69", "-i")):
            with self.subTest(body=body):
                self.assertEqual(agent._ansi_c(body), decoded)
        self.assertIsNone(agent._ansi_c(r"\U110000"))
        self.assertEqual(agent._unquoted(r"$'a\0b'c"), "ac")
        # bash reads \c\\ as one control character, and a non-ASCII character after
        # \c cannot be read here (it raised TypeError before 24-22), so the part acts.
        self.assertEqual(agent._ansi_c("a\\c\\\\b"), "a\x1cb")
        self.assertIsNone(agent._ansi_c("\\c\u00df"))
        self.assertFalse(agent.looking("grep $'\\c\u00df' f", python=True))

    def test_the_option_tables_place_each_option_one_way(self):
        # 24-22: IN-08 (458b1b3), a guard: no option is both a no-value and a
        # value-taking one for the same tool, and each entry has its table's shape.
        for tool in ("grep", "rg", "git"):
            with self.subTest(tool=tool):
                self.assertFalse(set(agent._NO_VALUE_FLAGS[tool]) & set(agent._VALUE_FLAGS[tool]))
                self.assertFalse(agent._NO_VALUE_LONG[tool] & agent._VALUE_LONG[tool])
                for option in agent._NO_VALUE_LONG[tool] | agent._VALUE_LONG[tool]:
                    self.assertTrue(option.startswith("--"), option)
                for letter in agent._NO_VALUE_FLAGS[tool] + agent._VALUE_FLAGS[tool]:
                    self.assertEqual(len(letter), 1, letter)

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
            # 24-26: P-24-70, quoted: a bare expansion that can vanish acts, and an
            # acting call is never carried out, so out would be None.
            out, _ = self.repo().serve(call(
                "Bash", command='echo "$CRAYON_EVAL_CANARY" "$OPENROUTER_API_KEY"'))
        finally:
            del os.environ["CRAYON_EVAL_CANARY"]
        self.assertIsNotNone(out)
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

    def graded(self, case, replies):
        """``replies`` replayed as a run of ``case`` and graded on its assertions."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(replies)), ctx)
        return grade.grade(case["assert"], tr, {"judge": ctx["judge"]})

    def test_the_closure_cases_refuse_a_question_tool(self):
        """21 IN-03: the closure asks in plain text, never through a question tool."""
        cases = dict((c["id"], c) for c in lanes.load_b())
        for case_id in ("B-44", "B-45", "B-46", "B-47"):
            with self.subTest(case=case_id):
                case = cases[case_id]
                self.assertIn({"kind": "no_tool_call", "tool": "AskUserQuestion"},
                              case["assert"])
                out = self.graded(case, case["oracle"])
                self.assertTrue(out["passed"], out["feedback"])

    def test_b53_bounds_the_intake_to_one_question(self):
        """21 IN-05: the intake asks one question a turn, so a second one fails."""
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
        """21 IN-06: a piped note is ``printf '%s'``, which adds nothing; the
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

    def test_b67_passes_a_located_claim_that_may_be_wrong(self):
        """22 WR-01 (third review) end to end: "the example in the draft could be
        incorrect" locates its claim, on a line that cites no file; it is no hedge."""
        out = self.reworded("B-67", "  → split it into two sentences",
                            "  → split it into two sentences; the example in the draft "
                            "could be incorrect as well: toyq init needs --force-dir")
        self.assertTrue(out["passed"], out["feedback"])

    def test_b68_passes_a_claim_on_the_page_that_may_be_wrong(self):
        """22 WR-01 (third review) end to end: a finding that says the line on the
        page may be wrong, or that cites its claim and says it may be wrong, is
        grounded."""
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
        """24-20, WR-01 end to end: a finding that cites its source anywhere in the
        hedge's clause, before the hedge or after it and with dots in its path, is
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
        """24-23, IN-01 (329fa95) end to end: the dots of "e.g." and "i.e." do not
        end the hedge's clause, so a cite after one grounds it; "etc." before a
        capitalised word still ends it, so a blanket hedge whose cite sits in the
        next sentence fails B-69."""
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
        """24-26, IN-09 (aac605a) and P-24-73 end to end: after "etc." the hedge's
        clause starts exactly where its stop ends one, so a cite before "etc. ("
        grounds a hedge after it, as a cite after "etc. (" does, and a blanket hedge
        in the next sentence fails B-69 whatever whitespace follows "etc."."""
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
        """22 WR-01 (third review) end to end: "I couldn't verify all of it against
        config.py" names what it checked against; it is not a blanket disclaimer."""
        case = dict((c["id"], c) for c in lanes.load_b())["B-69"]
        gap = next(line for line in case["oracle"][-1]["content"].split("\n")
                   if line.startswith("- I found no source"))
        out = self.reworded("B-69", gap,
                            "- I couldn't verify all of it against config.py: no source lists "
                            "the accepted log_level values, so the page gives only the default.")
        self.assertTrue(out["passed"], out["feedback"])

    def test_b70_fails_every_there_may_be_errors_form(self):
        """22 WR-02 (third review) end to end: an agent that disclaims by default
        fails B-70, however it words "there may be errors" or "every detail"."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        case = dict((c["id"], c) for c in lanes.load_b())["B-70"]
        for added in ("There may be errors I missed.", "There may still be errors.",
                      "There might be some errors.", "There may be a few mistakes.",
                      "There may be errors here and there.", "I can't verify every detail."):
            with self.subTest(added=added):
                hedged = [dict(reply) for reply in case["oracle"]]
                hedged[-1]["content"] += "\n\n" + added
                tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(hedged)), ctx)
                out = grade.grade(case["assert"], tr, {"judge": ctx["judge"]})
                self.assertFalse(out["passed"], "B-70 passed %r" % added)
                self.assertIn("not_text_re",
                              set(r["kind"] for r in out["results"] if not r["pass"]), out)

    def test_b69_and_b70_fail_a_blanket_hedge_beside_a_citation(self):
        """24-17, WR-03 end to end: a blanket hedge fails B-69 and B-70 even on a line
        that names the staged page or a source file, because the cite exemption holds
        only inside the hedging clause; each oracle unchanged still passes."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        cases = dict((c["id"], c) for c in lanes.load_b())

        def appended(case_id, added):
            case = cases[case_id]
            hedged = [dict(reply) for reply in case["oracle"]]
            hedged[-1]["content"] += added
            tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(hedged)), ctx)
            return grade.grade(case["assert"], tr, {"judge": ctx["judge"]})

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
            refused = [spec["re"] for spec in case["assert"] if spec["kind"] == "not_text_re"]
            for pattern in NOTICE_NOT_RES:
                with self.subTest(case=case["id"], not_re=pattern):
                    self.assertIn(pattern, refused)
        self.assertTrue(conversation_key(b65) != conversation_key(b75),
                        "B-65 and B-75 are one conversation")
        tr = lanes.run_b(b65, SPEC, StubProvider(run.scripted(b75["foil"])), ctx)
        out = grade.grade(b65["assert"], tr, {"judge": ctx["judge"]})
        self.assertFalse(out["passed"], "the bare verdict question passed B-65")
        self.assertIn("text_re", set(r["kind"] for r in out["results"] if not r["pass"]), out)

    def test_b04_names_the_version_the_skills_need(self):
        """D-07, D-08: B-04 is the version-stop case, so the version it names is
        the one the skills need: ``crayon.py``'s ``__version__``, read through the
        lint. The case file is then a checked copy, not a second definition site.
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
        """24-15, B-01 and B-02: a chain runs its commands in order, as two calls in one
        turn do, so a chained opening opens on version, then the state read. The closing
        run's two models chained it and failed on the second command, which the grader
        hid; the feedback now names what really ran, and the order still binds."""
        cases = dict((c["id"], c) for c in lanes.load_b())
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}

        def bash_turn(command):
            return {"content": "", "tool_calls": [
                {"name": "Bash", "arguments": {"command": command}}]}

        def graded(case_id, replies):
            case = cases[case_id]
            tr = lanes.run_b(case, SPEC, StubProvider(run.scripted(replies)), ctx)
            return [item for item in grade.grade(case["assert"], tr,
                                                 {"judge": ctx["judge"]})["results"]
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
        # 24-17: WR-02 probe, an inert tail after the version call changes nothing.
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
        """24-15, B-18: the history is the writer's own work up to a ``busy`` refusal, so
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
        """24-15, B-69: the history hands the writer a draft as its own, just recorded,
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
        """24-15, B-57: a history replays the model's own onboarding report, so its gap
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
        """D-12, 23 WR-03: B-30 replays the intake past both fixed questions,
        quoted as the plan skill writes them, so the turn under test is step 3's
        proposal of the mechanical fields. Offline the stub judge passes any
        reply, so the asking foil has to fail a deterministic assertion: a
        ``text_re`` that names the source the repository answers."""
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
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        tr = lanes.run_b(b30, SPEC, StubProvider(run.scripted(b30["foil"])), ctx)
        out = grade.grade(b30["assert"], tr, {"judge": ctx["judge"]})
        self.assertFalse(out["passed"], "B-30 passed a reply that asks for the source")
        self.assertIn("text_re", set(r["kind"] for r in out["results"] if not r["pass"]), out)
        tr = lanes.run_b(b30, SPEC, StubProvider(run.scripted(b30["oracle"])), ctx)
        out = grade.grade(b30["assert"], tr, {"judge": ctx["judge"]})
        self.assertTrue(out["passed"], out["feedback"])

    def test_b64_reads_a_step_claim_that_contains_no(self):
        """D-13, 23 IN-01: B-64's exception excuses a line that says no step was
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
        # The 24-05 replay audit: glm-5.3 run 1 of the 2026-10-11 sweep said this, rightly.
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
        """D-13, 22 IN-01: B-40's ``why`` says the provenance summary comes
        first, so a verdict question asked without it fails B-40 itself, not
        only its sibling B-31."""
        ctx = {"skills": skillmod.load_skills(), "cache": False,
               "judge": (StubProvider(run.stub_judge), SPEC)}
        b40 = dict((c["id"], c) for c in lanes.load_b())["B-40"]
        bare = [dict(reply) for reply in b40["oracle"]]
        self.assertRegex(bare[-1]["content"], r"record:\s+intact\s+at")
        bare[-1]["content"] = ""
        tr = lanes.run_b(b40, SPEC, StubProvider(run.scripted(bare)), ctx)
        out = grade.grade(b40["assert"], tr, {"judge": ctx["judge"]})
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
        """22 WR-03 end to end: step 3a's notice said three faithful ways passes
        B-65 and B-75; a correct model must not lose either on word choice."""
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
        """23 IN-02 end to end: the widened pair must not admit a reply that says
        the answer is never recorded; ``NOTICE_NOT_RES`` fails it."""
        for case_id in ("B-65", "B-75"):
            with self.subTest(case=case_id):
                out = self.renoticed(case_id, "That answer is never recorded, not even "
                                              "with a fix verdict.")
                self.assertFalse(out["passed"], "%s passed the opposite claim" % case_id)
                self.assertIn("not_text_re",
                              set(r["kind"] for r in out["results"] if not r["pass"]), out)

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
            # 21 IN-06: piped through printf '%s', which adds nothing; '%s\n' adds a newline.
            ("B-37", [bash("crayon review cfg --verdict fix --note '%s'" % fix)], True),
            ("B-37", [bash('crayon review cfg --verdict fix --note "%s"' % fix)], True),
            ("B-37", [bash("printf '%%s' '%s' | crayon review cfg --verdict fix --note-file -"
                           % fix)], True),
            ("B-37", [bash("printf '%%s\\n' '%s' | crayon review cfg --verdict fix --note-file -"
                           % fix)], False),
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
            # WR-10: resuming is a mechanical choice and may keep its marked default.
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
        # 24-26: P-24-69 keep
        self.assertEqual(text("crayon draft cfg x; echo exit: $?"), "crayon draft cfg x")

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

    _cases_b = None

    @classmethod
    def lane_b_case(cls, judged=False):
        """The first lane-B case with one judged assertion, or with none."""
        if cls._cases_b is None:
            cls._cases_b = lanes.load_b()
        return next(case for case in cls._cases_b
                    if sum(s["kind"] == "judge" for s in case["assert"]) == int(judged))

    @staticmethod
    def run_ctx(judge=None):
        return {"skills": skillmod.load_skills(), "cache": True,
                "judge": (judge or StubProvider(run.stub_judge), SPEC)}

    SUMMARY_CTX = {"judge_id": "j", "date": "2026-01-02", "crayon_version": "v",
                   "repo_head": "abc1234", "skills_sha256": "0" * 64}

    def test_an_empty_answer_is_retried_once_uncached(self):
        """D-24: one empty lane-B turn is re-sent once, uncached, and the case goes on."""
        case = self.lane_b_case()
        stub = CacheRecordingStub(run.scripted([EMPTY] + lanes.oracle_b(case)))
        record, _ = run.run_one(lanes.LANES["B"], case, SPEC, stub, self.run_ctx())
        self.assertIsNone(record["error"])
        self.assertTrue(record["passed"], record.get("failed"))
        self.assertEqual(record.get("retries"), 1)
        self.assertEqual(stub.caches[:2], [True, False])

    def test_an_answer_empty_twice_is_a_run_level_error(self):
        """D-24: still empty after the one retry, the case errors and the run is filed errored."""
        case = self.lane_b_case()
        stub = CacheRecordingStub(run.scripted([EMPTY, EMPTY] + lanes.oracle_b(case)))
        record, _ = run.run_one(lanes.LANES["B"], case, SPEC, stub, self.run_ctx())
        self.assertIn("empty answer", record["error"] or "")
        self.assertFalse(record["passed"])
        self.assertEqual(record.get("retries"), 1)
        self.assertEqual(len(stub.calls), 2)
        summary = run.summarise("B", SPEC, [record], self.SUMMARY_CTX, False, None, False)
        meta = summary["meta"]
        self.assertEqual((meta["errors"], meta["failed"]), (1, 0))
        self.assertEqual(meta.get("retries"), 1)
        with tempfile.TemporaryDirectory() as tmp:
            saved = run.RESULTS, run.RAW
            run.RESULTS, run.RAW = Path(tmp), Path(tmp) / "raw"
            try:
                path = run.destination(summary, "120000")
            finally:
                run.RESULTS, run.RAW = saved
            self.assertEqual(path.parent, Path(tmp) / "raw")
            self.assertTrue(path.name.endswith("-errored.json"), path.name)

    def test_retries_are_summed_across_runs(self):
        """D-24: the K-run combine sums ``meta.retries``; it does not keep run 1's."""
        records = [{"id": "B-01", "passed": True, "error": None, "cost": 0.0, "retries": 1},
                   {"id": "B-02", "passed": True, "error": None, "cost": 0.0, "retries": 2}]
        single = run.summarise("B", SPEC, records, self.SUMMARY_CTX, False, None, False)
        runs = [dict(single, meta=dict(single["meta"], retries=n)) for n in (1, 0, 2)]
        self.assertEqual(run.aggregate(runs)["meta"].get("retries"), 3)
        self.assertEqual(single["meta"].get("retries"), 3)

    def test_an_empty_lane_a_answer_is_retried_once_uncached(self):
        """D-24: lane A re-sends one empty answer once, uncached; empty twice is an error."""
        case = lanes.load_a()[0]
        stub = CacheRecordingStub(run.scripted(["", case["expect"]]))
        record, _ = run.run_one(lanes.LANES["A"], case, SPEC, stub, self.run_ctx())
        self.assertIsNone(record["error"])
        self.assertTrue(record["passed"], record.get("failed"))
        self.assertEqual(record.get("retries"), 1)
        self.assertEqual(stub.caches, [True, False])
        twice = CacheRecordingStub(run.scripted(["", "", case["expect"]]))
        record, _ = run.run_one(lanes.LANES["A"], case, SPEC, twice, self.run_ctx())
        self.assertIn("empty answer", record["error"] or "")
        self.assertEqual(record.get("retries"), 1)
        self.assertEqual(len(twice.calls), 2)

    def test_an_unparsable_judge_reply_is_retried_once_uncached(self):
        """D-24: the judge's unparsable reply is re-asked once, uncached, and counted."""
        case = self.lane_b_case(judged=True)
        verdict = run.stub_judge(None, None, None)
        judge = CacheRecordingStub(run.scripted(["not json", verdict]))
        model = StubProvider(run.scripted(lanes.oracle_b(case)))
        record, _ = run.run_one(lanes.LANES["B"], case, SPEC, model, self.run_ctx(judge))
        self.assertIsNone(record["error"])
        self.assertTrue(record["passed"], record.get("failed"))
        self.assertEqual(record.get("retries"), 1)
        self.assertEqual(judge.caches, [True, False])
        twice = CacheRecordingStub(run.scripted(["not json"]))
        model = StubProvider(run.scripted(lanes.oracle_b(case)))
        record, _ = run.run_one(lanes.LANES["B"], case, SPEC, model, self.run_ctx(twice))
        self.assertIn("judge returned no JSON object", record["error"] or "")
        self.assertEqual(record.get("retries"), 1)
        self.assertEqual(len(twice.calls), 2)

    def test_a_judge_cache_failure_is_a_run_level_error(self):
        """24-20, IN-03: a judge cache that cannot be written fails its one case as a
        recorded run-level error; no exception escapes ``run_one`` to stop the sweep."""
        case = self.lane_b_case(judged=True)
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "cache"
            blocker.write_text("", encoding="utf-8")
            judge = client(FakeOpener(ok_body(run.stub_judge(None, None, None))),
                           Budget(10.0), cache_dir=str(blocker))
            model = StubProvider(run.scripted(lanes.oracle_b(case)))
            try:
                record, _ = run.run_one(lanes.LANES["B"], case, SPEC, model,
                                        self.run_ctx(judge))
            except OSError as exc:
                self.fail("a judge cache failure escaped run_one: %r" % exc)
        self.assertIn("judge API error", record["error"] or "")
        self.assertIn("cache", record["error"] or "")
        self.assertFalse(record["passed"])
        # 24-23, WR-02 (329fa95): the judge's call was paid; the record counts it.
        self.assertAlmostEqual(record["cost"], 0.0123)

    def test_a_lane_a_cache_failure_records_its_cost(self):
        """24-23, WR-02 (329fa95): a lane-A answer whose cache entry cannot be written
        is a run-level error whose record still counts the paid call."""
        case = lanes.load_a()[0]
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "cache"
            blocker.write_text("", encoding="utf-8")
            paid = client(FakeOpener(ok_body(case["expect"])), Budget(10.0),
                          cache_dir=str(blocker))
            record, _ = run.run_one(lanes.LANES["A"], case, SPEC, paid, self.run_ctx())
        self.assertIn("cache", record["error"] or "")
        self.assertFalse(record["passed"])
        self.assertAlmostEqual(record["cost"], 0.0123)

    def test_a_budget_stop_records_a_case_that_ran_as_stopped(self):
        """24-27, WR-11 (aac605a): a case the spend cap stops after it paid is recorded
        as ``stopped:`` with what it paid, in its place, so the run's ``cost_usd``
        agrees with the spend; only a case the cap refused before any paid call reads
        ``not run:``, at 0.0. Pinned on the three paths the review names."""
        bogen = [{"id": "b1", "type": "function",
                  "function": {"name": "Bogen", "arguments": "{}"}}]

        def one(lane, case, provider, ctx):
            records, _, stopped = run.run_lane(lane, [case], SPEC, lambda c: provider, ctx, 1)
            self.assertEqual([r["id"] for r in records], [case["id"]])
            return records[0], records, stopped

        with self.subTest(path="lane A, the empty-answer retry refused"):
            case = lanes.load_a()[0]
            budget = Budget(0.01)
            paid = client(FakeOpener(ok_body(content=""), ok_body(case["expect"])), budget)
            record, records, stopped = one("A", case, paid, self.run_ctx())
            self.assertTrue(record["error"].startswith("stopped: spend cap reached"),
                            record["error"])
            self.assertAlmostEqual(budget.spent, 0.0123)
            self.assertAlmostEqual(record["cost"], budget.spent)
            self.assertTrue(stopped)
            meta = run.summarise("A", SPEC, records, self.SUMMARY_CTX, False, stopped,
                                 False)["meta"]
            self.assertAlmostEqual(meta["cost_usd"], budget.spent)
        with self.subTest(path="lane B, stopped on the second turn"):
            if sandbox.jail() is None:
                self.skipTest("no usable bwrap here; a live lane B run refuses too")
            case = self.lane_b_case()
            paid = client(FakeOpener(ok_body(content=None, calls=bogen), ok_body("x")),
                          Budget(0.01))
            record, _, _ = one("B", case, paid, self.run_ctx())
            self.assertTrue(record["error"].startswith("stopped: "), record["error"])
            self.assertAlmostEqual(record["cost"], 0.0123)
        with self.subTest(path="the judge's retry refused"):
            case = self.lane_b_case(judged=True)
            judge = client(FakeOpener(ok_body("not json"),
                                      ok_body(run.stub_judge(None, None, None))),
                           Budget(0.01))
            model = StubProvider(run.scripted(lanes.oracle_b(case)))
            record, _, _ = one("B", case, model, self.run_ctx(judge))
            self.assertTrue(record["error"].startswith("stopped: "), record["error"])
            self.assertAlmostEqual(record["cost"], 0.0123)
        with self.subTest(path="refused before any paid call"):
            case = lanes.load_a()[0]
            paid = client(FakeOpener(ok_body(case["expect"])), Budget(0.0))
            record, _, stopped = one("A", case, paid, self.run_ctx())
            self.assertTrue(record["error"].startswith("not run: "), record["error"])
            self.assertEqual(record["cost"], 0.0)
            self.assertTrue(stopped)

    #: WR-13's mutation table: each cost-adding statement of ``run_one``'s
    #: ``except BudgetExceeded`` arm, verbatim, and the scenario whose record it
    #: must change. Re-derive it if ``run_one`` is refactored: the test refuses a
    #: statement that does not occur exactly once.
    BUDGET_STOP_MUTANTS = (
        ('exc.cost += case_ctx.get("judge_cost", 0.0)', "judge's retry refused after a paid lane"),
        ('exc.cost += sum(turn["usage"]["cost"] for turn in trace["turns"])',
         "judge's first call refused"),
    )

    def test_a_paid_lane_then_a_refused_judge_records_its_cost(self):
        """24-30, WR-13 (1ba4892): a case whose lane turns were paid and whose judge
        call the cap then refuses is recorded ``stopped:`` with the lane's paid cost,
        plus the judge's first call when only its retry was refused. The test carries
        its own mutation proof: an in-memory mutant of ``run_one`` per cost-adding
        statement of its budget-stop arm must fail the same predicate the real
        records pass, or the test fails with ``mutant survived``. No file is written."""
        case = self.lane_b_case(judged=True)
        verdict = run.stub_judge(None, None, None)

        class PaidStub(StubProvider):
            """The stub, each of whose replayed turns costs 0.0123."""

            def complete(self, spec, messages, tools=None, cache=True, scope=None):
                turn = StubProvider.complete(self, spec, messages, tools=tools, cache=cache,
                                             scope=scope)
                turn["usage"]["cost"] = 0.0123
                return turn

        scenarios = {
            "judge's first call refused": ((ok_body(verdict),), 0.0, 0.0),
            "judge's retry refused after a paid lane":
                ((ok_body("not json"), ok_body(verdict)), 0.01, 0.0123),
        }

        def scenario(label):
            """(record, expected cost) for one scenario, through ``run.run_lane``."""
            script, cap, judge_paid = scenarios[label]
            lane = PaidStub(run.scripted(lanes.oracle_b(case)))
            judge = client(FakeOpener(*script), Budget(cap))
            records, _, _ = run.run_lane("B", [case], SPEC, lambda c: lane,
                                         self.run_ctx(judge), 1)
            self.assertEqual([r["id"] for r in records], [case["id"]])
            self.assertGreater(len(lane.calls), 0)
            return records[0], 0.0123 * len(lane.calls) + judge_paid

        def holds(record, expected):
            return (record["error"] or "").startswith("stopped: ") and \
                abs(record["cost"] - expected) < 1e-6

        for label in scenarios:
            with self.subTest(path=label):
                record, expected = scenario(label)
                self.assertTrue(holds(record, expected), (record, expected))
        with self.subTest(path="the pin bites"):
            source = inspect.getsource(run.run_one)
            for statement, label in self.BUDGET_STOP_MUTANTS:
                self.assertEqual(source.count(statement), 1,
                                 "re-derive the mutation table: %s" % statement)
                namespace = dict(vars(run))
                exec(compile(source.replace(statement, "pass"), run.__file__, "exec"),
                     namespace)
                with mock.patch.object(run, "run_one", namespace["run_one"]):
                    record, expected = scenario(label)
                if holds(record, expected):
                    self.fail("mutant survived: %s" % statement)

    def test_a_budget_reached_at_preflight_is_a_clean_stop(self):
        """24-30, WR-16 (1ba4892): a budget already spent when a preflight runs, the
        judge's or a model's, ends the run as a budget stop, code 2, with a stop line
        on stderr; ``BudgetExceeded`` does not escape ``main`` as a traceback."""
        gate = run.load_roster()[0]["gate"]
        for label, argv in (("preflight_judge", ["B", "--model", gate, "--budget", "0"]),
                            ("preflight_model", ["A", "--model", gate, "--budget", "0"])):
            with self.subTest(preflight=label):
                opener = FakeOpener()

                def paid(budget, cache_dir=None):
                    return OpenRouter(budget, api_key="sk-test", sleep=lambda s: None,
                                      opener=opener)

                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(run, "OpenRouter", paid), \
                        mock.patch.object(run.sandbox, "jail", return_value=object()), \
                        mock.patch.object(sys, "stdout", out), \
                        mock.patch.object(sys, "stderr", err):
                    try:
                        code = run.main(argv)
                    except BudgetExceeded as exc:
                        self.fail("a budget stop at %s escaped main: %r" % (label, exc))
                self.assertEqual(code, 2)
                self.assertIn("budget stop: spend cap reached", err.getvalue())
                self.assertIn(label, err.getvalue())
                self.assertNotIn("Traceback", err.getvalue())
                self.assertEqual(opener.requests, [], "a refused preflight was sent")

    def test_a_run_level_error_is_recorded_not_raised(self):
        """24-30, WR-17 (1ba4892), the backstop: an exception from ``lane["run"]``
        that is not a ``ProviderError``, a ``GradeError`` or a budget stop is the
        case's run-level error, recorded, never raised; ``run_lane`` goes on to the
        next case rather than one malformed turn aborting every remaining case."""
        cases = lanes.load_a()[:2]
        real = lanes.LANES["A"]["run"]

        def flaky(case, spec, provider, ctx):
            if case["id"] == cases[0]["id"]:
                raise RuntimeError("a malformed turn")
            return real(case, spec, provider, ctx)

        lane = dict(lanes.LANES["A"], run=flaky)
        try:
            record, trace = run.run_one(lane, cases[0], SPEC, StubProvider(), self.run_ctx())
        except RuntimeError as exc:
            self.fail("a lane exception escaped run_one: %r" % exc)
        self.assertIsNone(trace)
        self.assertIn("RuntimeError: a malformed turn", record["error"] or "")
        self.assertFalse(record["passed"])
        with mock.patch.dict(lanes.LANES, {"A": lane}):
            records, _, stopped = run.run_lane(
                "A", cases, SPEC, lambda c: StubProvider(run.scripted([c["expect"]])),
                self.run_ctx(), 1)
        self.assertIsNone(stopped)
        self.assertEqual([r["id"] for r in records], [c["id"] for c in cases])
        self.assertIn("RuntimeError", records[0]["error"] or "")
        self.assertIsNone(records[1]["error"])
        self.assertTrue(records[1]["passed"], records[1].get("failed"))
        summary = run.summarise("A", SPEC, records, self.SUMMARY_CTX, False, None, False)
        self.assertEqual(summary["meta"]["errors"], 1)

    def test_the_cost_claim_names_the_preflight_spend(self):
        """24-30, IN-12 (1ba4892): a run's ``cost_usd`` is every case's paid cost, not
        ``budget.spent``: the two preflights charge the budget and are on no case
        record, and ``run.py`` says so rather than claiming the two are equal."""
        doc = " ".join((run.summarise.__doc__ or "").split())
        self.assertIn("every case's paid cost", doc)
        self.assertIn("preflight_judge", doc)
        self.assertIn("preflight_model", doc)
        flat = " ".join(inspect.getsource(run).split())
        self.assertIsNone(re.search(
            r"cost_usd\W*(?:equals|agrees with|is equal to)\W*(?:the )?(?:budget\.spent|spend)",
            flat), "run.py states an unqualified cost_usd equal to the spend")

    def test_a_partial_cache_entry_does_not_stop_the_sweep(self):
        """24-27, WR-12 (aac605a): an entry at a lane-A request's key whose ``usage``
        holds no token counts is a miss, not a hit ``run_one`` would raise
        ``KeyError`` on: the call is made once and the case is graded."""
        case = lanes.load_a()[0]
        skills = skillmod.load_skills()
        msgs = [{"role": "system", "content": skillmod.selection_system_prompt(skills)},
                {"role": "user", "content": case["ask"]}]
        with tempfile.TemporaryDirectory() as tmp:
            opener = FakeOpener(ok_body(case["expect"]))
            paid = client(opener, Budget(10.0), cache_dir=tmp)
            paid._cache_path(SPEC, msgs).write_text(
                '{"content": "crayon-plan", "usage": {}}', encoding="utf-8")
            try:
                record, _ = run.run_one(lanes.LANES["A"], case, SPEC, paid, self.run_ctx())
            except KeyError as exc:
                self.fail("a partial cache entry escaped run_one: %r" % exc)
        self.assertIsNone(record["error"])
        self.assertTrue(record["passed"], record.get("failed"))
        self.assertEqual(len(opener.requests), 1)

    def test_a_hostile_cache_entry_does_not_stop_the_sweep(self):
        """24-30, WR-14 (1ba4892): an entry at a lane-A request's key whose
        ``served_by`` is a list is a miss, not a hit ``run_one`` would raise
        ``TypeError`` on outside its ``try``: the call is made once, the case is
        graded, and a hostile or hand-edited entry costs one call, not the sweep."""
        case = lanes.load_a()[0]
        skills = skillmod.load_skills()
        msgs = [{"role": "system", "content": skillmod.selection_system_prompt(skills)},
                {"role": "user", "content": case["ask"]}]
        with tempfile.TemporaryDirectory() as tmp:
            opener = FakeOpener(ok_body(case["expect"]))
            paid = client(opener, Budget(10.0), cache_dir=tmp)
            paid._cache_path(SPEC, msgs).write_text(json.dumps(
                {"content": "x", "tool_calls": [], "finish_reason": "stop",
                 "served_by": ["a"],
                 "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}}),
                encoding="utf-8")
            try:
                record, _ = run.run_one(lanes.LANES["A"], case, SPEC, paid, self.run_ctx())
            except TypeError as exc:
                self.fail("a hostile cache entry escaped run_one: %r" % exc)
        self.assertIsNone(record["error"])
        self.assertTrue(record["passed"], record.get("failed"))
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(record["served_by"], ["Vendor"])

    def test_a_malformed_live_response_does_not_stop_the_sweep(self):
        """24-33, WR-18 (802e0e3), end to end: a live body whose ``provider`` is a list
        is charged and refused as a ``ProviderError`` that its case records with the
        charge; ``run_lane`` goes on to the next case, and the budget holds both."""
        cases = lanes.load_a()[:2]
        budget = Budget(10.0)
        first = ok_body(cases[0]["expect"])
        first["provider"] = ["Vendor"]  # 24-33: WR-18 (802e0e3)
        bodies = {cases[0]["id"]: first, cases[1]["id"]: ok_body(cases[1]["expect"])}
        try:
            records, _, stopped = run.run_lane(
                "A", cases, SPEC, lambda c: client(FakeOpener(bodies[c["id"]]), budget),
                self.run_ctx(), 1)
        except Exception as exc:  # noqa: BLE001 - any escape is the bug
            self.fail("a malformed live response escaped run_lane: %r" % exc)
        self.assertIsNone(stopped)
        self.assertEqual([r["id"] for r in records], [c["id"] for c in cases])
        self.assertTrue((records[0]["error"] or "").startswith("malformed response"),
                        records[0]["error"])
        self.assertAlmostEqual(records[0]["cost"], 0.0123, delta=1e-9)
        self.assertIsNone(records[1]["error"])
        self.assertTrue(records[1]["passed"], records[1].get("failed"))
        self.assertAlmostEqual(budget.spent, 0.0246, delta=1e-9)

    def test_a_bookkeeping_error_is_a_run_level_error(self):
        """24-33, WR-18 (802e0e3), the backstop: a line of ``run_one``'s bookkeeping
        after its ``try`` that raises, here on a turn whose ``served_by`` is a list
        from a provider that bypasses ``normalise``, is the case's ``run error:``,
        with the turn's paid cost kept and nothing raised to ``run_lane``."""
        case = lanes.load_a()[0]

        class ListServedBy(StubProvider):  # 24-33: WR-18 (802e0e3)
            """The stub, its turn paid at 0.0123 and labelled with a list."""

            def complete(self, spec, messages, tools=None, cache=True, scope=None):
                turn = StubProvider.complete(self, spec, messages, tools=tools, cache=cache,
                                             scope=scope)
                turn["usage"]["cost"] = 0.0123
                turn["served_by"] = ["x"]
                return turn

        provider = ListServedBy(run.scripted([case["expect"]]))
        try:
            record, _ = run.run_one(lanes.LANES["A"], case, SPEC, provider, self.run_ctx())
        except Exception as exc:  # noqa: BLE001 - any escape is the bug
            self.fail("a bookkeeping error escaped run_one: %r" % exc)
        self.assertTrue((record["error"] or "").startswith("run error: TypeError"),
                        record["error"])
        self.assertAlmostEqual(record["cost"], 0.0123, delta=1e-9)
        self.assertFalse(record["passed"])

    def test_an_answer_lost_after_a_paid_turn_keeps_its_cost(self):  # 24-36: WR-24 (5fdfe1b)
        """24-36: WR-24 and WR-25 of the review at 5fdfe1b, the verifier's repro end to
        end: turn 1 is a paid tool call at $0.05, and turn 2's body is lost while it
        is read (``IncompleteRead``). ``run_one`` raises nothing and records a
        ``transport:`` error whose cost equals ``budget.spent``: the paid turn the
        episode held, plus the lost answer's estimate, after exactly two requests."""
        bogen = [{"id": "b1", "type": "function",
                  "function": {"name": "Bogen", "arguments": "{}"}}]
        budget = Budget(10.0)
        opener = FakeOpener(ok_body(content=None, calls=bogen, cost=0.05),
                            ReadFails(http.client.IncompleteRead(b"{", 10)))

        def episode(case, spec, provider, ctx):
            return agent.run_episode(provider, spec, [{"role": "user", "content": "go"}],
                                     None, None, cache=False)

        lane = dict(lanes.LANES["A"], run=episode)
        try:
            record, _ = run.run_one(lane, lanes.load_a()[0], SPEC, client(opener, budget),
                                    self.run_ctx())
        except Exception as exc:  # noqa: BLE001 - any escape is the bug
            self.fail("run_one raised %s: %r" % (type(exc).__name__, exc))
        self.assertEqual(record["cost"], round(budget.spent, 6),
                         "the record's cost is not what was spent: %r" % (record,))
        self.assertEqual(len(opener.requests), 2)
        self.assertTrue((record["error"] or "").startswith("transport:"), record["error"])
        self.assertIn("IncompleteRead", record["error"])
        self.assertAlmostEqual(
            budget.spent, 0.05 + (len(opener.requests[1].data) * 1.0 + 512 * 2.0) / 1e6,
            delta=1e-9)

    def test_an_unexpected_error_mid_episode_keeps_the_paid_turns(self):
        """24-36: WR-24 of the review at 5fdfe1b, and the 24-30 residual in
        deferred-items.md. An exception that is not a ``ProviderError`` or a budget
        stop, raised mid-episode by a tool or by the empty-answer retry, becomes a
        ``ProviderError`` (``run error: <Type>: <message>``, caused by the original)
        that carries the turns already paid, so the case's record keeps them."""
        msgs = [{"role": "user", "content": "go"}]
        read = [{"id": "r1", "type": "function",
                 "function": {"name": "Read", "arguments": json.dumps({"file_path": "x"})}}]

        class Broken(object):
            def serve(self, call):
                raise RuntimeError("tool broke")

        def paid_read(budget):
            return client(FakeOpener(ok_body(content=None, calls=read, cost=0.05)), budget)

        with self.subTest(path="a raising tool"):  # 24-36: WR-24 (5fdfe1b)
            budget = Budget(10.0)

            def episode(case, spec, provider, ctx):
                return agent.run_episode(provider, spec, msgs, None, Broken(), cache=False)

            lane = dict(lanes.LANES["A"], run=episode)
            try:
                record, _ = run.run_one(lane, lanes.load_a()[0], SPEC, paid_read(budget),
                                        self.run_ctx())
            except Exception as exc:  # noqa: BLE001 - any escape is the bug
                self.fail("run_one raised %s: %r" % (type(exc).__name__, exc))
            self.assertTrue((record["error"] or "").startswith(
                "run error: RuntimeError: tool broke"), record["error"])
            self.assertEqual(record["cost"], round(budget.spent, 6),
                             "the record's cost is not what was spent: %r" % (record,))
            self.assertAlmostEqual(record["cost"], 0.05, delta=1e-9)
            self.assertFalse(record["passed"])
            try:
                agent.run_episode(paid_read(Budget(10.0)), SPEC, msgs, None, Broken(),
                                  cache=False)
            except ProviderError as exc:
                self.assertIsInstance(exc.__cause__, RuntimeError)
            except Exception as exc:  # noqa: BLE001 - any other type is the bug
                self.fail("run_episode raised %s: %r, not a ProviderError"
                          % (type(exc).__name__, exc))
            else:
                self.fail("run_episode returned past a raising tool")

        class RetryBreaks(StubProvider):
            """An empty turn paid at 0.01, then a retry that raises."""

            def complete(self, spec, messages, tools=None, cache=True, scope=None):
                if self.calls:
                    raise RuntimeError("retry broke")
                turn = StubProvider.complete(self, spec, messages, tools=tools,
                                             cache=cache, scope=scope)
                turn["content"] = ""
                turn["usage"]["cost"] = 0.01
                return turn

        with self.subTest(path="a raising retry"):  # 24-36: WR-24 (5fdfe1b)
            try:
                agent.run_episode(RetryBreaks(), SPEC, msgs, None, None, cache=False)
            except ProviderError as exc:
                raised = exc
            except Exception as exc:  # noqa: BLE001 - any other type is the bug
                self.fail("run_episode raised %s: %r, not a ProviderError"
                          % (type(exc).__name__, exc))
            else:
                self.fail("run_episode returned past a raising retry")
            self.assertTrue(str(raised).startswith("run error: RuntimeError: retry broke"),
                            str(raised))
            self.assertAlmostEqual(raised.cost, 0.01, delta=1e-9)

    def test_the_changelog_names_no_cap_figure(self):
        """D-22 / 23 WR-04: the caps have one definition site, ``caps`` in models.json."""
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        unreleased = text.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        entries = [entry for entry in re.split(r"\n(?=- |### )", unreleased)
                   if "Lane B checks" in entry]
        self.assertEqual(len(entries), 1, "the evals entry is not found once")
        self.assertIn("validation/evals/models.json", entries[0])
        self.assertIsNone(re.search(r"\$\d", entries[0]),
                          "the evals entry types a cap figure; point at models.json")

    def test_an_unknown_model_is_refused_before_anything_runs(self):
        stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            self.assertEqual(run.main(["A", "--model", "vendor/not-listed", "--dry-run"]), 2)
        finally:
            sys.stderr = stderr


if __name__ == "__main__":
    unittest.main()
