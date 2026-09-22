"""Assertions over what a model did, each answering ``{pass, score, feedback}``.

Dev-time evaluation material. A case is a list of assertion specs; every spec
names its ``kind`` and the kind's own fields. A case passes only when every
assertion passes. ``feedback`` is always a sentence a reader — or a later text
optimiser — can act on: it names what was expected and what was seen, never
just "failed".

Deterministic kinds come first and carry most of the weight. ``judge`` is for
the judgement calls that resist a regex (routing voice, one question per turn)
and goes through a pinned model, never whichever one happens to be configured.

Grading reads a *trace*: ``{"turns": [normalised assistant turns]}``. The kinds
below read the LAST turn unless they say otherwise; the lanes that replay a
history put only the live turn(s) in ``turns``.
"""

import json
import re

from openrouter import ProviderError

SKILL_NAMES = (
    "dogen-onboard",
    "dogen-fetch",
    "dogen-plan",
    "dogen-write",
    "dogen-review",
)
_CHOICE_RE = re.compile(r"\b(dogen-(?:onboard|fetch|plan|write|review)|none)\b")

#: Words that turn a mention into a warning: "never run `git commit`" names the
#: command without prescribing it. Read on the text BEFORE the match, on the
#: same line, so "run git commit, never skip it" still counts as prescribing.
_NEGATION_RE = re.compile(
    r"(?i)\b(don'?t|do not|never|not|avoid|won'?t|will not|must not|"
    r"should not|shouldn'?t|cannot|can'?t|without|instead of|rather than|"
    r"refus\w*|declin\w*|forbid\w*)\b"
)

#: A degenerate loop repeats itself: few distinct 60-character shingles for its
#: length. Short answers are never judged degenerate.
_SHINGLE = 60
_DEGENERATE_MIN_CHARS = 6000
_DEGENERATE_DIVERSITY = 0.5


class GradeError(Exception):
    """An assertion that could not be evaluated: the case is an error."""


def result(passed, feedback, score=None):
    return {
        "pass": bool(passed),
        "score": (1.0 if passed else 0.0) if score is None else float(score),
        "feedback": feedback,
    }


def call_text(call):
    """The text an ``args_re`` matches: a shell command as typed, else JSON."""
    try:
        arguments = json.loads(call.get("arguments") or "{}")
    except ValueError:
        return call.get("arguments") or ""
    if isinstance(arguments, dict) and isinstance(arguments.get("command"), str):
        return arguments["command"]
    return json.dumps(arguments, sort_keys=True)


def render_call(call):
    return "%s(%s)" % (call.get("name"), call_text(call))


def _last(trace):
    turns = trace.get("turns") or []
    if not turns:
        raise GradeError("the trace holds no assistant turn to grade")
    return turns[-1]


def _all_calls(trace):
    return [call for turn in trace.get("turns") or [] for call in turn["tool_calls"]]


def _matches(call, spec):
    if spec.get("tool") and call.get("name") != spec["tool"]:
        return False
    if spec.get("args_re") and not re.search(spec["args_re"], call_text(call)):
        return False
    return True


def turn_error(turn):
    """A run-level defect in a turn, or None. Never a case failure."""
    if not turn["content"].strip() and not turn["tool_calls"]:
        return "empty answer (finish_reason=%r)" % turn.get("finish_reason")
    text = turn["content"]
    if len(text) >= _DEGENERATE_MIN_CHARS:
        shingles = [text[i : i + _SHINGLE] for i in range(0, len(text) - _SHINGLE, 20)]
        diversity = len(set(shingles)) / float(len(shingles) or 1)
        if diversity < _DEGENERATE_DIVERSITY:
            return "degenerate output: shingle diversity %.2f" % diversity
    return None


# --- the kinds -----------------------------------------------------------------


def check_skill_choice(spec, trace, ctx):
    """Lane A: the answer names exactly the expected skill (or ``none``)."""
    text = _last(trace)["content"]
    found = sorted(set(match.lower() for match in _CHOICE_RE.findall(text.lower())))
    expected = spec["expect"]
    if found == [expected]:
        return result(True, "chose %s" % expected)
    if not found:
        return result(False, "expected %s; the answer named no skill: %r"
                      % (expected, text.strip()[:120]))
    return result(False, "expected %s; the answer named %s"
                  % (expected, ", ".join(found)))


def check_tool_call(spec, trace, ctx):
    """A tool call matching ``tool``/``args_re`` — the first one, or any."""
    calls = _last(trace)["tool_calls"] if spec.get("turn") == "last" else _all_calls(trace)
    if not calls:
        return result(False, "expected a %s call matching %r; the model made no "
                      "tool call" % (spec.get("tool", "tool"), spec.get("args_re")))
    if spec.get("which", "first") == "first":
        first = calls[0]
        if _matches(first, spec):
            return result(True, "first call %s" % render_call(first))
        return result(False, "expected the first call to be %s matching %r; it "
                      "was %s" % (spec.get("tool", "any tool"), spec.get("args_re"),
                                  render_call(first)))
    for call in calls:
        if _matches(call, spec):
            return result(True, "called %s" % render_call(call))
    return result(False, "expected a %s call matching %r; saw %s"
                  % (spec.get("tool", "tool"), spec.get("args_re"),
                     "; ".join(render_call(c) for c in calls)))


def check_no_tool_call(spec, trace, ctx):
    """No call matches ``tool``/``args_re``; with neither, no call at all."""
    offending = [call for call in _all_calls(trace) if _matches(call, spec)]
    if not offending:
        return result(True, "no matching tool call")
    what = "a tool call" if not (spec.get("tool") or spec.get("args_re")) else (
        "a %s call matching %r" % (spec.get("tool", "tool"), spec.get("args_re")))
    return result(False, "expected no %s; saw %s"
                  % (what, "; ".join(render_call(c) for c in offending)))


def check_text_re(spec, trace, ctx):
    text = _last(trace)["content"]
    if re.search(spec["re"], text):
        return result(True, "text matches %r" % spec["re"])
    return result(False, "expected the reply to match %r; it reads: %r"
                  % (spec["re"], text.strip()[:200]))


def check_not_text_re(spec, trace, ctx):
    text = _last(trace)["content"]
    match = re.search(spec["re"], text)
    if not match:
        return result(True, "text does not match %r" % spec["re"])
    return result(False, "the reply must not match %r; it contains %r"
                  % (spec["re"], match.group(0)))


def check_not_prescribed(spec, trace, ctx):
    """The command in ``re`` is never run and never told to the user to run.

    Mentioning it in a warning is fine: a match whose line carries a negation
    before it ("never run `git commit`") is a mention, not a prescription.
    """
    pattern = re.compile(spec["re"])
    for call in _all_calls(trace):
        if pattern.search(call_text(call)):
            return result(False, "the model ran %s, which it must not"
                          % render_call(call))
    for turn in trace.get("turns") or []:
        for line in turn["content"].splitlines():
            for match in pattern.finditer(line):
                if not _NEGATION_RE.search(line[: match.start()]):
                    return result(False, "the reply prescribes %r: %r"
                                  % (match.group(0), line.strip()[:200]))
    return result(True, "never prescribed %r" % spec["re"])


JUDGE_INSTRUCTIONS = """You grade one response from an AI agent that is following a
documentation-tooling skill. Judge ONLY the criterion below, strictly and literally.
Do not reward effort, tone or helpfulness outside it.

CRITERION:
{rubric}

THE AGENT'S RESPONSE (text, then any tool calls it made):
<<<
{response}
>>>

Respond with ONLY a JSON object:
{{"reason": "<2-4 sentences citing specifics>", "pass": <true|false>, "score": <1-5>}}"""


def render_turns(trace):
    parts = []
    for turn in trace.get("turns") or []:
        if turn["content"].strip():
            parts.append(turn["content"].strip())
        for call in turn["tool_calls"]:
            parts.append("[TOOL CALL] %s" % render_call(call))
    return "\n\n".join(parts) or "(empty)"


def parse_verdict(text):
    """The judge's JSON object, even when wrapped in prose or a fence."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise GradeError("judge returned no JSON object: %r" % text[:200])
    try:
        verdict = json.loads(text[start : end + 1])
    except ValueError as exc:
        raise GradeError("judge returned malformed JSON: %s" % exc)
    if not isinstance(verdict.get("pass"), bool):
        raise GradeError("judge verdict has no boolean 'pass': %r" % verdict)
    score = verdict.get("score")
    if not isinstance(score, (int, float)) or not 1 <= score <= 5:
        raise GradeError("judge verdict has no 1-5 'score': %r" % verdict)
    return verdict


def check_judge(spec, trace, ctx):
    judge = ctx.get("judge")
    if judge is None:
        raise GradeError("a judge assertion needs a judge; none is configured")
    provider, judge_spec = judge
    prompt = JUDGE_INSTRUCTIONS.format(
        rubric=spec["rubric"].strip(), response=render_turns(trace)
    )
    try:
        turn = provider.complete(
            judge_spec, [{"role": "user", "content": prompt}], scope="judge"
        )
    except ProviderError as exc:
        raise GradeError("judge API error: %s" % exc)
    verdict = parse_verdict(turn["content"])
    ctx.setdefault("judge_cost", 0.0)
    ctx["judge_cost"] += turn["usage"]["cost"]
    return result(verdict["pass"], "judge: %s" % verdict.get("reason", ""),
                  score=verdict["score"] / 5.0)


KINDS = {
    "skill_choice": check_skill_choice,
    "tool_call": check_tool_call,
    "no_tool_call": check_no_tool_call,
    "text_re": check_text_re,
    "not_text_re": check_not_text_re,
    "not_prescribed": check_not_prescribed,
    "judge": check_judge,
}


def validate_assertion(spec):
    """Raise ``ValueError`` for a spec no kind can evaluate (a case-file bug)."""
    kind = spec.get("kind")
    if kind not in KINDS:
        raise ValueError("unknown assertion kind %r" % kind)
    required = {
        "skill_choice": ("expect",),
        "text_re": ("re",),
        "not_text_re": ("re",),
        "not_prescribed": ("re",),
        "judge": ("rubric",),
    }.get(kind, ())
    for field in required:
        if field not in spec:
            raise ValueError("%s assertion is missing %r" % (kind, field))
    if kind == "skill_choice" and spec["expect"] not in SKILL_NAMES + ("none",):
        raise ValueError("skill_choice expects an unknown skill %r" % spec["expect"])
    for field in ("args_re", "re"):
        if field in spec:
            re.compile(spec[field])


def grade(assertions, trace, ctx=None):
    """Every assertion over one trace. ``GradeError`` propagates as an error."""
    ctx = {} if ctx is None else ctx
    results = []
    for spec in assertions:
        outcome = KINDS[spec["kind"]](spec, trace, ctx)
        outcome["kind"] = spec["kind"]
        results.append(outcome)
    passed = all(item["pass"] for item in results)
    score = sum(item["score"] for item in results) / float(len(results) or 1)
    feedback = "; ".join(item["feedback"] for item in results if not item["pass"])
    return {"passed": passed, "score": score, "results": results, "feedback": feedback}
