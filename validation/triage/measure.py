#!/usr/bin/env python3
"""How often crayon's documentation triage advice matched what the authors then did.

Dev-time evaluation material. Reads ``crayon triage export --json`` from one or
more documentation repositories that turned the triage mode on (``git config
crayon.collect true``), and reports, over the records that have a label:

- precision and recall of "needs documentation", the decision the advice makes;
- how often the advised Diataxis type was the type the author signed off;
- how many records carry each kind of label, and how many are still pending.

    python3 validation/triage/measure.py --repo ~/src/docs-a --repo ~/src/docs-b

The first use of the triage records is this measurement. A model is trained for
the decision (``build_dataset.py``) only if the advice is often wrong and enough
labelled records exist.

Exit codes: 0 a report was printed; 2 no repository gave a labelled record.
"""

import argparse
import json
import subprocess
import sys


def export(repo, crayon="crayon"):
    """The export rows of one repository, each tagged with the repository."""
    done = subprocess.run([crayon, "triage", "export", "--json"], cwd=repo,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    rows = json.loads(done.stdout.decode("utf-8"))["rows"]
    for row in rows:
        row["repo"] = repo
    return rows


def ratio(numerator, denominator):
    return None if denominator == 0 else round(numerator / float(denominator), 3)


def measure(rows):
    """The report as a dict, from export rows."""
    labelled = [row for row in rows if row["label"] is not None]
    advised = [row["advice"]["needs_docs"] for row in labelled]
    actual = [row["label"] for row in labelled]
    tp = sum(1 for a, b in zip(advised, actual) if a and b)
    fp = sum(1 for a, b in zip(advised, actual) if a and not b)
    fn = sum(1 for a, b in zip(advised, actual) if not a and b)
    typed = [row for row in labelled
             if row["advice"]["type"] and row["outcome"]["intent"]]
    sources = {}
    for row in rows:
        sources[row["label_source"]] = sources.get(row["label_source"], 0) + 1
    return {
        "records": len(rows),
        "labelled": len(labelled),
        "label_sources": sources,
        "needs_docs": {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
                       "true_positive": tp, "false_positive": fp, "false_negative": fn},
        "type_matches": {"matched": sum(1 for row in typed
                                        if row["advice"]["type"] == row["outcome"]["intent"]),
                         "compared": len(typed)},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", action="append", required=True,
                        help="a documentation repository with triage records (repeatable)")
    parser.add_argument("--crayon", default="crayon", help="the crayon executable")
    args = parser.parse_args(argv)
    rows = [row for repo in args.repo for row in export(repo, args.crayon)]
    report = measure(rows)
    print(json.dumps(report, indent=2))
    return 0 if report["labelled"] else 2


if __name__ == "__main__":
    sys.exit(main())
