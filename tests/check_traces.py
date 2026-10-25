"""Bookkeeping gate: every trace in ``docs/contract.md`` names a test FUNCTION.

The claim is deliberately narrow and the wording everywhere here is chosen to
keep it that way (WR-12). This script greps the suites for a function whose
NAME carries the row's test id. It never opens that function's body, so it can
say that a row's test exists and nothing at all about whether the row's outcome
is the outcome that test asserts — a row can be "cleared" while its clause is
unexercised in the shape that matters, or unimplemented. The contract's §"Trace
table" preamble says exactly this, and the two statements are kept in step by
hand.

D-09 makes each test carry its own id and the trace(s) it discharges in its
name — ``test_n40_t31_t32_retire_releases_the_target_claim`` — so the link
between the contract's trace table and the suites is greppable rather than
remembered. This script is the grep: it reads the table, and for every row
either finds the named test or says exactly which T#, which expected id and
which files it looked in. Clearing a mark is then a one-line edit to the table.

It mirrors :mod:`skill_lint`: a single :func:`main` with
a ``0`` (clean) / ``1`` (violation) / ``2`` (vacuous pass — nothing was checked)
contract. Phase 18's docs-check calls it.

Scan scope (decided in plan 17-01 for the Trace table; widened to the
Mechanisms table by 19 D-12):

1. **The ``## Trace table`` section, every row.** Unchanged: each row names a
   T#, and the checker either finds a test whose name carries the row's test id
   or says which T#, which expected id and which files it looked in.
2. **The ``## Mechanisms`` section, under one rule.** A Mechanisms row is
   scanned when its signal cell carries a parenthetical naming a file — the
   shape ``N-40 (`tests/test_crayon_lifecycle.sh`)`` the table already uses —
   **and** that file is in :data:`SUITE_FILES`. Two rows qualify today: the
   ``verify`` row's ``V-01…V-04 (`validation/fixtures.sh`)``, which is the link
   D-12 exists to gate and was swept by hand until this phase, and the
   ``retire`` row's ``N-40``. The earlier note here said the Mechanisms table
   was excluded because U-08, A-36 and A-37 were then unlanded; all three have
   since landed and no ``planned`` mark remains anywhere in the contract, so
   the exclusion is now the parenthetical rule above and nothing else.
3. **Every Mechanisms row the rule does not scan is printed by name, with the
   reason, on every run.** The narrowing is reported, never silent — docs-check
   surfaces this output on every CI run. Two reasons occur today:

   - ``tests/install_smoke.sh`` (the ``contract`` + ``min_tool`` row's A-37) is
     named but is not a suite file: it is a linear install walk with zero
     ``test_`` functions — its A-37 ids live in assertion message strings — and
     restructuring a 258-line script to satisfy a name grep buys less than it
     costs.
   - Eleven rows carry no suite-file parenthetical at all. Five of them
     (``N-01/02/05``, ``U-05 · U-08``, ``N-04``, ``N-03, N-24``, ``N-16``) name
     ids no test function carries anywhere; that is pre-existing traceability
     drift STATE.md already records, and closing it by renaming real tests to
     carry ids they do not otherwise have is rejected.

V-05 (the T25 unknown-kinds trace) is a ``verify`` behaviour test and lives in
``tests/test_crayon_lifecycle.sh`` with ``v05`` in its function name, not in the
phase 19 fixture series; A-36 lives in ``tests/test_crayon_lifecycle.sh`` rather
than in the acceptance file, and the function that landed carries a comment
saying why an A-id lives in the N file.

Two rows may name the same test id — the table already does, and T31/T32 both
point at N-40 — so the check is per row and never a bijection.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contract.md"

#: The suites a trace test may live in. Each is skipped with a printed note when
#: absent — ``tests/test_skill_text.py`` lands in plan 17-02, and
#: ``validation/fixtures.sh`` is phase 19's validation kit: the four corruption
#: fixtures V-01…V-04, added here by 19 D-12 so the Mechanisms ``verify`` row's
#: link to them is a gate rather than a hand sweep.
SUITE_FILES = (
    ROOT / "tests" / "test_crayon_acceptance.sh",
    ROOT / "tests" / "test_crayon_lifecycle.sh",
    ROOT / "tests" / "test_crayon_unit.py",
    ROOT / "tests" / "test_skill_text.py",
    ROOT / "validation" / "fixtures.sh",
)

#: The suite file the Mechanisms scan exists for (19 D-12). The scan must reach
#: it on every run: dropping the parenthetical from the one row D-12 was written
#: to gate would otherwise leave the other parenthetical row scanning happily
#: and the run reading clean, which is the vacuous pass in miniature.
GATED_SUITE = ROOT / "validation" / "fixtures.sh"

_SECTION_RE = re.compile(r"^##\s")
_TRACE_TABLE_RE = re.compile(r"^##\s+Trace table\s*$")
_MECHANISMS_TABLE_RE = re.compile(r"^##\s+Mechanisms\s*$")
#: The parenthetical the Mechanisms table uses to name a row's suite file:
#: ``N-40 (`tests/test_crayon_lifecycle.sh`)`` — backticks inside parentheses,
#: and an extension, so ``(`summary --md`)``-shaped prose is not mistaken for a
#: file name.
_SUITE_PAREN_RE = re.compile(r"\(`([^`]+\.[A-Za-z0-9]+)`\)")
_TRACE_ID_RE = re.compile(r"^T\d+[a-z]?$")
_TEST_ID_RE = re.compile(r"\b([A-Za-z])-(\d+)\b")
_PLANNED_RE = re.compile(r"planned")
#: One shape for both suites: ``test_foo() {`` in bash and ``def test_foo(self):``
#: in unittest. The ``test_`` prefix is the same prefix the bash auto-discovery
#: greps for, so the two cannot drift apart.
_TEST_NAME_RE = re.compile(r"^\s*(?:def\s+)?(test_[A-Za-z0-9_]+)\s*\(", re.MULTILINE)


def parse_trace_rows(text):
    """Return ``[(trace_id, governing_rule, test_id_cell)]`` in table order.

    Only the ``## Trace table`` section is read; the section ends at the next
    ``## `` heading or at the end of the file. The header and separator rows are
    dropped by requiring the first cell to look like a trace id.
    """
    rows = []
    inside = False
    for line in text.splitlines():
        if _TRACE_TABLE_RE.match(line):
            inside = True
            continue
        if inside and _SECTION_RE.match(line):
            break
        if not inside or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or not _TRACE_ID_RE.match(cells[0]):
            continue
        rows.append((cells[0], cells[1], cells[2]))
    return rows


def parse_mechanism_rows(text):
    """Return ``[(mechanism, signal_cell, suite_name)]`` in table order.

    Only the ``## Mechanisms`` section is read; the section ends at the next
    ``## `` heading. That table is five cells wide with a prose first cell, so
    :func:`parse_trace_rows`'s three-cell / ``^T\\d+$`` shape cannot read it.
    The header and separator rows are dropped the same way the trace parser
    drops its own — by requiring the shape rather than by special-casing them:
    a row must have five cells and its signal cell (the last) must name a test
    id, which neither ``Signal (how we know it helped)`` nor ``---`` does.

    ``suite_name`` is the file named by the signal cell's parenthetical, or
    ``None`` when the cell carries none. A row without a parenthetical is
    returned rather than discarded, so :func:`main` can name it in the
    not-scanned report instead of narrowing the scan silently.
    """
    rows = []
    inside = False
    for line in text.splitlines():
        if _MECHANISMS_TABLE_RE.match(line):
            inside = True
            continue
        if inside and _SECTION_RE.match(line):
            break
        if not inside or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or not _TEST_ID_RE.search(cells[-1]):
            continue
        match = _SUITE_PAREN_RE.search(cells[-1])
        rows.append((cells[0], cells[-1], match.group(1) if match else None))
    return rows


def test_token(cell):
    """``'N-40 (`planned`)'`` → ``'n40'``; ``None`` when the cell names no id."""
    match = _TEST_ID_RE.search(cell)
    if match is None:
        return None
    return "%s%s" % (match.group(1).lower(), match.group(2))


def collect_test_names(paths):
    """``({path: {names}}, [missing paths])`` for the suites that exist."""
    found = {}
    missing = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            missing.append(path)
            continue
        found[path] = set(_TEST_NAME_RE.findall(text))
    return found, missing


def locate(token, suites):
    """Every suite file holding a test whose name carries ``token`` as a part.

    The token is matched between underscores rather than as a bare substring, so
    ``n4`` never satisfies a row that asked for ``n40``.
    """
    bounded = re.compile(r"(?:^|_)%s(?:_|$)" % re.escape(token))
    return [
        path
        for path, names in suites.items()
        if any(bounded.search(name) for name in names)
    ]


def check_row(row, suites, grepped):
    """One row's violation message, or ``None`` when the row is clean."""
    trace_id, _rule, cell = row
    token = test_token(cell)
    if token is None:
        return "%s: the test-id cell %r names no test id; grepped %s" % (
            trace_id,
            cell,
            grepped,
        )
    expected = cell.split("(")[0].strip() or cell
    holders = locate(token, suites)
    if _PLANNED_RE.search(cell):
        if holders:
            return (
                "%s: %s is still marked planned, but a test named for it exists "
                "in %s — clear the mark" % (trace_id, expected, ", ".join(holders))
            )
        return (
            "%s: %s is still marked planned and no test named for it exists; "
            "grepped %s" % (trace_id, expected, grepped)
        )
    if not holders:
        return "%s: %s names no test; grepped %s" % (trace_id, expected, grepped)
    return None


def check_mechanism_row(row, suites, grepped):
    """One scanned Mechanisms row's violation message, or ``None`` when clean.

    Same grep, same narrowness as :func:`check_row`: the row's first test id is
    turned into a token and a function whose NAME carries it is looked for. Note
    that ``_TEST_ID_RE`` takes only the first id in a cell, so ``V-01…V-04``
    checks ``v01`` alone — intended, because the four fixtures land together.

    The file the row NAMES is where the test has to be (WR-04). This used to
    unpack ``suite_name`` and then use it only in the error message, while the
    existence test searched every entry of :data:`SUITE_FILES` — so the
    ``verify`` row's claim that V-01…V-04 live in ``validation/fixtures.sh``,
    which is the link 19 D-12 exists to gate, was satisfied identically by a
    ``test_v01_*`` function in any other suite. A row that says *where* and is
    checked for *whether* is not a gate on the row. :data:`GATED_SUITE`'s guard
    in :func:`main` is a different assertion and does not cover this one: it
    checks only that some scanned row still NAMES the file.

    Every file the token was found in is named on a violation, because "it is
    not in the file the row points at" is only actionable once a reader knows
    where it is instead.
    """
    mechanism, cell, suite_name = row
    token = test_token(cell)
    if token is None:
        return "Mechanisms %s: the signal cell %r names no test id; grepped %s" % (
            mechanism,
            cell,
            grepped,
        )
    expected = cell.split("(")[0].strip() or cell
    holders = locate(token, suites)
    if suite_name not in holders:
        return (
            "Mechanisms %s: %s points at %s, and no test function THERE carries "
            "the token %r (found in %s); grepped %s"
            % (
                mechanism,
                expected,
                suite_name,
                token,
                ", ".join(sorted(holders)) or "nothing",
                grepped,
            )
        )
    return None


def main():
    """Check every trace-table row, and every gated Mechanisms row, against the suites.

    Returns
    -------
    int
        ``0`` when every checked row names a test function that exists and
        carries no planned mark; ``1`` on any violation; and ``2`` on a vacuous
        pass — a run that checked nothing it was written to check, which must
        never read as clean. Three conditions raise ``2``:

        * zero trace rows parsed (a renamed heading or a reshaped Trace table),
        * zero Mechanisms rows scanned (the same, for the Mechanisms table),
        * no scanned Mechanisms row naming :data:`GATED_SUITE` — the row 19 D-12
          exists to gate lost its suite-file parenthetical, which the bare
          zero-scanned count would miss while the ``retire`` row kept the scan
          non-empty.
    """
    try:
        text = CONTRACT.read_text(encoding="utf-8")
    except OSError as bad:
        print(
            "check-traces: ERROR - %s is unreadable (%s)"
            % (CONTRACT.relative_to(ROOT), type(bad).__name__),
            file=sys.stderr,
        )
        return 2

    rows = parse_trace_rows(text)
    if not rows:
        print(
            "check-traces: ERROR - parsed 0 trace rows from %s (heading renamed "
            "or table reshaped?)" % CONTRACT.relative_to(ROOT),
            file=sys.stderr,
        )
        return 2

    suites, missing = collect_test_names(SUITE_FILES)
    for path in missing:
        print("check-traces: note - %s is absent, skipped" % path.relative_to(ROOT))
    sys.stdout.flush()
    # Keyed by the repo-relative path, because that is the string every
    # violation message has to print for the report to be actionable.
    by_file = {str(path.relative_to(ROOT)): names for path, names in suites.items()}
    grepped = ", ".join(sorted(by_file)) or "(no suite file present)"

    violations = []
    cleared = []
    for row in rows:
        message = check_row(row, by_file, grepped)
        if message is None:
            cleared.append("%s (%s)" % (row[0], row[2]))
        else:
            violations.append(message)

    if cleared:
        print(
            "check-traces: cleared %d row(s): %s" % (len(cleared), ", ".join(cleared))
        )
    sys.stdout.flush()

    # The Mechanisms pass (19 D-12). A row is scanned only when its signal cell
    # names a file that is in SUITE_FILES; every other row is named below with
    # the reason, because a narrowing nobody can see is the defect this report
    # exists against.
    suite_names = set(str(path.relative_to(ROOT)) for path in SUITE_FILES)
    gated = str(GATED_SUITE.relative_to(ROOT))
    scanned = []
    not_scanned = []
    for row in parse_mechanism_rows(text):
        mechanism, _cell, suite_name = row
        if suite_name is None:
            not_scanned.append(
                (mechanism, "signal cell carries no suite-file parenthetical")
            )
        elif suite_name not in suite_names:
            not_scanned.append(
                (mechanism, "names %s, which is not a suite file" % suite_name)
            )
        else:
            scanned.append(row)
            message = check_mechanism_row(row, by_file, grepped)
            if message is not None:
                violations.append(message)

    print(
        "check-traces: %d Mechanisms row(s) not scanned, named rather than "
        "silently skipped:" % len(not_scanned),
        *["%s - %s" % (mechanism, reason) for mechanism, reason in not_scanned],
        sep="\n  "
    )
    sys.stdout.flush()

    if violations:
        print(
            "check-traces: VIOLATION(S) - %d across %d trace row(s) and %d "
            "scanned Mechanisms row(s):" % (len(violations), len(rows), len(scanned)),
            *violations,
            sep="\n  ",
            file=sys.stderr,
        )
        return 1
    if not scanned:
        print(
            "check-traces: ERROR - scanned 0 Mechanisms rows of %s (heading "
            "renamed, table reshaped, or every suite-file parenthetical "
            "dropped?)" % CONTRACT.relative_to(ROOT),
            file=sys.stderr,
        )
        return 2
    if not any(row[2] == gated for row in scanned):
        print(
            "check-traces: ERROR - no scanned Mechanisms row names %s; the row "
            "D-12 exists to gate has lost its suite-file parenthetical and its "
            "link to the fixtures is unchecked" % gated,
            file=sys.stderr,
        )
        return 2
    print(
        "check-traces: OK - %d trace rows and %d scanned Mechanisms rows (%d not "
        "scanned), every id names a test function that exists (bodies are not "
        "read)" % (len(rows), len(scanned), len(not_scanned))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
