"""The ``dogen skills`` subcommand — the install flow's CLI surface (Q7).

Thin per D-11: each verb delegates to :mod:`dogen.adapters.skills_install` and
renders the result. ``install`` stages the canonical family into a harness's
discovery root (with minimal auto-discovery when ``--harness`` is omitted),
``status`` reports per-install drift against the canonical family, and
``update`` re-stages every recorded install. The manifest lives at
``.dogen/skills-install.yaml``.
"""

import json
from pathlib import Path
from typing import Annotated

import typer

from dogen.adapters.skills_install import (
    HARNESS_ROOTS,
    SkillsInstallError,
    discover_harnesses,
    install,
    status,
    update,
)
from dogen.app.compose import utc_now

skills_app = typer.Typer(help="Install the skill family into agent harnesses.")

_JsonOutput = Annotated[
    bool,
    typer.Option("--json", help="Emit a structured JSON result."),
]
_FromPath = Annotated[
    Path | None,
    typer.Option(
        "--from",
        help="Canonical skills/ directory (defaults to the dogen checkout's).",
    ),
]


@skills_app.command("install")
def skills_install(
    harness: Annotated[
        list[str] | None,
        typer.Option(
            "--harness",
            help="Target harness (repeatable): claude|copilot|opencode. "
            "Omit to auto-detect from the repo's directories.",
        ),
    ] = None,
    from_path: _FromPath = None,
    json_output: _JsonOutput = False,
) -> None:
    """Stage the canonical skill family into harness discovery roots.

    Copies are byte-identical (recorded with content hashes in
    ``.dogen/skills-install.yaml``); per-harness tailoring is applied when a
    harness needs it. With no ``--harness``, the repo's directories are
    scanned (``.claude/`` / ``.github/`` / ``.opencode/``) and every detected
    harness is installed.

    Parameters
    ----------
    harness : list of str or None
        The harness(es) to stage for; ``None`` auto-detects.
    from_path : Path or None
        An explicit canonical ``skills/`` directory (``--from``).
    json_output : bool
        Emit the structured JSON array instead of plain lines.
    """
    root = Path.cwd()
    targets = harness or discover_harnesses(root)
    if not targets:
        known = ", ".join(sorted(HARNESS_ROOTS))
        typer.echo(
            f"No harness detected in this repo. Pass --harness ({known}) explicitly.",
            err=True,
        )
        raise typer.Exit(code=2)
    records = []
    for target in targets:
        try:
            records.append(install(root, target, source=from_path, at=utc_now()))
        except SkillsInstallError as exc:
            typer.echo(f"Cannot install for {target!r}: {exc}", err=True)
            raise typer.Exit(code=2) from exc
    if json_output:
        typer.echo(json.dumps(records))
        return
    for record in records:
        typer.echo(f"Installed {record['harness']} -> {record['path']}")


@skills_app.command("status")
def skills_status(
    from_path: _FromPath = None,
    json_output: _JsonOutput = False,
) -> None:
    """Report each recorded install's drift state against the canonical family.

    Parameters
    ----------
    from_path : Path or None
        An explicit canonical ``skills/`` directory (``--from``).
    json_output : bool
        Emit the structured JSON array instead of plain lines.
    """
    root = Path.cwd()
    try:
        rows = status(root, source=from_path)
    except SkillsInstallError as exc:
        typer.echo(f"Cannot check skills status: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if json_output:
        typer.echo(json.dumps(rows))
        return
    if not rows:
        typer.echo("No skills installed. Run `dogen skills install`.")
        return
    for row in rows:
        typer.echo(f"{row['harness']:10s} {row['state']:8s} {row['path']}")


@skills_app.command("update")
def skills_update(
    from_path: _FromPath = None,
    json_output: _JsonOutput = False,
) -> None:
    """Re-stage every recorded install from the canonical family.

    Parameters
    ----------
    from_path : Path or None
        An explicit canonical ``skills/`` directory (``--from``).
    json_output : bool
        Emit the structured JSON array instead of plain lines.
    """
    root = Path.cwd()
    try:
        records = update(root, source=from_path, at=utc_now())
    except SkillsInstallError as exc:
        typer.echo(f"Cannot update skills: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    if json_output:
        typer.echo(json.dumps(records))
        return
    if not records:
        typer.echo("No skills installed. Run `dogen skills install`.")
        return
    for record in records:
        typer.echo(f"Refreshed {record['harness']} -> {record['path']}")
