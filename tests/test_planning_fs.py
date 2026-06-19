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

"""Tests for the filesystem PlanningStore, splitter, and git-identity adapter."""

from pathlib import Path

import pytest

from dogen.adapters.git_identity import GitIdentityError, read_git_identity
from dogen.adapters.planning_fs import (
    FilesystemPlanningStore,
    UnitExistsError,
    split_front_matter,
)
from dogen.core.models import Intent, Unit


def test_scaffold_unit_writes_editable_unit_md(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    written = store.scaffold_unit("my-unit", root=tmp_path)
    assert written == tmp_path / ".dogen" / "units" / "my-unit" / "unit.md"
    assert written.exists()
    front, body = split_front_matter(written.read_text(encoding="utf-8"))
    unit = Unit(**front)
    assert unit.unit_id == "my-unit"
    assert "Intent & scope" in body
    assert "Outline / acceptance" in body


def test_scaffold_unit_prefills_intent_and_audience(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    written = store.scaffold_unit(
        "my-unit",
        root=tmp_path,
        intent=Intent.reference,
        audience="developers",
    )
    front, _ = split_front_matter(written.read_text(encoding="utf-8"))
    unit = Unit(**front)
    assert unit.intent is Intent.reference
    assert unit.audience == "developers"


def test_scaffold_unit_never_writes_under_planning(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    store.scaffold_unit("ok-unit", root=tmp_path)
    # No file the store wrote may live under any `.planning/` path (D-30).
    assert (
        not list((tmp_path / ".planning").rglob("*"))
        if (tmp_path / ".planning").exists()
        else True
    )


def test_scaffold_unit_refuses_unit_id_with_path_traversal(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    for bad in ["../escape", "a/b", "..", "/abs", "with\\sep"]:
        with pytest.raises(ValueError):
            store.scaffold_unit(bad, root=tmp_path)


def test_scaffold_unit_refuses_to_clobber_without_force(tmp_path: Path) -> None:
    store = FilesystemPlanningStore()
    written = store.scaffold_unit("my-unit", root=tmp_path)
    written.write_text(written.read_text() + "\nedited by operator\n")
    with pytest.raises(UnitExistsError):
        store.scaffold_unit("my-unit", root=tmp_path)
    # The edit survived (no silent overwrite).
    assert "edited by operator" in written.read_text()
    # --force overwrites.
    store.scaffold_unit("my-unit", root=tmp_path, force=True)
    assert "edited by operator" not in written.read_text()


def test_split_front_matter_round_trips_normal_doc() -> None:
    text = "---\nunit_id: x\nintent: reference\n---\n# Body\n\ncontent\n"
    front, body = split_front_matter(text)
    assert front == {"unit_id": "x", "intent": "reference"}
    assert body == "# Body\n\ncontent\n"


def test_split_front_matter_handles_empty_body() -> None:
    text = "---\nunit_id: x\n---\n"
    front, body = split_front_matter(text)
    assert front == {"unit_id": "x"}
    assert body == ""


def test_split_front_matter_handles_dashes_in_body() -> None:
    text = "---\nunit_id: x\n---\nintro\n\n---\n\nafter a horizontal rule\n"
    front, body = split_front_matter(text)
    assert front == {"unit_id": "x"}
    assert "---" in body
    assert "after a horizontal rule" in body


def test_split_front_matter_handles_crlf() -> None:
    text = "---\r\nunit_id: x\r\n---\r\nbody line\r\n"
    front, body = split_front_matter(text)
    assert front == {"unit_id": "x"}
    assert "body line" in body


def test_split_front_matter_rejects_missing_front_matter() -> None:
    with pytest.raises(ValueError):
        split_front_matter("# Just a body, no front-matter\n")


def test_read_git_identity_returns_configured_values() -> None:
    calls: list[list[str]] = []

    def fake_runner(args: list[str]) -> str:
        calls.append(args)
        return {"user.name": "Ada Lovelace", "user.email": "ada@example.com"}[args[-1]]

    name, email = read_git_identity(runner=fake_runner)
    assert name == "Ada Lovelace"
    assert email == "ada@example.com"
    # Only the two allowlisted git-config reads were issued.
    assert calls == [
        ["git", "config", "user.name"],
        ["git", "config", "user.email"],
    ]


def test_read_git_identity_raises_when_unset() -> None:
    def empty_runner(args: list[str]) -> str:
        return ""

    with pytest.raises(GitIdentityError):
        read_git_identity(runner=empty_runner)
