"""CLI contract: the coarse exit-code x stable JSON ``reason`` matrix (SC4/D-10).

Drives the four verbs through Typer's ``CliRunner`` and locks the machine seam
the Phase-4 skills consume: every failure maps to a coarse exit code
(``0`` ok / ``1`` domain refusal / ``2`` bad input or not-found) AND a stable
``--json`` ``reason`` code, and a successful ``draft`` names the provider that ran
(D-09). Fully offline — ``--provider mock`` / seeded-on-disk steering, no token,
no network (D-17). Signoff is seeded directly through the store (not the ``steer``
verb) so the draft-path cases need no git-identity round-trip; the ``repo`` fixture
still configures a local identity for the ``review`` path (which captures a
reviewer).
"""

import ast
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.cli.main import app
from dogen.core.models import (
    Intent,
    ProgressState,
    Provenance,
    Signoff,
)

runner = CliRunner()


def _payload(result) -> dict:
    """Parse the single JSON object line from a CLI result.

    ``configure_observability`` routes Logfire's console span to stderr (so real
    stdout stays clean JSON), but ``CliRunner`` mixes stderr back into
    ``result.output``; scan for the one JSON line so the assertion is robust to
    that interleaving.
    """
    for line in result.output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON object in output: {result.output!r}")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tmp git repo with a configured identity, used as the working dir.

    ``git config user.*`` resolves the reviewer/author deterministically with no
    network; ``chdir`` makes the CLI (which uses ``Path.cwd()``) write under the
    tmp root. ``DOGEN_PROVIDER`` is cleared so an ambient CI pin never overrides
    the explicit ``--provider`` values under test.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Ada Lovelace"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "ada@example.com"],
        check=True,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOGEN_PROVIDER", raising=False)
    return tmp_path


def _declare_unit(root: Path) -> FilesystemPlanningStore:
    """Scaffold an un-steered unit ``u`` and return the store."""
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=root, intent=Intent.reference, audience="devs")
    return store


def _seed_steering(store: FilesystemPlanningStore, root: Path) -> None:
    """Record a steering act for unit ``u`` directly on disk (no git round-trip)."""
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Ada",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
        ),
        root=root,
    )


def test_steered_draft_mock_json_exits_ok_names_provider(repo):
    # A steered mock draft exits 0; the --json object names the provider that ran
    # (D-09) and carries a null reason with the written draft path + progress.
    store = _declare_unit(repo)
    _seed_steering(store, repo)

    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["provider"] == "mock"
    assert payload["reason"] is None
    assert payload["draft_path"] == str(repo / "docs" / "u.md")
    assert payload["progress"] == ProgressState.drafted.value


def test_steered_draft_plain_line_names_provider(repo):
    # D-09: the plain-text success line names the provider that ran, so an
    # auto-selected driver-vs-passenger run is never invisible.
    store = _declare_unit(repo)
    _seed_steering(store, repo)

    result = runner.invoke(app, ["draft", "u", "--provider", "mock"])
    assert result.exit_code == 0, result.output
    assert "Drafted u via mock ->" in result.output


def test_unsteered_draft_exits_domain_refusal_signoff_required(repo):
    # The HITL gate: an un-steered draft is a domain refusal — exit 1 with the
    # stable reason="signoff_required" (D-10), and no draft is written.
    _declare_unit(repo)

    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "signoff_required"
    assert not (repo / "docs" / "u.md").exists()


def test_missing_unit_draft_exits_bad_input(repo):
    # A not-found unit is bad-input — exit 2 with an existence reason in the
    # stable vocabulary (D-10). No unit was scaffolded.
    result = runner.invoke(app, ["draft", "ghost", "--provider", "mock", "--json"])
    assert result.exit_code == 2, result.output
    assert _payload(result)["reason"] in {"unit_exists", "not_drafted"}


def test_unit_new_clobber_exits_domain_refusal_unit_exists(repo):
    # A clobber without --force is a domain refusal — exit 1, reason="unit_exists"
    # (the unit already exists).
    runner.invoke(app, ["unit", "new", "u"])
    result = runner.invoke(app, ["unit", "new", "u", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "unit_exists"


def test_review_undrafted_exits_not_drafted(repo):
    # A steered-but-never-drafted unit has no progress.yaml, so review is
    # bad-input — exit 2, reason="not_drafted" (D-10).
    store = _declare_unit(repo)
    _seed_steering(store, repo)

    result = runner.invoke(
        app, ["review", "u", "--note", "premature", "--verdict", "fix", "--json"]
    )
    assert result.exit_code == 2, result.output
    assert _payload(result)["reason"] == "not_drafted"


def test_full_verb_matrix_is_exposed():
    # SC4: the four verbs are wired (unit / steer / draft / review) so the skills
    # shell has the full seam surface.
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    for verb in ("unit", "steer", "draft", "review"):
        assert verb in result.output


def _write_raw_provenance(root: Path, unit_id: str, body: str) -> None:
    """Write a raw provenance.yaml directly into a scaffolded unit's dir."""
    prov = root / ".dogen" / "units" / unit_id / "provenance.yaml"
    prov.write_text(body, encoding="utf-8")


def test_unit_show_future_schema_version_exits_schema_unsupported(repo):
    # D-08: a sidecar declaring schema_version 99 refuses at load — `unit show`
    # exits non-zero with the stable reason "schema_unsupported" (the unit dir
    # genuinely exists, proving this is not a not-found conflation).
    _declare_unit(repo)
    _write_raw_provenance(repo, "u", "schema_version: 99\nunit_id: u\n")

    result = runner.invoke(app, ["unit", "show", "u", "--json"])
    assert result.exit_code != 0, result.output
    assert _payload(result)["reason"] == "schema_unsupported"

    # The plain-mode message names found (99) vs the supported version.
    plain = runner.invoke(app, ["unit", "show", "u"])
    assert plain.exit_code != 0, plain.output
    assert "99" in plain.output


def test_unit_show_corrupt_provenance_exits_provenance_invalid(repo):
    # D-09: a present-but-invalid provenance (a generation missing required
    # keys) refuses with "provenance_invalid" — never "unit_not_found".
    _declare_unit(repo)
    _write_raw_provenance(
        repo, "u", "schema_version: 2\nunit_id: u\ngenerations:\n  - model: m\n"
    )

    result = runner.invoke(app, ["unit", "show", "u", "--json"])
    assert result.exit_code != 0, result.output
    reason = _payload(result)["reason"]
    assert reason == "provenance_invalid"
    assert reason != "unit_not_found"


def test_unit_show_missing_unit_still_exits_unit_not_found(repo):
    # No regression: a genuinely missing unit still yields "unit_not_found".
    result = runner.invoke(app, ["unit", "show", "ghost", "--json"])
    assert result.exit_code != 0, result.output
    assert _payload(result)["reason"] == "unit_not_found"


def test_unit_show_json_carries_additive_targets_array(repo):
    # D-06: a multi-file unit's --json payload gains a top-level targets[]
    # (docs paths, primary first) and changes no pre-existing key.
    store = FilesystemPlanningStore()
    store.scaffold_unit(
        "u",
        root=repo,
        intent=Intent.reference,
        audience="devs",
        sphinx_target="guide.md",
        extra_targets=["appendix.md"],
    )

    result = runner.invoke(app, ["unit", "show", "u", "--json"])
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["targets"] == ["docs/guide.md", "docs/appendix.md"]
    for key in (
        "unit",
        "format",
        "progress",
        "signoff",
        "steering",
        "generations",
        "generations_count",
        "reviewer_edits",
    ):
        assert key in payload, key


def test_unit_show_plain_lists_every_target_primary_first(repo):
    # D-04/D-05: plain `unit show` prints a "targets:" count line ("2 page(s)")
    # then one indented docs path per target, with "(primary)" on the primary
    # entry only.
    store = FilesystemPlanningStore()
    store.scaffold_unit(
        "u",
        root=repo,
        intent=Intent.reference,
        audience="devs",
        sphinx_target="guide.md",
        extra_targets=["appendix.md"],
    )

    result = runner.invoke(app, ["unit", "show", "u"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    targets_line = next(line for line in lines if line.startswith("targets:"))
    assert "2 page(s)" in targets_line
    primary = next(line for line in lines if "docs/guide.md" in line)
    extra = next(line for line in lines if "docs/appendix.md" in line)
    assert "(primary)" in primary
    assert "(primary)" not in extra
    assert primary.strip().startswith("-")
    # Old single-line surface is gone.
    assert "target:    docs/guide.md" not in result.output


def test_unit_show_single_file_unit_renders_count_one(repo):
    # A single-file unit reads identically: "1 page(s)" with one "(primary)".
    store = FilesystemPlanningStore()
    store.scaffold_unit(
        "u",
        root=repo,
        intent=Intent.reference,
        audience="devs",
        sphinx_target="solo.md",
    )

    result = runner.invoke(app, ["unit", "show", "u"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    targets_line = next(line for line in lines if line.startswith("targets:"))
    assert "1 page(s)" in targets_line
    assert sum("(primary)" in line for line in lines) == 1


def test_cli_module_imports_no_sdk():
    # The CLI classifies backend errors by type-name; it must never import the
    # Copilot SDK/adapter (the mock/host-harness path stays SDK-free). Parse the
    # module's own import statements (not its source text, which self-matches on
    # the banned tokens).
    tree = ast.parse(Path("src/dogen/cli/main.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "copilot" not in imported
    assert "github_copilot_sdk" not in imported
