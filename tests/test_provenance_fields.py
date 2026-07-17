"""Provenance-truth tests for the provider-reported ``sdk``/``mode`` fields.

Phase 03 Plan 01 (D-14/D-12): the recorded ``sdk`` and ``mode`` must be
*provider-reported*, not unconditional module constants. These tests lock the
honest defaults and the mock's driver identity so the SDK-free mock can never
again fabricate ``github-copilot-sdk==1.0.2`` / ``local`` provenance (T-03-03).
"""

import importlib
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.mock_provider import MockDraftingProvider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.cli.main import app
from dogen.core.models import (
    SCHEMA_VERSION,
    DraftResult,
    Generation,
    Intent,
    Provenance,
    ReviewerEdit,
    Signoff,
    SourceRef,
    Step,
)


def _generation(**overrides: object) -> Generation:
    fields: dict = {
        "model": "m",
        "model_version": "v",
        "effort": None,
        "tooling_version": "0.0.0",
        "sdk": "s",
        "run_id": "r",
        "at": "2026-01-01T00:00:00Z",
        "action": "draft",
        "files": [{"path": "docs/a.md", "sha256": "ab12"}],
    }
    fields.update(overrides)
    return Generation.model_validate(fields)


def test_draft_result_defaults_sdk_and_mode_empty() -> None:
    # A bare DraftResult carries honest empty defaults — no SDK id and no run
    # mode are asserted unless a provider reports them (D-14/D-12).
    result = DraftResult(text="body", model="m", output_tokens=1, run_id="")
    assert result.sdk == ""
    assert result.mode == ""


@pytest.mark.asyncio
async def test_mock_provider_reports_driver_mode_and_empty_sdk() -> None:
    # The deterministic mock is an in-process *driver* double (D-12): it reports
    # mode="driver" and, being SDK-free, sdk="" — never the copilot SDK id.
    steering = Signoff(
        author="ta",
        at="2026-07-02T00:00:00Z",
        intent=Intent.reference,
        audience="devs",
    )
    result = await MockDraftingProvider().draft_unit(
        intent=Intent.reference,
        audience="devs",
        signoff=steering,
        sources=[SourceRef(path="README.md")],
    )
    assert result.sdk == ""
    assert result.mode == "driver"


def test_provenance_schema_version_is_current() -> None:
    # v1: the steering split (signoff + stream) is an explicit, versioned
    # migration — records now stamp the current schema generation.
    assert Provenance(unit_id="u").schema_version == SCHEMA_VERSION


# --- Phase 5: schema v2 field disposition (PROV-01/PROV-02) --------------------


def test_deleted_legacy_fields_absent_from_v2_models() -> None:
    assert "draft_path" not in Generation.model_fields
    assert "draft_sha256" not in Generation.model_fields
    assert "draft_sha256" not in ReviewerEdit.model_fields
    assert "verification" not in Provenance.model_fields
    # The verification block classes are gone — `from dogen.core.models import
    # Verification` would raise ImportError (asserted here as absence).
    models = importlib.import_module("dogen.core.models")
    assert not hasattr(models, "Verification")
    assert not hasattr(models, "VerificationStep")


def test_generation_omits_empty_effort_model_version_sdk_no_over_drop() -> None:
    gen = _generation(effort=None, model_version="", sdk="", gaps_note="")
    dump = gen.model_dump(mode="json")
    assert "effort" not in dump
    assert "model_version" not in dump
    assert "sdk" not in dump
    # No over-drop: an unrelated empty field stays present.
    assert "gaps_note" in dump
    assert "files" in dump


def test_generation_retains_non_empty_omit_fields() -> None:
    gen = _generation(effort="medium", model_version="1.2", sdk="copilot")
    dump = gen.model_dump(mode="json")
    assert dump["effort"] == "medium"
    assert dump["model_version"] == "1.2"
    assert dump["sdk"] == "copilot"


def test_generation_model_origin_defaults_empty() -> None:
    assert _generation().model_origin == ""


# --- Phase 12 Plan 03: compose-root steps/evidence readers + status surface ---
# The `--steps-file`/`--evidence-file` payloads are validated at the compose root
# (V5); only typed values cross into core/. `unit show`/`status` gain additive
# step-status keys guarded on `provenance.steps` presence so step-free units stay
# byte-identical (EVID-06).


runner = CliRunner()


def _payload(result) -> dict:
    """Parse the single JSON object line from a CLI result (stderr interleaves)."""
    for line in result.output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON object in output: {result.output!r}")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tmp git repo with a configured identity, used as the working dir."""
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
    monkeypatch.delenv("DOGEN_MODEL", raising=False)
    return tmp_path


def _declare_signed(root: Path) -> FilesystemPlanningStore:
    """Scaffold a signed unit ``u`` (no steps) and return the store."""
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=root, intent=Intent.reference, audience="devs")
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
    return store


def test_record_plan_seeds_steps_from_steps_file(repo):
    # A valid --steps-file is read + validated at the compose root and replaces
    # provenance.steps; record show reflects it.
    store = _declare_signed(repo)
    steps = repo / "steps.yaml"
    steps.write_text(
        "- id: s1\n  text: run the check\n- id: s2\n  text: build the docs\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["record", "plan", "u", "--steps-file", str(steps)])
    assert result.exit_code == 0, result.output
    prov = store.read_provenance("u", root=repo)
    assert [s.id for s in prov.steps] == ["s1", "s2"]

    show = runner.invoke(app, ["record", "show", "u", "--json"])
    assert show.exit_code == 0, show.output
    assert [s["id"] for s in _payload(show)["steps"]] == ["s1", "s2"]


def test_malformed_steps_file_refused_no_core_mutation(repo):
    # A malformed steps file is refused at the boundary with a stable reason and
    # a non-zero exit — never a raw traceback, and nothing crosses into core/.
    store = _declare_signed(repo)
    bad = repo / "steps.yaml"
    bad.write_text("not: a list of steps\n", encoding="utf-8")

    result = runner.invoke(
        app, ["record", "plan", "u", "--steps-file", str(bad), "--json"]
    )
    assert result.exit_code == 2, result.output
    assert _payload(result)["reason"] == "bad_steps_file"
    assert store.read_provenance("u", root=repo).steps == []


def test_malformed_evidence_file_refused_at_boundary(repo):
    # A malformed evidence file (unparseable YAML) is refused with a stable reason
    # at the compose boundary — distinct from the micro-gate's evidence_required.
    store = _declare_signed(repo)
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Ada",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            steps=[Step(id="s1", text="run the check")],
        ),
        root=repo,
    )
    bad = repo / "ev.yaml"
    bad.write_text("verdict: not-a-real-verdict\n", encoding="utf-8")

    result = runner.invoke(
        app, ["record", "step", "u", "s1", "--evidence-file", str(bad), "--json"]
    )
    assert result.exit_code == 2, result.output
    assert _payload(result)["reason"] == "bad_evidence_file"
    assert store.read_provenance("u", root=repo).steps[0].evidence is None


def test_unit_show_json_carries_additive_steps_key_when_stepped(repo):
    # A unit with steps gains an additive `steps` key in unit show --json, each
    # step carrying its derived status; existing keys are untouched.
    store = _declare_signed(repo)
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Ada",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            steps=[Step(id="s1", text="run the check")],
        ),
        root=repo,
    )
    result = runner.invoke(app, ["unit", "show", "u", "--json"])
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["steps"][0]["id"] == "s1"
    assert payload["steps"][0]["status"] == "unverified"
    assert payload["all_steps_verified"] is False


def test_unit_show_step_free_json_omits_steps_keys(repo):
    # EVID-06: a step-free unit's unit show --json is byte-identical — the additive
    # step keys are absent entirely, not present-and-empty.
    _declare_signed(repo)
    result = runner.invoke(app, ["unit", "show", "u", "--json"])
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert "steps" not in payload
    assert "all_steps_verified" not in payload


def test_status_json_step_free_row_omits_step_keys(repo):
    # EVID-06: a step-free unit's status --json row carries no step keys.
    _declare_signed(repo)
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0, result.output
    board = next(
        json.loads(line.strip())
        for line in result.output.splitlines()
        if line.strip().startswith("[")
    )
    assert "steps_verified" not in board[0]


def test_status_json_stepped_row_carries_steps_verified(repo):
    # A unit with steps gains an additive `steps_verified` boolean in its status
    # --json row (derived via all_steps_verified).
    store = _declare_signed(repo)
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Ada",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            steps=[Step(id="s1", text="run the check")],
        ),
        root=repo,
    )
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0, result.output
    board = next(
        json.loads(line.strip())
        for line in result.output.splitlines()
        if line.strip().startswith("[")
    )
    assert board[0]["steps_verified"] is False


def test_record_plan_undeclared_unit_refuses_no_side_effect(repo):
    # WR-01: planning steps for a *safe* id that names no declared unit must
    # refuse cleanly (unit_not_found, exit 1 — matching `unit edit`) and write
    # no orphan provenance and no step-planned commit, mirroring signoff/steer
    # which load_unit first. Previously `plan_steps` never verified the unit
    # existed, so it created `.dogen/units/ghost/provenance.yaml` for a unit
    # with no `unit.md` and recorded a git commit for it.
    steps = repo / "steps.yaml"
    steps.write_text("- id: s1\n  text: run the check\n", encoding="utf-8")

    result = runner.invoke(
        app, ["record", "plan", "ghost", "--steps-file", str(steps), "--json"]
    )

    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "unit_not_found"
    # No orphan sidecar and no per-unit directory for the undeclared unit.
    assert not (repo / ".dogen" / "units" / "ghost").exists()
    # No step-planned commit landed for a unit that does not exist.
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert "step-planned" not in log.stdout


def test_record_step_undeclared_unit_refuses_unit_not_found(repo):
    # IN-03 (resolved by WR-01's shared load_unit guard): recording a step for
    # an undeclared unit must report unit_not_found (exit 1), not the misleading
    # unknown_step ("write the step plan first") that conflated "unit not
    # planned" with "step not planned".
    ev = repo / "ev.yaml"
    ev.write_text(
        "verdict: pass\noutput_sha256: abc\nexit_code: 0\n", encoding="utf-8"
    )

    result = runner.invoke(
        app,
        ["record", "step", "ghost", "s1", "--evidence-file", str(ev), "--json"],
    )

    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "unit_not_found"
    assert not (repo / ".dogen" / "units" / "ghost").exists()
