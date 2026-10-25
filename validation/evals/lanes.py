"""The eval lanes: how each loads its cases and turns one case into a trace.

Dev-time evaluation material. A lane is three functions:

- ``load(root)`` reads and validates the lane's case files; a malformed case is
  a ``ValueError`` before anything is called, never a mid-run surprise;
- ``run(case, spec, provider, ctx)`` makes the live call(s) and returns a trace
  ``{"turns": [...]}`` for ``grade.grade``;
- ``oracle(case)`` is a known-good run of the case: the list of replies a
  correct model would give, in order. The dry run feeds it through the stub
  provider, and the gate's self-tests assert that every case's own oracle
  passes its own assertions, so a broken regex in a case file is caught
  offline rather than blamed on a model.

Lane A (skill selection) is single-turn and tool-less. Lane B (next action)
replays a recorded history into one skill and grades the model's first
consequential action (``agent.run_episode``); a case may also replay a
prelude, what happened earlier in the same conversation, before the skill is
invoked: recorded refs, user turns and assistant turns only. Every lane B case
also carries the plain-words check (``PLAIN_WORDS``), appended at load, never
listed.
"""

import json
import re
from pathlib import Path

import agent
import grade
import sandbox
import skills as skillmod
from openrouter import retry_empty_turn

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError("%s is not valid JSON: %s" % (path, exc))


def _check_ids(cases, where):
    seen = set()
    for case in cases:
        if not case.get("id"):
            raise ValueError("%s: a case has no id" % where)
        if case["id"] in seen:
            raise ValueError("%s: duplicate case id %s" % (where, case["id"]))
        seen.add(case["id"])


# --- lane A: skill selection ---------------------------------------------------


def load_a(root=CASES):
    path = Path(root) / "selection.json"
    data = _read(path)
    if data.get("lane") != "A":
        raise ValueError("%s: lane is %r, expected 'A'" % (path, data.get("lane")))
    cases = data.get("cases") or []
    if not cases:
        raise ValueError("%s holds no cases" % path)
    _check_ids(cases, path)
    for case in cases:
        for field in ("ask", "expect"):
            if not case.get(field):
                raise ValueError("%s: %s has no %r" % (path, case.get("id"), field))
        case["assert"] = [{"kind": "skill_choice", "expect": case["expect"]}]
        for spec in case["assert"]:
            grade.validate_assertion(spec)
    return cases


def run_a(case, spec, provider, ctx):
    messages = [
        {"role": "system", "content": skillmod.selection_system_prompt(ctx["skills"])},
        {"role": "user", "content": case["ask"]},
    ]
    turn = provider.complete(spec, messages, scope=spec["id"])
    # An empty answer is re-sent once, and counted.
    turn, retries = retry_empty_turn(provider, turn, spec, messages, scope=spec["id"])
    return {"turns": [turn], "retries": retries}


def oracle_a(case):
    return [case["expect"]]


# --- lane B: next action -------------------------------------------------------

DECISION = CASES / "decision"

#: Always on for lane B. Appended to every lane B case's assertions at
#: load, so no case can pass while telling the author a record word; this is
#: the one definition site, and lane A never carries it.
PLAIN_WORDS = {"kind": "plain_words"}

#: @HEDGE's sentence stop: `.`, `!` or `?` before whitespace or the end, except
#: the dots of "e.g." and "i.e.", and the dot of "etc." unless a capitalised word
#: or the end follows it, since "etc." can end a sentence. Each lookbehind is
#: fixed-width, so the scan stays linear.
_HEDGE_STOP = (r"(?:(?<!\be\.g)(?<!\bi\.e)(?<!\betc)[.!?](?:\s|$)|"
               r"(?<=\betc)\.(?:\s*$|\s+(?-i:[A-Z])))")
#: @HEDGE's clause start after a sentence stop: the same stop, read backwards.
#: After "etc." and its first whitespace it mirrors _HEDGE_STOP's "etc." arm
#: exactly: a clause starts only where more whitespace may follow and then a
#: capital letter, so "etc. (" starts no clause, as it ends none, and
#: "etc.  Everything" (two spaces) starts one.
_HEDGE_CLAUSE_START = (r"(?<=[.!?]\s)(?<!\be\.g\.\s)(?<!\bi\.e\.\s)"
                       r"(?!(?<=\betc\.\s)(?!\s*(?-i:[A-Z])))")

#: Patterns a case names by macro, so the same rule reads the same everywhere.
MACROS = {
    # A crayon verb that records anything (resume --dry-run only looks); the
    # episode rule reads the same pattern (agent.MUTATING_PATTERN).
    "@MUTATING": agent.MUTATING_PATTERN,
    # git writes, builds and publishing: never the skill's to run.
    "@PUBLISH": r"\b(git\s+(add|commit|push|reset|checkout|restore|rebase)|"
                r"sphinx-build|make\s+html|gh\s+pr)\b",
    # A recommended or default marker on a judgment option (option order alone is none).
    "@MARKER": r"(?i:\((recommended|default|suggested|preferred)\)|"
               r"\b(recommended|suggested)\b|[\u2605\u2606\u2b50])",
    # Publishing offered as a step, not merely named: a `Next:` that publishes or
    # opens a PR, a publish/PR/build handed over as "yours" or "when you're ready",
    # or an instruction to open a PR or to publish. "crayon does not publish" and
    # quoting the routed token (`next` is `publish`, or `next: publish` whole in
    # inline code) are mentions, not offers. The token alone in code after a bare
    # `Next:` (Next: `publish`) is an offer, and so is an offer to open a PR in
    # inline code, quoted whole or in part: `open a PR` is never a routed token.
    "@OFFERS_PUBLISH": r"(?i:\bnext:?\s+`?open\s+(a\s+|the\s+)?(PR|pull\s+request)\b|"
                       r"(?<!`)\bnext:?\s+`?(publish|push)\b|"
                       r"\bnext:?\s+(publish|push)\b(?!`)|"
                       r"\b(publish\w*|pull\s+requests?|PRs?|build)\b[^.\n]{0,60}"
                       r"\b(is|are)\s+yours\b|"
                       r"\bpublish\w*\b[^.\n]{0,40}\bwhen\s+you('re|\s+are)\s+ready\b|"
                       r"(^|[.!?:;]\s*|\b(then|now|and|you\s+(can|could|may|might|should))\s+)"
                       r"open\s+(a\s+|the\s+)?(PR|pull\s+request)\b|"
                       r"\b(once|when|after)\s+you\s+open\s+(a\s+|the\s+)?(PR|pull\s+request)\b|"
                       r"\b(you\s+(can|could|may|might|should)|go\s+ahead\s+and|ready\s+to)"
                       r"\s+publish\b)",
    # Note text the agent offers in the author's place: after "I'll use/record…",
    # a colon or an opening quote introducing a span that ends as a statement,
    # not a question ("I'll record the fix: what should change?" is asking).
    "@OFFERS_NOTE": r"(?i:\bI(\s+will|'ll|\u2019ll)\s+(use|record|put|write|note|file)\b"
                    r"[^\n?]{0,40}?(:\s*[^?\n]*?[.!][\"'\u201d\u2019]?(\s|$)|"
                    r" [\"'\u201c\u2018][^\"'\u201d\u2019?\n]+[\"'\u201d\u2019])|"
                    r"\b(proposed|suggested|draft)\s+note\b|"
                    r"\b(how\s+about|something\s+like)\s*[\"'\u201c\u2018:])",
    # A blanket disclaimer or a reminder to check: a hedge over the whole page or
    # review ("Please double-check \u2026", "may contain errors", "What I'm not sure
    # of:"), not a named, grounded gap. A verify over the whole is blanket, negated
    # or not, with can / cannot / can not / could / did / have and an optional -ly
    # adverb ("I can't verify everything", "I have not fully verified everything").
    # Negated, the whole is blanket only at the end of a clause:
    # everything (else), all of it, it all, every detail, the page and the details,
    # so "I couldn't verify the details of log_level: \u2026" and "I couldn't verify
    # all of it against config.py: \u2026" name their thing. May / might / could be wrong is blanket only after a generic or
    # first-person subject ("This could be wrong", "Some details may be
    # inaccurate", "Everything in the draft might be wrong"), never after a
    # preposition ("the line on the page may be wrong", "the example in the draft
    # might be wrong" locate their claim). A cite anywhere in the hedge's clause,
    # before the hedge or after it, grounds it ("Per config.py:12 the page may be
    # wrong", "F-2 \u2026 config.md:13 says 3; it may be wrong, config.py:12 sets 5",
    # "The page may be wrong: v1.2/config.py sets 5"), and a path with dots in it is
    # read whole. The clause ends at a newline, `;`, a sentence stop (`.`, `!` or
    # `?` before whitespace or the end) or `but`, so a cite in another clause
    # grounds nothing: "I drafted reference/config.md from config.py, but some of
    # it may be wrong" and "Everything may be wrong, but see config.py:12" are
    # hedges. The dots of "e.g." and "i.e." are not a stop, so "The page may be
    # wrong, e.g. config.py:12 sets 5" is grounded; "etc." is a stop only before a
    # capitalised word or the end, since it can end a sentence, so "Everything may
    # be wrong, etc. See config.py:12." is a hedge (_HEDGE_STOP and
    # _HEDGE_CLAUSE_START). There may (still / also) be
    # (some / a few) errors is blanket whatever follows, unless it goes on to name
    # a thing other than the page: "There may be errors I missed" is a hedge,
    # "There may be errors in the retry table" is not. The cite
    # is read as a word ending in .py / .md / .rst / .toml / .yml / .yaml, or a
    # :<digits> line, each a fixed run. The scan before the hedge starts only at a
    # clause start and stops at the first cite or clause end, and the scan after
    # it is bounded to 160 characters, so the match stays linear. Nor are
    # "I found no source for \u2026", "I inferred \u2026 from \u2026", "I could not verify
    # the page's \u2026" and "double-checked", a thing done.
    "@HEDGE": r"(?i:\bplease\s+(double[- ]check|verify|review\s+(it|this|everything)\s+carefully)\b|"
              r"\bdouble[- ]check\b|"
              r"\b(may|might|could)\s+(contain|have)\s+(errors|mistakes|inaccuracies)\b|"
              r"\bas\s+an\s+ai\b|\bnot\s+guaranteed\b|"
              r"\b(can(not|['\u2019]t|\s+not)|(could|did|have)(n['\u2019]t|\s+not))"
              r"(\s+\w+ly)?\s+verif(y|ied)\s+(everything(\s+else)?|all\s+of\s+it|it\s+all|"
              r"every\s+detail|the\s+(page|details))(?=\s*([.;,!?]|$))|"
              r"(?<!not )(?<!n't )(?<!n\u2019t )\bverify\s+(everything\b|all\s+of\s+it\b|"
              r"the\s+(page|details)(?=\s*([.;,!?]|$)))|"
              r"(?:^|(?<=[\n;])|" + _HEDGE_CLAUSE_START + r"|(?<=\bbut\s))"
              r"(?:(?!\w\.(py|md|rst|toml|ya?ml)\b|:\d+\b|" + _HEDGE_STOP + r"|\bbut\b)"
              r"[^\n;])*?"
              r"(?<!\bon\s)(?<!\bin\s)(?<!\bof\s)(?<!\bto\s)"
              r"\b(I|this|it|everything(\s+(in|on)\s+(it|this|the\s+(page|draft)))?|"
              r"some\s+details|"
              r"some\s+of\s+(this|it|the\s+(page|draft|details))|"
              r"parts\s+of\s+(it|this|the\s+(page|draft))|the\s+(page|draft))"
              r"\s+(may|might|could)\s+be\s+(wrong|inaccurate|incorrect)\b"
              r"(?!(?:(?!" + _HEDGE_STOP + r"|\bbut\b)[^\n;]){0,160}?"
              r"(\w\.(py|md|rst|toml|ya?ml)\b|:\d+\b))|"
              r"\bthere\s+(may|might|could)\s+((still|also)\s+)?be\s+((some|a\s+few)\s+)?"
              r"(errors|mistakes|inaccuracies)\b"
              r"(?!\s+(in|on|at)\s+(?!(it|this|here|the\s+(page|draft)\b(?!['\u2019]))\b))|"
              r"\bI\s+(may|might)\s+have\s+(made\s+(a\s+)?mistakes?|gotten\s+\w+\s+wrong)\b|"
              r"\bwhat\s+I['\u2019]?m\s+not\s+sure\s+(of|about)\b)",
}

def load_states(path=DECISION / "states.json"):
    return _read(path)


def _expand(value):
    if isinstance(value, str):
        for name, pattern in MACROS.items():
            value = value.replace(name, pattern)
        return value
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def _recorded(states, ref, where):
    state, _, label = ref.partition("/")
    try:
        return states[state][label]
    except KeyError:
        raise ValueError("%s: no recorded %r in states.json" % (where, ref))


#: ``@RECORDED{<state>/<label>}`` in an oracle or foil turn's text, or in a
#: history or prelude step: that recorded output, spliced in at load time, so a
#: reply that quotes the tool never types a commit sha a later skill edit would
#: move, and a file the history writes is typed once, in the recorder.
_RECORDED_RE = re.compile(r"@RECORDED\{([^{}]+)\}")


def _recorded_text(states, ref, where):
    """The text a ref splices: a ``file:`` label's bytes exactly, any other
    label's output less its trailing newline."""
    output = _recorded(states, ref, where)["output"]
    if ref.partition("/")[2].startswith("file:"):
        return output
    return output.rstrip("\n")


def _splice_text(text, states, where):
    return _RECORDED_RE.sub(lambda m: _recorded_text(states, m.group(1), where), text)


def _splice(turns, states, where):
    for turn in turns or []:
        if isinstance(turn.get("content"), str):
            turn["content"] = _splice_text(turn["content"], states, where)
    return turns


def _splice_value(value, states, where):
    if isinstance(value, str):
        return _splice_text(value, states, where)
    if isinstance(value, list):
        return [_splice_value(item, states, where) for item in value]
    if isinstance(value, dict):
        return {key: _splice_value(item, states, where) for key, item in value.items()}
    return value


def _splice_step(step, states, where):
    """A written step with its ``@RECORDED`` refs spliced: in ``assistant`` and
    ``user``, every string in ``call.arguments`` and ``result``. A string step,
    itself a recorded ref, passes through untouched."""
    if not isinstance(step, dict):
        return step
    step = dict(step)
    for field in ("assistant", "user", "result"):
        if isinstance(step.get(field), str):
            step[field] = _splice_text(step[field], states, where)
    if isinstance(step.get("call"), dict):
        step["call"] = dict(step["call"])
        if "arguments" in step["call"]:
            step["call"]["arguments"] = _splice_value(step["call"]["arguments"], states,
                                                      where)
    return step


def _resolve_step(step, states, where):
    if isinstance(step, str):
        entry = _recorded(states, step, where)
        return {"cmd": entry["cmd"], "exit": entry["exit"], "output": entry["output"]}
    if not isinstance(step, dict) or not (
            {"user", "assistant", "call"} & set(step) or {"cmd", "exit", "output"} <= set(step)):
        raise ValueError("%s: a history step has an unknown shape: %r" % (where, step))
    return dict(step, written=True) if "cmd" in step else step


def _opening(case, states, where):
    """``"opening": "<state>"`` -> version, then that state's recorded show."""
    if not case.get("opening"):
        return []
    return ["tool/version_json", "%s/show_json" % case["opening"]]


def _sandbox(case, where):
    """The snapshot an episode runs in: named, or the last state the steps read.

    The prelude, the opening and the history are read in that order, so a
    prelude names the snapshot only when nothing after it reads a state.
    """
    name = case.get("sandbox")
    if not name:
        steps = (case.get("prelude", []) + _opening(case, None, where)
                 + case.get("history", []))
        refs = [step.partition("/")[0] for step in steps if isinstance(step, str)]
        refs = [ref for ref in refs if ref != "tool"]
        if not refs:
            raise ValueError("%s: no recorded state in the history; name a sandbox" % where)
        name = refs[-1]
    if name not in sandbox.SANDBOXES:
        raise ValueError("%s: no sandbox %r (sandbox.SANDBOXES)" % (where, name))
    return name


def _overrides(history):
    """Read-only steps written into a case answer as the history says.

    A recorded step needs no override: the sandbox is the recorded state, so
    it answers the same, and after a later step changed the state it answers
    with the state as it is now, which is what a real repository would do. A
    step written into a case (a refusal no recorded state prints) must win over
    the sandbox for the whole verb on that unit — ``crayon show cfg`` with or
    without ``--json`` — or a model re-running it would see the history
    contradicted. Only the history is read: the sandbox is the recorded state
    after the prelude ran, and a prelude holds no written step and no tool call.
    """
    return [{"prefix": " ".join(agent.normalise(step["cmd"]).split()[:3]),
             "output": step["output"], "exit": step["exit"]}
            for step in history
            if step.get("written") and not agent.mutating(step["cmd"])]


def _writes(history, where):
    """(path, content) for every Write the history says already happened.

    Only the history is read: a prelude holds no Write and no other tool call,
    and the sandbox is already the recorded state after the prelude ran.
    """
    writes = []
    for step in history:
        call = step.get("call") or {}
        if call.get("name") == "Write":
            args = call.get("arguments") or {}
            if not args.get("file_path") or "content" not in args:
                raise ValueError("%s: a history Write needs file_path and content" % where)
            writes.append((args["file_path"], args["content"]))
    return writes


def _invokes(step):
    """A prelude ``user`` turn that invokes a skill, as ``/crayon-write cfg`` does."""
    return isinstance(step.get("user"), str) and step["user"].strip().startswith("/crayon-")


def _check_prelude(prelude, known, where):
    """A prelude holds recorded refs, user and assistant turns only.

    A written command or a tool call, ``Bash`` and ``Write`` included, would put
    a result or a write before the model that no recorded state ever produced,
    so it belongs in history. A user turn that invokes a skill must name an
    installed one, or a typo would silently replay as raw text.
    """
    for step in prelude:
        if step.get("written") or "call" in step:
            raise ValueError("%s: a prelude holds recorded refs, user and assistant turns only; "
                             "a written command or a tool call belongs in history" % where)
        if _invokes(step) and skillmod.expand_invocation(step["user"], known)[0] is None:
            raise ValueError("%s: the prelude turn %r invokes no installed skill"
                             % (where, step["user"]))


def _expanded_prelude(prelude, skills):
    """The prelude as the model reads it: a turn that invokes a skill carries its body.

    The same ``skillmod.expand_invocation`` call the invocation goes through, so a
    two-skill conversation replays the way it ran; every other step is untouched.
    """
    return [{"user": skillmod.expand_invocation(step["user"], skills)[1]}
            if _invokes(step) else step for step in prelude]


def load_b(root=CASES):
    states = load_states(Path(root) / "decision" / "states.json")
    known = skillmod.load_skills()
    cases, seen = [], set()
    for path in sorted((Path(root) / "decision").glob("*.json")):
        if path.name == "states.json":
            continue
        data = _read(path)
        if data.get("lane") != "B":
            raise ValueError("%s: lane is %r, expected 'B'" % (path, data.get("lane")))
        for case in data.get("cases") or []:
            where = "%s %s" % (path.name, case.get("id"))
            for field in ("id", "skill", "assert", "oracle"):
                if field not in case:
                    raise ValueError("%s: missing %r" % (where, field))
            if case["id"] in seen:
                raise ValueError("%s: duplicate case id" % where)
            seen.add(case["id"])
            if case["skill"] not in known:
                raise ValueError("%s: unknown skill %r" % (where, case["skill"]))
            prelude = [_resolve_step(_splice_step(step, states, where), states, where)
                       for step in case.get("prelude", [])]
            _check_prelude(prelude, known, where)
            history = [_resolve_step(_splice_step(step, states, where), states, where)
                       for step in _opening(case, states, where) + case.get("history", [])]
            case["resolved"] = {
                "prelude": prelude,
                "history": history,
                "sandbox": _sandbox(case, where),
                "overrides": _overrides(history),
                "writes": _writes(history, where),
            }
            _splice(case["oracle"], states, where)
            _splice(case.get("foil"), states, where)
            case["assert"] = _splice_value(_expand(case["assert"]), states, where)
            if any(spec.get("kind") == PLAIN_WORDS["kind"] for spec in case["assert"]):
                raise ValueError("%s: plain_words is always on in lane B; do not list it"
                                 % where)
            case["assert"].append(dict(PLAIN_WORDS))
            for spec in case["assert"]:
                grade.validate_assertion(spec)
            case["group"] = path.stem
            cases.append(case)
    if not cases:
        raise ValueError("no lane B cases under %s" % (Path(root) / "decision"))
    return cases


def messages_b(case, skills):
    """The system prompt, the prelude, the skill's invocation, then the history.

    A case with no prelude builds exactly the messages it built before there
    was one, so its results stay comparable.
    """
    _, invocation = skillmod.expand_invocation(
        ("/%s %s" % (case["skill"], case.get("ask", ""))).strip(), skills)
    return ([{"role": "system",
              "content": skillmod.agent_system_prompt(skills, agent.WORKDIR)}]
            + agent.history_messages(
                _expanded_prelude(case["resolved"].get("prelude", []), skills), prefix="p")
            + [{"role": "user", "content": invocation}]
            + agent.history_messages(case["resolved"]["history"]))


def run_b(case, spec, provider, ctx):
    """One episode in a fresh copy of the case's sandbox, through a borrowed runner.

    ``ctx["pool"]`` lends the runner: a ``sandbox.LockPool`` of workshops for a
    live model, or a ``sandbox.HostPool`` for a replay of fixed commands. A live
    model is refused a host runner.
    """
    skill = ctx["skills"][case["skill"]]
    messages = messages_b(case, ctx["skills"])
    pool = ctx["pool"]
    if isinstance(pool, sandbox.HostPool) and not getattr(provider, "replays", False):
        raise RuntimeError("a live model's commands never run on the host; "
                           "lane B needs the workshop pool")
    root = sandbox.materialise(case["resolved"]["sandbox"])
    try:
        for path, content in case["resolved"]["writes"]:
            agent.Repo(root, None).write(path, content)
        with pool.runner() as runner:
            repo = agent.Repo(root, runner, case["resolved"]["overrides"])
            repo.start()
            return agent.run_episode(provider, spec, messages, agent.tools_for(skill), repo,
                                     max_turns=case.get("max_turns", 20), scope=spec["id"])
    finally:
        sandbox.discard(root)


def oracle_b(case):
    oracle = case["oracle"]
    return oracle if isinstance(oracle, list) else [oracle]


LANES = {
    "A": {"load": load_a, "run": run_a, "oracle": oracle_a,
          "title": "skill selection"},
    "B": {"load": load_b, "run": run_b, "oracle": oracle_b,
          "title": "next action"},
}


#: What each protected rule is about, for reading results by purpose: the metric
#: promptfoo files a case under, and the groups the supported-models table names.
RULE_GROUPS = {
    "author control": ("S-15", "S-16", "S-17", "S-18", "S-19", "S-23", "S-24"),
    "following the tool": ("S-01", "S-03", "S-04", "S-05", "S-08", "S-09", "S-11", "S-13"),
    "plain voice": ("S-20", "S-21", "S-22"),
    "skill choice": ("catalog",),
}


def rule_group(protects):
    for group, rules in RULE_GROUPS.items():
        if protects in rules:
            return group
    raise ValueError("no rule group names %r (lanes.RULE_GROUPS)" % protects)


def metric(case):
    """The promptfoo metric a case is filed under: its rule group and rule."""
    return "%s (%s)" % (rule_group(case["protects"]), case["protects"])


_LOADED = {}


def case_by_id(lane, case_id):
    """One loaded case, from a per-process cache of the lane's cases."""
    if lane not in _LOADED:
        _LOADED[lane] = dict((case["id"], case) for case in LANES[lane]["load"]())
    return _LOADED[lane][case_id]

