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
import yaml
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


def test_remove_staging_refuses_symlink_to_sibling_in_repo(repo):
    # CR-01: the escape-*out* test above gave false confidence. The real hole is
    # a staging leaf symlinked to a sibling dir *inside* the root (docs/), which
    # _assert_within_root + _assert_not_under_planning both PASS — the old code
    # then rmtree'd the symlink target (the very output an accept just sealed).
    # Must refuse with a clean ValueError and delete NOTHING.
    store = FilesystemPlanningStore()
    docs = repo / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("sealed output\n", encoding="utf-8")
    staging_parent = repo / ".dogen" / "staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    (staging_parent / "u").symlink_to(Path("../../docs"), target_is_directory=True)
    with pytest.raises(ValueError):
        store.remove_staging("u", root=repo)
    assert (docs / "page.md").read_text(encoding="utf-8") == "sealed output\n"


def test_remove_staging_refuses_symlink_to_repo_root(repo):
    # CR-01 worst case: a staging leaf symlinked to the repo root would rmtree
    # the entire working tree (including .git). Refuse it; delete nothing.
    store = FilesystemPlanningStore()
    staging_parent = repo / ".dogen" / "staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    (staging_parent / "u").symlink_to(Path("../.."), target_is_directory=True)
    with pytest.raises(ValueError):
        store.remove_staging("u", root=repo)
    assert (repo / "README.md").exists()
    assert (repo / ".git").exists()


def test_delete_unit_refuses_symlink_to_sibling_in_repo(repo):
    # CR-01: delete_unit shares the identical root cause — a .dogen/units/<id>
    # symlinked to a sibling in-repo dir (docs/) must refuse cleanly and delete
    # nothing, not rmtree through the symlink.
    store = FilesystemPlanningStore()
    docs = repo / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("real docs\n", encoding="utf-8")
    units_parent = repo / ".dogen" / "units"
    units_parent.mkdir(parents=True, exist_ok=True)
    (units_parent / "u").symlink_to(Path("../../docs"), target_is_directory=True)
    with pytest.raises(ValueError):
        store.delete_unit("u", root=repo)
    assert (docs / "page.md").read_text(encoding="utf-8") == "real docs\n"


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
    summary = (
        FilesystemPlanningStore()
        .read_provenance("u", root=repo)
        .reviewer_edits[-1]
        .summary
    )
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
    summary = (
        FilesystemPlanningStore()
        .read_provenance("u", root=repo)
        .reviewer_edits[-1]
        .summary
    )
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


# --- Plan 09-02 Task 2: single caller unpacks the note in lockstep (STAGE-01) --


def _declare_span(repo: Path) -> None:
    """Declare + sign off a three-page unit ``u`` spanning distinct basenames."""
    result = runner.invoke(
        app,
        [
            "unit",
            "new",
            "u",
            "--intent",
            "reference",
            "--audience",
            "d",
            "--target",
            "guide/a.md",
            "--also-target",
            "guide/b.md",
            "--also-target",
            "reference/c.rst",
        ],
    )
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0


def _stage_flat(repo: Path, files: dict[str, str]) -> Path:
    """Stage ``files`` (basename-keyed) under ``.dogen/staging/u/handoff``."""
    base = repo / ".dogen" / "staging" / "u" / "handoff"
    for rel, text in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return base


def test_flat_handoff_draft_prints_mapped_by_basename(repo):
    _declare_span(repo)
    base = _stage_flat(
        repo,
        {
            "a.md": "# A\nprimary\n",
            "b.md": "# B\nextra one\n",
            "c.rst": "C\n=\nextra two\n",
        },
    )
    result = runner.invoke(
        app, ["draft", "u", "--provider", "host-harness", "--draft-dir", str(base)]
    )
    assert result.exit_code == 0, result.output
    # The caller unpacks the widened 3-tuple and surfaces the note (Pitfall 3).
    assert "mapped by basename" in result.output
    # The pages land at their declared docs-relative targets.
    assert "primary" in (repo / "docs" / "guide" / "a.md").read_text(encoding="utf-8")
    assert "extra two" in (repo / "docs" / "reference" / "c.rst").read_text(
        encoding="utf-8"
    )


def test_flat_handoff_leaves_staged_files_on_disk(repo):
    # STAGE-01 signature: the fallback accepts WITHOUT deleting any staged draft.
    _declare_span(repo)
    base = _stage_flat(repo, {"a.md": "# A\n", "b.md": "# B\n", "c.rst": "C\n=\n"})
    result = runner.invoke(
        app, ["draft", "u", "--provider", "host-harness", "--draft-dir", str(base)]
    )
    assert result.exit_code == 0, result.output
    assert (base / "a.md").exists()
    assert (base / "b.md").exists()
    assert (base / "c.rst").exists()


# --- Plan 09-03 Task 1: read_context_report lenient YAML->JSON + hint (STAGE-04) -


def _valid_report_yaml() -> str:
    """A valid ``report.yaml`` body with one commit-stampable origin."""
    return (
        "schema_version: 2\n"
        "context_origins:\n"
        "- path: src/a.py\n"
        "  commit: ''\n"
        "  note: ''\n"
        "tools_used: []\n"
        "gaps: []\n"
        "gaps_note: ''\n"
    )


def test_report_lenient_parses_valid_yaml(tmp_path):
    # Tier 1 (unchanged): a valid YAML report parses into a ContextReport.
    report = tmp_path / "report.yaml"
    report.write_text(_valid_report_yaml(), encoding="utf-8")
    parsed = compose.read_context_report(report)
    assert parsed.schema_version == 2
    assert parsed.context_origins[0].path == "src/a.py"


def test_report_lenient_parses_quoted_double_colon_scalar(tmp_path):
    # A report that QUOTES the '::' scalar is valid YAML and parses — the
    # round-3 trap was an unquoted '::'; quoting is exactly what the hint asks.
    report = tmp_path / "report.yaml"
    report.write_text(
        "schema_version: 2\n"
        "context_origins:\n"
        '- path: "a::b"\n'
        "  commit: ''\n"
        "  note: ''\n",
        encoding="utf-8",
    )
    parsed = compose.read_context_report(report)
    assert parsed.context_origins[0].path == "a::b"


def test_report_lenient_json_fallback_parses(tmp_path):
    # Valid JSON that is NOT valid YAML (a tab between flow entries) parses via
    # the silent json.loads fallback inside the except-YAMLError arm (D-08).
    report = tmp_path / "report.json"
    report.write_text(
        '{"schema_version": 2,\t"context_origins": [], "tools_used": [],'
        ' "gaps": [], "gaps_note": ""}',
        encoding="utf-8",
    )
    # sanity: the payload really is YAML-invalid so the JSON arm is exercised.
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(report.read_text(encoding="utf-8"))
    parsed = compose.read_context_report(report)
    assert parsed.schema_version == 2


def test_report_lenient_still_runs_full_validation(tmp_path):
    # Leniency is FORMAT-only: a parsed report still runs the ContextReport
    # validator, so a non-hex commit stamp is refused (typed load boundary).
    report = tmp_path / "report.yaml"
    report.write_text(
        "context_origins:\n- path: src/a.py\n  commit: nothex!\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hex SHA or"):
        compose.read_context_report(report)


def test_report_hint_on_unparseable_reports_line_col_and_double_colon(tmp_path):
    # Neither valid YAML nor valid JSON: raise ValueError naming the YAML
    # parser's 1-based line/column and the '::'-quoting hint (D-08).
    report = tmp_path / "report.yaml"
    report.write_text("context_origins:\n- path: a:: b\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        compose.read_context_report(report)
    msg = str(excinfo.value)
    assert "line 2" in msg  # 0-indexed mark.line 1 -> displayed 2
    assert "column 11" in msg  # 0-indexed mark.column 10 -> displayed 11
    assert "::" in msg


def test_report_hint_markless_yaml_error_does_not_crash(tmp_path, monkeypatch):
    # Pitfall 2: a YAMLError carrying no problem_mark must degrade gracefully
    # (no AttributeError) and still surface the '::' hint, with no location.
    report = tmp_path / "report.yaml"
    report.write_text("context_origins: []\n", encoding="utf-8")

    def _boom(_text):
        raise yaml.YAMLError("markless boom")

    monkeypatch.setattr(compose.yaml, "safe_load", _boom)
    with pytest.raises(ValueError) as excinfo:
        compose.read_context_report(report)
    msg = str(excinfo.value)
    assert "::" in msg
    assert "line" not in msg  # markless -> no " at line ..." suffix


# --- Plan 09-03 Task 2: report template skeleton (STAGE-04, D-05/D-06) ---------


def _declare_with_sources(repo: Path) -> None:
    """Declare + sign off unit ``u`` with two declared sources + one target."""
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "a.py").write_text("a\n", encoding="utf-8")
    (repo / "src" / "b.py").write_text("b\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "unit",
            "new",
            "u",
            "--intent",
            "reference",
            "--audience",
            "d",
            "--source",
            "src/a.py",
            "--source",
            "src/b.py",
            "--target",
            "guide/a.md",
        ],
    )
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0


def test_report_template_prints_skeleton_from_sources(repo):
    _declare_with_sources(repo)
    result = runner.invoke(app, ["report", "template", "u"])
    assert result.exit_code == 0, result.output
    parsed = yaml.safe_load(result.output)
    # One origin per declared source, empty tools_used/gaps (D-06).
    assert [o["path"] for o in parsed["context_origins"]] == ["src/a.py", "src/b.py"]
    assert parsed["tools_used"] == []
    assert parsed["gaps"] == []
    # Nothing is written by default (print-by-default, D-05).
    assert not (repo / ".dogen" / "staging" / "u" / "report.yaml").exists()


def test_report_template_roundtrips_through_read_context_report(repo, tmp_path):
    _declare_with_sources(repo)
    result = runner.invoke(app, ["report", "template", "u"])
    assert result.exit_code == 0, result.output
    out = tmp_path / "roundtrip.yaml"
    out.write_text(result.output, encoding="utf-8")
    report = compose.read_context_report(out)
    assert [o.path for o in report.context_origins] == ["src/a.py", "src/b.py"]
    assert report.schema_version >= 2


def test_report_template_write_lands_report_yaml(repo):
    _declare_with_sources(repo)
    result = runner.invoke(app, ["report", "template", "u", "--write"])
    assert result.exit_code == 0, result.output
    written = repo / ".dogen" / "staging" / "u" / "report.yaml"
    assert written.is_file()
    parsed = yaml.safe_load(written.read_text(encoding="utf-8"))
    assert [o["path"] for o in parsed["context_origins"]] == ["src/a.py", "src/b.py"]


def test_report_template_write_refuses_clobber_without_force(repo):
    _declare_with_sources(repo)
    written = repo / ".dogen" / "staging" / "u" / "report.yaml"
    written.parent.mkdir(parents=True, exist_ok=True)
    written.write_text("in: progress\n", encoding="utf-8")
    result = runner.invoke(app, ["report", "template", "u", "--write"])
    assert result.exit_code == 2, result.output
    assert "refusing to overwrite" in _combined(result).lower()
    # The in-progress report is untouched.
    assert written.read_text(encoding="utf-8") == "in: progress\n"


def test_report_template_write_force_overwrites(repo):
    _declare_with_sources(repo)
    written = repo / ".dogen" / "staging" / "u" / "report.yaml"
    written.parent.mkdir(parents=True, exist_ok=True)
    written.write_text("in: progress\n", encoding="utf-8")
    result = runner.invoke(app, ["report", "template", "u", "--write", "--force"])
    assert result.exit_code == 0, result.output
    parsed = yaml.safe_load(written.read_text(encoding="utf-8"))
    assert [o["path"] for o in parsed["context_origins"]] == ["src/a.py", "src/b.py"]


def test_report_template_missing_unit_refuses(repo):
    result = runner.invoke(app, ["report", "template", "nope"])
    assert result.exit_code == 2, result.output


# --- Plan 09-03 Task 3: staging plan expected tree + scaffold (STAGE-03, D-07) -


def _stage_page(repo: Path, relpath: str, text: str = "draft\n") -> Path:
    """Stage a page at the exact ``.dogen/staging/u/handoff/<relpath>``."""
    path = repo / ".dogen" / "staging" / "u" / "handoff" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_staging_plan_prints_expected_tree_all_missing(repo):
    _declare_span(repo)  # targets: guide/a.md, guide/b.md, reference/c.rst
    result = runner.invoke(app, ["staging", "plan", "u"])
    assert result.exit_code == 0, result.output
    for target in ("guide/a.md", "guide/b.md", "reference/c.rst"):
        assert f"handoff/{target} [missing]" in result.output


def test_staging_plan_marks_staged_pages(repo):
    _declare_span(repo)
    _stage_page(repo, "guide/a.md")
    result = runner.invoke(app, ["staging", "plan", "u"])
    assert result.exit_code == 0, result.output
    assert "handoff/guide/a.md [✓]" in result.output
    assert "handoff/guide/b.md [missing]" in result.output
    assert "handoff/reference/c.rst [missing]" in result.output


def test_staging_plan_scaffold_creates_missing_placeholders(repo):
    _declare_span(repo)
    result = runner.invoke(app, ["staging", "plan", "u", "--scaffold"])
    assert result.exit_code == 0, result.output
    handoff = repo / ".dogen" / "staging" / "u" / "handoff"
    for target in ("guide/a.md", "guide/b.md", "reference/c.rst"):
        assert (handoff / target).is_file()
    # After scaffold the tree reads back as fully staged.
    assert "handoff/guide/a.md [✓]" in result.output


def test_staging_plan_scaffold_does_not_clobber_existing(repo):
    _declare_span(repo)
    staged = _stage_page(repo, "guide/a.md", "real work\n")
    result = runner.invoke(app, ["staging", "plan", "u", "--scaffold"])
    assert result.exit_code == 0, result.output
    # The pre-staged page keeps its content; the missing ones are created.
    assert staged.read_text(encoding="utf-8") == "real work\n"
    handoff = repo / ".dogen" / "staging" / "u" / "handoff"
    assert (handoff / "guide/b.md").is_file()
    assert (handoff / "reference/c.rst").is_file()


def test_staging_plan_scaffold_does_not_seed_report_yaml(repo):
    # Open Question 2: staging plan --scaffold is handoff-only; report.yaml is
    # report template --write's responsibility.
    _declare_span(repo)
    result = runner.invoke(app, ["staging", "plan", "u", "--scaffold"])
    assert result.exit_code == 0, result.output
    assert not (repo / ".dogen" / "staging" / "u" / "report.yaml").exists()


def test_staging_plan_missing_unit_refuses(repo):
    result = runner.invoke(app, ["staging", "plan", "nope"])
    assert result.exit_code == 2, result.output
