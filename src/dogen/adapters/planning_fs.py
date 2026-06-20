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

"""Filesystem PlanningStore over ``.dogen/units/<id>/`` and ``docs/`` (D-31/33).

This adapter implements :class:`dogen.core.ports.PlanningStore`. It serializes
the F1 Pydantic models to disk and **never writes anywhere under ``.planning/``**
(D-30) — that is GSD's directory and is an explicit, enforced guard, not a
convention (threat T-02.1-01). Machine-written files (``provenance.yaml`` /
``progress.yaml``) use PyYAML; ``unit.md`` is only ever *created* here (the
operator hand-edits it afterward), so PyYAML suffices and ruamel.yaml is not
needed for round-trip comment preservation (A4 decision — recorded in SUMMARY).
"""

from pathlib import Path

import yaml

from dogen.core.models import Intent, Progress, Provenance, Unit

_UNITS_SUBDIR = ".dogen/units"
_FORBIDDEN_OUTPUT_ROOT = ".planning"
_FRONT_MATTER_FENCE = "---"

_BODY_TEMPLATE = """\
## Intent & scope

Describe what this page covers and who it serves.

## Outline / acceptance

- Outline the sections to draft.
- List the acceptance criteria a reviewer checks the draft against.
"""


class UnitExistsError(FileExistsError):
    """Raised when scaffolding would clobber an existing ``unit.md``."""


def split_front_matter(text: str) -> tuple[dict, str]:
    """Split a ``---``-delimited document into front-matter and body.

    A small, tested splitter (not a regex) handling CRLF endings, an empty
    body, and a body that itself contains a ``---`` line (RESEARCH "Don't
    Hand-Roll"). Only the first two fences delimit the front-matter.

    Parameters
    ----------
    text : str
        The full document text.

    Returns
    -------
    tuple of (dict, str)
        The parsed front-matter mapping and the remaining body text.

    Raises
    ------
    ValueError
        If the document does not open with a ``---`` front-matter fence or the
        closing fence is missing.
    """
    normalized = text.replace("\r\n", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != _FRONT_MATTER_FENCE:
        raise ValueError("document does not begin with a '---' front-matter fence")
    closing = next(
        (i for i in range(1, len(lines)) if lines[i].strip() == _FRONT_MATTER_FENCE),
        None,
    )
    if closing is None:
        raise ValueError("front-matter is missing its closing '---' fence")
    front_text = "\n".join(lines[1:closing])
    body = "\n".join(lines[closing + 1 :])
    parsed = yaml.safe_load(front_text) or {}
    return parsed, body


class FilesystemPlanningStore:
    """A :class:`PlanningStore` backed by the repo filesystem."""

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
            The unit identifier; must be a single safe path segment.
        root : Path
            The repo root to write beneath.
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

        Raises
        ------
        ValueError
            If ``unit_id`` is unsafe (separators, ``..``, absolute).
        UnitExistsError
            If ``unit.md`` already exists and ``force`` is ``False``.
        """
        self._reject_unsafe_unit_id(unit_id)
        target = self._unit_md_path(unit_id, root=root)
        self._assert_within_root(target, root=root)
        self._assert_not_under_planning(target, root=root)
        if target.exists() and not force:
            raise UnitExistsError(f"{target} exists; pass force=True to overwrite")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            self._render_unit_md(unit_id, intent=intent, audience=audience),
            encoding="utf-8",
        )
        return target

    def load_unit(self, unit_id: str, *, root: Path) -> Unit:
        """Load and validate a unit's ``unit.md`` front-matter.

        Parameters
        ----------
        unit_id : str
            The unit to load.
        root : Path
            The repo root to read beneath.

        Returns
        -------
        Unit
            The validated unit model.

        Raises
        ------
        ValueError
            If the front-matter ``unit_id`` disagrees with the directory the
            unit was loaded from (audit-record integrity; D-36/AC5).
        """
        self._reject_unsafe_unit_id(unit_id)
        front, _ = split_front_matter(
            self._unit_md_path(unit_id, root=root).read_text(encoding="utf-8")
        )
        unit = Unit(**front)
        if unit.unit_id != unit_id:
            raise ValueError(
                f"unit.md declares unit_id {unit.unit_id!r} but lives under {unit_id!r}"
            )
        return unit

    def write_draft(self, unit: Unit, text: str, *, root: Path) -> Path:
        """Write a drafted MyST page to the unit's Sphinx target.

        Parameters
        ----------
        unit : Unit
            The unit being drafted (provides ``sphinx_target``).
        text : str
            The MyST Markdown content.
        root : Path
            The repo root to write beneath.

        Returns
        -------
        Path
            The path to the written ``.md`` under ``docs/``.
        """
        docs_root = (root / "docs").resolve()
        target = (docs_root / unit.sphinx_target).resolve()
        # Positive containment (CR-01/T-02.1-01): the draft target must be
        # ``docs/`` itself or live beneath it. ``Path.resolve`` collapses ``..``
        # before this runs, so an operator-authored ``sphinx_target`` such as
        # ``../../escape.md`` is rejected here rather than written outside the
        # repo. The ``.planning/`` and root guards remain as defense-in-depth.
        if target != docs_root and docs_root not in target.parents:
            raise ValueError(f"sphinx_target escapes docs/: {unit.sphinx_target!r}")
        self._assert_within_root(target, root=root)
        self._assert_not_under_planning(target, root=root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def read_provenance(self, unit_id: str, *, root: Path) -> Provenance:
        """Load a unit's provenance record.

        Parameters
        ----------
        unit_id : str
            The unit to read.
        root : Path
            The repo root to read beneath.

        Returns
        -------
        Provenance
            The validated provenance model.
        """
        return Provenance(**self._read_yaml(unit_id, "provenance.yaml", root=root))

    def write_provenance(self, provenance: Provenance, *, root: Path) -> Path:
        """Persist a unit's provenance record.

        Parameters
        ----------
        provenance : Provenance
            The provenance model to serialize.
        root : Path
            The repo root to write beneath.

        Returns
        -------
        Path
            The path to the written ``provenance.yaml``.
        """
        return self._write_yaml(
            provenance.unit_id, "provenance.yaml", provenance, root=root
        )

    def read_progress(self, unit_id: str, *, root: Path) -> Progress:
        """Load a unit's progress state machine.

        Parameters
        ----------
        unit_id : str
            The unit to read.
        root : Path
            The repo root to read beneath.

        Returns
        -------
        Progress
            The validated progress model.
        """
        return Progress(**self._read_yaml(unit_id, "progress.yaml", root=root))

    def write_progress(self, progress: Progress, *, root: Path) -> Path:
        """Persist a unit's progress state machine.

        Parameters
        ----------
        progress : Progress
            The progress model to serialize.
        root : Path
            The repo root to write beneath.

        Returns
        -------
        Path
            The path to the written ``progress.yaml``.
        """
        return self._write_yaml(progress.unit_id, "progress.yaml", progress, root=root)

    @staticmethod
    def _reject_unsafe_unit_id(unit_id: str) -> None:
        """Reject a unit id that is not a single safe path segment (T-02.1-01).

        Parameters
        ----------
        unit_id : str
            The candidate identifier.

        Raises
        ------
        ValueError
            If the id is empty, ``..``, absolute, or contains a path separator.
        """
        if not unit_id or unit_id in {".", ".."}:
            raise ValueError(f"invalid unit id: {unit_id!r}")
        if "/" in unit_id or "\\" in unit_id or Path(unit_id).name != unit_id:
            raise ValueError(f"unit id must be a single path segment: {unit_id!r}")

    def _unit_md_path(self, unit_id: str, *, root: Path) -> Path:
        """Return the resolved ``unit.md`` path for a unit.

        Parameters
        ----------
        unit_id : str
            The (already-validated) unit id.
        root : Path
            The repo root.

        Returns
        -------
        Path
            The resolved ``<root>/.dogen/units/<id>/unit.md`` path.
        """
        return (root / _UNITS_SUBDIR / unit_id / "unit.md").resolve()

    @staticmethod
    def _assert_within_root(target: Path, *, root: Path) -> None:
        """Refuse to write anywhere outside ``root`` (WR-01; T-02.1-01).

        The positive containment that pairs with
        :meth:`_assert_not_under_planning`: every write target must be ``root``
        itself or live beneath it. This is the primary control; the
        ``.planning/`` guard is then a narrower, defense-in-depth check.

        Parameters
        ----------
        target : Path
            The resolved write target.
        root : Path
            The repo root.

        Raises
        ------
        ValueError
            If ``target`` resolves outside ``<root>/``.
        """
        resolved_root = root.resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise ValueError(f"refusing to write outside the repo root: {target}")

    @staticmethod
    def _assert_not_under_planning(target: Path, *, root: Path) -> None:
        """Refuse to write anywhere under ``.planning/`` (D-30; T-02.1-01).

        Parameters
        ----------
        target : Path
            The resolved write target.
        root : Path
            The repo root.

        Raises
        ------
        ValueError
            If ``target`` resolves under ``<root>/.planning/``.
        """
        forbidden = (root / _FORBIDDEN_OUTPUT_ROOT).resolve()
        if target == forbidden or forbidden in target.parents:
            raise ValueError(f"refusing to write under {_FORBIDDEN_OUTPUT_ROOT}/")

    def _render_unit_md(
        self,
        unit_id: str,
        *,
        intent: Intent | None,
        audience: str | None,
    ) -> str:
        """Render the ``unit.md`` template (front-matter + body skeleton).

        Parameters
        ----------
        unit_id : str
            The unit id.
        intent : Intent or None
            Optional pre-filled intent.
        audience : str or None
            Optional pre-filled audience.

        Returns
        -------
        str
            The full ``unit.md`` document text.
        """
        unit = Unit(
            unit_id=unit_id,
            intent=intent or Intent.reference,
            audience=audience or "",
            title="",
            sphinx_target=f"{unit_id}.md",
        )
        front = unit.model_dump(mode="json")
        front_yaml = yaml.safe_dump(front, sort_keys=False).rstrip("\n")
        fence = _FRONT_MATTER_FENCE
        return f"{fence}\n{front_yaml}\n{fence}\n{_BODY_TEMPLATE}"

    def _read_yaml(self, unit_id: str, name: str, *, root: Path) -> dict:
        """Read a machine YAML file for a unit.

        Parameters
        ----------
        unit_id : str
            The unit id.
        name : str
            The file name (``provenance.yaml`` / ``progress.yaml``).
        root : Path
            The repo root.

        Returns
        -------
        dict
            The parsed mapping (empty when the file holds no data).
        """
        self._reject_unsafe_unit_id(unit_id)
        path = (root / _UNITS_SUBDIR / unit_id / name).resolve()
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _write_yaml(
        self,
        unit_id: str,
        name: str,
        model: Provenance | Progress,
        *,
        root: Path,
    ) -> Path:
        """Serialize a Pydantic model to a unit's machine YAML file.

        Parameters
        ----------
        unit_id : str
            The unit id.
        name : str
            The target file name.
        model : Provenance or Progress
            The model to serialize.
        root : Path
            The repo root.

        Returns
        -------
        Path
            The written file path.
        """
        self._reject_unsafe_unit_id(unit_id)
        target = (root / _UNITS_SUBDIR / unit_id / name).resolve()
        self._assert_within_root(target, root=root)
        self._assert_not_under_planning(target, root=root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(model.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )
        return target
