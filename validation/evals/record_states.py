#!/usr/bin/env python3
"""Record the real tool's output for every state lane B replays.

Dev-time evaluation material. Runs ``fixtures/states.sh`` (hermetic temp repos
from ``tests/lib.sh``, the real ``crayon.py``), folds its JSON lines into
``cases/decision/states.json``::

    {"<state>": {"<label>": {"cmd": "crayon ...", "exit": N, "output": "..."}}}

and writes it. ``--check`` writes nothing and exits 1 when the committed file
differs from a fresh recording, which is how the gate notices that the tool's
output moved under lane B's replayed histories.

Exit codes: 0 written / in step; 1 drift (``--check``); 2 the recorder failed
or recorded nothing.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STATES = HERE / "cases" / "decision" / "states.json"
RECORDER = HERE / "fixtures" / "states.sh"


def record():
    """A fresh recording, as the dict ``states.json`` holds."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "states.jsonl"
        subprocess.run(["bash", str(RECORDER), str(out)], cwd=str(REPO), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        states = {}
        for line in out.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            states.setdefault(entry["state"], {})[entry["label"]] = {
                "cmd": entry["cmd"], "exit": entry["exit"], "output": entry["output"],
            }
    if not states:
        raise RuntimeError("the recorder recorded nothing")
    return states


def dump(states):
    return json.dumps(states, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="compare with the committed file; write nothing")
    args = parser.parse_args(argv)
    try:
        fresh = dump(record())
    except (subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
        print("record-states: the recorder failed: %s" % exc, file=sys.stderr)
        return 2
    if args.check:
        current = STATES.read_text(encoding="utf-8") if STATES.is_file() else ""
        if current != fresh:
            print("record-states: %s differs from the tool's output; run "
                  "python3 validation/evals/record_states.py and review the diff"
                  % STATES.relative_to(REPO))
            return 1
        print("record-states: OK - lane B's recorded states match the tool")
        return 0
    STATES.parent.mkdir(parents=True, exist_ok=True)
    STATES.write_text(fresh, encoding="utf-8")
    print("record-states: wrote %s" % STATES.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
