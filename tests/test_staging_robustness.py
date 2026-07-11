"""Phase 9 staging + input robustness beats (STAGE-05, PROV-05).

Behavioral coverage for the two round-3 friction fixes that both land in the
``review`` verb — staging cleanup on a sealing accept (PROV-05) and
``--note-file -`` stdin parity (STAGE-05) — plus the guarded, idempotent
``remove_staging`` seam they depend on. Self-contained: it re-declares the small
git-repo fixture rather than importing test helpers across modules (this module
is shared by the later Phase-9 plans).
"""

import contextlib
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose
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
    with contextlib.suppress(ValueError, AttributeError):
        text += result.stderr or ""
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


# --- Task 2: review --note-file stdin parity + exactly-one guard (STAGE-05) ---


def test_review_note_file_stdin_records_quote_heavy_note(repo):
    _seal_a_unit(repo)
    tricky = 'He said "ship it" now::later then\nsecond line'
    result = runner.invoke(
        app,
        ["review", "u", "--verdict", "accept", "--note-file", "-"],
        input=tricky,
    )
    assert result.exit_code == 0, result.output
    summary = FilesystemPlanningStore().read_provenance(
        "u", root=repo
    ).reviewer_edits[-1].summary
    # Quotes, the `::` trap, and the newline all round-trip through stdin.
    assert '"ship it"' in summary
    assert "::" in summary
    assert "second line" in summary


def test_review_note_file_path_reads_from_file(repo):
    _seal_a_unit(repo)
    note_path = repo / "note.txt"
    note_path.write_text("from a file::yes\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["review", "u", "--verdict", "accept", "--note-file", str(note_path)],
    )
    assert result.exit_code == 0, result.output
    summary = FilesystemPlanningStore().read_provenance(
        "u", root=repo
    ).reviewer_edits[-1].summary
    assert "from a file::yes" in summary


def test_review_both_note_and_note_file_refuses_exit_2(repo):
    _seal_a_unit(repo)
    result = runner.invoke(
        app,
        ["review", "u", "--verdict", "accept", "--note", "x", "--note-file", "-"],
        input="y",
    )
    assert result.exit_code == 2, result.output
    assert "exactly one of --note" in _combined(result).lower()


def test_review_neither_note_nor_note_file_refuses_exit_2(repo):
    _seal_a_unit(repo)
    result = runner.invoke(app, ["review", "u", "--verdict", "accept"])
    assert result.exit_code == 2, result.output
    assert "exactly one of --note" in _combined(result).lower()


def test_review_note_file_missing_path_refuses_exit_2(repo):
    _seal_a_unit(repo)
    result = runner.invoke(
        app,
        ["review", "u", "--verdict", "accept", "--note-file", "nope.txt"],
    )
    assert result.exit_code == 2, result.output
    assert "no such note file" in _combined(result).lower()


# --- Task 3: accept-branch staging cleanup + --keep-staging (PROV-05) ---------


def test_accept_cleans_staging_and_narrates(repo):
    _seal_a_unit(repo)
    staging = _make_staging(repo)
    assert staging.is_dir()
    result = runner.invoke(
        app, ["review", "u", "--verdict", "accept", "--note", "ship it"]
    )
    assert result.exit_code == 0, result.output
    assert "staging: removed .dogen/staging/u/" in result.output
    assert not staging.exists()


def test_keep_staging_preserves_dir_and_narrates(repo):
    _seal_a_unit(repo)
    staging = _make_staging(repo)
    result = runner.invoke(
        app,
        [
            "review",
            "u",
            "--verdict",
            "accept",
            "--note",
            "ship it",
            "--keep-staging",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "staging: kept (--keep-staging)" in result.output
    assert staging.is_dir()


def test_accept_with_absent_staging_is_silent_noop(repo):
    _seal_a_unit(repo)
    assert not (repo / ".dogen" / "staging" / "u").exists()
    result = runner.invoke(
        app, ["review", "u", "--verdict", "accept", "--note", "ship it"]
    )
    assert result.exit_code == 0, result.output
    # Removal returned False (nothing to clean) -> no narration line, no error.
    assert "staging: removed" not in result.output
    assert "staging: kept" not in result.output


def test_fix_verdict_does_not_touch_staging(repo):
    _seal_a_unit(repo)
    staging = _make_staging(repo)
    result = runner.invoke(
        app, ["review", "u", "--verdict", "fix", "--note", "tighten the intro"]
    )
    assert result.exit_code == 0, result.output
    # Only a sealing accept cleans; fix reopens and must keep the scratch.
    assert staging.is_dir()
    assert "staging:" not in result.output


# --- Plan 09-02 Task 1: read_draft_dir two-tier basename fallback (STAGE-01/02)


def _write(base: Path, rel: str, text: str = "x\n") -> None:
    """Write ``text`` at ``base/rel``, creating parents."""
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_exact_relpath_handoff_returns_no_note(tmp_path):
    # Tier 1 (mirrored) is unchanged: exact-relpath mapping, note is None.
    base = tmp_path / "handoff"
    base.mkdir()
    _write(base, "guide/a.md", "# A\nprimary\n")
    _write(base, "guide/b.md", "# B\nextra one\n")
    _write(base, "reference/c.rst", "C\n=\nextra two\n")
    text, pages, note = compose.read_draft_dir(
        base, primary="guide/a.md", extras=["guide/b.md", "reference/c.rst"]
    )
    assert "primary" in text
    assert "extra one" in pages["guide/b.md"]
    assert "extra two" in pages["reference/c.rst"]
    assert note is None


def test_flat_handoff_maps_by_basename_unit(tmp_path):
    # Tier 2 (STAGE-01, D-01): a flat handoff with unique basenames maps and
    # emits the note; the staged files are read, never deleted.
    base = tmp_path / "handoff"
    base.mkdir()
    _write(base, "a.md", "# A\nprimary\n")
    _write(base, "b.md", "# B\nextra one\n")
    _write(base, "c.rst", "C\n=\nextra two\n")
    text, pages, note = compose.read_draft_dir(
        base, primary="guide/a.md", extras=["guide/b.md", "reference/c.rst"]
    )
    assert "primary" in text
    assert "extra one" in pages["guide/b.md"]
    assert "extra two" in pages["reference/c.rst"]
    assert note == "handoff staged flat; mapped by basename"
    # never-delete: the fallback only reads the staged files.
    assert (base / "a.md").exists()
    assert (base / "b.md").exists()
    assert (base / "c.rst").exists()


def test_partial_mirror_flat_retry_maps_whole_set_by_basename(tmp_path):
    # D-01: when exact mapping leaves ANY target unmatched, the WHOLE handoff
    # is retried by basename (no per-file mixing) — a half-mirrored/half-flat
    # handoff with unique basenames still maps and emits the note.
    base = tmp_path / "handoff"
    base.mkdir()
    _write(base, "guide/a.md", "# A\nprimary\n")  # mirrored
    _write(base, "b.md", "# B\nextra one\n")  # flat
    _write(base, "c.rst", "C\n=\nextra two\n")  # flat
    text, pages, note = compose.read_draft_dir(
        base, primary="guide/a.md", extras=["guide/b.md", "reference/c.rst"]
    )
    assert "primary" in text
    assert "extra one" in pages["guide/b.md"]
    assert "extra two" in pages["reference/c.rst"]
    assert note == "handoff staged flat; mapped by basename"


def test_ambiguous_basename_declared_side_refuses(tmp_path):
    # D-02: two declared targets share a basename -> fallback does NOT apply;
    # falls through to handoff_incomplete naming the colliding basename.
    base = tmp_path / "handoff"
    base.mkdir()
    _write(base, "index.rst", "x\n")
    with pytest.raises(compose.HandoffIncompleteError) as excinfo:
        compose.read_draft_dir(
            base, primary="guide/index.rst", extras=["reference/index.rst"]
        )
    msg = str(excinfo.value)
    assert "index.rst" in msg
    assert "guide/index.rst" in msg and "reference/index.rst" in msg
    assert msg.endswith("move the staged files into place; do not delete them")


def test_ambiguous_basename_staged_side_refuses(tmp_path):
    # D-02 / Pitfall 1: two staged files share a basename -> refuse (uniqueness
    # required on BOTH sides), naming the colliding basename.
    base = tmp_path / "handoff"
    base.mkdir()
    _write(base, "a.md")
    _write(base, "b.md")
    _write(base, "sub1/c.rst")
    _write(base, "sub2/c.rst")
    with pytest.raises(compose.HandoffIncompleteError) as excinfo:
        compose.read_draft_dir(
            base, primary="guide/a.md", extras=["guide/b.md", "reference/c.rst"]
        )
    msg = str(excinfo.value)
    assert "c.rst" in msg
    assert "sub1/c.rst" in msg and "sub2/c.rst" in msg
    assert msg.endswith("move the staged files into place; do not delete them")


def test_handoff_error_enumerates_expected_paths(tmp_path):
    # STAGE-02, D-02b: a genuinely incomplete handoff enumerates the exact
    # expected path per missing target and ends with the never-delete sentence.
    base = tmp_path / "handoff"
    base.mkdir()
    _write(base, "guide/a.md", "# A\n")  # b + c missing
    with pytest.raises(compose.HandoffIncompleteError) as excinfo:
        compose.read_draft_dir(
            base, primary="guide/a.md", extras=["guide/b.md", "reference/c.rst"]
        )
    msg = str(excinfo.value)
    assert "expected: handoff/guide/b.md" in msg
    assert "expected: handoff/reference/c.rst" in msg
    assert msg.endswith("move the staged files into place; do not delete them")


def test_handoff_error_undeclared_names_move_destination(tmp_path):
    # STAGE-02, D-02b: a complete-plus-surplus handoff refuses undeclared_target,
    # naming the stray file and ending with the never-delete sentence.
    base = tmp_path / "handoff"
    base.mkdir()
    _write(base, "guide/a.md", "# A\n")
    _write(base, "guide/b.md", "# B\n")
    _write(base, "reference/c.rst", "C\n=\n")
    _write(base, "rogue.md", "# R\n")
    with pytest.raises(compose.UndeclaredTargetError) as excinfo:
        compose.read_draft_dir(
            base, primary="guide/a.md", extras=["guide/b.md", "reference/c.rst"]
        )
    msg = str(excinfo.value)
    assert "rogue.md" in msg
    assert msg.endswith("move the staged files into place; do not delete them")
