"""Anonymization-lint tests, single-sourcing the CI/pre-commit check.

Mirrors the skill-lint keystone set: a positive gate on the real ``.planning/``
tree, negative keystones against forbidden and unreadable content, and explicit
coverage that a missing or empty optional planning tree is clean.

WR-08 (iteration 3): this module was pytest-based, and this branch has no
pyproject, no pytest and no uv — so it errored under ``python3 -m unittest
tests.test_planning_lint`` and no command in ``AGENTS.md``'s gate,
``tests/run_matrix.sh`` or either bash suite ran it. A test module in ``tests/``
that no gate executes and that fails when executed is the "silently green" class
the rest of this phase's infrastructure was built against. Ported to the stdlib
runner and added to the gate.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_planning_lint():
    """Import ``scripts/planning_lint.py`` without putting ``scripts/`` on the path.

    ``sys.path.insert`` would shadow any stdlib module that shares a name with a
    file in ``scripts/`` for the whole process, and this module runs inside the
    same interpreter as every other suite under ``python3 -m unittest``.
    """
    import importlib.machinery
    import importlib.util

    path = ROOT / "scripts" / "planning_lint.py"
    loader = importlib.machinery.SourceFileLoader("planning_lint", str(path))
    spec = importlib.util.spec_from_loader("planning_lint", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


planning_lint = _load_planning_lint()


class TestPlanningLint(unittest.TestCase):
    """The ``0`` clean / ``1`` violation contract, in both directions."""

    def setUp(self):
        self._root = planning_lint.PLANNING_ROOT
        self.tmp = Path(tempfile.mkdtemp(prefix="planning-lint-"))

    def tearDown(self):
        planning_lint.PLANNING_ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_real_planning_tree_is_clean(self):
        """The committed ``.planning/`` tree carries no unscrubbed prior-art names.

        ``.planning/`` lives on the planning branch and is gitignored on
        ``main``. Its absence is a clean result because the tree is optional.
        """
        self.assertEqual(planning_lint.main(), 0)

    def test_forbidden_name_is_detected(self):
        """Each unscrubbed prior-art name must yield a hit (negative keystone)."""
        for line in ("see the angie skills", "the Elastic teardown", "ANGIE-review"):
            with self.subTest(line=line):
                bad = self.tmp / "notes.md"
                bad.write_text("clean line\n%s\n" % line, encoding="utf-8")
                hits = planning_lint.check_file(bad)
                self.assertTrue(
                    hits,
                    "expected a violation for %r but check_file returned []" % line,
                )
                self.assertIn(":2:", hits[0])

    def test_scrubbed_tokens_pass(self):
        """The sanctioned scrubbed tokens (ng/els/c2d/gd) are not violations."""
        ok = self.tmp / "notes.md"
        ok.write_text(
            "the ng family; the els, c2d and gd teardowns\n", encoding="utf-8"
        )
        self.assertEqual(planning_lint.check_file(ok), [])

    def test_main_returns_0_on_missing_root(self):
        """A missing optional planning root is clean."""
        planning_lint.PLANNING_ROOT = self.tmp / "missing"
        self.assertEqual(planning_lint.main(), 0)

    def test_main_returns_0_on_empty_root(self):
        """An empty optional planning root is clean."""
        planning_lint.PLANNING_ROOT = self.tmp
        self.assertEqual(planning_lint.main(), 0)

    def test_main_returns_0_on_clean_file(self):
        """Eligible clean files are still scanned successfully."""
        self.tmp.joinpath("STATE.md").write_text("the ng family\n", encoding="utf-8")
        planning_lint.PLANNING_ROOT = self.tmp
        self.assertEqual(planning_lint.main(), 0)

    def test_main_returns_1_on_violation(self):
        """``main()`` returns 1 when any scanned planning file carries a hit."""
        self.tmp.joinpath("STATE.md").write_text("angie was here\n", encoding="utf-8")
        planning_lint.PLANNING_ROOT = self.tmp
        self.assertEqual(planning_lint.main(), 1)

    def test_main_returns_1_on_unreadable_content(self):
        """A file that is not UTF-8 is an unreadable-file violation."""
        self.tmp.joinpath("STATE.md").write_bytes(b"\xff\xfebinary\n")
        planning_lint.PLANNING_ROOT = self.tmp
        self.assertEqual(planning_lint.main(), 1)


if __name__ == "__main__":
    unittest.main()
