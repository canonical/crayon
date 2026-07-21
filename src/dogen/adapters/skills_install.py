"""The skills install flow: stage the canonical family into a harness (Q7).

One canonical `skills/` directory is the single source of truth; per-harness
staging is this adapter's job — never a hand-copy or a symlink (the smoke
runbook's copy method, promoted to a supported verb). It stages byte-identical
copies into the chosen harness's discovery root, records a manifest
(`.dogen/skills-install.yaml`) with per-harness content hashes so drift is
detectable, and refreshes installs in place.

Minimal harness discovery: a harness is "present" when its conventional
directory exists in the target repo (`.claude/`, `.github/`, `.opencode/`).
Per-harness tailoring is a deliberate no-op hook today — the skills are
authored delimiter-agnostically (`allowed-tools` tokenizes on commas AND
whitespace), so byte-identical copies work on every supported harness; the
hook exists so a future harness quirk has a place to land without changing
the flow's shape.
"""

import contextlib
import hashlib
import shutil
from pathlib import Path

import yaml

from dogen import __version__

#: Harness name → skills discovery root, relative to the target repo.
HARNESS_ROOTS: dict[str, str] = {
    "claude": ".claude/skills",
    "copilot": ".github/skills",
    "opencode": ".opencode/skills",
}

#: The manifest recording what was installed where, with content hashes.
MANIFEST_RELPATH = ".dogen/skills-install.yaml"

#: The canonical entries staged into a harness root (skill dirs + family docs).
_FAMILY_ENTRIES = (
    "dogen-plan",
    "dogen-write",
    "dogen-review",
    "dogen-record",
    "README.md",
    "LICENSE",
)


class SkillsInstallError(RuntimeError):
    """Raised when the install flow cannot locate or stage the skill family."""


def canonical_skills_dir(explicit: Path | None = None) -> Path:
    """Locate the canonical ``skills/`` directory.

    Resolution order: an explicit ``--from`` path; else the directory shipped
    alongside the installed ``dogen`` package (a repo checkout's ``skills/``).

    Parameters
    ----------
    explicit : Path or None
        The operator's ``--from`` override, when given.

    Returns
    -------
    Path
        The canonical skills directory (contains ``dogen-plan/SKILL.md``).

    Raises
    ------
    SkillsInstallError
        If no candidate contains the skill family.
    """
    candidates = [explicit] if explicit is not None else []
    # src/dogen/adapters/skills_install.py -> repo root -> skills/
    candidates.append(Path(__file__).resolve().parents[3] / "skills")
    for candidate in candidates:
        if candidate is not None and (candidate / "dogen-plan" / "SKILL.md").is_file():
            return candidate.resolve()
    raise SkillsInstallError(
        "cannot locate the canonical skills/ directory; pass --from <path>"
    )


def discover_harnesses(root: Path) -> list[str]:
    """Return the harnesses whose conventional directories exist in ``root``.

    Parameters
    ----------
    root : Path
        The target repo root.

    Returns
    -------
    list of str
        The detected harness names, in :data:`HARNESS_ROOTS` order; empty when
        none are detectable.
    """
    detected = []
    for name, rel in HARNESS_ROOTS.items():
        marker = root / Path(rel).parts[0]
        if marker.is_dir():
            detected.append(name)
    return detected


def _tree_sha256(base: Path) -> str:
    """Hash the family's staged content beneath ``base`` deterministically.

    Parameters
    ----------
    base : Path
        A directory holding the staged family entries.

    Returns
    -------
    str
        A SHA-256 hex digest over every family file's relative path and bytes,
        in sorted order; ``""`` when nothing staged exists.
    """
    digest = hashlib.sha256()
    seen = False
    for entry in _FAMILY_ENTRIES:
        target = base / entry
        if target.is_file():
            files: list[Path] = [target]
        elif target.is_dir():
            files = sorted(p for p in target.rglob("*") if p.is_file())
        else:
            continue
        for path in files:
            seen = True
            digest.update(str(path.relative_to(base)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest() if seen else ""


def _tailor(harness: str, staged: Path) -> None:
    """Apply per-harness tailoring to a freshly staged copy (no-op today).

    Parameters
    ----------
    harness : str
        The harness the copy was staged for.
    staged : Path
        The staged root to tailor in place.
    """
    # Deliberately empty: the family is authored harness-agnostically. A future
    # harness quirk (e.g. a delimiter or frontmatter dialect) lands here.


def _remove_family(base: Path) -> None:
    """Remove the staged family entries beneath ``base`` (dogen-owned only).

    Used when a harness's discovery root changed between dogen versions: the
    stale staged copy is dogen's to clean up, but foreign files beside it are
    not — the base directory itself is removed only when the family was its
    sole content.

    Parameters
    ----------
    base : Path
        The previously recorded staging root.
    """
    for entry in _FAMILY_ENTRIES:
        target = base / entry
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()
    with contextlib.suppress(OSError):
        base.rmdir()


def read_manifest(root: Path) -> dict:
    """Load the install manifest, or an empty shell when absent.

    Parameters
    ----------
    root : Path
        The target repo root.

    Returns
    -------
    dict
        The parsed manifest mapping (``{"installs": [...]}``).
    """
    path = root / MANIFEST_RELPATH
    if not path.is_file():
        return {"installs": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"installs": []}


def _write_manifest(root: Path, manifest: dict) -> Path:
    """Persist the install manifest.

    Parameters
    ----------
    root : Path
        The target repo root.
    manifest : dict
        The manifest mapping to serialize.

    Returns
    -------
    Path
        The written manifest path.
    """
    path = root / MANIFEST_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def install(  # noqa: PLR0913
    root: Path,
    harness: str,
    *,
    source: Path | None = None,
    at: str = "",
) -> dict:
    """Stage the canonical family into one harness and record the manifest.

    Parameters
    ----------
    root : Path
        The target repo root.
    harness : str
        The harness to stage for (a :data:`HARNESS_ROOTS` key).
    source : Path or None
        An explicit canonical ``skills/`` override (``--from``).
    at : str
        The ISO-8601 install timestamp recorded in the manifest.

    Returns
    -------
    dict
        The manifest entry recorded for this harness.

    Raises
    ------
    SkillsInstallError
        If the harness is unknown or the canonical family cannot be located.
    """
    if harness not in HARNESS_ROOTS:
        known = ", ".join(sorted(HARNESS_ROOTS))
        raise SkillsInstallError(f"unknown harness {harness!r}; choose one of: {known}")
    canonical = canonical_skills_dir(source)
    dest = root / HARNESS_ROOTS[harness]
    dest.mkdir(parents=True, exist_ok=True)
    for entry in _FAMILY_ENTRIES:
        src = canonical / entry
        target = dest / entry
        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        elif src.is_file():
            shutil.copy2(src, target)
    _tailor(harness, dest)
    record = {
        "harness": harness,
        "path": HARNESS_ROOTS[harness],
        "sha256": _tree_sha256(dest),
        "at": at,
        "dogen_version": __version__,
    }
    manifest = read_manifest(root)
    manifest["installs"] = [
        e for e in manifest.get("installs", []) if e.get("harness") != harness
    ]
    manifest["installs"].append(record)
    _write_manifest(root, manifest)
    return record


def status(root: Path, *, source: Path | None = None) -> list[dict]:
    """Report each recorded install's drift state.

    Parameters
    ----------
    root : Path
        The target repo root.
    source : Path or None
        An explicit canonical ``skills/`` override (``--from``).

    Returns
    -------
    list of dict
        One row per manifest entry: the record plus ``state`` —
        ``ok`` (installed tree matches the canonical family), ``drifted``
        (either side changed since install), or ``missing`` (the staged tree
        is gone).
    """
    canonical_hash = _tree_sha256(canonical_skills_dir(source))
    rows = []
    for entry in read_manifest(root).get("installs", []):
        staged = root / entry.get("path", "")
        staged_hash = _tree_sha256(staged)
        if not staged_hash:
            state = "missing"
        elif staged_hash == canonical_hash:
            state = "ok"
        else:
            state = "drifted"
        rows.append({**entry, "state": state})
    return rows


def update(root: Path, *, source: Path | None = None, at: str = "") -> list[dict]:
    """Re-stage every recorded install from the canonical family.

    Parameters
    ----------
    root : Path
        The target repo root.
    source : Path or None
        An explicit canonical ``skills/`` override (``--from``).
    at : str
        The ISO-8601 refresh timestamp recorded in the manifest.

    Returns
    -------
    list of dict
        The refreshed manifest entries.
    """
    refreshed = []
    for entry in read_manifest(root).get("installs", []):
        harness = entry.get("harness", "")
        recorded = entry.get("path", "")
        current = HARNESS_ROOTS.get(harness, "")
        if recorded and current and recorded != current:
            _remove_family(root / recorded)
        refreshed.append(install(root, harness, source=source, at=at))
    return refreshed
