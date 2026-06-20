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

"""The one drafting use-case: the inseparable A2 walking-skeleton loop.

This is pure domain orchestration. It enforces the **provable-HITL gate** as a
domain invariant (not CLI ceremony): if no ``steer`` event was recorded, it
raises :class:`SteeringRequiredError` and produces no side effects (D-40 /
HITL-01). When steering is present it opens the ``dogen.draft`` OTel span, mints
the ``run_id`` from the trace id, drives the injected :class:`DraftingProvider`,
writes the draft + a ``generations[]`` entry (whose ``run_id`` correlates to the
span — OBS-03/D-22) via the :class:`PlanningStore`, and auto-advances progress
``pending → sourced → drafted``. It **never** writes ``ProgressState.committed``
— that border belongs to the human (SKEL-03 / Pitfall 9 / D-38).

Everything host-facing is injected (provider, store, ``now``) so the use-case
depends only on abstractions (coding-guide §6) and tests stay deterministic.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dogen import __version__
from dogen.core import observability
from dogen.core.models import (
    DraftResult,
    Effort,
    Generation,
    Progress,
    ProgressEntry,
    ProgressState,
    Provenance,
    Unit,
)
from dogen.core.ports import DraftingProvider, PlanningStore

# The pinned agent SDK identifier recorded on every generation (D-36). The mock
# path does not call it, but the field is part of the audit shape.
_SDK_IDENTIFIER = "github-copilot-sdk==1.0.2"
_DRAFT_ACTION = "draft"

# The auto-advance ladder the loop walks; ``committed`` is deliberately absent.
_AUTO_ADVANCE: tuple[ProgressState, ...] = (
    ProgressState.sourced,
    ProgressState.drafted,
)

# The forward lifecycle ordering (D-38) used to keep auto-advance monotonic
# (WR-04): a state is only stamped when it is strictly later than the current
# one. ``reviewed`` is included so a re-draft of an already-reviewed unit is
# ranked correctly instead of falling through an "unknown state" path and
# walking the lifecycle backward (the WR-04 follow-up). The terminal
# ``committed`` state is deliberately NOT named here — the drafting use-case
# never references it (SKEL-03); a state beyond this ladder is handled
# positionally in :func:`_advance_progress`.
_PROGRESS_ORDER: tuple[ProgressState, ...] = (
    ProgressState.pending,
    ProgressState.sourced,
    ProgressState.drafted,
    ProgressState.reviewed,
)

Clock = Callable[[], str]


class SteeringRequiredError(RuntimeError):
    """Raised when drafting is attempted before a steering event is recorded.

    The HITL gate is consequential, not ceremonial (HITL-01 / Pitfall 3): the
    CLI surfaces this as a clear message and a nonzero exit, and no draft,
    provenance entry, or progress change is produced.
    """


@dataclass(frozen=True)
class DraftRequest:
    """The injected collaborators and parameters for one drafting run.

    Bundling the dependencies keeps the use-case depending only on abstractions
    (coding-guide §6) and keeps each function's argument list small.

    Parameters
    ----------
    unit_id : str
        The unit to draft.
    root : Path
        The repo root the store reads/writes beneath.
    provider : DraftingProvider
        The injected drafting provider (mock in CI/tests, Copilot in prod).
    store : PlanningStore
        The injected planning-directory store.
    provider_name : str
        The selected provider's name, recorded as a span attribute.
    now : Clock
        Injected timestamp source (ISO-8601) for deterministic tests.
    effort : Effort
        The reasoning effort recorded on the generation entry.
    """

    unit_id: str
    root: Path
    provider: DraftingProvider
    store: PlanningStore
    provider_name: str
    now: Clock
    effort: Effort = Effort.medium


async def draft(request: DraftRequest) -> Path:
    """Run the drafting use-case for one unit and return the draft path.

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters for the run.

    Returns
    -------
    pathlib.Path
        The path of the written draft under ``docs/``.

    Raises
    ------
    SteeringRequiredError
        If the unit has no recorded steering event (HITL-01 / D-40).
    """
    unit = request.store.load_unit(request.unit_id, root=request.root)
    provenance = _read_steered_provenance(request)
    return await _run_draft(request, unit=unit, provenance=provenance)


def _read_steered_provenance(request: DraftRequest) -> Provenance:
    """Read provenance and enforce the HITL gate (D-40/HITL-01).

    A wholly missing ``provenance.yaml`` means no ``steer`` ever ran, which is
    the same refusal as a present-but-unsteered record — both raise
    :class:`SteeringRequiredError`, never a generic file error.

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters.

    Returns
    -------
    Provenance
        The unit's provenance record, guaranteed to carry a steering event.

    Raises
    ------
    SteeringRequiredError
        If provenance is absent or carries no steering event.
    """
    try:
        provenance = request.store.read_provenance(request.unit_id, root=request.root)
    except FileNotFoundError as exc:
        raise SteeringRequiredError(
            "no recorded steering for this unit; run `dogen steer` before drafting"
        ) from exc
    _require_steering(provenance)
    return provenance


def _require_steering(provenance: Provenance) -> None:
    """Enforce the provable-HITL gate as a domain invariant (D-40).

    Parameters
    ----------
    provenance : Provenance
        The unit's current provenance record.

    Raises
    ------
    SteeringRequiredError
        If no steering event has been recorded.
    """
    if provenance.steering is None:
        raise SteeringRequiredError(
            "no recorded steering for this unit; run `dogen steer` before drafting"
        )


async def _run_draft(
    request: DraftRequest,
    *,
    unit: Unit,
    provenance: Provenance,
) -> Path:
    """Drive the provider, persist the draft, and advance state under a span.

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters.
    unit : Unit
        The loaded unit being drafted.
    provenance : Provenance
        The unit's provenance record (steering already verified present).

    Returns
    -------
    pathlib.Path
        The path of the written draft.
    """
    assert provenance.steering is not None  # guaranteed by _require_steering
    steering = provenance.steering
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
            audience=steering.audience,
            steering=steering,
            sources=unit.sources,
        )
        # WR-03: make the audit record durable BEFORE the draft is observable.
        # Provenance (the generations[] row) and progress are written first; the
        # draft .md is written last. A crash between these steps can then only
        # leave an audit row with no draft (re-runnable, harmless) — never a
        # drafted output with no recorded generation, the exact AC5 gap that an
        # output-first order would open. The store writes each YAML atomically
        # (temp-then-rename) so a partial step never leaves a torn file.
        _record_generation(provenance, request, result=result, run_id=run_id)
        request.store.write_provenance(provenance, root=request.root)
        _advance_progress(request)
        draft_path = request.store.write_draft(unit, result.text, root=request.root)
    return draft_path


def _record_generation(
    provenance: Provenance,
    request: DraftRequest,
    *,
    result: DraftResult,
    run_id: str,
) -> None:
    """Append a ``generations[]`` entry correlated to the run (D-36/OBS-03).

    The unit's human-pointed ``sources`` are deliberately *not* an input here:
    copying them into ``context_origins`` is the D-37 collapse this fix removes
    (BL-01). ``context_origins``/``tools_used`` come only from ``result``.

    Parameters
    ----------
    provenance : Provenance
        The provenance record to append to.
    request : DraftRequest
        The bundled run parameters (effort and timestamp source).
    result : DraftResult
        The provider's draft outcome, the sole source of truth for what the
        agent actually read and which tools it ran (BL-01).
    run_id : str
        The active span's 32-hex run id (stamped for correlation).
    """
    # D-37/BL-01: ``context_origins``/``tools_used`` record what the agent
    # *actually* read/ran, as reported by the provider — never the unit's
    # human-pointed ``sources``. Until a provider can observe and report these,
    # the result carries empty lists (an honest "nothing observed"), so the
    # audit record never fabricates read context or tool activity.
    provenance.generations.append(
        Generation(
            model=result.model,
            model_version=result.model_version,
            effort=request.effort,
            tooling_version=__version__,
            sdk=_SDK_IDENTIFIER,
            context_origins=list(result.context_origins),
            tools_used=list(result.tools_used),
            run_id=run_id,
            at=request.now(),
            action=_DRAFT_ACTION,
        )
    )


def _advance_progress(request: DraftRequest) -> None:
    """Land the unit at ``ProgressState.drafted`` after a draft (never committed).

    A draft always leaves the unit at ``drafted``, recorded as forward-only,
    idempotent history (WR-04 and its follow-up):

    - Already ``drafted``: a no-op — no transition, no spurious history entry.
    - Earlier (``pending``/``sourced``): walk the forward ladder, stamping each
      newly-reached state up to ``drafted``.
    - Later (``reviewed``, or any hand-set terminal state beyond the ladder): a
      re-draft deliberately supersedes the now-stale review and resets the unit
      to ``drafted`` in a single clean transition — never a backward walk
      through ``sourced`` (D-38; the regression the first WR-04 fix left for
      re-draft of a reviewed unit).

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters.
    """
    progress = _read_or_init_progress(request)
    if progress.state is ProgressState.drafted:
        return
    drafted_rank = _PROGRESS_ORDER.index(ProgressState.drafted)
    # A state outside the ladder (only the terminal post-review state can be) is
    # ranked just past its end, so a re-draft resets it cleanly to ``drafted``.
    current = (
        _PROGRESS_ORDER.index(progress.state)
        if progress.state in _PROGRESS_ORDER
        else len(_PROGRESS_ORDER)
    )
    if current > drafted_rank:
        # Re-draft of a reviewed (or later) unit: one clean reset to ``drafted``.
        progress.state = ProgressState.drafted
        progress.history.append(
            ProgressEntry(at=request.now(), state=ProgressState.drafted)
        )
    else:
        for state in _AUTO_ADVANCE:
            if _PROGRESS_ORDER.index(state) > current:
                progress.state = state
                progress.history.append(ProgressEntry(at=request.now(), state=state))
    request.store.write_progress(progress, root=request.root)


def _read_or_init_progress(request: DraftRequest) -> Progress:
    """Read the unit's progress, initializing a ``pending`` record if absent.

    A unit scaffolded with ``unit new`` has no ``progress.yaml`` until its first
    draft; the lifecycle starts at ``pending`` (D-38).

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
