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
consequential action (``agent.run_episode``).
"""

import json
import re
from pathlib import Path

import agent
import grade
import sandbox
import skills as skillmod

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
    turn = provider.complete(spec, messages, cache=ctx.get("cache", True),
                             scope=spec["id"])
    return {"turns": [turn]}


def oracle_a(case):
    return [case["expect"]]


# --- lane B: next action -------------------------------------------------------

DECISION = CASES / "decision"

#: Patterns a case names by macro, so the same rule reads the same everywhere.
MACROS = {
    # A crayon verb that records anything (resume --dry-run only looks).
    "@MUTATING": r"\bcrayon\s+(unit\s+(new|edit|retire)|context\s+(stage|record)|"
                 r"signoff|steer|plan-steps|step|draft|edits|review|"
                 r"resume(?![^\n]*--dry-run))\b",
    # git writes, builds and publishing: never the skill's to run.
    "@PUBLISH": r"\b(git\s+(add|commit|push|reset|checkout|restore|rebase)|"
                r"sphinx-build|make\s+html|gh\s+pr)\b",
    # A recommended or default marker on a judgment option (option order alone is none).
    "@MARKER": r"(?i:\((recommended|default|suggested|preferred)\)|"
               r"\b(recommended|suggested)\b|[\u2605\u2606\u2b50])",
    # Publishing offered as a step, not merely named: a `Next:` that publishes or
    # opens a PR, a publish/PR/build handed over as "yours" or "when you're ready",
    # or an instruction to open a PR or to publish. "crayon does not publish" and
    # quoting the routed token (`next` is `publish`) are mentions, not offers.
    "@OFFERS_PUBLISH": r"(?i:\bnext:?\s+(publish|push|open\s+(a\s+|the\s+)?(PR|pull\s+request))\b|"
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


#: ``@RECORDED{<state>/<label>}`` in an oracle or foil turn's text: that recorded
#: output, spliced in at load time, so a reply that quotes the tool never types a
#: commit sha a later skill edit would move.
_RECORDED_RE = re.compile(r"@RECORDED\{([^{}]+)\}")


def _splice(turns, states, where):
    for turn in turns or []:
        if isinstance(turn.get("content"), str):
            turn["content"] = _RECORDED_RE.sub(
                lambda m: _recorded(states, m.group(1), where)["output"].rstrip("\n"),
                turn["content"])
    return turns


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
    """The snapshot an episode runs in: named, or the last state the history reads."""
    name = case.get("sandbox")
    if not name:
        steps = _opening(case, None, where) + case.get("history", [])
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
    contradicted.
    """
    return [{"prefix": " ".join(agent.normalise(step["cmd"]).split()[:3]),
             "output": step["output"], "exit": step["exit"]}
            for step in history
            if step.get("written") and agent.looking(step["cmd"])]


def _writes(history, where):
    """(path, content) for every Write the history says already happened."""
    writes = []
    for step in history:
        call = step.get("call") or {}
        if call.get("name") == "Write":
            args = call.get("arguments") or {}
            if not args.get("file_path") or "content" not in args:
                raise ValueError("%s: a history Write needs file_path and content" % where)
            writes.append((args["file_path"], args["content"]))
    return writes


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
            history = [_resolve_step(step, states, where)
                       for step in _opening(case, states, where) + case.get("history", [])]
            case["resolved"] = {
                "history": history,
                "sandbox": _sandbox(case, where),
                "overrides": _overrides(history),
                "writes": _writes(history, where),
            }
            _splice(case["oracle"], states, where)
            _splice(case.get("foil"), states, where)
            case["assert"] = _expand(case["assert"])
            for spec in case["assert"]:
                grade.validate_assertion(spec)
            case["group"] = path.stem
            cases.append(case)
    if not cases:
        raise ValueError("no lane B cases under %s" % (Path(root) / "decision"))
    return cases


def run_b(case, spec, provider, ctx):
    skill = ctx["skills"][case["skill"]]
    _, invocation = skillmod.expand_invocation(
        ("/%s %s" % (case["skill"], case.get("ask", ""))).strip(), ctx["skills"])
    messages = [
        {"role": "system",
         "content": skillmod.agent_system_prompt(ctx["skills"], agent.WORKDIR)},
        {"role": "user", "content": invocation},
    ] + agent.history_messages(case["resolved"]["history"])
    jail = sandbox.jail()
    if jail is None and not getattr(provider, "replays", False):
        raise RuntimeError("no bubblewrap jail on this machine (bwrap missing or refused): "
                           "a live model's commands never run outside one")
    root = sandbox.materialise(case["resolved"]["sandbox"])
    try:
        repo = agent.SandboxRepo(root, sandbox.bin_dir(), case["resolved"]["overrides"],
                                 jail=jail)
        for path, content in case["resolved"]["writes"]:
            repo.write(path, content)
        return agent.run_episode(provider, spec, messages, agent.tools_for(skill), repo,
                                 max_turns=case.get("max_turns", 20),
                                 cache=ctx.get("cache", True), scope=spec["id"])
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
