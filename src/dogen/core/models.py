"""The F1 planning-directory schema (v1) as pure Pydantic v2 models.

This is the on-disk audit and provenance surface every later command writes to
(``unit.md`` front-matter, ``provenance.yaml``, ``progress.yaml``,
``config.yaml``). It is pure domain code: it carries **zero vendor imports** so
the provider seam (SEAM-01) stays real, and every machine-readable model carries
a ``schema_version`` so future migrations are explicit and detectable
(D-34/PLAN-02).

Schema v1 (the traceability redesign) adds one spine across every artifact —
**unit id + run id + git commit** — and splits steering into its two real
concepts:

* ``Signoff`` — the single HITL gate act (author, timestamp, and the plan hash
  it approved), provably preceding any draft.
* ``SteeringEntry`` — the append-only guidance stream (from planning, from
  review verdicts, or added manually) that a re-draft reads.

One v0 design invariant remains load-bearing and must never be collapsed:

* ``Unit.sources`` (human-pointed, authored in ``unit.md``) and
  ``Generation.context_origins`` (what the agent *actually read*) are distinct
  fields — the gap between them is itself audit-relevant (D-37).

Schema v2 (the provenance unification) promotes ``Generation.files`` /
``ReviewerEdit.files`` to the sole digest authority (always ≥1 entry on a
generation, primary first), deletes the legacy primary mirrors
(``draft_path``/``draft_sha256``) and the reserved-empty ``verification`` block,
adds ``Generation.model_origin``, and makes ``effort``/``model_version``/``sdk``
omit-empty on serialization.

Records load transparently across versions: the ``Provenance`` migrator lifts a
v0 single ``steering`` mapping into ``signoff`` and then lifts a v1 record into
v2 (synthesizing ``files`` from the legacy digests, dropping the dead fields),
and ``Generation`` lifts plain-string ``context_origins`` into
:class:`ReadRecord` entries. Migration is lazy and load-time only (D-01): a read
never writes, so a repo may hold mixed v1/v2 sidecars indefinitely.
"""

import re
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

#: The current on-disk schema generation for every machine-readable model.
SCHEMA_VERSION = 2

#: Supported page extensions → format names (v1.2). The target extension IS
#: the unit's format — a derived fact, never a stored field that could drift.
PAGE_FORMATS: dict[str, str] = {".md": "myst", ".rst": "rst"}


class Intent(StrEnum):
    """Diátaxis direction the operator steers a unit toward.

    These are a *direction*, not four separate pipelines: one category per
    page/navigation path (D-35). The skeleton drives one intent at a time.
    """

    reference = "reference"
    tutorial = "tutorial"
    how_to = "how-to"
    explanation = "explanation"


class ProgressState(StrEnum):
    """Lifecycle state of a single unit (D-38).

    The tool advances ``pending → sourced → drafted`` automatically and sets
    ``reviewed`` on review; it **never** sets ``committed`` — that member exists
    only to encode the scope border (the human owns the publishing commit; the
    commit seam records dogen's own artifacts, it never publishes).
    """

    pending = "pending"
    sourced = "sourced"
    drafted = "drafted"
    reviewed = "reviewed"
    committed = "committed"


class Effort(StrEnum):
    """Reasoning effort for a draft pass.

    Mirrors the Copilot SDK ``reasoning_effort`` ``Literal`` (RESEARCH-verified
    to include ``xhigh``) without importing any SDK type — the value is a plain
    domain enum the adapter maps to the SDK at the seam.
    """

    low = "low"
    medium = "medium"
    high = "high"
    xhigh = "xhigh"


class SourceRole(StrEnum):
    """How a source entered the unit's grounding set (schema v1).

    ``primary`` sources are human-pointed starting points declared at planning
    time; ``discovered`` sources were found load-bearing during drafting and
    promoted into the unit's set. Both ground claims; the distinction records
    *who* pointed at them.
    """

    primary = "primary"
    discovered = "discovered"


class SourceRef(BaseModel):
    """A single source: a repo ``path`` xor an external ``ref``, version-stamped.

    Exactly one of ``path`` (a file in the docs repo) or ``ref`` (a reserved
    pointer to an external artifact, e.g. a future SDLC connector) is set.

    Parameters
    ----------
    path : str or None
        A repo-relative file path the operator points the agent at.
    ref : str or None
        A reserved external reference (CONN-01 is design-only this phase).
    commit : str
        The repo HEAD commit when this source was recorded, tying the unit to
        the code version it documents (schema v1); ``""`` when the repo had no
        commit or the stamp is unknown (e.g. a migrated v0 record).
    role : SourceRole
        Whether the source was human-pointed at planning time (``primary``) or
        promoted after being discovered during drafting (``discovered``).
    """

    path: str | None = None
    ref: str | None = None
    commit: str = ""
    role: SourceRole = SourceRole.primary

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "SourceRef":
        """Enforce the path-xor-ref invariant.

        Returns
        -------
        SourceRef
            The validated instance.

        Raises
        ------
        ValueError
            If neither or both of ``path`` and ``ref`` are set.
        """
        if (self.path is None) == (self.ref is None):
            raise ValueError("SourceRef requires exactly one of 'path' or 'ref'")
        return self


class Unit(BaseModel):
    """The editable steering+plan artifact (``unit.md`` front-matter, D-35/PLAN-03).

    The operator authors this via ``dogen unit new`` / ``dogen unit edit`` (or a
    hand-edit): it records intent, audience, title, the human-pointed sources,
    the Sphinx output target, and free-form steering notes. The v0 reserved
    ``status`` mirror is retired in v1 — ``progress.yaml`` is the sole lifecycle
    authority (D-38), and a stale extra ``status`` key in an old file is ignored
    on load.

    Parameters
    ----------
    schema_version : int
        On-disk schema version for explicit migrations (D-34); defaults to
        :data:`SCHEMA_VERSION`.
    unit_id : str
        Stable identifier; also the per-unit directory name.
    intent : Intent
        The Diátaxis direction to draft toward.
    audience : str
        Who the page is written for.
    title : str
        Human-readable page title.
    sources : list of SourceRef
        Human-pointed and promoted sources (distinct from the agent-read
        ``context_origins`` — D-37).
    sphinx_target : str
        Output path under ``docs/`` where the drafted page lands; its
        extension decides the unit's format (v1.2). The unit's **primary**
        (anchor) page.
    extra_targets : list of str
        Additional docs-relative pages in this unit's change set (v1.2) — the
        horizontal-fix / restructure surface. Same containment rules as the
        primary; empty for the ordinary one-page unit. The unit's page set is
        ``[sphinx_target, *extra_targets]``.
    steering_notes : str
        Free-form operator guidance seeded at declare time. The live guidance
        stream is ``Provenance.steering`` (append-only, v1); this field holds
        the initial planning note.
    """

    schema_version: int = SCHEMA_VERSION
    unit_id: str
    intent: Intent
    audience: str
    title: str
    sources: list[SourceRef] = Field(default_factory=list)
    sphinx_target: str
    extra_targets: list[str] = Field(default_factory=list)
    steering_notes: str = ""

    @model_validator(mode="after")
    def _contain_sphinx_target(self) -> "Unit":
        """Reject absolute / ``..``-bearing / duplicated targets (T-02.1-01).

        Every target is operator-authored and load-bearing: each becomes a
        write path under ``docs/``. Enforcing containment once at the schema
        boundary — mirroring how :class:`SourceRef` validates its own shape —
        keeps the invariant from depending solely on the write adapter (CR-01).
        v1.2 applies the same rule to every ``extra_targets`` entry and rejects
        duplicates (including an extra equal to the primary).

        Returns
        -------
        Unit
            The validated instance.

        Raises
        ------
        ValueError
            If any target is empty, absolute, contains a ``..`` part, or
            duplicates another target in the set.
        """
        for target in (self.sphinx_target, *self.extra_targets):
            if not target:
                raise ValueError("a docs target must not be empty")
            if (
                PurePosixPath(target).is_absolute()
                or PureWindowsPath(target).is_absolute()
            ):
                raise ValueError(f"a docs target must be relative: {target!r}")
            parts = PurePosixPath(target).parts + PureWindowsPath(target).parts
            if ".." in parts:
                raise ValueError(f"a docs target must not contain '..': {target!r}")
        targets = [self.sphinx_target, *self.extra_targets]
        if len(set(targets)) != len(targets):
            raise ValueError(f"duplicate docs targets in the unit's set: {targets!r}")
        return self

    @property
    def format(self) -> str:
        """The unit's page format, derived from the target extension (v1.2).

        The extension IS the format — no stored field to drift: ``.md`` →
        ``myst``, ``.rst`` → ``rst``. Unknown extensions (possible only on
        records written before the eager extension check) fall back to
        ``myst``.

        Returns
        -------
        str
            ``"myst"`` or ``"rst"``.
        """
        suffix = PurePosixPath(self.sphinx_target).suffix
        return PAGE_FORMATS.get(suffix, "myst")

    @property
    def targets(self) -> list[str]:
        """The unit's full page set, primary first (v1.2).

        Returns
        -------
        list of str
            ``[sphinx_target, *extra_targets]``.
        """
        return [self.sphinx_target, *self.extra_targets]


class Signoff(BaseModel):
    """The recorded HITL gate act (``provenance.yaml.signoff``, v1; was v0 steering).

    Stamped by ``dogen signoff`` as a discrete act that provably precedes any
    draft — the strongest AC5 audit signal (HITL-01/02). In v1 the act attests
    the **whole unit plan**: ``plan_hash`` freezes the exact ``unit.md`` the
    author approved, so a post-signoff plan edit is detectable (a stale hash)
    rather than silent.

    Parameters
    ----------
    author : str
        Captured from git config at signoff time (D-41).
    at : str
        ISO-8601 timestamp of the signoff act.
    intent : Intent
        The approved Diátaxis direction.
    audience : str
        The approved audience.
    plan_hash : str
        SHA-256 hex digest of the full ``unit.md`` text the author signed off;
        ``""`` on a record migrated from v0 (the act predates plan hashing).
    commit : str
        The repo HEAD commit at signoff time; ``""`` when the repo had no
        commit or the record was migrated from v0.
    """

    author: str
    at: str
    intent: Intent
    audience: str
    plan_hash: str = ""
    commit: str = ""


class SteeringOrigin(StrEnum):
    """Where a steering entry came from (schema v1).

    ``plan`` entries are synthesized during planning intake; ``review`` entries
    are appended automatically from a fix/re-draft review verdict; ``manual``
    entries were added directly via ``dogen steer --note``.
    """

    plan = "plan"
    review = "review"
    manual = "manual"


class SteeringEntry(BaseModel):
    """One appended guidance note in the unit's steering stream (v1).

    The stream closes the loop the v0 design left open: mid-loop corrections
    (most importantly review verdicts that demand a re-draft) land here
    durably, timestamped and authored, where the next draft pass reads them —
    never only in a conversation.

    Parameters
    ----------
    author : str
        Captured from git config when the entry was recorded (D-41).
    at : str
        ISO-8601 timestamp of the entry.
    note : str
        The guidance text.
    origin : SteeringOrigin
        Where the entry came from (``plan`` / ``review`` / ``manual``).
    """

    author: str
    at: str
    note: str
    origin: SteeringOrigin = SteeringOrigin.manual


class FileDigest(BaseModel):
    """One written page's path and content hash (v1.2, multi-file units).

    Parameters
    ----------
    path : str
        The repo-relative page path (``docs/…``).
    sha256 : str
        The SHA-256 hex digest of the page's exact text.
    """

    path: str
    sha256: str


class ReadRecord(BaseModel):
    """A single observed read: a path plus the commit it was read at (v1).

    The structured replacement for v0's plain-string ``context_origins``
    entries, so what the agent actually read is tied to the code version it
    read (the traceability spine).

    Parameters
    ----------
    path : str
        The repo-relative path that was read.
    commit : str
        The repo HEAD commit when the read happened; ``""`` when unknown
        (e.g. a migrated v0 record or a repo with no commits).
    note : str
        Optional free-text context for the read (v1.2) — e.g. why an
        out-of-repo origin carries no commit stamp ("external dependency,
        pinned by go.sum"). Prose belongs here, never in ``commit``.
    """

    path: str
    commit: str = ""
    note: str = ""


class Generation(BaseModel):
    """One draft pass recorded in ``provenance.yaml.generations[]`` (D-36/PLAN-04).

    Parameters
    ----------
    model : str
        The model name used for the pass.
    model_version : str
        The resolved model version; ``""`` when the provider does not report
        one. Omitted from serialization while empty (v2, PROV-02).
    effort : Effort or None
        Reasoning effort the pass ran at; ``None`` when unknown. Omitted from
        serialization while ``None`` (v2, PROV-02).
    tooling_version : str
        The ``dogen`` package version that produced the pass.
    sdk : str
        The pinned agent SDK identifier/version; ``""`` when the provider is
        SDK-free. Omitted from serialization while empty (v2, PROV-02).
    model_origin : str
        How the recorded model identity was established (``""``|``ta``|``self``
        |``config``|``flag``); ``""`` until Phase 8 populates it (v2, PROV-02).
    provider : str
        The selected provider name (e.g. ``mock``/``copilot``). Defaults to the
        empty string. OQ-1 additive provenance extension — see ``mode``.
    mode : str
        The run mode (``driver``/``passenger``). Defaults to the empty string.
    context_origins : list of ReadRecord
        What the agent *actually read* — distinct from human-pointed sources
        (D-37). v0 plain strings are lifted to :class:`ReadRecord` on load.
    tools_used : list of str
        Source-qualified tool identifiers exercised in the pass.
    gaps : list of str
        Confidence gaps the writer reported instead of narrating them in the
        drafted prose (the stance contract's provenance outlet, v1).
    run_id : str
        Correlates the on-disk record to the runtime trace (OBS-03/D-22).
    at : str
        ISO-8601 timestamp of the pass.
    action : str
        The orchestrator action that produced this entry (e.g. ``draft``).
    handoff_path : str
        Repo-relative path of the passenger handoff file that carried the
        text, ``""`` for driver passes (v1 cross-ref).
    source_commit : str
        The repo HEAD commit when the pass ran — the code version the draft
        describes; ``""`` when the repo had no commit (v1).
    steering_count : int
        ``len(provenance.steering)`` at record time. The streams are
        append-only, so a later count larger than this means new steering
        arrived after the pass — the deterministic ordering signal behind the
        unsteered-redraft warning (timestamps mix ``Z``/``+00:00`` forms and
        cannot be compared). ``0`` on records that predate the field, which
        fails open (no warning).
    reviewer_edit_count : int
        ``len(provenance.reviewer_edits)`` at record time; same role as
        ``steering_count``.
    gaps_note : str
        The writer's justification for an empty ``gaps`` list, carried from
        the context report (v1.2); ``""`` on older records.
    files : list of FileDigest
        Every page this pass wrote, primary first, each with its content hash
        — the sole digest authority (v2, PROV-01). Always carries at least one
        entry; single- and multi-file units share this shape.
    """

    model: str
    model_version: str = ""
    effort: Effort | None = None
    tooling_version: str
    sdk: str = ""
    model_origin: str = ""
    provider: str = ""
    mode: str = ""
    context_origins: list[ReadRecord] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    gaps_note: str = ""
    files: list[FileDigest] = Field(default_factory=list)
    run_id: str
    at: str
    action: str
    handoff_path: str = ""
    source_commit: str = ""
    steering_count: int = 0
    reviewer_edit_count: int = 0

    @field_validator("context_origins", mode="before")
    @classmethod
    def _lift_v0_strings(cls, value: object) -> object:
        """Lift v0 plain-string origins into :class:`ReadRecord` mappings.

        Parameters
        ----------
        value : object
            The raw ``context_origins`` value from disk or a caller.

        Returns
        -------
        object
            The value with any plain-string entries wrapped as
            ``{"path": <str>}`` so v0 records validate under the v1 shape.
        """
        if isinstance(value, list):
            return [{"path": v} if isinstance(v, str) else v for v in value]
        return value

    @model_validator(mode="after")
    def _require_files(self) -> "Generation":
        """Enforce the ≥1 ``files`` invariant (v2, PROV-01, RESEARCH Pitfall 5).

        Every generation is a written pass, so it must carry at least one page
        digest. A migrated legacy record whose primary digest cannot be
        synthesized fails here as a :class:`ValidationError` rather than
        serializing a false-empty seal.

        Returns
        -------
        Generation
            The validated instance.
        """
        if not self.files:
            raise ValueError(
                "Generation.files must carry at least one page digest (PROV-01)"
            )
        return self

    @model_serializer(mode="wrap")
    def _omit_empty(self, handler: Any) -> dict[str, Any]:  # noqa: ANN401
        """Drop exactly the three PROV-02 fields when empty; keep everything else.

        A surgical omit-empty (RESEARCH Pattern 2): ``effort`` when ``None`` and
        ``model_version``/``sdk`` when ``""`` are popped from the serialized
        mapping. A blanket ``exclude_none``/``exclude_defaults`` is deliberately
        avoided because it over-drops unrelated empty fields.

        Parameters
        ----------
        handler : Any
            The default Pydantic serialization handler for this model.

        Returns
        -------
        dict of str to Any
            The serialized mapping with only the empty PROV-02 fields removed.
        """
        data = handler(self)
        if self.effort is None:
            data.pop("effort", None)
        if self.model_version == "":
            data.pop("model_version", None)
        if self.sdk == "":
            data.pop("sdk", None)
        return data


class ReviewVerdict(StrEnum):
    """The reviewer's structured judgment of a drafted unit (v1).

    ``accept`` seals the draft (its hash is stamped on the edit); ``fix`` and
    ``redraft`` route the unit back to drafting and append the verdict note to
    the steering stream so the next pass reads it.
    """

    accept = "accept"
    fix = "fix"
    redraft = "redraft"


class ReviewerEdit(BaseModel):
    """A post-generation human review record (``reviewer_edits[]``, D-36/PLAN-05).

    Parameters
    ----------
    at : str
        ISO-8601 timestamp of the review.
    reviewer : str
        Captured from git config at review time (D-41).
    summary : str
        The reviewer's note describing the judgment.
    verdict : ReviewVerdict or None
        The structured verdict (v1); ``None`` on a record migrated from v0.
    files : list of FileDigest
        Every page an ``accept`` verdict sealed, with content hashes — the sole
        seal authority (v2, PROV-01); empty for non-accept verdicts (they never
        sealed).
    """

    at: str
    reviewer: str
    summary: str
    verdict: ReviewVerdict | None = None
    files: list[FileDigest] = Field(default_factory=list)


def _lift_v0_steering(data: dict[str, Any]) -> dict[str, Any]:
    """v0→v1: lift a mapping-valued ``steering`` (the old gate act) to ``signoff``.

    Parameters
    ----------
    data : dict of str to Any
        The raw input mapping.

    Returns
    -------
    dict of str to Any
        A copy with a v0 ``steering`` mapping promoted to ``signoff`` and the
        stream emptied, or the input unchanged when it is not a v0 record.
    """
    steering = data.get("steering")
    if isinstance(steering, dict):
        migrated = dict(data)
        migrated.setdefault("signoff", None)
        if migrated["signoff"] is None:
            migrated["signoff"] = steering
        migrated["steering"] = []
        return migrated
    if steering is None and "steering" in data:
        migrated = dict(data)
        migrated["steering"] = []
        return migrated
    return data


def _primary_digest(files: Any) -> tuple[str | None, str | None]:  # noqa: ANN401
    """Return the ``(path, sha256)`` of a file list's primary entry, if any."""
    if isinstance(files, list) and files:
        first = files[0]
        if isinstance(first, dict):
            return first.get("path"), first.get("sha256")
        return getattr(first, "path", None), getattr(first, "sha256", None)
    return None, None


def _lift_generation(gen: dict[str, Any]) -> dict[str, Any]:
    """v1→v2: synthesize ``files`` from a generation's legacy primary digest.

    ``files`` wins on disagreement (D-03): a present, non-empty ``files`` is
    kept verbatim and the legacy mirrors are simply dropped. Copy-then-mutate —
    the input dict is never mutated in place.

    Parameters
    ----------
    gen : dict of str to Any
        One raw generation mapping.

    Returns
    -------
    dict of str to Any
        The generation lifted to v2 shape (legacy keys dropped, ``model_origin``
        defaulted).
    """
    out = dict(gen)
    if not out.get("files"):
        path = out.get("draft_path")
        sha = out.get("draft_sha256")
        if path and sha:
            out["files"] = [{"path": path, "sha256": sha}]
    out.pop("draft_path", None)
    out.pop("draft_sha256", None)
    out.setdefault("model_origin", "")
    return out


def _borrow_edit_path(sha: str, gens: list[Any]) -> str | None:
    """Borrow a reviewer edit's seal path from its paired generation (Pitfall 3).

    A legacy ``ReviewerEdit`` carried only a primary hash with no path. Match
    the generation whose primary sha equals the edit's, else fall back to the
    latest generation that carries a primary path.

    Parameters
    ----------
    sha : str
        The edit's legacy ``draft_sha256``.
    gens : list of Any
        The already-lifted generations (dicts or model instances).

    Returns
    -------
    str or None
        The borrowed docs-relative path, or ``None`` when none is available.
    """
    fallback: str | None = None
    for gen in gens:
        files = (
            gen.get("files") if isinstance(gen, dict) else getattr(gen, "files", None)
        )
        path, gsha = _primary_digest(files)
        if path:
            fallback = path
            if gsha == sha:
                return path
    return fallback


def _lift_reviewer_edit(edit: dict[str, Any], gens: list[Any]) -> dict[str, Any]:
    """v1→v2: synthesize an accept edit's ``files`` from its legacy seal hash.

    Non-accept edits carry an empty ``draft_sha256`` and never sealed — their
    ``files`` stay empty. Copy-then-mutate.

    Parameters
    ----------
    edit : dict of str to Any
        One raw reviewer-edit mapping.
    gens : list of Any
        The already-lifted generations, to borrow the seal path from.

    Returns
    -------
    dict of str to Any
        The edit lifted to v2 shape (legacy ``draft_sha256`` dropped).
    """
    out = dict(edit)
    sha = out.get("draft_sha256", "")
    if sha and not out.get("files"):
        path = _borrow_edit_path(sha, gens)
        if path:
            out["files"] = [{"path": path, "sha256": sha}]
    out.pop("draft_sha256", None)
    return out


def _lift_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """v1→v2: drop the ``verification`` block and legacy digests, stamp v2.

    Copy-then-mutate throughout (never mutates the input): each generation and
    reviewer edit is lifted into a fresh dict, and ``schema_version`` is stamped
    current so a re-load is a no-op (Pitfall 4).

    Parameters
    ----------
    data : dict of str to Any
        The (already v0-lifted) raw mapping.

    Returns
    -------
    dict of str to Any
        The mapping lifted to v2 shape.
    """
    out = dict(data)
    out.pop("verification", None)
    gens = out.get("generations")
    lifted_gens: list[Any] = []
    if isinstance(gens, list):
        lifted_gens = [
            _lift_generation(gen) if isinstance(gen, dict) else gen for gen in gens
        ]
        out["generations"] = lifted_gens
    edits = out.get("reviewer_edits")
    if isinstance(edits, list):
        out["reviewer_edits"] = [
            _lift_reviewer_edit(edit, lifted_gens) if isinstance(edit, dict) else edit
            for edit in edits
        ]
    out["schema_version"] = SCHEMA_VERSION
    return out


class Provenance(BaseModel):
    """The unit's consolidated audit record (``provenance.yaml``, D-36).

    Parameters
    ----------
    schema_version : int
        On-disk schema version (D-34); defaults to :data:`SCHEMA_VERSION`.
    unit_id : str
        The unit this record belongs to.
    signoff : Signoff or None
        The recorded HITL gate act; ``None`` until ``dogen signoff`` runs.
        (v0 stored this as a single ``steering`` mapping — migrated on load.)
    signoff_history : list of Signoff
        Superseded gate acts, oldest first (v1.2). A re-sign appends the act
        it replaces before overwriting ``signoff``, so every approved plan
        hash stays recoverable from the tip artifact alone — not just from
        git history (the round-2 opencode audit gap).
    steering : list of SteeringEntry
        The append-only guidance stream (v1): planning notes, review-verdict
        notes, and manual ``dogen steer --note`` entries, in recorded order.
    generations : list of Generation
        One entry per draft pass.
    reviewer_edits : list of ReviewerEdit
        Post-generation human reviews; empty at scaffold time.
    """

    schema_version: int = SCHEMA_VERSION
    unit_id: str
    signoff: Signoff | None = None
    signoff_history: list[Signoff] = Field(default_factory=list)
    steering: list[SteeringEntry] = Field(default_factory=list)
    generations: list[Generation] = Field(default_factory=list)
    reviewer_edits: list[ReviewerEdit] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate(cls, data: Any) -> Any:  # noqa: ANN401
        """Lift an on-disk record forward to the current schema (v0→v1→v2).

        The two lifts chain in one load-time pass (D-01, lazy — a read never
        writes). v0→v1: a mapping-valued ``steering`` (the old single gate act)
        becomes ``signoff`` and the stream empties. v1→v2: legacy primary
        digests (``draft_path``/``draft_sha256`` on a generation, ``draft_sha256``
        on an accept edit) are synthesized into ``files`` (``files`` wins on
        disagreement, D-03), the reserved ``verification`` block and legacy
        mirrors are dropped, ``model_origin`` defaults in, and ``schema_version``
        is stamped current. The v1→v2 lift is skipped for a record already at
        (or beyond) the current version, so a re-load is a no-op (Pitfall 4).

        Parameters
        ----------
        data : Any
            The raw input mapping (or a non-mapping passed through untouched).

        Returns
        -------
        Any
            The migrated mapping, stamped ``schema_version`` current.
        """
        if not isinstance(data, dict):
            return data
        original_version = data.get("schema_version")
        data = _lift_v0_steering(data)
        already_current = (
            isinstance(original_version, int) and original_version >= SCHEMA_VERSION
        )
        if not already_current:
            data = _lift_v1_to_v2(data)
        return data


class ProgressEntry(BaseModel):
    """One transition in a unit's progress history (D-38).

    Parameters
    ----------
    at : str
        ISO-8601 timestamp of the transition.
    state : ProgressState
        The state entered at this transition.
    run_id : str
        The draft run (or review act) that caused the transition, when one did
        (v1 cross-ref); ``""`` on migrated v0 entries and manual transitions.
    """

    at: str
    state: ProgressState
    run_id: str = ""


class Progress(BaseModel):
    """The per-unit state machine (``progress.yaml``, D-38/PLAN-06).

    Parameters
    ----------
    schema_version : int
        On-disk schema version (D-34); defaults to :data:`SCHEMA_VERSION`.
    unit_id : str
        The unit this record belongs to.
    state : ProgressState
        Current lifecycle state.
    history : list of ProgressEntry
        Ordered transition log.
    """

    schema_version: int = SCHEMA_VERSION
    unit_id: str
    state: ProgressState
    history: list[ProgressEntry] = Field(default_factory=list)


class UnitSummary(BaseModel):
    """A transient read-model summarizing one declared unit for listing.

    Assembled on demand by the ``list_units`` use-case from a unit's ``unit.md``
    and its resolved progress state, purely for the ``dogen unit ls`` /
    ``dogen status`` surfaces. It is never persisted, so it carries no
    ``schema_version``; it stays pure domain code with zero vendor imports so
    the provider seam (SEAM-01) stays real.

    Parameters
    ----------
    unit_id : str
        The unit's stable identifier and per-unit directory name.
    title : str
        The unit's human-readable page title.
    intent : Intent
        The unit's steered Diátaxis direction.
    state : ProgressState
        The unit's resolved lifecycle state (``pending`` when it has no
        ``progress.yaml`` yet — declared but not yet drafted).
    """

    unit_id: str
    title: str
    intent: Intent
    state: ProgressState


class ContextReport(BaseModel):
    """A provider's self-report of what a draft pass actually read (v1).

    The uniform provenance contract for every provider: the host-harness
    passenger writes it as ``report.yaml`` next to the handoff (ingested via
    ``dogen draft --report``); the Copilot driver synthesizes the same fields
    from its observed session tool events. It closes the v0 structural hole
    where a passenger had no channel to report reads — honest-empty remains
    possible, but becomes a choice, not an inevitability.

    Parameters
    ----------
    schema_version : int
        On-disk schema version; defaults to :data:`SCHEMA_VERSION`.
    context_origins : list of ReadRecord
        Everything the writer actually read, commit-stamped. At ingest each
        stamp must be a hex SHA or honestly empty (v1.2) — explanatory prose
        goes in the entry's ``note``, so audits can machine-verify every pin.
    tools_used : list of str
        Tool identifiers the writer exercised.
    gaps : list of str
        Confidence gaps: claims the writer could not verify at their origin
        and therefore left out of the prose (the stance contract's outlet).
    gaps_note : str
        A one-line justification expected when ``gaps`` is empty (v1.2) —
        an empty list next to deep internals reads is the round-2
        overconfidence pattern; the note makes "genuinely nothing unverified"
        an explicit claim rather than a default.
    """

    schema_version: int = SCHEMA_VERSION
    context_origins: list[ReadRecord] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    gaps_note: str = ""

    @model_validator(mode="after")
    def _hex_or_empty_stamps(self) -> "ContextReport":
        """Require every origin's commit stamp be a hex SHA or empty (v1.2).

        This validates only the *report* boundary (ingest); the shared
        :class:`ReadRecord` stays permissive so provenance records written
        before v1.2 keep loading.

        Returns
        -------
        ContextReport
            The validated instance.

        Raises
        ------
        ValueError
            If any ``context_origins[].commit`` is neither empty nor a
            7-40 char lowercase hex string.
        """
        for origin in self.context_origins:
            if origin.commit and not re.fullmatch(r"[0-9a-f]{7,40}", origin.commit):
                raise ValueError(
                    f"origin {origin.path!r}: commit must be a hex SHA or "
                    f"empty, got {origin.commit!r} — put explanations in the "
                    "entry's 'note' field"
                )
        return self


class CommitMode(StrEnum):
    """Whether the commit seam records transitions automatically (v1).

    ``auto`` commits dogen's own artifacts (and the draft) at every lifecycle
    transition; ``off`` disables the seam for repos that manage history
    themselves. The seam never pushes, opens PRs, builds, or publishes.
    """

    auto = "auto"
    off = "off"


class DogenConfig(BaseModel):
    """Per-repo configuration (``.dogen/config.yaml``, v1).

    Provider selection is **explicit** (the Q6/RC-5 decision): the shipped
    default is the hardened ``host-harness`` passenger, and the Copilot driver
    runs only when this file (or a flag/env with higher precedence) names it.
    No capability probe ever silently picks a provider.

    Parameters
    ----------
    schema_version : int
        On-disk schema version; defaults to :data:`SCHEMA_VERSION`.
    provider : str
        The repo's drafting provider (``host-harness`` / ``copilot`` /
        ``mock``); defaults to ``host-harness``.
    commits : CommitMode
        Whether the commit seam records transitions automatically.
    """

    schema_version: int = SCHEMA_VERSION
    provider: str = "host-harness"
    commits: CommitMode = CommitMode.auto


class DraftResult(BaseModel):
    """A drafting outcome in pure domain terms (no SDK shapes leak in).

    The adapter translates the vendor's response into this type at the seam
    (anti-corruption), so ``core/`` never sees an SDK message object.

    Parameters
    ----------
    text : str
        The drafted **primary** page content, in the unit's format (MyST or
        rST).
    pages : dict of str to str
        Extra pages for a multi-file unit (v1.2), keyed by docs-relative
        target path; empty for the ordinary one-page unit. The primary stays
        in ``text``.
    model : str
        The model that produced the draft.
    model_version : str
        The resolved model version (``"unknown"`` when the backend does not
        report one), kept distinct from ``model`` so the provenance record does
        not misrepresent a model name as a version (WR-03).
    output_tokens : int
        Tokens emitted (a provenance input).
    run_id : str
        Correlates the result to the runtime trace (OBS-03/D-22).
    context_origins : list of str
        The repo-relative paths the provider *actually read* during the pass,
        as reported/observed by the backend — distinct from the unit's
        human-pointed ``sources`` (D-37). The orchestrator stamps each entry
        with the source commit when recording (v1). Empty when the backend
        cannot report observed reads (an honest "nothing observed"); the
        orchestrator records this verbatim and never substitutes
        ``unit.sources`` (BL-01).
    tools_used : list of str
        Source-qualified tool identifiers the provider exercised, as reported
        by the backend. Empty when nothing was observed (BL-01).
    effort_used : Effort or None
        The reasoning effort the provider actually ran at (IN-03). When set,
        the orchestrator records it on the generation so the audit entry
        reflects the effort the SDK truly used rather than only the requested
        value; ``None`` means the provider did not report one and the requested
        effort stands.
    sdk : str
        The adapter-reported agent SDK identifier/version (D-14); ``""`` for
        SDK-free providers (the mock and the host-harness passenger).
    mode : str
        The provider-reported operational role (D-12): ``"driver"`` (headless,
        bounded-toolset, authoritative provenance) or ``"passenger"`` (rides
        the host harness).
    """

    text: str
    pages: dict[str, str] = Field(default_factory=dict)
    model: str
    model_version: str = "unknown"
    output_tokens: int
    run_id: str
    context_origins: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    effort_used: Effort | None = None
    sdk: str = ""
    mode: str = ""
