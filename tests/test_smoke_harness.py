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

"""Smoke-harness unit tests: the non-live and backend-unavailable branches.

The live SDK run is manual (out of CI, D-24); these tests exercise only the
gated branches — argument parsing, the not-live default (no SDK call), and the
backend-unavailable degradation — without ever touching the network or the SDK.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import smoke_draft  # noqa: E402


def test_not_live_by_default_makes_no_sdk_call(capsys) -> None:  # noqa: ANN001
    # Default (no --live, no env opt-in): returns 0 and prints the opt-in hint,
    # never importing or calling the SDK.
    code = smoke_draft.run(["--unit", "demo"], env={})
    out = capsys.readouterr().out
    assert code == 0
    assert "live SDK path not enabled" in out


def test_env_opt_in_enables_live() -> None:
    args = smoke_draft.parse_args(["--unit", "u"], env={"DOGEN_SMOKE_LIVE": "1"})
    assert args.live is True
    assert args.unit_id == "u"


def test_flag_opt_in_enables_live() -> None:
    args = smoke_draft.parse_args(["--live"], env={})
    assert args.live is True


def test_backend_unavailable_returns_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub the adapter the live path constructs so the harness's degraded branch
    # is provable without a live backend: a raised BackendUnavailableError must
    # become exit code 1, not a crash.
    from dogen.adapters.copilot import BackendUnavailableError  # noqa: PLC0415

    async def _boom(*_a: object, **_k: object) -> int:
        raise BackendUnavailableError("stubbed: backend down")

    monkeypatch.setattr(smoke_draft, "_draft_and_record", _boom)
    code = smoke_draft.run(["--live", "--unit", "demo"], env={})
    assert code == 1
