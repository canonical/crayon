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

from dogen.core.models import DraftResult, Intent, SourceRef, Steering
from dogen.core.ports import DraftingProvider

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


def _make_mock_provider() -> DraftingProvider:
    """Construct the mock provider behind the port type.

    Returns
    -------
    DraftingProvider
        A fresh :class:`MockDraftingProvider`.
    """
    return MockDraftingProvider()


def _make_copilot_provider() -> DraftingProvider:
    """Lazily construct the real Copilot provider (plan 03) behind the port.

    The import is deferred so the mock path never loads ``adapters/copilot/``
    and so this dispatch works before the real adapter exists.

    Returns
    -------
    DraftingProvider
        The real Copilot drafting provider.

    Raises
    ------
    NotImplementedError
        Until the Copilot adapter lands in plan 03.
    """
    raise NotImplementedError(
        "the copilot provider is not implemented yet; use --provider mock"
    )


# Dict dispatch, not an if/elif ladder (coding-guide §2). Each value is a
# factory so the copilot branch stays a lazy import (D-25).
_PROVIDER_FACTORIES: dict[str, Callable[[], DraftingProvider]] = {
    "mock": _make_mock_provider,
    "copilot": _make_copilot_provider,
}


def select_provider(name: str = _DEFAULT_PROVIDER) -> DraftingProvider:
    """Resolve a provider by name (D-25); default ``"copilot"``.

    Parameters
    ----------
    name : str
        The provider name (``"mock"`` or ``"copilot"``); defaults to the
        documented production default.

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
    return factory()
