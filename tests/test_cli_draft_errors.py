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

"""CLI exit-code rendering for draft-path domain errors (ERR-01/ERR-02).

The CLI classifies backend errors by ``type(exc).__name__`` so the ``mock`` path
never imports ``adapters/copilot/`` (or the SDK) — D-25. These tests assert that
contract via Typer's ``CliRunner`` WITHOUT importing the real adapter: they
monkeypatch the CLI's ``select_provider`` to raise locally-defined ``RuntimeError``
subclasses whose names match the real domain errors, then check the exit code and
the rendered message.

* a ``ModelRejectedError`` → exit 1, message echoed directly (it already names the
  model) — never a traceback (ERR-01);
* a ``BackendUnavailableError`` → exit 1, the existing "Copilot backend
  unavailable:" prefix (ERR-02);
* an unrelated ``RuntimeError`` is NOT swallowed — it propagates (the classifier
  only handles the two named domain errors).
"""

import pytest
from typer.testing import CliRunner

from dogen.cli import main as cli_main
from dogen.cli.main import app

runner = CliRunner()


class _LocalModelRejectedError(RuntimeError):
    """A stand-in whose ``__name__`` matches the real ``ModelRejectedError``."""


_LocalModelRejectedError.__name__ = "ModelRejectedError"
_LocalModelRejectedError.__qualname__ = "ModelRejectedError"


class _LocalBackendUnavailableError(RuntimeError):
    """A stand-in whose ``__name__`` matches ``BackendUnavailableError``."""


_LocalBackendUnavailableError.__name__ = "BackendUnavailableError"
_LocalBackendUnavailableError.__qualname__ = "BackendUnavailableError"


def _raise(exc: Exception):
    """Build a ``select_provider`` replacement that raises ``exc``."""

    def _select(*_a: object, **_k: object):
        raise exc

    return _select


def test_model_rejected_renders_exit_1_clean_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ERR-01: a ModelRejectedError exits 1 with the model named, no traceback."""
    err = _LocalModelRejectedError(
        "Model 'gpt-5' was rejected by the backend: Model \"gpt-5\" is not available"
    )
    monkeypatch.setattr(cli_main, "select_provider", _raise(err))

    result = runner.invoke(app, ["draft", "some-unit"])
    assert result.exit_code == 1, result.output
    assert "gpt-5" in result.output
    assert "Traceback" not in result.output


def test_backend_unavailable_renders_exit_1_with_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ERR-02: a BackendUnavailableError exits 1 with the existing prefix."""
    err = _LocalBackendUnavailableError("Copilot backend error (JSON-RPC -32000): boom")
    monkeypatch.setattr(cli_main, "select_provider", _raise(err))

    result = runner.invoke(app, ["draft", "some-unit"])
    assert result.exit_code == 1, result.output
    assert "Copilot backend unavailable:" in result.output


def test_unrelated_runtime_error_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The classifier handles only the two named domain errors; others propagate."""
    monkeypatch.setattr(
        cli_main, "select_provider", _raise(RuntimeError("unexpected"))
    )

    result = runner.invoke(app, ["draft", "some-unit"])
    # A re-raised RuntimeError surfaces as a non-1 failure (Typer wraps it), never
    # a clean exit-0 — the message is not classified as a handled backend error.
    assert result.exit_code != 0
    assert "Copilot backend unavailable:" not in result.output
