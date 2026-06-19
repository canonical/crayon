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

"""End-to-end tests for `dogen unit new` via Typer's CliRunner."""

from pathlib import Path

from typer.testing import CliRunner

from dogen.adapters.planning_fs import split_front_matter
from dogen.cli.main import app
from dogen.core.models import Intent, Unit

runner = CliRunner()


def test_unit_new_creates_unit_md(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["unit", "new", "my-unit"])
    assert result.exit_code == 0, result.output
    written = tmp_path / ".dogen" / "units" / "my-unit" / "unit.md"
    assert written.exists()
    assert str(written) in result.output or "my-unit" in result.output
    front, _ = split_front_matter(written.read_text(encoding="utf-8"))
    assert Unit(**front).unit_id == "my-unit"


def test_unit_new_prefills_intent_and_audience(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["unit", "new", "my-unit", "--intent", "reference", "--audience", "developers"],
    )
    assert result.exit_code == 0, result.output
    written = tmp_path / ".dogen" / "units" / "my-unit" / "unit.md"
    front, _ = split_front_matter(written.read_text(encoding="utf-8"))
    unit = Unit(**front)
    assert unit.intent is Intent.reference
    assert unit.audience == "developers"


def test_unit_new_twice_does_not_clobber(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["unit", "new", "my-unit"])
    written = tmp_path / ".dogen" / "units" / "my-unit" / "unit.md"
    written.write_text(written.read_text() + "\nedited\n")
    result = runner.invoke(app, ["unit", "new", "my-unit"])
    assert result.exit_code != 0
    assert "edited" in written.read_text()


def test_unit_new_rejects_bad_unit_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["unit", "new", "../escape"])
    assert result.exit_code != 0
