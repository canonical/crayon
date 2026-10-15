#!/usr/bin/env python3
"""Deterministic checker for the ``docs/`` wiki and its entry point ``AGENTS.md``.

The wiki is a flat set of pages under ``docs/``; ``AGENTS.md`` is the one entry
point and the root of reachability. Pages address one another with ``[[slug]]``,
where ``slug`` is the page's filename stem and nothing else: no ``#anchor``, no
``|alias``, no directory. The notation is reserved to the wiki and the entry
point, and it is checked even inside code fences — the checker is deliberately
fence-blind, so nothing later "fixes" that as a bug. Outside the wiki a page is
cited by its path, ``docs/<slug>.md``, and that path must exist.

Ten checks, in a fixed order that matters (earlier ones establish what later
ones rely on: slug uniqueness before link resolution, resolution before
reachability):

1.  ``entry-identity``      the entry point exists (one entry point; no twin)
2.  ``duplicate-slug``      no two pages share a basename
3.  ``dangling-link``       every ``[[...]]`` is well-formed and names a page
4.  ``orphan-page``         every page is reachable from AGENTS.md transitively
5.  ``h1-missing``          the first non-blank line of a page is an ``# `` H1
6.  ``link-outside-wiki``   ``[[slug]]`` appears nowhere outside the wiki
7.  ``stale-citation``      nothing cites "AGENTS.md section N"
8.  ``dead-path-citation``  every cited ``docs/<slug>.md`` path exists
9.  ``provenance-missing``  line 3 of a page is ``<!-- provenance: ... -->``
10. ``related-footer``      the last line of a page is ``Related: [[a]], [[b]].``

Exit codes: ``0`` the contract holds, ``1`` findings (one per line, then a
tally), ``2`` tool error (no wiki directory). ``--json`` emits
``{"findings": [...], "exit": N}``.

Scope decisions, stated so they are decisions and not accidents:

- Checks 6 and 7 scan ``scripts/``, ``tests/``, ``validation/``, ``skills/``,
  ``.github/``, the root ``*.md`` files and ``crayon.py``. The two files that
  must quote violations — this file and its test — are exempt by name.
- Check 8 scans the same set MINUS ``tests/`` and ``validation/``: in those
  trees ``docs/<name>.md`` is a path in a *target* repository's docs root (the
  thing crayon writes into), not a citation of this wiki, and the two cannot be
  told apart by shape. Inside the scanned set the one such example is the
  conventional Sphinx root document ``docs/index.md``, used as a seed in the
  hand walk in ``docs/development.md``; it is exempt by name below.
- No page-size cap: a wiki page is read on demand. No frontmatter, no
  backlink lists, no "last reviewed" dates — see the conventions page.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = "docs"
ENTRY_POINTS = ("AGENTS.md",)

LINK_RE = re.compile(r"\[\[([^\]]*)\]\]")  # permissive on purpose: catches malformed links
SLUG_RE = re.compile(r"^[a-z0-9-]+$")
STALE_RE = re.compile(r"AGENTS\.md\s*(§|section\s|sections\s)")
PATH_CITE_RE = re.compile(r"(?<![A-Za-z0-9_/.-])docs/([a-z0-9-]+)\.md")
PROVENANCE_PREFIX = "<!-- provenance:"
RELATED_RE = re.compile(r"^Related: \[\[[a-z0-9-]+\]\](?:, \[\[[a-z0-9-]+\]\])*\.$")

SCAN_DIRS = ("scripts", "tests", "validation", "skills", ".github", WIKI_DIR)
SCAN_SUFFIXES = {".py", ".md", ".txt", ".sh", ".yml", ".yaml", ".json", ".toml", ".cfg"}
SKIP_PARTS = {".venv", "node_modules", "__pycache__", ".git", ".planning"}
ROOT_FILES = ("crayon.py",)
#: Trees where ``docs/<name>.md`` names a target repository's page, not a wiki
#: page (see the module docstring). Check 8 skips them.
PATH_CITE_SKIP_DIRS = ("tests", "validation")
#: Files that must quote the violations they reject.
EXEMPT_FILES = {"scripts/wiki_lint.py", "tests/test_wiki_lint.py"}
#: Path citations that are not wiki pages, each with its reason.
EXEMPT_CITATIONS = {
    # The conventional Sphinx root document, seeded by the hand walk in
    # docs/development.md as a target-repository page.
    "docs/index.md",
}
#: Pages allowed to end without a ``Related:`` line, each with its reason.
NO_FOOTER = ()


class Lint:
    def __init__(self, root):
        self.root = Path(root)
        self.findings = []

    def flag(self, path, check, message):
        rel = path if isinstance(path, str) else str(Path(path).relative_to(self.root))
        self.findings.append({"file": rel, "check": check, "message": message})

    # -- helpers ------------------------------------------------------------

    def wiki_pages(self):
        return sorted((self.root / WIKI_DIR).rglob("*.md"))

    def entry_points(self):
        return [self.root / name for name in ENTRY_POINTS]

    def is_wiki_file(self, path):
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            return False
        return rel.parts[0] == WIKI_DIR or str(rel) in ENTRY_POINTS

    def read(self, path):
        return path.read_text(encoding="utf-8", errors="replace")

    def scan_files(self, skip_dirs=()):
        files = []
        for name in SCAN_DIRS:
            base = self.root / name
            if not base.is_dir() or name in skip_dirs:
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
                    continue
                if any(part in SKIP_PARTS for part in path.relative_to(self.root).parts):
                    continue
                files.append(path)
        for path in sorted(self.root.glob("*.md")):
            files.append(path)
        for name in ROOT_FILES:
            path = self.root / name
            if path.is_file():
                files.append(path)
        return [p for p in files if str(p.relative_to(self.root)) not in EXEMPT_FILES]

    # -- checks -------------------------------------------------------------

    def check_entry_identity(self):
        ok = True
        for path in self.entry_points():
            if not path.is_file():
                self.flag(str(path.relative_to(self.root)), "entry-identity", "entry point is missing")
                ok = False
        return ok

    def check_duplicate_slug(self):
        slugs = {}
        for path in self.wiki_pages():
            if path.stem in slugs:
                self.flag(
                    path,
                    "duplicate-slug",
                    "basename '%s.md' already used by %s; links resolve by basename, "
                    "so slugs must be unique" % (path.stem, slugs[path.stem].relative_to(self.root)),
                )
            else:
                slugs[path.stem] = path
        return slugs

    def check_links(self, slugs):
        for path in self.entry_points() + self.wiki_pages():
            if not path.is_file():
                continue
            for slug in LINK_RE.findall(self.read(path)):
                if not SLUG_RE.match(slug):
                    self.flag(
                        path,
                        "dangling-link",
                        "malformed wiki link [[%s]] -- slugs are kebab-case page names only "
                        "(no anchors or aliases)" % slug,
                    )
                elif slug not in slugs:
                    self.flag(
                        path,
                        "dangling-link",
                        "[[%s]] does not match any page under %s/" % (slug, WIKI_DIR),
                    )

    def check_orphans(self, slugs):
        entry = self.entry_points()[0]
        if not entry.is_file():
            return
        reachable = set()
        frontier = set(LINK_RE.findall(self.read(entry)))
        while frontier:
            slug = frontier.pop()
            if slug in reachable or slug not in slugs:
                continue
            reachable.add(slug)
            frontier |= set(LINK_RE.findall(self.read(slugs[slug])))
        for slug, path in sorted(slugs.items()):
            if slug not in reachable:
                self.flag(
                    path,
                    "orphan-page",
                    "not reachable from %s via [[links]]; add it to the topic index" % ENTRY_POINTS[0],
                )

    def check_page_shape(self):
        for path in self.wiki_pages():
            lines = self.read(path).splitlines()
            first = next((line for line in lines if line.strip()), None)
            if first is None:
                self.flag(path, "h1-missing", "page is empty")
                continue
            if not first.startswith("# "):
                self.flag(path, "h1-missing", "first non-blank line must be an '# ' H1 title")
            if len(lines) < 3 or not lines[2].lstrip().startswith(PROVENANCE_PREFIX):
                self.flag(
                    path,
                    "provenance-missing",
                    "line 3 must be an HTML comment starting '%s' saying where the page "
                    "came from" % PROVENANCE_PREFIX,
                )
            if path.stem in NO_FOOTER:
                continue
            last = next((line for line in reversed(lines) if line.strip()), "")
            if not RELATED_RE.match(last.strip()):
                self.flag(
                    path,
                    "related-footer",
                    "last line must be 'Related: [[a]], [[b]].' -- one line, comma-separated, "
                    "terminated with a period",
                )

    def check_scan_set(self):
        for path in self.scan_files():
            text = self.read(path)
            if not self.is_wiki_file(path):
                for match in LINK_RE.finditer(text):
                    if SLUG_RE.match(match.group(1)):
                        self.flag(
                            path,
                            "link-outside-wiki",
                            "[[%s]] wiki notation outside the wiki; cite the page by path "
                            "instead (e.g. %s/%s.md)" % (match.group(1), WIKI_DIR, match.group(1)),
                        )
            body = "\n".join(
                line for line in text.splitlines() if not line.lstrip().startswith(PROVENANCE_PREFIX)
            )
            if STALE_RE.search(body):
                self.flag(
                    path,
                    "stale-citation",
                    "monolith-style 'AGENTS.md section' citation; cite the %s/ page path "
                    "instead" % WIKI_DIR,
                )
        for path in self.scan_files(skip_dirs=PATH_CITE_SKIP_DIRS):
            text = self.read(path)
            for match in PATH_CITE_RE.finditer(text):
                cited = match.group(0)
                if cited in EXEMPT_CITATIONS:
                    continue
                if not (self.root / cited).exists():
                    self.flag(path, "dead-path-citation", "cited path %s does not exist" % cited)

    def run(self):
        if not (self.root / WIKI_DIR).is_dir():
            print("wiki_lint: ERROR - no %s/ directory under %s" % (WIKI_DIR, self.root), file=sys.stderr)
            return 2
        self.check_entry_identity()
        slugs = self.check_duplicate_slug()
        self.check_links(slugs)
        self.check_orphans(slugs)
        self.check_page_shape()
        self.check_scan_set()
        return 1 if self.findings else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: %(default)s)")
    parser.add_argument("--json", action="store_true", help="emit {findings, exit} as JSON")
    args = parser.parse_args(argv)
    lint = Lint(args.root)
    code = lint.run()
    if args.json:
        print(json.dumps({"findings": lint.findings, "exit": code}))
        return code
    for finding in lint.findings:
        print("%s: [%s] %s" % (finding["file"], finding["check"], finding["message"]))
    if code == 0:
        print("wiki_lint: OK - %d page(s), 0 finding(s)" % len(lint.wiki_pages()))
    elif code == 1:
        print("wiki_lint: %d finding(s)" % len(lint.findings))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
