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

from dogen.adapters.planning_fs import FilesystemPlanningStore, TargetClaimedError
from dogen.cli import main as cli
from dogen.cli.main import app
from dogen.core.models import (
    Intent,
    ProgressState,
    Provenance,
    Signoff,
    Step,
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
    monkeypatch.delenv("DOGEN_MODEL", raising=False)
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


def _plant_inflight_neighbour(store, root, unit_id, *, targets):
    """Plant a neighbour unit.md + an in-flight provenance directly on disk.

    Bypasses the declare guard so a second unit can hold a page an existing unit
    also targets — the reverse-hole precondition the draft re-check catches.
    """
    primary, *extras = targets
    md_path = store._unit_md_path(unit_id, root=root)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        store._render_unit_md(
            unit_id,
            intent=Intent.reference,
            audience="devs",
            sphinx_target=primary,
            extra_targets=extras or None,
        ),
        encoding="utf-8",
    )
    # An empty provenance is readable and not sealed ⇒ in-flight (holds its lease).
    store.write_provenance(Provenance(unit_id=unit_id), root=root)


def test_draft_target_claimed_reason(repo):
    # OWN-03: drafting a unit whose page is claimed by an in-flight neighbour is a
    # clean domain refusal — exit 1, reason="target_claimed" (the re-check maps
    # TargetClaimedError to a stable reason, NOT an uncaught Python traceback).
    store = _declare_unit(repo)  # unit "u" -> docs/u.md
    _seed_steering(store, repo)  # signed off, ready to draft
    _plant_inflight_neighbour(store, repo, "b", targets=["u.md"])

    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "target_claimed"
    # A clean refusal: TargetClaimedError was mapped, never surfaced as a traceback.
    assert not isinstance(result.exception, TargetClaimedError)
    # No draft was written under the refusal.
    assert not (repo / "docs" / "u.md").exists()


def test_draft_json_carries_identical_draft_false_on_first_draft(repo):
    # MODEL-03: the draft --json contract now includes an identical_draft boolean;
    # the first draft of a unit is never identical (no prior generation).
    store = _declare_unit(repo)
    _seed_steering(store, repo)

    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 0, result.output
    assert _payload(result)["identical_draft"] is False


def test_byte_identical_redraft_reports_identical_and_hints_amend(repo):
    # D-02/MODEL-03: a byte-identical redraft (same mock inputs) is a true no-op —
    # --json identical_draft True, the plain output hints --amend-model, and the
    # unsteered-redraft warning is suppressed (never fires on the no-op path).
    store = _declare_unit(repo)
    _seed_steering(store, repo)
    first = runner.invoke(app, ["draft", "u", "--provider", "mock"])
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert second.exit_code == 0, second.output
    assert _payload(second)["identical_draft"] is True

    plain = runner.invoke(app, ["draft", "u", "--provider", "mock"])
    assert plain.exit_code == 0, plain.output
    assert "--amend-model" in plain.output
    assert "no recorded steering" not in plain.output


def test_dogen_model_env_records_model_gpt_env_with_flag_origin(repo, monkeypatch):
    # MODEL-01/02: DOGEN_MODEL resolves at mid precedence and stamps the generation
    # with model "gpt-env" and the D-03 operator-tier origin "flag" (env folds into
    # flag), via the CLI resolver path.
    store = _declare_unit(repo)
    _seed_steering(store, repo)
    monkeypatch.setenv("DOGEN_MODEL", "gpt-env")

    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 0, result.output
    generation = store.read_provenance("u", root=repo).generations[-1]
    assert generation.model == "gpt-env"
    assert generation.model_origin == "flag"


def test_unit_new_clobber_exits_domain_refusal_unit_exists(repo):
    # A clobber without --force is a domain refusal — exit 1, reason="unit_exists"
    # (the unit already exists).
    runner.invoke(app, ["unit", "new", "u"])
    result = runner.invoke(app, ["unit", "new", "u", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "unit_exists"


def test_review_undrafted_exits_not_drafted(repo):
    # A steered-but-never-drafted unit has an empty generations stream (derived
    # state pending), so review is bad-input — exit 2, reason="not_drafted" (D-10).
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


# --------------------------------------------------------------------------- #
# `dogen model show|set` — the JSON contract (Phase 8, MODEL-01/D-03)
# --------------------------------------------------------------------------- #


def test_model_set_then_show_json_reports_model_source_origin(repo):
    # `model set --origin ta` persists both fields; `model show --json` reports
    # the fixed {model, source, model_origin} shape with origin carried through.
    set_result = runner.invoke(
        app, ["model", "set", "gpt-4o", "--origin", "ta", "--json"]
    )
    assert set_result.exit_code == 0, set_result.output
    set_payload = _payload(set_result)
    assert set_payload["model"] == "gpt-4o"
    assert set_payload["model_origin"] == "ta"

    show_result = runner.invoke(app, ["model", "show", "--json"])
    assert show_result.exit_code == 0, show_result.output
    show_payload = _payload(show_result)
    assert show_payload == {
        "model": "gpt-4o",
        "source": "repo config",
        "model_origin": "ta",
    }


def test_model_show_plain_reports_unset_when_no_model(repo):
    result = runner.invoke(app, ["model", "show"])
    assert result.exit_code == 0, result.output
    assert "model: (unset) (from default)" in result.output


def test_model_set_rejects_control_char_name_and_writes_nothing(repo):
    # A newline in the name is bad input (exit 2) and must NOT persist a config.
    result = runner.invoke(app, ["model", "set", "bad\nname", "--json"])
    assert result.exit_code == 2, result.output
    assert not (repo / ".dogen" / "config.yaml").exists()


def test_model_set_self_origin_persists_self(repo):
    # The dogen-write auto self-assert path passes --origin self explicitly.
    result = runner.invoke(
        app, ["model", "set", "claude-x", "--origin", "self", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert _payload(result)["model_origin"] == "self"
    store = FilesystemPlanningStore()
    config = store.read_config(root=repo)
    assert config.model == "claude-x"
    assert config.model_origin == "self"


# --------------------------------------------------------------------------- #
# SK-07/D-03: the human `next` key is dropped from `review --json` and
# `status --json`; the machine `next_id` routing token stays. Plain (non --json)
# output keeps the human `Next:` line.
# --------------------------------------------------------------------------- #


def test_review_json_omits_human_next_keeps_next_id(repo):
    # SK-07: review --json carries the durable next_id routing token but no longer
    # emits the human `next` string (that survives only in plain output).
    runner.invoke(
        app, ["unit", "new", "u", "--intent", "reference", "--audience", "devs"]
    )
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert runner.invoke(app, ["draft", "u", "--provider", "mock"]).exit_code == 0
    result = runner.invoke(
        app, ["review", "u", "--verdict", "fix", "--note", "n", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert "next" not in payload
    assert "next_id" in payload


def test_status_json_omits_human_next_keeps_next_id(repo):
    # SK-07: status --json rows carry next_id but not the human `next` key.
    runner.invoke(
        app, ["unit", "new", "u", "--intent", "reference", "--audience", "devs"]
    )
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0, result.output
    board = next(
        json.loads(line.strip())
        for line in result.output.splitlines()
        if line.strip().startswith("[")
    )
    row = board[0]
    assert "next" not in row
    assert "next_id" in row


# --------------------------------------------------------------------------- #
# `dogen signoff` flag hygiene — SK-06/D-03: `--force` hard-removed, `--re-sign`
# is the sole overwrite alias; `--force` on OTHER verbs is untouched.
# --------------------------------------------------------------------------- #


def test_signoff_force_alias_is_now_a_usage_error(repo):
    # SK-06/D-03: `--force` was hard-removed from `signoff` (no grace window); it
    # is now an unknown option — a Typer usage error, exit 2.
    runner.invoke(
        app, ["unit", "new", "u", "--intent", "reference", "--audience", "devs"]
    )
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    result = runner.invoke(app, ["signoff", "u", "--force"])
    assert result.exit_code == 2, result.output


def test_signoff_re_sign_alias_still_overwrites(repo):
    # SK-06: `--re-sign` survives as the sole re-sign alias — a bare re-signoff is
    # refused (the HITL gate stays provable), but `--re-sign` overwrites the act.
    runner.invoke(
        app, ["unit", "new", "u", "--intent", "reference", "--audience", "devs"]
    )
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    assert (
        runner.invoke(app, ["unit", "edit", "u", "--title", "Amended"]).exit_code == 0
    )
    # A bare re-signoff of an already-signed unit refuses (domain refusal, exit 1)...
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 1
    # ...but `--re-sign` overwrites the existing act with the fresh plan hash.
    assert runner.invoke(app, ["signoff", "u", "--re-sign"]).exit_code == 0


def test_signoff_force_removal_leaves_other_verbs_force_intact(repo):
    # D-03 scope guard: `--force` on OTHER verbs (here `unit rm`) is a different
    # real flag and is unaffected by the signoff alias removal.
    runner.invoke(
        app, ["unit", "new", "u", "--intent", "reference", "--audience", "devs"]
    )
    result = runner.invoke(app, ["unit", "rm", "u", "--force", "--json"])
    assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------- #
# Phase 12 Plan 03 (EVID-01/D-11): the `record` group + the two stable evidence
# reason codes on the machine seam. `record plan`/`record step`/`record show`
# make Plan 02's use-cases operable; the micro-gate surfaces `evidence_required`
# and the macro-gate `evidence_incomplete`, both at exit code 1 (domain refusal).
# --------------------------------------------------------------------------- #


def _seed_signed_with_step(
    store: FilesystemPlanningStore,
    root: Path,
    *,
    step_id: str = "s1",
    text: str = "run the check",
) -> None:
    """Seed a signed unit ``u`` with one planned (evidence-free) step on disk."""
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Ada",
                at="2026-01-01T00:00:00Z",
                intent=Intent.reference,
                audience="devs",
            ),
            steps=[Step(id=step_id, text=text)],
        ),
        root=root,
    )


def test_record_help_lists_plan_step_show():
    # EVID-01: the record group exposes exactly the three machine-seam verbs.
    result = runner.invoke(app, ["record", "--help"])
    assert result.exit_code == 0, result.output
    for verb in ("plan", "step", "show"):
        assert verb in result.output


def test_evidence_reason_codes_added_existing_unchanged():
    # D-11: the two evidence reasons are appended with their stable wire values;
    # an existing reason string is never renamed (append-only vocabulary).
    assert cli._REASON_EVIDENCE_REQUIRED == "evidence_required"
    assert cli._REASON_EVIDENCE_INCOMPLETE == "evidence_incomplete"
    assert cli._REASON_SIGNOFF_REQUIRED == "signoff_required"


def test_record_step_done_without_proof_exits_evidence_required(repo):
    # D-11 micro-gate: a `pass` verdict with no captured-output hash / exit code
    # is refused — exit 1, reason="evidence_required" (skills branch on the code).
    store = _declare_unit(repo)
    _seed_signed_with_step(store, repo)
    ev = repo / "ev.yaml"
    ev.write_text("verdict: pass\ncommand: pytest\n", encoding="utf-8")

    result = runner.invoke(
        app, ["record", "step", "u", "s1", "--evidence-file", str(ev), "--json"]
    )
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "evidence_required"
    # Zero side effects: the step kept no evidence.
    assert store.read_provenance("u", root=repo).steps[0].evidence is None


def test_record_step_wellshaped_pass_records_and_resolves(repo):
    # A well-shaped pass records the evidence and reports the derived status.
    store = _declare_unit(repo)
    _seed_signed_with_step(store, repo)
    ev = repo / "ev.yaml"
    ev.write_text(
        "verdict: pass\ncommand: pytest\n"
        f"output_sha256: {'a' * 64}\nexit_code: 0\noutput_excerpt: '1 passed'\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["record", "step", "u", "s1", "--evidence-file", str(ev), "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["reason"] is None
    assert payload["status"] == "resolved"
    assert store.read_provenance("u", root=repo).steps[0].evidence is not None


def test_record_step_stdin_evidence_parity(repo):
    # '-' reads the evidence payload from stdin (compose-root stdin parity).
    store = _declare_unit(repo)
    _seed_signed_with_step(store, repo)
    payload_text = (
        f"verdict: pass\ncommand: pytest\noutput_sha256: {'b' * 64}\nexit_code: 0\n"
    )
    result = runner.invoke(
        app,
        ["record", "step", "u", "s1", "--evidence-file", "-", "--json"],
        input=payload_text,
    )
    assert result.exit_code == 0, result.output
    assert store.read_provenance("u", root=repo).steps[0].evidence is not None


def test_record_step_unknown_step_exits_bad_input(repo):
    # An unknown step_id is bad input (the compose root validates well-shapedness;
    # the core raises ValueError) — exit 2, never an uncaught traceback.
    store = _declare_unit(repo)
    _seed_signed_with_step(store, repo)
    ev = repo / "ev.yaml"
    ev.write_text(
        f"verdict: pass\ncommand: pytest\noutput_sha256: {'c' * 64}\nexit_code: 0\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["record", "step", "u", "ghost", "--evidence-file", str(ev), "--json"]
    )
    assert result.exit_code == 2, result.output
    assert _payload(result)["reason"] == "unknown_step"


def test_record_step_boolean_exit_code_refused_at_boundary(repo):
    # WR-03: `bool` is a subclass of `int`, so `exit_code: false` used to pass
    # the isinstance(exit_code, int) check and become 0 — combined with the
    # deviated `exit_code == 0` rule (`False == 0`), a boolean could resolve a
    # step. A boolean exit code is malformed input and must be refused at the
    # compose boundary (bad_evidence_file, exit 2) with zero side effects.
    store = _declare_unit(repo)
    _seed_signed_with_step(store, repo)
    ev = repo / "ev.yaml"
    ev.write_text(
        f"verdict: deviated\ncommand: pytest\noutput_sha256: {'d' * 64}\n"
        "exit_code: false\nreason: diverged\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["record", "step", "u", "s1", "--evidence-file", str(ev), "--json"]
    )
    assert result.exit_code == 2, result.output
    assert _payload(result)["reason"] == "bad_evidence_file"
    # Zero side effects: no evidence was bound to the step.
    assert store.read_provenance("u", root=repo).steps[0].evidence is None


def test_draft_over_unresolved_step_exits_evidence_incomplete(repo):
    # D-11 macro-gate: drafting over an unresolved planned step is a domain
    # refusal — exit 1, reason="evidence_incomplete", and no draft is written.
    store = _declare_unit(repo)
    _seed_signed_with_step(store, repo)  # planned, no evidence -> unresolved

    result = runner.invoke(app, ["draft", "u", "--provider", "mock", "--json"])
    assert result.exit_code == 1, result.output
    assert _payload(result)["reason"] == "evidence_incomplete"
    assert not (repo / "docs" / "u.md").exists()


def test_record_show_reflects_recorded_plan_and_status(repo):
    # `record show` prints the recorded plan + per-step derived status (--json).
    store = _declare_unit(repo)
    _seed_signed_with_step(store, repo)

    result = runner.invoke(app, ["record", "show", "u", "--json"])
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["unit"] == "u"
    assert payload["all_steps_verified"] is False
    assert payload["steps"][0]["id"] == "s1"
    assert payload["steps"][0]["status"] == "unverified"


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
