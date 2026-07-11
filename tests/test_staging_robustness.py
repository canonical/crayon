"""Phase 9 staging + input robustness beats (STAGE-05, PROV-05).

Behavioral coverage for the two round-3 friction fixes that both land in the
``review`` verb — staging cleanup on a sealing accept (PROV-05) and
``--note-file -`` stdin parity (STAGE-05) — plus the guarded, idempotent
``remove_staging`` seam they depend on. Self-contained: it re-declares the small
git-repo fixture rather than importing test helpers across modules (this module
is shared by the later Phase-9 plans).
"""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.cli.main import app

runner = CliRunner()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tmp git repo with identity, an initial commit, cwd set, env cleared."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Ada Lovelace"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "ada@example.com"],
        check=True,
    )
    (tmp_path / "README.md").write_text("# target repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOGEN_PROVIDER", raising=False)
    return tmp_path


def _combined(result) -> str:
    """Return stdout + stderr regardless of the CliRunner capture mode."""
    text = result.output or ""
    try:
        text += result.stderr or ""
    except (ValueError, AttributeError):
        pass
    return text


def _seal_a_unit(repo: Path) -> None:
    """Drive unit ``u`` through declare -> signoff -> draft (caller reviews)."""
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "devs"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.output)


def _make_staging(repo: Path, unit_id: str = "u") -> Path:
    """Create ``.dogen/staging/<id>/handoff/page.md`` scratch and return its dir."""
    staging = repo / ".dogen" / "staging" / unit_id
    (staging / "handoff").mkdir(parents=True, exist_ok=True)
    (staging / "handoff" / "page.md").write_text("scratch\n", encoding="utf-8")
    return staging


# --- Task 1: remove_staging port + FS adapter (guarded idempotent rmtree) -----


def test_remove_staging_deletes_existing_dir_and_returns_true(repo):
    store = FilesystemPlanningStore()
    staging = _make_staging(repo)
    assert staging.is_dir()
    assert store.remove_staging("u", root=repo) is True
    assert not staging.exists()


def test_remove_staging_absent_dir_is_idempotent_false(repo):
    store = FilesystemPlanningStore()
    assert not (repo / ".dogen" / "staging" / "u").exists()
    assert store.remove_staging("u", root=repo) is False


@pytest.mark.parametrize("bad_id", ["../evil", "a/b", ".", "..", ""])
def test_remove_staging_refuses_traversing_id_with_no_side_effect(repo, bad_id):
    store = FilesystemPlanningStore()
    # A sibling dir a naive traversal could reach — it must survive untouched.
    sentinel = repo.parent / "sentinel"
    sentinel.mkdir(exist_ok=True)
    (sentinel / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        store.remove_staging(bad_id, root=repo)
    assert (sentinel / "keep.txt").exists()


def test_remove_staging_refuses_symlink_escaping_root(repo):
    store = FilesystemPlanningStore()
    outside = repo.parent / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "keep.txt").write_text("x", encoding="utf-8")
    staging_parent = repo / ".dogen" / "staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    (staging_parent / "u").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        store.remove_staging("u", root=repo)
    # The resolved-path containment guard refuses before any deletion.
    assert (outside / "keep.txt").exists()
