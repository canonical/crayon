"""Static guardrail: D-18 skill-surface + agentskills.io frontmatter invariants.

This is the deterministic enforcement that makes the Write/Edit tool-surface
isolation a **provable invariant in code, not authoring discipline** (D-18) — a
security-relevant boundary of the same kind as the provider seam. It mirrors
:mod:`seam_check`: a single :func:`main` with a ``0`` (clean) / ``1`` (violation)
/ ``2`` (scanned 0 skills — vacuous-pass guard) contract, invoked identically by
pytest, the pre-commit hook, and CI (the real-tree hook wiring lands in Plan
04-04, after Plan 04-03 authors the skills).

Per skill it asserts: frontmatter ``name`` equals the directory name and matches
the agentskills.io slug rules; ``description`` is present and non-empty; and a
**fail-closed** write-isolation invariant — any skill whose directory name is NOT
in the :data:`WRITERS` allowlist must have ``Write``/``Edit`` absent from
``allowed-tools`` (so a future skill is write-free by default and must be
deliberately allowlisted, D-02). The tool list is tokenized delimiter-agnostically
(commas AND whitespace) so a comma-authored list is not read as one opaque token
on a space-delimiter harness (Pitfall 1).
"""

import re
import sys
from pathlib import Path

from dogen.adapters.planning_fs import split_front_matter

SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
WRITERS = {"dogen-write", "dogen-record"}
_WRITE_TOOLS = {"Write", "Edit"}
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DELIM_RE = re.compile(r"[,\s]+")
_MAX_NAME = 64
_MAX_DESC = 1024


def _tools(frontmatter: dict) -> set[str]:
    """Return the ``allowed-tools`` tokens, split on commas AND whitespace.

    Parameters
    ----------
    frontmatter : dict
        The parsed SKILL.md front-matter mapping.

    Returns
    -------
    set of str
        The declared tool names. ``allowed-tools`` may be a delimiter-flexible
        string (comma- or space-separated) or a YAML list; either is tokenized
        delimiter-agnostically so the Write/Edit-absence check holds under any
        harness delimiter (Pitfall 1).
    """
    raw = frontmatter.get("allowed-tools", "") or ""
    if not isinstance(raw, str):
        raw = " ".join(str(item) for item in raw)
    return {token for token in _DELIM_RE.split(raw) if token}


def check_skill(skill_dir: Path) -> list[str]:
    """Return every invariant violation for a single skill directory.

    Parameters
    ----------
    skill_dir : Path
        A ``skills/<name>/`` directory containing a ``SKILL.md``.

    Returns
    -------
    list of str
        Human-readable violation messages; empty when the skill is clean.
    """
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

    if skill_dir.name not in WRITERS and (_tools(frontmatter) & _WRITE_TOOLS):
        errs.append(f"{skill_dir.name}: Write/Edit must be absent (write-free skill)")
    return errs


def main() -> int:
    """Scan ``SKILLS_ROOT/*/SKILL.md`` and report any invariant violation.

    Returns
    -------
    int
        ``0`` when every scanned skill is clean, ``1`` on any violation, and
        ``2`` when zero skills were scanned (the vacuous-pass guard, so a
        misconfigured or not-yet-populated root cannot masquerade as clean).
    """
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
    print(
        f"skill-lint: OK - {scanned} skills, tool-surface + frontmatter invariants hold"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
