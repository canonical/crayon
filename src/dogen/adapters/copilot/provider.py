"""The real Copilot drafting provider — the sole ``github-copilot-sdk`` importer.

:class:`CopilotDraftingProvider` implements the same ``core.ports.DraftingProvider``
port the deterministic mock proved (SEAM-03 swappability from both sides), so the
orchestrator drives it unchanged. It opens a bounded read-only Copilot session
(allowlist ``grep``/``glob``/``view`` from :mod:`.tools`), sends the composed
drafting prompt, and translates the result through :func:`.mapping.to_draft_result`
so no SDK shape reaches ``core/``.

A down, unauthenticated, or transport-broken backend (Copilot CLI auto-update
breaking JSON-RPC, issue #1606) is converted into a handled
:class:`BackendUnavailableError` — a clear message and a nonzero CLI exit, never
a crash (SKEL-05/D-27, threat T-02.3-03).

Runtime facts honoured here (confirmed against the authenticated CLI ``1.0.64-0``):

* ``create_session`` is a **coroutine** — it must be ``await``ed, and its result
  is itself an async context manager (RESEARCH Pitfall 2).
* ``working_directory`` **must be an absolute path** — a relative value such as
  ``"."`` is rejected with JSON-RPC ``-32603`` ("Directory path must be absolute").
"""

import os
from collections.abc import Iterable

from copilot import (
    CopilotClient,
    SessionEvent,
    SessionEventType,
    StopError,
)

# ``JsonRpcError``/``ProcessExitedError`` live in the SDK's private ``_jsonrpc``
# module (not re-exported in ``copilot.__all__``). Importing a private symbol is
# sanctioned ONLY inside this adapter subtree (SEAM-01); the D-08 regression guard
# fails loudly if an SDK bump moves it, rather than silently dropping the catch.
from copilot._jsonrpc import JsonRpcError, ProcessExitedError
from copilot.session import PermissionHandler, SystemMessageAppendConfig

from dogen.adapters.copilot.mapping import (
    to_draft_result,
    tool_events_to_provenance,
)
from dogen.adapters.copilot.tools import DENY, READONLY
from dogen.core.authoring import REFERENCE_CODE_RUBRIC, STANCE_CONTRACT
from dogen.core.models import (
    DraftResult,
    Effort,
    Intent,
    Signoff,
    SourceRef,
)

# Default drafting model and per-pass effort for the skeleton.
_DEFAULT_MODEL = "gpt-5-mini"
_DEFAULT_EFFORT: Effort = Effort.medium
# send_and_wait timeout (seconds) — the SDK default, made explicit here.
_DRAFT_TIMEOUT = 120.0
# JSON-RPC internal-error code the backend returns for a rejected model. It is
# OVERLOADED (also a generic catch-all internal error), so ERR-01 detection
# requires this code AND the not-available message signature (Pitfall 1).
_MODEL_NOT_AVAILABLE_CODE = -32603


class BackendUnavailableError(RuntimeError):
    """The Copilot backend is down, unauthenticated, or its transport broke.

    Raised instead of letting a raw SDK/connection failure crash the loop, so
    the CLI can surface a clear message and a nonzero exit (SKEL-05/D-27).
    """


class ModelRejectedError(RuntimeError):
    """The backend rejected the requested drafting model (ERR-01/D-06).

    Raised when ``create_session``/``send_and_wait`` fails with a JSON-RPC
    ``-32603`` whose message carries the model-not-available signature. Its
    message names the model the operator *requested* (``self._model``, D-07),
    not the string parsed out of the backend error. The CLI classifies it by
    type name (no SDK import, D-25) into a clean nonzero exit (ERR-01).
    """


def _is_gpt5_family(model: str) -> bool:
    """Return whether ``model`` belongs to the GPT-5 family (D-05).

    Parameters
    ----------
    model : str
        The requested model name.

    Returns
    -------
    bool
        ``True`` for any ``gpt-5*`` model. A prefix match is forward-safe and
        omit-on-doubt: unknown/Claude families return ``False`` so
        ``reasoning_effort`` is withheld for them.
    """
    return model.startswith("gpt-5")


def _is_model_not_available(message: str) -> bool:
    """Return whether a backend message is the model-not-available signature.

    Parameters
    ----------
    message : str
        The ``JsonRpcError.message`` text from the backend.

    Returns
    -------
    bool
        ``True`` when the message carries the "is not available" signature
        (D-07: detect by signature, never parse the model name out of it).
    """
    return "is not available" in message.lower()


class CopilotDraftingProvider:
    """A real :class:`~dogen.core.ports.DraftingProvider` on the Copilot SDK.

    Parameters
    ----------
    model : str
        The drafting model to request; defaults to ``gpt-5-mini``.
    effort : Effort
        The reasoning effort for the pass; defaults to ``medium``.
    working_directory : str or None
        Absolute repo-root path the session looks up sources in. ``None``
        resolves to the current working directory (always made absolute).
    """

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        effort: Effort = _DEFAULT_EFFORT,
        working_directory: str | None = None,
    ) -> None:
        self._model = model
        self._effort = effort
        # The SDK rejects a relative working_directory; resolve to absolute.
        self._working_directory = os.path.abspath(working_directory or os.getcwd())

    async def draft_unit(  # noqa: PLR0913
        self,
        *,
        intent: Intent,
        audience: str,
        signoff: Signoff,
        sources: list[SourceRef],
        notes: list[str] | None = None,
        page_format: str = "myst",
    ) -> DraftResult:
        """Draft one unit on the real Copilot SDK behind the shared port.

        Parameters
        ----------
        intent : Intent
            The Diátaxis direction to draft toward.
        audience : str
            Who the page is written for.
        signoff : Signoff
            The recorded HITL gate act that precedes this draft.
        sources : list of SourceRef
            The declared sources — the primary grounding and the starting
            points for the session's read-only navigation (v1).
        notes : list of str
            The unit's steering notes, oldest first; folded into the drafting
            prompt so review-verdict corrections steer the re-draft (v1).
        page_format : str
            The unit's page format (v1.2); the prompt names the markup so an
            ``.rst`` unit is authored as reStructuredText, not MyST.

        Returns
        -------
        DraftResult
            The drafted page content plus provenance inputs, in domain terms.

        Raises
        ------
        ModelRejectedError
            If the backend rejected the requested model (a ``-32603`` with the
            not-available signature) — names the requested model (ERR-01/D-07).
        BackendUnavailableError
            If the backend is unavailable, unauthenticated, or its transport
            broke, or any other draft-path JSON-RPC / process-exit error
            occurred (a handled state, never a crash — SKEL-05/D-27, ERR-02).
        """
        prompt = _compose_prompt(
            intent, audience, sources, notes or [], page_format=page_format
        )
        steer = _compose_steering(intent, audience, signoff)
        try:
            return await self._run_draft(prompt, steer)
        except StopError as exc:
            raise BackendUnavailableError(
                f"Copilot backend stopped unexpectedly: {exc}"
            ) from exc
        except JsonRpcError as exc:
            raise self._map_jsonrpc_error(exc) from exc
        except ProcessExitedError as exc:
            raise BackendUnavailableError(
                f"Copilot backend process exited: {exc}"
            ) from exc
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise BackendUnavailableError(
                f"Copilot backend is unavailable: {exc}"
            ) from exc

    def _map_jsonrpc_error(self, exc: JsonRpcError) -> RuntimeError:
        """Classify a draft-path ``JsonRpcError`` into a handled domain error.

        Parameters
        ----------
        exc : JsonRpcError
            The raw SDK error raised on the draft path.

        Returns
        -------
        RuntimeError
            :class:`ModelRejectedError` when ``exc`` is a ``-32603`` carrying the
            model-not-available signature (ERR-01); otherwise a
            :class:`BackendUnavailableError` (ERR-02). The ``-32603`` overload is
            disambiguated by requiring BOTH conditions (Pitfall 1).
        """
        if exc.code == _MODEL_NOT_AVAILABLE_CODE and _is_model_not_available(
            exc.message
        ):
            return ModelRejectedError(
                f"Model {self._model!r} was rejected by the backend: {exc.message}"
            )
        return BackendUnavailableError(
            f"Copilot backend error (JSON-RPC {exc.code}): {exc.message}"
        )

    async def _run_draft(self, prompt: str, steer: str) -> DraftResult:
        """Open a bounded session, send the prompt, and map the result.

        Parameters
        ----------
        prompt : str
            The composed drafting instruction.
        steer : str
            The system-message steering text (intent + audience).

        Returns
        -------
        DraftResult
            The mapped domain result.

        Raises
        ------
        BackendUnavailableError
            If the pre-flight status check reports an unhealthy backend.
        """
        # D-05: send reasoning_effort only for GPT-5-family models; compute it to
        # None otherwise and pass it unconditionally — the SDK omits a falsy value
        # from the wire (client.py:1843), so Claude drafts no longer error on it.
        reasoning_effort = self._effort.value if _is_gpt5_family(self._model) else None
        async with CopilotClient() as client:
            await _require_available_backend(client)
            session_cm = await client.create_session(
                model=self._model,
                reasoning_effort=reasoning_effort,
                # D-04: auto-approve non-interactive read-only source lookups. Safe
                # by construction — only grep/glob/view are available; write/exec/
                # network tools are unavailable AND on DENY. Pass the staticmethod
                # reference, never call it (Pitfall 5).
                on_permission_request=PermissionHandler.approve_all,
                available_tools=READONLY,
                excluded_tools=DENY,
                working_directory=self._working_directory,
                system_message=SystemMessageAppendConfig(mode="append", content=steer),
            )
            async with session_cm as session:
                event = await session.send_and_wait(prompt, timeout=_DRAFT_TIMEOUT)
                # PROV-01/02: observe the full session history while the session
                # is still open — get_events() raises once it closes (Pitfall 3).
                events = await session.get_events()
        # Translate the observed events to the two domain lists in the mapping
        # seam (no event-shape handling here, D-04); honest-empty when none seen.
        context_origins, tools_used = tool_events_to_provenance(events)
        result = _require_assistant_message(event)
        # IN-03: report the effort the SDK actually ran at, so the recorded
        # provenance reflects the real effort rather than only the requested one.
        # PROV-01/02: attach what the agent actually read/ran via the same
        # established model_copy attach point, kept distinct from unit.sources.
        return result.model_copy(
            update={
                "effort_used": self._effort,
                "context_origins": context_origins,
                "tools_used": tools_used,
            }
        )


async def _require_available_backend(client: CopilotClient) -> None:
    """Fail fast with a handled error if the backend is not ready.

    Parameters
    ----------
    client : CopilotClient
        The connected SDK client to probe.

    Raises
    ------
    BackendUnavailableError
        If status or auth-status reports the backend cannot serve a draft,
        including any JSON-RPC or process-exit error during the status probe.
        A status-path ``-32603`` is classified here as backend-unavailable
        (ERR-02), never run through the model-rejection mapping (it has nothing
        to do with the requested model).
    """
    try:
        await client.get_status()
        await client.get_auth_status()
    except StopError as exc:
        raise BackendUnavailableError(
            f"Copilot backend status check failed: {exc}"
        ) from exc
    except JsonRpcError as exc:
        raise BackendUnavailableError(
            f"Copilot backend status check error (JSON-RPC {exc.code}): {exc.message}"
        ) from exc
    except ProcessExitedError as exc:
        raise BackendUnavailableError(
            f"Copilot backend process exited during status check: {exc}"
        ) from exc
    except (ConnectionError, OSError, TimeoutError) as exc:
        raise BackendUnavailableError(f"Copilot backend is unreachable: {exc}") from exc


def _require_assistant_message(event: SessionEvent | None) -> DraftResult:
    """Translate the final event into a ``DraftResult`` or fail clearly.

    Parameters
    ----------
    event : SessionEvent or None
        The final event returned by ``send_and_wait``.

    Returns
    -------
    DraftResult
        The mapped domain result.

    Raises
    ------
    BackendUnavailableError
        If no ``assistant.message`` event was produced (no draft to map).
    """
    if event is None or event.type is not SessionEventType.ASSISTANT_MESSAGE:
        raise BackendUnavailableError(
            "Copilot returned no assistant message to draft from"
        )
    # run_id is stamped by core/ from the active OTel trace; the adapter is not
    # the owner of correlation, so it passes through an empty placeholder that
    # the orchestrator overwrites when recording the generation.
    return to_draft_result(event, run_id="")


def _compose_prompt(
    intent: Intent,
    audience: str,
    sources: Iterable[SourceRef],
    notes: Iterable[str],
    *,
    page_format: str = "myst",
) -> str:
    """Compose the drafting instruction from domain inputs only.

    Parameters
    ----------
    intent : Intent
        The Diátaxis direction.
    audience : str
        The target audience.
    sources : iterable of SourceRef
        The declared sources — primary grounding and navigation starting
        points (v1: a starting set, not a boundary).
    notes : iterable of str
        The unit's steering notes, oldest first; review-verdict corrections
        arrive here so a re-draft actually applies them (v1).
    page_format : str
        The unit's page format (v1.2): the markup named in the instruction —
        ``rst`` → reStructuredText, else MyST Markdown.

    Returns
    -------
    str
        A plain-text drafting prompt carrying no SDK shapes.
    """
    listed = ", ".join(s.path or s.ref or "" for s in sources) or "no sources"
    steering_block = ""
    note_list = [n for n in notes if n]
    if note_list:
        joined = "\n".join(f"- {n}" for n in note_list)
        steering_block = f" Steering notes to honour, oldest first:\n{joined}\n"
    markup = "reStructuredText" if page_format == "rst" else "MyST Markdown"
    return (
        f"Draft a {intent.value} documentation page for {audience}, in {markup} "
        f"suitable for Sphinx. Start from these declared sources and "
        f"ground every claim in what you actually read: {listed}. You may "
        "navigate beyond them with the read-only tools when a fact's origin "
        "lies elsewhere; never assert what you have not read."
        f"{steering_block} "
        "Reference code entities by qualified name; do not reproduce their "
        f"source in the page. {REFERENCE_CODE_RUBRIC} {STANCE_CONTRACT}"
    )


def _compose_steering(intent: Intent, audience: str, signoff: Signoff) -> str:
    """Compose the system-message steering text from the recorded gate act.

    Parameters
    ----------
    intent : Intent
        The steered Diátaxis direction.
    audience : str
        The steered audience.
    signoff : Signoff
        The recorded signoff act (its author anchors accountability).

    Returns
    -------
    str
        The steering text appended to the session's system message.
    """
    return (
        f"You are drafting documentation under human steering recorded by "
        f"{signoff.author}. Direction: {intent.value}. Audience: {audience}. "
        "Draft only; never commit, push, or modify files. "
        f"{REFERENCE_CODE_RUBRIC}"
    )
