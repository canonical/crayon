#!/usr/bin/env python3
"""Static guardrail: agentskills.io frontmatter invariants for the crayon skill family.

Asserts per skill: frontmatter ``name`` equals the directory name and matches
agentskills.io slug rules; ``description`` is present, non-empty (≤1024 chars), and
contains no bare ``: `` (colon+space) that would break a real YAML parser; the
single-writer rule (only :data:`WRITERS` may hold a write-capable tool); and
both compatibility numbers from ``docs/contract.md`` §5.10, compared as literal
strings and never parsed as versions. ``min_tool`` is read from ``crayon.py``'s
``__version__`` line, its one definition site, as text: the tool is never
imported.

Exit codes: 0 = clean, 1 = violation, 2 = vacuous pass (0 skills scanned).
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_MAX_NAME = 64
_MAX_DESC = 1024

#: The single-writer rule. Every other skill reaches disk through the tool
#: (``crayon unit new --body-file -``), so a write-capable tool in its
#: ``allowed-tools`` is a drift to catch, not a capability to use. This is a lint
#: and a convention: the real write boundary is the tool's own containment check.
WRITERS = {"crayon-write"}
_WRITE_TOOLS = {"write", "edit", "multiedit", "notebookedit"}

#: The tool's version line, anchored to a whole line of ``crayon.py``.
_VERSION_RE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)


def tool_version(root):
    """The tool's ``__version__``, read from ``<root>/crayon.py`` as text.

    ``crayon.py`` is the one definition site of the version, so every copy
    that names it is read from here or asserted against it, never typed. The
    tool is not imported. No match is an error, never an empty-string pass, and
    the value is a literal string, never parsed as a version (contract §5.10).
    """
    text = (Path(root) / "crayon.py").read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if match is None:
        raise RuntimeError("crayon.py carries no __version__ line")
    return match.group(1)


#: contract.md §5.10. Compared as literal strings — never parsed, ordered or
#: rounded as versions. ``min_tool`` is the tool's own ``__version__``, read from
#: ``crayon.py``, its one definition site; the lint types no version.
_EXPECTED_METADATA = {
    "metadata.crayon_contract": "1",
    "metadata.crayon_min_tool": tool_version(REPO_ROOT),
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def split_front_matter(text: str) -> tuple[dict, str]:
    """Split SKILL.md into (frontmatter_dict, body). Minimal YAML parser.

    Flat ``key: value`` lines land under ``key``, exactly as before. One level of
    nesting is understood: a key whose value is empty, followed by indented
    ``key: value`` lines, yields ``parent.child`` entries (so
    ``metadata.crayon_contract`` is addressable). This parser is shared verbatim
    with ``tests/test_skill_text.py`` so the lint and the S-suite can never
    disagree about what a skill declares.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("no YAML front-matter block found")
    fm: dict = {}
    parent = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        indented = line[:1].isspace()
        if ":" not in line:
            if not indented:
                parent = None
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"')
        if indented:
            if parent is not None:
                fm["%s.%s" % (parent, key)] = val
            continue
        fm[key] = val
        parent = key if val == "" else None
    return fm, text[m.end() :]


def _tools(frontmatter: dict) -> list:
    """The ``allowed-tools`` value as a list of non-empty names."""
    raw = str(frontmatter.get("allowed-tools") or "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def check_skill(skill_dir: Path) -> list:
    """Return every invariant violation for a single skill directory."""
    errs: list = []
    try:
        frontmatter, _ = split_front_matter(
            skill_dir.joinpath("SKILL.md").read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        return [f"{skill_dir.name}: unreadable SKILL.md front-matter ({exc})"]

    name = str(frontmatter.get("name") or "")
    if name != skill_dir.name:
        errs.append(f"{skill_dir.name}: name {name!r} != directory name")
    if not _NAME_RE.match(name) or len(name) > _MAX_NAME:
        errs.append(f"{skill_dir.name}: name {name!r} is not agentskills.io-conformant")

    description = str(frontmatter.get("description") or "")
    if not description.strip():
        errs.append(f"{skill_dir.name}: missing or empty description")
    elif len(description) > _MAX_DESC:
        errs.append(f"{skill_dir.name}: description exceeds {_MAX_DESC} chars")
    # A ":" followed by whitespace inside an unquoted plain scalar breaks a real
    # YAML parser (it is read as the start of a nested mapping, e.g. "intent:
    # reference"). Our lenient partition() splitter misses it; flag it here.
    if re.search(r":\s", description):
        errs.append(
            f"{skill_dir.name}: description contains a bare ': ' (colon+space) — "
            "breaks YAML plain-scalar parsing; reword or quote the description"
        )

    tools = _tools(frontmatter)
    if not tools:
        errs.append(f"{skill_dir.name}: missing or empty allowed-tools")
    if skill_dir.name not in WRITERS:
        for tool in tools:
            if tool.lower() in _WRITE_TOOLS:
                errs.append(
                    f"{skill_dir.name}: allowed-tools holds the write-capable tool "
                    f"{tool!r}, but only {sorted(WRITERS)} may write; the plan and "
                    "the page reach disk through the tool's own verbs"
                )

    for key, expected in _EXPECTED_METADATA.items():
        actual = frontmatter.get(key)
        if actual is None:
            errs.append(f"{skill_dir.name}: missing {key} (expected {expected!r})")
        elif actual != expected:
            errs.append(
                f"{skill_dir.name}: {key} is {actual!r}, expected the literal string "
                f"{expected!r} (contract §5.10 — compared as strings, never parsed "
                "as a version)"
            )

    return errs


def main(argv=None) -> int:
    """Scan <root>/*/SKILL.md and report any invariant violation."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=SKILLS_ROOT,
        help="directory holding the skill directories (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    root = args.root

    scanned = 0
    bad: list = []
    for skill_md in sorted(root.glob("*/SKILL.md")):
        scanned += 1
        bad += check_skill(skill_md.parent)
    if scanned == 0:
        print(
            "skill-lint: ERROR - scanned 0 skills (path misconfigured or empty)",
            file=sys.stderr,
        )
        return 2
    if bad:
        print("skill-lint: VIOLATION(S):", *bad, sep="\n  ", file=sys.stderr)
        return 1
    print(f"skill-lint: OK - {scanned} skills, frontmatter invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
