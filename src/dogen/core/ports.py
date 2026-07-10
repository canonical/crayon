"""Domain ports for dogen, shaped by domain verbs (not vendor signatures).

These ``Protocol`` classes are the seam (SEAM-03/04): ``core/`` depends only on
them, and adapters implement them. A port that mirrored an SDK method has already
failed the design (ARCHITECTURE Anti-Pattern 2), so every signature here speaks
the domain — ``draft_unit``, ``scaffold_unit``, ``read_provenance`` — and no
parameter or return type references any ``copilot``/SDK symbol (S5). Drafting is
async because the SDK is async end-to-end (RESEARCH Pitfall 2).
"""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from dogen.core.models import (
    DogenConfig,
    DraftResult,
    Intent,
    Provenance,
    Signoff,
    SourceRef,
    Takeover,
    Unit,
)

# The injected identity port (D-05): a zero-argument callable returning the
# operator's ``(name, email)``. Mirrors the ``Clock`` alias precedent — a plain
# callable type the use-cases depend on, so git-config lookup is injected at the
# composition root and the promoted steer/review flows stay deterministic and
# testable (Plan 04, Option A from the RESEARCH Promotion Delta).
Identity = Callable[[], tuple[str, str]]


@runtime_checkable
class DraftingProvider(Protocol):
    """The provider seam: draft one unit, steered by intent and audience.

    Implemented by the real Copilot adapter and by a deterministic mock (the
    mock *is* the second provider that proves swappability — D-26/SEAM-04).
    """

    async def draft_unit(  # noqa: PLR0913
        self,
        *,
        intent: Intent,
        audience: str,
        signoff: Signoff,
        sources: list[SourceRef],
        notes: list[str] | None = None,
        page_format: str = "myst",
    ) -> DraftResult:
        """Draft a single unit from the signed-off plan and steering stream.

        Parameters
        ----------
        intent : Intent
            The Diátaxis direction to draft toward.
        audience : str
            Who the page is written for.
        signoff : Signoff
            The recorded HITL gate act that must precede the draft.
        sources : list of SourceRef
            The declared sources — the primary grounding and the starting
            points for navigation (v1: a starting set, not a boundary).
        notes : list of str
            The unit's steering notes, oldest first: the seeded planning note
            plus every appended stream entry (review-verdict and manual). A
            driver folds them into its prompt; a passenger receives them for
            completeness (its host already read the stream from disk).
        page_format : str
            The unit's page format (``myst`` / ``rst``, derived from the
            target extension — v1.2). A driver authors in this markup; a
            passenger receives it for completeness (its host reads the
            target from disk).

        Returns
        -------
        DraftResult
            The drafted page content plus provenance inputs, in domain terms.
        """
        ...


@runtime_checkable
class SourceLookup(Protocol):
    """Bounded, read-only access to the sources the agent may read."""

    async def read_source(self, ref: SourceRef) -> str:
        """Return the text content of a single source.

        Parameters
        ----------
        ref : SourceRef
            The source to read.

        Returns
        -------
        str
            The source's textual content.
        """
        ...


@runtime_checkable
class PlanningStore(Protocol):
    """Read/write the F1 planning directory in domain verbs (D-31/33).

    The adapter owns file layout (``.dogen/units/<id>/`` + ``docs/``); the port
    speaks only of units, drafts, provenance, and progress.
    """

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
            The unit identifier and per-unit directory name.
        root : Path
            The repo root the store writes beneath.
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
            Optional docs-relative output path (subdirectories welcome);
            defaults to ``<unit_id>.<ext>`` (v1.2: dominant docs format).
        extra_targets : list of str or None
            Additional docs-relative pages in the unit's change set (v1.2).
        force : bool
            Overwrite an existing ``unit.md`` when ``True``.

        Returns
        -------
        Path
            The path to the written ``unit.md``.
        """
        ...

    def list_unit_ids(self, *, root: Path) -> list[str]:
        """Enumerate the declared units under the planning tree.

        A pure, read-only enumeration verb in domain terms: return the ids of
        every unit that has an editable ``unit.md``, so a caller can list units
        without knowing the on-disk layout. The store must not create the units
        directory as a side effect.

        Parameters
        ----------
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        list of str
            The declared unit ids, sorted; empty when no units exist.
        """
        ...

    def load_unit(self, unit_id: str, *, root: Path) -> Unit:
        """Load and validate a unit's ``unit.md`` front-matter.

        Parameters
        ----------
        unit_id : str
            The unit to load.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        Unit
            The validated unit model.
        """
        ...

    def plan_takeovers(
        self, unit_id: str, targets: list[str], *, root: Path
    ) -> list[Takeover]:
        """Plan the supersede edges a unit's claim records over sealed owners.

        The read-only companion to :meth:`scaffold_unit`/:meth:`update_unit`:
        after a unit is written, its final target set is scanned against every
        other declared unit. Ownership is a **lease** (D-01): an *in-flight*
        overlap has already been refused by the write guard, so every remaining
        overlapping owner is *sealed* and may be superseded. For each page,
        the newest-accept sealed owner (D-04 ordering, tie by smaller unit id)
        yields one :class:`~dogen.core.models.Takeover`; a corrupt/absent
        neighbour is skipped (WR-01), never aborting the scan.

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
            One supersede edge per superseded sealed page, page-sorted; empty
            when the claim overlaps no sealed owner.
        """
        ...

    def assert_draft_targets_unclaimed(
        self, unit_id: str, targets: list[str], *, root: Path
    ) -> None:
        """Refuse a draft when another *in-flight* unit claims any target (OWN-03).

        The draft-time half of the lease (D-03): ownership is held only while a
        unit is in flight, so before a unit writes its pages the store re-checks
        that no *other* in-flight unit claims any of ``targets``. This closes the
        reverse hole — a sealed owner that reopened via a post-accept
        ``fix``/``redraft`` (D-02, its lease re-armed) now blocks a competitor
        that took the page while it was sealed. A *sealed* overlapping owner does
        not block (its lease was released); an absent/unreadable neighbour is
        skipped WR-01-tolerantly, never wedging a draft.

        The type raised is the store's own ``TargetClaimedError`` (a
        ``FileExistsError`` subclass) — the same the write guard raises — so the
        core caller need not name an adapter type across the provider seam.

        Parameters
        ----------
        unit_id : str
            The unit about to draft (excluded from the scan).
        targets : list of str
            The unit's full docs-relative page set (primary + extras).
        root : Path
            The repo root the store reads beneath.

        Raises
        ------
        FileExistsError
            (``TargetClaimedError``) if any overlapping owner is in-flight.
        """
        ...

    def delete_unit(
        self,
        unit_id: str,
        *,
        root: Path,
        sphinx_target: str | None = None,
        extra_targets: list[str] | None = None,
    ) -> None:
        """Delete a unit's directory and, optionally, its drafted docs output.

        The destructive counterpart to :meth:`scaffold_unit`. The store validates
        every path before acting: a traversing ``sphinx_target`` must raise
        without any filesystem side effect, and a missing unit must be a
        distinguishable not-found outcome rather than a silent no-op.

        Parameters
        ----------
        unit_id : str
            The unit to delete; must be a single safe path segment.
        root : Path
            The repo root the store deletes beneath.
        sphinx_target : str or None
            The unit's drafted docs target (relative to ``docs/``) to remove
            alongside the directory; ``None`` removes only the unit directory.
        extra_targets : list of str or None
            The unit's extra pages to remove alongside the primary (v1.2).
        """
        ...

    def rename_unit(self, old_id: str, new_id: str, *, root: Path) -> None:
        """Rename a unit's id everywhere, rollback-safe.

        Rewrites the id in the unit's ``unit.md`` + machine records, re-derives
        the Sphinx output target, and moves the drafted docs page. The store must
        be rollback-safe: all guards run before any mutation, and a mid-failure
        must never leave a half-renamed unit.

        Parameters
        ----------
        old_id : str
            The current unit id; must be a single safe path segment.
        new_id : str
            The target unit id; must be a single safe path segment.
        root : Path
            The repo root the store operates beneath.
        """
        ...

    def write_draft(self, unit: Unit, text: str, *, root: Path) -> Path:
        """Write a drafted page to the unit's primary Sphinx target.

        Parameters
        ----------
        unit : Unit
            The unit being drafted (provides ``sphinx_target``).
        text : str
            The page content, in the unit's format (MyST or rST).
        root : Path
            The repo root the store writes beneath.

        Returns
        -------
        Path
            The path to the written page under ``docs/``.
        """
        ...

    def write_page(self, target: str, text: str, *, root: Path) -> Path:
        """Write one page of a unit's set to its docs-relative target (v1.2).

        The multi-file counterpart of :meth:`write_draft` (which delegates to
        this for the primary): the orchestrator loops a unit's target set and
        collects per-page digests for provenance and the seam pathspec.

        Parameters
        ----------
        target : str
            The docs-relative page path.
        text : str
            The page content, in the page's format.
        root : Path
            The repo root the store writes beneath.

        Returns
        -------
        Path
            The path to the written page under ``docs/``.
        """
        ...

    def read_page(self, target: str, *, root: Path) -> str:
        """Return one page's recorded text at a docs-relative target (v1.2).

        Parameters
        ----------
        target : str
            The docs-relative page path.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        str
            The page's full text.
        """
        ...

    def read_provenance(self, unit_id: str, *, root: Path) -> Provenance:
        """Load a unit's provenance record.

        Parameters
        ----------
        unit_id : str
            The unit to read.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        Provenance
            The validated provenance model.
        """
        ...

    def write_provenance(self, provenance: Provenance, *, root: Path) -> Path:
        """Persist a unit's provenance record.

        Parameters
        ----------
        provenance : Provenance
            The provenance model to serialize.
        root : Path
            The repo root the store writes beneath.

        Returns
        -------
        Path
            The path to the written ``provenance.yaml``.
        """
        ...

    def read_unit_text(self, unit_id: str, *, root: Path) -> str:
        """Return the full raw text of a unit's ``unit.md`` (v1).

        The signoff use-case hashes this text to freeze the approved plan
        (``Signoff.plan_hash``), and the draft use-case re-hashes it to detect
        a post-signoff plan edit. The store returns the bytes-as-text verbatim;
        hashing is the core's concern.

        Parameters
        ----------
        unit_id : str
            The unit to read.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        str
            The complete ``unit.md`` document text.
        """
        ...

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

        The amend counterpart to :meth:`scaffold_unit` (the Q3 decision): only
        the named fields change; every other front-matter field and the
        hand-edited body are preserved verbatim. This is the delegable update
        path for Write/Edit-free skills.

        Parameters
        ----------
        unit_id : str
            The unit to update.
        root : Path
            The repo root the store writes beneath.
        intent : Intent or None
            Replacement Diátaxis direction; ``None`` leaves it unchanged.
        audience : str or None
            Replacement audience; ``None`` leaves it unchanged.
        title : str or None
            Replacement title; ``None`` leaves it unchanged.
        add_sources : list of SourceRef or None
            Sources appended to the declared set (duplicates by path/ref are
            ignored).
        remove_sources : list of str or None
            Source paths/refs removed from the declared set.
        steering_notes : str or None
            Replacement seeded steering note; ``None`` leaves it unchanged.
        body : str or None
            Replacement plan body (everything below the front matter);
            ``None`` preserves the existing body verbatim.
        sphinx_target : str or None
            Replacement docs-relative output path; ``None`` leaves it
            unchanged. An existing draft at the old target moves with the
            repoint.
        add_targets : list of str or None
            Extra pages appended to the unit's change set (v1.2; duplicates
            ignored).
        drop_targets : list of str or None
            Extra pages removed from the set (v1.2; de-scope only — the
            on-disk page is never touched; the primary cannot be dropped).

        Returns
        -------
        Path
            The path to the rewritten ``unit.md``.
        """
        ...

    def read_draft(self, unit: Unit, *, root: Path) -> str:
        """Return the recorded draft text at the unit's Sphinx target (v1).

        The review use-case hashes this to seal an ``accept`` verdict to the
        exact text the reviewer approved.

        Parameters
        ----------
        unit : Unit
            The unit whose draft is read (provides ``sphinx_target``).
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        str
            The draft's full text.
        """
        ...

    def read_config(self, *, root: Path) -> DogenConfig:
        """Load the repo's ``.dogen/config.yaml``, defaulting when absent (v1).

        Parameters
        ----------
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        DogenConfig
            The validated config; the model's defaults (``host-harness``
            provider, ``auto`` commits) when no file exists.
        """
        ...

    def write_config(self, config: DogenConfig, *, root: Path) -> Path:
        """Persist the repo's ``.dogen/config.yaml`` (v1).

        Parameters
        ----------
        config : DogenConfig
            The config model to serialize.
        root : Path
            The repo root the store writes beneath.

        Returns
        -------
        Path
            The path to the written ``config.yaml``.
        """
        ...

    def list_context(self, *, root: Path) -> list[str]:
        """Enumerate the context artifacts under ``.dogen/context/`` (v1).

        The B1/B2 landing zone: presence of a well-known filename is the
        contract, so listing is a pure directory read.

        Parameters
        ----------
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        list of str
            The artifact filenames present, sorted; empty when none exist.
        """
        ...

    def add_context(self, name: str, text: str, *, root: Path) -> Path:
        """File a context artifact into ``.dogen/context/<name>`` (v1).

        Parameters
        ----------
        name : str
            The artifact filename (a single safe path segment, e.g.
            ``code-to-docs-map.md``).
        text : str
            The artifact's full content, landed as-is (free-form welcome).
        root : Path
            The repo root the store writes beneath.

        Returns
        -------
        Path
            The path to the written artifact.
        """
        ...


@runtime_checkable
class RepoSeam(Protocol):
    """Version-stamp and commit dogen's own artifacts — the commit seam (v1).

    Implemented by the git adapter; injected into the use-cases so ``core/``
    stays adapter-free. When no seam is injected (``None``), transitions are
    not committed and stamps are empty — the ``commits: off`` posture. The
    seam records **local** commits only: it never pushes, opens PRs, builds,
    or publishes (the amended scope boundary).
    """

    def head_commit(self, *, root: Path) -> str:
        """Return the repo's current HEAD commit hash.

        Parameters
        ----------
        root : Path
            The repo root.

        Returns
        -------
        str
            The full HEAD commit hash, or ``""`` when the directory is not a
            git repository or has no commits yet.
        """
        ...

    def tracked(self, *, root: Path, paths: list[str]) -> set[str]:
        """Return the subset of ``paths`` that are tracked in the repo.

        Used to keep provenance commit pins honest: a read of an untracked
        file must stamp ``commit: ""`` (unknown), never a HEAD SHA at which
        the file does not exist in the tree. Directory paths count as tracked
        when at least one tracked file lives beneath them.

        Parameters
        ----------
        root : Path
            The repo root.
        paths : list of str
            Repo-relative candidate paths (files or directories).

        Returns
        -------
        set of str
            The members of ``paths`` with tracked content; empty when the
            directory is not a git repository.
        """
        ...

    def commit(self, *, root: Path, paths: list[Path], message: str) -> str:
        """Stage the given paths and record one local commit.

        Parameters
        ----------
        root : Path
            The repo root.
        paths : list of Path
            The paths to stage and commit (dogen's artifacts and the draft).
        message : str
            The full commit message, including the ``Dogen-*`` trailers.

        Returns
        -------
        str
            The new commit's hash, or ``""`` when there was nothing to commit
            (the paths held no changes).
        """
        ...
