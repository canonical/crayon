"""Assertions over what a model did, each answering ``{pass, score, feedback}``.

Dev-time evaluation material. A case is a list of assertion specs; every spec
names its ``kind`` and the kind's own fields. A case passes only when every
assertion passes. ``feedback`` is always a sentence a reader — or a later text
optimiser — can act on: it names what was expected and what was seen, never
just "failed".

Deterministic kinds come first and carry most of the weight. ``judge`` is for
the judgement calls that resist a regex (routing voice, one question per turn)
and goes through a pinned model, never whichever one happens to be configured.

Grading reads a *trace*: ``{"turns": [normalised assistant turns]}``, plus, for
an episode, ``decisive`` — the action that ended it (``agent.run_episode``).
Only live turns are in ``turns``; a replayed history is never graded. The text
kinds read everything the model *said*: every live turn's content and every
question it put to the author through ``AskUserQuestion``.
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


#: A leading change into the directory the command already runs in (the
#: sandbox's working directory as the model sees it, ``agent.WORKDIR``). It
#: changes nothing, so a pattern anchored at the command's start ignores it.
_CD_WORKDIR_RE = re.compile(r"^\s*cd\s+(/srv/toyq|\.)/?\s*(&&|;)\s*")


def _typed(call):
    """A shell command as typed, else the arguments as JSON."""
    try:
        arguments = json.loads(call.get("arguments") or "{}")
    except ValueError:
        return call.get("arguments") or ""
    if isinstance(arguments, dict) and isinstance(arguments.get("command"), str):
        return arguments["command"]
    return json.dumps(arguments, sort_keys=True)


def call_text(call):
    """The text an ``args_re`` matches: :func:`_typed`, less a no-op ``cd``."""
    return _CD_WORKDIR_RE.sub("", _typed(call), count=1)


def render_call(call):
    return "%s(%s)" % (call.get("name"), _typed(call))


def _last(trace):
    turns = trace.get("turns") or []
    if not turns:
        raise GradeError("the trace holds no assistant turn to grade")
    return turns[-1]


def _all_calls(trace):
    return [call for turn in trace.get("turns") or [] for call in turn["tool_calls"]]


def _args(call):
    try:
        parsed = json.loads(call.get("arguments") or "{}")
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _said(trace):
    """Every live turn's text, then the text of every question asked."""
    if not trace.get("turns"):
        raise GradeError("the trace holds no assistant turn to grade")
    parts = [turn["content"] for turn in trace["turns"] if turn["content"]]
    for call in _all_calls(trace):
        if call.get("name") == "AskUserQuestion":
            for question in _args(call).get("questions") or []:
                if not isinstance(question, dict):
                    continue
                parts.append(str(question.get("question", "")))
                for option in question.get("options") or []:
                    if isinstance(option, dict):
                        parts.append("%s %s" % (option.get("label", ""),
                                                option.get("description", "")))
    return "\n".join(parts)


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
    """A tool call matching ``tool``/``args_re`` — the first one, or any.

    With ``tool`` named, "first" means the first call OF THAT TOOL: a model may
    read a reference file before its first command without failing a check on
    that command.
    """
    calls = _all_calls(trace)
    if spec.get("tool"):
        calls = [call for call in calls if call.get("name") == spec["tool"]]
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
    """No call matches ``tool``/``args_re``; with neither, no call at all.

    A call the episode carried out as looking (``served_ids``) is skipped: it
    was read-only by construction, so ``dogen signoff --help`` is not a signoff.
    """
    served = set(trace.get("served_ids") or ())
    offending = [call for call in _all_calls(trace)
                 if call.get("id") not in served and _matches(call, spec)]
    if not offending:
        return result(True, "no matching tool call")
    what = "a tool call" if not (spec.get("tool") or spec.get("args_re")) else (
        "a %s call matching %r" % (spec.get("tool", "tool"), spec.get("args_re")))
    return result(False, "expected no %s; saw %s"
                  % (what, "; ".join(render_call(c) for c in offending)))


def check_text_re(spec, trace, ctx):
    text = _said(trace)
    if re.search(spec["re"], text):
        return result(True, "text matches %r" % spec["re"])
    return result(False, "expected the reply to match %r; it reads: %r"
                  % (spec["re"], text.strip()[:200]))


def check_not_text_re(spec, trace, ctx):
    text = _said(trace)
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


def _decisive(trace):
    decisive = trace.get("decisive")
    if decisive is None:
        raise GradeError("this assertion needs an episode trace with a decisive action")
    return decisive


def describe_decisive(decisive):
    if decisive["type"] == "call":
        return render_call(decisive["call"])
    if decisive["type"] == "text":
        return "a reply with no tool call"
    return "nothing: the turn cap was reached while the model was still looking"


def check_decisive(spec, trace, ctx):
    """What ended the episode: a matching call, or (``type: text``) a reply."""
    decisive = _decisive(trace)
    if spec.get("type") == "text":
        if decisive["type"] == "text":
            return result(True, "ended on a reply with no tool call")
        return result(False, "expected the model to stop and reply; it ended on %s"
                      % describe_decisive(decisive))
    if decisive["type"] == "call" and _matches(decisive["call"], spec):
        return result(True, "acted with %s" % render_call(decisive["call"]))
    return result(False, "expected the action to be %s matching %r; it was %s"
                  % (spec.get("tool", "a call"), spec.get("args_re"),
                     describe_decisive(decisive)))


def check_asks_user(spec, trace, ctx):
    """The episode ended by putting a question to the author.

    Either through ``AskUserQuestion`` or as a plain reply that asks (contains a
    question mark). Acting — any other consequential call — fails.
    """
    decisive = _decisive(trace)
    if decisive["type"] == "call" and decisive["call"].get("name") == "AskUserQuestion":
        return result(True, "asked the author through AskUserQuestion")
    if decisive["type"] == "text" and "?" in (trace["turns"][-1]["content"] or ""):
        return result(True, "asked the author in its reply")
    return result(False, "expected the model to ask the author before acting; it "
                  "ended on %s" % describe_decisive(decisive))


def check_bash_sequence(spec, trace, ctx):
    """The first shell commands, in order, match ``prefix``."""
    commands = [call_text(call) for call in _all_calls(trace) if call.get("name") == "Bash"]
    for index, pattern in enumerate(spec["prefix"]):
        if index >= len(commands):
            return result(False, "expected shell command %d to match %r; only %d "
                          "command(s) ran: %s" % (index + 1, pattern, len(commands),
                                                  "; ".join(commands) or "none"))
        if not re.search(pattern, commands[index]):
            return result(False, "expected shell command %d to match %r; it was %r"
                          % (index + 1, pattern, commands[index]))
    return result(True, "opened with %s" % "; ".join(commands[: len(spec["prefix"])]))


def check_before(spec, trace, ctx):
    """A call matching ``first`` happens, and none matching ``then`` precedes it."""
    texts = [call_text(call) for call in _all_calls(trace)]
    firsts = [i for i, text in enumerate(texts) if re.search(spec["first"], text)]
    if not firsts:
        return result(False, "expected a call matching %r; saw %s"
                      % (spec["first"], "; ".join(texts) or "no calls"))
    early = [text for text in texts[: firsts[0]] if re.search(spec["then"], text)]
    if early:
        return result(False, "%r ran before %r" % (early[0], spec["first"]))
    return result(True, "%r came first" % texts[firsts[0]])


def check_any_of(spec, trace, ctx):
    """At least one of the nested assertions passes (the right action can differ)."""
    outcomes = [KINDS[inner["kind"]](inner, trace, ctx) for inner in spec["of"]]
    for outcome in outcomes:
        if outcome["pass"]:
            return result(True, outcome["feedback"])
    return result(False, "none of the acceptable actions happened: %s"
                  % " | ".join(outcome["feedback"] for outcome in outcomes))


JUDGE_INSTRUCTIONS = """You grade one response from an AI agent that is following a
documentation-tooling skill. Judge ONLY the criterion below, strictly and literally.
Do not reward effort, tone or helpfulness outside it.

CRITERION:
{rubric}
{context}
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
    context = ""
    if spec.get("context"):
        context = ("\nCONTEXT (what the agent saw earlier in the session; not part of its "
                   "response):\n<<<\n%s\n>>>\n" % spec["context"].strip())
    prompt = JUDGE_INSTRUCTIONS.format(
        rubric=spec["rubric"].strip(), context=context, response=render_turns(trace)
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
    "decisive": check_decisive,
    "asks_user": check_asks_user,
    "bash_sequence": check_bash_sequence,
    "before": check_before,
    "any_of": check_any_of,
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
        "bash_sequence": ("prefix",),
        "before": ("first", "then"),
        "any_of": ("of",),
    }.get(kind, ())
    for field in required:
        if field not in spec:
            raise ValueError("%s assertion is missing %r" % (kind, field))
    if kind == "skill_choice" and spec["expect"] not in SKILL_NAMES + ("none",):
        raise ValueError("skill_choice expects an unknown skill %r" % spec["expect"])
    for field in ("args_re", "re", "first", "then"):
        if field in spec:
            re.compile(spec[field])
    for pattern in spec.get("prefix", []):
        re.compile(pattern)
    for inner in spec.get("of", []):
        if inner.get("kind") in ("any_of", "judge"):
            raise ValueError("any_of may not nest %r" % inner.get("kind"))
        validate_assertion(inner)


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
