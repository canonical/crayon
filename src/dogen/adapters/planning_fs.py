"""Filesystem PlanningStore over ``.dogen/units/<id>/`` and ``docs/`` (D-31/33).

This adapter implements :class:`dogen.core.ports.PlanningStore`. It serializes
the F1 Pydantic models to disk and **never writes anywhere under ``.planning/``**
(D-30) — that is GSD's directory and is an explicit, enforced guard, not a
convention (threat T-02.1-01). The machine-written ``provenance.yaml`` uses
PyYAML; progress is **derived** from that record, not persisted (PROV-04 /
D-01/D-02). ``unit.md`` is only ever *created* here (the
operator hand-edits it afterward), so PyYAML suffices and ruamel.yaml is not
needed for round-trip comment preservation (A4 decision — recorded in SUMMARY).
"""

import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath

import yaml
from pydantic import ValidationError

from dogen.core.models import (
    PAGE_FORMATS,
    SCHEMA_VERSION,
    DogenConfig,
    Intent,
    Provenance,
    ReviewerEdit,
    SourceRef,
    Takeover,
    Unit,
    _latest_accept_at,
    _latest_accept_edit,
    derive_progress,
    is_sealed,
)

_UNITS_SUBDIR = ".dogen/units"
#: Passenger-handoff scratch root; a unit's staging lives at
#: ``.dogen/staging/<id>/`` and is gitignored, disposable, and removed on a
#: sealing accept (PROV-05 / D-03).
_STAGING_SUBDIR = ".dogen/staging"
_CONTEXT_SUBDIR = ".dogen/context"
_CONFIG_RELPATH = ".dogen/config.yaml"
_DOGEN_GITIGNORE_RELPATH = ".dogen/.gitignore"
#: Seeded into target repos so passenger staging scratch never gets swept into
#: a human's `git add .` commit (D5). Scoped: a blanket `.dogen/` ignore would
#: hide the committed unit sidecars.
_DOGEN_GITIGNORE_CONTENT = "staging/\n"
_FORBIDDEN_OUTPUT_ROOT = ".planning"
_FRONT_MATTER_FENCE = "---"

_BODY_TEMPLATE = """\
## Intent & scope

Describe what this page covers and who it serves.

## Outline / acceptance

- Outline the sections to draft.
- List the acceptance criteria a reviewer checks the draft against.
"""


class UnitExistsError(FileExistsError):
    """Raised when scaffolding would clobber an existing ``unit.md``."""


class UnitNotFoundError(FileNotFoundError):
    """Raised when an operation targets a unit whose directory does not exist."""


class UnsupportedTargetError(ValueError):
    """Raised when a target's extension names no supported page format (v1.2).

    The target extension IS the unit's format (``.md`` → MyST, ``.rst`` →
    reStructuredText). An extensionless or unknown-suffix target is refused
    eagerly at declare/edit time — round 2's extensionless target was accepted
    silently and cost a full fix-move-restale-re-sign detour (R4).
    """


class TargetClaimedError(FileExistsError):
    """Raised when a docs target already belongs to another unit's page set.

    Two units claiming one page would make draft ownership ambiguous
    (``find_unit_by_draft`` returns the first match) and let one unit's draft
    pass silently overwrite another's — refused eagerly at declare/edit time
    (v1.2).
    """


class SchemaUnsupportedError(ValueError):
    """Raised when a provenance record declares a newer ``schema_version`` (D-08).

    The loader refuses a record whose ``schema_version`` exceeds the tool's
    :data:`~dogen.core.models.SCHEMA_VERSION` *before* constructing the model —
    no partial/best-effort read of a shape the tool does not understand
    (threat T-05-04). Subclasses :class:`ValueError` so existing write-verb
    callers that catch ``ValueError`` do not crash; ``unit show`` classifies it
    by type-name into the stable ``schema_unsupported`` reason.
    """

    def __init__(self, found: int, supported: int) -> None:
        self.found = found
        self.supported = supported
        super().__init__(
            f"provenance schema_version {found} is newer than this tool "
            f"supports ({supported}); upgrade dogen to read it"
        )


class ProvenanceInvalidError(ValueError):
    """Raised when a present provenance record fails to parse/validate (D-09).

    A unit whose ``provenance.yaml`` exists but is malformed refuses cleanly
    with the parse/validation detail instead of masquerading as a missing unit
    (threat T-05-05). Subclasses :class:`ValueError`; ``unit show`` maps it to
    the stable ``provenance_invalid`` reason (never ``unit_not_found``).
    """

    def __init__(self, unit_id: str, *, detail: str) -> None:
        self.unit_id = unit_id
        self.detail = detail
        super().__init__(f"provenance for unit {unit_id!r} is invalid: {detail}")


def _in_flight_detail(prov: Provenance) -> str:
    """Compose an in-flight owner's state phrase for the refuse message (D-01).

    ``derive_progress`` alone cannot distinguish ``fix`` from ``redraft`` (both
    read as ``reviewed``), so the latest verdict is appended when present — the
    refuse names the owner's derived state and why it still holds its lease
    ("drafted, not accepted" / "reviewed, fix, not accepted").

    Parameters
    ----------
    prov : Provenance
        The overlapping in-flight owner's provenance record.

    Returns
    -------
    str
        The parenthetical state phrase, without surrounding parentheses.
    """
    state = derive_progress(prov)
    last_verdict = next(
        (e.verdict for e in reversed(prov.reviewer_edits) if e.verdict is not None),
        None,
    )
    if last_verdict is None:
        return f"{state.value}, not accepted"
    return f"{state.value}, {last_verdict.value}, not accepted"


def _page_sha12(edit: ReviewerEdit, page: str) -> str:
    """Return the first 12 hex of ``edit``'s sealed digest for ``page`` (A3).

    The seal authority is the ``accept`` reviewer edit's ``files[]``, each a
    ``docs/<page>`` digest. This looks up the digest for ``page`` and returns
    its 12-hex prefix — the exact text the owner's seal attests.

    Parameters
    ----------
    edit : ReviewerEdit
        The owner's latest ``accept`` reviewer edit.
    page : str
        The docs-relative page (e.g. ``guide.md``) to look up.

    Returns
    -------
    str
        The 12-hex digest prefix, or ``""`` when the page carries no sealed
        digest (defensive — a sealed page in the owner's target set always has
        one).
    """
    wanted = PurePosixPath("docs") / page
    for digest in edit.files:
        if PurePosixPath(digest.path) == wanted:
            return digest.sha256[:12]
    return ""


def _dominant_page_extension(root: Path) -> str:
    """Return the docs tree's dominant page extension (v1.2 scaffold default).

    Counts ``.md`` vs ``.rst`` pages under ``docs/``, skipping underscore
    directories (``_build``, ``_static``, ``_interfaces`` snippet dirs, …) so
    only real pages vote. An rst-heavy brownfield thereby scaffolds
    ``<unit_id>.rst`` by default instead of dropping a lone ``.md`` into an
    all-rst tree (round 2's opencode friction).

    Parameters
    ----------
    root : Path
        The repo root.

    Returns
    -------
    str
        ``".rst"`` when rst pages outnumber md pages; else ``".md"``
        (including an absent or empty docs tree, and ties).
    """
    docs = root / "docs"
    if not docs.is_dir():
        return ".md"
    counts = dict.fromkeys(PAGE_FORMATS, 0)
    for path in docs.rglob("*"):
        if not path.is_file() or path.suffix not in counts:
            continue
        if any(part.startswith("_") for part in path.relative_to(docs).parts[:-1]):
            continue
        counts[path.suffix] += 1
    return ".rst" if counts[".rst"] > counts[".md"] else ".md"


def _require_page_extension(target: str) -> None:
    """Refuse a docs target whose suffix is not a supported page format.

    Parameters
    ----------
    target : str
        The docs-relative target path to check.

    Raises
    ------
    UnsupportedTargetError
        If the suffix is not one of :data:`PAGE_FORMATS`.
    """
    suffix = PurePosixPath(target).suffix
    if suffix not in PAGE_FORMATS:
        known = ", ".join(sorted(PAGE_FORMATS))
        raise UnsupportedTargetError(
            f"target {target!r} must end in a page extension ({known}) — "
            "the extension decides the unit's format"
        )


def split_front_matter(text: str) -> tuple[dict, str]:
    """Split a ``---``-delimited document into front-matter and body.

    A small, tested splitter (not a regex) handling CRLF endings, an empty
    body, and a body that itself contains a ``---`` line (RESEARCH "Don't
    Hand-Roll"). Only the first two fences delimit the front-matter.

    Parameters
    ----------
    text : str
        The full document text.

    Returns
    -------
    tuple of (dict, str)
        The parsed front-matter mapping and the remaining body text.

    Raises
    ------
    ValueError
        If the document does not open with a ``---`` front-matter fence or the
        closing fence is missing.
    """
    normalized = text.replace("\r\n", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != _FRONT_MATTER_FENCE:
        raise ValueError("document does not begin with a '---' front-matter fence")
    closing = next(
        (i for i in range(1, len(lines)) if lines[i].strip() == _FRONT_MATTER_FENCE),
        None,
    )
    if closing is None:
        raise ValueError("front-matter is missing its closing '---' fence")
    front_text = "\n".join(lines[1:closing])
    body = "\n".join(lines[closing + 1 :])
    parsed = yaml.safe_load(front_text) or {}
    return parsed, body


class FilesystemPlanningStore:
    """A :class:`PlanningStore` backed by the repo filesystem."""

    def scaffold_unit(  # noqa: PLR0913
        self,
        unit_id: str,
        *,
        root: Path,
        intent: Intent | None = None,
        audience: str | None = None,
        title: str | None = None,
        sources: list[SourceRef] | None = None,
        steering_notes: str | None = None,
        sphinx_target: str | None = None,
        extra_targets: list[str] | None = None,
        force: bool = False,
    ) -> Path:
        """Create an editable ``unit.md`` for a new unit.

        Parameters
        ----------
        unit_id : str
            The unit identifier; must be a single safe path segment.
        root : Path
            The repo root to write beneath.
        intent : Intent or None
            Optional pre-filled Diátaxis direction.
        audience : str or None
            Optional pre-filled audience.
        title : str or None
            Optional pre-filled human-readable page title.
        sources : list of SourceRef or None
            Optional pre-filled human-pointed sources, in declared order.
        steering_notes : str or None
            Optional pre-filled free-form steering note.
        sphinx_target : str or None
            Optional docs-relative output path (subdirectories welcome, e.g.
            ``reference/definition-files/page.md``); the extension decides
            the unit's format and must be ``.md`` or ``.rst`` (v1.2). Defaults
            to ``<unit_id>.<ext>`` where the extension follows the docs
            tree's dominant page format (``.md`` when the tree is empty or
            tied). Validated eagerly so a traversing or extensionless target
            fails at declare time.
        extra_targets : list of str or None
            Additional docs-relative pages in the unit's change set (v1.2),
            validated like the primary.
        force : bool
            Overwrite an existing ``unit.md`` when ``True``.

        Returns
        -------
        Path
            The path to the written ``unit.md``.

        Raises
        ------
        ValueError
            If ``unit_id`` is unsafe (separators, ``..``, absolute) or
            ``sphinx_target`` escapes ``docs/``.
        UnsupportedTargetError
            If ``sphinx_target`` carries no supported page extension.
        UnitExistsError
            If ``unit.md`` already exists and ``force`` is ``False``.
        """
        self._reject_unsafe_unit_id(unit_id)
        if sphinx_target is not None:
            _require_page_extension(sphinx_target)
            self._resolve_docs_target(sphinx_target, root=root)
        for extra in extra_targets or []:
            _require_page_extension(extra)
            self._resolve_docs_target(extra, root=root)
        resolved_target = sphinx_target or f"{unit_id}{_dominant_page_extension(root)}"
        self._assert_targets_unclaimed(
            unit_id, [resolved_target, *(extra_targets or [])], root=root
        )
        target = self._unit_md_path(unit_id, root=root)
        self._assert_within_root(target, root=root)
        self._assert_not_under_planning(target, root=root)
        if target.exists() and not force:
            raise UnitExistsError(f"{target} exists; pass force=True to overwrite")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._seed_dogen_gitignore(root)
        target.write_text(
            self._render_unit_md(
                unit_id,
                intent=intent,
                audience=audience,
                title=title,
                sources=sources,
                steering_notes=steering_notes,
                sphinx_target=resolved_target,
                extra_targets=extra_targets,
            ),
            encoding="utf-8",
        )
        return target

    def list_unit_ids(self, *, root: Path) -> list[str]:
        """Enumerate the declared units under ``<root>/.dogen/units/``.

        Read-only: return the sorted names of the immediate subdirectories that
        contain a ``unit.md``. When the units directory does not exist yet, an
        empty list is returned and the directory is *not* created (no side
        effect), so listing an untouched repo is safe.

        Parameters
        ----------
        root : Path
            The repo root to read beneath.

        Returns
        -------
        list of str
            The declared unit ids, sorted; empty when no units exist.
        """
        units_dir = (root / _UNITS_SUBDIR).resolve()
        if not units_dir.is_dir():
            return []
        return sorted(
            entry.name for entry in units_dir.iterdir() if (entry / "unit.md").is_file()
        )

    def load_unit(self, unit_id: str, *, root: Path) -> Unit:
        """Load and validate a unit's ``unit.md`` front-matter.

        Parameters
        ----------
        unit_id : str
            The unit to load.
        root : Path
            The repo root to read beneath.

        Returns
        -------
        Unit
            The validated unit model.

        Raises
        ------
        UnitNotFoundError
            If the unit has no ``unit.md`` to load (WR-01). Raised explicitly —
            the more specific ``FileNotFoundError`` subclass ``update_unit``
            already raises — so callers (``plan_steps``/``record_step``) can
            refuse an undeclared unit as a domain not-found rather than a raw
            filesystem error.
        ValueError
            If the front-matter ``unit_id`` disagrees with the directory the
            unit was loaded from (audit-record integrity; D-36/AC5).
        """
        self._reject_unsafe_unit_id(unit_id)
        target = self._unit_md_path(unit_id, root=root)
        if not target.is_file():
            raise UnitNotFoundError(f"no such unit: {unit_id!r}")
        front, _ = split_front_matter(target.read_text(encoding="utf-8"))
        unit = Unit(**front)
        if unit.unit_id != unit_id:
            raise ValueError(
                f"unit.md declares unit_id {unit.unit_id!r} but lives under {unit_id!r}"
            )
        return unit

    def write_draft(self, unit: Unit, text: str, *, root: Path) -> Path:
        """Write a drafted page to the unit's primary Sphinx target.

        Parameters
        ----------
        unit : Unit
            The unit being drafted (provides ``sphinx_target``).
        text : str
            The page content, in the unit's format (MyST or rST).
        root : Path
            The repo root to write beneath.

        Returns
        -------
        Path
            The path to the written page under ``docs/``.
        """
        return self.write_page(unit.sphinx_target, text, root=root)

    def write_page(self, target: str, text: str, *, root: Path) -> Path:
        """Write one page of a unit's set to its docs-relative target (v1.2).

        Parameters
        ----------
        target : str
            The docs-relative page path.
        text : str
            The page content, in the page's format.
        root : Path
            The repo root to write beneath.

        Returns
        -------
        Path
            The path to the written page under ``docs/``.
        """
        resolved = self._resolve_docs_target(target, root=root)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        # Atomic (WR-03): pages are written last in the loop, after the audit
        # record is durable, and atomically so a crash never leaves a torn file.
        self._atomic_write_text(resolved, text)
        return resolved

    def read_page(self, target: str, *, root: Path) -> str:
        """Return one page's recorded text at a docs-relative target (v1.2).

        Parameters
        ----------
        target : str
            The docs-relative page path.
        root : Path
            The repo root to read beneath.

        Returns
        -------
        str
            The page's full text.
        """
        return self._resolve_docs_target(target, root=root).read_text(encoding="utf-8")

    def delete_unit(
        self,
        unit_id: str,
        *,
        root: Path,
        sphinx_target: str | None = None,
        extra_targets: list[str] | None = None,
    ) -> None:
        """Delete a unit's directory and, optionally, its drafted docs output.

        The destructive counterpart to :meth:`scaffold_unit`. Both the unit id
        and — when given — the ``sphinx_target`` are validated before *any*
        deletion, so a traversing docs target raises without touching the
        filesystem (T-INS-01): the same ``_reject_unsafe_unit_id`` +
        ``_assert_within_root`` + ``_assert_not_under_planning`` + docs
        containment the write path uses gate every path. Removing the drafted
        ``.md`` is best-effort (``missing_ok``) — an undrafted unit has none.

        Parameters
        ----------
        unit_id : str
            The unit to delete; must be a single safe path segment.
        root : Path
            The repo root to delete beneath.
        sphinx_target : str or None
            The unit's drafted docs target (relative to ``docs/``) to remove
            alongside the directory; ``None`` removes only the unit directory.
        extra_targets : list of str or None
            The unit's extra pages to remove alongside the primary (v1.2).

        Raises
        ------
        ValueError
            If ``unit_id`` is unsafe, or any docs target escapes ``docs/``.
        UnitNotFoundError
            If the unit directory does not exist.
        """
        self._reject_unsafe_unit_id(unit_id)
        # CR-01: same leaf-symlink refusal + positive subtree containment as
        # remove_staging — a symlink at .dogen/units/<id> must not redirect the
        # rmtree to a sibling in-repo directory.
        unit_dir = self._resolve_bounded_child(root / _UNITS_SUBDIR, unit_id)
        if not unit_dir.is_dir():
            raise UnitNotFoundError(f"no such unit: {unit_id!r}")
        self._assert_within_root(unit_dir, root=root)
        self._assert_not_under_planning(unit_dir, root=root)
        # Validate every docs target BEFORE any deletion so a traversing target
        # raises with zero side effects (the unit directory is left intact).
        removals = [sphinx_target] if sphinx_target is not None else []
        removals.extend(extra_targets or [])
        docs_targets = [self._resolve_docs_target(t, root=root) for t in removals]
        shutil.rmtree(unit_dir)
        for docs_target in docs_targets:
            docs_target.unlink(missing_ok=True)

    def remove_staging(self, unit_id: str, *, root: Path) -> bool:
        """Remove ``.dogen/staging/<unit_id>/`` (PROV-05); idempotent, guarded.

        The passenger-handoff scratch under ``.dogen/staging/<id>/`` is
        gitignored and fully disposable once a unit seals — its content already
        lives in ``docs/`` and the ``files[]`` digests — so a sealing
        ``review --verdict accept`` removes it (D-03/D-04) instead of leaving
        stale full-byte page duplicates behind. The delete is bounded to
        *exactly* ``(root / _STAGING_SUBDIR / unit_id)``: the same
        ``_reject_unsafe_unit_id`` + ``_assert_within_root`` +
        ``_assert_not_under_planning`` guard stack that gates
        :meth:`delete_unit` runs on the *resolved* path before ``shutil.rmtree``
        (T-INS-01 / T-09-SD), so a traversing or symlinked ``unit_id`` raises
        without touching the filesystem. Absence is a silent no-op that returns
        ``False`` — a re-accept whose scratch is already gone keeps the "a
        sealed unit => no staging scratch" invariant intact (D-03). ``rmtree``
        has no ``missing_ok``; the ``is_dir()`` check is the idempotence gate,
        and ``ignore_errors`` is deliberately *not* passed so a real permission
        failure surfaces rather than being masked.

        Parameters
        ----------
        unit_id : str
            The unit whose staging scratch to remove; a single safe path
            segment.
        root : Path
            The repo root to delete beneath.

        Returns
        -------
        bool
            ``True`` when a staging directory was removed, ``False`` when none
            existed (the idempotent no-op).

        Raises
        ------
        ValueError
            If ``unit_id`` is unsafe, or the resolved path escapes the repo root
            or lands under ``.planning/``.
        """
        self._reject_unsafe_unit_id(unit_id)
        # CR-01: bind the delete to exactly one child of .dogen/staging/ and
        # refuse a symlinked leaf, so a symlink at .dogen/staging/<id> pointing
        # at a sibling in-repo dir (docs/) or the repo root cannot widen the
        # rmtree. The stale _assert_within_root/_assert_not_under_planning stack
        # permitted that redirect (it only barred escaping the root / .planning).
        staging_dir = self._resolve_bounded_child(root / _STAGING_SUBDIR, unit_id)
        self._assert_within_root(staging_dir, root=root)
        self._assert_not_under_planning(staging_dir, root=root)
        if not staging_dir.is_dir():
            return False
        shutil.rmtree(staging_dir)
        return True

    def rename_unit(self, old_id: str, new_id: str, *, root: Path) -> None:
        """Rename a unit's id everywhere, rollback-safe (unit mv).

        Rewrites ``unit_id`` in ``unit.md`` + ``provenance.yaml`` (lifecycle
        state is derived from provenance, so nothing else travels with the
        rename), re-derives ``sphinx_target``'s **basename** to
        ``<new_id><ext>`` only when it was the id-derived ``<old_id><ext>``
        (the extension — the unit's format — survives, as do a custom basename
        set via ``--target`` and the directory portion), and moves the draft
        accordingly — preserving every
        other field and the hand-edited ``unit.md`` body verbatim (the body is
        *not* re-templated). The ordering is build-new-then-remove-old so a mid-failure
        never leaves a half-renamed unit (T-INS-03): all guards run before any
        mutation, the old directory stays canonical until the new one is fully
        built, and a partially-built new directory is cleaned up on failure.

        Parameters
        ----------
        old_id : str
            The current unit id; must be a single safe path segment.
        new_id : str
            The target unit id; must be a single safe path segment.
        root : Path
            The repo root to operate beneath.

        Raises
        ------
        ValueError
            If either id is unsafe, or a docs target escapes ``docs/``.
        UnitNotFoundError
            If the source unit directory does not exist.
        UnitExistsError
            If the target unit directory already exists.
        """
        self._reject_unsafe_unit_id(old_id)
        self._reject_unsafe_unit_id(new_id)
        # CR-01: bind both endpoints to a direct child of .dogen/units/ and
        # refuse a symlinked leaf, so neither the source (rmtree'd last) nor a
        # pre-existing symlink at the destination can redirect the operation
        # outside the units subtree.
        old_dir = self._resolve_bounded_child(root / _UNITS_SUBDIR, old_id)
        new_dir = self._resolve_bounded_child(root / _UNITS_SUBDIR, new_id)
        if not old_dir.is_dir():
            raise UnitNotFoundError(f"no such unit: {old_id!r}")
        if new_dir.exists():
            raise UnitExistsError(f"unit already exists: {new_id!r}")
        for path in (old_dir, new_dir):
            self._assert_within_root(path, root=root)
            self._assert_not_under_planning(path, root=root)
        # Read the old state into memory; the old dir stays canonical until the
        # new dir is fully built below.
        front, body = split_front_matter(
            (old_dir / "unit.md").read_text(encoding="utf-8")
        )
        old_sphinx = front.get("sphinx_target")
        prov_text = self._read_if_exists(old_dir / "provenance.yaml")
        try:
            new_dir.mkdir(parents=True, exist_ok=False)
            # Patch only unit_id + sphinx_target; preserve every other front-matter
            # field and the hand-edited body verbatim (do NOT re-template).
            # Basename rule: re-derive to <new_id><ext> only when the old basename
            # was the id-derived <old_id><ext> — the extension (format, v1.2)
            # survives the rename, as do a custom basename (set via --target)
            # and the directory portion.
            front["unit_id"] = new_id
            new_sphinx = old_sphinx or f"{new_id}.md"
            if old_sphinx:
                old_pure = PurePosixPath(old_sphinx)
                basename = (
                    f"{new_id}{old_pure.suffix}"
                    if old_pure.stem == old_id
                    else old_pure.name
                )
                new_sphinx = str(old_pure.parent / basename)
            front["sphinx_target"] = new_sphinx
            front_yaml = yaml.safe_dump(front, sort_keys=False).rstrip("\n")
            fence = _FRONT_MATTER_FENCE
            self._atomic_write_text(
                new_dir / "unit.md", f"{fence}\n{front_yaml}\n{fence}\n{body}"
            )
            self._rewrite_unit_id_yaml(prov_text, new_dir / "provenance.yaml", new_id)
            # Move the drafted output if present, under the same containment checks.
            if old_sphinx:
                old_docs = self._resolve_docs_target(old_sphinx, root=root)
                new_docs = self._resolve_docs_target(new_sphinx, root=root)
                if old_docs != new_docs and old_docs.exists():
                    new_docs.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(old_docs, new_docs)
        except BaseException:
            # Roll back a partially-built new dir; the old unit stays canonical.
            shutil.rmtree(new_dir, ignore_errors=True)
            raise
        # Remove the old dir last, once the new one is fully built.
        shutil.rmtree(old_dir)

    @staticmethod
    def _read_if_exists(path: Path) -> str | None:
        """Return a file's text, or ``None`` when it does not exist.

        Parameters
        ----------
        path : Path
            The file to read.

        Returns
        -------
        str or None
            The file content, or ``None`` when the file is absent.
        """
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _rewrite_unit_id_yaml(
        self, text: str | None, target: Path, new_id: str
    ) -> None:
        """Re-stamp ``unit_id`` in a machine YAML and write it to ``target``.

        Parses the source YAML text, sets ``unit_id`` to ``new_id`` while
        preserving every other key (generations, steering, history, state), and
        atomically writes it. A ``None`` source (the file did not exist for the
        old unit) is a no-op, so an un-steered/un-drafted unit renames cleanly.

        Parameters
        ----------
        text : str or None
            The source YAML text, or ``None`` when the source file was absent.
        target : Path
            The destination path in the new unit directory.
        new_id : str
            The new unit id to stamp.
        """
        if text is None:
            return
        data = yaml.safe_load(text) or {}
        data["unit_id"] = new_id
        self._atomic_write_text(target, yaml.safe_dump(data, sort_keys=False))

    def read_provenance(self, unit_id: str, *, root: Path) -> Provenance:
        """Load a unit's provenance record.

        Parameters
        ----------
        unit_id : str
            The unit to read.
        root : Path
            The repo root to read beneath.

        Returns
        -------
        Provenance
            The validated provenance model.

        Raises
        ------
        FileNotFoundError
            When the sidecar is absent (unchanged — maps to ``unit_not_found``).
        SchemaUnsupportedError
            When the record declares a ``schema_version`` newer than
            :data:`~dogen.core.models.SCHEMA_VERSION` (D-08). Raised at the
            loader boundary, before model construction, so the refusal is not a
            best-effort read of an unknown shape.
        ProvenanceInvalidError
            When the record is present but fails Pydantic validation (D-09),
            carrying the validation-error location so a corrupt sidecar refuses
            cleanly rather than surfacing as ``unit_not_found``.
        """
        # CR-01: normalize EVERY unreadable-record shape to a tolerated
        # ValueError subclass so the WR-01 scan loaders (which skip
        # SchemaUnsupportedError/ProvenanceInvalidError) cover them. A
        # syntactically-broken sidecar raises yaml.YAMLError (NOT a ValueError),
        # and a valid-but-non-mapping top level (a list/scalar) has no ``.get``
        # — both previously escaped every tolerant handler and wedged the scan.
        try:
            raw = self._read_yaml(unit_id, "provenance.yaml", root=root)
        except yaml.YAMLError as exc:
            raise ProvenanceInvalidError(
                unit_id, detail=f"not valid YAML: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise ProvenanceInvalidError(
                unit_id,
                detail=f"provenance.yaml is not a mapping (got {type(raw).__name__})",
            )
        # D-08: gate on the declared version BEFORE Provenance(**raw). The gate
        # must live here (not in a model_validator) so a future version yields
        # the distinct schema_unsupported reason rather than collapsing into a
        # ValidationError -> provenance_invalid.
        found = raw.get("schema_version", 1)
        # WR-03: coerce the declared version before the comparison. A stringified
        # or float version (``"999"``, ``2.0``) is otherwise not an ``int``, so
        # the D-08 gate was skipped and a future record read best-effort and
        # silently downgraded by ``_migrate``. Refuse a non-coercible version
        # rather than fall through.
        try:
            found = int(found)
        except (TypeError, ValueError) as exc:
            raise ProvenanceInvalidError(
                unit_id, detail=f"non-numeric schema_version {found!r}"
            ) from exc
        if found > SCHEMA_VERSION:
            raise SchemaUnsupportedError(found, SCHEMA_VERSION)
        try:
            return Provenance(**raw)
        except ValidationError as exc:
            raise ProvenanceInvalidError(unit_id, detail=str(exc)) from exc

    def write_provenance(self, provenance: Provenance, *, root: Path) -> Path:
        """Persist a unit's provenance record.

        Parameters
        ----------
        provenance : Provenance
            The provenance model to serialize.
        root : Path
            The repo root to write beneath.

        Returns
        -------
        Path
            The path to the written ``provenance.yaml``.
        """
        path = self._write_yaml(
            provenance.unit_id, "provenance.yaml", provenance, root=root
        )
        # D-01/D-02: silently drop any stale sibling progress.yaml. State is now
        # derived from provenance (PROV-04), so the second stored artefact is
        # never kept — a pre-existing one self-cleans on the next write, riding
        # the verb's own transition commit (no narration). The target is derived
        # from ``path.parent`` of the guarded write above, so it inherits
        # ``_reject_unsafe_unit_id`` / ``_assert_within_root`` (never a fresh
        # unit_id join); ``missing_ok`` avoids a TOCTOU exists-check.
        (path.parent / "progress.yaml").unlink(missing_ok=True)
        return path

    def read_unit_text(self, unit_id: str, *, root: Path) -> str:
        """Return the full raw text of a unit's ``unit.md`` (v1).

        Parameters
        ----------
        unit_id : str
            The unit to read.
        root : Path
            The repo root to read beneath.

        Returns
        -------
        str
            The complete ``unit.md`` document text.
        """
        self._reject_unsafe_unit_id(unit_id)
        return self._unit_md_path(unit_id, root=root).read_text(encoding="utf-8")

    def update_unit(  # noqa: PLR0913
        self,
        unit_id: str,
        *,
        root: Path,
        intent: Intent | None = None,
        audience: str | None = None,
        title: str | None = None,
        add_sources: list[SourceRef] | None = None,
        remove_sources: list[str] | None = None,
        steering_notes: str | None = None,
        body: str | None = None,
        sphinx_target: str | None = None,
        add_targets: list[str] | None = None,
        drop_targets: list[str] | None = None,
    ) -> Path:
        """Merge changes into an existing ``unit.md``, never clobbering (v1).

        Only the named fields change; every other front-matter field and the
        hand-edited body are preserved verbatim (the Q3 merge decision — the
        amend counterpart to :meth:`scaffold_unit`'s explicit ``force``
        re-scaffold). The patched front-matter is re-validated through the
        :class:`Unit` model before anything is written.

        Parameters
        ----------
        unit_id : str
            The unit to update.
        root : Path
            The repo root to write beneath.
        intent : Intent or None
            Replacement Diátaxis direction; ``None`` leaves it unchanged.
        audience : str or None
            Replacement audience; ``None`` leaves it unchanged.
        title : str or None
            Replacement title; ``None`` leaves it unchanged.
        add_sources : list of SourceRef or None
            Sources appended to the declared set (entries whose path/ref is
            already declared are skipped).
        remove_sources : list of str or None
            Source paths/refs removed from the declared set.
        steering_notes : str or None
            Replacement seeded steering note; ``None`` leaves it unchanged.
        body : str or None
            Replacement plan body (everything below the front matter);
            ``None`` preserves the existing body verbatim. This is the
            delegable persistence path for the outline/acceptance sections —
            Write/Edit-free skills pipe the TA-approved body through the CLI
            instead of asking the TA to hand-edit ``unit.md``.
        sphinx_target : str or None
            Replacement docs-relative output path; ``None`` leaves it
            unchanged. Validated eagerly (assignment would bypass the model's
            containment validator). When a draft already exists at the old
            target it is **moved** to the new one — the delegable "move the
            page" path a reviewer can order without hand git-mv'ing.
        add_targets : list of str or None
            Extra pages appended to the unit's change set (v1.2; entries
            already in the set are skipped).
        drop_targets : list of str or None
            Extra pages removed from the set (v1.2; de-scope only — the
            on-disk page is never touched; dropping the primary raises).

        Returns
        -------
        Path
            The path to the rewritten ``unit.md``.

        Raises
        ------
        UnitNotFoundError
            If the unit has no ``unit.md`` to update.
        UnitExistsError
            If a file already exists at the new ``sphinx_target``.
        UnsupportedTargetError
            If a new or added target carries no supported page extension.
        ValueError
            If the id is unsafe, the patched front-matter fails validation,
            or any target escapes ``docs/``.
        """
        self._reject_unsafe_unit_id(unit_id)
        target = self._unit_md_path(unit_id, root=root)
        if not target.is_file():
            raise UnitNotFoundError(f"no such unit: {unit_id!r}")
        front, existing_body = split_front_matter(target.read_text(encoding="utf-8"))
        unit = Unit(**front)
        if intent is not None:
            unit.intent = intent
        if audience is not None:
            unit.audience = audience
        if title is not None:
            unit.title = title
        if steering_notes is not None:
            unit.steering_notes = steering_notes
        self._merge_sources(unit, add_sources, remove_sources)
        self._merge_targets(unit, add_targets, drop_targets)
        move = self._plan_target_change(unit, sphinx_target, root=root)
        # Re-validate the whole patched model: field assignment above bypasses
        # the containment validator, and added extras must pass it too.
        unit = Unit(**unit.model_dump(mode="json"))
        self._assert_targets_unclaimed(unit_id, unit.targets, root=root)
        body = body.strip("\n") + "\n" if body is not None else existing_body
        front_yaml = yaml.safe_dump(self._dump_unit_front(unit), sort_keys=False)
        fence = _FRONT_MATTER_FENCE
        if move is not None:
            move[1].parent.mkdir(parents=True, exist_ok=True)
            os.replace(move[0], move[1])
        try:
            self._atomic_write_text(
                target, f"{fence}\n{front_yaml.rstrip()}\n{fence}\n{body}"
            )
        except BaseException:
            if move is not None:
                os.replace(move[1], move[0])
            raise
        return target

    @staticmethod
    def _merge_sources(
        unit: Unit,
        add_sources: list[SourceRef] | None,
        remove_sources: list[str] | None,
    ) -> None:
        """Apply the Q3 merge semantics to ``unit.sources`` in place.

        Parameters
        ----------
        unit : Unit
            The loaded unit whose source list is patched.
        add_sources : list of SourceRef or None
            Sources appended (entries whose path/ref is already declared are
            skipped).
        remove_sources : list of str or None
            Source paths/refs removed from the declared set.
        """
        sources = list(unit.sources)
        if remove_sources:
            targets = set(remove_sources)
            sources = [s for s in sources if (s.path or s.ref) not in targets]
        for candidate in add_sources or []:
            if (candidate.path or candidate.ref) not in {
                s.path or s.ref for s in sources
            }:
                sources.append(candidate)
        unit.sources = sources

    @staticmethod
    def _merge_targets(
        unit: Unit,
        add_targets: list[str] | None,
        drop_targets: list[str] | None,
    ) -> None:
        """Apply the v1.2 merge semantics to ``unit.extra_targets`` in place.

        Adds are validated for a supported page extension here (containment is
        re-checked by the model re-validation in :meth:`update_unit`); drops
        de-scope only — the on-disk page is never touched, and the primary
        cannot be dropped.

        Parameters
        ----------
        unit : Unit
            The loaded unit whose target set is patched.
        add_targets : list of str or None
            Extra pages appended (entries already in the set are skipped).
        drop_targets : list of str or None
            Extra pages removed from the set.

        Raises
        ------
        UnsupportedTargetError
            If an added target carries no supported page extension.
        ValueError
            If a drop names the primary target.
        """
        extras = list(unit.extra_targets)
        if drop_targets:
            dropped = set(drop_targets)
            if unit.sphinx_target in dropped:
                raise ValueError(
                    "cannot drop the primary target — repoint it with --target"
                )
            extras = [t for t in extras if t not in dropped]
        for candidate in add_targets or []:
            _require_page_extension(candidate)
            if candidate != unit.sphinx_target and candidate not in extras:
                extras.append(candidate)
        unit.extra_targets = extras

    def _read_provenance_tolerant(
        self, unit_id: str, *, root: Path
    ) -> Provenance | None:
        """Load a neighbour's provenance for a lease scan, tolerating corruption.

        The adapter-side WR-01 loader (mirrors the orchestrator's
        ``_scan_load_provenance``): a repo-wide lease scan reads *every*
        overlapping neighbour's ``provenance.yaml``, so one schema-newer or
        malformed sidecar must never abort an unrelated declare/edit. Returns
        ``None`` for an absent (declared-but-not-drafted) or unreadable record;
        the corruption case emits a one-line ``stderr`` warning naming the
        skipped unit.

        Parameters
        ----------
        unit_id : str
            The neighbour whose provenance is loaded.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        Provenance or None
            The loaded record, or ``None`` when it is absent or unreadable.
        """
        try:
            return self.read_provenance(unit_id, root=root)
        except FileNotFoundError:
            return None
        except (SchemaUnsupportedError, ProvenanceInvalidError) as exc:
            print(
                f"warning: skipping unit {unit_id!r} from the lease scan "
                f"(unreadable provenance): {exc}",
                file=sys.stderr,
            )
            return None

    def _load_unit_tolerant(self, unit_id: str, *, root: Path) -> Unit | None:
        """Load a neighbour's ``unit.md`` for a lease scan, tolerating corruption.

        The WR-01 counterpart to :meth:`_read_provenance_tolerant`, one step
        earlier in every scan loop: a repo-wide lease scan reads *every*
        neighbour's ``unit.md`` to test target overlap, and ``list_unit_ids``
        only guarantees the file *exists*, not that it parses. ``load_unit``
        raises :class:`ValueError` on a malformed neighbour (a missing/duplicated
        front-matter fence via ``split_front_matter``, a failed :class:`Unit`
        validation, or the ``unit_id``/directory-mismatch check). A single such
        poisoned neighbour must never abort an unrelated declare/edit/draft.

        A neighbour whose ``unit.md`` cannot be parsed cannot be proven to
        overlap the claimed pages, so it is skipped (returns ``None``) with a
        one-line ``stderr`` warning — the conservative, non-aborting choice.

        Parameters
        ----------
        unit_id : str
            The neighbour whose ``unit.md`` is loaded.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        Unit or None
            The loaded unit, or ``None`` when it is absent or unreadable.
        """
        try:
            return self.load_unit(unit_id, root=root)
        except (FileNotFoundError, ValueError) as exc:
            print(
                f"warning: skipping unit {unit_id!r} from the lease scan "
                f"(unreadable unit.md): {exc}",
                file=sys.stderr,
            )
            return None

    def _assert_targets_unclaimed(
        self, unit_id: str, targets: list[str], *, root: Path
    ) -> None:
        """Refuse a target set overlapping an *in-flight* owner's pages (D-01).

        Ownership is a **lease** (Phase 7): an overlap is a conflict only while
        the overlapping owner is *in flight*. This scans every other declared
        unit whose ``unit.targets`` overlap ``targets`` (primary and extras
        alike — OWN-06) and splits on :func:`~dogen.core.models.is_sealed`:

        * an **in-flight** owner (readable provenance whose latest verdict is not
          ``accept``) still refuses — :class:`TargetClaimedError` names the owner
          and its derived state ("claimed by in-flight unit 'x' (drafted, not
          accepted)");
        * a **sealed** owner is *not* a conflict here — the claim is allowed and
          its supersede is recorded separately by :meth:`plan_takeovers`.

        A neighbour whose provenance is absent (declared-but-not-drafted) or
        unreadable (schema-newer/corrupt) is skipped WR-01-tolerantly: it cannot
        be proven in-flight from a record, so it never aborts an unrelated
        declare/edit (a corrupt sidecar must not wedge every future claim).

        Parameters
        ----------
        unit_id : str
            The unit being declared or amended (excluded from the scan).
        targets : list of str
            The unit's prospective full page set (primary + extras).
        root : Path
            The repo root.

        Raises
        ------
        TargetClaimedError
            If any overlapping owner is in-flight (holds its lease).
        """
        claimed = set(targets)
        for other_id in self.list_unit_ids(root=root):
            if other_id == unit_id:
                continue
            other = self._load_unit_tolerant(other_id, root=root)
            if other is None:
                # WR-01: a malformed neighbour unit.md cannot be proven to
                # overlap, so it never aborts this scan (skip, warned).
                continue
            overlap = claimed.intersection(other.targets)
            if not overlap:
                continue
            prov = self._read_provenance_tolerant(other_id, root=root)
            if prov is None or is_sealed(prov):
                # Absent/unreadable ⇒ cannot prove in-flight (WR-01 skip);
                # sealed ⇒ lease released, superseded via plan_takeovers.
                continue
            raise TargetClaimedError(
                f"docs target(s) claimed by in-flight unit {other_id!r} "
                f"({_in_flight_detail(prov)}): " + ", ".join(sorted(overlap))
            )

    def assert_draft_targets_unclaimed(
        self, unit_id: str, targets: list[str], *, root: Path
    ) -> None:
        """Draft-time lease re-check (OWN-03/D-03): refuse an in-flight overlap.

        The draft-time half of the lease reuses the exact declare/edit scan:
        :meth:`_assert_targets_unclaimed` already refuses only an *in-flight*
        overlapping owner (naming it + its derived state), allows a *sealed* one,
        and skips an absent/unreadable neighbour WR-01-tolerantly. Calling it
        here — after a sealed owner may have reopened (D-02) — closes the reverse
        hole: a competitor that took the page while it was sealed is now refused
        at draft time via :class:`TargetClaimedError`.

        Parameters
        ----------
        unit_id : str
            The unit about to draft (excluded from the scan).
        targets : list of str
            The unit's full docs-relative page set (primary + extras).
        root : Path
            The repo root.

        Raises
        ------
        TargetClaimedError
            If any overlapping owner is in-flight (holds its lease).
        """
        self._assert_targets_unclaimed(unit_id, targets, root=root)

    def plan_takeovers(
        self, unit_id: str, targets: list[str], *, root: Path
    ) -> list[Takeover]:
        """Plan the supersede edges a claim records over sealed owners (D-04/D-05).

        The read-only companion to the write guard: after the unit is written,
        its final target set is re-scanned. An in-flight overlap has already been
        refused by :meth:`_assert_targets_unclaimed`, so every remaining
        overlapping owner is *sealed* and may be superseded. Per page, the
        newest-accept sealed owner wins (:func:`_latest_accept_at` ordering, tie
        by smaller unit id — the same D-04 order as ``resolve_owners``, delegated
        to the shared derivation so the two cannot disagree). A corrupt/absent
        neighbour is skipped WR-01-tolerantly.

        The deliberate second neighbour scan (the guard scans first) is the trade
        for keeping ``scaffold_unit``/``update_unit`` return types stable.

        Parameters
        ----------
        unit_id : str
            The claiming unit (excluded from the scan).
        targets : list of str
            The unit's final docs-relative page set (primary + extras).
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        list of Takeover
            One supersede edge per superseded sealed page, page-sorted.
        """
        claimed = set(targets)
        # page -> (owner_id, accept_at, accept_edit) for the newest-accept owner.
        best: dict[str, tuple[str, datetime, ReviewerEdit]] = {}
        for other_id in self.list_unit_ids(root=root):
            if other_id == unit_id:
                continue
            other = self._load_unit_tolerant(other_id, root=root)
            if other is None:
                # WR-01: a malformed neighbour unit.md cannot be proven to
                # overlap, so it never aborts takeover planning (skip, warned).
                continue
            overlap = claimed.intersection(other.targets)
            if not overlap:
                continue
            prov = self._read_provenance_tolerant(other_id, root=root)
            if prov is None or not is_sealed(prov):
                continue
            accept_edit = _latest_accept_edit(prov)
            accept_at = _latest_accept_at(prov)
            if accept_edit is None or accept_at is None:
                continue  # sealed always carries an accept — defensive guard.
            for page in overlap:
                current = best.get(page)
                if (
                    current is None
                    or accept_at > current[1]
                    or (accept_at == current[1] and other_id < current[0])
                ):
                    best[page] = (other_id, accept_at, accept_edit)
        return sorted(
            (
                Takeover(
                    page=page,
                    owner_id=owner_id,
                    sealed_sha12=_page_sha12(accept_edit, page),
                    accept_at=accept_edit.at,
                )
                for page, (owner_id, _at, accept_edit) in best.items()
            ),
            key=lambda takeover: takeover.page,
        )

    @staticmethod
    def _dump_unit_front(unit: Unit) -> dict:
        """Serialize a unit's front-matter, omitting an empty target set.

        Keeps the ordinary one-page unit's ``unit.md`` byte-stable across the
        v1.2 field addition: ``extra_targets`` appears only when the unit
        actually spans extra pages.

        Parameters
        ----------
        unit : Unit
            The validated unit to serialize.

        Returns
        -------
        dict
            The JSON-mode mapping for YAML dumping.
        """
        front = unit.model_dump(mode="json")
        if not front.get("extra_targets"):
            front.pop("extra_targets", None)
        return front

    def _plan_target_change(
        self, unit: Unit, sphinx_target: str | None, *, root: Path
    ) -> tuple[Path, Path] | None:
        """Validate a target repoint and plan the draft move (mutates ``unit``).

        Validation is eager and explicit: attribute assignment bypasses the
        model's containment validator, so ``_resolve_docs_target`` is the real
        guard here. A destination clobber is refused before any mutation.

        Parameters
        ----------
        unit : Unit
            The loaded unit; its ``sphinx_target`` is updated in place when a
            change is requested.
        sphinx_target : str or None
            The requested docs-relative target; ``None``/unchanged is a no-op.
        root : Path
            The repo root.

        Returns
        -------
        tuple of (Path, Path) or None
            The (old, new) resolved draft paths to move, or ``None`` when no
            file move is needed.

        Raises
        ------
        UnitExistsError
            If a file already exists at the new target.
        UnsupportedTargetError
            If the new target carries no supported page extension.
        ValueError
            If either target escapes ``docs/``.
        """
        if sphinx_target is None or sphinx_target == unit.sphinx_target:
            return None
        _require_page_extension(sphinx_target)
        old_docs = self._resolve_docs_target(unit.sphinx_target, root=root)
        new_docs = self._resolve_docs_target(sphinx_target, root=root)
        unit.sphinx_target = sphinx_target
        if not old_docs.exists():
            return None
        if new_docs.exists():
            raise UnitExistsError(f"a file already exists at docs/{sphinx_target}")
        return (old_docs, new_docs)

    def read_draft(self, unit: Unit, *, root: Path) -> str:
        """Return the recorded draft text at the unit's Sphinx target (v1).

        Parameters
        ----------
        unit : Unit
            The unit whose draft is read (provides ``sphinx_target``).
        root : Path
            The repo root to read beneath.

        Returns
        -------
        str
            The draft's full text.
        """
        target = self._resolve_docs_target(unit.sphinx_target, root=root)
        return target.read_text(encoding="utf-8")

    def read_config(self, *, root: Path) -> DogenConfig:
        """Load ``.dogen/config.yaml``, returning defaults when absent (v1).

        Parameters
        ----------
        root : Path
            The repo root to read beneath.

        Returns
        -------
        DogenConfig
            The validated config; the model defaults (``host-harness``
            provider, ``auto`` commits) when no file exists.
        """
        path = (root / _CONFIG_RELPATH).resolve()
        if not path.is_file():
            return DogenConfig()
        return DogenConfig(**(yaml.safe_load(path.read_text(encoding="utf-8")) or {}))

    def write_config(self, config: DogenConfig, *, root: Path) -> Path:
        """Persist ``.dogen/config.yaml`` (v1).

        Parameters
        ----------
        config : DogenConfig
            The config model to serialize.
        root : Path
            The repo root to write beneath.

        Returns
        -------
        Path
            The path to the written ``config.yaml``.
        """
        target = (root / _CONFIG_RELPATH).resolve()
        self._assert_within_root(target, root=root)
        self._assert_not_under_planning(target, root=root)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_text(
            target, yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False)
        )
        return target

    def list_context(self, *, root: Path) -> list[str]:
        """Enumerate the context artifacts under ``.dogen/context/`` (v1).

        Parameters
        ----------
        root : Path
            The repo root to read beneath.

        Returns
        -------
        list of str
            The artifact filenames present, sorted; empty when none exist.
        """
        context_dir = (root / _CONTEXT_SUBDIR).resolve()
        if not context_dir.is_dir():
            return []
        return sorted(entry.name for entry in context_dir.iterdir() if entry.is_file())

    def add_context(self, name: str, text: str, *, root: Path) -> Path:
        """File a context artifact into ``.dogen/context/<name>`` (v1).

        Parameters
        ----------
        name : str
            The artifact filename; must be a single safe path segment.
        text : str
            The artifact's full content, landed as-is (free-form welcome).
        root : Path
            The repo root to write beneath.

        Returns
        -------
        Path
            The path to the written artifact.

        Raises
        ------
        ValueError
            If ``name`` is not a single safe path segment.
        """
        self._reject_unsafe_unit_id(name)
        target = (root / _CONTEXT_SUBDIR / name).resolve()
        self._assert_within_root(target, root=root)
        self._assert_not_under_planning(target, root=root)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._seed_dogen_gitignore(root)
        self._atomic_write_text(target, text)
        return target

    @staticmethod
    def _seed_dogen_gitignore(root: Path) -> None:
        """Seed ``.dogen/.gitignore`` (``staging/``) into a target repo, once.

        Passenger staging scratch (``.dogen/staging/<unit>/``) is deliberately
        left on disk for inspection but must never be swept into a human's
        ``git add .`` commit. dogen owns ``.dogen/``, so it seeds the scoped
        ignore the first time it writes beneath the directory; an existing
        file (operator-tuned or already seeded) is never touched.

        Parameters
        ----------
        root : Path
            The repo root to seed beneath.
        """
        ignore = root / _DOGEN_GITIGNORE_RELPATH
        if ignore.exists():
            return
        ignore.parent.mkdir(parents=True, exist_ok=True)
        ignore.write_text(_DOGEN_GITIGNORE_CONTENT, encoding="utf-8")

    @staticmethod
    def _atomic_write_text(target: Path, text: str) -> None:
        """Write ``text`` to ``target`` atomically (temp-then-rename, WR-03).

        A torn write (disk full, interrupt) must never leave a half-written
        audit file: the content is written to a temp file in the same directory,
        flushed and fsynced, then ``os.replace``-d over the target — an atomic
        rename on the same filesystem. A failure leaves the prior file intact.

        Parameters
        ----------
        target : Path
            The destination path (its parent must already exist).
        text : str
            The full file content to write.
        """
        fd, tmp_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, target)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _reject_unsafe_unit_id(unit_id: str) -> None:
        """Reject a unit id that is not a single safe path segment (T-02.1-01).

        Parameters
        ----------
        unit_id : str
            The candidate identifier.

        Raises
        ------
        ValueError
            If the id is empty, ``..``, absolute, or contains a path separator.
        """
        if not unit_id or unit_id in {".", ".."}:
            raise ValueError(f"invalid unit id: {unit_id!r}")
        if "/" in unit_id or "\\" in unit_id or Path(unit_id).name != unit_id:
            raise ValueError(f"unit id must be a single path segment: {unit_id!r}")

    @staticmethod
    def _resolve_bounded_child(subtree: Path, name: str) -> Path:
        """Resolve ``<subtree>/<name>`` bound to the subtree, refusing a symlink leaf.

        Binds a destructive op (``shutil.rmtree``/``os.replace``) to *exactly*
        one direct child of a resolved subtree root (CR-01 / T-09-SD). The stale
        guard stack (``_assert_within_root`` + ``_assert_not_under_planning``)
        resolved the leaf *before* checking it and only forbade escaping the
        repo root or landing under ``.planning/`` — a symlink at the leaf that
        redirected to a *sibling inside the root* (e.g. ``docs/`` or the repo
        root itself) therefore passed, and ``rmtree`` followed it. This helper
        closes that hole with two positive controls:

        1. **Refuse a symlinked leaf outright** — resolved *before* following it,
           so we never ``rmtree``/``replace`` *through* a symlink.
        2. **Positive containment** — the resolved child must live *directly*
           under the resolved subtree root, so it cannot resolve elsewhere.

        The parent (never the final component) is what gets resolved, so a
        legitimate, non-symlink, properly-contained child behaves exactly as the
        old ``(subtree / name).resolve()`` did — backward-compatible for the
        existing ``delete_unit`` / ``rename_unit`` callers and their tests.

        Parameters
        ----------
        subtree : Path
            The trusted subtree root the child must live directly beneath (e.g.
            ``root / _STAGING_SUBDIR`` or ``root / _UNITS_SUBDIR``).
        name : str
            The single-segment child name (an already-``_reject_unsafe_unit_id``
            -validated unit id).

        Returns
        -------
        Path
            The resolved child path, guaranteed a direct child of ``subtree``.

        Raises
        ------
        ValueError
            If the leaf is a symlink, or the resolved child does not live
            directly under the resolved subtree root.
        """
        subtree_root = subtree.resolve()
        candidate = subtree_root / name
        if candidate.is_symlink():
            raise ValueError(f"refusing to act through a symlinked path: {name!r}")
        resolved = candidate.resolve()
        if resolved.parent != subtree_root:
            raise ValueError(f"path escapes {subtree}: {name!r}")
        return resolved

    def _resolve_docs_target(self, sphinx_target: str, *, root: Path) -> Path:
        """Resolve a ``docs/``-relative target and enforce containment (CR-01).

        The single positive-containment check shared by the draft write and the
        lifecycle delete/rename paths: the resolved target must be ``docs/``
        itself or live beneath it. ``Path.resolve`` collapses ``..`` first, so a
        target such as ``../../escape.md`` is rejected here rather than acted on
        outside the repo. The ``.planning/`` and root guards remain as
        defense-in-depth.

        Parameters
        ----------
        sphinx_target : str
            The docs-relative output path to resolve.
        root : Path
            The repo root.

        Returns
        -------
        Path
            The resolved, contained target under ``<root>/docs/``.

        Raises
        ------
        ValueError
            If the target escapes ``docs/``, the repo root, or lands under
            ``.planning/``.
        """
        docs_root = (root / "docs").resolve()
        target = (docs_root / sphinx_target).resolve()
        if target != docs_root and docs_root not in target.parents:
            raise ValueError(f"sphinx_target escapes docs/: {sphinx_target!r}")
        self._assert_within_root(target, root=root)
        self._assert_not_under_planning(target, root=root)
        return target

    def _unit_md_path(self, unit_id: str, *, root: Path) -> Path:
        """Return the resolved ``unit.md`` path for a unit.

        Parameters
        ----------
        unit_id : str
            The (already-validated) unit id.
        root : Path
            The repo root.

        Returns
        -------
        Path
            The resolved ``<root>/.dogen/units/<id>/unit.md`` path.
        """
        return (root / _UNITS_SUBDIR / unit_id / "unit.md").resolve()

    @staticmethod
    def _assert_within_root(target: Path, *, root: Path) -> None:
        """Refuse to write anywhere outside ``root`` (WR-01; T-02.1-01).

        The positive containment that pairs with
        :meth:`_assert_not_under_planning`: every write target must be ``root``
        itself or live beneath it. This is the primary control; the
        ``.planning/`` guard is then a narrower, defense-in-depth check.

        Parameters
        ----------
        target : Path
            The resolved write target.
        root : Path
            The repo root.

        Raises
        ------
        ValueError
            If ``target`` resolves outside ``<root>/``.
        """
        resolved_root = root.resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise ValueError(f"refusing to write outside the repo root: {target}")

    @staticmethod
    def _assert_not_under_planning(target: Path, *, root: Path) -> None:
        """Refuse to write anywhere under ``.planning/`` (D-30; T-02.1-01).

        Parameters
        ----------
        target : Path
            The resolved write target.
        root : Path
            The repo root.

        Raises
        ------
        ValueError
            If ``target`` resolves under ``<root>/.planning/``.
        """
        forbidden = (root / _FORBIDDEN_OUTPUT_ROOT).resolve()
        if target == forbidden or forbidden in target.parents:
            raise ValueError(f"refusing to write under {_FORBIDDEN_OUTPUT_ROOT}/")

    def _render_unit_md(  # noqa: PLR0913
        self,
        unit_id: str,
        *,
        intent: Intent | None,
        audience: str | None,
        title: str | None = None,
        sources: list[SourceRef] | None = None,
        steering_notes: str | None = None,
        sphinx_target: str | None = None,
        extra_targets: list[str] | None = None,
    ) -> str:
        """Render the ``unit.md`` template (front-matter + body skeleton).

        Parameters
        ----------
        unit_id : str
            The unit id.
        intent : Intent or None
            Optional pre-filled intent.
        audience : str or None
            Optional pre-filled audience.
        title : str or None
            Optional pre-filled human-readable page title.
        sources : list of SourceRef or None
            Optional pre-filled human-pointed sources, in declared order.
        steering_notes : str or None
            Optional pre-filled free-form steering note.
        sphinx_target : str or None
            Optional docs-relative output path; defaults to ``<unit_id>.md``.
        extra_targets : list of str or None
            Additional pages in the unit's change set (v1.2); omitted from
            the front-matter when empty.

        Returns
        -------
        str
            The full ``unit.md`` document text.
        """
        unit = Unit(
            unit_id=unit_id,
            intent=intent or Intent.reference,
            audience=audience or "",
            title=title or "",
            sources=sources or [],
            steering_notes=steering_notes or "",
            sphinx_target=sphinx_target or f"{unit_id}.md",
            extra_targets=extra_targets or [],
        )
        front_yaml = yaml.safe_dump(
            self._dump_unit_front(unit), sort_keys=False
        ).rstrip("\n")
        fence = _FRONT_MATTER_FENCE
        return f"{fence}\n{front_yaml}\n{fence}\n{_BODY_TEMPLATE}"

    def _read_yaml(self, unit_id: str, name: str, *, root: Path) -> dict:
        """Read a machine YAML file for a unit.

        Parameters
        ----------
        unit_id : str
            The unit id.
        name : str
            The file name (e.g. ``provenance.yaml``).
        root : Path
            The repo root.

        Returns
        -------
        dict
            The parsed mapping (empty when the file holds no data).
        """
        self._reject_unsafe_unit_id(unit_id)
        path = (root / _UNITS_SUBDIR / unit_id / name).resolve()
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _write_yaml(
        self,
        unit_id: str,
        name: str,
        model: Provenance,
        *,
        root: Path,
    ) -> Path:
        """Serialize a Pydantic model to a unit's machine YAML file.

        Parameters
        ----------
        unit_id : str
            The unit id.
        name : str
            The target file name.
        model : Provenance
            The model to serialize.
        root : Path
            The repo root.

        Returns
        -------
        Path
            The written file path.
        """
        self._reject_unsafe_unit_id(unit_id)
        target = (root / _UNITS_SUBDIR / unit_id / name).resolve()
        self._assert_within_root(target, root=root)
        self._assert_not_under_planning(target, root=root)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic (WR-03): provenance is the audit trail; a torn write
        # must never leave a half-serialized YAML. temp-then-rename guarantees
        # the on-disk file is either the prior or the new content, never partial.
        self._atomic_write_text(
            target, yaml.safe_dump(model.model_dump(mode="json"), sort_keys=False)
        )
        return target
