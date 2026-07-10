"""dogen command-line entrypoint — the thin deterministic machine seam (D-11).

This module backs the ``[project.scripts] dogen = "dogen.cli.main:app"`` console
script. It is the deterministic **machine seam** the skills shell into, not the
Technical Author's primary surface. Each verb assembles a frozen request via
the ``dogen.app.compose`` builders and delegates to the ``core.orchestrator``
use-cases behind a single ``asyncio.run`` boundary (``draft``); no business
logic lives here (D-11).

The v1 surface:

* ``unit new|edit|ls|rm|mv|show`` — declare, amend (merge, never clobber),
  list, delete, rename, and inspect units;
* ``signoff`` — the HITL gate act (freezes the plan hash);
* ``steer --note`` — append to the unit's steering stream (gate-free);
* ``draft`` — run the drafting loop (``--report`` ingests the passenger's
  context report; ``--resolve-only`` stays the zero-side-effect probe);
* ``review --verdict --note`` — record the structured verdict;
* ``status`` — the repo-level board with suggested next verbs;
* ``provider show|set`` / ``commits`` — explicit provider selection and the
  commit-seam toggle;
* ``context ls|add`` — the B1/B2 landing zone;
* ``skills install|status|update`` — stage the canonical skill family into a
  harness's discovery root (see :mod:`dogen.cli.skills`).

Every state-changing verb records one local transition commit through the
seam (``Dogen-Unit``/``Dogen-Phase`` trailers) unless the repo config says
``commits: off`` or ``--no-commit`` is passed; a seam failure degrades to a
warning, never a failed verb. Failures map to coarse exit codes (``0`` ok /
``1`` domain refusal / ``2`` bad input) **and** a stable machine-readable
``reason`` code in ``--json`` (D-10).

Backend domain errors are classified by ``type(exc).__name__`` so the
``mock``/``host-harness`` path never imports ``adapters/copilot/`` (or the
SDK): this module holds **no** ``copilot``/SDK import — the provider seam
stays intact.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Annotated

import typer

from dogen.adapters.git_identity import GitIdentityError
from dogen.adapters.planning_fs import (
    ProvenanceInvalidError,
    SchemaUnsupportedError,
    TargetClaimedError,
    UnitExistsError,
    UnitNotFoundError,
    UnsupportedTargetError,
)
from dogen.app import compose
from dogen.cli.skills import skills_app
from dogen.core.models import (
    CommitMode,
    Intent,
    Provenance,
    ReviewVerdict,
    Unit,
    derive_progress,
)
from dogen.core.orchestrator import (
    AlreadyAcceptedError,
    NotDraftedError,
    SignoffExistsError,
    SignoffRequiredError,
    find_unit_by_draft,
)
from dogen.core.orchestrator import add_context_artifact as context_add_use_case
from dogen.core.orchestrator import add_steering_note as steer_use_case
from dogen.core.orchestrator import declare as declare_use_case
from dogen.core.orchestrator import draft as draft_use_case
from dogen.core.orchestrator import edit_unit as edit_use_case
from dogen.core.orchestrator import list_units as list_units_use_case
from dogen.core.orchestrator import remove as remove_use_case
from dogen.core.orchestrator import rename as rename_use_case
from dogen.core.orchestrator import review as review_use_case
from dogen.core.orchestrator import signoff as signoff_use_case
from dogen.core.orchestrator import unit_statuses as unit_statuses_use_case
from dogen.core.ports import PlanningStore, RepoSeam

#: The ``DOGEN_PROVIDER`` env var — the mid-precedence provider signal (below
#: an explicit ``--provider`` flag, above the repo config). CI pins ``mock``.
_PROVIDER_ENV = "DOGEN_PROVIDER"

# The stable, machine-readable D-10 ``reason`` vocabulary emitted in ``--json``.
# Skills branch on these codes; humans/CI read the coarse exit code + message.
_REASON_SIGNOFF_REQUIRED = "signoff_required"
_REASON_BACKEND_UNAVAILABLE = "backend_unavailable"
_REASON_MODEL_REJECTED = "model_rejected"
#: Emitted when a unit's existence is the problem — a clobber refusal in
#: ``unit new`` (the unit already exists) **or** a not-found unit in ``draft``
#: / ``signoff`` / ``steer`` / ``review``.
_REASON_UNIT_EXISTS = "unit_exists"
_REASON_NOT_DRAFTED = "not_drafted"
#: Emitted by the lifecycle verbs (``unit rm`` / ``unit mv`` / ``unit edit``)
#: when the target unit's directory does not exist.
_REASON_UNIT_NOT_FOUND = "unit_not_found"
#: Emitted by ``unit rm`` when it is invoked without ``--force``.
_REASON_CONFIRM_REQUIRED = "confirm_required"
#: Emitted by ``signoff`` when the act already exists (pass ``--re-sign``).
_REASON_SIGNOFF_EXISTS = "signoff_exists"
#: Emitted by ``review --verdict accept`` when the latest sealed accept
#: already covers the identical on-disk draft (a harness double-fire).
_REASON_ALREADY_ACCEPTED = "already_accepted"
#: Emitted by ``unit edit --target`` when a file already exists at the new
#: target (the draft move refuses to clobber).
_REASON_TARGET_EXISTS = "target_exists"
#: Emitted by ``draft --report`` when the context report fails validation
#: (unreadable YAML, or an origin commit stamp that is neither hex nor empty).
_REASON_BAD_REPORT = "bad_report"
#: Emitted by ``unit new``/``unit edit`` when a target carries no supported
#: page extension (``.md``/``.rst`` — the extension IS the unit's format).
_REASON_BAD_TARGET = "bad_target"
#: Emitted by ``unit new``/``unit edit`` when a docs target already belongs
#: to another unit's page set (v1.2).
_REASON_TARGET_CLAIMED = "target_claimed"
#: Emitted by ``draft --draft-dir`` when a declared target has no staged file.
_REASON_HANDOFF_INCOMPLETE = "handoff_incomplete"
#: Emitted by ``draft --draft-dir`` when a staged file matches no declared
#: target.
_REASON_UNDECLARED_TARGET = "undeclared_target"
#: Emitted by ``draft`` when a driver provider is asked to draft a
#: multi-file unit (drivers are single-page this cycle; use the passenger).
_REASON_MULTI_TARGET_UNSUPPORTED = "multi_target_unsupported"
#: Emitted by ``unit show`` when a provenance record declares a
#: ``schema_version`` newer than this tool supports (D-08) — the loader refuses
#: an unknown shape instead of a best-effort read; the message names found vs
#: supported.
_REASON_SCHEMA_UNSUPPORTED = "schema_unsupported"
#: Emitted by ``unit show`` when a present provenance record fails to
#: parse/validate (D-09) — a corrupt-but-present sidecar refuses with the
#: validation-error location instead of masquerading as ``unit_not_found``.
_REASON_PROVENANCE_INVALID = "provenance_invalid"

# mvp-1's coarse exit codes (carried, D-10).
_EXIT_OK = 0
_EXIT_DOMAIN_REFUSAL = 1
_EXIT_BAD_INPUT = 2

app = typer.Typer(help="Draft review-ready documentation, human in the loop.")
unit_app = typer.Typer(help="Create and manage documentation units.")
provider_app = typer.Typer(help="Show or set the explicit drafting provider.")
context_app = typer.Typer(help="Manage the B1/B2 context-artifact landing zone.")
app.add_typer(unit_app, name="unit")
app.add_typer(provider_app, name="provider")
app.add_typer(context_app, name="context")
app.add_typer(skills_app, name="skills")

_NoCommit = Annotated[
    bool,
    typer.Option(
        "--no-commit",
        help="Skip the transition commit for this invocation only.",
    ),
]
_JsonOutput = Annotated[
    bool,
    typer.Option("--json", help="Emit a structured JSON result."),
]


def _emit_json(  # noqa: PLR0913
    *,
    unit: str,
    provider: str | None = None,
    draft_path: str | None = None,
    progress: str | None = None,
    reason: str | None = None,
    **extra: object,
) -> None:
    """Print one CLI result as a single-line JSON object (D-08).

    The stable structured surface the skills parse. The five base fields are
    always present (``null`` when not applicable) so a skill can branch on a
    fixed shape; verbs may append additive named fields (e.g. ``stale_plan``).

    Parameters
    ----------
    unit : str
        The unit id the command acted on.
    provider : str or None
        The resolved provider that ran (or would run, for ``--resolve-only``).
    draft_path : str or None
        The path of the written draft, on a successful ``draft``.
    progress : str or None
        The unit's progress state after the command, when relevant.
    reason : str or None
        The stable D-10 failure ``reason`` code, or ``None`` on success.
    **extra : object
        Additive verb-specific fields appended to the object.
    """
    payload: dict[str, object] = {
        "unit": unit,
        "provider": provider,
        "draft_path": draft_path,
        "progress": progress,
        "reason": reason,
    }
    payload.update(extra)
    typer.echo(json.dumps(payload))


def _fail(  # noqa: PLR0913
    unit_id: str,
    *,
    message: str,
    reason: str | None,
    code: int,
    json_output: bool,
    provider: str | None = None,
) -> typer.Exit:
    """Render a failure and return the :class:`typer.Exit` for the caller.

    Returning (rather than raising) the ``Exit`` lets callers write
    ``raise _fail(...) from exc`` so the original exception stays chained.

    Parameters
    ----------
    unit_id : str
        The unit id the failed command acted on.
    message : str
        The human-facing message printed to stderr in plain mode.
    reason : str or None
        The stable D-10 ``reason`` code emitted in ``--json`` mode.
    code : int
        The coarse process exit code (``1`` domain refusal / ``2`` bad input).
    json_output : bool
        Whether to emit the structured JSON object instead of the message.
    provider : str or None
        The resolved provider name, carried in the JSON object when known.

    Returns
    -------
    typer.Exit
        The exit signal for the caller to ``raise ... from exc``.
    """
    if json_output:
        _emit_json(unit=unit_id, provider=provider, reason=reason)
    else:
        typer.echo(message, err=True)
    return typer.Exit(code=code)


def _warn_commit_failure(message: str) -> None:
    """Print a commit-seam failure as a warning (the verb still succeeded).

    Parameters
    ----------
    message : str
        The seam's failure message.
    """
    typer.echo(f"Warning: transition commit failed: {message}", err=True)


def _seam(store: PlanningStore, root: Path, *, no_commit: bool) -> RepoSeam | None:
    """Resolve the commit seam for one invocation.

    Parameters
    ----------
    store : PlanningStore
        The planning store (reads the repo config).
    root : Path
        The repo root.
    no_commit : bool
        The per-invocation ``--no-commit`` override.

    Returns
    -------
    RepoSeam or None
        The tolerant seam when ``commits: auto`` and not overridden, else
        ``None``.
    """
    config, _ = compose.repo_config(store, root=root)
    enabled = config.commits is CommitMode.auto and not no_commit
    return compose.make_repo_seam(enabled=enabled, on_error=_warn_commit_failure)


def _read_body_file(
    unit_id: str, body_file: str | None, *, json_output: bool
) -> str | None:
    """Resolve ``--body-file`` into the replacement plan-body text.

    Parameters
    ----------
    unit_id : str
        The unit being edited (for the failure payload).
    body_file : str or None
        The operator's ``--body-file`` value; ``-`` reads stdin, ``None``
        leaves the body unchanged.
    json_output : bool
        Whether failures render as JSON.

    Returns
    -------
    str or None
        The replacement body text, or ``None`` when no replacement was asked.
    """
    if body_file is None:
        return None
    if body_file == "-":
        return sys.stdin.read()
    body_path = Path(body_file)
    if not body_path.is_file():
        raise _fail(
            unit_id,
            message=f"No such body file: {body_file!r}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        )
    return body_path.read_text(encoding="utf-8")


def _resolve_passenger_input(  # noqa: PLR0913
    unit_id: str,
    *,
    store: PlanningStore,
    root: Path,
    provider_name: str,
    draft_file: Path | None,
    draft_dir: Path | None,
    json_output: bool,
) -> tuple[str | None, dict[str, str] | None, str]:
    """Resolve the draft verb's handoff inputs (v1.2, D-03 compose-root IO).

    Validates the ``--draft-file`` / ``--draft-dir`` shape against the unit's
    target set before any use-case runs: mutual exclusivity, the 1:1 staged
    mapping for a directory handoff, and the driver-provider refusal on
    multi-file units.

    Parameters
    ----------
    unit_id : str
        The unit being drafted.
    store : PlanningStore
        The planning store (loads the unit's target set).
    root : Path
        The repo root.
    provider_name : str
        The resolved provider name.
    draft_file : Path or None
        The single-page handoff, when given.
    draft_dir : Path or None
        The staged multi-page handoff directory, when given.
    json_output : bool
        Whether failures render as JSON.

    Returns
    -------
    tuple of (str or None, dict or None, str)
        ``(draft_text, pages, handoff_path)`` for the provider factory:
        pre-read text + extra pages for a directory handoff (else ``None``),
        and the handoff path recorded in provenance.
    """
    if draft_file is not None and draft_dir is not None:
        raise _fail(
            unit_id,
            message="Pass --draft-file OR --draft-dir, not both.",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
            provider=provider_name,
        )
    try:
        unit = store.load_unit(unit_id, root=root)
    except (FileNotFoundError, ValueError):
        # A missing/invalid unit surfaces from the use case with its usual
        # reason; the input-shape checks below need the unit only when it
        # exists.
        return None, None, str(draft_file) if draft_file is not None else ""
    if unit.extra_targets and provider_name != "host-harness":
        raise _fail(
            unit_id,
            message=(
                f"Provider {provider_name!r} drafts a single page; unit "
                f"{unit_id!r} spans {len(unit.targets)} pages. Multi-file "
                "units run through the host-harness passenger this cycle."
            ),
            reason=_REASON_MULTI_TARGET_UNSUPPORTED,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
            provider=provider_name,
        )
    if draft_dir is None:
        return None, None, str(draft_file) if draft_file is not None else ""
    try:
        text, pages = compose.read_draft_dir(
            draft_dir, primary=unit.sphinx_target, extras=list(unit.extra_targets)
        )
    except compose.HandoffIncompleteError as exc:
        raise _fail(
            unit_id,
            message=f"Incomplete handoff: {exc}",
            reason=_REASON_HANDOFF_INCOMPLETE,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
            provider=provider_name,
        ) from exc
    except compose.UndeclaredTargetError as exc:
        raise _fail(
            unit_id,
            message=f"Refusing the handoff: {exc}",
            reason=_REASON_UNDECLARED_TARGET,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
            provider=provider_name,
        ) from exc
    return text, pages, str(draft_dir)


def _report_git(seam: RepoSeam | None, *, no_commit: bool) -> str:
    """Surface the invocation's git event on stderr and return its sha (v1.2, R5).

    Round-2 forensics: the seam committed silently on every leg — agents
    asserted "committed by the CLI's seam" with nothing to quote, and no
    transcript carried a hash. One line per verb closes that: the operator
    (and the harness transcript) sees exactly what landed, and JSON callers
    get the same sha via the ``commit`` field.

    Parameters
    ----------
    seam : RepoSeam or None
        The seam instance this invocation used (``None`` = commits off).
    no_commit : bool
        The per-invocation ``--no-commit`` override.

    Returns
    -------
    str
        The transition commit's hash, or ``""`` when none landed.
    """
    if no_commit:
        typer.echo("git: transition commit skipped (--no-commit)", err=True)
        return ""
    if seam is None:
        # commits: off is a configured posture, not a per-verb event — silent.
        return ""
    sha = getattr(seam, "last_sha", "")
    subject = getattr(seam, "last_subject", "")
    if sha:
        typer.echo(f"git: committed {sha[:7]} — {subject}", err=True)
    else:
        typer.echo(
            "git: no transition commit (nothing to record, or not a git repo)",
            err=True,
        )
    return sha


def _note_docs_prefix_stripped(
    raw_target: str | None,
    raw_extras: list[str] | None,
    raw_drops: list[str] | None,
) -> None:
    """Notice each target flag whose leading ``docs/`` was normalized away (M1).

    Targets are docs-relative; ``compose`` strips a stray leading ``docs/`` so a
    ``docs/reference/x.rst`` cannot land at ``docs/docs/…`` (round-3's opencode
    trap). This surfaces the silent correction so the operator sees it and the
    transcript records it. Called only after the use case succeeds (a validation
    failure exits first); the ``note:`` prefix stays clear of the ``_json_line``
    sniff, which keys on a leading ``{``/``[``.
    """
    for raw in [raw_target, *(raw_extras or []), *(raw_drops or [])]:
        if not raw:
            continue
        normalized = compose._strip_docs_prefix(raw)
        if normalized != raw:
            typer.echo(
                f"note: target normalized (leading docs/ stripped): "
                f"{raw} -> {normalized}",
                err=True,
            )


@unit_app.command("new")
def unit_new(  # noqa: PLR0913
    unit_id: Annotated[str, typer.Argument(help="Identifier for the new unit.")],
    intent: Annotated[
        Intent | None,
        typer.Option(help="Pre-fill the Diátaxis direction."),
    ] = None,
    audience: Annotated[
        str | None,
        typer.Option(help="Pre-fill the target audience."),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option(help="Pre-fill the human-readable page title."),
    ] = None,
    source: Annotated[
        list[str] | None,
        typer.Option(help="Repeatable source path; accumulates in declared order."),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option(help="Pre-fill the free-form steering note."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help=(
                "docs-relative output path for the drafted page, subdirectories "
                "welcome (e.g. reference/definition-files/page.md); the "
                "extension (.md/.rst) decides the unit's format. Defaults to "
                "<unit_id>.<ext> at the docs root, following the docs tree's "
                "dominant format."
            ),
        ),
    ] = None,
    also_target: Annotated[
        list[str] | None,
        typer.Option(
            "--also-target",
            help=(
                "Repeatable: an additional docs-relative page in this unit's "
                "change set (v1.2) — the horizontal-fix / restructure surface."
            ),
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(help="Explicit re-scaffold: overwrite an existing unit.md."),
    ] = False,
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """Scaffold an editable ``unit.md`` for a new documentation unit (UNIT-01).

    Sources are commit-stamped at declare time and the transition is committed
    through the seam (v1). A clobber without ``--force`` exits ``1``
    (``reason=unit_exists``); an unsafe unit id or a ``--target`` escaping
    ``docs/`` exits ``2``. To amend an existing unit, use ``dogen unit edit``
    — ``--force`` is a full re-scaffold.

    Parameters
    ----------
    unit_id : str
        Identifier and per-unit directory name for the new unit.
    intent : Intent or None
        Optional pre-filled Diátaxis direction.
    audience : str or None
        Optional pre-filled audience.
    title : str or None
        Optional pre-filled human-readable page title.
    source : list of str or None
        Repeatable ``--source`` path; accumulates the human-pointed sources.
    notes : str or None
        Optional pre-filled free-form steering note.
    target : str or None
        Optional docs-relative output path; defaults to ``<unit_id>.md``.
    force : bool
        Explicit re-scaffold of an existing ``unit.md`` when set.
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    seam = _seam(store, root, no_commit=no_commit)
    request = compose.build_declare_request(
        unit_id,
        root=root,
        store=store,
        intent=intent,
        audience=audience,
        title=title,
        sources=source or [],
        steering_notes=notes,
        sphinx_target=target,
        extra_targets=also_target,
        force=force,
        repo=seam,
    )
    try:
        written = declare_use_case(request)
    except TargetClaimedError as exc:
        raise _fail(
            unit_id,
            message=f"Refusing to declare: {exc}",
            reason=_REASON_TARGET_CLAIMED,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except UnitExistsError as exc:
        raise _fail(
            unit_id,
            message=(
                f"Refusing to overwrite: {exc}. Use `dogen unit edit` to amend, "
                "or pass --force to re-scaffold."
            ),
            reason=_REASON_UNIT_EXISTS,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except UnsupportedTargetError as exc:
        raise _fail(
            unit_id,
            message=f"Invalid --target: {exc}",
            reason=_REASON_BAD_TARGET,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    except ValueError as exc:
        raise _fail(
            unit_id,
            message=f"Invalid unit id or target: {exc}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    _note_docs_prefix_stripped(target, also_target, None)
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        _emit_json(unit=unit_id, draft_path=str(written), commit=sha)
    else:
        typer.echo(f"Created {written}")


@unit_app.command("edit")
def unit_edit(  # noqa: PLR0913
    unit_id: Annotated[str, typer.Argument(help="Unit to amend.")],
    intent: Annotated[
        Intent | None,
        typer.Option(help="Replace the Diátaxis direction."),
    ] = None,
    audience: Annotated[
        str | None,
        typer.Option(help="Replace the target audience."),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option(help="Replace the page title."),
    ] = None,
    add_source: Annotated[
        list[str] | None,
        typer.Option(help="Repeatable source path to append to the declared set."),
    ] = None,
    remove_source: Annotated[
        list[str] | None,
        typer.Option(help="Repeatable source path/ref to remove."),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option(help="Replace the seeded steering note."),
    ] = None,
    body_file: Annotated[
        str | None,
        typer.Option(
            "--body-file",
            help=(
                "Replace the plan body (Intent & scope / Outline sections) "
                "from a file; pass '-' to read stdin. The delegable "
                "persistence path for a TA-approved outline."
            ),
        ),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help=(
                "Repoint the docs-relative output path (e.g. "
                "reference/definition-files/page.md). An existing draft at "
                "the old target is MOVED with the repoint — the delegable "
                "'move the page' a reviewer can order."
            ),
        ),
    ] = None,
    also_target: Annotated[
        list[str] | None,
        typer.Option(
            "--also-target",
            help=(
                "Repeatable: add a docs-relative page to this unit's change set (v1.2)."
            ),
        ),
    ] = None,
    drop_target: Annotated[
        list[str] | None,
        typer.Option(
            "--drop-target",
            help=(
                "Repeatable: remove a page from the unit's change set "
                "(de-scope only — the on-disk page is never touched; the "
                "primary cannot be dropped)."
            ),
        ),
    ] = None,
    re_sign: Annotated[
        bool,
        typer.Option(
            "--re-sign",
            help=(
                "Re-approve the amended plan in the same act: the superseded "
                "signoff is archived and a fresh plan hash stamped, so the "
                "edit never parks the unit on a stale plan. Requires an "
                "existing signoff and at least one field change."
            ),
        ),
    ] = False,
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """Merge changes into an existing unit plan — never a clobber (v1).

    Only the named fields change; the body and every unnamed field survive
    verbatim (the Q3 decision) — unless ``--body-file`` explicitly replaces
    the body below the front matter. ``--target`` repoints the drafted page's
    output path and moves an existing draft along (refusing to clobber a file
    already at the destination, ``reason=target_exists``). Appended sources
    are commit-stamped. Editing a signed-off plan is allowed — the stale plan
    hash surfaces on the next draft and in ``dogen status`` — and
    ``--re-sign`` folds the re-approval into the same act (v1.2).

    Parameters
    ----------
    unit_id : str
        The unit to amend.
    intent : Intent or None
        Replacement Diátaxis direction; omit to leave unchanged.
    audience : str or None
        Replacement audience; omit to leave unchanged.
    title : str or None
        Replacement title; omit to leave unchanged.
    add_source : list of str or None
        Repeatable source paths appended to the declared set.
    remove_source : list of str or None
        Repeatable source paths/refs removed from the declared set.
    notes : str or None
        Replacement seeded steering note; omit to leave unchanged.
    body_file : str or None
        Path to a file whose text replaces the plan body below the front
        matter; ``-`` reads stdin. Omit to leave the body unchanged.
    target : str or None
        Replacement docs-relative output path; an existing draft moves with
        the repoint. Omit to leave the target unchanged.
    re_sign : bool
        Fold a re-approval of the amended plan into this act (v1.2).
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    if not any(
        [
            intent,
            audience,
            title,
            add_source,
            remove_source,
            notes,
            body_file,
            target,
            also_target,
            drop_target,
        ]
    ):
        message = (
            "Nothing to change: --re-sign rides on an actual amendment; to "
            "re-approve the plan as it stands, run `dogen signoff --re-sign`."
            if re_sign
            else "Nothing to change: pass at least one field option."
        )
        raise _fail(
            unit_id,
            message=message,
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        )
    body = _read_body_file(unit_id, body_file, json_output=json_output)
    store = compose.default_store()
    root = Path.cwd()
    seam = _seam(store, root, no_commit=no_commit)
    request = compose.build_edit_request(
        unit_id,
        root=root,
        store=store,
        intent=intent,
        audience=audience,
        title=title,
        add_sources=add_source,
        remove_sources=remove_source,
        steering_notes=notes,
        body=body,
        sphinx_target=target,
        add_targets=also_target,
        drop_targets=drop_target,
        re_sign=re_sign,
        repo=seam,
    )
    try:
        written = edit_use_case(request)
    except TargetClaimedError as exc:
        raise _fail(
            unit_id,
            message=f"Refusing to amend: {exc}",
            reason=_REASON_TARGET_CLAIMED,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except UnitNotFoundError as exc:
        raise _fail(
            unit_id,
            message=f"No such unit: {unit_id!r}",
            reason=_REASON_UNIT_NOT_FOUND,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except SignoffRequiredError as exc:
        raise _fail(
            unit_id,
            message=f"Cannot fold a re-sign into this edit: {exc}",
            reason=_REASON_SIGNOFF_REQUIRED,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except GitIdentityError as exc:
        raise _fail(
            unit_id,
            message=f"Cannot record the folded re-sign: {exc}",
            reason=None,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except UnitExistsError as exc:
        raise _fail(
            unit_id,
            message=(
                f"Refusing to move the draft: {exc}. Pick another --target or "
                "remove the file at the destination first."
            ),
            reason=_REASON_TARGET_EXISTS,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except UnsupportedTargetError as exc:
        raise _fail(
            unit_id,
            message=f"Invalid --target: {exc}",
            reason=_REASON_BAD_TARGET,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    except ValueError as exc:
        raise _fail(
            unit_id,
            message=f"Cannot edit {unit_id!r}: {exc}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    _note_docs_prefix_stripped(target, also_target, drop_target)
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        _emit_json(unit=unit_id, draft_path=str(written), commit=sha)
    else:
        typer.echo(f"Amended {written}")


@unit_app.command("ls")
def unit_ls(json_output: _JsonOutput = False) -> None:
    """List every declared unit with its resolved progress state.

    Parameters
    ----------
    json_output : bool
        Emit a single-line JSON array instead of the plain table.
    """
    store = compose.default_store()
    summaries = list_units_use_case(
        compose.build_list_request(root=Path.cwd(), store=store)
    )
    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "unit": s.unit_id,
                        "intent": s.intent.value,
                        "state": s.state.value,
                        "title": s.title,
                    }
                    for s in summaries
                ]
            )
        )
        return
    if not summaries:
        typer.echo("No units.")
        return
    headers = ("ID", "INTENT", "STATE", "TITLE")
    rows = [(s.unit_id, s.intent.value, s.state.value, s.title) for s in summaries]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]
    for cols in [headers, *rows]:
        typer.echo("  ".join(col.ljust(widths[i]) for i, col in enumerate(cols)))


@unit_app.command("show")
def unit_show(
    unit_id: Annotated[
        str | None,
        typer.Argument(help="Unit to inspect (omit with --by-draft)."),
    ] = None,
    by_draft: Annotated[
        str | None,
        typer.Option(
            "--by-draft",
            help="Resolve the owning unit of a drafted docs page instead.",
        ),
    ] = None,
    latest: Annotated[
        bool,
        typer.Option(
            "--latest",
            help=(
                "In --json mode, emit only the newest generations[] entry "
                "(plus generations_count) — the lean projection for skills; "
                "full context_origins of every pass stay on disk."
            ),
        ),
    ] = False,
    json_output: _JsonOutput = False,
) -> None:
    """Show one unit's full state: plan, progress, signoff, and generations.

    With ``--by-draft docs/<page>.md`` the owning unit is resolved first (the
    reverse lookup that keeps draft files clean of embedded markers, Q5).
    ``--latest`` trims the ``--json`` payload to the newest generation —
    provenance grows a full ``context_origins`` list per draft pass, and a
    reviewing/drafting skill only needs the latest one (D7).

    Parameters
    ----------
    unit_id : str or None
        The unit to inspect; omitted when ``--by-draft`` resolves it.
    by_draft : str or None
        A drafted docs path whose owning unit should be resolved.
    latest : bool
        Emit only the newest generation in ``--json`` mode.
    json_output : bool
        Emit the structured JSON object instead of the plain report.
    """
    store = compose.default_store()
    root = Path.cwd()
    if by_draft is not None:
        resolved = find_unit_by_draft(
            compose.build_list_request(root=root, store=store), by_draft
        )
        if resolved is None:
            raise _fail(
                by_draft,
                message=f"No declared unit targets {by_draft!r}.",
                reason=_REASON_UNIT_NOT_FOUND,
                code=_EXIT_DOMAIN_REFUSAL,
                json_output=json_output,
            )
        unit_id = resolved
    if unit_id is None:
        raise _fail(
            "",
            message="Pass a unit id or --by-draft <docs path>.",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        )
    try:
        unit, state, provenance = _gather_unit_detail(store, root, unit_id)
    except SchemaUnsupportedError as exc:
        # D-08: order matters — SchemaUnsupportedError subclasses ValueError, so
        # this specific handler must precede the generic clause below.
        raise _fail(
            unit_id,
            message=f"Cannot read unit {unit_id!r}: {exc}",
            reason=_REASON_SCHEMA_UNSUPPORTED,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except ProvenanceInvalidError as exc:
        # D-09: a present-but-invalid provenance is a distinct refusal, never
        # the not-found conflation. ProvenanceInvalidError also subclasses
        # ValueError, so it too precedes the generic clause.
        raise _fail(
            unit_id,
            message=f"Cannot read unit {unit_id!r}: {exc}",
            reason=_REASON_PROVENANCE_INVALID,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(
            unit_id,
            message=f"Cannot read unit {unit_id!r}: {exc}",
            reason=_REASON_UNIT_NOT_FOUND,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    if json_output:
        prov_dump = provenance.model_dump(mode="json")
        generations = prov_dump["generations"]
        typer.echo(
            json.dumps(
                {
                    "unit": unit.model_dump(mode="json"),
                    "format": unit.format,
                    # D-06: additive top-level targets[] (docs paths, primary
                    # first) — changes no existing key.
                    "targets": [f"docs/{t}" for t in unit.targets],
                    "progress": state,
                    "signoff": prov_dump["signoff"],
                    "steering": prov_dump["steering"],
                    "generations": generations[-1:] if latest else generations,
                    "generations_count": len(generations),
                    "reviewer_edits": prov_dump["reviewer_edits"],
                }
            )
        )
        return
    for line in _render_unit_detail(unit, state, provenance):
        typer.echo(line)


def _load_or_init_provenance(
    store: PlanningStore, root: Path, unit_id: str
) -> Provenance:
    """Load a unit's provenance, returning an empty record when none exists yet.

    PROV-04: the single load-or-init seam the CLI derives lifecycle state from —
    an absent record ⇒ empty generations ⇒ ``pending`` with no special-casing.
    """
    try:
        return store.read_provenance(unit_id, root=root)
    except FileNotFoundError:
        return Provenance(unit_id=unit_id)


def _gather_unit_detail(
    store: PlanningStore, root: Path, unit_id: str
) -> tuple[Unit, str, Provenance]:
    """Assemble the ``unit show`` read-model from the store's records.

    Parameters
    ----------
    store : PlanningStore
        The planning store.
    root : Path
        The repo root.
    unit_id : str
        The unit to read.

    Returns
    -------
    tuple of (Unit, str, Provenance)
        The unit's plan, its resolved progress state, and its provenance (an
        empty record when none exists yet).
    """
    unit = store.load_unit(unit_id, root=root)
    provenance = _load_or_init_provenance(store, root, unit_id)
    # PROV-04: derive lifecycle state from provenance rather than reading a
    # second stored artefact. An empty/absent record derives to ``pending``,
    # so the former FileNotFoundError→"pending" guard is no longer needed.
    state = derive_progress(provenance).value
    return unit, state, provenance


def _render_unit_detail(unit: Unit, state: str, provenance: Provenance) -> list[str]:
    """Render the ``unit show`` detail as plain human-readable lines.

    Parameters
    ----------
    unit : Unit
        The unit's plan front-matter.
    state : str
        The resolved progress state.
    provenance : Provenance
        The unit's provenance record (possibly empty).

    Returns
    -------
    list of str
        The lines to print.
    """
    lines = [
        f"unit:      {unit.unit_id}",
        f"title:     {unit.title}",
        f"intent:    {unit.intent.value}",
        f"audience:  {unit.audience}",
        f"targets:   {len(unit.targets)} page(s)",
    ]
    # D-04/D-05: one indented docs path per target, primary first, with a
    # (primary) marker on the primary entry only. A single-file unit reads
    # identically with count 1. Mirrors the sources: idiom below.
    for index, target in enumerate(unit.targets):
        marker = " (primary)" if index == 0 else ""
        lines.append(f"  - docs/{target}{marker}")
    lines += [
        f"format:    {unit.format}",
        f"progress:  {state}",
        f"sources:   {len(unit.sources)}",
    ]
    for src in unit.sources:
        stamp = f" @ {src.commit[:12]}" if src.commit else ""
        lines.append(f"  - {src.path or src.ref}{stamp} ({src.role.value})")
    signoff_act = provenance.signoff
    if signoff_act is not None:
        plan = f" (plan {signoff_act.plan_hash[:12]})" if signoff_act.plan_hash else ""
        lines.append(f"signoff:   {signoff_act.author} at {signoff_act.at}{plan}")
    else:
        lines.append("signoff:   (none — run `dogen signoff`)")
    lines.append(f"steering:  {len(provenance.steering)} note(s)")
    for entry in provenance.steering:
        lines.append(f"  - [{entry.origin.value}] {entry.note}")
    lines.append(f"drafts:    {len(provenance.generations)} generation(s)")
    for gen in provenance.generations:
        lines.append(
            f"  - {gen.at}  {gen.provider}/{gen.mode}  {gen.model}"
            f"  run {gen.run_id[:12]}"
        )
    lines.append(f"reviews:   {len(provenance.reviewer_edits)} edit(s)")
    for edit in provenance.reviewer_edits:
        verdict = edit.verdict.value if edit.verdict is not None else "note"
        lines.append(f"  - [{verdict}] {edit.summary}")
    return lines


@unit_app.command("rm")
def unit_rm(
    unit_id: Annotated[str, typer.Argument(help="Unit to delete.")],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "--yes",
            help="Delete without an interactive prompt — required "
            "(this verb is non-interactive).",
        ),
    ] = False,
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """Delete a declared unit's directory and its drafted docs output.

    Parameters
    ----------
    unit_id : str
        The unit to delete.
    force : bool
        Delete without a prompt; required because the verb is non-interactive.
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    if not force:
        raise _fail(
            unit_id,
            message=(
                f"Refusing to delete {unit_id!r} without --force "
                "(this verb is non-interactive)."
            ),
            reason=_REASON_CONFIRM_REQUIRED,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        )
    store = compose.default_store()
    root = Path.cwd()
    seam = _seam(store, root, no_commit=no_commit)
    request = compose.build_remove_request(unit_id, root=root, store=store, repo=seam)
    try:
        remove_use_case(request)
    except UnitNotFoundError as exc:
        raise _fail(
            unit_id,
            message=f"No such unit: {unit_id!r}",
            reason=_REASON_UNIT_NOT_FOUND,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except ValueError as exc:
        raise _fail(
            unit_id,
            message=f"Invalid unit id: {exc}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        _emit_json(unit=unit_id, commit=sha)
    else:
        typer.echo(f"Removed {unit_id}")


@unit_app.command("mv")
def unit_mv(
    old_id: Annotated[str, typer.Argument(help="Current unit id.")],
    new_id: Annotated[str, typer.Argument(help="New unit id.")],
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """Rename a unit's id everywhere it is stamped, moving its drafted output.

    Target rule: the output path's directory always survives; its basename is
    re-derived to ``<new_id>.md`` only when it was the id-derived
    ``<old_id>.md`` — a custom basename set via ``--target`` survives the
    rename. Use ``dogen unit edit --target`` to change the path itself.

    Parameters
    ----------
    old_id : str
        The current unit id.
    new_id : str
        The target unit id.
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    seam = _seam(store, root, no_commit=no_commit)
    request = compose.build_rename_request(
        old_id,
        new_id,
        root=root,
        store=store,
        repo=seam,
    )
    try:
        rename_use_case(request)
    except UnitExistsError as exc:
        raise _fail(
            new_id,
            message=f"Refusing to rename: {exc}",
            reason=_REASON_UNIT_EXISTS,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except UnitNotFoundError as exc:
        raise _fail(
            new_id,
            message=f"No such unit: {old_id!r}",
            reason=_REASON_UNIT_NOT_FOUND,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except ValueError as exc:
        raise _fail(
            new_id,
            message=f"Invalid unit id: {exc}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        _emit_json(unit=new_id, commit=sha)
    else:
        typer.echo(f"Renamed {old_id} -> {new_id}")


@app.command("signoff")
def signoff(
    unit_id: Annotated[str, typer.Argument(help="Unit to sign off.")],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "--re-sign",
            help="Overwrite an existing signoff act (re-sign).",
        ),
    ] = False,
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """Record the HITL gate act for a unit (UNIT-02, v1).

    The act freezes the whole plan: the author, timestamp, and a SHA-256 of
    the exact ``unit.md`` approved (plus the repo HEAD) land in provenance,
    and drafting is gated on its presence. Appending steering notes never
    needs a re-sign; changing the plan itself surfaces as a stale hash.

    Parameters
    ----------
    unit_id : str
        The unit to sign off.
    force : bool
        Overwrite an existing signoff act (re-sign) when set.
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    seam = _seam(store, root, no_commit=no_commit)
    request = compose.build_signoff_request(
        unit_id,
        root=root,
        store=store,
        force=force,
        repo=seam,
    )
    try:
        warn = signoff_use_case(request)
    except SignoffExistsError as exc:
        raise _fail(
            unit_id,
            message=(
                f"Refusing to re-sign {unit_id!r}: {exc}. Pass --re-sign to overwrite."
            ),
            reason=_REASON_SIGNOFF_EXISTS,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except GitIdentityError as exc:
        raise _fail(
            unit_id,
            message=f"Cannot record signoff: {exc}",
            reason=None,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(
            unit_id,
            message=f"Cannot read unit {unit_id!r}: {exc}",
            reason=_REASON_UNIT_EXISTS,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    if warn:
        typer.echo(
            f"Warning: re-signing {unit_id!r} which already has recorded "
            "generation(s); existing generations predate this new signoff act.",
            err=True,
        )
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        _emit_json(unit=unit_id, commit=sha)
    else:
        typer.echo(f"Recorded signoff for {unit_id}")


@app.command("steer")
def steer(
    unit_id: Annotated[str, typer.Argument(help="Unit to steer.")],
    note: Annotated[
        str,
        typer.Option(help="Guidance to append to the unit's steering stream."),
    ],
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """Append a guidance note to the unit's steering stream (v1).

    Gate-free and append-only: guidance flows without ceremony, is durable
    immediately, and the next draft pass reads it. (The v0 ``steer`` gate act
    is now ``dogen signoff``.)

    Parameters
    ----------
    unit_id : str
        The unit to steer.
    note : str
        The guidance text to append.
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    seam = _seam(store, root, no_commit=no_commit)
    request = compose.build_note_request(
        unit_id,
        root=root,
        store=store,
        note=note,
        repo=seam,
    )
    try:
        steer_use_case(request)
    except GitIdentityError as exc:
        raise _fail(
            unit_id,
            message=f"Cannot record steering note: {exc}",
            reason=None,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(
            unit_id,
            message=f"Cannot read unit {unit_id!r}: {exc}",
            reason=_REASON_UNIT_EXISTS,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        _emit_json(unit=unit_id, commit=sha)
    else:
        typer.echo(f"Appended steering note for {unit_id}")


@app.command("draft")
def draft(  # noqa: PLR0913, C901, PLR0912, PLR0915
    unit_id: Annotated[str, typer.Argument(help="Unit to draft.")],
    provider: Annotated[
        str | None,
        typer.Option(
            help="Drafting provider: host-harness|copilot|mock "
            "(default: repo config, else host-harness).",
        ),
    ] = None,
    draft_file: Annotated[
        Path | None,
        typer.Option(
            help="Path to the host agent's draft text (host-harness handoff).",
        ),
    ] = None,
    draft_dir: Annotated[
        Path | None,
        typer.Option(
            help="Staged handoff directory for a multi-file unit (v1.2): "
            "files map 1:1 by relative path onto the unit's target set. "
            "Mutually exclusive with --draft-file.",
        ),
    ] = None,
    report: Annotated[
        Path | None,
        typer.Option(
            help="Path to the passenger's context report "
            "(context_origins/tools_used/gaps YAML).",
        ),
    ] = None,
    resolve_only: Annotated[
        bool,
        typer.Option(
            "--resolve-only",
            help="Print the resolved provider and exit with zero side effects.",
        ),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option(help="Drafting model to request (provider default if unset)."),
    ] = None,
    model_version: Annotated[
        str | None,
        typer.Option(
            help="Host-asserted model version, recorded verbatim (passenger).",
        ),
    ] = None,
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """Run the drafting loop for a unit, or resolve the provider (DRAFT-05/06).

    Resolves the provider by the explicit v1 precedence (``--provider`` flag >
    ``DOGEN_PROVIDER`` env > repo config > ``host-harness``) — no silent
    capability probe. With ``--resolve-only`` it prints the resolution and
    returns with **zero side effects** (D-07). Otherwise it delegates to the
    draft use-case: the HITL gate refuses without a recorded signoff
    (``signoff_required``), the passenger's ``--report`` is validated and
    merged into the generation record, and the transition is committed through
    the seam. A plan changed since signoff is surfaced as a warning (and a
    ``stale_plan`` JSON field), never silently drafted over.

    Parameters
    ----------
    unit_id : str
        The unit to draft.
    provider : str or None
        The explicit ``--provider`` value; ``None`` defers to env/config.
    draft_file : Path or None
        The host-harness passenger handoff file (read at the compose root).
    draft_dir : Path or None
        The staged multi-file handoff directory (v1.2, read at the compose
        root); mutually exclusive with ``--draft-file``.
    report : Path or None
        The passenger's context report (read at the compose root, v1).
    resolve_only : bool
        Resolve and print the provider with zero side effects, then return.
    model : str or None
        The drafting model to request; ``None`` leaves the provider default.
    model_version : str or None
        The host-asserted model version, recorded verbatim (passenger only).
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    config, _ = compose.repo_config(store, root=root)
    try:
        provider_name = compose.resolve_provider_name(
            provider, os.environ.get(_PROVIDER_ENV), config.provider
        )
    except ValueError as exc:
        raise _fail(
            unit_id,
            message=f"Cannot resolve provider: {exc}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    if resolve_only:
        # D-07: report the resolution only — no builder call, no gate, no writes.
        if json_output:
            _emit_json(unit=unit_id, provider=provider_name)
        else:
            typer.echo(f"Resolved provider for {unit_id}: {provider_name}")
        return
    draft_text, pages, handoff_path = _resolve_passenger_input(
        unit_id,
        store=store,
        root=root,
        provider_name=provider_name,
        draft_file=draft_file,
        draft_dir=draft_dir,
        json_output=json_output,
    )
    try:
        # WR-06: build the provider (which validates the name and, for
        # host-harness, reads --draft-file at the compose root) INSIDE the try
        # so a bad name / missing handoff renders a clean exit-2.
        provider_obj = compose.make_provider(
            provider_name,
            draft_file=draft_file,
            draft_text=draft_text,
            pages=pages,
            model=model,
            model_version=model_version,
        )
        context_report = None
        if report is not None:
            try:
                context_report = compose.read_context_report(report)
            except (OSError, ValueError) as exc:
                raise _fail(
                    unit_id,
                    message=f"Cannot ingest the context report {report}: {exc}",
                    reason=_REASON_BAD_REPORT,
                    code=_EXIT_BAD_INPUT,
                    json_output=json_output,
                    provider=provider_name,
                ) from exc
        seam = _seam(store, root, no_commit=no_commit)
        request = compose.build_draft_request(
            unit_id,
            root=root,
            store=store,
            provider=provider_obj,
            provider_name=provider_name,
            model=model,
            report=context_report,
            handoff_path=handoff_path,
            repo=seam,
        )
        outcome = asyncio.run(draft_use_case(request))
    except SignoffRequiredError as exc:
        raise _fail(
            unit_id,
            message=f"Refusing to draft: {exc}",
            reason=_REASON_SIGNOFF_REQUIRED,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
            provider=provider_name,
        ) from exc
    except TargetClaimedError as exc:
        # OWN-03: the draft-time lease re-check refused an in-flight overlap.
        # Placed BEFORE the (FileNotFoundError, ValueError) clause because
        # TargetClaimedError subclasses FileExistsError — a clean domain refusal,
        # not an uncaught traceback (mirrors the declare/edit handlers).
        raise _fail(
            unit_id,
            message=f"Refusing to draft: {exc}",
            reason=_REASON_TARGET_CLAIMED,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
            provider=provider_name,
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(
            unit_id,
            message=f"Cannot draft {unit_id!r}: {exc}",
            reason=_REASON_UNIT_EXISTS,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
            provider=provider_name,
        ) from exc
    except RuntimeError as exc:
        # WR-01/D-10: classify the two backend domain errors by type-name so
        # the mock/host-harness path never pulls adapters/copilot (or the SDK).
        name = type(exc).__name__
        if name == "ModelRejectedError":
            raise _fail(
                unit_id,
                message=f"{exc}",
                reason=_REASON_MODEL_REJECTED,
                code=_EXIT_DOMAIN_REFUSAL,
                json_output=json_output,
                provider=provider_name,
            ) from exc
        if name == "BackendUnavailableError":
            raise _fail(
                unit_id,
                message=f"Copilot backend unavailable: {exc}",
                reason=_REASON_BACKEND_UNAVAILABLE,
                code=_EXIT_DOMAIN_REFUSAL,
                json_output=json_output,
                provider=provider_name,
            ) from exc
        raise
    if outcome.stale_plan:
        typer.echo(
            f"Warning: unit.md for {unit_id!r} changed after its signoff — "
            "review the plan and re-sign (`dogen signoff --re-sign`) if the "
            "changes are substantive.",
            err=True,
        )
    if outcome.unsteered_redraft:
        typer.echo(
            f"Warning: re-drafted {unit_id!r} with no recorded steering or "
            "review verdict since the last generation — record corrections "
            "with `dogen review --verdict fix` or `dogen steer --note` so "
            "the loop stays auditable.",
            err=True,
        )
    if outcome.model_unrecorded:
        typer.echo(
            f"Warning: no model recorded for this draft of {unit_id!r} — the "
            "harness hid it and --model was not given. Ask the TA which model "
            "wrote the page and pass --model so the provenance names it.",
            err=True,
        )
    progress = derive_progress(_load_or_init_provenance(store, root, unit_id)).value
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        _emit_json(
            unit=unit_id,
            provider=provider_name,
            draft_path=str(outcome.path),
            progress=progress,
            stale_plan=outcome.stale_plan,
            unsteered_redraft=outcome.unsteered_redraft,
            model_unrecorded=outcome.model_unrecorded,
            commit=sha,
        )
    else:
        typer.echo(f"Drafted {unit_id} via {provider_name} -> {outcome.path}")


@app.command("review")
def review(  # noqa: PLR0913
    unit_id: Annotated[str, typer.Argument(help="Unit to review.")],
    note: Annotated[str, typer.Option(help="The reviewer's verdict note.")],
    verdict: Annotated[
        ReviewVerdict,
        typer.Option(
            help="Structured verdict: accept seals the draft; fix/redraft "
            "append the note to the steering stream for the next pass.",
        ),
    ],
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """Record a structured review and advance progress (REVIEW-01/02, v1).

    ``accept`` stamps the exact draft's SHA-256 on the edit (the sealed
    bookend); ``fix``/``redraft`` also append the note to the steering stream
    so the next ``dogen draft`` reads the correction. The output carries the
    deterministic ``next`` routing hint (after ``fix``/``redraft`` the next
    actor is the drafting flow, never the reviewer editing files). A unit
    that was never drafted exits ``2`` (``reason=not_drafted``); an ``accept``
    that would duplicate the latest sealed accept for the identical draft
    exits ``1`` (``reason=already_accepted``) and records nothing.

    Parameters
    ----------
    unit_id : str
        The unit to review.
    note : str
        The reviewer's verdict note.
    verdict : ReviewVerdict
        The structured verdict (``accept`` / ``fix`` / ``redraft``).
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    seam = _seam(store, root, no_commit=no_commit)
    request = compose.build_review_request(
        unit_id,
        root=root,
        store=store,
        note=note,
        verdict=verdict,
        repo=seam,
    )
    try:
        outcome = review_use_case(request)
    except NotDraftedError as exc:
        raise _fail(
            unit_id,
            message=(
                f"Cannot review {unit_id!r}: it has not been drafted yet — "
                f"run `dogen draft {unit_id}` first."
            ),
            reason=_REASON_NOT_DRAFTED,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    except AlreadyAcceptedError as exc:
        raise _fail(
            unit_id,
            message=f"Nothing recorded: {exc}.",
            reason=_REASON_ALREADY_ACCEPTED,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except GitIdentityError as exc:
        raise _fail(
            unit_id,
            message=f"Cannot record review: {exc}",
            reason=None,
            code=_EXIT_DOMAIN_REFUSAL,
            json_output=json_output,
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise _fail(
            unit_id,
            message=f"Cannot read unit {unit_id!r}: {exc}",
            reason=_REASON_UNIT_EXISTS,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    if outcome.unapplied_steering:
        typer.echo(
            f"Warning: accepted {unit_id!r} while a correction recorded after "
            "the last draft sits unapplied in the steering stream — it was "
            "sealed over, never drafted against. Re-draft first if it still "
            "applies.",
            err=True,
        )
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        _emit_json(
            unit=unit_id,
            progress=outcome.state.value,
            verdict=verdict.value,
            next=outcome.next_action,
            next_id=outcome.next_id,
            unapplied_steering=outcome.unapplied_steering,
            commit=sha,
        )
    else:
        typer.echo(
            f"Reviewed {unit_id} ({verdict.value}): progress -> {outcome.state.value}"
        )
        typer.echo(f"Next: {outcome.next_action}")


@app.command("status")
def status(json_output: _JsonOutput = False) -> None:
    """Show the repo-level board: every unit, its state, and the next verb (v1).

    Parameters
    ----------
    json_output : bool
        Emit a single-line JSON array instead of the plain table.
    """
    store = compose.default_store()
    rows = unit_statuses_use_case(
        compose.build_list_request(root=Path.cwd(), store=store)
    )
    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "unit": r.unit_id,
                        "intent": r.intent.value,
                        "state": r.state.value,
                        "signed_off": r.signed_off,
                        "stale_plan": r.stale_plan,
                        "next": r.next_action,
                        "next_id": r.next_id,
                        "title": r.title,
                    }
                    for r in rows
                ]
            )
        )
        return
    if not rows:
        typer.echo("No units. Declare one with `dogen unit new`.")
        return
    headers = ("ID", "STATE", "SIGNOFF", "NEXT")
    table = [
        (
            r.unit_id,
            r.state.value,
            ("stale" if r.stale_plan else "yes") if r.signed_off else "no",
            r.next_action,
        )
        for r in rows
    ]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in table))
        for i in range(len(headers))
    ]
    for cols in [headers, *table]:
        typer.echo("  ".join(col.ljust(widths[i]) for i, col in enumerate(cols)))


@provider_app.command("show")
def provider_show(json_output: _JsonOutput = False) -> None:
    """Explain the provider resolution: the effective name, why, and viability.

    Parameters
    ----------
    json_output : bool
        Emit the structured JSON object instead of the plain report.
    """
    store = compose.default_store()
    root = Path.cwd()
    config, config_exists = compose.repo_config(store, root=root)
    env = os.environ.get(_PROVIDER_ENV)
    configured = config.provider if config_exists else None
    try:
        effective = compose.resolve_provider_name(None, env, configured)
        source = compose.provider_resolution_source(None, env, configured)
    except ValueError as exc:
        raise _fail(
            "",
            message=f"Provider resolution is broken: {exc}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    viable = compose.copilot_viable()
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "provider": effective,
                    "source": source,
                    "copilot_viable": viable,
                    "commits": config.commits.value,
                }
            )
        )
        return
    typer.echo(f"provider: {effective} (from {source})")
    typer.echo(f"copilot viable: {'yes' if viable else 'no'} (diagnostic only)")
    typer.echo(f"commits: {config.commits.value}")


@provider_app.command("set")
def provider_set(
    name: Annotated[
        str,
        typer.Argument(help="Provider to pin: host-harness|copilot|mock."),
    ],
    json_output: _JsonOutput = False,
) -> None:
    """Pin the repo's drafting provider in ``.dogen/config.yaml`` (v1).

    Parameters
    ----------
    name : str
        The provider to pin (``host-harness`` / ``copilot`` / ``mock``).
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    try:
        resolved = compose.resolve_provider_name(name, None, None)
    except ValueError as exc:
        raise _fail(
            "",
            message=str(exc),
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    config, _ = compose.repo_config(store, root=root)
    config.provider = resolved
    written = store.write_config(config, root=root)
    if json_output:
        typer.echo(json.dumps({"provider": resolved, "config": str(written)}))
    else:
        typer.echo(f"Pinned provider {resolved} in {written}")


@app.command("commits")
def commits(
    mode: Annotated[
        CommitMode,
        typer.Argument(help="Commit-seam posture: auto|off."),
    ],
    json_output: _JsonOutput = False,
) -> None:
    """Set the repo's commit-seam posture in ``.dogen/config.yaml`` (v1).

    Parameters
    ----------
    mode : CommitMode
        ``auto`` commits every lifecycle transition; ``off`` disables the
        seam (a per-invocation ``--no-commit`` also exists on each verb).
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    config, _ = compose.repo_config(store, root=root)
    config.commits = mode
    written = store.write_config(config, root=root)
    if json_output:
        typer.echo(json.dumps({"commits": mode.value, "config": str(written)}))
    else:
        typer.echo(f"Commit seam set to {mode.value} in {written}")


@context_app.command("ls")
def context_ls(json_output: _JsonOutput = False) -> None:
    """List the context artifacts in the B1/B2 landing zone (v1).

    Parameters
    ----------
    json_output : bool
        Emit a single-line JSON array instead of plain lines.
    """
    store = compose.default_store()
    names = store.list_context(root=Path.cwd())
    if json_output:
        typer.echo(json.dumps(names))
        return
    if not names:
        typer.echo(
            "No context artifacts. Add one with "
            "`dogen context add <file> [--as <name>]`."
        )
        return
    for name in names:
        typer.echo(f".dogen/context/{name}")


@context_app.command("add")
def context_add(
    file: Annotated[
        Path,
        typer.Argument(help="The artifact file to land (free-form welcome)."),
    ],
    as_name: Annotated[
        str | None,
        typer.Option(
            "--as",
            help="Landing filename (well-known: doc-style.md, glossary.md, "
            "structure.md, code-to-docs-map.md, doc-gaps.md); defaults to "
            "the file's name.",
        ),
    ] = None,
    no_commit: _NoCommit = False,
    json_output: _JsonOutput = False,
) -> None:
    """File a B1/B2 artifact into ``.dogen/context/`` and commit it (v1).

    Parameters
    ----------
    file : Path
        The artifact file to land, read at the compose root.
    as_name : str or None
        The landing filename; defaults to the source file's basename.
    no_commit : bool
        Skip the transition commit for this invocation.
    json_output : bool
        Emit the structured JSON object instead of a plain line.
    """
    store = compose.default_store()
    root = Path.cwd()
    name = as_name or file.name
    try:
        text = file.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise _fail(
            name,
            message=f"Cannot read {file}: {exc}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    seam = _seam(store, root, no_commit=no_commit)
    request = compose.build_context_request(
        name,
        text=text,
        root=root,
        store=store,
        repo=seam,
    )
    try:
        written = context_add_use_case(request)
    except ValueError as exc:
        raise _fail(
            name,
            message=f"Cannot land context artifact: {exc}",
            reason=None,
            code=_EXIT_BAD_INPUT,
            json_output=json_output,
        ) from exc
    sha = _report_git(seam, no_commit=no_commit)
    if json_output:
        typer.echo(json.dumps({"context": name, "path": str(written), "commit": sha}))
    else:
        typer.echo(f"Landed {written}")


if __name__ == "__main__":
    app()
