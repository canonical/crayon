"""CI's size guard for VERB-09's line budget — the local guard's own code.

The budget is a **review trigger**, not a design goal (rev8 section 2.1):
behaviour is never deleted to fit it. Two thresholds carry that: above the
review trigger the guard REPORTS and stays green, at or above the failing
threshold it FAILS. The relation is deliberately asymmetric, and restating it
is how a CI job and the local guard end up disagreeing about a file sitting
exactly on a threshold.

So this script restates nothing. D-06 asks for one authoring site for the pair
of numbers; the strongest reading of it is that the job and the local guard
become the same *code*, not merely the same constants. Both thresholds and the
comparison itself are loaded out of ``tests/test_crayon_unit.py`` — the module
whose U-10 block already pins all four boundary counts — through the same
``SourceFileLoader`` shim that module uses to import the extension-less
``crayon``. No threshold and no comparison operator implementing the budget
relation is written here.

D-07 puts the verdict in the **exit code** and never in the job summary: a
summary upload failure does not fail a job on the platform, so a guard whose
verdict lived in the report would be silently green the day the report failed
to upload. The summary write is therefore best-effort and its failure is logged
and ignored; the same facts always go to stdout as well, so the guard is
readable from a developer's shell with no job-summary variable set at all.

Usage — no argument in CI and locally, where the measured file is ``crayon``:

    python3 tests/size_guard.py

An optional path argument measures a different file. It exists for U-10's
boundary tests, which stage exact line counts without touching the tool.

Exit codes mirror the sibling lints' contract: ``0`` clean (including the
reporting band, which is not a failure), ``1`` the failing threshold is reached.
"""

import importlib.machinery
import importlib.util
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The tool the budget is about.
CRAYON_PATH = ROOT / "crayon.py"

#: The single authoring site for the thresholds AND for the comparison. U-10
#: cross-checks the pair against ``.planning/REQUIREMENTS.md`` VERB-09 wherever
#: the planning tree is checked out, so the human home and the machine home
#: cannot drift apart either.
GUARD_MODULE = ROOT / "tests" / "test_crayon_unit.py"

#: Where the platform wants a job's markdown report appended.
SUMMARY_ENV = "GITHUB_STEP_SUMMARY"


def load_guard():
    """Import ``tests/test_crayon_unit.py`` for its budget block.

    Loaded under a private module name so this never collides with the same
    file imported as a test module, and because the file's ``unittest.main()``
    entry point is guarded, loading it runs no test.
    """
    loader = importlib.machinery.SourceFileLoader("_crayon_budget", str(GUARD_MODULE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def count_lines(path):
    """Count lines the way U-10 counts them.

    Read as UTF-8 text and split, identically to the assertion in
    ``TestLineBudget``, so the two can never disagree about a trailing newline.
    """
    return len(path.read_text(encoding="utf-8").splitlines())


def report_rows(path, lines, annotate, fail, verdict):
    """The report's facts, as ``(label, value)`` pairs.

    The five the decision asks for — line count, review trigger, fail
    threshold, headroom, verdict — plus the name of the file they were measured
    from, because the measured path is an argument and a report that does not
    say what it measured cannot be checked by the person reading it.
    """
    return [
        ("measured file", "`%s`" % path.name),
        ("line count", "%d" % lines),
        ("review trigger", "%d" % annotate),
        ("fail threshold", "%d" % fail),
        ("headroom", "%d line(s) to the fail threshold" % (fail - lines)),
        ("verdict", "**%s**" % verdict),
    ]


def render_table(rows):
    """A markdown table the job summary renders and a terminal still reads."""
    out = ["| what | value |", "| --- | --- |"]
    out.extend("| %s | %s |" % (label, value) for label, value in rows)
    return "\n".join(out) + "\n"


def write_summary(table, destination):
    """Append the table to the job summary. Best effort, never the verdict.

    A summary upload failure does not fail a job, so a guard that let this
    write decide anything would be green on the day the report went missing.
    """
    try:
        with open(destination, "a", encoding="utf-8") as handle:
            handle.write(table)
    except OSError as exc:
        sys.stderr.write(
            "size_guard: could not write the job summary to %s (%s); the "
            "verdict is the exit code and is unaffected\n" % (destination, exc)
        )
        return False
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if len(argv) > 1:
        sys.stderr.write("usage: size_guard.py [path-to-measure]\n")
        return 2
    measured = pathlib.Path(argv[0]) if argv else CRAYON_PATH
    if not measured.is_file():
        sys.stderr.write("size_guard: %s is not a file\n" % measured)
        return 2

    guard = load_guard()
    lines = count_lines(measured)
    verdict = guard.budget_verdict(lines)
    rows = report_rows(
        measured, lines, guard.BUDGET_ANNOTATE, guard.BUDGET_FAIL, verdict
    )
    table = render_table(rows)

    sys.stdout.write(table)
    destination = os.environ.get(SUMMARY_ENV)
    if destination:
        write_summary(table, destination)

    # The verdict, and only the verdict, decides the exit code. The reporting
    # band is not a failure: it is the review trigger doing its job.
    return 1 if verdict == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
