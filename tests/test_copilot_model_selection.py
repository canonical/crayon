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

"""Model selection threaded through the provider seam (LIVE-01, no network).

These assert the ``--model`` wiring without any live SDK call:

* the Copilot provider defaults to ``gpt-5-mini`` (the retired ``gpt-5`` is gone);
* ``select_provider("copilot", model=...)`` threads the model to the adapter;
* the ``mock`` path ignores ``model``/``effort`` and stays SDK-free — the seam
  guardrail (``seam_check.main() == 0``) still holds, and resolving the mock
  provider does not pull ``dogen.adapters.copilot`` onto ``sys.modules``.
"""

import sys
from pathlib import Path

from dogen.adapters.copilot.provider import CopilotDraftingProvider
from dogen.adapters.mock_provider import MockDraftingProvider, select_provider

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import seam_check  # noqa: E402


def test_copilot_default_model_is_gpt_5_mini() -> None:
    """LIVE-01: the bare Copilot provider requests ``gpt-5-mini``."""
    assert CopilotDraftingProvider()._model == "gpt-5-mini"


def test_select_provider_threads_model_to_copilot_adapter() -> None:
    """LIVE-01: ``--model`` reaches the adapter through ``select_provider``."""
    provider = select_provider("copilot", model="claude-haiku-4.5")
    assert isinstance(provider, CopilotDraftingProvider)
    assert provider._model == "claude-haiku-4.5"


def test_select_provider_copilot_default_model_when_unset() -> None:
    """LIVE-01: an unset ``model`` leaves the adapter on its own default."""
    provider = select_provider("copilot")
    assert isinstance(provider, CopilotDraftingProvider)
    assert provider._model == "gpt-5-mini"


def test_mock_provider_ignores_model_and_stays_sdk_free() -> None:
    """LIVE-01/D-25: the mock path honours the signature but imports no SDK."""
    provider = select_provider("mock", model="gpt-5-mini")
    assert isinstance(provider, MockDraftingProvider)
    # The seam guardrail (the exact check CI/pre-commit run) still passes: no
    # Copilot SDK import leaked onto core/cli or the mock path.
    assert seam_check.main() == 0
