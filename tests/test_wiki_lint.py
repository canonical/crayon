"""The wiki lint's own tests.

Two layers. The live tree IS the fixture: a red lint over the repository is a
contract regression, not a test problem, and the first test prints the lint's
own output so a red run names the page. The synthetic layer builds a two-page
tree in a temp directory, applies exactly one mutation per check, and asserts
on the check NAME, never on message text — wording is a UI concern, the check
identity is the contract. The negative tests are the ones that matter most:
they stop a check from being tightened into rejecting legitimate content.
"""

import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "wiki_lint.py"


def load_lint():
    loader = importlib.machinery.SourceFileLoader("wiki_lint", str(LINT))
    spec = importlib.util.spec_from_loader("wiki_lint", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


PAGE_ALPHA = "# Alpha\n\n<!-- provenance: fixture -->\n\nSee [[beta]].\n\nRelated: [[beta]].\n"
PAGE_BETA = "# Beta\n\n<!-- provenance: fixture -->\n\nplain page\n\nRelated: [[alpha]].\n"
GOOD_ENTRY = "# Guide\n\nIndex: [[alpha]] and [[beta]].\n"


class LiveTree(unittest.TestCase):
    def test_wiki_contract_holds(self):
        proc = subprocess.run(
            [sys.executable, str(LINT)], cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        )
        self.assertEqual(
            proc.returncode, 0,
            "wiki_lint found contract violations:\n%s%s" % (proc.stdout, proc.stderr),
        )

    def test_json_mode(self):
        proc = subprocess.run(
            [sys.executable, str(LINT), "--json"], cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["exit"], 0, payload)
        self.assertEqual(payload["findings"], [])

    def test_the_live_scan_is_not_vacuous(self):
        lint = load_lint().Lint(ROOT)
        self.assertGreaterEqual(len(lint.wiki_pages()), 5)
        self.assertGreaterEqual(len(lint.scan_files()), 20)


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.lint = load_lint()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "docs" / "a").mkdir(parents=True)
        (self.tmp / "docs" / "b").mkdir(parents=True)
        (self.tmp / "scripts").mkdir()
        self.write("AGENTS.md", GOOD_ENTRY)
        self.write("docs/a/alpha.md", PAGE_ALPHA)
        self.write("docs/b/beta.md", PAGE_BETA)

    def write(self, relative, text):
        path = self.tmp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def checks(self):
        lint = self.lint.Lint(self.tmp)
        code = lint.run()
        return code, sorted(set(f["check"] for f in lint.findings))

    def test_clean_tree(self):
        self.assertEqual(self.checks(), (0, []))

    def test_a_file_git_ignores_is_not_scanned(self):
        self.write("scripts/tool.py", '"""Per [[alpha]]."""\n')
        self.write(".gitignore", "scripts/tool.py\n")
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)
        self.assertEqual(self.checks(), (0, []))
        (self.tmp / ".gitignore").unlink()
        self.assertIn("link-outside-wiki", self.checks()[1])

    def test_missing_entry_point(self):
        (self.tmp / "AGENTS.md").unlink()
        self.assertIn("entry-identity", self.checks()[1])

    def test_duplicate_slug(self):
        self.write("docs/b/alpha.md", PAGE_ALPHA)
        self.assertIn("duplicate-slug", self.checks()[1])

    def test_dangling_link(self):
        self.write("docs/b/beta.md", PAGE_BETA.replace("plain page", "see [[missing-page]]"))
        self.assertIn("dangling-link", self.checks()[1])

    def test_malformed_link(self):
        self.write("docs/b/beta.md", PAGE_BETA.replace("plain page", "see [[alpha#section]]"))
        self.assertIn("dangling-link", self.checks()[1])

    def test_orphan_page(self):
        self.write("AGENTS.md", "# Guide\n\nIndex: [[alpha]].\n")
        self.write("docs/a/alpha.md", PAGE_ALPHA.replace("See [[beta]].", "").replace("Related: [[beta]].", "Related: [[alpha]]."))
        self.assertIn("orphan-page", self.checks()[1])

    def test_orphan_is_transitive_not_index_bound(self):
        """A page linked only from another page is reachable, not an orphan."""
        self.write("AGENTS.md", "# Guide\n\nIndex: [[alpha]].\n")
        self.assertEqual(self.checks(), (0, []))

    def test_missing_h1(self):
        self.write("docs/b/beta.md", PAGE_BETA.replace("# Beta\n", "Beta\n"))
        self.assertIn("h1-missing", self.checks()[1])

    def test_empty_page(self):
        self.write("docs/b/beta.md", "")
        self.assertIn("h1-missing", self.checks()[1])

    def test_provenance_missing(self):
        self.write("docs/b/beta.md", PAGE_BETA.replace("<!-- provenance: fixture -->", "no comment"))
        self.assertIn("provenance-missing", self.checks()[1])

    def test_related_footer_missing(self):
        self.write("docs/b/beta.md", PAGE_BETA.replace("Related: [[alpha]].", "See also alpha."))
        self.assertIn("related-footer", self.checks()[1])

    def test_link_outside_wiki(self):
        self.write("scripts/tool.py", '"""Per [[alpha]]."""\n')
        self.assertIn("link-outside-wiki", self.checks()[1])

    def test_bracket_pairs_outside_the_grammar_are_not_links(self):
        """A list literal whose inner text is not a slug is left alone.

        `[[1]]` IS a slug by the grammar and is reported; that is the known
        false positive the notation's reservation costs, and the fix is a space
        or a split literal, as the linter's docstring says."""
        self.write("scripts/tool.py", "x = [[1, 2]]\ny = [[ ]]\nz = [[a_b]]\n")
        self.assertEqual(self.checks(), (0, []))

    def test_stale_citation(self):
        self.write("scripts/tool.py", '"""Per AGENTS.md section 3.9."""\n')
        self.assertIn("stale-citation", self.checks()[1])

    def test_provenance_comment_is_exempt_from_stale_citation(self):
        self.write("docs/b/beta.md", PAGE_BETA.replace("<!-- provenance: fixture -->", "<!-- provenance: AGENTS.md section 3.9 -->"))
        self.assertEqual(self.checks(), (0, []))

    def test_dead_path_citation(self):
        self.write("scripts/tool.py", '"""See docs/renamed-away.md."""\n')
        self.assertIn("dead-path-citation", self.checks()[1])

    def test_live_path_citation_passes(self):
        self.write("scripts/tool.py", '"""See docs/a/alpha.md and docs/alpha.md."""\n')
        # docs/alpha.md does not exist in this tree; only flat citations are checked
        self.write("docs/alpha.md", PAGE_ALPHA.replace("# Alpha", "# Alpha Root"))
        (self.tmp / "docs" / "a" / "alpha.md").unlink()
        self.assertEqual(self.checks(), (0, []))

    def test_index_citation_is_exempt(self):
        self.write("scripts/tool.py", '"""Seed docs/index.md."""\n')
        self.assertEqual(self.checks(), (0, []))

    def test_tests_tree_is_outside_the_path_citation_scan(self):
        self.write("tests/t.py", '"""Writes docs/never-existed.md in the target repo."""\n')
        self.assertEqual(self.checks(), (0, []))

    def test_fence_blind(self):
        self.write("docs/b/beta.md", PAGE_BETA.replace("plain page", "```\n[[missing-page]]\n```"))
        self.assertIn("dangling-link", self.checks()[1])

    def test_no_wiki_dir_is_a_two(self):
        shutil.rmtree(self.tmp / "docs")
        self.assertEqual(self.checks()[0], 2)


if __name__ == "__main__":
    unittest.main()
