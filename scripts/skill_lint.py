#!/usr/bin/env python3
"""Static guardrail: agentskills.io frontmatter invariants for the dogen skill family.

Asserts per skill: frontmatter ``name`` equals the directory name and matches
agentskills.io slug rules; ``description`` is present, non-empty (≤1024 chars), and
contains no bare ``: `` (colon+space) that would break a real YAML parser.

Exit codes: 0 = clean, 1 = violation, 2 = vacuous pass (0 skills scanned).
"""

import re
import sys
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_MAX_NAME = 64
_MAX_DESC = 1024

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def split_front_matter(text: str) -> tuple[dict, str]:
    """Split SKILL.md into (frontmatter_dict, body). Minimal YAML parser."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("no YAML front-matter block found")
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"')
    return fm, text[m.end() :]


def check_skill(skill_dir: Path) -> list[str]:
    """Return every invariant violation for a single skill directory."""
    errs: list[str] = []
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

    return errs


def main() -> int:
    """Scan SKILLS_ROOT/*/SKILL.md and report any invariant violation."""
    scanned = 0
    bad: list[str] = []
    for skill_md in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
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
