"""The eval lanes: how each loads its cases and turns one case into a trace.

Dev-time evaluation material. A lane is three functions:

- ``load(root)`` reads and validates the lane's case files; a malformed case is
  a ``ValueError`` before anything is called, never a mid-run surprise;
- ``run(case, spec, provider, ctx)`` makes the live call(s) and returns a trace
  ``{"turns": [...]}`` for ``grade.grade``;
- ``oracle(case)`` is a known-good reply for the case. The dry run feeds it
  through the stub provider, and the gate's self-tests assert that every
  case's own oracle passes its own assertions, so a broken regex in a case
  file is caught offline rather than blamed on a model.

Lane A (skill selection) is single-turn and tool-less.
"""

import json
from pathlib import Path

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
    return case["expect"]


LANES = {
    "A": {"load": load_a, "run": run_a, "oracle": oracle_a,
          "title": "skill selection"},
}
