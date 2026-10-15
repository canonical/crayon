"""Documentation-accuracy gate: the observables, one release check, one delegation.

Everything else this phase ships can be true on the day it lands and quietly
false a month later — a verb renamed, a reason added, a file moved. This is the
one artefact that goes red when that happens, and it goes red naming what it
compared.

What it claims, and nothing wider:

1. **Verbs** — the rows in the ``VERBS`` region, carried by exactly one
   document of the documented set (``docs/internals.md`` today), are exactly
   the subcommands the tool registers. The oracle is ``crayon --help``'s own
   subcommand list, never a list kept here, so a wrong document cannot be made
   green by editing this file (T-18-30).
2. **Reasons** — the ``REASONS`` region, carried by exactly one document of the
   documented set (``docs/internals.md`` today), is ONE compact table, one
   row per exit code with that code's reasons listed in its last cell; the
   rows in ``docs/contract.md``'s reason table are one per reason. Each side,
   flattened to ``{reason: exit}``, equals ``crayon.REASONS`` by name and code.
3. **Compatibility** — the ``COMPAT`` region, carried by exactly one document
   of the documented set (``docs/compatibility.md`` today), and
   ``docs/contract.md`` section 5.10 carry ``contract`` and ``min_tool`` as the
   literal strings the tool reports. A region present in two documents is a
   violation: two reader-facing copies are the drift this gate exists against.
4. **Links** — every in-repo markdown link in the documented set resolves to a
   path that exists, and every ``#anchor`` to a heading in the target file.
5. **Release record** — ``CHANGELOG.md``'s topmost ``## [x.y.z]`` section
   carries an ISO date and none of ``RELEASE_PLACEHOLDERS``. A file with no
   versioned heading scanned nothing and is a ``2``, never a clean run, so an
   unfilled release-time slot cannot ship green (REL-02, CI-03).
6. **Traces** — ``tests/check_traces.py``'s ``main()`` is called and folded into
   the tally. There is exactly one trace-table parser in this repository and it
   is not here (17 D-09).
7. **Skills first** — the reader-facing documents in ``SKILLS_FIRST_DOCS`` name
   no ``crayon <verb>`` outside a ``## Under the hood`` section. The verbs are
   ``crayon --help``'s, the same oracle as observable 1. The reader drives crayon
   through the skills; the tool's commands belong to the pages that say they
   are looking underneath.

What it does **not** claim: nothing here judges prose. A section can be wrong,
stale or misleading in every word and this gate stays green, because it compares
the named observables and only those. Observable 7 reads prose lines, but only
for one literal shape. The release record is no exception:
it asserts that the section is dated and does not announce its own
incompleteness, and nothing about whether what it says is true. There is deliberately no general
"every module constant must have a doc row" rule and nothing walks the tool's
namespace: the tool's own step-count backstop constant has no contract row
behind it by design — section 5.2 caps the step plan in bytes and names no count
cap — so a general rule would report it forever and be silenced forever
(``.planning/WINDOWS.md`` entry 17). This file does not know that constant
exists.

Nothing outside the repository is opened, fetched or resolved: a link bearing a
scheme is skipped by construction, so an outage somewhere else can never turn
this gate red (D-11, T-18-31).

The file is deliberately **not** named with a ``test_`` prefix. A ``test_*.py``
in ``tests/`` is pulled into the unittest namespace and into
``test_every_test_module_in_tests_is_in_the_gate``, and this is a checker with
its own suite (``tests/test_check_docs.py``), not a suite.

Mirrors :mod:`check_traces` / ``scripts/planning_lint.py`` / ``scripts/skill_lint.py``:
one :func:`main` with a ``0`` clean / ``1`` violation / ``2`` scanned-nothing
contract. Each observable carries its **own** ``2`` arm: a single shared counter
would let a reshaped verbs table ride to green on the links that did parse.
"""

import argparse
import importlib.machinery
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The documented set. Every file here is scanned for links; the ones that carry
#: observables (the region carriers and ``docs/contract.md``) are also parsed for
#: them.
DOC_FILES = (
    "README.md",
    "AGENTS.md",
    "docs/contents.md",
    "docs/internals.md",
    "docs/contract.md",
    "docs/install.md",
    "docs/compatibility.md",
    "docs/hooks.md",
    "docs/shellcheck.md",
    "docs/development.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/upgrade.md",
    "docs/context.md",
    "docs/evals.md",
    "CHANGELOG.md",
    "skills/README.md",
    "skills/crayon-fetch/SKILL.md",
    "skills/crayon-onboard/SKILL.md",
    "skills/crayon-plan/SKILL.md",
    "skills/crayon-review/SKILL.md",
    "skills/crayon-write/SKILL.md",
)

#: Row shapes. Each requires the first cell to look like the id it is after, so
#: header and separator rows fall out without being special-cased — the idiom
#: :mod:`check_traces` uses for the trace table.
VERB_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z-]*)`\s*\|")
REASON_ROW_RE = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*([0-9])\s*\|$")
#: README's compact shape: the exit code in the first cell, a meaning in the
#: second, and every reason of that code as a backticked name in the last.
COMPACT_REASON_ROW_RE = re.compile(r"^\|\s*`([0-9])`\s*\|[^|]*\|([^|]*)\|$")
COMPACT_REASON_NAME_RE = re.compile(r"`([a-z_]+)`")
COMPAT_ROW_RE = re.compile(r"^\|\s*`(contract|min_tool)`\s*\|\s*`([^`]+)`\s*\|$")

#: ``[text](target)``, with an optional quoted title. Reference-style links and
#: bare autolinks are out of scope: the documented set uses neither, and a
#: pattern that guessed at them would report its own guesses.
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SECTION_RE = re.compile(r"^##\s")

#: The anchor of ``docs/contract.md``'s reason table, the same literal
#: ``tests/test_crayon_unit.py``'s ``contract_reason_table()`` anchors at. The two
#: readers are pinned to one anchor on purpose so they cannot drift apart.
REASON_TABLE_ANCHOR = "Reason table:"
COMPAT_HEADING = "## 5.10 Compatibility"

#: The reader-facing documents: the ones a Technical Author follows to install
#: and use crayon through its skills. Every other document in the set is under
#: the hood by definition. In these, a ``crayon <verb>`` may appear only in a
#: section headed exactly ``UNDER_THE_HOOD_HEADING``.
SKILLS_FIRST_DOCS = (
    "README.md",
    "docs/contents.md",
    "docs/install.md",
    "docs/context.md",
    "docs/upgrade.md",
    "docs/hooks.md",
)
UNDER_THE_HOOD_HEADING = "## Under the hood"

#: The literal markers that mean a release-time slot was never filled. Their
#: presence in the TOPMOST released section is a violation and never a vacuous
#: pass: the section was found and read, and what it says is that it is
#: incomplete. The first is the fragment 18 CR-02 found live in the tree
#: (``#### Release-time evidence — the one placeholder left`` closed with it),
#: the second is the reserved-slot wording plan 18-04 introduced when it wrote
#: the section, and the last two are the generic debt markers — a released
#: section is the one place in this repository where either is never a note to
#: self but a gap in the record the tag is cut against.
#:
#: Matched as substrings against the section body only. A marker in
#: ``## [Unreleased]`` or in an older release below the topmost one is not a
#: finding: this observable is about the section the tag is cut against.
RELEASE_PLACEHOLDERS = (
    "it is **not** filled",
    "PLACEHOLDER, not final",
    "TBD",
    "TODO",
)

#: A released heading — ``## [x.y.z]`` with an optional ``- YYYY-MM-DD`` suffix.
#: Requiring a semantic version inside the bracket is what keeps
#: ``## [Unreleased]`` out of the released slice, and it sits DIRECTLY above the
#: released heading in this repository's changelog, so a positional split would
#: have taken it instead. The date is group 2 and is ``None`` when the heading
#: carries none, which is itself the finding: the file's preamble declares Keep
#: a Changelog, whose released headings are dated, and the date is the one field
#: that says whether ``[Unreleased]``'s "Nothing unreleased" was true at a
#: moment or is merely stale.
RELEASED_HEADING_RE = re.compile(
    r"^##[ \t]+\[(\d+\.\d+\.\d+)\](?:[ \t]+-[ \t]+(\d{4}-\d{2}-\d{2}))?[ \t]*$",
    re.MULTILINE,
)


def load_module(name, path):
    """Import an extension-less or off-path file as ``name``.

    ``sys.path.insert`` would shadow any stdlib module sharing a name with a
    file in the tree for the whole process, and this runs inside the same
    interpreter as every other suite under ``python3 -m unittest``.
    """
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def marked_region(text, name):
    """The body between ``<!-- NAME:BEGIN -->`` and ``<!-- NAME:END -->``.

    ``None`` when either marker is absent. Regions are located by their
    sentinels rather than by a heading, so renaming the heading above a table
    can never silently move it out of scope.
    """
    begin = "<!-- %s:BEGIN -->" % name
    end = "<!-- %s:END -->" % name
    start = text.find(begin)
    if start < 0:
        return None
    stop = text.find(end, start)
    if stop < 0:
        return None
    return text[start + len(begin) : stop]


def region_in_documents(documents, name):
    """The one document carrying the ``name`` region, as ``(path, body)``.

    ``(None, [])`` when no document carries it, and ``(None, paths)`` when more
    than one does — the caller reports the second as a violation, because a
    reader-facing table with two homes is the drift this file exists against.
    """
    carriers = []
    for relative, text in sorted(documents.items()):
        body = marked_region(text, name)
        if body is not None:
            carriers.append((relative, body))
    if len(carriers) == 1:
        return carriers[0]
    return None, [relative for relative, _ in carriers]


def one_home(documents, name, observable, report):
    """The one carrier of the ``name`` region, as ``(path, body)``.

    ``(None, None)`` when no document carries it, and also when two or more
    do — reported here as a violation, because a reader-facing table with two
    homes is the drift this file exists against. The caller's own ``2`` arm
    then reports that nothing was checked.
    """
    carrier, body = region_in_documents(documents, name)
    if carrier is None:
        if body:
            report.violation(
                observable,
                "the <!-- %s:BEGIN --> / <!-- %s:END --> region is carried by "
                "%d documents; it has exactly one reader-facing home"
                % (name, name, len(body)),
                "carriers",
                body,
                "allowed",
                ["one document"],
            )
        return None, None
    return carrier, body


def heading_section(text, heading):
    """The body under ``heading`` up to the next ``## `` heading, or ``None``."""
    start = text.find(heading)
    if start < 0:
        return None
    body = text[start + len(heading) :]
    lines = []
    for line in body.splitlines():
        if _SECTION_RE.match(line):
            break
        lines.append(line)
    return "\n".join(lines)


def anchored_slice(text, anchor):
    """The text from ``anchor`` onward, or ``None`` when the anchor is absent."""
    start = text.find(anchor)
    if start < 0:
        return None
    return text[start:]


def table_rows(body, row_re):
    """Every match of ``row_re`` over ``body``'s lines, as tuples of its groups.

    The one table reader for every table observable. Rows stop being collected
    at the first non-table line after rows have begun, so a second table further
    down a slice is never folded into the first.
    """
    if body is None:
        return []
    rows = []
    for line in body.splitlines():
        stripped = line.strip()
        match = row_re.match(stripped)
        if match is not None:
            rows.append(match.groups())
        elif rows and not stripped.startswith("|"):
            break
    return rows


def compact_reason_rows(body):
    """README's compact reason table, flattened to ``(name, code)`` tuples.

    One table row per exit code; every backticked name in the row's last cell
    is a reason with that code. A row with no names (exit ``0``) contributes
    nothing, which is why the vacuous-pass guard counts tuples and not rows.
    """
    rows = []
    for code, cell in table_rows(body, COMPACT_REASON_ROW_RE):
        for name in COMPACT_REASON_NAME_RE.findall(cell):
            rows.append((name, code))
    return rows


def slugify(heading):
    """A markdown heading to its anchor, the way the forge renders one.

    Lowercase, drop every character that is not a letter, digit, space, hyphen
    or underscore (so ``5.10`` becomes ``510`` and backticks vanish), then spaces
    to hyphens. This is the rule as commonly understood rather than one read off
    a published specification: if an anchor that renders correctly is reported
    dead, this function is the first suspect.
    """
    text = heading.strip().lower()
    text = "".join(ch for ch in text if ch.isalnum() or ch in " -_")
    return "-".join(text.split())


def file_anchors(path):
    """Every anchor the markdown file at ``path`` offers, as a set."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    anchors = set()
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match is not None:
            slug = slugify(match.group(2))
            if slug:
                anchors.add(slug)
    return anchors


def registered_verbs(root):
    """The subcommands ``crayon --help`` registers, in the order it prints them.

    Taken from the brace group argparse renders in the usage block. ``COLUMNS``
    is widened so the group is not wrapped, and the whitespace is stripped
    anyway so a wrapped group would still parse.
    """
    tool = root / "crayon.py"
    if not tool.is_file():
        return []
    env = dict(os.environ)
    env["COLUMNS"] = "200"
    try:
        proc = subprocess.run(
            [sys.executable, str(tool), "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
    except OSError:
        return []
    text = proc.stdout.decode("utf-8", "replace")
    match = re.search(r"\{([^{}]+)\}", text)
    if match is None:
        return []
    return [verb for verb in "".join(match.group(1).split()).split(",") if verb]


def render(values):
    """One rendering for every side of every message: a list, or ``(none)``."""
    if isinstance(values, dict):
        values = ["%s=%s" % (key, values[key]) for key in sorted(values)]
    listed = [str(value) for value in values]
    return ", ".join(listed) if listed else "(none)"


class Report:
    """The tally. Violations are ``1``; an observable that scanned nothing is ``2``.

    Every violation goes through :meth:`violation` so all of them read the same:
    the observable, what differs, and both sides.
    """

    def __init__(self):
        self.violations = []
        self.vacuous = []
        self.checked = []

    def violation(self, observable, difference, left_label, left, right_label, right):
        self.violations.append(
            "%s: %s (%s: %s | %s: %s)"
            % (observable, difference, left_label, render(left), right_label, render(right))
        )

    def nothing_checked(self, observable, looked_for):
        self.vacuous.append(
            "%s: scanned nothing; looked for %s" % (observable, looked_for)
        )

    def ok(self, observable, count, noun):
        self.checked.append("%s (%d %s)" % (observable, count, noun))


def check_verbs(root, documents, report):
    """The one VERBS region against the subcommands the tool registers."""
    observable = "verbs"
    carrier, body = one_home(documents, "VERBS", observable, report)
    markers = "a <!-- VERBS:BEGIN --> / <!-- VERBS:END --> region in %s" % (
        carrier or "one of the documented set"
    )
    documented = [row[0] for row in table_rows(body, VERB_ROW_RE)]
    if not documented:
        report.nothing_checked(observable, markers)
        return
    registered = registered_verbs(root)
    if not registered:
        report.nothing_checked(observable, "`crayon --help`'s subcommand list")
        return
    for verb in registered:
        if verb not in documented:
            report.violation(
                observable,
                "`%s` is registered by the tool and has no row" % verb,
                "documented",
                documented,
                "registered",
                registered,
            )
    for verb in documented:
        if verb not in registered:
            report.violation(
                observable,
                "`%s` has a row and the tool does not register it" % verb,
                "documented",
                documented,
                "registered",
                registered,
            )
    report.ok(observable, len(documented), "rows")


def _compare_reasons(report, side, documented, tool):
    for name in sorted(tool):
        if name not in documented:
            report.violation(
                "reasons",
                "`%s` is in the tool and has no row in %s" % (name, side),
                side,
                sorted(documented),
                "crayon.REASONS",
                sorted(tool),
            )
    for name in sorted(documented):
        if name not in tool:
            report.violation(
                "reasons",
                "`%s` has a row in %s and the tool does not raise it" % (name, side),
                side,
                sorted(documented),
                "crayon.REASONS",
                sorted(tool),
            )
        elif documented[name] != tool[name]:
            report.violation(
                "reasons",
                "`%s` is exit %s in %s and exit %s in the tool"
                % (name, documented[name], side, tool[name]),
                side,
                ["%s=%s" % (name, documented[name])],
                "crayon.REASONS",
                ["%s=%s" % (name, tool[name])],
            )


def check_reasons(documents, contract, tool_reasons, report):
    """Both documented reason tables against ``crayon.REASONS``, name and code."""
    observable = "reasons"
    if not tool_reasons:
        report.nothing_checked(observable, "the tool's REASONS table")
        return
    carrier, body = one_home(documents, "REASONS", observable, report)
    compact_rows = compact_reason_rows(body)
    if not compact_rows:
        report.nothing_checked(
            observable,
            "a <!-- REASONS:BEGIN --> / <!-- REASONS:END --> region in %s"
            % (carrier or "one of the documented set"),
        )
    else:
        _compare_reasons(
            report,
            carrier,
            dict((name, int(code)) for name, code in compact_rows),
            tool_reasons,
        )
        report.ok("reasons (%s)" % carrier, len(compact_rows), "rows")
    contract_rows = table_rows(anchored_slice(contract, REASON_TABLE_ANCHOR), REASON_ROW_RE)
    if not contract_rows:
        report.nothing_checked(
            observable,
            "docs/contract.md's %r anchor in section 5.7" % REASON_TABLE_ANCHOR,
        )
        return
    _compare_reasons(
        report,
        "docs/contract.md",
        dict((name, int(code)) for name, code in contract_rows),
        tool_reasons,
    )
    report.ok("reasons (docs/contract.md)", len(contract_rows), "rows")


def _compare_compat(report, side, documented, expected):
    for number in sorted(expected):
        stated = documented.get(number)
        if stated is None:
            report.violation(
                "compatibility",
                "`%s` has no row in %s" % (number, side),
                side,
                documented,
                "the tool",
                expected,
            )
        elif stated != expected[number]:
            # String equality, never a version parse: contract section 5.10 says
            # the two numbers are compared as literal strings, and a skill that
            # reads `0.2` where the tool says `0.2.0` stops. A check that
            # normalised them would pass a tree the runtime refuses (T-18-33).
            report.violation(
                "compatibility",
                "`%s` reads `%s` in %s and `%s` in the tool"
                % (number, stated, side, expected[number]),
                side,
                ["%s=%s" % (number, stated)],
                "the tool",
                ["%s=%s" % (number, expected[number])],
            )


def check_compat(documents, contract, expected, report):
    """The one COMPAT region in the documented set, and contract 5.10, against the tool."""
    observable = "compatibility"
    carrier, body = one_home(documents, "COMPAT", observable, report)
    doc_rows = table_rows(body, COMPAT_ROW_RE)
    if not doc_rows:
        report.nothing_checked(
            observable,
            "a <!-- COMPAT:BEGIN --> / <!-- COMPAT:END --> region in one of the "
            "documented set",
        )
    else:
        _compare_compat(report, carrier, dict(doc_rows), expected)
        report.ok("compatibility (%s)" % carrier, len(doc_rows), "numbers")
    contract_rows = table_rows(heading_section(contract, COMPAT_HEADING), COMPAT_ROW_RE)
    if not contract_rows:
        report.nothing_checked(
            observable, "docs/contract.md's `%s` heading" % COMPAT_HEADING
        )
        return
    _compare_compat(report, "docs/contract.md", dict(contract_rows), expected)
    report.ok("compatibility (docs/contract.md)", len(contract_rows), "numbers")


def _check_one_link(root, relative, source, target, report):
    """One link: inside the repository, then present, then anchored at a heading."""
    observable = "links"
    path_part, _, anchor = target.partition("#")
    destination = source if not path_part else (source.parent / path_part)
    try:
        destination = destination.resolve()
    except OSError:
        destination = None
    inside = destination is not None and (
        destination == root or root in destination.parents
    )
    if not inside:
        # Reported, never opened for writing: this file is read-only by
        # construction, so a traversal in a document is a finding here rather
        # than a reach outside the tree (T-18-32).
        report.violation(
            observable,
            "`%s` in %s leaves the repository" % (target, relative),
            "source",
            [relative],
            "resolved",
            [str(destination)],
        )
        return
    if not destination.exists():
        report.violation(
            observable,
            "`%s` in %s resolves to no file" % (target, relative),
            "source",
            [relative],
            "resolved",
            [str(destination.relative_to(root))],
        )
        return
    if not anchor or destination.suffix != ".md":
        return
    anchors = file_anchors(destination)
    if anchor not in anchors:
        report.violation(
            observable,
            "`#%s` in %s is no heading in %s"
            % (anchor, relative, path_part or relative),
            "wanted",
            [anchor],
            "offered",
            sorted(anchors),
        )


def check_links(root, documents, report):
    """Every in-repo link in the documented set: the path, then the anchor."""
    observable = "links"
    root = root.resolve()
    resolved = 0
    for relative, text in sorted(documents.items()):
        source = root / relative
        for target in LINK_RE.findall(text):
            if "://" in target or target.startswith("mailto:"):
                # Out of scope by construction: nothing outside this repository
                # is opened or reached, so an outage elsewhere cannot turn this
                # gate red (D-11, T-18-31).
                continue
            resolved += 1
            _check_one_link(root, relative, source, target, report)
    if not resolved:
        report.nothing_checked(
            observable,
            "in-repo markdown links across %s" % ", ".join(sorted(documents)),
        )
        return
    report.ok(observable, resolved, "in-repo links")


def user_facing_lines(text):
    """``(line number, line)`` for every line outside an under-the-hood section.

    A section runs from its ``## `` heading to the next one, so a ``### ``
    subsection inside ``## Under the hood`` stays inside it.
    """
    inside = False
    for number, line in enumerate(text.splitlines(), 1):
        if _SECTION_RE.match(line):
            inside = line.strip() == UNDER_THE_HOOD_HEADING
        if not inside:
            yield number, line


def check_skills_first(root, documents, report):
    """No ``crayon <verb>`` in a reader-facing document outside an under-the-hood section."""
    observable = "skills-first"
    verbs = registered_verbs(root)
    if not verbs:
        report.nothing_checked(observable, "`crayon --help`'s subcommand list")
        return
    # Longest first, so `plan-steps` is never read as a shorter verb.
    alternatives = "|".join(re.escape(verb) for verb in sorted(verbs, key=len, reverse=True))
    command = re.compile(r"\bcrayon[ \t]+(?:%s)\b" % alternatives)
    scanned = []
    for relative in SKILLS_FIRST_DOCS:
        text = documents.get(relative)
        if text is None:
            continue
        scanned.append(relative)
        for number, line in user_facing_lines(text):
            for match in command.finditer(line):
                report.violation(
                    observable,
                    "`%s` at %s:%d is outside a `%s` section"
                    % (match.group(0), relative, number, UNDER_THE_HOOD_HEADING),
                    "found",
                    [match.group(0)],
                    "allowed",
                    ["skill names; tool commands only under `%s`" % UNDER_THE_HOOD_HEADING],
                )
    if not scanned:
        report.nothing_checked(observable, ", ".join(SKILLS_FIRST_DOCS))
        return
    report.ok(observable, len(scanned), "reader-facing documents")


def check_release_record(changelog, report):
    """REL-02 / CI-03: the released section is dated and carries no unfilled slot.

    The topmost ``## [x.y.z]`` heading is the section the tag is cut against and
    the one a reader diffs the tag against. Two things are asserted about it and
    nothing wider: that it carries a date, and that no marker in
    :data:`RELEASE_PLACEHOLDERS` survives in its body. Nothing here reads the
    section's prose — an entry can be wrong in every word and this stays green,
    exactly as the four table observables do.

    A changelog with no versioned heading at all is a ``2``, never a ``0``: an
    absent, empty or unreleased-only file has no released section, so reporting
    it clean would say the released section carries no marker about a section
    that does not exist. The FIRST match in document order is the released one,
    which makes "the released section" specified rather than incidental.
    """
    observable = "release record"
    headings = list(RELEASED_HEADING_RE.finditer(changelog))
    if not headings:
        report.nothing_checked(observable, "a `## [x.y.z]` heading in CHANGELOG.md")
        return
    heading = headings[0]
    fired = False
    if heading.group(2) is None:
        report.violation(
            observable,
            "the topmost released heading carries no date",
            "required",
            ["## [%s] - YYYY-MM-DD" % heading.group(1)],
            "found",
            [heading.group(0).strip()],
        )
        fired = True
    # The section body, to the next `## ` heading or the end of the file — the
    # same line-wise idiom `heading_section` uses, so an older release below and
    # `[Unreleased]` above are both outside the slice.
    body_lines = []
    for line in changelog[heading.end() :].splitlines():
        if _SECTION_RE.match(line):
            break
        body_lines.append(line)
    body = "\n".join(body_lines)
    for marker in RELEASE_PLACEHOLDERS:
        if marker in body:
            report.violation(
                observable,
                "the topmost released section still carries an unfilled-slot marker",
                "required",
                ["a released section carrying none of them"],
                "found",
                [marker],
            )
            fired = True
    if not fired:
        report.ok(observable, 1, "released section")


def check_traces(root, report):
    """Delegate the trace table to its one parser (17 D-09).

    ``tests/check_traces.py`` reads the trace table and this file does not, so
    there is exactly one reader of that table in the repository and a change to
    its shape has one place to break. Its output is printed rather than
    swallowed: the delegation must be visible in the report, not inferred.
    """
    observable = "traces"
    delegate = root / "tests" / "check_traces.py"
    if not delegate.is_file():
        report.nothing_checked(observable, "%s" % delegate)
        return
    code = load_module("check_traces", delegate).main()
    sys.stdout.flush()
    if code == 1:
        report.violation(
            observable,
            "tests/check_traces.py reported a violation (its lines are above)",
            "delegate",
            ["tests/check_traces.py"],
            "exit",
            [code],
        )
    elif code != 0:
        report.nothing_checked(observable, "tests/check_traces.py (it returned 2)")
    else:
        report.ok(observable, 1, "delegate")


def read_documents(root):
    """``{relative path: text}`` for every document present, with a note for the rest."""
    documents = {}
    for relative in DOC_FILES:
        path = root / relative
        try:
            documents[relative] = path.read_text(encoding="utf-8")
        except OSError:
            print("check-docs: note - %s is absent, skipped" % relative)
    return documents


def run_checks(root, documents, tool, report):
    """Every observable, in one place, against one tool and one documented set."""
    contract = documents.get("docs/contract.md", "")
    check_verbs(root, documents, report)
    check_reasons(documents, contract, dict(getattr(tool, "REASONS", {})), report)
    check_compat(
        documents,
        contract,
        {
            "contract": str(getattr(tool, "CONTRACT", "")),
            "min_tool": str(getattr(tool, "__version__", "")),
        },
        report,
    )
    check_links(root, documents, report)
    check_skills_first(root, documents, report)
    check_release_record(documents.get("CHANGELOG.md", ""), report)
    check_traces(root, report)


def conclude(report):
    """Print the tally and return the exit code the contract assigns it.

    Violations outrank a vacuous observable: a tree with both has a named
    disagreement to fix first, and reporting 2 would bury it.
    """
    if report.checked:
        print("check-docs: checked %s" % "; ".join(report.checked))
    sys.stdout.flush()
    if report.violations:
        print(
            "check-docs: VIOLATION(S) - %d:" % len(report.violations),
            *report.violations,
            sep="\n  ",
            file=sys.stderr
        )
        return 1
    if report.vacuous:
        print(
            "check-docs: ERROR - %d observable(s) scanned nothing:"
            % len(report.vacuous),
            *report.vacuous,
            sep="\n  ",
            file=sys.stderr
        )
        return 2
    print("check-docs: OK - the documented set agrees with the tool")
    return 0


def main(argv=None):
    """Check the documented set against the tool.

    Returns
    -------
    int
        ``0`` when every observable was checked and agreed, ``1`` when any
        observable disagreed (one line each, naming the observable, the
        difference and both sides), and ``2`` when an observable scanned
        nothing — printed with the region or heading it looked for, so a
        renamed marker or a reshaped table can never read as a clean run.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root to check (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    root = args.root

    report = Report()
    documents = read_documents(root)

    try:
        tool = load_module("crayon", root / "crayon.py")
    except Exception as bad:  # noqa: BLE001 - reported, never swallowed
        print(
            "check-docs: ERROR - the tool at %s could not be read (%s)"
            % (root / "crayon.py", type(bad).__name__),
            file=sys.stderr,
        )
        return 2

    run_checks(root, documents, tool, report)
    return conclude(report)


if __name__ == "__main__":
    raise SystemExit(main())
