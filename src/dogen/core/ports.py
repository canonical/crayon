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

"""Domain ports for dogen, shaped by domain verbs (not vendor signatures).

These ``Protocol`` classes are the seam (SEAM-03/04): ``core/`` depends only on
them, and adapters implement them. A port that mirrored an SDK method has already
failed the design (ARCHITECTURE Anti-Pattern 2), so every signature here speaks
the domain — ``draft_unit``, ``scaffold_unit``, ``read_provenance`` — and no
parameter or return type references any ``copilot``/SDK symbol (S5). Drafting is
async because the SDK is async end-to-end (RESEARCH Pitfall 2).
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from dogen.core.models import (
    DraftResult,
    Intent,
    Progress,
    Provenance,
    SourceRef,
    Steering,
    Unit,
)


@runtime_checkable
class DraftingProvider(Protocol):
    """The provider seam: draft one unit, steered by intent and audience.

    Implemented by the real Copilot adapter and by a deterministic mock (the
    mock *is* the second provider that proves swappability — D-26/SEAM-04).
    """

    async def draft_unit(
        self,
        *,
        intent: Intent,
        audience: str,
        steering: Steering,
        sources: list[SourceRef],
    ) -> DraftResult:
        """Draft a single unit from steering and human-pointed sources.

        Parameters
        ----------
        intent : Intent
            The Diátaxis direction to draft toward.
        audience : str
            Who the page is written for.
        steering : Steering
            The recorded HITL steering event that must precede the draft.
        sources : list of SourceRef
            The human-pointed sources to ground the draft in.

        Returns
        -------
        DraftResult
            The drafted MyST content plus provenance inputs, in domain terms.
        """
        ...


@runtime_checkable
class SourceLookup(Protocol):
    """Bounded, read-only access to the sources the agent may read."""

    async def read_source(self, ref: SourceRef) -> str:
        """Return the text content of a single source.

        Parameters
        ----------
        ref : SourceRef
            The source to read.

        Returns
        -------
        str
            The source's textual content.
        """
        ...


@runtime_checkable
class PlanningStore(Protocol):
    """Read/write the F1 planning directory in domain verbs (D-31/33).

    The adapter owns file layout (``.dogen/units/<id>/`` + ``docs/``); the port
    speaks only of units, drafts, provenance, and progress.
    """

    def scaffold_unit(
        self,
        unit_id: str,
        *,
        root: Path,
        intent: Intent | None = None,
        audience: str | None = None,
        force: bool = False,
    ) -> Path:
        """Create an editable ``unit.md`` for a new unit.

        Parameters
        ----------
        unit_id : str
            The unit identifier and per-unit directory name.
        root : Path
            The repo root the store writes beneath.
        intent : Intent or None
            Optional pre-filled Diátaxis direction.
        audience : str or None
            Optional pre-filled audience.
        force : bool
            Overwrite an existing ``unit.md`` when ``True``.

        Returns
        -------
        Path
            The path to the written ``unit.md``.
        """
        ...

    def load_unit(self, unit_id: str, *, root: Path) -> Unit:
        """Load and validate a unit's ``unit.md`` front-matter.

        Parameters
        ----------
        unit_id : str
            The unit to load.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        Unit
            The validated unit model.
        """
        ...

    def write_draft(self, unit: Unit, text: str, *, root: Path) -> Path:
        """Write a drafted MyST page to the unit's Sphinx target.

        Parameters
        ----------
        unit : Unit
            The unit being drafted (provides ``sphinx_target``).
        text : str
            The MyST Markdown content.
        root : Path
            The repo root the store writes beneath.

        Returns
        -------
        Path
            The path to the written ``.md`` under ``docs/``.
        """
        ...

    def read_provenance(self, unit_id: str, *, root: Path) -> Provenance:
        """Load a unit's provenance record.

        Parameters
        ----------
        unit_id : str
            The unit to read.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        Provenance
            The validated provenance model.
        """
        ...

    def write_provenance(self, provenance: Provenance, *, root: Path) -> Path:
        """Persist a unit's provenance record.

        Parameters
        ----------
        provenance : Provenance
            The provenance model to serialize.
        root : Path
            The repo root the store writes beneath.

        Returns
        -------
        Path
            The path to the written ``provenance.yaml``.
        """
        ...

    def read_progress(self, unit_id: str, *, root: Path) -> Progress:
        """Load a unit's progress state machine.

        Parameters
        ----------
        unit_id : str
            The unit to read.
        root : Path
            The repo root the store reads beneath.

        Returns
        -------
        Progress
            The validated progress model.
        """
        ...

    def write_progress(self, progress: Progress, *, root: Path) -> Path:
        """Persist a unit's progress state machine.

        Parameters
        ----------
        progress : Progress
            The progress model to serialize.
        root : Path
            The repo root the store writes beneath.

        Returns
        -------
        Path
            The path to the written ``progress.yaml``.
        """
        ...
