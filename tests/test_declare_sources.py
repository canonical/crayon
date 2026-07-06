"""Round-trip: ``--title`` + repeatable ``--source`` thread through declare (D-05).

Proves the six-layer write-path (CLI ``unit new`` -> ``build_declare_request`` ->
``DeclareRequest`` -> ``declare`` -> ``PlanningStore.scaffold_unit`` ->
``_render_unit_md``) persists an operator-supplied ``title`` and an ordered list
of ``--source`` pointers into ``unit.md``, so a Write-free ``dogen-plan`` skill
(Plan 04-03) can record its Socratic intake through the CLI (SKILL-01).

Two paths are exercised: the direct compose+orchestrator path over a real
:class:`FilesystemPlanningStore` under ``tmp_path`` (the domain round-trip), and
one Typer ``CliRunner`` case that proves repeatable ``--source`` accumulates in
declared order. The non-breaking default (no flags -> ``title==""``,
``sources==[]``) is asserted as the control so the additive change stays green
for the existing declare path.
"""

from pathlib import Path

from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose
from dogen.cli.main import app
from dogen.core.models import Intent, SourceRef
from dogen.core.orchestrator import declare

runner = CliRunner()


def _load(root: Path, unit_id: str):
    """Load and validate a unit's ``unit.md`` from disk under ``root``."""
    return FilesystemPlanningStore().load_unit(unit_id, root=root)


def test_declare_threads_title_and_sources_round_trip(tmp_path: Path) -> None:
    """``build_declare_request`` + ``declare`` persist title + ordered sources."""
    store = FilesystemPlanningStore()
    request = compose.build_declare_request(
        "u1",
        root=tmp_path,
        store=store,
        intent=Intent.reference,
        audience="developers",
        title="Widget API",
        sources=["docs/a.md", "docs/b.md"],
    )
    declare(request)

    unit = _load(tmp_path, "u1")
    assert unit.title == "Widget API"
    assert unit.sources == [
        SourceRef(path="docs/a.md"),
        SourceRef(path="docs/b.md"),
    ]
    # --source maps to path (path-xor-ref honored; ref stays unset).
    assert all(s.ref is None for s in unit.sources)


def test_declare_default_path_is_non_breaking(tmp_path: Path) -> None:
    """No ``title``/``sources`` -> empty title and empty sources (control)."""
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
    assert unit.title == ""
    assert unit.sources == []


def test_cli_repeatable_source_accumulates_in_order(
    tmp_path: Path, monkeypatch
) -> None:
    """``unit new --title X --source A --source B`` records both, ordered."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "unit",
            "new",
            "u3",
            "--title",
            "Widget API",
            "--source",
            "docs/a.md",
            "--source",
            "docs/b.md",
        ],
    )
    assert result.exit_code == 0, result.output

    unit = _load(tmp_path, "u3")
    assert unit.title == "Widget API"
    assert unit.sources == [
        SourceRef(path="docs/a.md"),
        SourceRef(path="docs/b.md"),
    ]
