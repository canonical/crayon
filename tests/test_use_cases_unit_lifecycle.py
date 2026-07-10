"""Domain + adapter tests for the unit-lifecycle use-cases (ls / rm / mv).

Mirrors tests/test_use_cases_declare_steer_review.py: a real
:class:`FilesystemPlanningStore` over ``tmp_path`` exercising the list/remove/
rename use-cases and their path-safety as core+adapter invariants rather than
CLI ceremony. Signoff/progress are seeded directly through the store so the
lifecycle-verb behaviour is tested without a git-identity round-trip.
"""

from pathlib import Path

import pytest

from dogen.adapters.planning_fs import (
    FilesystemPlanningStore,
    UnitExistsError,
    UnitNotFoundError,
)
from dogen.core.models import (
    Effort,
    FileDigest,
    Generation,
    Intent,
    Progress,
    ProgressEntry,
    ProgressState,
    Provenance,
    Signoff,
)
from dogen.core.orchestrator import (
    ListRequest,
    RemoveRequest,
    RenameRequest,
    list_units,
    remove,
    rename,
)


def _scaffold(
    store: FilesystemPlanningStore,
    root: Path,
    unit_id: str,
    *,
    intent: Intent = Intent.reference,
    audience: str = "devs",
) -> None:
    """Scaffold a unit with a deterministic title under ``root``."""
    store.scaffold_unit(
        unit_id,
        root=root,
        intent=intent,
        audience=audience,
        title=f"Title {unit_id}",
    )


def _seed_drafted(store: FilesystemPlanningStore, root: Path, unit_id: str) -> None:
    """Seed a steered + drafted unit (provenance with one generation).

    PROV-04: the drafted lifecycle state is derived from the provenance record
    (a landed generation), not from a stored ``progress.yaml``.
    """
    store.write_provenance(
        Provenance(
            unit_id=unit_id,
            signoff=Signoff(
                author="Ada Lovelace",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            generations=[
                Generation(
                    model="m",
                    model_version="v",
                    effort=Effort.medium,
                    tooling_version="0.0.0",
                    sdk="",
                    files=[FileDigest(path=f"docs/{unit_id}.md", sha256="ab12")],
                    run_id="r",
                    at="2026-01-01T00:00:01Z",
                    action="draft",
                )
            ],
        ),
        root=root,
    )


# --------------------------------------------------------------------------- #
# list_units (unit ls)
# --------------------------------------------------------------------------- #


def test_list_units_empty_returns_empty(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    assert list_units(ListRequest(root=tmp_path, store=store)) == []


def test_list_units_enumerates_with_progress(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    _scaffold(store, tmp_path, "a")
    _scaffold(store, tmp_path, "b")
    _seed_drafted(store, tmp_path, "b")

    summaries = list_units(ListRequest(root=tmp_path, store=store))
    assert [s.unit_id for s in summaries] == ["a", "b"]
    by_id = {s.unit_id: s for s in summaries}
    # ``a`` has no progress.yaml — it defaults to pending; ``b`` was seeded drafted.
    assert by_id["a"].state is ProgressState.pending
    assert by_id["b"].state is ProgressState.drafted
    assert by_id["a"].title == "Title a"
    assert by_id["a"].intent is Intent.reference


# --------------------------------------------------------------------------- #
# remove (unit rm)
# --------------------------------------------------------------------------- #


def test_remove_deletes_unit_dir_and_docs(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    _scaffold(store, tmp_path, "u")
    _seed_drafted(store, tmp_path, "u")
    store.write_draft(store.load_unit("u", root=tmp_path), "# u\n", root=tmp_path)
    assert (tmp_path / "docs" / "u.md").exists()

    remove(RemoveRequest(unit_id="u", root=tmp_path, store=store))
    assert not (tmp_path / ".dogen" / "units" / "u").exists()
    assert not (tmp_path / "docs" / "u.md").exists()


def test_remove_missing_unit_raises_not_found(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    with pytest.raises(UnitNotFoundError):
        remove(RemoveRequest(unit_id="ghost", root=tmp_path, store=store))


def test_remove_best_effort_on_unreadable_unit_md(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    _scaffold(store, tmp_path, "u")
    # Corrupt the unit by removing its unit.md; the directory survives.
    (tmp_path / ".dogen" / "units" / "u" / "unit.md").unlink()

    remove(RemoveRequest(unit_id="u", root=tmp_path, store=store))
    assert not (tmp_path / ".dogen" / "units" / "u").exists()


def test_delete_unit_rejects_traversing_sphinx_target(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    _scaffold(store, tmp_path, "u")
    evil = tmp_path.parent / "evil.md"
    evil.write_text("do not delete me\n", encoding="utf-8")

    with pytest.raises(ValueError):
        store.delete_unit("u", root=tmp_path, sphinx_target="../../evil.md")
    # The traversing target must never be touched (path-safety before unlink).
    assert evil.exists()


# --------------------------------------------------------------------------- #
# rename (unit mv)
# --------------------------------------------------------------------------- #


def _seed_full(store: FilesystemPlanningStore, root: Path, unit_id: str) -> None:
    """Seed a steered + drafted unit with a generation and drafted docs page."""
    store.write_provenance(
        Provenance(
            unit_id=unit_id,
            signoff=Signoff(
                author="Ada Lovelace",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            generations=[
                Generation(
                    model="m",
                    model_version="v",
                    effort=Effort.medium,
                    tooling_version="0.0.0",
                    sdk="",
                    files=[FileDigest(path="docs/u.md", sha256="ab12")],
                    run_id="r",
                    at="2026-01-01T00:00:01Z",
                    action="draft",
                )
            ],
        ),
        root=root,
    )
    store.write_progress(
        Progress(
            unit_id=unit_id,
            state=ProgressState.drafted,
            history=[
                ProgressEntry(at="2026-01-01T00:00:02Z", state=ProgressState.drafted)
            ],
        ),
        root=root,
    )
    store.write_draft(
        store.load_unit(unit_id, root=root), f"# {unit_id} body\n", root=root
    )


def test_rename_moves_dir_and_rewrites_all_refs(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    _scaffold(store, tmp_path, "old", audience="ops")
    _seed_full(store, tmp_path, "old")
    original = (tmp_path / "docs" / "old.md").read_text(encoding="utf-8")

    rename(RenameRequest(old_id="old", new_id="new", root=tmp_path, store=store))

    assert not (tmp_path / ".dogen" / "units" / "old").exists()
    assert (tmp_path / ".dogen" / "units" / "new").exists()
    unit = store.load_unit("new", root=tmp_path)
    assert unit.unit_id == "new"
    assert unit.sphinx_target == "new.md"
    prov = store.read_provenance("new", root=tmp_path)
    assert prov.unit_id == "new"
    assert prov.signoff is not None
    assert prov.signoff.author == "Ada Lovelace"
    assert len(prov.generations) == 1
    prog = store.read_progress("new", root=tmp_path)
    assert prog.unit_id == "new"
    assert prog.state is ProgressState.drafted
    assert any(e.state is ProgressState.drafted for e in prog.history)
    assert not (tmp_path / "docs" / "old.md").exists()
    assert (tmp_path / "docs" / "new.md").read_text(encoding="utf-8") == original


def test_rename_preserves_unrelated_unit_md_fields(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    _scaffold(store, tmp_path, "old", audience="platform team")
    rename(RenameRequest(old_id="old", new_id="new", root=tmp_path, store=store))
    unit = store.load_unit("new", root=tmp_path)
    assert unit.audience == "platform team"
    assert unit.title == "Title old"


def test_rename_target_exists_raises_unit_exists(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    _scaffold(store, tmp_path, "old")
    _scaffold(store, tmp_path, "taken")
    with pytest.raises(UnitExistsError):
        rename(RenameRequest(old_id="old", new_id="taken", root=tmp_path, store=store))
    # The source unit is left untouched (still loadable) on a target clash.
    assert store.load_unit("old", root=tmp_path).unit_id == "old"


def test_rename_source_missing_raises_not_found(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    with pytest.raises(UnitNotFoundError):
        rename(RenameRequest(old_id="ghost", new_id="new", root=tmp_path, store=store))


def test_rename_unsafe_ids_raise_value_error(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    _scaffold(store, tmp_path, "old")
    with pytest.raises(ValueError):
        rename(
            RenameRequest(old_id="old", new_id="../escape", root=tmp_path, store=store)
        )
    with pytest.raises(ValueError):
        rename(
            RenameRequest(old_id="../escape", new_id="new", root=tmp_path, store=store)
        )
    # An unsafe id moves nothing — the original unit is intact.
    assert store.load_unit("old", root=tmp_path).unit_id == "old"
