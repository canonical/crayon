"""Draft-path JSON-RPC error mapping (ERR-01/ERR-02, no network).

A scripted ``_StubClient`` (``tests/conftest.py``) injects a fake ``JsonRpcError``
or ``ProcessExitedError`` into the draft and the provider must translate it into a
handled domain error — never leak a raw SDK traceback:

* a ``-32603`` "is not available" rejection → :class:`ModelRejectedError` whose
  message names the **requested** model (``self._model``, not the parsed backend
  string) (ERR-01, D-07);
* every other ``JsonRpcError`` — including the **overloaded** ``-32603`` "Directory
  path must be absolute" and any non-``-32603`` code — plus a ``ProcessExitedError``
  → :class:`BackendUnavailableError`, NOT ``ModelRejectedError`` (ERR-02, Pitfall 1).

No live SDK call or network access occurs: pytest only touches the stubs.
"""

import pytest
from copilot._jsonrpc import JsonRpcError, ProcessExitedError

from dogen.adapters.copilot.provider import (
    BackendUnavailableError,
    CopilotDraftingProvider,
    ModelRejectedError,
)
from tests.conftest import _draft


@pytest.mark.asyncio
async def test_model_not_available_raises_model_rejected_naming_requested_model(
    install_stub_client,
) -> None:
    """ERR-01: a ``-32603`` "is not available" → ``ModelRejectedError``.

    The message must contain the model the operator *requested* (``self._model``),
    not the model string parsed out of the backend error (D-07).
    """
    error = JsonRpcError(-32603, 'Model "gpt-5" is not available')
    stub = install_stub_client(send_error=error)
    provider = CopilotDraftingProvider(model="gpt-5")

    with pytest.raises(ModelRejectedError) as excinfo:
        await _draft(provider)
    assert "gpt-5" in str(excinfo.value)
    assert stub.session_kwargs is not None


@pytest.mark.asyncio
async def test_model_rejection_reports_requested_not_backend_model(
    install_stub_client,
) -> None:
    """ERR-01/D-07: the requested model is reported even when it differs.

    The backend names ``other-model`` but the operator requested ``gpt-5-mini``;
    the surfaced error must name the requested one.
    """
    error = JsonRpcError(-32603, 'Model "other-model" is not available')
    install_stub_client(send_error=error)
    provider = CopilotDraftingProvider(model="gpt-5-mini")

    with pytest.raises(ModelRejectedError) as excinfo:
        await _draft(provider)
    assert "gpt-5-mini" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        # -32603 is OVERLOADED: this one is NOT a model rejection (Pitfall 1).
        JsonRpcError(-32603, "Directory path must be absolute"),
        # A non-(-32603) JSON-RPC error: a generic transport/internal failure.
        JsonRpcError(-32000, "internal backend failure"),
        # The CLI process exited mid-draft.
        ProcessExitedError("copilot process exited"),
    ],
)
async def test_other_backend_errors_map_to_backend_unavailable(
    install_stub_client, error: Exception
) -> None:
    """ERR-02: every non-model-rejection backend error → ``BackendUnavailableError``.

    A ``-32603`` whose message is NOT the model-not-available signature, a
    non-``-32603`` ``JsonRpcError``, and a ``ProcessExitedError`` must all map to
    ``BackendUnavailableError`` and NOT to ``ModelRejectedError`` (the Pitfall-1
    both-conditions guard).
    """
    install_stub_client(send_error=error)
    provider = CopilotDraftingProvider(model="gpt-5-mini")

    with pytest.raises(BackendUnavailableError):
        await _draft(provider)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        # A status-path ``-32603`` whose message LOOKS like a model rejection
        # (CR-01): an entitlement/quota failure during the status probe. It must
        # NOT be run through the model-rejection mapping — it has nothing to do
        # with the requested model.
        JsonRpcError(-32603, 'Model "gpt-5-mini" is not available'),
        # A plain status-path JSON-RPC error.
        JsonRpcError(-32000, "status backend failure"),
        # The CLI process exited during the status probe.
        ProcessExitedError("copilot process exited during status check"),
    ],
)
async def test_status_path_errors_map_to_backend_unavailable_not_model_rejected(
    install_stub_client, error: Exception
) -> None:
    """CR-01: status-probe ``JsonRpcError``/``ProcessExitedError`` → ERR-02.

    ``_require_available_backend`` runs ``get_status``/``get_auth_status`` before
    the draft. A ``JsonRpcError`` or ``ProcessExitedError`` raised there must be
    classified as ``BackendUnavailableError`` (ERR-02), never escape to the
    draft-path model-rejection mapping — even a ``-32603`` "is not available"
    status error, which is a backend/entitlement failure, not a model rejection.
    """
    install_stub_client(status_error=error)
    provider = CopilotDraftingProvider(model="gpt-5-mini")

    with pytest.raises(BackendUnavailableError):
        await _draft(provider)
