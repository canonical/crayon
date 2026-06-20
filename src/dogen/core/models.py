# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

"""The F1 planning-directory schema (v0) as pure Pydantic v2 models.

This is the on-disk audit and provenance surface every later command writes to
(``unit.md`` front-matter, ``provenance.yaml``, ``progress.yaml``). It is pure
domain code: it carries **zero vendor imports** so the provider seam (SEAM-01)
stays real, and every machine-readable model carries a ``schema_version`` so
future migrations are explicit and detectable (D-34/PLAN-02).

Two design invariants are load-bearing and must never be collapsed:

* ``Unit.sources`` (human-pointed, authored in ``unit.md``) and
  ``Generation.context_origins`` (what the agent *actually read*) are distinct
  fields — the gap between them is itself audit-relevant (D-37).
* ``Verification`` and ``reviewer_edits`` are reserved present-but-empty at v0
  (D-36/PLAN-07): the fields exist so a later phase can fill them without a
  breaking migration.
"""

from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath

from pydantic import BaseModel, Field, model_validator


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
    only to encode the scope border (the human owns the commit).
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


class SourceRef(BaseModel):
    """A single human-pointed source: a repo ``path`` xor an external ``ref``.

    Exactly one of ``path`` (a file in the docs repo) or ``ref`` (a reserved
    pointer to an external artifact, e.g. a future SDLC connector) is set.

    Parameters
    ----------
    path : str or None
        A repo-relative file path the operator points the agent at.
    ref : str or None
        A reserved external reference (CONN-01 is design-only this phase).
    """

    path: str | None = None
    ref: str | None = None

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

    The operator authors this by hand: it records intent, audience, title, the
    human-pointed sources, the Sphinx output target, and free-form steering
    notes. ``status`` is **reserved and not yet maintained** (WR-02): the
    authoritative lifecycle state lives in ``progress.yaml`` (D-38), and no
    command writes ``status`` back to ``unit.md``, so it must not be read as a
    live progress mirror. It is kept on the schema so a later phase can populate
    it without a breaking migration.

    Parameters
    ----------
    schema_version : int
        On-disk schema version for explicit migrations (D-34); defaults to ``0``.
    unit_id : str
        Stable identifier; also the per-unit directory name.
    intent : Intent
        The Diátaxis direction to draft toward.
    audience : str
        Who the page is written for.
    title : str
        Human-readable page title.
    sources : list of SourceRef
        Human-pointed sources (distinct from agent-read ``context_origins``).
    sphinx_target : str
        Output path under ``docs/`` where the drafted MyST lands.
    steering_notes : str
        Free-form operator guidance for the draft.
    status : ProgressState
        Reserved; not yet maintained (WR-02). ``progress.yaml`` is the sole
        source of truth for lifecycle state — no command writes this field back,
        so it must not be treated as a live mirror.
    """

    schema_version: int = 0
    unit_id: str
    intent: Intent
    audience: str
    title: str
    sources: list[SourceRef] = Field(default_factory=list)
    sphinx_target: str
    steering_notes: str = ""
    status: ProgressState = ProgressState.pending

    @model_validator(mode="after")
    def _contain_sphinx_target(self) -> "Unit":
        """Reject an absolute or ``..``-bearing ``sphinx_target`` (T-02.1-01).

        ``sphinx_target`` is operator-authored and load-bearing: it becomes a
        write path under ``docs/``. Enforcing containment once at the schema
        boundary — mirroring how :class:`SourceRef` validates its own shape —
        keeps the invariant from depending solely on the write adapter (CR-01).

        Returns
        -------
        Unit
            The validated instance.

        Raises
        ------
        ValueError
            If ``sphinx_target`` is empty, absolute, or contains a ``..`` part.
        """
        target = self.sphinx_target
        if not target:
            raise ValueError("sphinx_target must not be empty")
        if PurePosixPath(target).is_absolute() or PureWindowsPath(target).is_absolute():
            raise ValueError(f"sphinx_target must be relative: {target!r}")
        parts = PurePosixPath(target).parts + PureWindowsPath(target).parts
        if ".." in parts:
            raise ValueError(f"sphinx_target must not contain '..': {target!r}")
        return self


class Steering(BaseModel):
    """The recorded HITL steering event (``provenance.yaml.steering``, D-39).

    Stamped by ``dogen steer`` as a discrete act that provably precedes any
    draft — the strongest AC5 audit signal (HITL-01/02).

    Parameters
    ----------
    author : str
        Captured from git config at steer time (D-41).
    at : str
        ISO-8601 timestamp of the steering act.
    intent : Intent
        The steered Diátaxis direction.
    audience : str
        The steered audience.
    """

    author: str
    at: str
    intent: Intent
    audience: str


class Generation(BaseModel):
    """One draft pass recorded in ``provenance.yaml.generations[]`` (D-36/PLAN-04).

    Parameters
    ----------
    model : str
        The model name used for the pass.
    model_version : str
        The resolved model version.
    effort : Effort
        Reasoning effort requested.
    tooling_version : str
        The ``dogen`` package version that produced the pass.
    sdk : str
        The pinned agent SDK identifier/version.
    context_origins : list of str
        What the agent *actually read* — distinct from human-pointed sources (D-37).
    tools_used : list of str
        Source-qualified tool identifiers exercised in the pass.
    run_id : str
        Correlates the on-disk record to the runtime trace (OBS-03/D-22).
    at : str
        ISO-8601 timestamp of the pass.
    action : str
        The orchestrator action that produced this entry (e.g. ``draft``).
    """

    model: str
    model_version: str
    effort: Effort
    tooling_version: str
    sdk: str
    context_origins: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    run_id: str
    at: str
    action: str


class ReviewerEdit(BaseModel):
    """A post-generation human edit (``reviewer_edits[]``, D-36/PLAN-05).

    Parameters
    ----------
    at : str
        ISO-8601 timestamp of the review.
    reviewer : str
        Captured from git config at review time (D-41).
    summary : str
        The reviewer's note describing the edit.
    """

    at: str
    reviewer: str
    summary: str


class VerificationStep(BaseModel):
    """A reserved-empty verification step (v0; PLAN-07).

    Present-but-empty so a later phase can record actionable-content checks
    without a breaking migration (D-36, RESEARCH Pitfall 5).

    Parameters
    ----------
    id : str
        Stable step identifier.
    state : str
        Verification state; defaults to ``"unverified"``.
    evidence : str or None
        Pointer to captured evidence; reserved ``None`` at v0.
    env_fingerprint : str or None
        Environment fingerprint for the check; reserved ``None`` at v0.
    """

    id: str
    state: str = "unverified"
    evidence: str | None = None
    env_fingerprint: str | None = None


class Verification(BaseModel):
    """The reserved verification block of a unit's provenance (v0; PLAN-07).

    Parameters
    ----------
    steps : list of VerificationStep
        Reserved, empty at v0.
    """

    steps: list[VerificationStep] = Field(default_factory=list)


class Provenance(BaseModel):
    """The unit's consolidated audit record (``provenance.yaml``, D-36).

    Parameters
    ----------
    schema_version : int
        On-disk schema version (D-34); defaults to ``0``.
    unit_id : str
        The unit this record belongs to.
    steering : Steering or None
        The recorded HITL steering event; ``None`` until ``dogen steer`` runs.
    generations : list of Generation
        One entry per draft pass.
    reviewer_edits : list of ReviewerEdit
        Post-generation human edits; reserved-empty at scaffold time.
    verification : Verification
        Reserved verification block (empty at v0).
    """

    schema_version: int = 0
    unit_id: str
    steering: Steering | None = None
    generations: list[Generation] = Field(default_factory=list)
    reviewer_edits: list[ReviewerEdit] = Field(default_factory=list)
    verification: Verification = Field(default_factory=Verification)


class ProgressEntry(BaseModel):
    """One transition in a unit's progress history (D-38).

    Parameters
    ----------
    at : str
        ISO-8601 timestamp of the transition.
    state : ProgressState
        The state entered at this transition.
    """

    at: str
    state: ProgressState


class Progress(BaseModel):
    """The per-unit state machine (``progress.yaml``, D-38/PLAN-06).

    Parameters
    ----------
    schema_version : int
        On-disk schema version (D-34); defaults to ``0``.
    unit_id : str
        The unit this record belongs to.
    state : ProgressState
        Current lifecycle state.
    history : list of ProgressEntry
        Ordered transition log.
    """

    schema_version: int = 0
    unit_id: str
    state: ProgressState
    history: list[ProgressEntry] = Field(default_factory=list)


class DraftResult(BaseModel):
    """A drafting outcome in pure domain terms (no SDK shapes leak in).

    The adapter translates the vendor's response into this type at the seam
    (anti-corruption), so ``core/`` never sees an SDK message object.

    Parameters
    ----------
    text : str
        The drafted MyST Markdown content.
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
        What the provider *actually read* during the pass, as reported by the
        backend — distinct from the unit's human-pointed ``sources`` (D-37).
        Empty when the backend cannot report observed reads (an honest "nothing
        observed"); the orchestrator records this verbatim and never substitutes
        ``unit.sources`` (BL-01).
    tools_used : list of str
        Source-qualified tool identifiers the provider exercised, as reported by
        the backend. Empty when nothing was observed (BL-01).
    effort_used : Effort or None
        The reasoning effort the provider actually ran at (IN-03). When set, the
        orchestrator records it on the generation so the audit entry reflects the
        effort the SDK truly used rather than only the requested value; ``None``
        means the provider did not report one and the requested effort stands.
    """

    text: str
    model: str
    model_version: str = "unknown"
    output_tokens: int
    run_id: str
    context_origins: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    effort_used: Effort | None = None
