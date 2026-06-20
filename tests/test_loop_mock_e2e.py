# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

"""The mock end-to-end CI loop: unit new -> steer -> draft -> review (D-24).

Covers Task 3. Drives the four thin subcommands through Typer's ``CliRunner``
against a tmp git repo on ``--provider mock`` (no SDK, no Copilot token), and
asserts the HITL refusal path, the steering-precedes-draft ordering (HITL-02 /
AC5), the single reviewer edit, and that progress ends ``reviewed`` and never
``committed``. Deterministic and order-independent (coding-guide §4).
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.cli.main import app
from dogen.core.models import Intent, ProgressState

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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
    return tmp_path


def _new_unit(unit_id: str) -> None:
    result = runner.invoke(
        app, ["unit", "new", unit_id, "--intent", "reference", "--audience", "devs"]
    )
    assert result.exit_code == 0, result.output


def test_full_loop_reaches_reviewed(repo: Path) -> None:
    store = FilesystemPlanningStore()
    _new_unit("u")
    assert runner.invoke(app, ["steer", "u"]).exit_code == 0
    draft_res = runner.invoke(app, ["draft", "u", "--provider", "mock"])
    assert draft_res.exit_code == 0, draft_res.output
    review_res = runner.invoke(app, ["review", "u", "--note", "reworded intro"])
    assert review_res.exit_code == 0, review_res.output

    unit_dir = repo / ".dogen" / "units" / "u"
    assert (unit_dir / "unit.md").exists()
    assert (unit_dir / "provenance.yaml").exists()
    assert (unit_dir / "progress.yaml").exists()
    unit = store.load_unit("u", root=repo)
    assert (repo / "docs" / unit.sphinx_target).exists()

    progress = store.read_progress("u", root=repo)
    assert progress.state is ProgressState.reviewed
    assert ProgressState.committed not in [e.state for e in progress.history]


def test_review_twice_appends_single_reviewed_transition(repo: Path) -> None:
    # Re-running `review` records each reviewer edit but stamps the `reviewed`
    # progress transition only once (WR-05: idempotent lifecycle history).
    store = FilesystemPlanningStore()
    _new_unit("u")
    runner.invoke(app, ["steer", "u"])
    runner.invoke(app, ["draft", "u", "--provider", "mock"])
    runner.invoke(app, ["review", "u", "--note", "first pass"])
    runner.invoke(app, ["review", "u", "--note", "second pass"])
    provenance = store.read_provenance("u", root=repo)
    progress = store.read_progress("u", root=repo)
    # Both edits are recorded (each is a distinct, audit-relevant act).
    assert len(provenance.reviewer_edits) == 2
    # But only one `reviewed` transition lives in the progress history.
    reviewed_entries = [
        e for e in progress.history if e.state is ProgressState.reviewed
    ]
    assert len(reviewed_entries) == 1
    assert progress.state is ProgressState.reviewed


def test_draft_refuses_without_steer(repo: Path) -> None:
    _new_unit("u")
    result = runner.invoke(app, ["draft", "u", "--provider", "mock"])
    assert result.exit_code != 0
    assert "no recorded steering" in result.output
    assert not (repo / "docs" / "u.md").exists()


def test_review_before_draft_says_draft_first(repo: Path) -> None:
    # A unit steered but never drafted has no progress.yaml to attach a review
    # to; the CLI says so plainly rather than emitting a generic read error
    # (WR-05 UX follow-up).
    _new_unit("u")
    runner.invoke(app, ["steer", "u"])
    result = runner.invoke(app, ["review", "u", "--note", "premature"])
    assert result.exit_code == 2
    assert "has not been drafted yet" in result.output


def test_steer_records_author_and_precedes_draft(repo: Path) -> None:
    store = FilesystemPlanningStore()
    _new_unit("u")
    runner.invoke(app, ["steer", "u"])
    provenance = store.read_provenance("u", root=repo)
    assert provenance.steering is not None
    assert provenance.steering.author == "Ada Lovelace"
    assert provenance.steering.intent is Intent.reference

    runner.invoke(app, ["draft", "u", "--provider", "mock"])
    after = store.read_provenance("u", root=repo)
    assert after.steering is not None
    assert after.steering.at < after.generations[0].at
    # model_version is a real version, not a duplicate of the model name (WR-03).
    generation = after.generations[0]
    assert generation.model == "mock-model"
    assert generation.model_version == "mock-1"


def test_review_appends_single_reviewer_edit(repo: Path) -> None:
    store = FilesystemPlanningStore()
    _new_unit("u")
    runner.invoke(app, ["steer", "u"])
    runner.invoke(app, ["draft", "u", "--provider", "mock"])
    runner.invoke(app, ["review", "u", "--note", "reworded intro"])
    provenance = store.read_provenance("u", root=repo)
    assert len(provenance.reviewer_edits) == 1
    edit = provenance.reviewer_edits[0]
    assert edit.summary == "reworded intro"
    assert edit.reviewer == "Ada Lovelace"
    assert edit.at


def test_steer_refuses_to_overwrite_without_force(repo: Path) -> None:
    # WR-04: re-running `steer` on a unit that already has steering must refuse
    # without an explicit flag, so the recorded steering act is never silently
    # rewritten (which could invert the steering-precedes-draft ordering).
    store = FilesystemPlanningStore()
    _new_unit("u")
    assert runner.invoke(app, ["steer", "u"]).exit_code == 0
    first = store.read_provenance("u", root=repo).steering
    assert first is not None
    result = runner.invoke(app, ["steer", "u"])
    assert result.exit_code == 1
    assert "already recorded" in result.output
    # The original steering act is untouched.
    again = store.read_provenance("u", root=repo).steering
    assert again is not None
    assert again.at == first.at


def test_re_steer_flag_overwrites_steering(repo: Path) -> None:
    # An explicit --re-steer is honoured and replaces the steering act (WR-04).
    store = FilesystemPlanningStore()
    _new_unit("u")
    runner.invoke(app, ["steer", "u"])
    first = store.read_provenance("u", root=repo).steering
    assert first is not None
    result = runner.invoke(app, ["steer", "u", "--re-steer"])
    assert result.exit_code == 0, result.output
    replaced = store.read_provenance("u", root=repo).steering
    assert replaced is not None
    # A fresh act was stamped (the same author, a newly recorded event).
    assert replaced.author == first.author


def test_re_steer_after_draft_warns(repo: Path) -> None:
    # Re-steering a drafted unit is allowed with --re-steer but warns that
    # existing generations predate the new steering act (WR-04).
    _new_unit("u")
    runner.invoke(app, ["steer", "u"])
    runner.invoke(app, ["draft", "u", "--provider", "mock"])
    result = runner.invoke(app, ["steer", "u", "--re-steer"])
    assert result.exit_code == 0, result.output
    assert "already has" in result.output


def test_draft_unknown_provider_exits_cleanly(repo: Path) -> None:
    # WR-06: an unknown --provider must render a clean exit-2 message, not an
    # uncaught ValueError traceback (select_provider is now inside the try).
    _new_unit("u")
    runner.invoke(app, ["steer", "u"])
    result = runner.invoke(app, ["draft", "u", "--provider", "banana"])
    assert result.exit_code == 2, result.output
    assert "Cannot draft" in result.output
    assert "unknown provider" in result.output


def test_draft_mock_error_path_does_not_import_copilot_adapter(repo: Path) -> None:
    # WR-01/D-25: an error on the ``--provider mock`` path (here a ValueError
    # from a unit_id that disagrees with its directory) must be handled WITHOUT
    # importing ``adapters/copilot/``. The pre-fix code caught the
    # backend-unavailable error via a lazy import that ran on every non-steering
    # error, pulling the SDK adapter onto the mock path. Catching by class name
    # instead keeps the mock path SDK-free.
    _new_unit("u")
    runner.invoke(app, ["steer", "u"])
    # Corrupt the front-matter so load_unit raises ValueError (unit_id mismatch).
    unit_md = repo / ".dogen" / "units" / "u" / "unit.md"
    unit_md.write_text(
        unit_md.read_text(encoding="utf-8").replace("unit_id: u\n", "unit_id: not-u\n"),
        encoding="utf-8",
    )
    sys.modules.pop("dogen.adapters.copilot", None)
    sys.modules.pop("dogen.adapters.copilot.provider", None)
    result = runner.invoke(app, ["draft", "u", "--provider", "mock"])
    assert result.exit_code == 2, result.output
    assert "Cannot draft" in result.output
    # The mock error path must never have loaded the Copilot SDK adapter.
    assert "dogen.adapters.copilot" not in sys.modules
    assert "dogen.adapters.copilot.provider" not in sys.modules


def test_e2e_imports_no_sdk() -> None:
    # Parse the module's own import statements (not its source text, which would
    # self-match on the banned tokens used in this very assertion) and assert no
    # SDK package is imported — the CI loop runs without the SDK / token (D-24).
    tree = ast.parse(Path("tests/test_loop_mock_e2e.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "copilot" not in imported
    assert "github_copilot_sdk" not in imported
