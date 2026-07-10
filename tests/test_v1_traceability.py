"""v1 traceability behaviours: commit seam, plan hash, verdicts, report, verbs.

The redesign's acceptance surface, end-to-end where it matters:

* the commit seam records every lifecycle transition with ``Dogen-*`` trailers,
  so a unit's whole path is reconstructable from ``git log`` alone;
* ``signoff`` freezes the plan hash and a post-signoff edit surfaces as a
  ``stale_plan`` signal instead of drafting silently;
* review verdicts are structured — ``accept`` seals the exact draft text,
  ``fix``/``redraft`` append the note to the steering stream;
* the passenger's context report closes the passenger-blind provenance hole;
* the new CLI verbs (unit edit/show, status, provider show/set, commits,
  context ls/add) behave per the Q1–Q8 decisions.

Fully offline: mock/host-harness providers only, local tmp git repos.
"""

import asyncio
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.git_repo import GitRepoSeam
from dogen.adapters.mock_provider import MockDraftingProvider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose
from dogen.cli.main import app
from dogen.core import orchestrator
from dogen.core.models import Intent, SteeringOrigin

runner = CliRunner()


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tmp git repo with identity, an initial commit, cwd set, env cleared."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Ada Lovelace"], check=True
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


def _json_line(result) -> dict:
    for line in result.output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            return json.loads(stripped)
    raise AssertionError(f"no JSON in output: {result.output!r}")


# --- the git seam adapter ----------------------------------------------------


def test_head_commit_empty_outside_a_repo(tmp_path):
    assert GitRepoSeam().head_commit(root=tmp_path) == ""


def test_commit_outside_a_repo_is_a_benign_noop(tmp_path):
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    sha = GitRepoSeam().commit(root=tmp_path, paths=[tmp_path / "f.txt"], message="m")
    assert sha == ""


def test_commit_records_trailers_and_returns_head(repo):
    (repo / "f.txt").write_text("x", encoding="utf-8")
    sha = GitRepoSeam().commit(
        root=repo,
        paths=[repo / "f.txt"],
        message="dogen(u): declared — t\n\nDogen-Unit: u\nDogen-Phase: declared",
    )
    assert sha == _git(repo, "rev-parse", "HEAD")
    body = _git(repo, "log", "-1", "--format=%B")
    assert "Dogen-Unit: u" in body
    assert "Dogen-Phase: declared" in body


def test_commit_with_no_changes_is_a_noop(repo):
    sha = GitRepoSeam().commit(root=repo, paths=[repo / "README.md"], message="noop")
    assert sha == ""


# --- end-to-end: a unit's path is reconstructable from git log alone ---------


def test_full_loop_is_reconstructable_from_git_log(repo):
    store = FilesystemPlanningStore()
    for args in (
        [
            "unit",
            "new",
            "u",
            "--intent",
            "reference",
            "--audience",
            "devs",
            "--title",
            "About",
            "--source",
            "README.md",
        ],
        ["signoff", "u"],
        ["steer", "u", "--note", "state facts; no researcher register"],
        ["draft", "u", "--provider", "mock"],
        ["review", "u", "--verdict", "accept", "--note", "ship it"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.output)

    # Reconstruction: the grep alone replays the unit's path, oldest first.
    log = _git(
        repo, "log", "--reverse", "--grep", "Dogen-Unit: u", "--format=%(trailers)"
    )
    phases = [
        line.split(": ", 1)[1]
        for line in log.splitlines()
        if line.startswith("Dogen-Phase: ")
    ]
    assert phases == ["declared", "signed-off", "steered", "drafted", "reviewed"]

    # The drafted transition committed the draft alongside the sidecars.
    drafted_files = _git(
        repo,
        "log",
        "--grep",
        "Dogen-Phase: drafted",
        "--name-only",
        "--format=",
    ).splitlines()
    assert "docs/u.md" in drafted_files
    assert ".dogen/units/u/provenance.yaml" in drafted_files

    # The spine: sources, signoff, and generation all carry commit stamps.
    unit = store.load_unit("u", root=repo)
    assert unit.sources[0].commit  # stamped at declare time
    prov = store.read_provenance("u", root=repo)
    assert prov.signoff is not None
    assert prov.signoff.plan_hash
    assert prov.signoff.commit
    generation = prov.generations[0]
    assert generation.source_commit
    draft_text = (repo / "docs" / "u.md").read_text(encoding="utf-8")
    assert (
        generation.files[0].sha256
        == hashlib.sha256(draft_text.encode("utf-8")).hexdigest()
    )
    assert generation.files[0].path == "docs/u.md"
    # The drafted run is correlated into the progress history (v1 cross-ref).
    progress = store.read_progress("u", root=repo)
    assert any(e.run_id == generation.run_id for e in progress.history)
    # accept sealed the exact reviewed text (the second bookend).
    accept = prov.reviewer_edits[-1]
    assert accept.verdict is not None and accept.verdict.value == "accept"
    assert accept.files[0].sha256 == generation.files[0].sha256
    # The manual steer note is durable in the stream.
    assert [e.origin for e in prov.steering] == [SteeringOrigin.manual]


def test_fix_verdict_appends_a_review_steering_entry(repo):
    store = FilesystemPlanningStore()
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "devs"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
        ["review", "u", "--verdict", "redraft", "--note", "drop the Go names"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.output)
    prov = store.read_provenance("u", root=repo)
    # The verdict IS steering for the next pass — recorded durably (RC-2 fix).
    assert [e.origin for e in prov.steering] == [SteeringOrigin.review]
    assert prov.steering[0].note == "drop the Go names"
    assert prov.reviewer_edits[-1].verdict is not None
    assert prov.reviewer_edits[-1].verdict.value == "redraft"
    assert prov.reviewer_edits[-1].files == []  # only accept seals


def test_commits_off_disables_the_seam(repo):
    result = runner.invoke(app, ["commits", "off"])
    assert result.exit_code == 0, result.output
    head_before = _git(repo, "rev-parse", "HEAD")
    result = runner.invoke(
        app, ["unit", "new", "u", "--intent", "reference", "--audience", "devs"]
    )
    assert result.exit_code == 0, result.output
    assert _git(repo, "rev-parse", "HEAD") == head_before


def test_no_commit_flag_skips_one_transition(repo):
    head_before = _git(repo, "rev-parse", "HEAD")
    result = runner.invoke(
        app,
        [
            "unit",
            "new",
            "u",
            "--intent",
            "reference",
            "--audience",
            "devs",
            "--no-commit",
        ],
    )
    assert result.exit_code == 0, result.output
    assert _git(repo, "rev-parse", "HEAD") == head_before


# --- signoff freezes the plan; edits surface as stale ------------------------


def test_post_signoff_plan_edit_surfaces_as_stale(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "devs"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(
        app, ["unit", "edit", "u", "--title", "Changed after approval"]
    )
    assert result.exit_code == 0, result.output
    # status flags the stale plan and suggests the re-sign.
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["stale_plan"] is True
    assert "signoff" in board[0]["next"]
    # drafting still runs, but the gap is surfaced, never silent.
    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 0, result.output
    assert _json_line(result)["stale_plan"] is True
    assert "changed after its signoff" in result.output


def test_steering_notes_reach_the_provider(repo):
    captured: dict = {}

    class _Spy(MockDraftingProvider):
        async def draft_unit(self, **kwargs):  # noqa: ANN003
            captured.update(kwargs)
            return await super().draft_unit(**kwargs)

    store = FilesystemPlanningStore()
    for args in (
        [
            "unit",
            "new",
            "u",
            "--intent",
            "reference",
            "--audience",
            "devs",
            "--notes",
            "seeded planning note",
        ],
        ["signoff", "u"],
        ["steer", "u", "--note", "appended correction"],
    ):
        assert runner.invoke(app, args).exit_code == 0

    request = compose.build_draft_request(
        "u", root=repo, store=store, provider=_Spy(), provider_name="mock"
    )
    asyncio.run(orchestrator.draft(request))
    assert captured["notes"] == ["seeded planning note", "appended correction"]


# --- the passenger context report (uniform provenance contract) --------------


def test_report_merges_into_the_generation(repo):
    store = FilesystemPlanningStore()
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "devs"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    handoff = repo / "handoff.md"
    handoff.write_text("# Drafted by the host\n\nbody\n", encoding="utf-8")
    report = repo / "report.yaml"
    report.write_text(
        "context_origins:\n"
        "  - path: internal/foo.go\n"
        "    commit: abc1234\n"
        "  - path: tests/main/fixture.yaml\n"
        "tools_used: [Read, Grep]\n"
        "gaps: ['interface semantics unverified at origin']\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "draft",
            "u",
            "--provider",
            "host-harness",
            "--draft-file",
            str(handoff),
            "--report",
            str(report),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    generation = store.read_provenance("u", root=repo).generations[0]
    assert [o.path for o in generation.context_origins] == [
        "internal/foo.go",
        "tests/main/fixture.yaml",
    ]
    assert generation.context_origins[0].commit == "abc1234"
    assert generation.tools_used == ["Read", "Grep"]
    assert generation.gaps == ["interface semantics unverified at origin"]
    assert generation.mode == "passenger"
    assert generation.handoff_path == str(handoff)


# --- the new CLI verbs --------------------------------------------------------


def test_unit_edit_merges_and_preserves_the_body(repo):
    store = FilesystemPlanningStore()
    assert (
        runner.invoke(
            app,
            [
                "unit",
                "new",
                "u",
                "--intent",
                "reference",
                "--audience",
                "devs",
                "--title",
                "Original",
                "--source",
                "README.md",
            ],
        ).exit_code
        == 0
    )
    unit_md = repo / ".dogen" / "units" / "u" / "unit.md"
    hand_edited = unit_md.read_text(encoding="utf-8") + "\nHand-authored outline.\n"
    unit_md.write_text(hand_edited, encoding="utf-8")
    result = runner.invoke(
        app,
        ["unit", "edit", "u", "--add-source", "docs/", "--audience", "operators"],
    )
    assert result.exit_code == 0, result.output
    unit = store.load_unit("u", root=repo)
    assert unit.title == "Original"  # untouched field survives
    assert unit.audience == "operators"  # named field replaced
    assert [s.path for s in unit.sources] == ["README.md", "docs/"]
    assert "Hand-authored outline." in unit_md.read_text(encoding="utf-8")


def test_unit_edit_nothing_to_change_is_bad_input(repo):
    assert (
        runner.invoke(
            app, ["unit", "new", "u", "--intent", "reference", "--audience", "d"]
        ).exit_code
        == 0
    )
    result = runner.invoke(app, ["unit", "edit", "u"])
    assert result.exit_code == 2


def test_unit_edit_body_file_replaces_the_plan_body(repo):
    assert (
        runner.invoke(
            app,
            [
                "unit",
                "new",
                "u",
                "--intent",
                "reference",
                "--audience",
                "devs",
                "--title",
                "Original",
                "--source",
                "README.md",
            ],
        ).exit_code
        == 0
    )
    outline = repo / "outline.md"
    outline.write_text(
        "## Intent & scope\n\nSettled in dialogue.\n\n"
        "## Outline / acceptance\n\n- covers every field\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["unit", "edit", "u", "--body-file", str(outline)])
    assert result.exit_code == 0, result.output
    text = (repo / ".dogen" / "units" / "u" / "unit.md").read_text(encoding="utf-8")
    assert "Settled in dialogue." in text
    assert "covers every field" in text
    assert "Describe what this page covers" not in text  # placeholder replaced
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.title == "Original"  # front matter untouched
    assert [s.path for s in unit.sources] == ["README.md"]
    trailers = _git(repo, "log", "-1", "--format=%(trailers)")
    assert "Dogen-Phase: edited" in trailers  # the seam recorded the transition


def test_unit_edit_body_from_stdin(repo):
    assert (
        runner.invoke(
            app, ["unit", "new", "u", "--intent", "reference", "--audience", "d"]
        ).exit_code
        == 0
    )
    result = runner.invoke(
        app,
        ["unit", "edit", "u", "--body-file", "-"],
        input="## Intent & scope\n\nPiped from the skill.\n",
    )
    assert result.exit_code == 0, result.output
    text = (repo / ".dogen" / "units" / "u" / "unit.md").read_text(encoding="utf-8")
    assert "Piped from the skill." in text


def test_unit_edit_body_file_missing_is_bad_input(repo):
    assert (
        runner.invoke(
            app, ["unit", "new", "u", "--intent", "reference", "--audience", "d"]
        ).exit_code
        == 0
    )
    result = runner.invoke(app, ["unit", "edit", "u", "--body-file", "nope.md"])
    assert result.exit_code == 2


def test_unit_edit_body_after_signoff_surfaces_as_stale(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(
        app,
        ["unit", "edit", "u", "--body-file", "-"],
        input="## Outline / acceptance\n\n- late scope change\n",
    )
    assert result.exit_code == 0, result.output
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["stale_plan"] is True


def test_unit_show_by_draft_reverse_lookup(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "devs"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(app, ["unit", "show", "--by-draft", "docs/u.md", "--json"])
    assert result.exit_code == 0, result.output
    assert _json_line(result)["unit"]["unit_id"] == "u"


def test_status_suggests_the_next_verb(repo):
    assert (
        runner.invoke(
            app, ["unit", "new", "u", "--intent", "reference", "--audience", "d"]
        ).exit_code
        == 0
    )
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["signed_off"] is False
    assert board[0]["next"] == "dogen signoff u"
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["next"] == "dogen draft u"
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["next"] == "dogen review u"


def test_provider_defaults_show_and_set(repo):
    shown = _json_line(runner.invoke(app, ["provider", "show", "--json"]))
    assert shown["provider"] == "host-harness"
    assert shown["source"] == "default"
    assert runner.invoke(app, ["provider", "set", "copilot"]).exit_code == 0
    shown = _json_line(runner.invoke(app, ["provider", "show", "--json"]))
    assert shown["provider"] == "copilot"
    assert shown["source"] == "repo config"


def test_provider_set_rejects_unknown_and_auto(repo):
    assert runner.invoke(app, ["provider", "set", "banana"]).exit_code == 2
    assert runner.invoke(app, ["provider", "set", "auto"]).exit_code == 2


def test_env_pin_outranks_repo_config(repo, monkeypatch):
    assert runner.invoke(app, ["provider", "set", "copilot"]).exit_code == 0
    monkeypatch.setenv("DOGEN_PROVIDER", "mock")
    shown = _json_line(runner.invoke(app, ["provider", "show", "--json"]))
    assert shown["provider"] == "mock"
    assert shown["source"] == "env"


def test_context_add_and_ls_land_artifacts(repo):
    artifact = repo / "map.md"
    artifact.write_text("# code-to-docs map\n", encoding="utf-8")
    result = runner.invoke(
        app, ["context", "add", str(artifact), "--as", "code-to-docs-map.md"]
    )
    assert result.exit_code == 0, result.output
    landed = repo / ".dogen" / "context" / "code-to-docs-map.md"
    assert landed.read_text(encoding="utf-8") == "# code-to-docs map\n"
    listed = _json_line(runner.invoke(app, ["context", "ls", "--json"]))
    assert listed == ["code-to-docs-map.md"]
    body = _git(repo, "log", "-1", "--grep", "Dogen-Phase: context", "--format=%B")
    assert "Dogen-Phase: context" in body


def test_signoff_records_plan_hash_of_unit_md(repo):
    store = FilesystemPlanningStore()
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "devs"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    text = store.read_unit_text("u", root=repo)
    prov = store.read_provenance("u", root=repo)
    assert prov.signoff is not None
    assert prov.signoff.plan_hash == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert prov.signoff.intent is Intent.reference


# --- v1.1 mechanism hardening: --target, routing, guards, honesty -------------


def _declare(repo, *extra):
    args = ["unit", "new", "u", "--intent", "reference", "--audience", "d", *extra]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return result


def test_unit_new_target_subdir_end_to_end(repo):
    _declare(repo, "--target", "reference/definition-files/workshop-definition.md")
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.sphinx_target == "reference/definition-files/workshop-definition.md"
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    draft_file = repo / "docs" / "reference" / "definition-files"
    draft_file = draft_file / "workshop-definition.md"
    assert draft_file.is_file()  # parent dirs created by the store
    # The drafted seam commit carries the subdir path.
    files = _git(repo, "log", "-1", "--grep", "Dogen-Phase: drafted", "--name-only")
    assert "docs/reference/definition-files/workshop-definition.md" in files


def test_unit_new_traversing_target_is_bad_input(repo):
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
            "../escape.md",
        ],
    )
    assert result.exit_code == 2
    assert not (repo / ".dogen" / "units" / "u").exists()  # nothing scaffolded


def test_unit_edit_target_moves_existing_draft(repo):
    _declare(repo)
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    old = repo / "docs" / "u.md"
    assert old.is_file()
    result = runner.invoke(app, ["unit", "edit", "u", "--target", "reference/u.md"])
    assert result.exit_code == 0, result.output
    assert not old.exists()
    assert (repo / "docs" / "reference" / "u.md").is_file()
    # The edited seam commit covers the unit dir AND both docs paths (git
    # records the pair as a rename; --no-renames splits it into D + A).
    files = _git(repo, "log", "-1", "--name-status", "--format=", "--no-renames")
    assert ".dogen/units/u/unit.md" in files
    assert "D\tdocs/u.md" in files
    assert "A\tdocs/reference/u.md" in files
    trailers = _git(repo, "log", "-1", "--format=%(trailers)")
    assert "Dogen-Phase: edited" in trailers


def test_unit_edit_target_refuses_destination_clobber(repo):
    _declare(repo)
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    occupied = repo / "docs" / "taken.md"
    occupied.write_text("occupant\n", encoding="utf-8")
    result = runner.invoke(app, ["unit", "edit", "u", "--target", "taken.md", "--json"])
    assert result.exit_code == 1
    assert _json_line(result)["reason"] == "target_exists"
    assert occupied.read_text(encoding="utf-8") == "occupant\n"  # untouched
    assert (repo / "docs" / "u.md").is_file()  # draft not moved


def test_unit_edit_target_without_draft_is_pure_repoint(repo):
    _declare(repo)
    result = runner.invoke(app, ["unit", "edit", "u", "--target", "guides/u.md"])
    assert result.exit_code == 0, result.output
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.sphinx_target == "guides/u.md"
    assert not (repo / "docs").exists()  # nothing was moved or created


def test_unit_edit_target_moves_even_with_no_commit(repo):
    _declare(repo)
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    head_before = _git(repo, "rev-parse", "HEAD")
    result = runner.invoke(
        app, ["unit", "edit", "u", "--target", "moved/u.md", "--no-commit"]
    )
    assert result.exit_code == 0, result.output
    assert (repo / "docs" / "moved" / "u.md").is_file()  # file moved anyway
    assert _git(repo, "rev-parse", "HEAD") == head_before  # no seam commit


def test_unit_mv_preserves_directory_and_custom_basename(repo):
    # Id-derived basename: re-derived to the new id, directory preserved.
    _declare(repo, "--target", "reference/u.md")
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    assert runner.invoke(app, ["unit", "mv", "u", "w"]).exit_code == 0
    store = FilesystemPlanningStore()
    assert store.load_unit("w", root=repo).sphinx_target == "reference/w.md"
    assert (repo / "docs" / "reference" / "w.md").is_file()
    # Custom basename: survives a rename untouched.
    result = runner.invoke(
        app, ["unit", "edit", "w", "--target", "reference/workshop-definition.md"]
    )
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["unit", "mv", "w", "x"]).exit_code == 0
    unit = store.load_unit("x", root=repo)
    assert unit.sphinx_target == "reference/workshop-definition.md"
    assert (repo / "docs" / "reference" / "workshop-definition.md").is_file()


def test_review_emits_next_routing_hint(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    fix = _json_line(
        runner.invoke(
            app, ["review", "u", "--verdict", "fix", "--note", "wrong dir", "--json"]
        )
    )
    # A fix verdict speaks "apply the recorded fix", never "re-draft" (M2).
    assert fix["next"] == "dogen draft u  # apply the recorded fix"
    assert fix["next_id"] == "draft"
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    accept = _json_line(
        runner.invoke(
            app, ["review", "u", "--verdict", "accept", "--note", "ok", "--json"]
        )
    )
    assert accept["next"] == "accepted — the publishing commit/PR is yours"


def test_duplicate_accept_is_refused(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
        ["review", "u", "--verdict", "accept", "--note", "ship it"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    store = FilesystemPlanningStore()
    edits_before = len(store.read_provenance("u", root=repo).reviewer_edits)
    result = runner.invoke(
        app, ["review", "u", "--verdict", "accept", "--note", "ship it", "--json"]
    )
    assert result.exit_code == 1
    assert _json_line(result)["reason"] == "already_accepted"
    edits_after = len(store.read_provenance("u", root=repo).reviewer_edits)
    assert edits_after == edits_before  # nothing appended
    # A changed draft may legitimately be re-accepted.
    unit = store.load_unit("u", root=repo)
    target = repo / "docs" / unit.sphinx_target
    target.write_text(target.read_text(encoding="utf-8") + "\nedit\n", "utf-8")
    result = runner.invoke(
        app, ["review", "u", "--verdict", "accept", "--note", "re-sealed"]
    )
    assert result.exit_code == 0, result.output


def test_unsteered_redraft_is_flagged(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    first = _json_line(
        runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    )
    assert first["unsteered_redraft"] is False  # first pass is never a redraft
    second = _json_line(
        runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    )
    assert second["unsteered_redraft"] is True  # nothing arrived in between
    assert (
        runner.invoke(
            app, ["review", "u", "--verdict", "fix", "--note", "tighten intro"]
        ).exit_code
        == 0
    )
    third = _json_line(
        runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    )
    assert third["unsteered_redraft"] is False  # the fix verdict is steering


def test_seam_commit_never_sweeps_unrelated_files(repo):
    stray = repo / "WIP-notes.md"
    stray.write_text("operator scratch\n", encoding="utf-8")
    staged = repo / "staged-elsewhere.md"
    staged.write_text("pre-staged operator work\n", encoding="utf-8")
    _git(repo, "add", "staged-elsewhere.md")
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    initial_commit = _git(repo, "rev-list", "--max-parents=0", "HEAD").splitlines()[-1]
    all_committed = _git(
        repo, "log", "--name-only", "--format=", f"{initial_commit}..HEAD"
    ) or _git(repo, "log", "--name-only", "--format=")
    assert "WIP-notes.md" not in all_committed
    assert "staged-elsewhere.md" not in all_committed
    # The operator's index entry survives the seam commits untouched.
    assert "staged-elsewhere.md" in _git(repo, "diff", "--cached", "--name-only")


def test_dogen_gitignore_seeded_and_committed(repo):
    _declare(repo)
    ignore = repo / ".dogen" / ".gitignore"
    assert ignore.read_text(encoding="utf-8") == "staging/\n"
    files = _git(repo, "log", "-1", "--grep", "Dogen-Phase: declared", "--name-only")
    assert ".dogen/.gitignore" in files
    # Effect: staging scratch is invisible to a blanket git add.
    scratch = repo / ".dogen" / "staging" / "u" / "handoff.md"
    scratch.parent.mkdir(parents=True)
    scratch.write_text("scratch\n", encoding="utf-8")
    _git(repo, "add", "-A")
    assert ".dogen/staging" not in _git(repo, "diff", "--cached", "--name-only")


def test_untracked_source_stamps_empty_commit(repo):
    tracked = repo / "README.md"  # committed by the fixture
    untracked = repo / "overlay.md"
    untracked.write_text("copied in, never committed\n", encoding="utf-8")
    _declare(repo, "--source", "README.md", "--source", "overlay.md")
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    by_path = {s.path: s.commit for s in unit.sources}
    assert by_path["README.md"] == _git(repo, "rev-parse", "HEAD^")  # pre-declare HEAD
    assert by_path["overlay.md"] == ""  # honest: no false pin
    assert tracked.is_file()


def test_driver_origins_deduped_and_honestly_stamped(repo):
    class _Fabricating(MockDraftingProvider):
        async def draft_unit(self, **kwargs):  # noqa: ANN003
            result = await super().draft_unit(**kwargs)
            return result.model_copy(
                update={
                    "context_origins": ["README.md", "README.md", "ghost.md"],
                }
            )

    store = FilesystemPlanningStore()
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    request = compose.build_draft_request(
        "u",
        root=repo,
        store=store,
        provider=_Fabricating(),
        provider_name="mock",
        repo=compose.make_repo_seam(enabled=True),
    )
    asyncio.run(orchestrator.draft(request))
    generation = store.read_provenance("u", root=repo).generations[-1]
    paths = [o.path for o in generation.context_origins]
    assert paths == ["README.md", "ghost.md"]  # duplicate collapsed
    stamps = {o.path: o.commit for o in generation.context_origins}
    assert stamps["README.md"] == generation.source_commit  # tracked -> pinned
    assert stamps["ghost.md"] == ""  # untracked -> honest unknown


def test_unit_show_latest_projects_one_generation(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
        ["review", "u", "--verdict", "fix", "--note", "again"],
        ["draft", "u", "--provider", "mock"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    full = _json_line(runner.invoke(app, ["unit", "show", "u", "--json"]))
    assert len(full["generations"]) == 2
    assert full["generations_count"] == 2
    lean = _json_line(runner.invoke(app, ["unit", "show", "u", "--json", "--latest"]))
    assert len(lean["generations"]) == 1
    assert lean["generations_count"] == 2
    assert lean["generations"][0] == full["generations"][-1]


def test_status_routes_back_to_draft_after_fix_verdict(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
        ["review", "u", "--verdict", "fix", "--note", "not yet"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["next"] == "dogen draft u  # apply the recorded fix"
    assert board[0]["next_id"] == "draft"


# --- v1.2: routing tokens, re-sign fold, git visibility, forensic bodies ------


def test_review_json_carries_next_id_token(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    fix = _json_line(
        runner.invoke(
            app, ["review", "u", "--verdict", "fix", "--note", "wrong", "--json"]
        )
    )
    assert fix["next_id"] == "draft"
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    accept = _json_line(
        runner.invoke(
            app, ["review", "u", "--verdict", "accept", "--note", "ok", "--json"]
        )
    )
    assert accept["next_id"] == "publish"


def test_status_next_id_tracks_the_lifecycle(repo):
    _declare(repo)
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["next_id"] == "sign_off"
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["next_id"] == "draft"
    # A post-signoff plan edit flips the token to re_sign, and the human
    # string now names the flag that actually exists on signoff (R4: the
    # round-2 --re-sign/--force contradiction).
    assert runner.invoke(app, ["unit", "edit", "u", "--title", "New"]).exit_code == 0
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["next_id"] == "re_sign"
    assert "--re-sign" in board[0]["next"]
    assert "--force" not in board[0]["next"]


def test_edit_re_sign_folds_re_approval_into_one_act(repo):
    _declare(repo)
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    store = FilesystemPlanningStore()
    first = store.read_provenance("u", root=repo).signoff
    assert first is not None
    result = runner.invoke(
        app, ["unit", "edit", "u", "--title", "Amended", "--re-sign", "--json"]
    )
    assert result.exit_code == 0, result.output
    provenance = store.read_provenance("u", root=repo)
    # Fresh act: the hash matches the amended plan; no stale flag remains.
    text = store.read_unit_text("u", root=repo)
    assert provenance.signoff is not None
    assert (
        provenance.signoff.plan_hash == hashlib.sha256(text.encode("utf-8")).hexdigest()
    )
    board = _json_line(runner.invoke(app, ["status", "--json"]))
    assert board[0]["stale_plan"] is False
    # The superseded act is archived, not lost (R4: opencode's overwrite).
    assert [s.plan_hash for s in provenance.signoff_history] == [first.plan_hash]
    # The edited commit body records the re-sign for log-only forensics.
    body = _git(repo, "log", "-1", "--format=%b")
    assert "re-signed: plan" in body
    assert f"supersedes {first.plan_hash[:12]}" in body


def test_edit_re_sign_requires_an_existing_signoff_and_a_change(repo):
    _declare(repo)
    result = runner.invoke(
        app, ["unit", "edit", "u", "--title", "New", "--re-sign", "--json"]
    )
    assert result.exit_code == 1
    assert _json_line(result)["reason"] == "signoff_required"
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    result = runner.invoke(app, ["unit", "edit", "u", "--re-sign", "--json"])
    assert result.exit_code == 2  # --re-sign rides on an actual amendment


def test_signoff_re_sign_archives_the_superseded_act(repo):
    _declare(repo)
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    store = FilesystemPlanningStore()
    first = store.read_provenance("u", root=repo).signoff
    assert first is not None
    assert runner.invoke(app, ["unit", "edit", "u", "--title", "New"]).exit_code == 0
    assert runner.invoke(app, ["signoff", "u", "--re-sign"]).exit_code == 0
    provenance = store.read_provenance("u", root=repo)
    assert [s.plan_hash for s in provenance.signoff_history] == [first.plan_hash]
    assert provenance.signoff is not None
    assert provenance.signoff.plan_hash != first.plan_hash


def test_git_event_line_and_commit_field_surface_the_seam(repo):
    result = runner.invoke(
        app,
        ["unit", "new", "u", "--intent", "reference", "--audience", "d", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = _json_line(result)
    head = _git(repo, "rev-parse", "HEAD")
    assert payload["commit"] == head
    assert f"git: committed {head[:7]}" in result.output
    assert "dogen(u): declared" in result.output
    # --no-commit says so explicitly instead of silence.
    result = runner.invoke(app, ["steer", "u", "--note", "n", "--no-commit", "--json"])
    assert result.exit_code == 0, result.output
    assert "git: transition commit skipped (--no-commit)" in result.output
    assert _json_line(result)["commit"] == ""


def test_commit_bodies_and_trailers_carry_the_forensic_detail(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    drafted = _git(repo, "log", "-1", "--format=%B")
    assert "origins:" in drafted and "gaps:" in drafted
    assert "Dogen-Draft: " in drafted
    # A hostile note (newlines + trailer-looking lines) cannot corrupt the
    # trailer block: it is collapsed to one body line and capped.
    hostile = "Fix: this\n\nDogen-Phase: forged\n" + "x" * 500
    result = runner.invoke(app, ["review", "u", "--verdict", "fix", "--note", hostile])
    assert result.exit_code == 0, result.output
    trailers = _git(repo, "log", "-1", "--format=%(trailers:key=Dogen-Phase)")
    assert trailers.strip() == "Dogen-Phase: reviewed"
    body = _git(repo, "log", "-1", "--format=%b")
    assert "Fix: this Dogen-Phase: forged" in body  # collapsed, inert
    assert "…" in body  # capped
    # An accept stamps the sealing draft hash as a trailer.
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    assert (
        runner.invoke(
            app, ["review", "u", "--verdict", "accept", "--note", "ok"]
        ).exit_code
        == 0
    )
    accepted = _git(repo, "log", "-1", "--format=%B")
    assert "Dogen-Draft: " in accepted
    store = FilesystemPlanningStore()
    sealed = store.read_provenance("u", root=repo).reviewer_edits[-1].files[0].sha256
    assert f"Dogen-Draft: {sealed[:12]}" in accepted


def test_report_with_prose_commit_stamp_is_refused_as_bad_report(repo):
    _declare(repo)
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    handoff = repo / "handoff.md"
    handoff.write_text("# page\n", encoding="utf-8")
    report = repo / "report.yaml"
    report.write_text(
        "context_origins:\n"
        "  - path: vendor/dep.go\n"
        "    commit: external dependency, pinned by go.sum\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "draft",
            "u",
            "--provider",
            "host-harness",
            "--draft-file",
            str(handoff),
            "--report",
            str(report),
            "--json",
        ],
    )
    assert result.exit_code == 2
    assert _json_line(result)["reason"] == "bad_report"
    # No generation was recorded and no draft landed.
    store = FilesystemPlanningStore()
    assert store.read_provenance("u", root=repo).generations == []


def test_report_note_and_gaps_note_flow_into_the_generation(repo):
    _declare(repo)
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    handoff = repo / "handoff.md"
    handoff.write_text("# page\n", encoding="utf-8")
    report = repo / "report.yaml"
    report.write_text(
        "context_origins:\n"
        "  - path: vendor/dep.go\n"
        "    commit: ''\n"
        "    note: external dependency, pinned by go.sum at v3.0.1\n"
        "gaps: []\n"
        "gaps_note: every claim verified at its origin in this small surface\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "draft",
            "u",
            "--provider",
            "host-harness",
            "--draft-file",
            str(handoff),
            "--report",
            str(report),
        ],
    )
    assert result.exit_code == 0, result.output
    generation = (
        FilesystemPlanningStore().read_provenance("u", root=repo).generations[-1]
    )
    assert generation.context_origins[0].commit == ""
    assert "go.sum" in generation.context_origins[0].note
    assert generation.gaps == []
    assert "verified at its origin" in generation.gaps_note


# --- v1.2: rst first-class (the target extension IS the format) --------------


def test_extensionless_target_is_refused_eagerly(repo):
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
            "reference/workshop-definition",
            "--json",
        ],
    )
    assert result.exit_code == 2
    assert _json_line(result)["reason"] == "bad_target"
    assert not (repo / ".dogen" / "units" / "u").exists()  # zero mutation
    # Same gate on the edit path.
    _declare(repo)
    result = runner.invoke(
        app, ["unit", "edit", "u", "--target", "reference/u.txt", "--json"]
    )
    assert result.exit_code == 2
    assert _json_line(result)["reason"] == "bad_target"
    store = FilesystemPlanningStore()
    assert store.load_unit("u", root=repo).sphinx_target == "u.md"  # unchanged


def test_scaffold_default_follows_the_docs_trees_dominant_format(repo):
    docs = repo / "docs"
    (docs / "reference").mkdir(parents=True)
    (docs / "index.rst").write_text("Index\n=====\n", encoding="utf-8")
    (docs / "reference" / "a.rst").write_text("A\n=\n", encoding="utf-8")
    (docs / "_build").mkdir()
    for i in range(5):  # build artifacts must not vote
        (docs / "_build" / f"junk{i}.md").write_text("x\n", encoding="utf-8")
    _declare(repo)
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.sphinx_target == "u.rst"
    assert unit.format == "rst"


def test_unit_mv_preserves_the_rst_suffix(repo):
    _declare(repo, "--target", "reference/u.rst")
    assert runner.invoke(app, ["unit", "mv", "u", "w"]).exit_code == 0
    unit = FilesystemPlanningStore().load_unit("w", root=repo)
    assert unit.sphinx_target == "reference/w.rst"


def test_unit_show_reports_the_format(repo):
    _declare(repo, "--target", "reference/definition-files/workshop-definition.rst")
    shown = _json_line(runner.invoke(app, ["unit", "show", "u", "--json"]))
    assert shown["format"] == "rst"
    plain = runner.invoke(app, ["unit", "show", "u"])
    assert "format:    rst" in plain.output


def test_mock_driver_authors_valid_rst_for_an_rst_target(repo):
    _declare(repo, "--target", "reference/u.rst")
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    text = (repo / "docs" / "reference" / "u.rst").read_text(encoding="utf-8")
    assert ".. note::" in text
    assert "```" not in text  # no MyST fences in an rst page
    title, underline = text.splitlines()[0:2]
    assert underline == "=" * len(title)
    # The md sibling keeps the MyST shape.
    result = runner.invoke(
        app,
        [
            "unit",
            "new",
            "m",
            "--intent",
            "reference",
            "--audience",
            "d",
            "--target",
            "reference/m.md",
        ],
    )
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["signoff", "m"]).exit_code == 0
    assert runner.invoke(app, ["draft", "m", "--provider", "mock"]).exit_code == 0
    md_text = (repo / "docs" / "reference" / "m.md").read_text(encoding="utf-8")
    assert "```{note}" in md_text


# --- v1.2: multi-file units (horizontal fixes / restructures) ----------------


def _stage_handoff(repo, files: dict) -> Path:
    base = repo / ".dogen" / "staging" / "u" / "handoff"
    for rel, text in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return base


def _declare_span(repo):
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


def test_multi_file_unit_declares_and_shows_the_set(repo):
    _declare_span(repo)
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.targets == ["guide/a.md", "guide/b.md", "reference/c.rst"]
    shown = _json_line(runner.invoke(app, ["unit", "show", "u", "--json"]))
    assert shown["unit"]["extra_targets"] == ["guide/b.md", "reference/c.rst"]


def test_cross_unit_target_claim_is_refused(repo):
    _declare_span(repo)
    result = runner.invoke(
        app,
        [
            "unit",
            "new",
            "w",
            "--intent",
            "reference",
            "--audience",
            "d",
            "--target",
            "guide/b.md",
            "--json",
        ],
    )
    assert result.exit_code == 1
    assert _json_line(result)["reason"] == "target_claimed"
    assert not (repo / ".dogen" / "units" / "w").exists()
    # The edit path refuses the same way.
    result = runner.invoke(
        app,
        [
            "unit",
            "new",
            "w",
            "--intent",
            "reference",
            "--audience",
            "d",
            "--target",
            "guide/w.md",
        ],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        app, ["unit", "edit", "w", "--also-target", "reference/c.rst", "--json"]
    )
    assert result.exit_code == 1
    assert _json_line(result)["reason"] == "target_claimed"


def test_draft_dir_maps_pages_onto_the_target_set(repo):
    _declare_span(repo)
    base = _stage_handoff(
        repo,
        {
            "guide/a.md": "# A\n\nprimary\n",
            "guide/b.md": "# B\n\nextra one\n",
            "reference/c.rst": "C\n=\n\nextra two\n",
        },
    )
    result = runner.invoke(
        app,
        [
            "draft",
            "u",
            "--provider",
            "host-harness",
            "--draft-dir",
            str(base),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    for rel, marker in (
        ("guide/a.md", "primary"),
        ("guide/b.md", "extra one"),
        ("reference/c.rst", "extra two"),
    ):
        assert marker in (repo / "docs" / rel).read_text(encoding="utf-8")
    # The drafted seam commit carries every written page.
    files = _git(
        repo,
        "log",
        "-1",
        "--grep",
        "Dogen-Phase: drafted",
        "--name-only",
        "--format=",
    ).splitlines()
    for rel in ("docs/guide/a.md", "docs/guide/b.md", "docs/reference/c.rst"):
        assert rel in files
    # The generation records per-page digests, primary first.
    generation = FilesystemPlanningStore().read_provenance("u", root=repo)
    gen = generation.generations[-1]
    assert [f.path for f in gen.files] == [
        "docs/guide/a.md",
        "docs/guide/b.md",
        "docs/reference/c.rst",
    ]
    a_text = (repo / "docs" / "guide" / "a.md").read_text(encoding="utf-8")
    assert gen.files[0].sha256 == hashlib.sha256(a_text.encode("utf-8")).hexdigest()


def test_draft_dir_refuses_incomplete_and_undeclared_handoffs(repo):
    _declare_span(repo)
    base = _stage_handoff(repo, {"guide/a.md": "# A\n"})  # missing b + c
    result = runner.invoke(
        app,
        [
            "draft",
            "u",
            "--provider",
            "host-harness",
            "--draft-dir",
            str(base),
            "--json",
        ],
    )
    assert result.exit_code == 1
    assert _json_line(result)["reason"] == "handoff_incomplete"
    _stage_handoff(
        repo,
        {"guide/b.md": "# B\n", "reference/c.rst": "C\n=\n", "rogue.md": "# R\n"},
    )
    result = runner.invoke(
        app,
        [
            "draft",
            "u",
            "--provider",
            "host-harness",
            "--draft-dir",
            str(base),
            "--json",
        ],
    )
    assert result.exit_code == 1
    assert _json_line(result)["reason"] == "undeclared_target"
    assert FilesystemPlanningStore().read_provenance("u", root=repo).generations == []


def test_multi_file_accept_seals_every_page(repo):
    _declare_span(repo)
    base = _stage_handoff(
        repo,
        {
            "guide/a.md": "# A\n",
            "guide/b.md": "# B\n",
            "reference/c.rst": "C\n=\n",
        },
    )
    args = ["draft", "u", "--provider", "host-harness", "--draft-dir", str(base)]
    assert runner.invoke(app, args).exit_code == 0
    assert (
        runner.invoke(
            app, ["review", "u", "--verdict", "accept", "--note", "ok"]
        ).exit_code
        == 0
    )
    store = FilesystemPlanningStore()
    sealed = store.read_provenance("u", root=repo).reviewer_edits[-1]
    assert [f.path for f in sealed.files] == [
        "docs/guide/a.md",
        "docs/guide/b.md",
        "docs/reference/c.rst",
    ]
    # A byte-identical duplicate accept is refused on the full digest list.
    result = runner.invoke(
        app, ["review", "u", "--verdict", "accept", "--note", "ok", "--json"]
    )
    assert result.exit_code == 1
    assert _json_line(result)["reason"] == "already_accepted"
    # Changing ONLY an extra page legitimately re-arms the accept.
    extra = repo / "docs" / "guide" / "b.md"
    extra.write_text(extra.read_text(encoding="utf-8") + "\npolish\n", "utf-8")
    result = runner.invoke(
        app, ["review", "u", "--verdict", "accept", "--note", "re-sealed"]
    )
    assert result.exit_code == 0, result.output


def test_driver_provider_refuses_a_multi_file_unit(repo):
    _declare_span(repo)
    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 2
    assert _json_line(result)["reason"] == "multi_target_unsupported"


def test_drop_target_descopes_without_touching_the_page(repo):
    _declare_span(repo)
    base = _stage_handoff(
        repo,
        {
            "guide/a.md": "# A\n",
            "guide/b.md": "# B\n",
            "reference/c.rst": "C\n=\n",
        },
    )
    args = ["draft", "u", "--provider", "host-harness", "--draft-dir", str(base)]
    assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(
        app, ["unit", "edit", "u", "--drop-target", "reference/c.rst"]
    )
    assert result.exit_code == 0, result.output
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.extra_targets == ["guide/b.md"]
    assert (repo / "docs" / "reference" / "c.rst").is_file()  # page untouched
    # Dropping the primary is refused.
    result = runner.invoke(app, ["unit", "edit", "u", "--drop-target", "guide/a.md"])
    assert result.exit_code == 2


def test_unit_rm_removes_the_whole_page_set(repo):
    _declare_span(repo)
    base = _stage_handoff(
        repo,
        {
            "guide/a.md": "# A\n",
            "guide/b.md": "# B\n",
            "reference/c.rst": "C\n=\n",
        },
    )
    args = ["draft", "u", "--provider", "host-harness", "--draft-dir", str(base)]
    assert runner.invoke(app, args).exit_code == 0
    assert runner.invoke(app, ["unit", "rm", "u", "--force"]).exit_code == 0
    for rel in ("guide/a.md", "guide/b.md", "reference/c.rst"):
        assert not (repo / "docs" / rel).exists()


def test_find_unit_by_draft_resolves_extras(repo):
    _declare_span(repo)
    shown = _json_line(
        runner.invoke(app, ["unit", "show", "--by-draft", "docs/guide/b.md", "--json"])
    )
    assert shown["unit"]["unit_id"] == "u"


def test_unit_rm_of_an_undrafted_unit_still_records_the_removal(repo):
    """An unmatched docs pathspec must not silently skip the removal commit.

    Caught by the v1.2 git-event line: `unit rm` on an undrafted unit put the
    never-written docs target in the pathspec, `git add` fataled, and the
    tolerant seam degraded the whole removal commit into a warning.
    """
    _declare(repo)  # declared, never drafted — docs/u.md does not exist
    result = runner.invoke(app, ["unit", "rm", "u", "--force", "--json"])
    assert result.exit_code == 0, result.output
    payload = _json_line(result)
    assert payload["commit"]  # the removal transition commit landed
    assert "git: committed" in result.output
    subject = _git(repo, "log", "-1", "--format=%s")
    assert subject.startswith("dogen(u): removed")


# --- v1.3: docs/ normalization, verdict-aware next, orphan steering, model ----


def test_docs_prefix_stripped_at_declare_with_notice(repo):
    """A leading docs/ on --target is normalized away, not doubled (M1, R1)."""
    result = _declare(repo, "--target", "docs/reference/x.rst")
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.sphinx_target == "reference/x.rst"
    assert "note: target normalized (leading docs/ stripped)" in result.output
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    # Written at the canonical slot — never docs/docs/.
    assert (repo / "docs" / "reference" / "x.rst").is_file()
    assert not (repo / "docs" / "docs").exists()


def test_docs_double_prefix_strips_only_one_segment(repo):
    _declare(repo, "--target", "docs/docs/x.rst")
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.sphinx_target == "docs/x.rst"  # exactly one segment removed


def test_unprefixed_target_is_unchanged_and_silent(repo):
    result = _declare(repo, "--target", "reference/x.rst")
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.sphinx_target == "reference/x.rst"
    assert "target normalized" not in result.output


def test_docs_prefix_stripped_at_edit_target_and_also_target(repo):
    _declare(repo, "--target", "reference/a.rst")
    result = runner.invoke(
        app,
        [
            "unit",
            "edit",
            "u",
            "--target",
            "docs/reference/b.rst",
            "--also-target",
            "docs/reference/c.rst",
        ],
    )
    assert result.exit_code == 0, result.output
    unit = FilesystemPlanningStore().load_unit("u", root=repo)
    assert unit.sphinx_target == "reference/b.rst"
    assert unit.extra_targets == ["reference/c.rst"]
    assert result.output.count("target normalized") == 2


def test_redraft_verdict_keeps_the_redraft_wording(repo):
    """A redraft verdict still says "re-draft"; only fix diverges (M2)."""
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    out = _json_line(
        runner.invoke(
            app,
            ["review", "u", "--verdict", "redraft", "--note", "start over", "--json"],
        )
    )
    assert out["next"] == "dogen draft u  # re-draft per the recorded steering"
    assert out["next_id"] == "draft"


def test_accept_after_orphan_fix_flags_unapplied_steering(repo):
    """Fix, then accept with no draft between: the fix note is orphaned (M3, R5)."""
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
        ["review", "u", "--verdict", "fix", "--note", "fix me"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(
        app, ["review", "u", "--verdict", "accept", "--note", "ship", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert _json_line(result)["unapplied_steering"] is True
    assert "unapplied" in result.output.lower()


def test_accept_after_the_fix_was_drafted_is_clean(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
        ["draft", "u", "--provider", "mock"],
        ["review", "u", "--verdict", "fix", "--note", "fix me"],
        ["draft", "u", "--provider", "mock"],  # the fix is applied here
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(
        app, ["review", "u", "--verdict", "accept", "--note", "ship", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert _json_line(result)["unapplied_steering"] is False


def _passenger_draft(repo, *extra):
    handoff = repo / "handoff.md"
    handoff.write_text("# page\n\nbody\n", encoding="utf-8")
    report = repo / "report.yaml"
    report.write_text(
        "context_origins: []\ntools_used: [Read]\n"
        "gaps: []\ngaps_note: nothing left unverified\n",
        encoding="utf-8",
    )
    return runner.invoke(
        app,
        [
            "draft",
            "u",
            "--provider",
            "host-harness",
            "--draft-file",
            str(handoff),
            "--report",
            str(report),
            "--json",
            *extra,
        ],
    )


def test_passenger_draft_without_model_flags_unrecorded(repo):
    """A passenger draft with no --model records empty and is flagged (M4, R4)."""
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = _passenger_draft(repo)
    assert result.exit_code == 0, result.output
    assert _json_line(result)["model_unrecorded"] is True
    assert "no model recorded" in result.output


def test_passenger_draft_with_model_is_not_flagged(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = _passenger_draft(repo, "--model", "claude-sonnet-4.6")
    assert result.exit_code == 0, result.output
    assert _json_line(result)["model_unrecorded"] is False


def test_mock_draft_records_a_model(repo):
    for args in (
        ["unit", "new", "u", "--intent", "reference", "--audience", "d"],
        ["signoff", "u"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 0, result.output
    assert _json_line(result)["model_unrecorded"] is False
