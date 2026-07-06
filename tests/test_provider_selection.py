"""Offline provider auto-selection (DRAFT-06, D-05/D-06).

These tests exercise the selection seam with **no network and no real SDK**: the
three capability signals the offline probe reads (Copilot SDK importable, an auth
env present, selection not explicitly disabled) are injected by monkeypatch, so
``resolve_auto_provider`` / ``select_provider('auto')`` are decided purely from
substituted signals. They cover the ``-k auto`` resolution (present -> copilot,
absent -> host-harness) and the ``-k precedence`` rules (``mock`` explicitly
selectable, ``auto`` never yields ``mock``, ``auto`` is not a factory key, an
unknown name raises ``ValueError``). The flag > env > auto precedence across the
CLI surface is exercised at the compose layer (``resolve_provider_name``) below.
"""

from pathlib import Path

import pytest

from dogen.adapters import mock_provider
from dogen.adapters.host_harness import HostHarnessDraftingProvider
from dogen.adapters.mock_provider import (
    MockDraftingProvider,
    resolve_auto_provider,
    select_provider,
)
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose


def _patch_signals(monkeypatch, *, importable, auth, disabled=False):
    """Substitute the three offline capability signals the probe reads."""
    monkeypatch.setattr(mock_provider, "_copilot_sdk_importable", lambda: importable)
    monkeypatch.setattr(mock_provider, "_copilot_auth_env_present", lambda: auth)
    monkeypatch.setattr(mock_provider, "_copilot_disabled", lambda: disabled)


# --- auto resolution (offline probe) ---------------------------------------


def test_auto_resolves_to_copilot_when_all_signals_present(monkeypatch):
    _patch_signals(monkeypatch, importable=True, auth=True, disabled=False)
    assert resolve_auto_provider() == "copilot"


def test_auto_resolves_to_host_harness_when_sdk_not_importable(monkeypatch):
    _patch_signals(monkeypatch, importable=False, auth=True)
    assert resolve_auto_provider() == "host-harness"


def test_auto_resolves_to_host_harness_when_auth_env_absent(monkeypatch):
    _patch_signals(monkeypatch, importable=True, auth=False)
    assert resolve_auto_provider() == "host-harness"


def test_auto_resolves_to_host_harness_when_explicitly_disabled(monkeypatch):
    _patch_signals(monkeypatch, importable=True, auth=True, disabled=True)
    assert resolve_auto_provider() == "host-harness"


def test_auto_via_select_provider_returns_passenger_when_unavailable(monkeypatch):
    # select_provider('auto') resolves to a concrete name BEFORE the dict lookup
    # and, when the probe is unavailable, builds the SDK-free passenger.
    _patch_signals(monkeypatch, importable=False, auth=False)
    provider = select_provider("auto")
    assert isinstance(provider, HostHarnessDraftingProvider)


def test_auto_probe_reads_real_env_signals(monkeypatch):
    # Exercise the real auth-env / disabled signal readers against os.environ
    # (still offline: presence of a token string is not a network round-trip).
    monkeypatch.setattr(mock_provider, "_copilot_sdk_importable", lambda: True)
    monkeypatch.delenv("DOGEN_DISABLE_COPILOT", raising=False)
    monkeypatch.setenv("COPILOT_SDK_AUTH_TOKEN", "present")
    assert resolve_auto_provider() == "copilot"
    monkeypatch.setenv("DOGEN_DISABLE_COPILOT", "1")
    assert resolve_auto_provider() == "host-harness"
    monkeypatch.delenv("DOGEN_DISABLE_COPILOT", raising=False)
    monkeypatch.delenv("COPILOT_SDK_AUTH_TOKEN", raising=False)
    assert resolve_auto_provider() == "host-harness"


# --- precedence / selectability --------------------------------------------


def test_precedence_mock_is_explicitly_selectable():
    assert isinstance(select_provider("mock"), MockDraftingProvider)


def test_precedence_auto_is_not_a_factory_key():
    assert "auto" not in mock_provider._PROVIDER_FACTORIES


def test_precedence_auto_never_resolves_to_mock(monkeypatch):
    for importable in (True, False):
        for auth in (True, False):
            for disabled in (True, False):
                _patch_signals(
                    monkeypatch, importable=importable, auth=auth, disabled=disabled
                )
                assert resolve_auto_provider() != "mock"


def test_precedence_unknown_provider_name_raises_valueerror():
    with pytest.raises(ValueError, match="unknown provider"):
        select_provider("banana")


def test_precedence_host_harness_selectable_by_name_carries_text():
    provider = select_provider("host-harness", draft_text="host draft")
    assert isinstance(provider, HostHarnessDraftingProvider)
    assert provider._text == "host draft"


# --- compose-layer precedence (flag > env > config > host-harness) ---------


def test_precedence_flag_beats_env_and_auto(monkeypatch):
    # An explicit --provider wins even when DOGEN_PROVIDER and the probe disagree.
    _patch_signals(monkeypatch, importable=True, auth=True)
    assert compose.resolve_provider_name("host-harness", "mock") == "host-harness"


def test_precedence_env_beats_auto_when_no_flag(monkeypatch):
    # DOGEN_PROVIDER=mock (CI's pin) is honoured when no explicit flag is given,
    # over what the offline probe would auto-resolve.
    _patch_signals(monkeypatch, importable=True, auth=True)
    assert compose.resolve_provider_name(None, "mock") == "mock"


def test_precedence_defaults_to_host_harness_regardless_of_probe(monkeypatch):
    # v1 (RC-5): no flag, env, or config means the hardened host-harness
    # default — even when every Copilot capability signal is present. The
    # probe never selects a provider.
    _patch_signals(monkeypatch, importable=True, auth=True)
    assert compose.resolve_provider_name(None, None, None) == "host-harness"
    _patch_signals(monkeypatch, importable=False, auth=False)
    assert compose.resolve_provider_name(None, None, None) == "host-harness"


def test_precedence_repo_config_beats_default_and_env_beats_config():
    # v1: repo config is the third precedence level; env still outranks it.
    assert compose.resolve_provider_name(None, None, "copilot") == "copilot"
    assert compose.resolve_provider_name(None, "mock", "copilot") == "mock"


def test_precedence_auto_is_retired_and_rejected():
    # v1: "auto" is no longer a selection value at any precedence level.
    with pytest.raises(ValueError, match="retired"):
        compose.resolve_provider_name("auto", None, None)
    with pytest.raises(ValueError, match="retired"):
        compose.resolve_provider_name(None, "auto", None)
    with pytest.raises(ValueError, match="retired"):
        compose.resolve_provider_name(None, None, "auto")


def test_build_draft_request_stamps_resolved_provider_name():
    # Pitfall 7: the stamped provider name follows the resolved provider, not a
    # hardcoded "mock". Default (no provider) still stamps "mock".
    store = FilesystemPlanningStore()
    default_req = compose.build_draft_request("u", root=Path("."), store=store)
    assert default_req.provider_name == "mock"
    passenger = select_provider("host-harness", draft_text="x")
    hh_req = compose.build_draft_request(
        "u",
        root=Path("."),
        store=store,
        provider=passenger,
        provider_name="host-harness",
    )
    assert hh_req.provider_name == "host-harness"


def test_make_provider_host_harness_reads_draft_file(tmp_path, monkeypatch):
    # The compose root reads --draft-file into pure passenger text; core/ never
    # sees the path. Observability is configured (send_to_logfire=False, no net).
    draft = tmp_path / "handoff.md"
    draft.write_text("# Host draft\n\nbody\n", encoding="utf-8")
    provider = compose.make_provider("host-harness", draft_file=draft)
    assert isinstance(provider, HostHarnessDraftingProvider)
    assert provider._text == "# Host draft\n\nbody\n"


def test_make_provider_host_harness_requires_draft_file():
    with pytest.raises(ValueError, match="requires --draft-file"):
        compose.make_provider("host-harness")
