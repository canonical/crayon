"""Round-trip: ``--notes`` threads a steering note through declare (SKILL-01).

Proves the six-layer write-path (CLI ``unit new`` -> ``build_declare_request`` ->
``DeclareRequest`` -> ``declare`` -> ``PlanningStore.scaffold_unit`` ->
``_render_unit_md``) persists an operator-supplied ``steering_notes`` string into
``unit.md``, so a Write-free ``dogen-plan`` skill can record the substance of its
Socratic intake through the CLI instead of a manual hand-edit of ``unit.md``.

Two paths are exercised: the direct compose+orchestrator path over a real
:class:`FilesystemPlanningStore` under ``tmp_path`` (the domain round-trip), and
one Typer ``CliRunner`` case that proves the ``--notes`` flag persists. The
non-breaking default (no ``--notes`` -> ``steering_notes == ""``) is asserted as
the control so the additive change stays green for the existing declare path.
"""

from pathlib import Path

from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose
from dogen.cli.main import app
from dogen.core.models import Intent
from dogen.core.orchestrator import declare

runner = CliRunner()


def _load(root: Path, unit_id: str):
    """Load and validate a unit's ``unit.md`` from disk under ``root``."""
    return FilesystemPlanningStore().load_unit(unit_id, root=root)


def test_declare_threads_notes_round_trip(tmp_path: Path) -> None:
    """``build_declare_request`` + ``declare`` persist the steering note."""
    store = FilesystemPlanningStore()
    request = compose.build_declare_request(
        "u1",
        root=tmp_path,
        store=store,
        intent=Intent.reference,
        audience="developers",
        title="Widget API",
        steering_notes=(
            "Reader wants to know exactly which config fields exist and their defaults."
        ),
    )
    declare(request)

    unit = _load(tmp_path, "u1")
    assert unit.steering_notes == (
        "Reader wants to know exactly which config fields exist and their defaults."
    )


def test_declare_default_path_omits_notes(tmp_path: Path) -> None:
    """No ``steering_notes`` -> empty steering note (control)."""
    store = FilesystemPlanningStore()
    request = compose.build_declare_request(
        "u2",
        root=tmp_path,
        store=store,
        intent=Intent.reference,
        audience="developers",
    )
    declare(request)

    unit = _load(tmp_path, "u2")
    assert unit.steering_notes == ""


def test_cli_notes_flag_persists_steering_notes(tmp_path: Path, monkeypatch) -> None:
    """``unit new --notes TEXT`` persists TEXT into ``steering_notes``."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["unit", "new", "u3", "--notes", "Reader needs the field reference."],
    )
    assert result.exit_code == 0, result.output

    unit = _load(tmp_path, "u3")
    assert unit.steering_notes == "Reader needs the field reference."
