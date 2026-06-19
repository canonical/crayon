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

"""The thin Typer CLI for dogen (composition + delegation only).

This holds no business logic: each command validates its inputs minimally,
delegates into the core/adapters, prints the result, and maps domain errors to
a clean nonzero exit (D-42; CLI-stays-thin). The four subcommands are
``unit new`` (scaffold), ``steer`` (record the HITL event), ``draft`` (run the
orchestrator behind a single ``asyncio.run`` boundary), and ``review`` (append a
reviewer edit, advance to ``reviewed`` — never ``committed``). The composition
root configures the local observability backend once (D-21) and selects the
provider by name (D-25); ``core/`` never sees Logfire or the SDK.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from dogen.adapters.git_identity import GitIdentityError, read_git_identity
from dogen.adapters.mock_provider import select_provider
from dogen.adapters.planning_fs import FilesystemPlanningStore, UnitExistsError
from dogen.core.models import (
    Intent,
    ProgressEntry,
    ProgressState,
    Provenance,
    ReviewerEdit,
    Steering,
)
from dogen.core.orchestrator import DraftRequest, SteeringRequiredError
from dogen.core.orchestrator import draft as draft_use_case
from dogen.obs.logfire_backend import configure_observability

app = typer.Typer(help="Draft review-ready documentation, human in the loop.")
unit_app = typer.Typer(help="Create and manage documentation units.")
app.add_typer(unit_app, name="unit")


def _utc_now() -> str:
    """Return the current time as an ISO-8601 UTC timestamp.

    Returns
    -------
    str
        The current UTC time in ISO-8601 form (the real composition-root clock).
    """
    return datetime.now(UTC).isoformat()


@unit_app.command("new")
def unit_new(
    unit_id: Annotated[str, typer.Argument(help="Identifier for the new unit.")],
    intent: Annotated[
        Intent | None,
        typer.Option(help="Pre-fill the Diátaxis direction."),
    ] = None,
    audience: Annotated[
        str | None,
        typer.Option(help="Pre-fill the target audience."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(help="Overwrite an existing unit.md."),
    ] = False,
) -> None:
    """Scaffold an editable ``unit.md`` for a new documentation unit.

    Parameters
    ----------
    unit_id : str
        Identifier and per-unit directory name for the new unit.
    intent : Intent or None
        Optional pre-filled Diátaxis direction.
    audience : str or None
        Optional pre-filled audience.
    force : bool
        Overwrite an existing ``unit.md`` when set.
    """
    store = FilesystemPlanningStore()
    try:
        written = store.scaffold_unit(
            unit_id,
            root=Path.cwd(),
            intent=intent,
            audience=audience,
            force=force,
        )
    except UnitExistsError as exc:
        typer.echo(f"Refusing to overwrite: {exc}. Pass --force to replace.", err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo(f"Invalid unit id: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"Created {written}")


@app.command("steer")
def steer(
    unit_id: Annotated[str, typer.Argument(help="Unit to record steering for.")],
) -> None:
    """Record the HITL steering event for a unit (D-39).

    Captures ``{author, at}`` from git identity plus the unit's steered
    ``intent``/``audience`` into ``provenance.yaml.steering`` — a discrete act
    that provably precedes any draft (HITL-01/02).

    Parameters
    ----------
    unit_id : str
        The unit to record steering for.
    """
    store = FilesystemPlanningStore()
    root = Path.cwd()
    try:
        unit = store.load_unit(unit_id, root=root)
        author, _email = read_git_identity()
    except GitIdentityError as exc:
        typer.echo(f"Cannot record steering: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Cannot read unit {unit_id!r}: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    provenance = _load_or_init_provenance(store, unit_id, root=root)
    provenance.steering = Steering(
        author=author, at=_utc_now(), intent=unit.intent, audience=unit.audience
    )
    written = store.write_provenance(provenance, root=root)
    typer.echo(f"Recorded steering for {unit_id} -> {written}")


@app.command("draft")
def draft(
    unit_id: Annotated[str, typer.Argument(help="Unit to draft.")],
    provider: Annotated[
        str,
        typer.Option(help="Drafting provider: copilot or mock."),
    ] = "copilot",
) -> None:
    """Run the drafting loop for a unit (D-25/D-40).

    Refuses with a clear message and nonzero exit when no steering has been
    recorded (HITL-01); otherwise writes the draft + provenance + progress and
    prints the written paths.

    Parameters
    ----------
    unit_id : str
        The unit to draft.
    provider : str
        The provider to use (``copilot`` default; tests/CI use ``mock``).
    """
    configure_observability()
    store = FilesystemPlanningStore()
    request = DraftRequest(
        unit_id=unit_id,
        root=Path.cwd(),
        provider=select_provider(provider),
        store=store,
        provider_name=provider,
        now=_utc_now,
    )
    try:
        draft_path = asyncio.run(draft_use_case(request))
    except SteeringRequiredError as exc:
        typer.echo(f"Refusing to draft: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Cannot draft {unit_id!r}: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"Drafted {unit_id} -> {draft_path}")


@app.command("review")
def review(
    unit_id: Annotated[str, typer.Argument(help="Unit to review.")],
    note: Annotated[str, typer.Option(help="Summary of the reviewer's edit.")],
) -> None:
    """Append a reviewer edit and advance progress to ``reviewed`` (PLAN-05/06).

    Never advances to ``committed`` — that border belongs to the human (D-38).

    Parameters
    ----------
    unit_id : str
        The unit to review.
    note : str
        A summary of the reviewer's edit.
    """
    store = FilesystemPlanningStore()
    root = Path.cwd()
    try:
        reviewer, _email = read_git_identity()
        provenance = store.read_provenance(unit_id, root=root)
        progress = store.read_progress(unit_id, root=root)
    except GitIdentityError as exc:
        typer.echo(f"Cannot record review: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Cannot read unit {unit_id!r}: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    provenance.reviewer_edits.append(
        ReviewerEdit(at=_utc_now(), reviewer=reviewer, summary=note)
    )
    store.write_provenance(provenance, root=root)
    progress.state = ProgressState.reviewed
    progress.history.append(ProgressEntry(at=_utc_now(), state=ProgressState.reviewed))
    store.write_progress(progress, root=root)
    typer.echo(f"Reviewed {unit_id}: progress -> {ProgressState.reviewed.value}")


def _load_or_init_provenance(
    store: FilesystemPlanningStore, unit_id: str, *, root: Path
) -> Provenance:
    """Read a unit's provenance, initializing an empty record if absent.

    Parameters
    ----------
    store : FilesystemPlanningStore
        The planning-directory store.
    unit_id : str
        The unit whose provenance is loaded.
    root : Path
        The repo root.

    Returns
    -------
    Provenance
        The existing or a freshly initialized provenance record.
    """
    try:
        return store.read_provenance(unit_id, root=root)
    except FileNotFoundError:
        return Provenance(unit_id=unit_id)


if __name__ == "__main__":
    app()
