"""The executable contract for ``tests/check_docs.py``, the docs-accuracy checker.

Every case builds its own fixture tree in a temp directory and points the
checker's ``--root`` at it, so the suite never reads the real documents except
in the one test that asserts the real tree is clean. The fixture tree carries a
fixture ``dogen`` — a real ``argparse`` program with three subcommands and its
own ``REASONS``, ``CONTRACT`` and ``__version__`` — because the checker's oracle
is whatever tool sits at its root, not a hard-coded list (T-18-30).

Two things are asserted about every violation, not one: the return code **and**
the message text. A checker that returns 1 without naming what it compared is
the failure mode ``tests/check_traces.py``'s "name what was grepped" rule exists
against, and it would pass a code-only assertion.

Mirrors ``tests/test_planning_lint.py``: stdlib ``unittest``, Python 3.9 syntax,
no third-party runner on this branch.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tests" / "check_docs.py"
TRACE_CHECKER = ROOT / "tests" / "check_traces.py"


def _load_check_docs():
    """Import ``tests/check_docs.py`` without putting ``tests/`` on the path.

    ``sys.path.insert`` would shadow any stdlib module sharing a name with a
    file in ``tests/`` for the whole process, and this module runs in the same
    interpreter as every other suite under ``python3 -m unittest``.

    A load failure is returned rather than raised. Raising here aborts
    collection, and a suite that cannot be collected reports zero tests — which
    reads as "nothing to run" to every runner and to the TDD gate alike. Every
    case below then fails on :meth:`CheckDocsCase.setUp`'s named assertion
    instead, so the report says which file is missing and how many contracts
    are unhonoured.
    """
    loader = importlib.machinery.SourceFileLoader("check_docs", str(CHECKER))
    spec = importlib.util.spec_from_loader("check_docs", loader)
    module = importlib.util.module_from_spec(spec)
    try:
        loader.exec_module(module)
    except Exception as bad:  # noqa: BLE001 - reported, not swallowed
        return None, "tests/check_docs.py could not be loaded: %s: %s" % (
            type(bad).__name__,
            bad,
        )
    return module, None


check_docs, LOAD_ERROR = _load_check_docs()

#: The fixture tool's surfaces. Deliberately unlike the real tool's, so a
#: checker that quietly fell back to the repository's own dogen would fail
#: every case here instead of passing by coincidence.
FIXTURE_VERBS = ("alpha", "beta", "gamma")
FIXTURE_REASONS = (("alpha_gate", 1), ("beta_bad", 2), ("gamma_busy", 5))
FIXTURE_CONTRACT = "7"
FIXTURE_VERSION = "9.9.9"

FIXTURE_TOOL = '''#!/usr/bin/env python3
"""A fixture stand-in for the repo-root tool: three verbs and three reasons."""

import argparse

__version__ = "9.9.9"
CONTRACT = 7
REASONS = {"alpha_gate": 1, "beta_bad": 2, "gamma_busy": 5}


def main():
    parser = argparse.ArgumentParser(prog="dogen", description="fixture tool")
    sub = parser.add_subparsers(dest="verb")
    for verb in ("alpha", "beta", "gamma"):
        sub.add_parser(verb, help="fixture verb")
    parser.parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

#: The claims the CLAIMS region must carry, mirroring the three statements
#: ``check_docs.REQUIRED_CLAIMS`` still requires after phase 19 — the
#: fixture-hooks reading, the unnamed supported configurations, and the
#: grounding the actionable walk did not establish — worded as the real README
#: words them. The two originals left when real sessions discharged them; the
#: checker's own comment records why, and this fixture follows it rather than
#: keeping a region the checker no longer accepts.
#:
#: Each sentence carries its own NEGATION (19 WR-05), which is what the keys are
#: matched on: ``not a repository's own configured hooks``, ``are unproven``,
#: ``did not prove the loop``. The inversion cases below flip exactly one of
#: them and assert the checker notices, which is the whole job of this boundary.
FIXTURE_CLAIMS = (
    "- **They ran against fixture hooks, not a repository's own configured "
    "hooks.** The hook shapes came from the test fixtures.\n"
    "- **Supported configurations are unproven, and none is listed.** No "
    "install session was run for this release.\n"
    "- **The walk did not prove the loop produces a how-to grounded in observed "
    "command behaviour.** Three of its four steps resolved skipped.\n"
)

#: The Mechanisms rows the fixture tree's contract carries (19 D-12). Their
#: signal cells use the real table's ``id (`suite file`)`` shape, because that
#: parenthetical is exactly what scopes the delegate's widened scan. There are
#: two, as in the real table, so a case that drops one parenthetical still
#: leaves the scan non-empty — which is the only way to reach the delegate's
#: gated-suite guard rather than its bare zero-scanned one.
DEFAULT_MECHANISM_ROWS = (
    (
        "`verify` (read-only)",
        "a fixture journey",
        "a fixture experience",
        "one fixture mechanism",
        "V-01 (`validation/fixtures.sh`)",
    ),
    (
        "`retire`",
        "another fixture journey",
        "another fixture experience",
        "another fixture mechanism",
        "N-01 (`tests/test_dogen_unit.py`)",
    ),
)

DEFAULT_LINKS = (
    ("the contract", "docs/contract.md"),
    ("compatibility", "docs/contract.md#510-compatibility"),
    ("the upgrade note", "docs/upgrade.md"),
)

#: The fixture release record, shaped so the default tree PASSES the release
#: observable: an ``## [Unreleased]`` section with a body, then a topmost
#: released heading that carries its ISO date and a body with no unfilled-slot
#: marker in it. The earlier fixture was the bare ``"# Changelog\n\n## [0.0.0]\n"``,
#: which carries no date — wiring the observable in would have turned every
#: existing case into a violation over a mutation none of them made.
DEFAULT_CHANGELOG = (
    "# Changelog\n"
    "\n"
    "## [Unreleased]\n"
    "\n"
    "Nothing unreleased. Stated rather than omitted.\n"
    "\n"
    "## [0.0.0] - 2020-01-01\n"
    "\n"
    "The fixture release.\n"
)


def _table(header, rows):
    lines = ["| %s |" % " | ".join(header), "|%s|" % "|".join(["---"] * len(header))]
    for row in rows:
        lines.append("| %s |" % " | ".join(row))
    return "\n".join(lines) + "\n"


def _region(name, body):
    return "<!-- %s:BEGIN -->\n\n%s\n<!-- %s:END -->\n" % (name, body, name)


def build_tree(
    root,
    verb_rows=None,
    reason_rows=None,
    compat=None,
    claims=True,
    links=DEFAULT_LINKS,
    contract_reason_rows=None,
    contract_compat=None,
    mechanism_rows=None,
    v01_suite="validation/fixtures.sh",
    changelog=None,
):
    """Write a minimal but complete documented set under ``root``.

    Every knob defaults to the shape the fixture tool agrees with, so a test
    mutates exactly one thing and the rest of the tree stays clean.
    """
    root = Path(root)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)

    (root / "dogen").write_text(FIXTURE_TOOL, encoding="utf-8")

    if verb_rows is None:
        verb_rows = [(("`%s`" % verb), "does %s" % verb) for verb in FIXTURE_VERBS]
    if reason_rows is None:
        reason_rows = [("`%s`" % name, str(code)) for name, code in FIXTURE_REASONS]
    if contract_reason_rows is None:
        contract_reason_rows = [
            ("`%s`" % name, str(code)) for name, code in FIXTURE_REASONS
        ]
    if compat is None:
        compat = (FIXTURE_CONTRACT, FIXTURE_VERSION)
    if contract_compat is None:
        contract_compat = (FIXTURE_CONTRACT, FIXTURE_VERSION)

    verbs_body = _table(("Verb", "What it records"), verb_rows) if verb_rows else ""
    compat_body = _table(
        ("Number", "Value"),
        (("`contract`", "`%s`" % compat[0]), ("`min_tool`", "`%s`" % compat[1])),
    )
    readme = [
        "# Fixture\n",
        _region("VERBS", verbs_body),
        _region("REASONS", _table(("Reason", "Exit"), reason_rows)),
        _region("COMPAT", compat_body),
    ]
    # `claims` is False (omit the region), True (the honest fixture text) or a
    # string body of the caller's own — the last is how an INVERTED claim is
    # spelled without restating the other two.
    if claims:
        readme.append(
            _region(
                "CLAIMS", claims if isinstance(claims, str) else FIXTURE_CLAIMS
            )
        )
    readme.append(
        "".join("See [%s](%s).\n" % (text, target) for text, target in links)
    )
    (root / "README.md").write_text("\n".join(readme), encoding="utf-8")

    contract = [
        "# Fixture contract\n",
        "## 5.7 Verb order, per-verb preconditions, refusals\n",
        "Reason table:\n",
        _table(("Reason", "Exit"), contract_reason_rows),
        "## 5.10 Compatibility\n",
        _table(
            ("Number", "Value"),
            (
                ("`contract`", "`%s`" % contract_compat[0]),
                ("`min_tool`", "`%s`" % contract_compat[1]),
            ),
        ),
        # 19 D-12: the delegate also scans the Mechanisms table, and a tree
        # where it scans zero rows is a vacuous pass it reports as exit 2. The
        # fixture therefore carries the same five-cell shape the real table has,
        # with one row whose signal cell names a suite file — the shape the
        # widened scan is scoped to.
        "## Mechanisms\n",
        _table(
            (
                "Mechanism",
                "Failure / journey protected",
                "What the author experiences",
                "Simplest adequate mechanism",
                "Signal (how we know it helped)",
            ),
            (mechanism_rows if mechanism_rows is not None else DEFAULT_MECHANISM_ROWS),
        ),
        "## Trace table\n",
        _table(("Trace", "Governing rule", "Test"), (("T1", "a fixture rule", "N-01"),)),
    ]
    (root / "docs" / "contract.md").write_text("\n".join(contract), encoding="utf-8")

    (root / "AGENTS.md").write_text("# Fixture agents\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        DEFAULT_CHANGELOG if changelog is None else changelog, encoding="utf-8"
    )
    (root / "docs" / "upgrade.md").write_text("# Upgrade\n", encoding="utf-8")
    (root / "skills" / "README.md").write_text("# Skills\n", encoding="utf-8")
    for skill in ("dogen-plan", "dogen-review", "dogen-write"):
        (root / "skills" / skill).mkdir(parents=True, exist_ok=True)
        (root / "skills" / skill / "SKILL.md").write_text(
            "# %s\n" % skill, encoding="utf-8"
        )

    # The trace observable is a delegation, so the fixture carries the real
    # delegate and a table it can clear (17 D-09). A fixture without it would
    # exercise the "delegate absent" arm in every case instead of the one.
    shutil.copy(str(TRACE_CHECKER), str(root / "tests" / "check_traces.py"))
    # The delegate's Mechanisms pass greps the same suite files, so the fixture
    # carries the one the fixture table's row names. `v01_suite` decides WHICH
    # file the `verify` row's `test_v01_*` is written into (19 WR-04): the row
    # points at `validation/fixtures.sh`, and a token satisfying it from some
    # other suite is the defect — the row says where, so the check has to read
    # where.
    unit_body = ["def test_n01_the_fixture_row_is_cleared():\n    pass\n"]
    fixtures_body = ["test_a_fixture_carrying_no_row_id() {\n  :\n}\n"]
    if v01_suite == "tests/test_dogen_unit.py":
        unit_body.append("def test_v01_the_fixture_row_is_cleared():\n    pass\n")
    else:
        fixtures_body.append("test_v01_the_fixture_row_is_cleared() {\n  :\n}\n")
    (root / "tests" / "test_dogen_unit.py").write_text(
        "".join(unit_body), encoding="utf-8"
    )
    (root / "validation").mkdir(parents=True, exist_ok=True)
    (root / "validation" / "fixtures.sh").write_text(
        "".join(fixtures_body), encoding="utf-8"
    )
    return root


class CheckDocsCase(unittest.TestCase):
    """Shared fixture-tree plumbing: one temp root per test, torn down after."""

    def setUp(self):
        if check_docs is None:
            self.fail(LOAD_ERROR)
        self.tmp = Path(tempfile.mkdtemp(prefix="check-docs-"))

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def tree(self, **kwargs):
        return build_tree(self.tmp / "tree", **kwargs)

    def run_checker(self, root):
        """``(exit code, everything it printed)`` — both streams, one string."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check_docs.main(["--root", str(root)])
        return code, out.getvalue() + err.getvalue()


class TestCleanTree(CheckDocsCase):
    """The 0 arm, on a fixture tree and on the repository itself."""

    def test_a_consistent_fixture_tree_is_clean(self):
        code, output = self.run_checker(self.tree())
        self.assertEqual(code, 0, output)

    def test_the_real_repository_tree_is_clean(self):
        """The documents in this checkout agree with this checkout's tool."""
        code, output = self.run_checker(ROOT)
        self.assertEqual(code, 0, output)


class TestVerbs(CheckDocsCase):
    """`dogen --help`'s subcommands are the oracle, in both directions."""

    def test_a_registered_verb_with_no_row_is_a_violation(self):
        rows = [("`%s`" % verb, "does it") for verb in ("alpha", "beta")]
        code, output = self.run_checker(self.tree(verb_rows=rows))
        self.assertEqual(code, 1, output)
        self.assertIn("gamma", output)
        self.assertIn("verbs", output)

    def test_a_documented_verb_the_tool_lacks_is_a_violation(self):
        rows = [("`%s`" % verb, "does it") for verb in FIXTURE_VERBS + ("delta",)]
        code, output = self.run_checker(self.tree(verb_rows=rows))
        self.assertEqual(code, 1, output)
        self.assertIn("delta", output)

    def test_an_empty_verbs_region_is_a_two_naming_the_markers(self):
        """An empty region scanned nothing; that is 2, and it says where it looked."""
        code, output = self.run_checker(self.tree(verb_rows=[]))
        self.assertEqual(code, 2, output)
        self.assertIn("VERBS:BEGIN", output)
        self.assertIn("VERBS:END", output)


class TestReasons(CheckDocsCase):
    """Name and exit code, on both the README side and the contract side."""

    def test_a_wrong_exit_code_in_the_readme_names_both_codes(self):
        rows = [("`alpha_gate`", "1"), ("`beta_bad`", "4"), ("`gamma_busy`", "5")]
        code, output = self.run_checker(self.tree(reason_rows=rows))
        self.assertEqual(code, 1, output)
        self.assertIn("beta_bad", output)
        self.assertIn("4", output)
        self.assertIn("2", output)

    def test_a_reason_missing_from_the_contract_table_is_a_violation(self):
        rows = [("`alpha_gate`", "1"), ("`beta_bad`", "2")]
        code, output = self.run_checker(self.tree(contract_reason_rows=rows))
        self.assertEqual(code, 1, output)
        self.assertIn("gamma_busy", output)

    def test_an_empty_reasons_region_is_a_two(self):
        code, output = self.run_checker(self.tree(reason_rows=[]))
        self.assertEqual(code, 2, output)
        self.assertIn("REASONS:BEGIN", output)


class TestCompatibility(CheckDocsCase):
    """Contract section 5.10: literal strings, never parsed as versions."""

    def test_a_different_min_tool_string_is_a_violation(self):
        code, output = self.run_checker(
            self.tree(compat=(FIXTURE_CONTRACT, "1.2.3"))
        )
        self.assertEqual(code, 1, output)
        self.assertIn("min_tool", output)
        self.assertIn("1.2.3", output)

    def test_an_equivalent_but_differently_written_version_is_a_violation(self):
        """`9.9` is the same version as `9.9.9` to a parser and not to this check.

        Contract section 5.10 says the two numbers are compared as literal
        strings; a check that normalised them would pass this tree, and a skill
        comparing the strings at runtime would still stop (T-18-33).
        """
        code, output = self.run_checker(self.tree(compat=(FIXTURE_CONTRACT, "9.9")))
        self.assertEqual(code, 1, output)
        self.assertIn("min_tool", output)

    def test_a_contract_side_compat_mismatch_is_a_violation(self):
        code, output = self.run_checker(
            self.tree(contract_compat=("8", FIXTURE_VERSION))
        )
        self.assertEqual(code, 1, output)
        self.assertIn("contract", output)
        self.assertIn("8", output)


class TestLinks(CheckDocsCase):
    """In-repo resolution only: a path that exists, an anchor that is a heading."""

    def test_a_link_to_a_missing_path_names_the_link_and_its_source(self):
        links = DEFAULT_LINKS + (("gone", "docs/nowhere.md"),)
        code, output = self.run_checker(self.tree(links=links))
        self.assertEqual(code, 1, output)
        self.assertIn("docs/nowhere.md", output)
        self.assertIn("README.md", output)

    def test_a_link_to_an_unknown_anchor_names_the_anchor(self):
        links = DEFAULT_LINKS + (("nope", "docs/contract.md#no-such-heading"),)
        code, output = self.run_checker(self.tree(links=links))
        self.assertEqual(code, 1, output)
        self.assertIn("no-such-heading", output)

    def test_a_documented_set_with_no_links_at_all_is_a_two(self):
        code, output = self.run_checker(self.tree(links=()))
        self.assertEqual(code, 2, output)
        self.assertIn("links", output)


class TestClaimsBoundary(CheckDocsCase):
    """REL-01: the release states what it has not proved, or it does not ship."""

    def test_an_absent_claims_region_is_a_violation_not_a_two(self):
        """The region's absence is the finding, so it is 1 and never 2."""
        code, output = self.run_checker(self.tree(claims=False))
        self.assertEqual(code, 1, output)
        self.assertIn("CLAIMS", output)

    def test_inverting_the_hooks_boundary_is_caught(self):
        """19 WR-05: the key has to carry the claim's POLARITY.

        ``a repository's own configured hooks`` is present in the inverted
        sentence as well as in the honest one, so the boundary could be erased
        by the exact edit this check exists to notice. The fixture performs that
        edit — "not a repository's own configured hooks" becomes "a repository's
        own configured hooks" — and changes nothing else.
        """
        inverted = FIXTURE_CLAIMS.replace(
            "fixture hooks, not a repository's own configured hooks",
            "a repository's own configured hooks",
        )
        self.assertNotEqual(inverted, FIXTURE_CLAIMS)
        code, output = self.run_checker(self.tree(claims=inverted))
        self.assertEqual(code, 1, output)
        self.assertIn("not a repository's own configured hooks", output)

    def test_inverting_the_actionable_walk_boundary_is_caught(self):
        """The same, for the grounding the walk did NOT establish.

        ``grounded in observed command behaviour`` survives "The walk **proved**
        the loop produces a how-to grounded in observed command behaviour",
        which is the release claiming the opposite of the boundary. The key is
        ``did not prove the loop``, which does not.
        """
        inverted = FIXTURE_CLAIMS.replace(
            "The walk did not prove the loop produces",
            "The walk proved the loop produces",
        )
        self.assertNotEqual(inverted, FIXTURE_CLAIMS)
        code, output = self.run_checker(self.tree(claims=inverted))
        self.assertEqual(code, 1, output)
        self.assertIn("did not prove the loop", output)

    def test_the_honest_region_still_clears_all_three(self):
        """The other direction, so the two cases above cannot pass by refusing
        every region: the unedited fixture text satisfies all three keys."""
        code, output = self.run_checker(self.tree())
        self.assertEqual(code, 0, output)
        self.assertIn("claims (3 statements)", output)


class TestReleaseRecord(CheckDocsCase):
    """REL-02 / CI-03: the topmost released section is dated and carries no slot.

    The section the tag is cut against is the one a reader diffs the tag
    against. Before this observable existed, ``CHANGELOG.md`` was read by this
    checker for link resolution only, so a released section could ship undated
    and carrying an explicitly unfilled slot and every gate stayed green — the
    "silently green" shape the rest of this phase's infrastructure was built
    against.
    """

    def test_an_undated_released_heading_is_a_violation(self):
        """A released heading with no date is 1, and it names the observable.

        Not a 2: the heading was found and read, and what it says disagrees
        with the format the file's own preamble declares. Routing it to the
        vacuous arm would report "scanned nothing" about something scanned.
        """
        undated = DEFAULT_CHANGELOG.replace("## [0.0.0] - 2020-01-01", "## [0.0.0]")
        self.assertNotEqual(undated, DEFAULT_CHANGELOG)
        code, output = self.run_checker(self.tree(changelog=undated))
        self.assertEqual(code, 1, output)
        self.assertIn("release record", output)
        self.assertIn("## [0.0.0]", output)

    def test_every_release_placeholder_marker_is_a_violation(self):
        """Each marker in ``RELEASE_PLACEHOLDERS``, one subTest per entry.

        Keyed on the tuple rather than on a written-out list, so a marker added
        to the checker later is covered here without a new case — and a marker
        added there and never enforced fails this test instead of passing
        quietly.
        """
        self.assertTrue(check_docs.RELEASE_PLACEHOLDERS)
        for marker in check_docs.RELEASE_PLACEHOLDERS:
            with self.subTest(marker=marker):
                mutated = DEFAULT_CHANGELOG.replace(
                    "The fixture release.",
                    "The fixture release, and %s." % marker,
                )
                self.assertNotEqual(mutated, DEFAULT_CHANGELOG)
                code, output = self.run_checker(self.tree(changelog=mutated))
                self.assertEqual(code, 1, output)
                self.assertIn("release record", output)
                self.assertIn(marker, output)

    def test_a_changelog_with_no_versioned_heading_is_a_two(self):
        """The vacuous-pass guard: nothing to scan is 2, never 0.

        An absent, empty or unreleased-only changelog has no released section,
        so there is nothing for the markers to be absent from. Reporting 0
        would say the released section is clean about a section that does not
        exist — exactly the shape the 0/1/2 contract exists against.
        """
        code, output = self.run_checker(
            self.tree(changelog="# Changelog\n\n## [Unreleased]\n\nNothing yet.\n")
        )
        self.assertEqual(code, 2, output)
        self.assertIn("release record", output)
        self.assertIn("## [x.y.z]", output)
        self.assertIn("CHANGELOG.md", output)

    def test_a_marker_outside_the_topmost_released_section_is_not_a_violation(self):
        """REL-02's adjacency and ordering edges, in one tree.

        ``## [Unreleased]`` sits directly above the released heading and an
        older release sits directly below it. The observable is about the
        section the tag is cut against: a marker in either neighbour is not a
        finding, and mistaking ``[Unreleased]`` for the released section is the
        failure ``RELEASED_HEADING_RE``'s semantic-version requirement prevents.
        """
        marker = check_docs.RELEASE_PLACEHOLDERS[0]
        noisy_neighbours = (
            "# Changelog\n"
            "\n"
            "## [Unreleased]\n"
            "\n"
            "Nothing unreleased, and %s.\n"
            "\n"
            "## [0.0.0] - 2020-01-01\n"
            "\n"
            "The fixture release.\n"
            "\n"
            "## [0.0.1] - 2019-01-01\n"
            "\n"
            "An older fixture release, and %s.\n"
        ) % (marker, marker)
        code, output = self.run_checker(self.tree(changelog=noisy_neighbours))
        self.assertEqual(code, 0, output)
        self.assertIn("release record", output)

    def test_the_real_repository_tree_is_clean_on_the_release_record(self):
        """This checkout's own ``CHANGELOG.md``, not a fixture.

        The other direction, so the four cases above cannot pass by refusing
        every tree: the repository's released section is dated and carries no
        marker, and the observable reports it as checked.
        """
        code, output = self.run_checker(ROOT)
        self.assertEqual(code, 0, output)
        self.assertIn("release record", output)


class TestTraceDelegation(CheckDocsCase):
    """19 D-12 / T-19-26: the delegate's second vacuous-pass guard, seen from here."""

    def test_a_mechanisms_row_that_names_no_suite_file_is_a_two(self):
        """Dropping the parenthetical unchecks the link and must not read clean.

        The signal cell's ``(`validation/fixtures.sh`)`` is what scopes the
        widened Mechanisms scan; without it the row is reported as not scanned,
        no scanned row names the gated suite, and `tests/check_traces.py`
        returns 2 — even though the other parenthetical row keeps the scan
        non-empty, which a bare zero-scanned count would miss. `check_docs`
        folds that into its nothing-checked arm rather than into a violation, so
        the report says the traces observable checked nothing — never that the
        tree is clean.
        """
        rows = tuple(
            row[:-1] + (row[-1].split("(")[0].strip(),)
            if "validation/fixtures.sh" in row[-1]
            else row
            for row in DEFAULT_MECHANISM_ROWS
        )
        code, output = self.run_checker(self.tree(mechanism_rows=rows))
        self.assertEqual(code, 2, output)
        self.assertIn("traces", output)
        self.assertIn("validation/fixtures.sh", output)

    def test_a_row_is_not_satisfied_by_a_test_in_some_other_suite(self):
        """19 WR-04: the row says WHERE, so the check has to read where.

        `check_mechanism_row` unpacked ``suite_name`` and then used it only in
        the error message; the existence test searched every entry of
        ``SUITE_FILES``. The ``verify`` row's claim is specifically that
        V-01…V-04 live in ``validation/fixtures.sh`` — the link 19 D-12 exists
        to gate — and a ``test_v01_*`` function in any other suite satisfied it
        identically. ``GATED_SUITE``'s guard is a different assertion and does
        not cover this one: it checks only that some scanned row still NAMES
        the file, which this tree does.

        The fixture moves the token and nothing else, so the row, the
        parenthetical and every other observable stay exactly as the clean tree
        has them.
        """
        code, output = self.run_checker(
            self.tree(v01_suite="tests/test_dogen_unit.py")
        )
        self.assertEqual(code, 1, output)
        self.assertIn("points at validation/fixtures.sh", output)
        self.assertIn("v01", output)
        # Where it IS, so the report is actionable and not only a refusal.
        self.assertIn("tests/test_dogen_unit.py", output)

    def test_a_row_whose_test_is_in_the_file_it_names_is_cleared(self):
        """The other direction, so the check above cannot pass by refusing
        everything: the default tree puts ``test_v01_*`` in the file the row
        points at, and the whole run is clean."""
        code, output = self.run_checker(self.tree())
        self.assertEqual(code, 0, output)
        self.assertNotIn("points at", output)


class TestScopeDiscipline(CheckDocsCase):
    """The checker has no general constant-versus-doc-row rule."""

    def test_the_step_count_backstop_is_never_reported_as_drift(self):
        """`.planning/WINDOWS.md` entry 17: the tool's step-count backstop constant
        has no contract row behind it — contract section 5.2 caps the step plan in
        bytes and names no count cap — so a general "every constant needs a row"
        rule would report it forever. The absence is asserted rather than assumed,
        over a clean tree, several mutated trees and the real repository.
        """
        forbidden = "MAX_" + "STEPS"
        trees = (
            self.tree(),
            build_tree(self.tmp / "b", verb_rows=[]),
            build_tree(self.tmp / "c", claims=False),
            build_tree(self.tmp / "d", links=DEFAULT_LINKS + (("x", "docs/no.md"),)),
        )
        for tree in trees:
            with self.subTest(tree=tree.name):
                _code, output = self.run_checker(tree)
                self.assertNotIn(forbidden, output)
        _code, output = self.run_checker(ROOT)
        self.assertNotIn(forbidden, output)


if __name__ == "__main__":
    unittest.main()
