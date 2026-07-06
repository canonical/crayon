"""A deterministic, SDK-free :class:`DraftingProvider` for CI and tests (D-23).

This is the second provider that proves the seam (SEAM-03/D-26): it implements
the exact same domain port as the real Copilot adapter but imports **no SDK and
touches no network**, so the whole ``steer → draft → review`` loop and every F1
write run in CI with no Copilot token (D-24). The draft it returns is a small
valid MyST snippet derived **only** from its inputs — same inputs yield a
byte-identical ``DraftResult`` (coding-guide §4: no wall-clock, no randomness).

``select_provider`` is the by-name dispatch (D-25): ``"mock"`` resolves here
eagerly; ``"copilot"`` is resolved lazily so the mock path never imports
``adapters/copilot/`` (and works before the real adapter exists, plan 03);
``"host-harness"`` resolves through an SDK-free wrapper over the passenger
factory (D-18). ``"auto"`` is not a factory key — it resolves to a concrete
``"copilot"``/``"host-harness"`` name via an **offline** capability probe
(SDK importable + auth env present + not disabled; no network, D-05) *before*
the dict lookup, and never yields ``"mock"`` (D-06).
"""

import importlib.util
import os
from collections.abc import Callable
from typing import TypedDict

from dogen.adapters.host_harness import _make_host_harness_provider
from dogen.core.models import DraftResult, Effort, Intent, Signoff, SourceRef
from dogen.core.ports import DraftingProvider


class _CopilotKwargs(TypedDict, total=False):
    """Type-precise kwargs forwarded to ``CopilotDraftingProvider`` (D-25).

    ``total=False`` so only the explicitly-set values are passed, letting the
    adapter's own defaults apply for anything the operator omitted, while keeping
    each argument's precise type (``model: str`` / ``effort: Effort``).
    """

    model: str
    effort: Effort


_MOCK_MODEL = "mock-model"
_MOCK_MODEL_VERSION = "mock-1"
# A fixed synthetic token count: deterministic provenance input, never measured.
_MOCK_OUTPUT_TOKENS = 128

# Selection surface (D-06). ``auto`` is the default; it is NOT a factory key —
# it resolves to a concrete name via the offline probe below.
_AUTO_PROVIDER = "auto"
_COPILOT_PROVIDER = "copilot"
_HOST_HARNESS_PROVIDER = "host-harness"
_DEFAULT_PROVIDER = _AUTO_PROVIDER

# The offline capability signals (D-05). The auth env var is the SDK's own token
# variable, confirmed against ``github-copilot-sdk==1.0.2`` in Plan 03-03 (OQ-1):
# the SDK spawns its runtime with ``--auth-token-env COPILOT_SDK_AUTH_TOKEN``.
# ``DOGEN_DISABLE_COPILOT`` lets an operator/CI force the passenger without
# unsetting the token (the D-05 "not explicitly disabled" signal).
_COPILOT_AUTH_ENV = "COPILOT_SDK_AUTH_TOKEN"
_COPILOT_DISABLE_ENV = "DOGEN_DISABLE_COPILOT"


class MockDraftingProvider:
    """A deterministic :class:`DraftingProvider` with no SDK import (D-23)."""

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
        """Return a canned, deterministic draft derived only from the inputs.

        Parameters
        ----------
        intent : Intent
            The Diátaxis direction to draft toward.
        audience : str
            Who the page is written for.
        signoff : Signoff
            The recorded HITL gate act that precedes this draft.
        sources : list of SourceRef
            The human-pointed sources to ground the draft in.
        notes : list of str
            The unit's steering notes (accepted for the port; the mock's
            output stays a pure function of intent/audience/signoff/sources
            so the deterministic byte-identity contract holds — D-23).
        page_format : str
            The unit's page format (v1.2): ``rst`` renders valid
            reStructuredText, anything else the MyST shape — a format-blind
            mock would silently write MyST fences into ``.rst`` pages in CI.

        Returns
        -------
        DraftResult
            A small valid page in the unit's format plus synthetic provenance
            inputs; identical arguments always produce a byte-identical
            ``text``.
        """
        renderer = _render_mock_rst if page_format == "rst" else _render_mock_myst
        text = renderer(
            intent=intent, audience=audience, signoff=signoff, sources=sources
        )
        return DraftResult(
            text=text,
            model=_MOCK_MODEL,
            model_version=_MOCK_MODEL_VERSION,
            output_tokens=_MOCK_OUTPUT_TOKENS,
            run_id="",
            # The mock is the in-process *driver* double (D-12): it reports
            # mode="driver" and, being SDK-free (D-14), an empty sdk id — never
            # the copilot SDK identifier.
            sdk="",
            mode="driver",
        )


def _render_mock_myst(
    *,
    intent: Intent,
    audience: str,
    signoff: Signoff,
    sources: list[SourceRef],
) -> str:
    """Render a deterministic MyST page body from the draft inputs.

    Parameters
    ----------
    intent : Intent
        The Diátaxis direction.
    audience : str
        The target audience.
    signoff : Signoff
        The recorded gate act (its author labels the synthetic draft).
    sources : list of SourceRef
        The human-pointed sources, listed deterministically.

    Returns
    -------
    str
        A small, valid MyST Markdown document.
    """
    listed = ", ".join(s.path or s.ref or "" for s in sources) or "no sources"
    return (
        f"# {intent.value.title()} for {audience}\n\n"
        f"Drafted under steering by {signoff.author}.\n\n"
        "```{note}\n"
        "Deterministic mock draft — no model was called.\n"
        "```\n\n"
        f"Grounded in: {listed}.\n"
    )


def _render_mock_rst(
    *,
    intent: Intent,
    audience: str,
    signoff: Signoff,
    sources: list[SourceRef],
) -> str:
    """Render a deterministic reStructuredText page body from the draft inputs.

    The rst twin of :func:`_render_mock_myst` (v1.2): an ``.rst`` unit drafted
    through the mock gets valid rST — title underline at title length, a
    ``.. note::`` directive — never MyST fences that Sphinx would render as
    literal text.

    Parameters
    ----------
    intent : Intent
        The Diátaxis direction.
    audience : str
        The target audience.
    signoff : Signoff
        The recorded gate act (its author labels the synthetic draft).
    sources : list of SourceRef
        The human-pointed sources, listed deterministically.

    Returns
    -------
    str
        A small, valid reStructuredText document.
    """
    listed = ", ".join(s.path or s.ref or "" for s in sources) or "no sources"
    title = f"{intent.value.title()} for {audience}"
    return (
        f"{title}\n{'=' * len(title)}\n\n"
        f"Drafted under steering by {signoff.author}.\n\n"
        ".. note::\n\n"
        "   Deterministic mock draft — no model was called.\n\n"
        f"Grounded in: {listed}.\n"
    )


def _make_mock_provider(
    *,
    model: str | None = None,
    effort: Effort | None = None,
    draft_text: str | None = None,
    model_version: str | None = None,
    pages: dict[str, str] | None = None,
) -> DraftingProvider:
    """Construct the mock provider behind the port type.

    Parameters
    ----------
    model : str or None
        Intentionally ignored — the deterministic mock calls no model (D-23/D-25).
        Accepted only to keep the factory signature uniform with the others.
    effort : Effort or None
        Intentionally ignored, for the same reason as ``model``.
    draft_text : str or None
        Intentionally ignored — the host draft text is the passenger's input,
        accepted only for the uniform factory signature.
    model_version : str or None
        Intentionally ignored, for the same reason as ``draft_text``.

    Returns
    -------
    DraftingProvider
        A fresh :class:`MockDraftingProvider`.
    """
    # Every argument is deliberately dropped: the mock is SDK-free and
    # deterministic, so nothing an operator passes can affect its output.
    return MockDraftingProvider()


def _make_copilot_provider(
    *,
    model: str | None = None,
    effort: Effort | None = None,
    draft_text: str | None = None,
    model_version: str | None = None,
    pages: dict[str, str] | None = None,
) -> DraftingProvider:
    """Lazily construct the real Copilot provider behind the port.

    The import is deferred so the mock path never loads ``adapters/copilot/``
    (and so the SDK is only imported when the copilot provider is actually
    selected — D-25).

    Parameters
    ----------
    model : str or None
        The drafting model to request; ``None`` leaves the adapter on its own
        default (``gpt-5-mini``).
    effort : Effort or None
        The reasoning effort for the pass; ``None`` leaves the adapter default.
    draft_text : str or None
        Intentionally ignored — the driver generates its own text; accepted only
        for the uniform factory signature (it is the passenger's input).
    model_version : str or None
        Intentionally ignored — the driver reports its own version; accepted only
        for the uniform factory signature.

    Returns
    -------
    DraftingProvider
        The real Copilot drafting provider.
    """
    # Deliberately deferred (D-25): a top-level import would load the SDK on the
    # mock/CI path, defeating the seam's whole point. The real
    # CopilotDraftingProvider was lifted in Plan 03-02, so this lazy
    # forward-reference now resolves at runtime.
    from dogen.adapters.copilot import (  # noqa: PLC0415
        CopilotDraftingProvider,
    )

    # Forward only the explicitly-set values so the adapter's own defaults apply
    # when the operator passed nothing — keeping each argument's precise type
    # (the adapter declares non-optional ``model: str`` / ``effort: Effort``).
    kwargs: _CopilotKwargs = {}
    if model is not None:
        kwargs["model"] = model
    if effort is not None:
        kwargs["effort"] = effort
    return CopilotDraftingProvider(**kwargs)


def _make_host_harness(
    *,
    model: str | None = None,
    effort: Effort | None = None,
    draft_text: str | None = None,
    model_version: str | None = None,
    pages: dict[str, str] | None = None,
) -> DraftingProvider:
    """Adapt the passenger factory to the uniform dict-dispatch signature (D-18).

    A thin uniform-signature wrapper over
    :func:`~dogen.adapters.host_harness._make_host_harness_provider` so the
    ``"host-harness"`` factory shares the ``(*, model, effort, draft_text,
    model_version)`` shape of the others and needs no ``if/elif`` at the call
    site. The passenger imports **no SDK** (D-18), so this needs no lazy import.

    Parameters
    ----------
    model : str or None
        The host-asserted model name; forwarded to the passenger (``None`` leaves
        its ``""`` unknown default, D-13).
    effort : Effort or None
        Intentionally ignored — the passenger records host-produced text and ran
        no model, so a reasoning effort is meaningless here (accepted only for the
        uniform signature).
    draft_text : str or None
        The host's draft text, read at the compose root from ``--draft-file``
        (Plan 05). Defaults to ``""`` when omitted so a bare
        ``select_provider("host-harness")`` (e.g. an ``auto`` resolution probed at
        selection time) still yields a valid passenger; the compose root always
        supplies the real text before a draft runs.
    model_version : str or None
        The host-asserted model version; forwarded like ``model``.

    Returns
    -------
    DraftingProvider
        A :class:`~dogen.adapters.host_harness.HostHarnessDraftingProvider`
        holding ``draft_text``.
    """
    return _make_host_harness_provider(
        draft_text=draft_text if draft_text is not None else "",
        model=model,
        model_version=model_version,
        pages=pages,
    )


# Dict dispatch, not an if/elif ladder (coding-guide §2). Each value is a factory
# so the copilot branch stays a lazy import (D-25). The factories share a uniform
# ``(*, model, effort, draft_text, model_version)`` signature so ``select_provider``
# threads every name through without branching. ``"auto"`` is deliberately absent:
# it is resolved to a concrete key by :func:`resolve_auto_provider` first (D-06).
_PROVIDER_FACTORIES: dict[str, Callable[..., DraftingProvider]] = {
    "mock": _make_mock_provider,
    _COPILOT_PROVIDER: _make_copilot_provider,
    _HOST_HARNESS_PROVIDER: _make_host_harness,
}


def _copilot_sdk_importable() -> bool:
    """Return whether the Copilot SDK is importable — an OFFLINE check (D-05).

    Uses :func:`importlib.util.find_spec`, which locates the module via the
    import machinery **without executing it**: the SDK is not loaded onto the
    mock/host-harness path and no network is touched. Factored as its own
    function so selection tests monkeypatch it without a real SDK.

    Returns
    -------
    bool
        ``True`` if the ``copilot`` package can be located on ``sys.path``.
    """
    return importlib.util.find_spec("copilot") is not None


def _copilot_auth_env_present() -> bool:
    """Return whether the Copilot auth-token env var is set — OFFLINE (D-05).

    Reads :data:`os.environ` only (presence of the token *string*, never a
    validation round-trip). Factored so tests inject the signal by monkeypatch.

    Returns
    -------
    bool
        ``True`` if ``COPILOT_SDK_AUTH_TOKEN`` is present and non-empty.
    """
    return bool(os.environ.get(_COPILOT_AUTH_ENV))


def _copilot_disabled() -> bool:
    """Return whether Copilot selection is explicitly disabled — OFFLINE (D-05).

    Lets an operator or CI force the passenger (``DOGEN_DISABLE_COPILOT``)
    without unsetting the auth token. Factored so tests inject the signal.

    Returns
    -------
    bool
        ``True`` if ``DOGEN_DISABLE_COPILOT`` is present and non-empty.
    """
    return bool(os.environ.get(_COPILOT_DISABLE_ENV))


def _probe_copilot_available() -> bool:
    """Combine the three OFFLINE signals into a Copilot-availability verdict (D-05).

    Copilot is considered available when it is not explicitly disabled AND the
    SDK is importable AND an auth token is present — all cheap local reads, no
    network at selection time. A genuinely-down backend still surfaces later as
    ``BackendUnavailableError`` at draft time (no silent live downgrade).

    Returns
    -------
    bool
        ``True`` when the driver should be auto-selected, else ``False``.
    """
    return (
        not _copilot_disabled()
        and _copilot_sdk_importable()
        and _copilot_auth_env_present()
    )


def resolve_auto_provider() -> str:
    """Resolve ``"auto"`` to a concrete provider name via the offline probe (D-06).

    Returns ``"copilot"`` when :func:`_probe_copilot_available` signals the driver
    is usable, else the ``"host-harness"`` passenger. It **never** returns
    ``"mock"`` — the deterministic double is explicitly selectable but is never
    auto-picked (D-06). The composition root reuses this so it can branch on the
    resolved name (e.g. reading ``--draft-file`` for the passenger).

    Returns
    -------
    str
        Either ``"copilot"`` or ``"host-harness"``.
    """
    return _COPILOT_PROVIDER if _probe_copilot_available() else _HOST_HARNESS_PROVIDER


def select_provider(  # noqa: PLR0913
    name: str = _DEFAULT_PROVIDER,
    *,
    model: str | None = None,
    effort: Effort | None = None,
    draft_text: str | None = None,
    model_version: str | None = None,
    pages: dict[str, str] | None = None,
) -> DraftingProvider:
    """Resolve a provider by name (D-25/D-06); default ``"auto"``.

    ``"auto"`` is resolved to a concrete ``"copilot"``/``"host-harness"`` name
    via the offline probe (:func:`resolve_auto_provider`) **before** the
    dict lookup — ``"auto"`` is never a factory key and never yields ``"mock"``.

    Parameters
    ----------
    name : str
        The provider name (``"auto"``, ``"copilot"``, ``"host-harness"`` or
        ``"mock"``); defaults to ``"auto"`` (D-06).
    model : str or None
        The drafting model to request; threaded to the copilot adapter and the
        passenger, ignored by the mock. ``None`` leaves each provider on its own
        default (LIVE-01).
    effort : Effort or None
        The reasoning effort to request; threaded to the copilot adapter, ignored
        by the mock and the passenger. ``None`` leaves the adapter default.
    draft_text : str or None
        The host-produced draft text for the ``"host-harness"`` passenger (read at
        the compose root from ``--draft-file``); ignored by the other providers.
    model_version : str or None
        The host-asserted model version for the passenger; ignored otherwise.

    Returns
    -------
    DraftingProvider
        The selected provider instance.

    Raises
    ------
    ValueError
        If ``name`` is not a known provider.
    """
    if name == _AUTO_PROVIDER:
        name = resolve_auto_provider()
    try:
        factory = _PROVIDER_FACTORIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(_PROVIDER_FACTORIES))
        raise ValueError(f"unknown provider {name!r}; choose one of: {known}") from exc
    return factory(
        model=model,
        effort=effort,
        draft_text=draft_text,
        model_version=model_version,
        pages=pages,
    )
