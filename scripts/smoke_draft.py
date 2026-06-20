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

"""Manual local smoke harness for the real Copilot SDK (SKEL-05 evidence, D-24).

This is **not** wired into CI. It exists to demonstrate the real
``CopilotDraftingProvider`` end-to-end against the dogfood repo **once**, capture
the bundled Copilot CLI version as the pin (Assumption A2), and serve as the
SDK/CLI version-bump gate: when either is bumped, re-run this and re-record the
version before trusting the loop again.

The live SDK path is gated behind an explicit opt-in (``--live`` or the
``DOGEN_SMOKE_LIVE`` env var), so the harness's argument handling and its
backend-unavailable branch are unit-testable **without ever touching the network
or the SDK** (the live run is a manual operator step; CI uses ``--provider mock``
and never needs a Copilot token). A backend-unavailable run degrades gracefully:
it reuses the adapter's :class:`BackendUnavailableError` and exits nonzero with a
clear message rather than crashing.

Usage (manual)::

    DOGEN_SMOKE_LIVE=1 uv run python scripts/smoke_draft.py --unit <unit-id>
    # or
    uv run python scripts/smoke_draft.py --live --unit <unit-id>
"""

import argparse
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass

# Env var that opts in to the real SDK call (belt-and-braces with --live).
_LIVE_ENV = "DOGEN_SMOKE_LIVE"
_NOT_LIVE_MESSAGE = (
    "smoke harness: live SDK path not enabled; pass --live or set "
    f"{_LIVE_ENV}=1 to run the real Copilot draft. (No SDK call was made.)"
)


@dataclass(frozen=True)
class SmokeArgs:
    """Parsed smoke-harness arguments.

    Parameters
    ----------
    live : bool
        Whether the real SDK path is enabled (``--live`` or the env opt-in).
    unit_id : str
        The unit to draft in the live run.
    audience : str
        The audience to steer the live draft toward.
    """

    live: bool
    unit_id: str
    audience: str


def parse_args(argv: Sequence[str], env: dict[str, str] | None = None) -> SmokeArgs:
    """Parse smoke-harness CLI arguments and the live opt-in.

    Parameters
    ----------
    argv : sequence of str
        The argument vector (excluding the program name).
    env : dict of str to str, optional
        Environment mapping consulted for the ``DOGEN_SMOKE_LIVE`` opt-in;
        defaults to ``os.environ`` when ``None``.

    Returns
    -------
    SmokeArgs
        The parsed arguments with the resolved ``live`` flag.
    """
    environ = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Manual Copilot SDK smoke draft.")
    parser.add_argument("--live", action="store_true", help="Enable the real SDK call.")
    parser.add_argument("--unit", default="smoke", help="Unit id to draft.")
    parser.add_argument(
        "--audience", default="operators", help="Audience to steer toward."
    )
    parsed = parser.parse_args(argv)
    live = bool(parsed.live) or environ.get(_LIVE_ENV) == "1"
    return SmokeArgs(live=live, unit_id=parsed.unit, audience=parsed.audience)


def run(argv: Sequence[str], env: dict[str, str] | None = None) -> int:
    """Run the smoke harness; return a process exit code.

    The non-live branch performs **no** SDK call (it prints how to opt in and
    returns ``0``). The live branch is delegated to :func:`_run_live`, which
    catches a backend-unavailable state and returns a nonzero code.

    Parameters
    ----------
    argv : sequence of str
        The argument vector (excluding the program name).
    env : dict of str to str, optional
        Environment mapping for the live opt-in; defaults to ``os.environ``.

    Returns
    -------
    int
        ``0`` on success (including the gated not-live path), nonzero on a
        handled backend-unavailable failure.
    """
    args = parse_args(argv, env=env)
    if not args.live:
        print(_NOT_LIVE_MESSAGE)
        return 0
    return _run_live(args)


def _run_live(args: SmokeArgs) -> int:
    """Execute the real SDK smoke draft and record the CLI version.

    Parameters
    ----------
    args : SmokeArgs
        The parsed arguments (``live`` is guaranteed ``True`` here).

    Returns
    -------
    int
        ``0`` on a completed draft; ``1`` when the backend is unavailable.
    """
    # Deferred so the non-live branch (and its unit tests) never import the SDK
    # adapter — the import is the seam-crossing the harness only needs when live.
    import asyncio  # noqa: PLC0415

    from dogen.adapters.copilot import BackendUnavailableError  # noqa: PLC0415

    try:
        return asyncio.run(_draft_and_record(args))
    except BackendUnavailableError as exc:
        print(f"smoke harness: backend unavailable: {exc}", file=sys.stderr)
        return 1


async def _draft_and_record(args: SmokeArgs) -> int:
    """Record the bundled CLI version, then run one real draft (live only).

    Parameters
    ----------
    args : SmokeArgs
        The parsed arguments.

    Returns
    -------
    int
        ``0`` once the draft completes.

    Raises
    ------
    BackendUnavailableError
        If the backend is unavailable (handled by the caller as exit ``1``).
    """
    # Deferred SDK imports: the harness only crosses the seam on the live path.
    from copilot import CopilotClient  # noqa: PLC0415

    from dogen.adapters.copilot import CopilotDraftingProvider  # noqa: PLC0415
    from dogen.core.models import Intent, SourceRef, Steering  # noqa: PLC0415

    async with CopilotClient() as client:
        status = await client.get_status()
        # The bundled CLI version is the A2 pin and the SDK/CLI bump gate.
        print(f"smoke harness: bundled Copilot CLI version = {status.version}")

    provider = CopilotDraftingProvider(working_directory=os.getcwd())
    steering = Steering(
        author="smoke@local",
        at="1970-01-01T00:00:00Z",
        intent=Intent.reference,
        audience=args.audience,
    )
    result = await provider.draft_unit(
        intent=Intent.reference,
        audience=args.audience,
        steering=steering,
        sources=[SourceRef(path="README.md")],
    )
    print(f"smoke harness: drafted {len(result.text)} chars with {result.model}")
    return 0


def main() -> int:
    """Entry point: run the harness over ``sys.argv`` and return its exit code.

    Returns
    -------
    int
        The process exit code from :func:`run`.
    """
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
