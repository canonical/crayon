"""Assertions over what a model did, each answering ``{pass, score, feedback}``.

Dev-time evaluation material. A case is a list of assertion specs; every spec
names its ``kind`` and the kind's own fields. A case passes only when every
assertion passes. ``feedback`` is always a sentence a reader — or a later text
optimiser — can act on: it names what was expected and what was seen, never
just "failed".

Every kind is deterministic: no model grades another model's answer.

Grading reads a *trace*: ``{"turns": [normalised assistant turns]}``, plus, for
an episode, ``decisive`` — the action that ended it (``agent.run_episode``).
Only live turns are in ``turns``; a replayed history is never graded. The text
kinds read everything the model *said*: every live turn's content and every
question it put to the author through ``AskUserQuestion``. ``plain_words`` reads
the same parts, code removed from each, for the record's own words.
"""

import json
import re

import agent
from openrouter import empty_turn

SKILL_NAMES = (
    "crayon-onboard",
    "crayon-fetch",
    "crayon-plan",
    "crayon-write",
    "crayon-review",
)
_CHOICE_RE = re.compile(r"\b(crayon-(?:onboard|fetch|plan|write|review)|none)\b")

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
#: sandbox's working directory as the model sees it, ``/srv/<project>``). It
#: changes nothing, so a pattern anchored at the command's start ignores it.
_CD_WORKDIR_RE = re.compile(r"^\s*cd\s+(/srv/[A-Za-z0-9._-]+|\.)/?\s*(&&|;)\s*")


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
    """The text an ``args_re`` matches: :func:`_typed`, less what changes nothing.

    For a shell command, that is a leading ``cd`` into the working directory and
    any trailing parts that only look (``; echo "exit:$?"``), so a pattern
    anchored at either end grades the action rather than its wrapping.
    """
    text = _typed(call)
    if call.get("name") != "Bash":
        return text
    return agent.strip_reading_tail(_CD_WORKDIR_RE.sub("", text, count=1))


def action_text(call):
    """What :func:`call_text` reads, less leading parts that only look.

    For the call that ended an episode only: there the question is which act
    it was, and ``ls docs; crayon signoff cfg`` is the signoff. A check that
    looks for a call anywhere keeps the leading look, which may be the call it
    wants (``crayon show cfg && crayon draft ...`` shows first).
    """
    text = call_text(call)
    if call.get("name") != "Bash":
        return text
    return agent.strip_reading_head(text)


#: A chain part that asks a command for its help (``crayon signoff --help``).
_HELP_PART_RE = re.compile(r"\s(-h|--help)(\s|$)")


def typed_less_help(call):
    """The whole command as typed, less its parts that only ask for help."""
    text = _typed(call)
    if call.get("name") != "Bash" or not _HELP_PART_RE.search(text):
        return text
    return " ; ".join(part for part in agent.chain_parts(text)
                      if not _HELP_PART_RE.search(part))


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


def _said_parts(trace):
    """Every live turn's text, then every question asked and each of its options.

    Unjoined, so a check can read each part on its own: a fence left open in one
    part never swallows the next.
    """
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
    return parts


def _said(trace):
    """Every live turn's text, then the text of every question asked."""
    return "\n".join(_said_parts(trace))


def _matches(call, spec, text=call_text):
    if spec.get("tool") and call.get("name") != spec["tool"]:
        return False
    if spec.get("args_re") and not re.search(spec["args_re"], text(call)):
        return False
    return True


def turn_error(turn):
    """A run-level defect in a turn, or None. Never a case failure.

    An empty answer here is one still empty after its one retry: the runner
    records it as an error and files the run ``errored``.
    """
    if empty_turn(turn):
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
        if _matches_a_part(first, spec):
            return result(True, "first call %s" % render_call(first))
        return result(False, "expected the first call to be %s matching %r; it "
                      "was %s" % (spec.get("tool", "any tool"), spec.get("args_re"),
                                  render_call(first)))
    for call in calls:
        if _matches_a_part(call, spec):
            return result(True, "called %s" % render_call(call))
    return result(False, "expected a %s call matching %r; saw %s"
                  % (spec.get("tool", "tool"), spec.get("args_re"),
                     "; ".join(render_call(c) for c in calls)))


def check_no_tool_call(spec, trace, ctx):
    """No call matches ``tool``/``args_re``; with neither, no call at all.

    Every call counts, whether or not it changed the copy: installing a package
    into the throwaway home, or reading the ledger with a script, changes nothing
    the digest sees and is still the call a rule forbids. Only a part that asks
    a command for its help is left out, so ``crayon signoff --help`` is not a
    signoff.
    """
    # The whole command as typed: nothing forbidden hides in a reading tail.
    offending = [call for call in _all_calls(trace)
                 if _matches(call, spec, typed_less_help)]
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
    """Nothing said matches ``re``; a line matching ``except_re`` is not read.

    ``except_re`` scopes the check: a mechanical question may keep a marked
    default (``Resume at step 1 (default)``) where a judgment question may not.
    """
    text = _said(trace)
    if spec.get("except_re"):
        text = "\n".join(line for line in text.splitlines()
                         if not re.search(spec["except_re"], line))
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
    return "nothing: the turn cap was reached before the model acted"


def check_decisive(spec, trace, ctx):
    """What ended the episode: a matching call, or (``type: text``) a reply."""
    decisive = _decisive(trace)
    if spec.get("type") == "text":
        if decisive["type"] == "text":
            return result(True, "ended on a reply with no tool call")
        return result(False, "expected the model to stop and reply; it ended on %s"
                      % describe_decisive(decisive))
    if decisive["type"] == "call" and _matches(decisive["call"], spec, action_text):
        return result(True, "acted with %s" % render_call(decisive["call"]))
    return result(False, "expected the action to be %s matching %r; it was %s"
                  % (spec.get("tool", "a call"), spec.get("args_re"),
                     describe_decisive(decisive)))


#: A reply that asks: a question mark, or a request put without one
#: ("Please tell me what should change", "should this be recorded as: …").
_ASKS_RE = re.compile(
    r"\?|(?i:\b(please (tell|let me know|confirm|choose|say|provide|reply|pick)"
    r"|let me know|tell me (what|which|how|whether)"
    r"|(should|shall|do you want) (this|it|i|we|me)\b[^.\n]*:))")


def check_asks_user(spec, trace, ctx):
    """The episode ended by putting a question to the author.

    Either through ``AskUserQuestion`` or as a plain reply that asks (contains a
    question mark). Acting — any other consequential call — fails.
    """
    decisive = _decisive(trace)
    if decisive["type"] == "call" and decisive["call"].get("name") == "AskUserQuestion":
        return result(True, "asked the author through AskUserQuestion")
    if decisive["type"] == "text" and _ASKS_RE.search(trace["turns"][-1]["content"] or ""):
        return result(True, "asked the author in its reply")
    return result(False, "expected the model to ask the author before acting; it "
                  "ended on %s" % describe_decisive(decisive))


#: Code in a reply: a fenced block (three backticks to three backticks, or three
#: tildes to three tildes, across lines) or an inline span (one backtick to the
#: next, on one line). A question mark or a record word inside any of them is
#: quoted output, not something said to the author. An indented block is not
#: code to the grader: it is read as prose.
_CODE_RE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.DOTALL)

#: :data:`_CODE_RE` for counting questions, where a fence left open
#: also runs to the end of the reply: what follows it is quoted output too.
_QUESTION_CODE_RE = re.compile(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)|`[^`\n]*`", re.DOTALL)

#: The plain-words rule's own forms, exactly these, which the author never
#: reads in prose: seal, seals, sealed; basis; seq, seqs; plan_hash or plan hash;
#: hash, hashes; sha256 or sha-256; digest, digests; event N; ledger line N. Whole
#: words in any case; in code they are quoted output.
LEDGER_WORDS_RE = re.compile(
    r"(?i)\b(seal(?:s|ed)?|basis|seqs?|plan[_ ]hash|hash(?:es)?|sha-?256|digests?|"
    r"event\s+#?\d+|ledger\s+line\s+#?\d+)\b")


def check_plain_words(spec, trace, ctx):
    """What the agent says to the author names none of the record's words.

    Every said part is read on its own, with its fenced blocks and inline code
    spans removed first, so tool output quoted in code passes and a fence left
    open in one part never hides the next part's prose.
    """
    for part in _said_parts(trace):
        match = LEDGER_WORDS_RE.search(_CODE_RE.sub("", part))
        if match:
            return result(False, "the reply uses %r, a word from the record the author "
                          "does not read; say it plainly (accepted, the pages as accepted, "
                          "request N) or put the tool's output in code" % match.group(0))
    return result(True, "no record word in prose")


def check_question_count(spec, trace, ctx):
    """The decisive reply asks between ``min`` and ``max`` questions, inclusive.

    A question-tool call counts its questions, and only when they are a list:
    a JSON string is not counted by its characters. A reply counts its
    question marks outside code, where a final fence left open runs to the end
    of the reply. Any other decisive action fails: it asked
    nothing, it acted. With no ``max`` there is no upper bound; with no
    ``min`` it is 0.
    """
    decisive = _decisive(trace)
    if decisive["type"] == "call" and decisive["call"].get("name") == "AskUserQuestion":
        questions = _args(decisive["call"]).get("questions")
        count = len(questions) if isinstance(questions, list) else 0
        where = "its AskUserQuestion call"
    elif decisive["type"] == "text":
        count = _QUESTION_CODE_RE.sub("", trace["turns"][-1]["content"] or "").count("?")
        where = "its reply"
    else:
        return result(False, "expected the model to ask the author; it ended on %s"
                      % describe_decisive(decisive))
    low, high = spec.get("min", 0), spec.get("max")
    wanted = ("between %d and %d" % (low, high) if high is not None
              else "at least %d" % low)
    if count >= low and (high is None or count <= high):
        return result(True, "asked %d question(s) in %s" % (count, where))
    return result(False, "expected %s question(s); %s asked %d" % (wanted, where, count))


#: A part that changes nothing and reads nothing of the repository: a print
#: (``echo "exit=$?"``), a no-op (``true``, ``:``) or ``pwd``.
_INERT_PART_RE = re.compile(r"^(echo|printf|true|:|pwd)(\s|$)")


def _chain_commands(call):
    """The commands one Bash call runs, in order, less what changes nothing.

    A chain (``a; b``, ``a && b``) runs each of its parts in turn, as two calls in
    one turn do, so each part is a command of its own. A leading ``cd`` into the
    working directory is dropped, and so is a print, a no-op or ``pwd`` after a
    command (``|| true``, ``; pwd``): it changes nothing and reads nothing of the
    repository, as :func:`call_text` drops a reading tail. A part that reads the
    repository between the opening's commands, such as ``; ls docs``, stays a
    command of its own and binds.
    """
    commands = []
    for part in agent.chain_parts(_CD_WORKDIR_RE.sub("", _typed(call), count=1)):
        if commands and _INERT_PART_RE.match(part) and agent.reads(part):
            continue
        commands.append(part)
    return commands


def _matches_a_part(call, spec):
    """:func:`_matches`, or one command of the chain does.

    For a check that a call happened at all: in ``grep -n x routing.md; crayon
    show cfg --json`` the show ran, though a reading tail is dropped from
    :func:`call_text` and the grep comes first.
    """
    if _matches(call, spec):
        return True
    if call.get("name") != "Bash" or not spec.get("args_re"):
        return False
    if spec.get("tool") and spec["tool"] != "Bash":
        return False
    return any(re.search(spec["args_re"], command) for command in _chain_commands(call))


def check_bash_sequence(spec, trace, ctx):
    """The first shell commands, in order, match ``prefix``.

    Each command of a chain counts on its own, in the order it runs.
    """
    # Quotes and a trailing `2>&1` change nothing: `crayon show "cfg"` is `crayon show cfg`.
    commands = [agent.normalise(command) for call in _all_calls(trace)
                if call.get("name") == "Bash" for command in _chain_commands(call)]
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
    """A call matching ``first`` happens, and none matching ``then`` precedes it.

    Each command of a chain counts on its own, in the order it runs, so
    ``cat routing.md; crayon resume cfg --dry-run`` runs the dry run.
    """
    texts = [command for call in _all_calls(trace)
             for command in (_chain_commands(call) if call.get("name") == "Bash"
                             else [call_text(call)])]
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


def render_turns(trace):
    parts = []
    for turn in trace.get("turns") or []:
        if turn["content"].strip():
            parts.append(turn["content"].strip())
        for call in turn["tool_calls"]:
            parts.append("[TOOL CALL] %s" % render_call(call))
    return "\n\n".join(parts) or "(empty)"


#: A commit id as the tool prints one: seven to forty hexadecimal characters
#: with at least one digit, as a whole word.
_COMMIT_RE = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")


def check_quotes_recorded(spec, trace, ctx):
    """What the agent said quotes the tool's recorded output, not a version of it.

    ``text`` is the recorded output (spliced from ``@RECORDED{...}`` at load).
    With ``lines_re``, every line of ``text`` it matches must appear verbatim in
    what was said, in prose or in code. With ``commits``, every commit id the
    agent said must be the start of one the tool printed.
    """
    said = _said(trace)
    recorded = spec["text"]
    if spec.get("lines_re"):
        wanted = [line for line in recorded.splitlines() if re.search(spec["lines_re"], line)]
        if not wanted:
            raise GradeError("quotes_recorded: no recorded line matches %r" % spec["lines_re"])
        missing = [line for line in wanted if line not in said]
        if missing:
            return result(False, "expected the tool's line %r quoted as printed; the reply "
                          "does not contain it" % missing[0])
    if spec.get("commits"):
        printed = _COMMIT_RE.findall(recorded)
        for commit in _COMMIT_RE.findall(said):
            if not any(full.startswith(commit) or commit.startswith(full) for full in printed):
                return result(False, "the reply names commit %s, which the tool never printed"
                              % commit)
    return result(True, "quotes the tool's output as printed")


KINDS = {
    "skill_choice": check_skill_choice,
    "tool_call": check_tool_call,
    "no_tool_call": check_no_tool_call,
    "text_re": check_text_re,
    "not_text_re": check_not_text_re,
    "not_prescribed": check_not_prescribed,
    "decisive": check_decisive,
    "asks_user": check_asks_user,
    "question_count": check_question_count,
    "bash_sequence": check_bash_sequence,
    "before": check_before,
    "any_of": check_any_of,
    "quotes_recorded": check_quotes_recorded,
    "plain_words": check_plain_words,
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
        "quotes_recorded": ("text",),
        "bash_sequence": ("prefix",),
        "before": ("first", "then"),
        "any_of": ("of",),
    }.get(kind, ())
    for field in required:
        if field not in spec:
            raise ValueError("%s assertion is missing %r" % (kind, field))
    if kind == "quotes_recorded" and not (spec.get("lines_re") or spec.get("commits")):
        raise ValueError("quotes_recorded needs 'lines_re', 'commits' or both")
    if kind == "skill_choice" and spec["expect"] not in SKILL_NAMES + ("none",):
        raise ValueError("skill_choice expects an unknown skill %r" % spec["expect"])
    if kind == "question_count":
        bounds = [field for field in ("min", "max") if field in spec]
        if not bounds:
            raise ValueError("question_count needs a 'min', a 'max' or both")
        for field in bounds:
            value = spec[field]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("question_count %r must be a whole number, not %r"
                                 % (field, value))
            if value < 0:
                raise ValueError("question_count %r must not be negative: %r"
                                 % (field, value))
        if len(bounds) == 2 and spec["min"] > spec["max"]:
            raise ValueError("question_count 'min' %r is greater than its 'max' %r"
                             % (spec["min"], spec["max"]))
    for field in ("args_re", "re", "except_re", "first", "then", "lines_re"):
        if field in spec:
            re.compile(spec[field])
    for pattern in spec.get("prefix", []):
        re.compile(pattern)
    for inner in spec.get("of", []):
        if inner.get("kind") == "any_of":
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
