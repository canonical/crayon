"""The F1 planning-directory schema (v1) as pure Pydantic v2 models.

This is the on-disk audit and provenance surface every later command writes to
(``unit.md`` front-matter, ``provenance.yaml``, ``config.yaml``); lifecycle
state is derived from provenance, not persisted (PROV-04). It is pure domain
code: it carries **zero vendor imports** so
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

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
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

#: Byte cap on the inline evidence excerpt (v1.2, D-01). The verbatim-capture
#: guarantee rides ``StepEvidence.output_sha256`` (the full captured bytes'
#: digest); the excerpt is only a bounded, human-readable window so
#: ``provenance.yaml`` stays loadable and no unbounded blob is ever inlined.
EXCERPT_CAP_BYTES = 4096


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
    """Lifecycle state of a single unit, **derived** from provenance (PROV-04).

    Not persisted: :func:`derive_progress` maps a unit's provenance record onto
    exactly one of three states — ``pending`` (no draft generation yet),
    ``drafted`` (a draft generation exists), and ``reviewed`` (a reviewer edit
    exists). Publishing stays the human's job and is never encoded here.
    """

    pending = "pending"
    drafted = "drafted"
    reviewed = "reviewed"


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
    ``status`` mirror is retired in v1 — lifecycle state is derived from the
    provenance record (PROV-04), and a stale extra ``status`` key in an old file
    is ignored on load.

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


class StepMode(StrEnum):
    """How a recorded step was executed (v1.2, EVID-01).

    ``agent`` — the host agent ran the step in-process; ``ta`` — a technical
    author ran it out of band. dogen never executes a step itself (the passenger
    pattern); this records *who* did.
    """

    agent = "agent"
    ta = "ta"


class StepVerdict(StrEnum):
    """The four-token per-step verdict vocabulary (v1.2, EVID-04, D-05).

    ``pass`` / ``fail`` / ``skipped`` / ``deviated`` are the stable *wire* values
    — ``skipped`` and ``deviated`` are first-class, never notes or flags. The
    member identifiers ``passed``/``failed`` differ from the wire values
    ``pass``/``fail`` because the latter are Python reserved words; the wire
    values are the D-05 vocabulary and the ``Dogen-Verdict`` commit-trailer
    values Plan 02 emits. A ``pass``/``fail`` carries its proof mechanically
    (exit code + captured output); ``skipped``/``deviated`` require a reason (D-06).
    """

    passed = "pass"
    failed = "fail"
    skipped = "skipped"
    deviated = "deviated"


class StepStatus(StrEnum):
    """The derived per-step completion status (v1.2, EVID-03).

    The result of :func:`derive_step_status`: ``resolved`` when a hash-matching
    evidence record proves the step (per the D-07/D-08 resolution rules), else
    ``unverified`` (no evidence, stale evidence, or a non-resolving verdict —
    default-FAIL). It is derived on read, never stored, and is deliberately **not**
    a fourth :class:`ProgressState` — verification surfaces here, never as a new
    lifecycle state.
    """

    unverified = "unverified"
    resolved = "resolved"


class StepEvidence(BaseModel):
    """The mechanical capture proving one step ran (``Step.evidence``, v1.2, EVID-01).

    Honest framing (carried from research + STATE): this schema proves a
    *well-shaped* capture exists — a real exit code, a bounded verbatim excerpt,
    and the SHA-256 of the full captured bytes — it does **not** prove the capture
    was not forged. dogen records and gates; it never executes the step and never
    claims tamper-proofness. No free-text "result" field is accepted as proof.
    SHA-256 here is content-addressing (integrity/dedup), not a security primitive.

    Parameters
    ----------
    mode : StepMode
        Who executed the step (``agent`` / ``ta``).
    command : str
        The command whose run this evidence captures.
    output_sha256 : str
        SHA-256 hex digest of the **full** captured output bytes — the
        verbatim-capture guarantee (D-01); the excerpt is only a bounded window.
    output_excerpt : str
        A bounded verbatim excerpt of the captured output, truncated to
        :data:`EXCERPT_CAP_BYTES` bytes on construction so ``provenance.yaml``
        stays loadable (D-01). The full bytes are represented only by
        ``output_sha256``, never an unbounded inline blob.
    exit_code : int
        The process exit code (``0`` == success).
    verdict : StepVerdict
        The four-token judgment (D-05).
    reason : str
        Required for ``skipped``/``deviated`` (enforced at the record-time
        micro-gate, Plan 02); ``""`` for ``pass``/``fail`` (their proof is
        mechanical, D-06). Omitted from serialization while empty.
    step_text_sha256 : str
        SHA-256 hex digest of the step text this evidence was captured against —
        the staleness bind (D-02): once the step text is edited it no longer
        matches, so the derivation rebinds the step to default-FAIL until it is
        re-verified.
    deterministic : bool
        Whether the step's output is expected to be reproducible; ``False`` marks
        a step whose output legitimately varies between runs (D-04) so a future
        re-verification does not spuriously fail a hash compare.
    at : str
        ISO-8601 timestamp of the capture.
    """

    mode: StepMode
    command: str
    output_sha256: str
    output_excerpt: str
    exit_code: int
    verdict: StepVerdict
    reason: str = ""
    step_text_sha256: str
    deterministic: bool = True
    at: str

    @field_validator("output_excerpt", mode="after")
    @classmethod
    def _cap_excerpt(cls, value: str) -> str:
        """Truncate the inline excerpt to :data:`EXCERPT_CAP_BYTES` bytes (D-01).

        The cap is a byte bound over the UTF-8 encoding, so a multibyte character
        straddling the boundary is dropped rather than split into invalid bytes.
        The full-output guarantee is unaffected — it rides ``output_sha256``.

        Parameters
        ----------
        value : str
            The raw excerpt.

        Returns
        -------
        str
            The excerpt, truncated to at most :data:`EXCERPT_CAP_BYTES` UTF-8 bytes.
        """
        encoded = value.encode("utf-8")
        if len(encoded) <= EXCERPT_CAP_BYTES:
            return value
        return encoded[:EXCERPT_CAP_BYTES].decode("utf-8", errors="ignore")

    @model_serializer(mode="wrap")
    def _omit_empty(self, handler: Any) -> dict[str, Any]:  # noqa: ANN401
        """Drop ``reason`` when empty; keep every other field (surgical omit-empty).

        Mirrors :meth:`Generation._omit_empty`: a blanket
        ``exclude_none``/``exclude_defaults`` is avoided because it over-drops.
        Only the ``pass``/``fail`` empty ``reason`` is removed so the serialized
        mapping stays minimal (D-06).

        Parameters
        ----------
        handler : Any
            The default Pydantic serialization handler for this model.

        Returns
        -------
        dict of str to Any
            The serialized mapping with an empty ``reason`` removed.
        """
        data = handler(self)
        if self.reason == "":
            data.pop("reason", None)
        return data


class Step(BaseModel):
    """One planned step in a unit's machine-owned step plan (v1.2).

    Lives in ``Provenance.steps``.

    Steps are provenance state — never written into the signed human ``unit.md``.
    The plan is authored/replaced whole (D-12) and each step's completion is
    *derived* from its evidence (:func:`derive_step_status`), never stored as a
    flag or cached count. Identity for re-matching a step across a whole-plan
    replace is the step-text hash (D-02), not ``id``.

    Parameters
    ----------
    id : str
        A stable, single-line short label — safe as a ``Dogen-Step`` commit-trailer
        value (D-15) and a human handle that survives a whole-plan replace. It is
        NOT the re-match key; the step-text hash is (D-02/D-12).
    text : str
        The step's instruction text; its SHA-256 is the evidence staleness bind.
    assumptions : list of str
        Preconditions the step assumes (D-03); persisted/round-tripped now,
        populated in Phase 13. Omitted from serialization while empty.
    invariants : list of str
        Invariants the step must preserve (D-03); same lifecycle as ``assumptions``.
    consumed : list of str
        Free-text state the step consumes (D-04); feeds Phase 13 branching/resume.
    produced : list of str
        Free-text state the step produces (D-04).
    deterministic : bool
        Whether the step's output is expected to be reproducible (D-04).
    evidence : StepEvidence or None
        The mechanical capture proving the step ran; ``None`` until recorded
        (default-FAIL until then). Omitted from serialization while ``None``.
    """

    id: str
    text: str
    assumptions: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    consumed: list[str] = Field(default_factory=list)
    produced: list[str] = Field(default_factory=list)
    deterministic: bool = True
    evidence: StepEvidence | None = None

    @model_serializer(mode="wrap")
    def _omit_empty(self, handler: Any) -> dict[str, Any]:  # noqa: ANN401
        """Drop the four empty list fields and a ``None`` ``evidence`` (surgical).

        Mirrors :meth:`Generation._omit_empty`. Keeps step-plan mappings minimal
        so a bare step (no assumptions/invariants/consumed/produced and no
        recorded evidence) serializes to just ``id``/``text``/``deterministic``.

        Parameters
        ----------
        handler : Any
            The default Pydantic serialization handler for this model.

        Returns
        -------
        dict of str to Any
            The serialized mapping with the empty additive fields removed.
        """
        data = handler(self)
        for name in ("assumptions", "invariants", "consumed", "produced"):
            if not getattr(self, name):
                data.pop(name, None)
        if self.evidence is None:
            data.pop("evidence", None)
        return data


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
    steps : list of Step
        The unit's machine-owned step plan and its per-step evidence (v1.2,
        additive, default ``[]``). Old records lack the key and load as ``[]``;
        the field is omitted from serialization while empty so a step-free record
        stays byte-identical to its pre-v1.2 shape with no ``SCHEMA_VERSION`` bump
        (EVID-06 keystone). Completion is *derived* from this list
        (:func:`all_steps_verified`), never stored.
    """

    schema_version: int = SCHEMA_VERSION
    unit_id: str
    signoff: Signoff | None = None
    signoff_history: list[Signoff] = Field(default_factory=list)
    steering: list[SteeringEntry] = Field(default_factory=list)
    generations: list[Generation] = Field(default_factory=list)
    reviewer_edits: list[ReviewerEdit] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_empty_steps(self, handler: Any) -> dict[str, Any]:  # noqa: ANN401
        """Drop ``steps`` when empty so step-free records stay byte-identical.

        The EVID-06 keystone: a v1.1 record and a v1.2 step-free record must
        serialize identically. ``steps`` is the only additive v1.2 field on
        :class:`Provenance`, so omitting it while empty keeps every pre-phase
        record's on-disk bytes unchanged (no new key, no ``SCHEMA_VERSION`` bump).
        A surgical wrap mirroring :meth:`Generation._omit_empty` — every other
        field serializes exactly as before.

        Parameters
        ----------
        handler : Any
            The default Pydantic serialization handler for this model.

        Returns
        -------
        dict of str to Any
            The serialized mapping with an empty ``steps`` removed.
        """
        data = handler(self)
        if not self.steps:
            data.pop("steps", None)
        return data

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


def derive_progress(prov: Provenance) -> ProgressState:
    """Derive a unit's lifecycle state from its provenance record alone (D-05).

    This is a **record-only** derivation (PROV-04): it reads the generation count
    and the latest generation's ``reviewer_edit_count`` snapshot, and never stats
    the drafted docs file, re-hashes the working tree, or opens any second stored
    artefact. Because the value is computed rather than
    stored, a read can never disagree with provenance — the desync class that
    motivated PROV-04 (git / provenance / progress divergence) is structurally
    impossible on the read side.

    The count-based rule:

    * no generations                                        ⇒ ``pending``
    * ``len(reviewer_edits) > latest.reviewer_edit_count``   ⇒ ``reviewed``
    * otherwise                                             ⇒ ``drafted``

    A redraft after a review falls back to ``drafted`` because the new generation
    snapshots the current ``len(reviewer_edits)`` into its ``reviewer_edit_count``,
    so the count is no longer strictly greater.

    Parameters
    ----------
    prov : Provenance
        The already-validated, in-memory provenance record.

    Returns
    -------
    ProgressState
        The derived lifecycle state (``pending``, ``drafted``, or ``reviewed``).
    """
    if not prov.generations:
        return ProgressState.pending
    latest = prov.generations[-1]
    if len(prov.reviewer_edits) > latest.reviewer_edit_count:
        return ProgressState.reviewed
    return ProgressState.drafted


def is_sealed(prov: Provenance) -> bool:
    """Derive whether a unit has *sealed* — released its target lease (D-01/D-03).

    A unit's claim on its target pages is a **lease**, held only while the unit
    is *in flight* and released the moment it seals. Sealed is defined purely
    over the loaded provenance record (D-01): a unit is sealed **iff the most
    recent verdict-bearing** ``reviewer_edits[]`` **entry is** ``accept``. A
    trailing non-verdict note appended after an accept is ignored (the scan
    stops at the first verdict-bearing entry, D-01); an empty or no-verdict
    history, or a latest verdict of ``fix``/``redraft``, is **in-flight** and
    holds its lease (D-03).

    Like :func:`derive_progress`, this is a **record-only** derivation
    (PROV-04): sealed is *derived on read*, never stored, so nothing can desync
    — there is no ``sealed`` field on :class:`Provenance` and none is added. It
    reads only the in-memory record: no ``Path``, no ``os.stat``, no git.

    Parameters
    ----------
    prov : Provenance
        The already-validated, in-memory provenance record.

    Returns
    -------
    bool
        ``True`` iff the latest verdict-bearing reviewer edit is ``accept``.
    """
    for edit in reversed(prov.reviewer_edits):
        if edit.verdict is not None:
            return edit.verdict is ReviewVerdict.accept
    return False


def _sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest of ``text`` encoded as UTF-8 (D-02).

    The single hashing discipline for the step-text staleness bind: it is
    content-addressing (integrity / staleness detection), **never** a security
    primitive — a match proves an evidence record is bound to this exact step
    text, never that the capture was not forged. Pure and zero-I/O: it hashes an
    in-memory string, never a file on disk.

    Parameters
    ----------
    text : str
        The step text to hash.

    Returns
    -------
    str
        The lowercase hex SHA-256 digest of the UTF-8 bytes of ``text``.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_step_status(step: Step) -> StepStatus:
    """Derive one step's completion status from its evidence alone (EVID-03, D-02).

    A pure, zero-I/O sibling of :func:`derive_progress`/:func:`is_sealed`: it reads
    only the in-memory :class:`Step` — no ``Path``, no ``os.stat``, no git, and no
    re-hashing of files on disk. A step resolves only when a hash-matching evidence
    record proves it; otherwise it is default-FAIL (``unverified``).

    The rule:

    * ``evidence is None``                                    ⇒ ``unverified``
    * ``evidence.step_text_sha256`` ≠ hash of ``step.text``   ⇒ ``unverified``
      (staleness, D-02 — an edited step rebinds to default-FAIL until re-verified)
    * verdict ``pass`` with a non-empty ``output_sha256``      ⇒ ``resolved``
    * verdict ``skipped`` with a non-empty ``reason``         ⇒ ``resolved`` (D-07)
    * verdict ``deviated`` with ``exit_code == 0`` and a
      non-empty ``output_sha256``                             ⇒ ``resolved`` (D-08)
    * verdict ``fail`` and every other case                  ⇒ ``unverified``
      (D-07 — ``fail`` never resolves; a reasonless skip or a non-zero-exit
      deviation does not resolve)

    WR-02 (read-side default-FAIL): the two proof-bearing verdicts
    (``pass``/``deviated``) re-assert the mechanical shape here rather than
    trusting the verdict token — a record carrying ``verdict: pass`` with an
    empty ``output_sha256`` (reachable via a hand-edited or externally-produced
    ``provenance.yaml``, an on-disk audit surface) derives ``unverified``. The
    write-time micro-gate closes the CLI path; the derivation is now
    self-sufficiently default-FAIL so it never resolves an *absent* capture.

    Honest framing: a hash match proves a *well-shaped* capture is bound to this
    exact step text — never that the capture was not forged.

    Parameters
    ----------
    step : Step
        The in-memory step and its optional evidence.

    Returns
    -------
    StepStatus
        ``resolved`` when the step's evidence resolves it, else ``unverified``.
    """
    evidence = step.evidence
    if evidence is None:
        return StepStatus.unverified
    if evidence.step_text_sha256 != _sha256_text(step.text):
        return StepStatus.unverified
    if evidence.verdict is StepVerdict.passed:
        # WR-02: fail closed on an absent capture — a pass without its output
        # hash carries no mechanical proof and must not resolve.
        return StepStatus.resolved if evidence.output_sha256 else StepStatus.unverified
    if evidence.verdict is StepVerdict.skipped and evidence.reason:
        return StepStatus.resolved
    if evidence.verdict is StepVerdict.deviated and evidence.exit_code == 0:
        # WR-02: same fail-closed re-assertion for the other proof-bearing verdict.
        return StepStatus.resolved if evidence.output_sha256 else StepStatus.unverified
    return StepStatus.unverified


def all_steps_verified(prov: Provenance) -> bool:
    """Derive whether every planned step resolves (EVID-03, EVID-06 keystone).

    The pure boolean the Plan 02 macro-gate keys on: ``True`` iff every step in
    ``prov.steps`` derives :attr:`StepStatus.resolved`. It is **vacuously True for
    an empty step plan** — a step-free unit is never blocked by the evidence gate,
    which is exactly what keeps step-free units byte-identical in behavior
    (EVID-06). Like its siblings it is record-only: no ``Path``, no ``os.stat``,
    no git, and it is never surfaced as a fourth :class:`ProgressState` or stored
    as a flag/cached count.

    Parameters
    ----------
    prov : Provenance
        The already-validated, in-memory provenance record.

    Returns
    -------
    bool
        ``True`` iff every present step resolves (and vacuously for an empty list).
    """
    return all(derive_step_status(s) is StepStatus.resolved for s in prov.steps)


def _latest_accept_edit(prov: Provenance) -> ReviewerEdit | None:
    """Return a unit's most recent ``accept`` reviewer edit, or ``None`` (D-04).

    The single backward scan that both the ordering key
    (:func:`_latest_accept_at`) and the supersede recorder (``plan_takeovers``,
    which reads the accept's ``files[]`` digest for a page) share, so the
    "newest accept" derivation lives in exactly one place and cannot drift.
    Record-only: no ``os.stat``, no git.

    Parameters
    ----------
    prov : Provenance
        The already-validated, in-memory provenance record.

    Returns
    -------
    ReviewerEdit or None
        The latest ``accept`` reviewer edit, or ``None`` when the record carries
        no ``accept`` verdict.
    """
    for edit in reversed(prov.reviewer_edits):
        if edit.verdict is ReviewVerdict.accept:
            return edit
    return None


def _latest_accept_at(prov: Provenance) -> datetime | None:
    """Return the aware timestamp of a unit's most recent ``accept`` (D-04).

    The cross-unit ordering key for multi-owner resolution: among several sealed
    owners of one page, the newest ``accept`` wins. This reads the latest
    ``accept`` reviewer edit (:func:`_latest_accept_edit`) and parses its ``at``
    timestamp to an aware :class:`~datetime.datetime`.

    Stored ``at`` values mix ``Z`` and ``+00:00`` UTC forms, which
    :func:`datetime.datetime.fromisoformat` on older Pythons — and raw string
    ordering everywhere — handle inconsistently. Normalizing ``Z`` → ``+00:00``
    before parsing yields a comparable aware datetime, defeating the mixed-form
    trap (never compare raw ``at`` strings). Like :func:`is_sealed`, this is
    record-only: no ``os.stat``, no git seal-commit time.

    Parameters
    ----------
    prov : Provenance
        The already-validated, in-memory provenance record.

    Returns
    -------
    datetime or None
        The aware timestamp of the latest ``accept`` edit, or ``None`` when the
        record carries no ``accept`` verdict.
    """
    edit = _latest_accept_edit(prov)
    if edit is None:
        return None
    # CR-02: ``at`` is an unvalidated ``str`` — a poisoned/hand-edited non-ISO
    # stamp must not crash the repo-wide scan. Fail closed: an un-parseable seal
    # time cannot participate in newest-accept ordering, so it is excluded
    # (``None``) rather than raised.
    try:
        dt = datetime.fromisoformat(edit.at.replace("Z", "+00:00"))
    except ValueError:
        return None
    # WR-02: the ``Z`` → ``+00:00`` swap only fixes the *form* of an already
    # offset stamp; a genuinely tz-less stamp parses naive and then raises
    # ``TypeError`` when compared against an aware one. Assume UTC when naive so
    # every comparison operates on aware datetimes.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Takeover:
    """One recorded supersede edge: a new claim over a sealed owner's page (D-05).

    A pure, immutable provenance-edge value produced by the adapter's lease scan
    (``plan_takeovers``) and carried up to the orchestrator commit, where it
    becomes a ``docs/<page> extends unit <owner> (sealed <sha12>)`` body line and
    a repeatable ``Dogen-Extends: <owner-id>`` trailer. It lives in
    :mod:`dogen.core.models` so both the adapter (which builds it) and the core
    orchestrator (which renders it) may import it without crossing the
    provider seam. Modeled on the frozen request dataclasses: no I/O, no
    behavior, just the four fields that name the edge.

    Parameters
    ----------
    page : str
        The docs-relative page the new unit claims (e.g. ``guide.md``).
    owner_id : str
        The superseded sealed owner's unit id (a validated single path segment).
    sealed_sha12 : str
        The first 12 hex of the owner's latest-accept ``files[]`` digest for
        ``page`` — the exact text its seal attests (A3).
    accept_at : str
        The owner's latest ``accept`` timestamp, verbatim from provenance.
    """

    page: str
    owner_id: str
    sealed_sha12: str
    accept_at: str


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
        The unit's derived lifecycle state (``pending`` when it has no draft
        generation yet — declared but not yet drafted).
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
    model : str
        The repo's persisted drafting model identity (additive, v1.1); ``""``
        when unrecorded, which fires ``model_unrecorded`` downstream. Resolved
        below an explicit ``--model`` flag and the ``DOGEN_MODEL`` env, above the
        built-in honest-empty. Old configs that predate this field simply lack
        it and load as ``""`` (no migration, no schema bump).
    model_origin : str
        Who vouched for :attr:`model` (the D-03 vocab ``""|ta|self|config|flag``);
        set to ``ta``/``self`` by ``dogen model set --origin`` and carried onto
        the generation's ``model_origin`` at draft time. ``""`` when no model is
        recorded.
    """

    schema_version: int = SCHEMA_VERSION
    provider: str = "host-harness"
    commits: CommitMode = CommitMode.auto
    model: str = ""
    model_origin: str = ""


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
