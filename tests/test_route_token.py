"""ROUTE-01: the type-aware `record` routing token for actionable units.

Plan 14-01 makes the single core routing decision (`_suggest_next`) type-aware:
a tutorial/how-to unit at the draft-stage fork (pending first-draft, reviewed+fix,
reviewed+redraft) emits the append-only `next_id` token `record` instead of
`draft`, routing the operator to dogen-record rather than dogen-write. Reference
and explanation stay byte-identical (proven in
``tests/test_route_reference_regression.py``).

This file asserts three things:
  1. `_suggest_next(..., intent=Intent.tutorial|how_to)` returns `record` at all
     three draft-stage forks, and rides the unchanged token everywhere else.
  2. The Pitfall-1 review path: running the review use-case over an actionable
     unit with a `fix` verdict yields `ReviewOutcome.next_id == "record"` — the
     review-outcome call site must load the unit unconditionally (today `unit` is
     loaded only inside the accept branch), else `intent` is unbound.
  3. Task 2: `dogen signoff --json` carries an additive `next_id` computed through
     the one core decision point — `draft` for reference, `record` for actionable.

Mirrors ``tests/test_step_free_regression.py`` (fixtures) and
``tests/test_cli_contract.py`` (the Typer ``CliRunner`` + git-repo harness).
Fully offline: no token, no network (D-17).
"""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.cli.main import app
from dogen.core.models import (
    Effort,
    FileDigest,
    Generation,
    Intent,
    ProgressState,
    Provenance,
    ReviewVerdict,
    Signoff,
)
from dogen.core.orchestrator import ReviewRequest, _suggest_next, review

runner = CliRunner()

_ACTIONABLE = (Intent.tutorial, Intent.how_to)


class _Clock:
    """A deterministic, monotonically increasing ISO-8601 clock."""

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"2026-01-01T00:00:{self._n:02d}Z"


# --------------------------------------------------------------------------- #
# 1. The `record` token at the three draft-stage forks (ROUTE-01 core).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("intent", _ACTIONABLE)
def test_actionable_pending_first_draft_routes_to_record(intent: Intent) -> None:
    # A signed-off, not-stale actionable unit awaiting its first draft → `record`.
    token, _ = _suggest_next(
        ProgressState.pending,
        signed_off=True,
        stale_plan=False,
        last_verdict=None,
        unit_id="u",
        intent=intent,
    )
    assert token == "record"


@pytest.mark.parametrize("intent", _ACTIONABLE)
@pytest.mark.parametrize("verdict", [ReviewVerdict.fix, ReviewVerdict.redraft])
def test_actionable_review_forks_route_to_record(
    intent: Intent, verdict: ReviewVerdict
) -> None:
    # Both non-accept review verdicts on an actionable unit route to `record`
    # (D-02: an actionable unit never goes back to dogen-write).
    token, _ = _suggest_next(
        ProgressState.reviewed,
        signed_off=True,
        stale_plan=False,
        last_verdict=verdict,
        unit_id="u",
        intent=intent,
    )
    assert token == "record"


@pytest.mark.parametrize("intent", _ACTIONABLE)
def test_actionable_accept_still_publishes(intent: Intent) -> None:
    # A non-draft-stage key is unchanged for actionable units too — an accepted
    # actionable unit still routes to `publish`, never `record`.
    token, _ = _suggest_next(
        ProgressState.reviewed,
        signed_off=True,
        stale_plan=False,
        last_verdict=ReviewVerdict.accept,
        unit_id="u",
        intent=intent,
    )
    assert token == "publish"


@pytest.mark.parametrize("intent", _ACTIONABLE)
@pytest.mark.parametrize(
    ("state", "signed", "stale", "verdict", "expected"),
    [
        (ProgressState.pending, False, False, None, "sign_off"),
        (ProgressState.pending, True, True, None, "re_sign"),
        (ProgressState.drafted, True, False, None, "review"),
    ],
)
def test_actionable_non_draft_stage_tokens_unchanged(  # noqa: PLR0913
    intent: Intent,
    state: ProgressState,
    signed: bool,
    stale: bool,
    verdict: ReviewVerdict | None,
    expected: str,
) -> None:
    # sign_off / re_sign / review are unchanged for actionable units — `record`
    # only replaces the draft-stage token (draft/fix/redraft).
    token, _ = _suggest_next(
        state,
        signed_off=signed,
        stale_plan=stale,
        last_verdict=verdict,
        unit_id="u",
        intent=intent,
    )
    assert token == expected


# --------------------------------------------------------------------------- #
# 2. Pitfall-1: the review use-case over an actionable unit + fix verdict must
#    load the unit unconditionally so `intent` is bound → next_id == "record".
# --------------------------------------------------------------------------- #


def _seed_drafted_actionable(root: Path, intent: Intent) -> FilesystemPlanningStore:
    """Scaffold a signed-off, drafted actionable unit (no plan_hash → not stale)."""
    store = FilesystemPlanningStore()
    store.scaffold_unit("u", root=root, intent=intent, audience="devs")
    store.write_provenance(
        Provenance(
            unit_id="u",
            signoff=Signoff(
                author="Ada",
                at="2026-01-01T00:00:00Z",
                intent=intent,
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
    return store


@pytest.mark.parametrize("intent", _ACTIONABLE)
def test_review_fix_on_actionable_returns_record(
    tmp_path: Path, intent: Intent
) -> None:
    # Pitfall-1: a fix verdict skips the accept branch (where `unit` is loaded
    # today); the review-outcome path must load the unit unconditionally so the
    # actionable intent reaches `_suggest_next` and next_id resolves to `record`
    # — no NameError/UnboundLocalError on `unit`.
    store = _seed_drafted_actionable(tmp_path, intent)
    outcome = review(
        ReviewRequest(
            unit_id="u",
            root=tmp_path,
            store=store,
            identity=lambda: ("Reviewer", "rev@example.com"),
            now=_Clock(),
            note="tighten step 2",
            verdict=ReviewVerdict.fix,
        )
    )
    assert outcome.state is ProgressState.reviewed
    assert outcome.next_id == "record"


def test_review_fix_on_reference_stays_draft(tmp_path: Path) -> None:
    # The reference complement: the unconditional load must not change reference
    # routing — a fix verdict on a reference unit still yields the `draft` token.
    store = _seed_drafted_actionable(tmp_path, Intent.reference)
    outcome = review(
        ReviewRequest(
            unit_id="u",
            root=tmp_path,
            store=store,
            identity=lambda: ("Reviewer", "rev@example.com"),
            now=_Clock(),
            note="tweak wording",
            verdict=ReviewVerdict.fix,
        )
    )
    assert outcome.next_id == "draft"


# --------------------------------------------------------------------------- #
# 3. Task 2: `dogen signoff --json` carries an additive `next_id` token.
# --------------------------------------------------------------------------- #


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
    return tmp_path


def _payload(result) -> dict:
    """Parse the single JSON object line from a CLI result."""
    for line in result.output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"no JSON object in output: {result.output!r}")


def test_signoff_json_reference_carries_next_id_draft(repo) -> None:
    # A freshly-signed reference unit's --json gains next_id == "draft" alongside
    # the pre-existing `unit` and `commit` keys (purely additive, D-08).
    runner.invoke(
        app, ["unit", "new", "u", "--intent", "reference", "--audience", "devs"]
    )
    result = runner.invoke(app, ["signoff", "u", "--json"])
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["next_id"] == "draft"
    assert "unit" in payload
    assert "commit" in payload


@pytest.mark.parametrize("intent", ["tutorial", "how-to"])
def test_signoff_json_actionable_carries_next_id_record(repo, intent: str) -> None:
    # A freshly-signed tutorial/how-to unit's --json carries next_id == "record".
    runner.invoke(app, ["unit", "new", "u", "--intent", intent, "--audience", "devs"])
    result = runner.invoke(app, ["signoff", "u", "--json"])
    assert result.exit_code == 0, result.output
    assert _payload(result)["next_id"] == "record"


def test_signoff_plain_output_is_unchanged(repo) -> None:
    # The plain (non-JSON) signoff line is untouched by the additive JSON key.
    runner.invoke(
        app, ["unit", "new", "u", "--intent", "tutorial", "--audience", "devs"]
    )
    result = runner.invoke(app, ["signoff", "u"])
    assert result.exit_code == 0, result.output
    assert "Recorded signoff for u" in result.output
    assert "next_id" not in result.output


# --------------------------------------------------------------------------- #
# 4. WR-01: `review --json` carries `intent` for the direction-specific
#    `re_sign` referral fork (reference → /dogen-write, actionable → /dogen-record).
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("intent", ["reference", "tutorial", "how-to"])
def test_review_json_carries_intent(repo, intent: str) -> None:
    # WR-01: `review --json` gains `intent` (mirroring `status --json`) so a
    # consumer can render the direction-specific `re_sign` referral line from the
    # review payload alone — the routed token stays direction-agnostic (D-01);
    # `intent` is the direction signal, never a re-derivation in core.
    runner.invoke(app, ["unit", "new", "u", "--intent", intent, "--audience", "devs"])
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    draft = runner.invoke(app, ["draft", "u", "--provider", "mock"])
    assert draft.exit_code == 0, draft.output
    result = runner.invoke(
        app, ["review", "u", "--note", "tighten wording", "--verdict", "fix", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["intent"] == intent
    # The pre-existing keys are untouched (purely additive).
    assert payload["verdict"] == "fix"
    assert "next_id" in payload


# --------------------------------------------------------------------------- #
# 5. WR-02: `signoff --re-sign --json` derives its `next_id` from the unit's
#    ACTUAL provenance — an already-drafted unit routes to `review`, never a
#    spurious first-draft token.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("intent", ["reference", "tutorial", "how-to"])
def test_re_sign_json_on_drafted_unit_routes_to_review(repo, intent: str) -> None:
    # WR-02: re-signing an already-drafted unit must not mis-route to a re-draft.
    # The post-signoff token is derived from real provenance, so a drafted unit
    # resolves to `review` regardless of direction (the draft-stage `record` fork
    # is only reached at `pending`).
    runner.invoke(app, ["unit", "new", "u", "--intent", intent, "--audience", "devs"])
    assert runner.invoke(app, ["signoff", "u"]).exit_code == 0
    draft = runner.invoke(app, ["draft", "u", "--provider", "mock"])
    assert draft.exit_code == 0, draft.output
    result = runner.invoke(app, ["signoff", "u", "--re-sign", "--json"])
    assert result.exit_code == 0, result.output
    assert _payload(result)["next_id"] == "review"


@pytest.mark.parametrize(
    ("intent", "expected"),
    [("reference", "draft"), ("tutorial", "record"), ("how-to", "record")],
)
def test_fresh_signoff_json_still_routes_to_first_draft(
    repo, intent: str, expected: str
) -> None:
    # WR-02 regression guard: deriving from real provenance leaves the fresh-
    # signoff path unchanged — a just-signed unit with no draft is `pending`, so
    # reference → `draft`, actionable → `record` (matches the pre-fix contract).
    runner.invoke(app, ["unit", "new", "u", "--intent", intent, "--audience", "devs"])
    result = runner.invoke(app, ["signoff", "u", "--json"])
    assert result.exit_code == 0, result.output
    assert _payload(result)["next_id"] == expected
