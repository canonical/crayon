"""Static guardrail: no unscrubbed prior-art identities in ``.planning/``.

All prior-art identities are anonymized in committed artifacts (the reference
skills family is ``ng``; the teardowns are ``els``/``c2d``/``gd``). This repo is
the canonical org repo, so its GSD planning tree must never carry the original
names. The v1.0 planning archive (TICKET) holds files that predate the rule;
they were deliberately NOT migrated here — this lint keeps it that way.

It mirrors :mod:`seam_check` / :mod:`skill_lint`: a single :func:`main` with a
``0`` (clean) / ``1`` (violation) contract, invoked identically by the unit
suite, the pre-commit hook, and CI. A missing or empty planning tree is clean;
the lint checks every eligible file that is present.
"""

import re
import sys
from pathlib import Path

PLANNING_ROOT = Path(__file__).resolve().parents[1] / ".planning"
_FORBIDDEN_RE = re.compile(r"angie|elastic", re.IGNORECASE)
_TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".txt", ".toml", ".csv"}


def check_file(path: Path) -> list[str]:
    """Return every forbidden-name hit in one planning file.

    Parameters
    ----------
    path : Path
        A text file under ``.planning/``.

    Returns
    -------
    list of str
        Human-readable ``file:line: match`` messages; empty when clean.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: unreadable ({exc})"]
    hits: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = _FORBIDDEN_RE.search(line)
        if match:
            hits.append(f"{path}:{lineno}: forbidden name {match.group(0)!r}")
    return hits


def main() -> int:
    """Scan every text file under ``PLANNING_ROOT`` for forbidden names.

    Returns
    -------
    int
        ``0`` when every scanned file is clean (including when there are no
        eligible files), and ``1`` on any hit or unreadable file.
    """
    scanned = 0
    bad: list[str] = []
    for path in sorted(PLANNING_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        scanned += 1
        bad += check_file(path)
    if bad:
        print("planning-lint: VIOLATION(S):", *bad, sep="\n  ", file=sys.stderr)
        return 1
    print(
        f"planning-lint: OK - {scanned} planning files, no unscrubbed prior-art names"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
