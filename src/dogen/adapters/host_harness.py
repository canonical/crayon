"""The host-harness *passenger* :class:`DraftingProvider` (DRAFT-05, D-18).

Where :class:`~dogen.adapters.copilot.CopilotDraftingProvider` is the *driver*
(a headless, bounded-toolset SDK session that generates a draft and reports its
own provenance), this passenger records a draft the **host agent** already
produced. It is constructed *with* the host's text — the port signature stays
unchanged (D-01) — and its :meth:`~HostHarnessDraftingProvider.draft_unit`
ignores ``sources`` and returns that text as a :class:`DraftResult`.

The provenance it reports is *delegated* and honest-empty (D-13): dogen observed
no reads and ran no tools, so ``context_origins``/``tools_used`` are always
empty, ``sdk`` is ``""`` (this provider imports no vendor SDK, D-18),
``model``/``model_version`` are ``""`` (unknown) unless the host asserts them —
recording the provider name as a "model" would be a falsehood — and ``mode`` is
``"passenger"`` (D-12/D-14), the marker that the whole record is for a
generation dogen did not itself drive. This closes repudiation threat T-03-03:
a passenger can never fabricate a copilot-SDK/driver provenance for text it
merely transcribed.

The module imports **only** from :mod:`dogen.core` — no ``copilot`` /
``github_copilot_sdk`` symbol anywhere — so the provider seam guards
(``scripts/seam_check.py`` + the import-linter contract) stay green with no
contract change (D-18).
"""

from dogen.core.models import DraftResult, Intent, Signoff, SourceRef
from dogen.core.ports import DraftingProvider


class HostHarnessDraftingProvider:
    """A text-in :class:`DraftingProvider` that records a host-produced draft.

    The passenger holds the host's draft text at construction and returns it
    verbatim from :meth:`draft_unit`, ignoring ``sources`` entirely: dogen did
    not read anything to produce this draft, so it must not claim it did (D-13).
    Imports no vendor SDK (D-18).
    """

    def __init__(
        self,
        *,
        draft_text: str,
        model: str = "",
        model_version: str = "",
        pages: dict[str, str] | None = None,
    ) -> None:
        """Hold the host's draft text and optional asserted model identity.

        Parameters
        ----------
        draft_text : str
            The **primary** page the host agent produced; returned verbatim by
            :meth:`draft_unit`. dogen never mutates the on-disk handoff this was
            read from — it only records this text (the compose root passes pure
            text, Plan 05).
        model : str
            The host-asserted model name; ``""`` (unknown, D-13) when the host
            asserts none — the provider name is never recorded as a model.
        model_version : str
            The host-asserted model version; same ``""`` convention.
        pages : dict of str to str or None
            The host's extra pages for a multi-file unit (v1.2), keyed by
            docs-relative target; empty for the ordinary one-page unit.
        """
        self._text = draft_text
        self._model = model
        self._model_version = model_version
        self._pages = dict(pages or {})

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
        """Return the held host text as a delegated, honest-empty draft result.

        Parameters
        ----------
        intent : Intent
            The Diátaxis direction (accepted to satisfy the port; unused — the
            host already produced the draft).
        audience : str
            Who the page is written for (accepted for the port; unused).
        signoff : Signoff
            The recorded HITL gate act (accepted for the port; unused — the
            orchestrator gate, not this provider, enforces its presence).
        sources : list of SourceRef
            The human-pointed sources — deliberately **ignored**: dogen read
            nothing to make this draft, so a passenger with ``sources=[]`` and
            with ``sources=[ref]`` returns identical output (D-13).
        notes : list of str
            The unit's steering notes — likewise ignored: the host agent
            already read the stream from disk before authoring (v1).
        page_format : str
            The unit's page format — likewise ignored: the host authored the
            handoff in the target's markup already (v1.2).

        Returns
        -------
        DraftResult
            The host text with delegated provenance: ``context_origins`` and
            ``tools_used`` honest-empty, ``output_tokens=0``, ``run_id=""``,
            ``sdk=""`` (SDK-free, D-14) and ``mode="passenger"`` (D-12).
        """
        return DraftResult(
            text=self._text,
            pages=dict(self._pages),
            model=self._model,
            model_version=self._model_version,
            output_tokens=0,
            run_id="",
            # Honest-empty delegated provenance (D-13): dogen observed no reads
            # and ran no tools, so it records nothing rather than fabricating the
            # unit's human-pointed sources as agent-read context (T-03-03).
            context_origins=[],
            tools_used=[],
            # D-14/D-12: SDK-free (this module imports no vendor SDK, D-18) and
            # the whole record is a passenger generation dogen did not drive.
            sdk="",
            mode="passenger",
        )


def _make_host_harness_provider(
    *,
    draft_text: str,
    model: str | None = None,
    model_version: str | None = None,
    pages: dict[str, str] | None = None,
) -> DraftingProvider:
    """Construct the passenger behind the port, holding the host draft text.

    Mirrors :func:`~dogen.adapters.mock_provider._make_copilot_provider`'s shape
    (a uniform factory the compose root threads by name), but is constructed
    **with** ``draft_text`` and needs no lazy import — there is no SDK to defer
    (D-18). Only explicitly-asserted ``model``/``model_version`` are forwarded so
    the provider's ``""`` (unknown) default applies when the host asserts none
    (D-13).

    Parameters
    ----------
    draft_text : str
        The host-produced draft text (read at the compose root from
        ``--draft-file`` as pure text, Plan 05 — never a filesystem path here).
    model : str or None
        The host-asserted model name; ``None`` leaves the ``""`` default.
    model_version : str or None
        The host-asserted model version; ``None`` leaves the ``""`` default.
    pages : dict of str to str or None
        Extra pages for a multi-file unit (v1.2), keyed by docs-relative
        target.

    Returns
    -------
    DraftingProvider
        A fresh :class:`HostHarnessDraftingProvider` holding ``draft_text``.
    """
    # Forward only the explicitly-asserted values so the provider's unknown
    # default stands for anything the host omitted (keeping each argument's
    # precise non-optional ``str`` type at the constructor boundary).
    kwargs: dict[str, str] = {}
    if model is not None:
        kwargs["model"] = model
    if model_version is not None:
        kwargs["model_version"] = model_version
    return HostHarnessDraftingProvider(draft_text=draft_text, pages=pages, **kwargs)
