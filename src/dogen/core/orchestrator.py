"""The drafting use-cases: the A2 loop under the v1 traceability redesign.

This is pure domain orchestration. It enforces the **provable-HITL gate** as a
domain invariant (not CLI ceremony): if no ``signoff`` act was recorded, a
draft raises :class:`SignoffRequiredError` and produces no side effects (D-40 /
HITL-01). When the signoff is present it opens the ``dogen.draft`` OTel span,
mints the ``run_id`` from the trace id, drives the injected
:class:`DraftingProvider`, writes the draft + a ``generations[]`` entry (whose
``run_id`` correlates to the span — OBS-03/D-22) via the
:class:`PlanningStore`, and auto-advances progress ``pending → sourced →
drafted``. It **never** writes ``ProgressState.committed`` — publishing belongs
to the human (SKEL-03 / Pitfall 9 / D-38).

Schema v1 adds the traceability spine here:

* every lifecycle transition records one local commit through the injected
  :class:`RepoSeam` (``Dogen-Unit`` / ``Dogen-Phase`` / ``Dogen-Run``
  trailers), so a unit's whole path is reconstructable from ``git log`` alone;
* ``signoff`` freezes the plan (a SHA-256 of ``unit.md``) and drafting flags a
  stale plan instead of silently drafting an unapproved one;
* review verdicts are structured — ``accept`` seals the exact draft text,
  ``fix``/``redraft`` append the note to the steering stream the next draft
  pass reads;
* generations carry the draft path/hash, the handoff path, the source commit,
  and the merged context report, closing the passenger-blind provenance hole.

Everything host-facing is injected (provider, store, repo seam, ``now``) so the
use-cases depend only on abstractions (coding-guide §6) and tests stay
deterministic.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import metadata as _metadata
from pathlib import Path, PurePosixPath

from dogen.core import observability
from dogen.core.models import (
    ContextReport,
    DraftResult,
    Effort,
    FileDigest,
    Generation,
    Intent,
    Progress,
    ProgressEntry,
    ProgressState,
    Provenance,
    ReadRecord,
    ReviewerEdit,
    ReviewVerdict,
    Signoff,
    SourceRef,
    SteeringEntry,
    SteeringOrigin,
    Unit,
    UnitSummary,
    derive_progress,
)
from dogen.core.ports import DraftingProvider, Identity, PlanningStore, RepoSeam

_DRAFT_ACTION = "draft"

# The auto-advance ladder the loop walks; ``committed`` is deliberately absent.
_AUTO_ADVANCE: tuple[ProgressState, ...] = (
    ProgressState.sourced,
    ProgressState.drafted,
)

# The forward lifecycle ordering (D-38) used to keep auto-advance monotonic
# (WR-04): a state is only stamped when it is strictly later than the current
# one. ``reviewed`` is included so a re-draft of an already-reviewed unit is
# ranked correctly instead of walking the lifecycle backward. The terminal
# ``committed`` state is deliberately NOT named here (SKEL-03).
_PROGRESS_ORDER: tuple[ProgressState, ...] = (
    ProgressState.pending,
    ProgressState.sourced,
    ProgressState.drafted,
    ProgressState.reviewed,
)

Clock = Callable[[], str]


class SignoffRequiredError(RuntimeError):
    """Raised when drafting is attempted before a signoff act is recorded.

    The HITL gate is consequential, not ceremonial (HITL-01 / Pitfall 3): the
    CLI surfaces this as a clear message and a nonzero exit, and no draft,
    provenance entry, or progress change is produced.
    """


class SignoffExistsError(RuntimeError):
    """Raised when ``signoff`` would overwrite an existing act (WR-04).

    Silently replacing the recorded signoff after a unit has been drafted
    would push ``signoff.at`` past ``generations[0].at``, inverting the
    "signoff provably precedes the draft" ordering the AC5 audit depends on
    (HITL-02). The refusal is a domain invariant — the use-case writes nothing
    and raises; the CLI maps it to a nonzero exit. Passing ``force`` honours
    an explicit re-signoff (and flags a non-fatal warn signal instead).
    """


class NotDraftedError(RuntimeError):
    """Raised when ``review`` targets a unit that was never drafted (WR-05).

    A missing ``progress.yaml`` means no draft has run, so a review has nothing
    to attach to. Surfacing a clear domain refusal — rather than letting a bare
    ``FileNotFoundError`` escape — keeps the "draft first" border legible
    (REVIEW-01); the CLI maps it to a nonzero exit.
    """


class AlreadyAcceptedError(RuntimeError):
    """Raised when ``review --verdict accept`` would duplicate a sealed accept.

    A harness double-fire (observed 1.3 s apart in validation) must not append
    a second identical accept record: if the latest reviewer edit is an
    ``accept`` sealing the *same* on-disk draft hash, the review writes nothing
    and raises. Re-accepting is legitimate only when the draft text actually
    changed since the seal (the hash comparison permits exactly that).
    """


def _sha256(text: str) -> str:
    """Return the SHA-256 hex digest of ``text`` (UTF-8).

    Parameters
    ----------
    text : str
        The text to hash.

    Returns
    -------
    str
        The 64-hex-character digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _page_digest(target: str, *, sha: str) -> FileDigest:
    """Build one page's digest record from its docs-relative target (v1.2).

    Parameters
    ----------
    target : str
        The docs-relative page path.
    sha : str
        The page text's SHA-256 hex digest.

    Returns
    -------
    FileDigest
        The digest with the repo-relative ``docs/…`` path.
    """
    return FileDigest(path=str(PurePosixPath("docs") / target), sha256=sha)


def same_file_digests(a: list[FileDigest], b: list[FileDigest]) -> bool:
    """Report whether two file lists carry the identical ``{path: sha256}`` set.

    Order-agnostic (D-10): target paths are unique (containment validation), so
    the path-keyed mapping compare is lossless and immune to spurious mismatches
    from reordered or repointed extras. The single shared digest-set compare —
    consumed by :func:`_same_seal` now and by Phase 8's identical-redraft
    suppression later, so the two cannot drift.

    Parameters
    ----------
    a, b : list of FileDigest
        The two digest lists to compare.

    Returns
    -------
    bool
        ``True`` when both lists map every path to the same hash.
    """
    return {f.path: f.sha256 for f in a} == {f.path: f.sha256 for f in b}


def _same_seal(last: ReviewerEdit, *, files: list[FileDigest]) -> bool:
    """Report whether a prior accept sealed the identical page set (v2, D-11).

    Every loaded record carries ``files ≥ 1`` after migration, so the compare is
    files-only — the legacy primary-hash fallback branch is gone.

    Parameters
    ----------
    last : ReviewerEdit
        The most recent reviewer edit (an ``accept``).
    files : list of FileDigest
        The current full digest list.

    Returns
    -------
    bool
        ``True`` when nothing changed since the prior seal.
    """
    return same_file_digests(last.files, files)


def tooling_version() -> str:
    """Return the installed ``dogen`` distribution version (PROV-06).

    Reads the real installed-dist metadata rather than a hardcoded constant. The
    version string stays ``"0.0.0"`` until ``pyproject.toml`` is bumped at
    release time — a distinct release concern, deliberately not this phase.

    Returns
    -------
    str
        ``importlib.metadata.version("dogen")``, or the honest non-semver
        sentinel ``"0+unknown"`` when the dist cannot be resolved
        (editable/uninstalled edge).
    """
    try:
        return _metadata.version("dogen")
    except _metadata.PackageNotFoundError:
        return "0+unknown"


def _body_note(note: str, *, limit: int = 400) -> str:
    """Collapse a free-text note into one trailer-safe body line (v1.2, R6).

    Newlines are collapsed (a note must never be able to split the message
    into extra paragraphs or masquerade as a trailer block) and the result is
    capped so log-only forensics carries the verdict's substance without
    unbounded message bloat.

    Parameters
    ----------
    note : str
        The operator-authored free text.
    limit : int
        The maximum body-line length; longer notes are cut with an ellipsis.

    Returns
    -------
    str
        A single sanitized line, possibly empty.
    """
    collapsed = " ".join(note.split())
    if len(collapsed) > limit:
        return collapsed[: limit - 1].rstrip() + "…"
    return collapsed


def _transition_message(  # noqa: PLR0913
    unit_id: str,
    *,
    phase: str,
    summary: str,
    body: str = "",
    run_id: str = "",
    provider: str = "",
    model: str = "",
    draft_sha: str = "",
) -> str:
    """Build the commit-seam message for one lifecycle transition (v1).

    The trailers are the reconstruction contract: ``git log --grep
    'Dogen-Unit: <id>'`` alone replays a unit's whole path. The optional body
    paragraph (v1.2, R6) carries the forensically load-bearing detail — the
    capped verdict note, origin/gap counts, plan-change summary — so an
    auditor rarely needs ``-p``; it always sits between the subject and the
    trailer block so trailer parsing stays intact.

    Parameters
    ----------
    unit_id : str
        The unit the transition belongs to.
    phase : str
        The transition phase (``declared`` / ``edited`` / ``signed-off`` /
        ``steered`` / ``drafted`` / ``reviewed`` / ``removed`` / ``renamed`` /
        ``context``).
    summary : str
        A one-line human summary after the phase.
    body : str
        An optional body paragraph (caller-controlled lines; free text must
        pass through :func:`_body_note` first).
    run_id : str
        The draft run id, stamped as ``Dogen-Run`` when non-empty.
    provider : str
        The provider name, stamped as ``Dogen-Provider`` when non-empty.
    model : str
        The generation's model identity, stamped as ``Dogen-Model`` when
        non-empty.
    draft_sha : str
        The draft's content hash, stamped as ``Dogen-Draft`` (first 12 hex)
        when non-empty.

    Returns
    -------
    str
        The full commit message including trailers.
    """
    lines = [f"dogen({unit_id}): {phase} — {summary}"]
    if body:
        lines.extend(["", body])
    lines.extend(["", f"Dogen-Unit: {unit_id}", f"Dogen-Phase: {phase}"])
    if run_id:
        lines.append(f"Dogen-Run: {run_id}")
    if provider:
        lines.append(f"Dogen-Provider: {provider}")
    if model:
        lines.append(f"Dogen-Model: {model}")
    if draft_sha:
        lines.append(f"Dogen-Draft: {draft_sha[:12]}")
    return "\n".join(lines)


def _commit_transition(  # noqa: PLR0913
    repo: RepoSeam | None,
    *,
    root: Path,
    paths: list[Path],
    unit_id: str,
    phase: str,
    summary: str,
    body: str = "",
    run_id: str = "",
    provider: str = "",
    model: str = "",
    draft_sha: str = "",
) -> str:
    """Record one transition commit through the seam, if one is injected.

    A ``None`` seam is the ``commits: off`` posture (or ``--no-commit``): the
    transition simply is not committed and ``""`` is returned.

    Parameters
    ----------
    repo : RepoSeam or None
        The injected commit seam, or ``None`` to skip committing.
    root : Path
        The repo root.
    paths : list of Path
        The artifact paths to stage and commit.
    unit_id : str
        The unit the transition belongs to.
    phase : str
        The transition phase (see :func:`_transition_message`).
    summary : str
        A one-line human summary.
    body : str
        The optional body paragraph (see :func:`_transition_message`).
    run_id : str
        The draft run id for the ``Dogen-Run`` trailer, when applicable.
    provider : str
        The provider name for the ``Dogen-Provider`` trailer, when applicable.
    model : str
        The model identity for the ``Dogen-Model`` trailer, when applicable.
    draft_sha : str
        The draft hash for the ``Dogen-Draft`` trailer, when applicable.

    Returns
    -------
    str
        The new commit hash, or ``""`` when no seam was injected or there was
        nothing to commit.
    """
    if repo is None:
        return ""
    return repo.commit(
        root=root,
        paths=paths,
        message=_transition_message(
            unit_id,
            phase=phase,
            summary=summary,
            body=body,
            run_id=run_id,
            provider=provider,
            model=model,
            draft_sha=draft_sha,
        ),
    )


def _unit_dir(root: Path, unit_id: str) -> Path:
    """Return the unit's planning directory for commit staging.

    Parameters
    ----------
    root : Path
        The repo root.
    unit_id : str
        The unit id (already validated by the store before any write).

    Returns
    -------
    Path
        The ``<root>/.dogen/units/<id>`` directory.
    """
    return root / ".dogen" / "units" / unit_id


def _head_commit(repo: RepoSeam | None, *, root: Path) -> str:
    """Return the repo HEAD stamp, or ``""`` when no seam is injected.

    Parameters
    ----------
    repo : RepoSeam or None
        The injected commit seam.
    root : Path
        The repo root.

    Returns
    -------
    str
        The HEAD commit hash, or ``""``.
    """
    return repo.head_commit(root=root) if repo is not None else ""


def _honest_stamps(
    repo: RepoSeam | None, *, root: Path, paths: list[str], stamp: str
) -> dict[str, str]:
    """Map each path to an honest commit stamp: HEAD if tracked, else ``""``.

    A read of an untracked file must never pin a HEAD SHA at which the file
    does not exist in the git tree — such a pin cannot reproduce the read and
    poisons a future audit (D6). ``""`` is the model's documented "unknown"
    convention.

    Parameters
    ----------
    repo : RepoSeam or None
        The injected commit seam; ``None`` (or an empty ``stamp``) skips the
        tracked check — everything gets ``stamp`` as-is, which is already
        ``""`` in those postures.
    root : Path
        The repo root.
    paths : list of str
        Repo-relative candidate paths.
    stamp : str
        The HEAD commit hash, or ``""``.

    Returns
    -------
    dict of str to str
        Each input path mapped to ``stamp`` (tracked) or ``""`` (untracked).
    """
    if repo is None or not stamp or not paths:
        return dict.fromkeys(paths, stamp)
    tracked = repo.tracked(root=root, paths=paths)
    return {p: (stamp if p in tracked else "") for p in paths}


def _stamp_sources(
    repo: RepoSeam | None, *, root: Path, sources: list[SourceRef], stamp: str
) -> list[SourceRef]:
    """Commit-stamp unstamped sources, honestly for path-backed ones.

    Sources carrying an explicit ``commit`` pass through verbatim; path
    sources get the tracked-checked stamp (:func:`_honest_stamps`); ref-only
    sources (no repo path to check) keep the plain HEAD stamp.

    Parameters
    ----------
    repo : RepoSeam or None
        The injected commit seam.
    root : Path
        The repo root.
    sources : list of SourceRef
        The declared/added sources.
    stamp : str
        The HEAD commit hash, or ``""``.

    Returns
    -------
    list of SourceRef
        The stamped source list, order preserved.
    """
    unstamped_paths = [s.path for s in sources if not s.commit and s.path]
    stamps = _honest_stamps(repo, root=root, paths=unstamped_paths, stamp=stamp)
    stamped: list[SourceRef] = []
    for source in sources:
        if source.commit:
            stamped.append(source)
        elif source.path:
            stamped.append(source.model_copy(update={"commit": stamps[source.path]}))
        else:
            stamped.append(source.model_copy(update={"commit": stamp}))
    return stamped


def _dogen_gitignore_path(root: Path) -> Path:
    """Return the seeded ``.dogen/.gitignore`` path for commit staging.

    Parameters
    ----------
    root : Path
        The repo root.

    Returns
    -------
    Path
        The ``<root>/.dogen/.gitignore`` path (the store guarantees it exists
        before any transition that stages it).
    """
    return root / ".dogen" / ".gitignore"


@dataclass(frozen=True)
class DeclareRequest:
    """The injected collaborators and parameters for declaring a unit.

    Parameters
    ----------
    unit_id : str
        The identifier and per-unit directory name for the new unit.
    root : Path
        The repo root the store writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    intent : Intent or None
        Optional pre-filled Diátaxis direction.
    audience : str or None
        Optional pre-filled audience.
    title : str or None
        Optional pre-filled human-readable page title.
    sources : list of SourceRef
        Optional pre-filled human-pointed sources, in declared order; each is
        commit-stamped at declare time when a repo seam is injected (v1).
    steering_notes : str or None
        Optional pre-filled free-form steering note.
    sphinx_target : str or None
        Optional docs-relative output path (``--target``); defaults to
        ``<unit_id>.<ext>`` (v1.2: dominant docs format).
    extra_targets : list of str
        Additional docs-relative pages in the unit's change set (v1.2,
        ``--also-target``).
    force : bool
        Overwrite an existing ``unit.md`` when ``True`` (explicit re-scaffold).
    repo : RepoSeam or None
        The injected commit seam; ``None`` disables stamps and the transition
        commit.
    """

    unit_id: str
    root: Path
    store: PlanningStore
    intent: Intent | None = None
    audience: str | None = None
    title: str | None = None
    sources: list[SourceRef] = field(default_factory=list)
    steering_notes: str | None = None
    sphinx_target: str | None = None
    extra_targets: list[str] = field(default_factory=list)
    force: bool = False
    repo: RepoSeam | None = None


def declare(request: DeclareRequest) -> Path:
    """Scaffold an editable ``unit.md`` and commit the transition (UNIT-01).

    Sources are stamped with the repo HEAD at declare time (v1), tying the
    unit to the code version it will document. The clobber and unsafe-id
    guards surface as raised domain outcomes — ``UnitExistsError`` and
    ``ValueError`` propagate unchanged; mapping them to a process exit is the
    CLI's job (D-01/D-04).

    Parameters
    ----------
    request : DeclareRequest
        The bundled collaborators and parameters for the declaration.

    Returns
    -------
    pathlib.Path
        The path of the written ``unit.md``.
    """
    stamp = _head_commit(request.repo, root=request.root)
    sources = _stamp_sources(
        request.repo, root=request.root, sources=request.sources, stamp=stamp
    )
    written = request.store.scaffold_unit(
        request.unit_id,
        root=request.root,
        intent=request.intent,
        audience=request.audience,
        title=request.title,
        sources=sources,
        steering_notes=request.steering_notes,
        sphinx_target=request.sphinx_target,
        extra_targets=list(request.extra_targets),
        force=request.force,
    )
    _commit_transition(
        request.repo,
        root=request.root,
        paths=[
            _unit_dir(request.root, request.unit_id),
            _dogen_gitignore_path(request.root),
        ],
        unit_id=request.unit_id,
        phase="declared",
        summary=request.title or request.unit_id,
    )
    return written


@dataclass(frozen=True)
class EditRequest:
    """The injected collaborators and parameters for amending a unit plan (v1).

    Parameters
    ----------
    unit_id : str
        The unit to amend.
    root : Path
        The repo root the store writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    intent : Intent or None
        Replacement Diátaxis direction; ``None`` leaves it unchanged.
    audience : str or None
        Replacement audience; ``None`` leaves it unchanged.
    title : str or None
        Replacement title; ``None`` leaves it unchanged.
    add_sources : list of SourceRef
        Sources appended to the declared set (commit-stamped at edit time).
    remove_sources : list of str
        Source paths/refs removed from the declared set.
    steering_notes : str or None
        Replacement seeded steering note; ``None`` leaves it unchanged.
    body : str or None
        Replacement plan body (Intent & scope / Outline sections below the
        front matter); ``None`` preserves the existing body verbatim.
    sphinx_target : str or None
        Replacement docs-relative output path (``--target``); an existing
        draft at the old target moves with the repoint.
    add_targets : list of str
        Extra pages appended to the unit's change set (v1.2,
        ``--also-target``).
    drop_targets : list of str
        Extra pages removed from the set (v1.2, ``--drop-target``; de-scope
        only).
    re_sign : bool
        Fold a re-approval into the same act (v1.2, R4): after the merge the
        amended plan is re-signed in place (fresh ``plan_hash``, superseded
        act archived), so a reviewer-ordered amendment never leaves the unit
        parked on a stale plan across extra commands.
    identity : Identity or None
        The identity port for the folded re-sign; required when ``re_sign``.
    now : Clock or None
        The timestamp source for the folded re-sign; required when
        ``re_sign``.
    repo : RepoSeam or None
        The injected commit seam.
    """

    unit_id: str
    root: Path
    store: PlanningStore
    intent: Intent | None = None
    audience: str | None = None
    title: str | None = None
    add_sources: list[SourceRef] = field(default_factory=list)
    remove_sources: list[str] = field(default_factory=list)
    steering_notes: str | None = None
    body: str | None = None
    sphinx_target: str | None = None
    add_targets: list[str] = field(default_factory=list)
    drop_targets: list[str] = field(default_factory=list)
    re_sign: bool = False
    identity: Identity | None = None
    now: Clock | None = None
    repo: RepoSeam | None = None


def edit_unit(request: EditRequest) -> Path:
    """Merge changes into an existing unit plan and commit the transition (v1).

    The Q3 decision: amendments merge — only the named fields change, the body
    and every unnamed field survive verbatim. This is the delegable update
    path that retires the v0 ``--force`` clobber for routine edits.

    With ``re_sign`` (v1.2), the amended plan is re-approved in the same act:
    the superseded gate act is archived to ``signoff_history`` and a fresh
    ``plan_hash`` is stamped, so the edit-then-re-sign detour (round-2's
    stale-plan grind) collapses into one call. The folded re-sign requires an
    existing signoff — the initial gate act stays a deliberate, separate
    ``dogen signoff``.

    Parameters
    ----------
    request : EditRequest
        The bundled collaborators and parameters for the amendment.

    Returns
    -------
    pathlib.Path
        The path of the rewritten ``unit.md``.

    Raises
    ------
    SignoffRequiredError
        If ``re_sign`` is set but the unit has no signoff act to refresh.
    """
    provenance: Provenance | None = None
    if request.re_sign:
        provenance = _load_or_init_provenance(
            request.store, request.unit_id, root=request.root
        )
        if provenance.signoff is None:
            raise SignoffRequiredError(
                f"cannot fold a re-sign into this edit: {request.unit_id!r} has "
                "no signoff act yet — run `dogen signoff` for the initial gate"
            )
    stamp = _head_commit(request.repo, root=request.root)
    add_sources = _stamp_sources(
        request.repo, root=request.root, sources=request.add_sources, stamp=stamp
    )
    # A target change may move the draft file: capture the old target and
    # whether a draft exists there BEFORE the store rewrites the plan, so the
    # transition pathspec can cover both docs paths — but only when a file
    # actually moved (an unmatched pathspec would make the seam commit fail
    # and be silently degraded to a warning by the tolerant wrapper).
    moved: tuple[str, str] | None = None
    retargeted: tuple[str, str] | None = None
    if request.sphinx_target is not None:
        unit_before = request.store.load_unit(request.unit_id, root=request.root)
        if unit_before.sphinx_target != request.sphinx_target:
            retargeted = (unit_before.sphinx_target, request.sphinx_target)
            try:
                request.store.read_draft(unit_before, root=request.root)
            except FileNotFoundError:
                pass
            else:
                moved = retargeted
    written = request.store.update_unit(
        request.unit_id,
        root=request.root,
        intent=request.intent,
        audience=request.audience,
        title=request.title,
        add_sources=add_sources,
        remove_sources=list(request.remove_sources),
        steering_notes=request.steering_notes,
        body=request.body,
        sphinx_target=request.sphinx_target,
        add_targets=list(request.add_targets),
        drop_targets=list(request.drop_targets),
    )
    body_line = _edit_body(request, retargeted=retargeted)
    if request.re_sign and provenance is not None:
        resign_note = _fold_re_sign(request, provenance, stamp=stamp)
        body_line = f"{body_line} · {resign_note}" if body_line else resign_note
    paths = [_unit_dir(request.root, request.unit_id)]
    if moved is not None:
        paths.extend(request.root / "docs" / target for target in moved)
    _commit_transition(
        request.repo,
        root=request.root,
        paths=paths,
        unit_id=request.unit_id,
        phase="edited",
        summary=(
            f"plan amended; draft moved to docs/{moved[1]}" if moved else "plan amended"
        ),
        body=body_line,
    )
    return written


def _fold_re_sign(request: EditRequest, provenance: Provenance, *, stamp: str) -> str:
    """Re-approve the amended plan inside the edit act (v1.2, R4).

    Reads the freshly merged ``unit.md``, stamps a new gate act (archiving the
    superseded one), and persists provenance. The caller has already verified
    a signoff exists.

    Parameters
    ----------
    request : EditRequest
        The amendment request carrying the identity and clock collaborators.
    provenance : Provenance
        The unit's audit record, mutated and written here.
    stamp : str
        The repo HEAD commit for the new act.

    Returns
    -------
    str
        The commit-body fragment describing the re-sign.

    Raises
    ------
    ValueError
        If the identity or clock collaborator is missing.
    """
    if request.identity is None or request.now is None:
        raise ValueError("re_sign requires the identity and now collaborators")
    author, _email = request.identity()
    unit_after = request.store.load_unit(request.unit_id, root=request.root)
    plan_text = request.store.read_unit_text(request.unit_id, root=request.root)
    superseded = _stamp_signoff(
        provenance,
        unit=unit_after,
        author=author,
        at=request.now(),
        plan_text=plan_text,
        commit=stamp,
    )
    request.store.write_provenance(provenance, root=request.root)
    new_act = provenance.signoff
    note = f"re-signed: plan {new_act.plan_hash[:12]}" if new_act else "re-signed"
    if superseded is not None:
        note += f" supersedes {superseded.plan_hash[:12]}"
    return note


def _edit_body(request: EditRequest, *, retargeted: tuple[str, str] | None) -> str:
    """Summarize what an edit changed, for the commit body (v1.2, R6).

    Parameters
    ----------
    request : EditRequest
        The amendment request whose named fields describe the change set.
    retargeted : tuple of (str, str) or None
        The ``(old, new)`` target pair when the plan was repointed.

    Returns
    -------
    str
        A one-line ``·``-joined change summary, possibly empty.
    """
    parts: list[str] = []
    if retargeted is not None:
        parts.append(f"target: {retargeted[0]} → {retargeted[1]}")
    if request.body is not None:
        parts.append("body amended")
    if request.intent is not None:
        parts.append(f"intent: {request.intent.value}")
    if request.audience is not None:
        parts.append("audience amended")
    if request.title is not None:
        parts.append("title amended")
    if request.steering_notes is not None:
        parts.append("steering note reseeded")
    counted = [
        (len(request.add_sources), "+{n} source(s)"),
        (len(request.remove_sources), "-{n} source(s)"),
        (len(request.add_targets), "+{n} target(s)"),
        (len(request.drop_targets), "-{n} target(s)"),
    ]
    parts.extend(tpl.format(n=n) for n, tpl in counted if n)
    return " · ".join(parts)


@dataclass(frozen=True)
class SignoffRequest:
    """The injected collaborators and parameters for the HITL gate act (v1).

    Parameters
    ----------
    unit_id : str
        The unit to sign off.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    identity : Identity
        The injected identity port returning the author's ``(name, email)``.
    now : Clock
        Injected timestamp source (ISO-8601) for deterministic tests.
    force : bool
        Overwrite an already-recorded signoff (re-signoff) when ``True``.
    repo : RepoSeam or None
        The injected commit seam.
    """

    unit_id: str
    root: Path
    store: PlanningStore
    identity: Identity
    now: Clock
    force: bool = False
    repo: RepoSeam | None = None


def signoff(request: SignoffRequest) -> bool:
    """Record the HITL signoff act for a unit and return a warn signal (UNIT-02).

    The act freezes the **whole plan** (v1, the Q2 decision): it stores a
    SHA-256 of the exact ``unit.md`` the author approved plus the repo HEAD,
    so a post-signoff plan edit is detectable (a stale hash at draft time)
    rather than silent. The WR-04 guard is a core invariant: re-signing an
    already-signed unit without ``force`` raises :class:`SignoffExistsError`
    and writes nothing. An explicit forced re-signoff of an already-drafted
    unit is honoured but returns a non-fatal warn signal.

    Parameters
    ----------
    request : SignoffRequest
        The bundled collaborators and parameters for the act.

    Returns
    -------
    bool
        ``True`` when a forced re-signoff overwrote the act on a unit that
        already has recorded generations (the warn signal), else ``False``.

    Raises
    ------
    SignoffExistsError
        If a signoff is already recorded and ``request.force`` is ``False``.
    """
    unit = request.store.load_unit(request.unit_id, root=request.root)
    author, _email = request.identity()
    provenance = _load_or_init_provenance(
        request.store, request.unit_id, root=request.root
    )
    if provenance.signoff is not None and not request.force:
        # WR-04: refuse to rewrite an existing act. No write happens.
        raise SignoffExistsError(
            f"signoff already recorded for {request.unit_id!r} "
            f"(by {provenance.signoff.author} at {provenance.signoff.at}); "
            "pass force=True to re-sign"
        )
    warn = provenance.signoff is not None and bool(provenance.generations)
    plan_text = request.store.read_unit_text(request.unit_id, root=request.root)
    superseded = _stamp_signoff(
        provenance,
        unit=unit,
        author=author,
        at=request.now(),
        plan_text=plan_text,
        commit=_head_commit(request.repo, root=request.root),
    )
    request.store.write_provenance(provenance, root=request.root)
    body = f"plan: {provenance.signoff.plan_hash[:12]}" if provenance.signoff else ""
    if superseded:
        body += f"\nsupersedes: {superseded.plan_hash[:12]}"
    _commit_transition(
        request.repo,
        root=request.root,
        paths=[_unit_dir(request.root, request.unit_id)],
        unit_id=request.unit_id,
        phase="signed-off",
        summary=f"plan signed off by {author}",
        body=body,
    )
    return warn


def _stamp_signoff(  # noqa: PLR0913
    provenance: Provenance,
    *,
    unit: Unit,
    author: str,
    at: str,
    plan_text: str,
    commit: str,
) -> Signoff | None:
    """Stamp a fresh gate act, archiving any superseded one (v1.2).

    Shared by ``signoff`` (initial and ``--re-sign``) and ``edit_unit``'s
    folded re-approval: the act it replaces is appended to
    ``signoff_history`` first, so every approved plan hash survives in the
    tip artifact.

    Parameters
    ----------
    provenance : Provenance
        The unit's audit record, mutated in place.
    unit : Unit
        The unit whose intent/audience the act attests.
    author : str
        The signing author (from git identity).
    at : str
        The ISO-8601 act timestamp.
    plan_text : str
        The exact ``unit.md`` text being approved.
    commit : str
        The repo HEAD stamp at approval.

    Returns
    -------
    Signoff or None
        The superseded act when this was a re-sign, else ``None``.
    """
    superseded = provenance.signoff
    if superseded is not None:
        provenance.signoff_history.append(superseded)
    provenance.signoff = Signoff(
        author=author,
        at=at,
        intent=unit.intent,
        audience=unit.audience,
        plan_hash=_sha256(plan_text),
        commit=commit,
    )
    return superseded


@dataclass(frozen=True)
class NoteRequest:
    """The injected collaborators and parameters for a steering-stream entry (v1).

    Parameters
    ----------
    unit_id : str
        The unit to steer.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    identity : Identity
        The injected identity port returning the author's ``(name, email)``.
    now : Clock
        Injected timestamp source (ISO-8601) for deterministic tests.
    note : str
        The guidance text to append.
    origin : SteeringOrigin
        Where the entry came from (``plan`` / ``review`` / ``manual``).
    repo : RepoSeam or None
        The injected commit seam.
    """

    unit_id: str
    root: Path
    store: PlanningStore
    identity: Identity
    now: Clock
    note: str
    origin: SteeringOrigin = SteeringOrigin.manual
    repo: RepoSeam | None = None


def add_steering_note(request: NoteRequest) -> None:
    """Append one entry to the unit's steering stream (v1).

    The stream is append-only and gate-free — guidance flows without ceremony
    (the Q2 decision: notes never require a re-signoff; only changing the plan
    itself does). The unit must exist; the entry is durable immediately and
    the next draft pass reads it.

    Parameters
    ----------
    request : NoteRequest
        The bundled collaborators and parameters for the entry.
    """
    request.store.load_unit(request.unit_id, root=request.root)
    author, _email = request.identity()
    provenance = _load_or_init_provenance(
        request.store, request.unit_id, root=request.root
    )
    provenance.steering.append(
        SteeringEntry(
            author=author,
            at=request.now(),
            note=request.note,
            origin=request.origin,
        )
    )
    request.store.write_provenance(provenance, root=request.root)
    _commit_transition(
        request.repo,
        root=request.root,
        paths=[_unit_dir(request.root, request.unit_id)],
        unit_id=request.unit_id,
        phase="steered",
        summary=f"steering note ({request.origin.value})",
    )


@dataclass(frozen=True)
class ReviewRequest:
    """The injected collaborators and parameters for recording a review.

    Parameters
    ----------
    unit_id : str
        The unit to review.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    identity : Identity
        The injected identity port returning the reviewer's ``(name, email)``.
    now : Clock
        Injected timestamp source (ISO-8601) for deterministic tests.
    note : str
        The reviewer's summary, recorded on the appended edit.
    verdict : ReviewVerdict
        The structured verdict (v1): ``accept`` seals the draft hash;
        ``fix``/``redraft`` also append the note to the steering stream.
    repo : RepoSeam or None
        The injected commit seam.
    """

    unit_id: str
    root: Path
    store: PlanningStore
    identity: Identity
    now: Clock
    note: str
    verdict: ReviewVerdict = ReviewVerdict.fix
    repo: RepoSeam | None = None


@dataclass(frozen=True)
class ReviewOutcome:
    """The result of one recorded review (v1).

    Parameters
    ----------
    state : ProgressState
        The unit's progress state after the review (``reviewed``).
    next_action : str
        The deterministic next-step suggestion (same vocabulary as the status
        board's ``next``): after ``fix``/``redraft`` it routes back to
        drafting; after ``accept`` the publishing commit is the human's.
    next_id : str
        The machine routing token behind ``next_action`` (``sign_off`` /
        ``re_sign`` / ``draft`` / ``review`` / ``publish`` / ``done``). Skills
        key their routing language off this token and never parrot the human
        line to the operator (v1.2, R3).
    """

    state: ProgressState
    next_action: str
    next_id: str = ""
    unapplied_steering: bool = False


def _has_unapplied_steering(provenance: Provenance) -> bool:
    """Return ``True`` when steering post-dates the last draft's consumed count.

    On an ``accept`` this means a ``fix``/``redraft`` note (or a ``steer``)
    landed in the stream but no draft ran to apply it — the reviewer's
    correction was sealed over, never drafted against (round-3's orphan
    fix→accept, R5). Fails closed on pre-field provenance whose last generation
    predates ``steering_count`` (the field defaults to 0) — the same
    first-draft signal that makes a genuine orphan detectable, an accepted
    tradeoff.
    """
    if not provenance.generations:
        return False
    return len(provenance.steering) > provenance.generations[-1].steering_count


def review(request: ReviewRequest) -> ReviewOutcome:
    """Record a structured review and advance progress (REVIEW-01/02, v1).

    Each call appends a :class:`ReviewerEdit`, but the ``reviewed`` progress
    transition is stamped exactly once (WR-05 idempotency). v1 adds the two
    bookend behaviours: an ``accept`` verdict seals the exact draft text (its
    SHA-256 lands on the edit), and a ``fix``/``redraft`` verdict appends the
    note to the steering stream so the next draft pass reads it — the review
    loop's correction never again lives only in a conversation.

    The loop never sets ``ProgressState.committed`` — publishing belongs to
    the human (SKEL-03/D-38).

    Parameters
    ----------
    request : ReviewRequest
        The bundled collaborators and parameters for the review.

    Returns
    -------
    ReviewOutcome
        The unit's progress state after the review plus the routing hint.

    Raises
    ------
    NotDraftedError
        If the unit has no ``progress.yaml`` (it was never drafted).
    AlreadyAcceptedError
        If an ``accept`` would duplicate the latest sealed accept for the
        same on-disk draft text (a harness double-fire); nothing is written.
    """
    reviewer, _email = request.identity()
    provenance = request.store.read_provenance(request.unit_id, root=request.root)
    # PROV-04 (Pitfall 2): "not drafted" now keys on an empty generation stream,
    # not a missing progress.yaml — the record is the single source of truth.
    if not provenance.generations:
        raise NotDraftedError(
            f"cannot review {request.unit_id!r}: it has not been drafted yet — "
            "run the draft use-case first"
        )
    draft_sha = ""
    sealed_files: list[FileDigest] = []
    unapplied_steering = False
    if request.verdict is ReviewVerdict.accept:
        unit = request.store.load_unit(request.unit_id, root=request.root)
        draft_sha = _sha256(request.store.read_draft(unit, root=request.root))
        sealed_files = [_page_digest(unit.sphinx_target, sha=draft_sha)]
        sealed_files.extend(
            _page_digest(
                target,
                sha=_sha256(request.store.read_page(target, root=request.root)),
            )
            for target in unit.extra_targets
        )
        last = provenance.reviewer_edits[-1] if provenance.reviewer_edits else None
        if (
            last is not None
            and last.verdict is ReviewVerdict.accept
            and _same_seal(last, files=sealed_files)
        ):
            raise AlreadyAcceptedError(
                f"this draft is already accepted (sealed {draft_sha[:12]}); "
                "nothing new to record"
            )
        unapplied_steering = _has_unapplied_steering(provenance)
    provenance.reviewer_edits.append(
        ReviewerEdit(
            at=request.now(),
            reviewer=reviewer,
            summary=request.note,
            verdict=request.verdict,
            files=sealed_files,
        )
    )
    if request.verdict is not ReviewVerdict.accept:
        # The verdict IS steering for the next pass — record it durably (v1).
        provenance.steering.append(
            SteeringEntry(
                author=reviewer,
                at=request.now(),
                note=request.note,
                origin=SteeringOrigin.review,
            )
        )
    request.store.write_provenance(provenance, root=request.root)
    # PROV-04 (D-01/D-02): no progress.yaml is written — the reviewer-edit append
    # above is the only durable state change, and write_provenance self-cleans any
    # stale sibling progress.yaml. The lifecycle state is derived from the record
    # after the append, so a landed review yields ``reviewed`` (WR-05 idempotency
    # falls out of the count-based rule: re-review appends another edit but the
    # derived state stays reviewed).
    state = derive_progress(provenance)
    _commit_transition(
        request.repo,
        root=request.root,
        paths=[_unit_dir(request.root, request.unit_id)],
        unit_id=request.unit_id,
        phase="reviewed",
        summary=f"review: {request.verdict.value}",
        body=_body_note(request.note),
        draft_sha=draft_sha,
    )
    signed = provenance.signoff is not None
    stale = False
    if provenance.signoff is not None and provenance.signoff.plan_hash:
        text = request.store.read_unit_text(request.unit_id, root=request.root)
        stale = _sha256(text) != provenance.signoff.plan_hash
    next_id, next_action = _suggest_next(
        state,
        signed_off=signed,
        stale_plan=stale,
        last_verdict=request.verdict,
        unit_id=request.unit_id,
    )
    return ReviewOutcome(
        state=state,
        next_action=next_action,
        next_id=next_id,
        unapplied_steering=unapplied_steering,
    )


@dataclass(frozen=True)
class DraftRequest:
    """The injected collaborators and parameters for one drafting run.

    Parameters
    ----------
    unit_id : str
        The unit to draft.
    root : Path
        The repo root the store reads/writes beneath.
    provider : DraftingProvider
        The injected drafting provider (mock in CI/tests, real in prod).
    store : PlanningStore
        The injected planning-directory store.
    provider_name : str
        The selected provider's name, recorded as a span attribute.
    now : Clock
        Injected timestamp source (ISO-8601) for deterministic tests.
    effort : Effort
        The reasoning effort recorded on the generation entry.
    report : ContextReport or None
        The provider's self-report of what it read (v1): the passenger's
        ``report.yaml`` ingested at the compose root, or ``None`` when the
        provider reports through its :class:`DraftResult` instead.
    handoff_path : str
        The repo-relative passenger handoff path recorded on the generation
        (v1 cross-ref); ``""`` for driver runs.
    repo : RepoSeam or None
        The injected commit seam.
    """

    unit_id: str
    root: Path
    provider: DraftingProvider
    store: PlanningStore
    provider_name: str
    now: Clock
    effort: Effort = Effort.medium
    report: ContextReport | None = None
    handoff_path: str = ""
    repo: RepoSeam | None = None


@dataclass(frozen=True)
class DraftOutcome:
    """The result of one drafting run (v1).

    Parameters
    ----------
    path : Path
        The path of the written draft under ``docs/``.
    stale_plan : bool
        ``True`` when ``unit.md`` no longer matches the signed-off plan hash —
        the draft still ran (guidance may legitimately evolve), but the gap
        between approval and plan is surfaced instead of silent.
    unsteered_redraft : bool
        ``True`` when this is a redraft (a prior generation exists) and no
        steering entry or review verdict arrived since the last generation —
        the steering-first loop expects recorded human input between passes
        (D4). A warning signal, never a block: manual redrafts are legitimate.
    model_unrecorded : bool
        ``True`` when the generation recorded an empty model — a passenger
        draft whose harness hid its model and was not given ``--model`` (M4,
        R4). A provenance-honesty signal, never a block: the skill should ask
        the TA for the model; honest-empty stays legal when they can't say.
    """

    path: Path
    stale_plan: bool
    unsteered_redraft: bool = False
    model_unrecorded: bool = False


async def draft(request: DraftRequest) -> DraftOutcome:
    """Run the drafting use-case for one unit and return the outcome.

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters for the run.

    Returns
    -------
    DraftOutcome
        The written draft path plus the stale-plan signal.

    Raises
    ------
    SignoffRequiredError
        If the unit has no recorded signoff act (HITL-01 / D-40).
    """
    unit = request.store.load_unit(request.unit_id, root=request.root)
    provenance = _read_signed_provenance(request)
    return await _run_draft(request, unit=unit, provenance=provenance)


def _read_signed_provenance(request: DraftRequest) -> Provenance:
    """Read provenance and enforce the HITL gate (D-40/HITL-01).

    A wholly missing ``provenance.yaml`` means no signoff ever ran, which is
    the same refusal as a present-but-unsigned record — both raise
    :class:`SignoffRequiredError`, never a generic file error.

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters.

    Returns
    -------
    Provenance
        The unit's provenance record, guaranteed to carry a signoff act.

    Raises
    ------
    SignoffRequiredError
        If provenance is absent or carries no signoff act.
    """
    try:
        provenance = request.store.read_provenance(request.unit_id, root=request.root)
    except FileNotFoundError as exc:
        raise SignoffRequiredError(
            "no recorded signoff for this unit; run `dogen signoff` before drafting"
        ) from exc
    if provenance.signoff is None:
        raise SignoffRequiredError(
            "no recorded signoff for this unit; run `dogen signoff` before drafting"
        )
    return provenance


def _steering_notes(unit: Unit, provenance: Provenance) -> list[str]:
    """Assemble the unit's guidance notes, oldest first (v1).

    Parameters
    ----------
    unit : Unit
        The unit (its seeded planning note comes first when non-empty).
    provenance : Provenance
        The provenance record carrying the appended steering stream.

    Returns
    -------
    list of str
        The seeded note (if any) followed by every stream entry's note.
    """
    notes = [unit.steering_notes] if unit.steering_notes else []
    notes.extend(entry.note for entry in provenance.steering)
    return notes


async def _run_draft(
    request: DraftRequest,
    *,
    unit: Unit,
    provenance: Provenance,
) -> DraftOutcome:
    """Drive the provider, persist the draft, and advance state under a span.

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters.
    unit : Unit
        The loaded unit being drafted.
    provenance : Provenance
        The unit's provenance record (signoff already verified present).

    Returns
    -------
    DraftOutcome
        The written draft path plus the stale-plan signal.
    """
    assert provenance.signoff is not None  # guaranteed by _read_signed_provenance
    signoff_act = provenance.signoff
    plan_text = request.store.read_unit_text(request.unit_id, root=request.root)
    stale_plan = bool(signoff_act.plan_hash) and (
        _sha256(plan_text) != signoff_act.plan_hash
    )
    # D4: the streams are append-only, so counts stamped on the last generation
    # give a deterministic "did any steering/review arrive since?" signal
    # (timestamps mix Z/+00:00 forms and cannot be compared). Old records
    # default both counts to 0, which fails open — no false warning.
    unsteered = False
    if provenance.generations:
        last = provenance.generations[-1]
        unsteered = (
            len(provenance.steering) <= last.steering_count
            and len(provenance.reviewer_edits) <= last.reviewer_edit_count
        )
    with observability.draft_span() as (span, run_id):
        observability.set_draft_attributes(
            span,
            unit_id=unit.unit_id,
            intent=unit.intent.value,
            provider=request.provider_name,
            run_id=run_id,
        )
        result = await request.provider.draft_unit(
            intent=unit.intent,
            audience=signoff_act.audience,
            signoff=signoff_act,
            sources=unit.sources,
            notes=_steering_notes(unit, provenance),
            page_format=unit.format,
        )
        # A multi-file unit's pages must map exactly onto the declared extras
        # (v1.2); the compose root pre-validates --draft-dir, this is the core
        # invariant behind it.
        supplied, expected = set(result.pages), set(unit.extra_targets)
        if supplied != expected:
            missing = sorted(expected - supplied)
            surplus = sorted(supplied - expected)
            raise ValueError(
                "draft pages do not match the unit's target set"
                + (f"; missing: {', '.join(missing)}" if missing else "")
                + (f"; undeclared: {', '.join(surplus)}" if surplus else "")
            )
        # WR-03: make the audit record durable BEFORE the draft is observable.
        # Provenance (the generations[] row) and progress are written first; the
        # pages are written last. A crash between these steps can then only
        # leave an audit row with no draft (re-runnable, harmless) — never a
        # drafted output with no recorded generation. The store writes each YAML
        # atomically (temp-then-rename) so a partial step never tears a file.
        _record_generation(provenance, request, unit=unit, result=result, run_id=run_id)
        request.store.write_provenance(provenance, root=request.root)
        # PROV-04 (D-01/D-02): draft no longer writes progress.yaml — the recorded
        # generation above IS the drafted state (derived on read), and the
        # write_provenance call self-cleans any stale sibling progress.yaml.
        draft_path = request.store.write_draft(unit, result.text, root=request.root)
        extra_paths = [
            request.store.write_page(target, result.pages[target], root=request.root)
            for target in unit.extra_targets
        ]
    generation = provenance.generations[-1]
    _commit_transition(
        request.repo,
        root=request.root,
        paths=[_unit_dir(request.root, request.unit_id), draft_path, *extra_paths],
        unit_id=request.unit_id,
        phase="drafted",
        summary=(f"draft #{len(provenance.generations)} via {request.provider_name}"),
        body=(
            f"origins: {len(generation.context_origins)} · gaps: {len(generation.gaps)}"
        ),
        run_id=run_id,
        provider=request.provider_name,
        model=generation.model,
        draft_sha=generation.files[0].sha256,
    )
    return DraftOutcome(
        path=draft_path,
        stale_plan=stale_plan,
        unsteered_redraft=unsteered,
        model_unrecorded=not generation.model,
    )


def _record_generation(  # noqa: PLR0913
    provenance: Provenance,
    request: DraftRequest,
    *,
    unit: Unit,
    result: DraftResult,
    run_id: str,
) -> None:
    """Append a ``generations[]`` entry correlated to the run (D-36/OBS-03).

    The unit's human-pointed ``sources`` are deliberately *not* an input here:
    copying them into ``context_origins`` is the D-37 collapse (BL-01). What
    the pass actually read comes from exactly one of two channels (v1, the
    uniform report contract): the ingested :class:`ContextReport` (passenger)
    or the provider-observed ``result.context_origins`` (driver), each entry
    commit-stamped so the read is tied to a code version.

    Parameters
    ----------
    provenance : Provenance
        The provenance record to append to.
    request : DraftRequest
        The bundled run parameters (effort, report, handoff, seam).
    unit : Unit
        The unit being drafted (provides the draft path cross-ref).
    result : DraftResult
        The provider's draft outcome.
    run_id : str
        The active span's 32-hex run id (stamped for correlation).
    """
    source_commit = _head_commit(request.repo, root=request.root)
    if request.report is not None:
        # Report-supplied commits are the passenger's own attestation — kept
        # verbatim (D-37); only deduplicated below.
        origins = list(request.report.context_origins)
        tools = list(request.report.tools_used)
        gaps = list(request.report.gaps)
        gaps_note = request.report.gaps_note
    else:
        stamps = _honest_stamps(
            request.repo,
            root=request.root,
            paths=list(result.context_origins),
            stamp=source_commit,
        )
        origins = [ReadRecord(path=p, commit=stamps[p]) for p in result.context_origins]
        tools = list(result.tools_used)
        gaps = []
        gaps_note = ""
    # Dedup within the generation by (path, commit), order-preserving: a
    # report listing the same read twice adds bytes to every future audit
    # read without adding information (D7).
    seen: set[tuple[str, str]] = set()
    deduped: list[ReadRecord] = []
    for record in origins:
        key = (record.path, record.commit)
        if key not in seen:
            seen.add(key)
            deduped.append(record)
    origins = deduped
    # IN-03: prefer the effort the provider actually ran at and fall back to
    # the requested effort only when the provider does not report one.
    effort = result.effort_used or request.effort
    provenance.generations.append(
        Generation(
            model=result.model,
            model_version=result.model_version,
            effort=effort,
            tooling_version=tooling_version(),
            # D-14/D-12: provider-reported, read verbatim from the DraftResult —
            # never a hard-coded module constant.
            sdk=result.sdk,
            provider=request.provider_name,
            mode=result.mode,
            context_origins=origins,
            tools_used=tools,
            gaps=gaps,
            gaps_note=gaps_note,
            files=[
                _page_digest(unit.sphinx_target, sha=_sha256(result.text)),
                *(
                    _page_digest(t, sha=_sha256(result.pages[t]))
                    for t in unit.extra_targets
                ),
            ],
            run_id=run_id,
            at=request.now(),
            action=_DRAFT_ACTION,
            handoff_path=request.handoff_path,
            source_commit=source_commit,
            steering_count=len(provenance.steering),
            reviewer_edit_count=len(provenance.reviewer_edits),
        )
    )


def _advance_progress(request: DraftRequest, *, run_id: str = "") -> None:
    """Land the unit at ``ProgressState.drafted`` after a draft (never committed).

    A draft always leaves the unit at ``drafted``, recorded as forward-only,
    idempotent history (WR-04 and its follow-up):

    - Already ``drafted``: a no-op — no transition, no spurious history entry.
    - Earlier (``pending``/``sourced``): walk the forward ladder, stamping each
      newly-reached state up to ``drafted``.
    - Later (``reviewed``, or any hand-set terminal state beyond the ladder): a
      re-draft deliberately supersedes the now-stale review and resets the unit
      to ``drafted`` in a single clean transition (D-38).

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters.
    run_id : str
        The draft run id stamped on each new history entry (v1 cross-ref).
    """
    progress = _read_or_init_progress(request)
    if progress.state is ProgressState.drafted:
        return
    drafted_rank = _PROGRESS_ORDER.index(ProgressState.drafted)
    current = (
        _PROGRESS_ORDER.index(progress.state)
        if progress.state in _PROGRESS_ORDER
        else len(_PROGRESS_ORDER)
    )
    if current > drafted_rank:
        progress.state = ProgressState.drafted
        progress.history.append(
            ProgressEntry(at=request.now(), state=ProgressState.drafted, run_id=run_id)
        )
    else:
        for state in _AUTO_ADVANCE:
            if _PROGRESS_ORDER.index(state) > current:
                progress.state = state
                progress.history.append(
                    ProgressEntry(at=request.now(), state=state, run_id=run_id)
                )
    request.store.write_progress(progress, root=request.root)


def _read_or_init_progress(request: DraftRequest) -> Progress:
    """Read the unit's progress, initializing a ``pending`` record if absent.

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters.

    Returns
    -------
    Progress
        The existing or a freshly initialized ``pending`` progress record.
    """
    try:
        return request.store.read_progress(request.unit_id, root=request.root)
    except FileNotFoundError:
        return Progress(unit_id=request.unit_id, state=ProgressState.pending)


def _load_or_init_provenance(
    store: PlanningStore, unit_id: str, *, root: Path
) -> Provenance:
    """Read a unit's provenance, initializing an empty record if absent.

    A unit that has only been declared (never signed off or steered) has no
    ``provenance.yaml`` yet; the first signoff or steering note initializes
    one.

    Parameters
    ----------
    store : PlanningStore
        The injected planning-directory store.
    unit_id : str
        The unit whose provenance is loaded.
    root : Path
        The repo root the store reads beneath.

    Returns
    -------
    Provenance
        The existing or a freshly initialized provenance record.
    """
    try:
        return store.read_provenance(unit_id, root=root)
    except FileNotFoundError:
        return Provenance(unit_id=unit_id)


@dataclass(frozen=True)
class ListRequest:
    """The injected collaborators for listing declared units (unit ls).

    Parameters
    ----------
    root : Path
        The repo root the store reads beneath.
    store : PlanningStore
        The injected planning-directory store.
    """

    root: Path
    store: PlanningStore


def list_units(request: ListRequest) -> list[UnitSummary]:
    """Summarize every declared unit with its resolved progress state (unit ls).

    Parameters
    ----------
    request : ListRequest
        The bundled collaborators for the listing.

    Returns
    -------
    list of UnitSummary
        One transient summary per declared unit, id-sorted; empty when none
        exist.
    """
    summaries: list[UnitSummary] = []
    for unit_id in request.store.list_unit_ids(root=request.root):
        unit = request.store.load_unit(unit_id, root=request.root)
        # PROV-04: derive lifecycle state from provenance (Pitfall 1 — list_units
        # did not previously load provenance). An absent record ⇒ empty
        # generations ⇒ pending, so no FileNotFoundError guard is needed.
        provenance = _load_or_init_provenance(request.store, unit_id, root=request.root)
        state = derive_progress(provenance)
        summaries.append(
            UnitSummary(
                unit_id=unit_id,
                title=unit.title,
                intent=unit.intent,
                state=state,
            )
        )
    return summaries


@dataclass(frozen=True)
class UnitStatus:
    """One row of the repo-level ``dogen status`` read-model (v1).

    Parameters
    ----------
    unit_id : str
        The unit's stable identifier.
    title : str
        The unit's human-readable title.
    intent : Intent
        The unit's Diátaxis direction.
    state : ProgressState
        The unit's resolved lifecycle state.
    signed_off : bool
        Whether the HITL gate act has been recorded.
    stale_plan : bool
        Whether ``unit.md`` has changed since it was signed off.
    next_action : str
        The suggested next CLI verb for this unit.
    next_id : str
        The machine routing token behind ``next_action`` (v1.2, R3).
    """

    unit_id: str
    title: str
    intent: Intent
    state: ProgressState
    signed_off: bool
    stale_plan: bool
    next_action: str
    next_id: str = ""


#: Internal suggestion key → the human one-liner template. ``fix`` and
#: ``redraft`` are presentation variants of the ``draft`` token (same routing):
#: ``fix`` applies the bounded correction the reviewer recorded, ``redraft`` is a
#: fresh pass. Splitting them (M2) keeps a bounded fix from reading as a
#: from-scratch re-draft — round-3's confusing "re-draft" for a fix verdict.
_NEXT_TEMPLATES: dict[str, str] = {
    "sign_off": "dogen signoff {unit_id}",
    "re_sign": "dogen signoff {unit_id} --re-sign  # plan changed since signoff",
    "draft": "dogen draft {unit_id}",
    "fix": "dogen draft {unit_id}  # apply the recorded fix",
    "redraft": "dogen draft {unit_id}  # re-draft per the recorded steering",
    "review": "dogen review {unit_id}",
    "publish": "accepted — the publishing commit/PR is yours",
    "done": "done",
}


def _suggest_next(
    state: ProgressState,
    *,
    signed_off: bool,
    stale_plan: bool,
    last_verdict: ReviewVerdict | None,
    unit_id: str,
) -> tuple[str, str]:
    """Derive the routing token and suggestion for one unit's status row (v1).

    Parameters
    ----------
    state : ProgressState
        The unit's resolved lifecycle state.
    signed_off : bool
        Whether the gate act exists.
    stale_plan : bool
        Whether the plan changed after signoff.
    last_verdict : ReviewVerdict or None
        The most recent structured review verdict, when one exists.
    unit_id : str
        The unit id interpolated into the suggestion.

    Returns
    -------
    tuple of (str, str)
        ``(next_id, next)`` — the machine routing token (``sign_off`` /
        ``re_sign`` / ``draft`` / ``review`` / ``publish`` / ``done``; skills
        translate it into loop language, never parrot the human line) and the
        one-line human suggestion in CLI terms.
    """
    if not signed_off:
        key = "sign_off"
    elif stale_plan:
        key = "re_sign"
    elif state is ProgressState.pending:
        key = "draft"
    elif state is ProgressState.drafted:
        key = "review"
    elif state is ProgressState.reviewed:
        if last_verdict is ReviewVerdict.accept:
            key = "publish"
        elif last_verdict is ReviewVerdict.fix:
            key = "fix"
        else:
            key = "redraft"
    else:
        key = "done"
    token = "draft" if key in {"fix", "redraft"} else key
    return token, _NEXT_TEMPLATES[key].format(unit_id=unit_id)


def unit_statuses(request: ListRequest) -> list[UnitStatus]:
    """Assemble the repo-level status board (``dogen status``, v1).

    Parameters
    ----------
    request : ListRequest
        The bundled collaborators for the read.

    Returns
    -------
    list of UnitStatus
        One row per declared unit, id-sorted; empty when none exist.
    """
    rows: list[UnitStatus] = []
    for unit_id in request.store.list_unit_ids(root=request.root):
        unit = request.store.load_unit(unit_id, root=request.root)
        provenance = _load_or_init_provenance(request.store, unit_id, root=request.root)
        # PROV-04: derive lifecycle state from the same provenance record used
        # for the signoff/stale checks below — one source of truth, no second read.
        state = derive_progress(provenance)
        signed = provenance.signoff is not None
        stale = False
        if signed and provenance.signoff is not None and provenance.signoff.plan_hash:
            text = request.store.read_unit_text(unit_id, root=request.root)
            stale = _sha256(text) != provenance.signoff.plan_hash
        last_verdict = next(
            (
                e.verdict
                for e in reversed(provenance.reviewer_edits)
                if e.verdict is not None
            ),
            None,
        )
        next_id, next_action = _suggest_next(
            state,
            signed_off=signed,
            stale_plan=stale,
            last_verdict=last_verdict,
            unit_id=unit_id,
        )
        rows.append(
            UnitStatus(
                unit_id=unit_id,
                title=unit.title,
                intent=unit.intent,
                state=state,
                signed_off=signed,
                stale_plan=stale,
                next_action=next_action,
                next_id=next_id,
            )
        )
    return rows


def find_unit_by_draft(request: ListRequest, draft_path: str) -> str | None:
    """Resolve which unit owns a drafted docs page (``unit show --by-draft``).

    The reverse lookup that keeps draft files clean of embedded markers (the
    Q5 decision): ownership is derivable from ``unit.md``'s target set
    (primary + extras, v1.2), so no stored index can desync.

    Parameters
    ----------
    request : ListRequest
        The bundled collaborators for the read.
    draft_path : str
        The draft path to resolve, with or without the leading ``docs/``.

    Returns
    -------
    str or None
        The owning unit id, or ``None`` when no declared unit targets it.
    """
    normalized = PurePosixPath(draft_path).as_posix()
    normalized = normalized.removeprefix("docs/")
    for unit_id in request.store.list_unit_ids(root=request.root):
        unit = request.store.load_unit(unit_id, root=request.root)
        if any(
            PurePosixPath(target).as_posix() == normalized for target in unit.targets
        ):
            return unit_id
    return None


@dataclass(frozen=True)
class RemoveRequest:
    """The injected collaborators and parameters for removing a unit (unit rm).

    Parameters
    ----------
    unit_id : str
        The unit to remove.
    root : Path
        The repo root the store deletes beneath.
    store : PlanningStore
        The injected planning-directory store.
    repo : RepoSeam or None
        The injected commit seam.
    """

    unit_id: str
    root: Path
    store: PlanningStore
    repo: RepoSeam | None = None


def remove(request: RemoveRequest) -> None:
    """Delete a declared unit's directory and its drafted docs output (unit rm).

    Parameters
    ----------
    request : RemoveRequest
        The bundled collaborators and parameters for the removal.

    Raises
    ------
    UnitNotFoundError
        If the unit directory does not exist (the store adapter's type,
        re-raised without importing the adapter — the seam stays intact).
    """
    try:
        unit: Unit | None = request.store.load_unit(request.unit_id, root=request.root)
    except (FileNotFoundError, ValueError):
        unit = None
    sphinx_target = unit.sphinx_target if unit is not None else None
    extra_targets = list(unit.extra_targets) if unit is not None else []
    # Pathspec discipline: only TRACKED pages join the removal commit's spec —
    # an undrafted (or untracked) page's path would make the seam's `git add`
    # fatal on an unmatched pathspec, which the tolerant wrapper degrades into
    # silently skipping the whole removal commit.
    candidates = ([sphinx_target] if sphinx_target else []) + extra_targets
    tracked: set[str] = set()
    if request.repo is not None and candidates:
        tracked = request.repo.tracked(
            root=request.root, paths=[f"docs/{t}" for t in candidates]
        )
    request.store.delete_unit(
        request.unit_id,
        root=request.root,
        sphinx_target=sphinx_target,
        extra_targets=extra_targets,
    )
    paths = [_unit_dir(request.root, request.unit_id)]
    paths.extend(
        request.root / "docs" / t for t in candidates if f"docs/{t}" in tracked
    )
    _commit_transition(
        request.repo,
        root=request.root,
        paths=paths,
        unit_id=request.unit_id,
        phase="removed",
        summary="unit removed",
    )


@dataclass(frozen=True)
class RenameRequest:
    """The injected collaborators and parameters for renaming a unit (unit mv).

    Parameters
    ----------
    old_id : str
        The current unit id.
    new_id : str
        The target unit id.
    root : Path
        The repo root the store operates beneath.
    store : PlanningStore
        The injected planning-directory store.
    repo : RepoSeam or None
        The injected commit seam.
    """

    old_id: str
    new_id: str
    root: Path
    store: PlanningStore
    repo: RepoSeam | None = None


def rename(request: RenameRequest) -> None:
    """Rename a declared unit's id everywhere it is stamped (unit mv).

    Parameters
    ----------
    request : RenameRequest
        The bundled collaborators and parameters for the rename.

    Raises
    ------
    ValueError
        If either id is unsafe.
    UnitNotFoundError
        If the source unit does not exist.
    UnitExistsError
        If the target unit already exists.
    """
    # Capture the draft's location(s) around the store move so the pathspec
    # can name the exact files: a wholesale `docs/` pathspec would sweep any
    # unrelated dirty docs file into the seam commit (D5's latent cousin),
    # and an unmatched pathspec would fail the commit outright.
    try:
        unit_before = request.store.load_unit(request.old_id, root=request.root)
    except FileNotFoundError:
        # Let rename_unit raise its domain UnitNotFoundError below.
        unit_before = None
    draft_existed = False
    if unit_before is not None:
        try:
            request.store.read_draft(unit_before, root=request.root)
        except FileNotFoundError:
            draft_existed = False
        else:
            draft_existed = True
    request.store.rename_unit(request.old_id, request.new_id, root=request.root)
    paths = [
        _unit_dir(request.root, request.old_id),
        _unit_dir(request.root, request.new_id),
    ]
    if draft_existed and unit_before is not None:
        unit_after = request.store.load_unit(request.new_id, root=request.root)
        paths.append(request.root / "docs" / unit_before.sphinx_target)
        if unit_after.sphinx_target != unit_before.sphinx_target:
            paths.append(request.root / "docs" / unit_after.sphinx_target)
    _commit_transition(
        request.repo,
        root=request.root,
        paths=paths,
        unit_id=request.new_id,
        phase="renamed",
        summary=f"{request.old_id} -> {request.new_id}",
    )


@dataclass(frozen=True)
class ContextAddRequest:
    """The injected collaborators and parameters for filing a context artifact.

    Parameters
    ----------
    name : str
        The artifact's landing filename (e.g. ``code-to-docs-map.md``).
    text : str
        The artifact's full content, landed as-is.
    root : Path
        The repo root the store writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    repo : RepoSeam or None
        The injected commit seam.
    """

    name: str
    text: str
    root: Path
    store: PlanningStore
    repo: RepoSeam | None = None


def add_context_artifact(request: ContextAddRequest) -> Path:
    """File a context artifact into the landing zone and commit it (v1).

    The B1/B2 contact surface: presence of a well-known filename under
    ``.dogen/context/`` is the whole contract, so this is a store write plus
    one transition commit.

    Parameters
    ----------
    request : ContextAddRequest
        The bundled collaborators and parameters.

    Returns
    -------
    pathlib.Path
        The path of the written artifact.
    """
    written = request.store.add_context(request.name, request.text, root=request.root)
    _commit_transition(
        request.repo,
        root=request.root,
        paths=[
            request.root / ".dogen" / "context" / request.name,
            _dogen_gitignore_path(request.root),
        ],
        unit_id=request.name,
        phase="context",
        summary=f"context artifact {request.name}",
    )
    return written
