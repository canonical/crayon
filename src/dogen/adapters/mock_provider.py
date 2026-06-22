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

"""A deterministic, SDK-free :class:`DraftingProvider` for CI and tests (D-23).

This is the second provider that proves the seam (SEAM-03/D-26): it implements
the exact same domain port as the real Copilot adapter but imports **no SDK and
touches no network**, so the whole ``steer → draft → review`` loop and every F1
write run in CI with no Copilot token (D-24). The draft it returns is a small
valid MyST snippet derived **only** from its inputs — same inputs yield a
byte-identical ``DraftResult`` (coding-guide §4: no wall-clock, no randomness).

``select_provider`` is the by-name dispatch (D-25): ``"mock"`` resolves here
eagerly; ``"copilot"`` is resolved lazily so the mock path never imports
``adapters/copilot/`` (and works before the real adapter exists, plan 03).
"""

from collections.abc import Callable
from typing import TypedDict

from dogen.core.models import DraftResult, Effort, Intent, SourceRef, Steering
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
_DEFAULT_PROVIDER = "copilot"


class MockDraftingProvider:
    """A deterministic :class:`DraftingProvider` with no SDK import (D-23)."""

    async def draft_unit(
        self,
        *,
        intent: Intent,
        audience: str,
        steering: Steering,
        sources: list[SourceRef],
    ) -> DraftResult:
        """Return a canned, deterministic draft derived only from the inputs.

        Parameters
        ----------
        intent : Intent
            The Diátaxis direction to draft toward.
        audience : str
            Who the page is written for.
        steering : Steering
            The recorded HITL steering event that precedes this draft.
        sources : list of SourceRef
            The human-pointed sources to ground the draft in.

        Returns
        -------
        DraftResult
            A small valid MyST snippet plus synthetic provenance inputs;
            identical arguments always produce a byte-identical ``text``.
        """
        text = _render_mock_myst(
            intent=intent, audience=audience, steering=steering, sources=sources
        )
        return DraftResult(
            text=text,
            model=_MOCK_MODEL,
            model_version=_MOCK_MODEL_VERSION,
            output_tokens=_MOCK_OUTPUT_TOKENS,
            run_id="",
        )


def _render_mock_myst(
    *,
    intent: Intent,
    audience: str,
    steering: Steering,
    sources: list[SourceRef],
) -> str:
    """Render a deterministic MyST page body from the draft inputs.

    Parameters
    ----------
    intent : Intent
        The Diátaxis direction.
    audience : str
        The target audience.
    steering : Steering
        The recorded steering event (its author labels the synthetic draft).
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
        f"Drafted under steering by {steering.author}.\n\n"
        "```{note}\n"
        "Deterministic mock draft — no model was called.\n"
        "```\n\n"
        f"Grounded in: {listed}.\n"
    )


def _make_mock_provider(
    *, model: str | None = None, effort: Effort | None = None
) -> DraftingProvider:
    """Construct the mock provider behind the port type.

    Parameters
    ----------
    model : str or None
        Intentionally ignored — the deterministic mock calls no model (D-23/D-25).
        Accepted only to keep the factory signature uniform with the copilot one.
    effort : Effort or None
        Intentionally ignored, for the same reason as ``model``.

    Returns
    -------
    DraftingProvider
        A fresh :class:`MockDraftingProvider`.
    """
    # model/effort are deliberately dropped: the mock is SDK-free and deterministic,
    # so neither a model name nor a reasoning effort can affect its output.
    return MockDraftingProvider()


def _make_copilot_provider(
    *, model: str | None = None, effort: Effort | None = None
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

    Returns
    -------
    DraftingProvider
        The real Copilot drafting provider.
    """
    # Deliberately deferred (D-25): a top-level import would load the SDK on the
    # mock/CI path, defeating the seam's whole point.
    from dogen.adapters.copilot import CopilotDraftingProvider  # noqa: PLC0415

    # Forward only the explicitly-set values so the adapter's own defaults apply
    # when the operator passed nothing — keeping each argument's precise type
    # (the adapter declares non-optional ``model: str`` / ``effort: Effort``).
    kwargs: _CopilotKwargs = {}
    if model is not None:
        kwargs["model"] = model
    if effort is not None:
        kwargs["effort"] = effort
    return CopilotDraftingProvider(**kwargs)


# Dict dispatch, not an if/elif ladder (coding-guide §2). Each value is a
# factory so the copilot branch stays a lazy import (D-25). The factories share a
# uniform ``(*, model, effort)`` signature so ``select_provider`` threads both
# through by name without branching.
_PROVIDER_FACTORIES: dict[str, Callable[..., DraftingProvider]] = {
    "mock": _make_mock_provider,
    "copilot": _make_copilot_provider,
}


def select_provider(
    name: str = _DEFAULT_PROVIDER,
    *,
    model: str | None = None,
    effort: Effort | None = None,
) -> DraftingProvider:
    """Resolve a provider by name (D-25); default ``"copilot"``.

    Parameters
    ----------
    name : str
        The provider name (``"mock"`` or ``"copilot"``); defaults to the
        documented production default.
    model : str or None
        The drafting model to request; threaded to the copilot adapter, ignored
        by the mock. ``None`` leaves each provider on its own default (LIVE-01).
    effort : Effort or None
        The reasoning effort to request; threaded to the copilot adapter, ignored
        by the mock. ``None`` leaves the adapter default.

    Returns
    -------
    DraftingProvider
        The selected provider instance.

    Raises
    ------
    ValueError
        If ``name`` is not a known provider.
    """
    try:
        factory = _PROVIDER_FACTORIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(_PROVIDER_FACTORIES))
        raise ValueError(f"unknown provider {name!r}; choose one of: {known}") from exc
    return factory(model=model, effort=effort)
