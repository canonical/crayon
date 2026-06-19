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
    provenance = request.store.read_provenance(request.unit_id, root=request.root)
    _require_steering(provenance)
    return await _run_draft(request, unit=unit, provenance=provenance)


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
        draft_path = request.store.write_draft(unit, result.text, root=request.root)
        _record_generation(provenance, request, unit=unit, result=result, run_id=run_id)
        request.store.write_provenance(provenance, root=request.root)
        _advance_progress(request)
    return draft_path


def _record_generation(
    provenance: Provenance,
    request: DraftRequest,
    *,
    unit: Unit,
    result: DraftResult,
    run_id: str,
) -> None:
    """Append a ``generations[]`` entry correlated to the run (D-36/OBS-03).

    Parameters
    ----------
    provenance : Provenance
        The provenance record to append to.
    request : DraftRequest
        The bundled run parameters (effort and timestamp source).
    unit : Unit
        The drafted unit (its human-pointed sources become context origins).
    result : DraftResult
        The provider's draft outcome.
    run_id : str
        The active span's 32-hex run id (stamped for correlation).
    """
    provenance.generations.append(
        Generation(
            model=result.model,
            model_version=result.model,
            effort=request.effort,
            tooling_version=__version__,
            sdk=_SDK_IDENTIFIER,
            context_origins=[s.path or s.ref or "" for s in unit.sources],
            tools_used=[],
            run_id=run_id,
            at=request.now(),
            action=_DRAFT_ACTION,
        )
    )


def _advance_progress(request: DraftRequest) -> None:
    """Auto-advance progress ``pending → sourced → drafted`` (never committed).

    Parameters
    ----------
    request : DraftRequest
        The bundled collaborators and parameters.
    """
    progress = request.store.read_progress(request.unit_id, root=request.root)
    for state in _AUTO_ADVANCE:
        if progress.state is not state:
            progress.state = state
            progress.history.append(ProgressEntry(at=request.now(), state=state))
    request.store.write_progress(progress, root=request.root)
