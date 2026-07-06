"""The provider seam: the sole sanctioned GitHub Copilot SDK import site.

This package is the single location where ``copilot`` / ``github_copilot_sdk``
may be imported (SEAM-01); the AST seam guardrail and the import-linter forbidden
contract exempt this subtree alone.

Phase 1 left the boundary intentionally empty (D-08, deferred dependency); that
dependency has now landed. The real :class:`CopilotDraftingProvider` implements
the same ``core.ports.DraftingProvider`` port the deterministic mock proved
(SEAM-03), driving a bounded read-only Copilot session and converting a
backend-unavailable runtime into a handled :class:`BackendUnavailableError`
(SKEL-05/D-27). The CI loop still runs on ``--provider mock``; the real SDK is
exercised only by the manual local smoke harness (D-24).
"""

from dogen.adapters.copilot.provider import (
    BackendUnavailableError,
    CopilotDraftingProvider,
    ModelRejectedError,
)

__all__ = [
    "BackendUnavailableError",
    "CopilotDraftingProvider",
    "ModelRejectedError",
]
