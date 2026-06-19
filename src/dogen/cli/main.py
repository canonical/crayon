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
a clean nonzero exit (D-42; CLI-stays-thin). ``unit new`` is the first of the
four planned subcommands; ``steer``/``draft``/``review`` land in plan 02.
"""

from pathlib import Path
from typing import Annotated

import typer

from dogen.adapters.planning_fs import FilesystemPlanningStore, UnitExistsError
from dogen.core.models import Intent

app = typer.Typer(help="Draft review-ready documentation, human in the loop.")
unit_app = typer.Typer(help="Create and manage documentation units.")
app.add_typer(unit_app, name="unit")


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


if __name__ == "__main__":
    app()
