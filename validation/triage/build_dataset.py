#!/usr/bin/env python3
"""Build a fine-tuning dataset for the documentation triage decision, once there is enough data.

Dev-time evaluation material. Reads ``crayon triage export --json`` from one or
more documentation repositories, keeps the records that have a label, and writes
chat-format rows (``{"messages": [system, user, assistant]}``, the format TRL's
supervised trainer reads) to ``--out``:

- the user turn is the change: its changed paths, ``git diff --stat`` and the
  diff itself, cut at ``--max-diff`` bytes, read from git when this runs, plus
  the repository's documentation pages;
- the assistant turn is what the authors' outcome says: whether the change
  needed documentation, which pages, and which Diataxis type.

The rows are split by time, oldest first: ``train.jsonl`` (80%),
``calibration.jsonl`` (10%, for fitting a temperature on held-out data) and
``test.jsonl`` (10%). With two or more repositories, ``--hold-out-repo`` keeps
one repository's rows out of training entirely, as a test of another source.

It refuses to build anything below ``MIN_ROWS`` labelled records whose commits
still exist: a model trained on fewer would measure noise. ``measure.py`` comes first; train only when it
shows the advice is often wrong.

Exit codes: 0 written; 2 too few labelled records, or none.
"""

import argparse
import json
import os
import subprocess
import sys

from measure import export

MIN_ROWS = 300
SYSTEM = ("Decide whether a code change needs a documentation change. Answer with JSON: "
          '{"needs_docs": true or false, "pages": [paths under docs/], "type": one of '
          '"tutorial", "how-to", "reference", "explanation", or null}.')


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args), stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, check=True).stdout.decode("utf-8", "replace")


def reachable(row):
    """Do both of the record's commits still exist? A squashed branch can take them away."""
    return all(subprocess.run(["git", "-C", row["repo"], "cat-file", "-e", rev + "^{commit}"],
                              stderr=subprocess.DEVNULL).returncode == 0
               for rev in (row["base"], row["head"]))


def prompt(row, max_diff):
    repo, base, head = row["repo"], row["base"], row["head"]
    diff = git(repo, "diff", base, head, "--", *row["paths"])
    if len(diff.encode("utf-8")) > max_diff:
        diff = diff.encode("utf-8")[:max_diff].decode("utf-8", "ignore") + "\n[diff cut]"
    pages = git(repo, "ls-tree", "-r", "--name-only", head, "--", "docs").split()
    return ("Changed paths:\n%s\n\nSummary:\n%s\nDiff:\n%s\nDocumentation pages:\n%s"
            % ("\n".join(row["paths"]), git(repo, "diff", "--stat", base, head),
               diff, "\n".join(pages)))


def answer(row):
    outcome = row["outcome"]
    return json.dumps({"needs_docs": row["label"],
                       "pages": outcome["targets"] if row["label"] else [],
                       "type": outcome["intent"] if row["label"] else None})


def split(rows, hold_out_repo=None):
    held = [row for row in rows if hold_out_repo and row["repo"] == hold_out_repo]
    rows = sorted((row for row in rows if row not in held), key=lambda row: row["at"])
    train_end, calibration_end = int(len(rows) * 0.8), int(len(rows) * 0.9)
    return {"train": rows[:train_end], "calibration": rows[train_end:calibration_end],
            "test": rows[calibration_end:] + held}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", action="append", required=True,
                        help="a documentation repository with triage records (repeatable)")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                      ".data"),
                        help="where the JSONL files go (default validation/triage/.data)")
    parser.add_argument("--hold-out-repo", help="a repository kept out of training")
    parser.add_argument("--max-diff", type=int, default=20000, help="diff bytes per row")
    parser.add_argument("--crayon", default="crayon", help="the crayon executable")
    args = parser.parse_args(argv)
    rows = [row for repo in args.repo for row in export(repo, args.crayon)
            if row["label"] is not None]
    gone = [row for row in rows if not reachable(row)]
    if gone:
        print("build-dataset: %d labelled record(s) skipped: their commits no longer exist"
              % len(gone), file=sys.stderr)
        rows = [row for row in rows if row not in gone]
    if len(rows) < MIN_ROWS:
        print("build-dataset: %d labelled record(s); a dataset needs at least %d. Keep "
              "collecting, and read measure.py's report first." % (len(rows), MIN_ROWS),
              file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    for name, part in split(rows, args.hold_out_repo).items():
        with open(os.path.join(args.out, "%s.jsonl" % name), "w", encoding="utf-8") as handle:
            for row in part:
                handle.write(json.dumps({"messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt(row, args.max_diff)},
                    {"role": "assistant", "content": answer(row)},
                ]}) + "\n")
        print("build-dataset: %s.jsonl, %d row(s)" % (name, len(part)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
