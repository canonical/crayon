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
FIXTURE = HERE / "fixtures" / "toyq"

#: Patterns a case names by macro, so the same rule reads the same everywhere.
MACROS = {
    # A dogen verb that records anything (resume --dry-run only looks).
    "@MUTATING": r"\bdogen\s+(unit\s+(new|edit|retire)|context\s+(stage|record)|"
                 r"signoff|steer|plan-steps|step|draft|edits|review|"
                 r"resume(?![^\n]*--dry-run))\b",
    # git writes, builds and publishing: never the skill's to run.
    "@PUBLISH": r"\b(git\s+(add|commit|push|reset|checkout|restore|rebase)|"
                r"sphinx-build|make\s+html|gh\s+pr)\b",
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


def _resolve_step(step, states, where):
    if isinstance(step, str):
        entry = _recorded(states, step, where)
        return {"cmd": entry["cmd"], "exit": entry["exit"], "output": entry["output"]}
    if not isinstance(step, dict) or not (
            {"user", "assistant", "call"} & set(step) or {"cmd", "exit", "output"} <= set(step)):
        raise ValueError("%s: a history step has an unknown shape: %r" % (where, step))
    return step


def _opening(case, states, where):
    """``"opening": "<state>"`` -> version, then that state's recorded show."""
    if not case.get("opening"):
        return []
    return ["tool/version_json", "%s/show_json" % case["opening"]]


def _tree(case, states, where):
    files = {}
    for path in sorted(FIXTURE.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(FIXTURE))] = path.read_text(encoding="utf-8")
    for skill_dir in sorted(skillmod.SKILLS_ROOT.glob("dogen-*")):
        for path in sorted(skill_dir.rglob("*.md")):
            key = "%s/%s/%s" % (skillmod.INSTALLED_AT, skill_dir.name,
                                path.relative_to(skill_dir))
            files[key] = path.read_text(encoding="utf-8")
    for state in case.get("files", []):
        if state not in states:
            raise ValueError("%s: no recorded state %r for files" % (where, state))
        for label, entry in states[state].items():
            if label.startswith("file:"):
                files[label[len("file:"):]] = entry["output"]
    return files


def _replies(case, history, states, where):
    """Every read-only command in the history, answered as recorded; plus extras."""
    replies = []
    for step in history:
        if "cmd" in step and agent._READONLY_DOGEN_RE.match(agent.normalise(step["cmd"])):
            replies.append({"exact": agent.normalise(step["cmd"]),
                            "output": step["output"], "exit": step["exit"]})
    for extra in case.get("replies", []):
        if isinstance(extra, str):
            entry = _recorded(states, extra, where)
            replies.append({"exact": agent.normalise(entry["cmd"]),
                            "output": entry["output"], "exit": entry["exit"]})
        elif "ref" in extra:
            entry = _recorded(states, extra["ref"], where)
            replies.append({"re": extra["re"], "output": entry["output"],
                            "exit": entry["exit"]})
        else:
            replies.append({"re": extra["re"], "output": extra["output"],
                            "exit": extra.get("exit", 0)})
    for reply in replies:
        if "re" in reply:
            re.compile(reply["re"])
    return replies


def load_b(root=CASES):
    states = load_states(Path(root) / "decision" / "states.json")
    known = skillmod.load_skills()
    cases, seen = [], set()
    files = sorted((Path(root) / "decision").glob("*.json"))
    for path in files:
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
                "files": _tree(case, states, where),
                "replies": _replies(case, history, states, where),
            }
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
    repo = agent.VirtualRepo(case["resolved"]["files"], case["resolved"]["replies"])
    return agent.run_episode(provider, spec, messages, agent.tools_for(skill), repo,
                             max_turns=case.get("max_turns", 6),
                             cache=ctx.get("cache", True), scope=spec["id"])


def oracle_b(case):
    oracle = case["oracle"]
    return oracle if isinstance(oracle, list) else [oracle]


LANES = {
    "A": {"load": load_a, "run": run_a, "oracle": oracle_a,
          "title": "skill selection"},
    "B": {"load": load_b, "run": run_b, "oracle": oracle_b,
          "title": "next action"},
}
