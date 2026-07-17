"""The composition root (D-10): wire obs + providers + seam + requests.

This module is the single place that assembles the concrete host collaborators
the core use-cases depend on — the local-mode observability backend (``obs/``),
the by-name provider selector (``adapters/``), the git-identity port, the
commit seam (``adapters/git_repo``), the filesystem store, and the real
wall-clock — into the frozen request dataclasses (``core.orchestrator``). The
CLI reuses these builders instead of re-implementing the wiring.

It lives under ``dogen.app`` (NOT ``dogen.core``) on purpose: composition is
allowed to import ``adapters/`` and ``obs/``, whereas ``dogen.core`` must not
(the import-linter provider-seam contract — Pitfall 6).

v1 provider resolution is **explicit** (the RC-5 decision): the precedence is
``--provider`` flag > ``DOGEN_PROVIDER`` env > repo config
(``.dogen/config.yaml``) > the built-in ``host-harness`` default. No capability
probe ever silently picks a provider — the old ``auto`` value is rejected with
a pointer to ``dogen provider``, and the offline Copilot probe survives only as
a diagnostic surfaced by ``dogen provider show``.
"""

import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml
from pydantic import ValidationError

from dogen.adapters.git_identity import read_git_identity
from dogen.adapters.git_repo import GitRepoError, GitRepoSeam
from dogen.adapters.mock_provider import _probe_copilot_available, select_provider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.core.models import (
    ContextReport,
    DogenConfig,
    Effort,
    Intent,
    ReviewVerdict,
    SourceRef,
    SteeringOrigin,
    Step,
    StepMode,
    StepVerdict,
)
from dogen.core.orchestrator import (
    Clock,
    ContextAddRequest,
    DeclareRequest,
    DraftRequest,
    EditRequest,
    ListRequest,
    NoteRequest,
    PlanStepsRequest,
    RecordStepRequest,
    RemoveRequest,
    RenameRequest,
    ReviewRequest,
    SignoffRequest,
)
from dogen.core.ports import (
    DraftingProvider,
    Identity,
    PlanningStore,
    RepoSeam,
)
from dogen.obs.logfire_backend import configure_observability

#: The built-in provider default (v1): the hardened host-harness passenger.
DEFAULT_PROVIDER = "host-harness"
#: The selectable provider names; ``auto`` is deliberately NOT one of them.
KNOWN_PROVIDERS = ("host-harness", "copilot", "mock")
#: The retired v0 selection value, rejected with a pointer to the new surface.
_RETIRED_AUTO = "auto"
#: The passenger provider name whose draft text the compose root reads from
#: ``--draft-file`` (D-03) — the only provider needing compose-root file IO.
_HOST_HARNESS_PROVIDER = "host-harness"
_MOCK_PROVIDER = "mock"


def utc_now() -> str:
    """Return the current time as an ISO-8601 UTC timestamp (the real clock).

    Returns
    -------
    str
        The current UTC time in ISO-8601 form, used as the composition-root
        ``now`` clock so recorded timestamps reflect real ordering.
    """
    return datetime.now(UTC).isoformat()


def git_identity() -> tuple[str, str]:
    """Return the operator's ``(name, email)`` from git config (Identity port).

    Returns
    -------
    tuple of (str, str)
        The ``(name, email)`` recorded as the signoff author / reviewer.
    """
    return read_git_identity()


def default_store() -> FilesystemPlanningStore:
    """Return the filesystem planning-directory store used by the loop.

    Returns
    -------
    FilesystemPlanningStore
        The concrete :data:`PlanningStore` implementation writing under
        ``.dogen/units/<id>/`` and ``docs/``.
    """
    return FilesystemPlanningStore()


class _TolerantSeam:
    """A :class:`RepoSeam` wrapper that degrades commit failures to warnings.

    The transition's artifact writes have already succeeded by the time the
    seam commits; a git failure (say, an unconfigured identity) must therefore
    warn — surfacing through the injected callback — rather than fail the verb
    and strand the operator mid-loop.

    The wrapper also stashes the last commit's hash and subject
    (``last_sha`` / ``last_subject``, v1.2 R5): the CLI owns the seam
    instance, so after a use case returns it can surface the git event —
    ``[git] committed <sha7> — <subject>`` — without any core signature
    changing hands.

    Parameters
    ----------
    inner : GitRepoSeam
        The real seam to delegate to.
    on_error : callable or None
        Receives the failure message; ``None`` swallows silently (tests).
    """

    def __init__(
        self, inner: GitRepoSeam, on_error: Callable[[str], None] | None
    ) -> None:
        self._inner = inner
        self._on_error = on_error
        #: The last transition commit's hash; ``""`` until one lands.
        self.last_sha: str = ""
        #: The last transition commit's subject line; ``""`` until one lands.
        self.last_subject: str = ""

    def head_commit(self, *, root: Path) -> str:
        """Return the repo's HEAD commit hash (delegated).

        Parameters
        ----------
        root : Path
            The repo root.

        Returns
        -------
        str
            The HEAD hash, or ``""`` when unavailable.
        """
        return self._inner.head_commit(root=root)

    def tracked(self, *, root: Path, paths: list[str]) -> set[str]:
        """Return the tracked subset of ``paths`` (delegated, no failure mode).

        Parameters
        ----------
        root : Path
            The repo root.
        paths : list of str
            Repo-relative candidate paths.

        Returns
        -------
        set of str
            The tracked members of ``paths``; empty outside a git repo.
        """
        return self._inner.tracked(root=root, paths=paths)

    def commit(self, *, root: Path, paths: list[Path], message: str) -> str:
        """Commit through the seam, converting a failure into a warning.

        Parameters
        ----------
        root : Path
            The repo root.
        paths : list of Path
            The paths to stage and commit.
        message : str
            The full commit message.

        Returns
        -------
        str
            The new commit hash, or ``""`` on a no-op or a warned failure.
        """
        try:
            sha = self._inner.commit(root=root, paths=paths, message=message)
        except GitRepoError as exc:
            if self._on_error is not None:
                self._on_error(str(exc))
            return ""
        if sha:
            self.last_sha = sha
            self.last_subject = message.splitlines()[0] if message else ""
        return sha


def make_repo_seam(
    *, enabled: bool, on_error: Callable[[str], None] | None = None
) -> RepoSeam | None:
    """Return the commit seam, or ``None`` when transitions are not committed.

    Parameters
    ----------
    enabled : bool
        The resolved posture: the repo config's ``commits: auto`` minus any
        per-invocation ``--no-commit``.
    on_error : callable or None
        Receives a commit-failure message so the CLI can warn without failing
        the verb (the artifact writes already succeeded).

    Returns
    -------
    RepoSeam or None
        A tolerant :class:`~dogen.adapters.git_repo.GitRepoSeam` when enabled,
        else ``None`` (the use-cases skip stamps and transition commits).
    """
    return _TolerantSeam(GitRepoSeam(), on_error) if enabled else None


def repo_config(store: PlanningStore, *, root: Path) -> tuple[DogenConfig, bool]:
    """Read the repo config plus whether a config file actually exists.

    Parameters
    ----------
    store : PlanningStore
        The injected planning-directory store.
    root : Path
        The repo root.

    Returns
    -------
    tuple of (DogenConfig, bool)
        The effective config (model defaults when absent) and a flag telling
        whether ``.dogen/config.yaml`` exists — ``provider show`` uses the
        flag to report the deciding precedence level truthfully.
    """
    exists = (root / ".dogen" / "config.yaml").is_file()
    return store.read_config(root=root), exists


def copilot_viable() -> bool:
    """Report whether the Copilot driver *could* run — a diagnostic only (v1).

    The offline capability probe (SDK importable + auth env present + not
    disabled) survives from v0 purely as ``dogen provider show`` information;
    it never selects a provider (RC-5).

    Returns
    -------
    bool
        ``True`` when the offline signals say the driver would be usable.
    """
    return _probe_copilot_available()


def resolve_provider_name(
    flag: str | None = None,
    env: str | None = None,
    configured: str | None = None,
) -> str:
    """Resolve the effective provider name by the explicit v1 precedence.

    ``--provider`` flag > ``DOGEN_PROVIDER`` env > repo config > the built-in
    ``host-harness`` default. The v0 ``auto`` probe value is retired: passing
    it (from any level) is an error pointing at the explicit surface, so a
    provider choice is always a recorded human/config decision, never a silent
    capability fallback (RC-5).

    Parameters
    ----------
    flag : str or None
        The explicit ``--provider`` value, or ``None`` when omitted.
    env : str or None
        The ``DOGEN_PROVIDER`` environment value (CI pins ``mock``), or
        ``None``.
    configured : str or None
        The repo config's ``provider`` value, or ``None`` when no config
        exists (the model default applies).

    Returns
    -------
    str
        A concrete provider name (``host-harness`` / ``copilot`` / ``mock``).

    Raises
    ------
    ValueError
        If the chosen value is ``auto`` (retired) or not a known provider.
    """
    chosen = flag or env or configured or DEFAULT_PROVIDER
    if chosen == _RETIRED_AUTO:
        raise ValueError(
            "provider 'auto' is retired: selection is explicit now — set the "
            "provider with `dogen provider set <name>` (repo config), the "
            "DOGEN_PROVIDER env var, or --provider"
        )
    if chosen not in KNOWN_PROVIDERS:
        known = ", ".join(KNOWN_PROVIDERS)
        raise ValueError(f"unknown provider {chosen!r}; choose one of: {known}")
    return chosen


def provider_resolution_source(
    flag: str | None = None,
    env: str | None = None,
    configured: str | None = None,
) -> str:
    """Name the precedence level that decided the provider (``provider show``).

    Parameters
    ----------
    flag : str or None
        The explicit ``--provider`` value.
    env : str or None
        The ``DOGEN_PROVIDER`` environment value.
    configured : str or None
        The repo config's ``provider`` value (``None`` when no file exists).

    Returns
    -------
    str
        One of ``"flag"``, ``"env"``, ``"repo config"``, or ``"default"``.
    """
    if flag:
        return "flag"
    if env:
        return "env"
    if configured:
        return "repo config"
    return "default"


def resolve_model_name(
    flag: str | None = None,
    env: str | None = None,
    configured: str | None = None,
) -> str:
    """Resolve the effective drafting model by the explicit §D4 precedence.

    ``--model`` flag > ``DOGEN_MODEL`` env > repo config, with **no default** —
    an unresolved model is a legal, honest-empty value (``""``) that fires
    ``model_unrecorded`` downstream. This is the one divergence from
    :func:`resolve_provider_name`: the provider falls back to the built-in
    ``host-harness`` passenger, but a model has no host-harness analog to
    silently assume, so absence is recorded truthfully rather than defaulted
    (D-03, MODEL-01).

    Parameters
    ----------
    flag : str or None
        The explicit ``--model`` value, or ``None`` / ``""`` when omitted.
    env : str or None
        The ``DOGEN_MODEL`` environment value, or ``None`` / ``""``.
    configured : str or None
        The repo config's ``model`` value, or ``None`` / ``""`` when unset.

    Returns
    -------
    str
        The resolved model name, or ``""`` when all three inputs are falsy.
    """
    return flag or env or configured or ""


def model_resolution_source(
    flag: str | None = None,
    env: str | None = None,
    configured: str | None = None,
) -> str:
    """Name the precedence level that decided the model (``model show`` label).

    The show-source label keeps ``env`` distinct (it reports *where* the value
    came from), unlike :func:`model_generation_origin`, which folds ``env`` into
    the ``flag`` operator-override tier for the vouch record. The two diverge by
    design (D-03) and must stay separate functions.

    Parameters
    ----------
    flag : str or None
        The explicit ``--model`` value.
    env : str or None
        The ``DOGEN_MODEL`` environment value.
    configured : str or None
        The repo config's ``model`` value (``None`` / ``""`` when unset).

    Returns
    -------
    str
        One of ``"flag"``, ``"env"``, ``"repo config"``, or ``"default"``.
    """
    if flag:
        return "flag"
    if env:
        return "env"
    if configured:
        return "repo config"
    return "default"


def model_generation_origin(
    flag: str | None = None,
    env: str | None = None,
    configured: str | None = None,
    configured_origin: str | None = None,
) -> str:
    """Derive the ``model_origin`` stamped on a generation (the D-03 vouch table).

    Encodes **who vouched** for the resolved model, reconciled with the
    precedence chain (D-03), in the frozen ``""|ta|self|config|flag`` vocab:

    * ``--model`` flag set → ``flag``.
    * ``DOGEN_MODEL`` env set (no flag) → ``flag`` (same operator-override tier;
      env carries no ta/self vouch and has no dedicated slot in the vocab).
    * config model (no flag/env) with ``configured_origin`` ``ta`` → ``ta``;
      ``self`` → ``self`` (the human/agent vouch carried through onto the
      generation).
    * config model present but unattributed (``configured_origin`` empty, e.g. a
      hand-edited config) → ``config`` (the honest fallback).
    * nothing resolved → ``""`` (fires ``model_unrecorded``).

    This is the show-source label's divergent twin: it must **not** be collapsed
    into :func:`model_resolution_source` (env → label ``env`` but origin
    ``flag``).

    Parameters
    ----------
    flag : str or None
        The explicit ``--model`` value.
    env : str or None
        The ``DOGEN_MODEL`` environment value.
    configured : str or None
        The repo config's ``model`` value.
    configured_origin : str or None
        The repo config's stored ``model_origin`` (``ta`` / ``self`` / ``""``);
        consulted only when ``configured`` is the deciding level.

    Returns
    -------
    str
        One of ``""``, ``"ta"``, ``"self"``, ``"config"``, or ``"flag"``.
    """
    if flag or env:
        return "flag"
    if configured:
        if configured_origin in ("ta", "self"):
            return configured_origin
        return "config"
    return ""


def validate_model_name(name: str) -> str:
    """Validate a model name before it enters a trailer or a YAML scalar (V5).

    A model name crosses from the operator into a ``.dogen/config.yaml`` scalar
    and later a ``Dogen-Model:`` commit trailer (the audit-replay contract), so
    it must be a single, non-empty, control-char-free line — mirroring the
    ``extends``-owner single-segment validation precedent
    (:func:`dogen.core.orchestrator._transition_message`). This refuses the
    newline / control-char injection surface (threats T-08-01 / T-08-02) at the
    boundary, before persistence or stamping.

    Parameters
    ----------
    name : str
        The candidate model name supplied by the operator.

    Returns
    -------
    str
        The validated name, unchanged, for the caller to persist or stamp.

    Raises
    ------
    ValueError
        If ``name`` is empty or contains a newline or any other control
        character (a name that could break the trailer or YAML scalar).
    """
    if not name:
        raise ValueError("model name must not be empty")
    # ``str.isprintable`` is False for any control character (newline, tab, NUL,
    # DEL, …) while keeping ordinary spaces printable — exactly the single-line,
    # no-control-char rule, with no magic ordinals.
    if not name.isprintable():
        raise ValueError(
            "model name must be a single line with no control characters "
            f"(got {name!r})"
        )
    return name


def _read_draft_file(draft_file: Path) -> str:
    """Read the host's draft text from ``--draft-file`` at the compose root (D-03).

    Parameters
    ----------
    draft_file : Path
        The path the operator passed as ``--draft-file``.

    Returns
    -------
    str
        The draft text the host agent produced.
    """
    return Path(draft_file).read_text(encoding="utf-8")


class StepsFileError(ValueError):
    """Raised when a ``--steps-file`` payload is malformed (v1.2, T-12-03).

    The untrusted step plan is parsed and validated at the compose root (V5):
    the file must be a YAML list of step mappings, each validating into a typed
    :class:`~dogen.core.models.Step`. A malformed shape is refused HERE with a
    stable reason — never a raw traceback, and no ``Path``/``yaml`` reaches
    ``core/``.
    """


class EvidenceFileError(ValueError):
    """Raised when an ``--evidence-file`` payload is malformed (v1.2, T-12-03).

    Distinct from the record-time micro-gate: this is a *boundary* refusal for
    an unparseable/ill-typed evidence file (bad YAML, an unknown verdict/mode
    token, a non-integer exit code). A well-formed file whose evidence is merely
    ill-shaped *for its verdict* (a ``pass`` with no hash) is NOT refused here —
    it crosses into :func:`record_step` and the micro-gate raises
    ``EvidenceRequiredError``, so the two refusal classes stay separable.
    """


@dataclass(frozen=True)
class _EvidenceFileInput:
    """The validated raw evidence fields read from an ``--evidence-file`` (v1.2).

    A compose-root carrier for the fields :class:`RecordStepRequest` needs. It
    deliberately does NOT build a :class:`~dogen.core.models.StepEvidence`: the
    frozen Plan 02 seam takes ``exit_code: int | None`` so the micro-gate can see
    a *missing* exit code, which a pre-built ``StepEvidence`` (required ``int``)
    could not express. ``step_text_sha256`` and ``at`` are dogen's to bind, so
    they are never read from the operator's file.
    """

    verdict: StepVerdict
    mode: StepMode = StepMode.agent
    command: str = ""
    output_sha256: str = ""
    output_excerpt: str = ""
    exit_code: int | None = None
    reason: str = ""
    deterministic: bool = True


def _read_maybe_stdin(path: Path) -> str:
    """Read ``path`` at the compose root, or stdin when it is ``-`` (parity).

    Mirrors the ``--draft-file``/``--note-file`` ``-`` convention: the untrusted
    bytes are read HERE, never inside ``core/``.
    """
    if str(path) == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _read_steps_file(steps_file: Path) -> list[Step]:
    """Read + validate a ``--steps-file`` into a typed step plan (v1.2, V5).

    The file is a YAML list of step mappings; each entry is validated into a
    typed :class:`~dogen.core.models.Step` HERE, so only typed values cross into
    the :func:`plan_steps` use-case. Any evidence a caller inlines is ignored by
    ``plan_steps`` (D-12 carry-forward is by text hash), so it is not a channel
    for forging proof.

    Parameters
    ----------
    steps_file : Path
        The ``--steps-file`` path (``-`` reads stdin).

    Returns
    -------
    list of Step
        The validated step plan (may be empty).

    Raises
    ------
    StepsFileError
        If the payload is not YAML, is not a list, or any entry fails validation.
    """
    try:
        data = yaml.safe_load(_read_maybe_stdin(steps_file)) or []
    except yaml.YAMLError as exc:
        raise StepsFileError(f"--steps-file is not valid YAML: {exc}") from exc
    if not isinstance(data, list):
        raise StepsFileError(
            "--steps-file must be a YAML list of step mappings "
            f"(got {type(data).__name__})"
        )
    steps: list[Step] = []
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise StepsFileError(
                f"--steps-file entry {index} must be a mapping "
                f"(got {type(entry).__name__})"
            )
        try:
            steps.append(Step.model_validate(entry))
        except ValidationError as exc:
            raise StepsFileError(
                f"--steps-file entry {index} is not a valid step: {exc}"
            ) from exc
    return steps


def _read_evidence_file(evidence_file: Path) -> _EvidenceFileInput:
    """Read + validate an ``--evidence-file`` into typed raw fields (v1.2, V5).

    The file is a YAML mapping. The ``verdict`` (and optional ``mode``) tokens
    are validated against their four-/two-token vocabularies and ``exit_code``
    against ``int``/absent — a boundary refusal (:class:`EvidenceFileError`) for
    any malformed shape. ``step_text_sha256``/``at`` are never read (dogen binds
    them); an oversized ``output_excerpt`` is bounded by the model's excerpt cap
    when :func:`record_step` constructs the persisted evidence (D-01).

    Parameters
    ----------
    evidence_file : Path
        The ``--evidence-file`` path (``-`` reads stdin).

    Returns
    -------
    _EvidenceFileInput
        The validated raw fields for a :class:`RecordStepRequest`.

    Raises
    ------
    EvidenceFileError
        If the payload is not a YAML mapping, or a field is ill-typed / carries
        an unknown verdict or mode token.
    """
    try:
        data = yaml.safe_load(_read_maybe_stdin(evidence_file)) or {}
    except yaml.YAMLError as exc:
        raise EvidenceFileError(f"--evidence-file is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise EvidenceFileError(
            "--evidence-file must be a YAML mapping "
            f"(got {type(data).__name__})"
        )
    try:
        verdict = StepVerdict(data["verdict"])
    except KeyError as exc:
        raise EvidenceFileError(
            "--evidence-file must carry a 'verdict' "
            "(pass/fail/skipped/deviated)"
        ) from exc
    except ValueError as exc:
        raise EvidenceFileError(
            f"--evidence-file 'verdict' must be one of "
            f"{[v.value for v in StepVerdict]} (got {data['verdict']!r})"
        ) from exc
    try:
        mode = StepMode(data.get("mode", StepMode.agent.value))
    except ValueError as exc:
        raise EvidenceFileError(
            f"--evidence-file 'mode' must be one of {[m.value for m in StepMode]} "
            f"(got {data.get('mode')!r})"
        ) from exc
    exit_code = data.get("exit_code")
    if exit_code is not None and not isinstance(exit_code, int):
        raise EvidenceFileError(
            f"--evidence-file 'exit_code' must be an integer or absent "
            f"(got {type(exit_code).__name__})"
        )
    return _EvidenceFileInput(
        verdict=verdict,
        mode=mode,
        command=str(data.get("command", "")),
        output_sha256=str(data.get("output_sha256", "")),
        output_excerpt=str(data.get("output_excerpt", "")),
        exit_code=exit_code,
        reason=str(data.get("reason", "")),
        deterministic=bool(data.get("deterministic", True)),
    )


class HandoffIncompleteError(ValueError):
    """Raised when a ``--draft-dir`` handoff misses a declared target (v1.2).

    Every page in the unit's set must be staged — a horizontal fix that
    silently skips one of its declared pages is an incomplete change, not a
    partial success.
    """


class UndeclaredTargetError(ValueError):
    """Raised when a ``--draft-dir`` handoff stages an undeclared file (v1.2).

    A staged page outside the unit's declared target set would land outside
    the signed-off plan — refused with zero mutation.
    """


# Every handoff refusal ends with this sentence so the agent never repeats the
# round-3 trap (flat-staged pages -> handoff_incomplete -> ``rm -rf`` of its own
# fresh drafts). The layout is fixed by *moving* files, never by deleting them.
_HANDOFF_NEVER_DELETE = "move the staged files into place; do not delete them"

# Emitted once (D-01) when the whole-set basename fallback maps a flat handoff.
_HANDOFF_MAPPED_BY_BASENAME = "handoff staged flat; mapped by basename"


def _by_basename(paths: list[str]) -> dict[str, list[str]]:
    """Group docs-relative paths by their basename (``{basename: [relpath]}``)."""
    grouped: dict[str, list[str]] = {}
    for rel in paths:
        grouped.setdefault(PurePosixPath(rel).name, []).append(rel)
    return grouped


def _handoff_incomplete_message(
    missing: list[str],
    *,
    exp_by_base: dict[str, list[str]],
    stg_by_base: dict[str, list[str]],
) -> str:
    """Build the enumerated, ambiguity-aware ``handoff_incomplete`` message (D-02b).

    Enumerates the exact expected path per missing target and, when the
    basename fallback was declined for a collision, names the colliding
    basename(s) on whichever side collided and points at the exact relpaths.
    Always ends with :data:`_HANDOFF_NEVER_DELETE`.
    """
    parts: list[str] = []
    if missing:
        parts.append(
            "the handoff is missing a staged file for declared target(s): "
            + "; ".join(f"expected: handoff/{t}" for t in missing)
        )
    # Declared-side collisions: two targets share a basename (D-02).
    for base, targets in sorted(exp_by_base.items()):
        if len(targets) > 1:
            parts.append(
                f"{base} is ambiguous across {', '.join(sorted(targets))} — "
                "stage each page at its exact handoff/<relpath>"
            )
    # Staged-side collisions: two staged files share a basename (Pitfall 1).
    for base, rels in sorted(stg_by_base.items()):
        if len(rels) > 1:
            parts.append(
                f"two staged files share basename {base} "
                f"({', '.join(sorted(rels))}) — "
                "stage each page at its exact handoff/<relpath>"
            )
    parts.append(_HANDOFF_NEVER_DELETE)
    return "; ".join(parts)


def _undeclared_target_message(surplus: list[str]) -> str:
    """Build the enumerated ``undeclared_target`` message (D-02b).

    Names each surplus staged file and its move destination, ending with
    :data:`_HANDOFF_NEVER_DELETE`.
    """
    return (
        "the handoff stages file(s) outside the unit's target set: "
        + "; ".join(
            f"{rel} is not a declared target — move it into place or "
            "--also-target it first"
            for rel in surplus
        )
        + "; "
        + _HANDOFF_NEVER_DELETE
    )


def read_draft_dir(
    draft_dir: Path, *, primary: str, extras: list[str]
) -> tuple[str, dict[str, str], str | None]:
    """Read a multi-page handoff directory at the compose root (v1.2, D-03).

    Maps the staged files onto the unit's target set (``[primary, *extras]``)
    with a two-tier, whole-set strategy (STAGE-01, D-01):

    1. **Exact relpath** — every declared page staged at ``handoff/<relpath>``.
    2. **Basename fallback** — only when exact mapping leaves a declared target
       unmatched, the *whole* handoff is retried by basename. It applies only
       when every declared basename is unique AND every staged basename is
       unique AND the two basename key-sets are equal (uniqueness on BOTH sides,
       Pitfall 1). On success it emits the ``handoff staged flat; mapped by
       basename`` note. Any collision or mismatch declines the fallback and
       falls through to the enumerated refusal (D-02) — never a per-file mix.

    Parameters
    ----------
    draft_dir : Path
        The staged handoff directory (``--draft-dir``).
    primary : str
        The unit's primary docs-relative target.
    extras : list of str
        The unit's extra docs-relative targets.

    Returns
    -------
    tuple of (str, dict of str to str, str or None)
        The primary page's text, the extras keyed by target path, and an
        optional note (the ``mapped by basename`` notice, else ``None``).

    Raises
    ------
    ValueError
        If ``draft_dir`` is not a directory.
    HandoffIncompleteError
        If a declared target has no staged file, or an ambiguous flat handoff
        declines the basename fallback (D-02).
    UndeclaredTargetError
        If a staged file matches no declared target.
    """
    base = Path(draft_dir)
    if not base.is_dir():
        raise ValueError(f"--draft-dir is not a directory: {draft_dir}")
    staged = {
        p.relative_to(base).as_posix(): p
        for p in sorted(base.rglob("*"))
        if p.is_file()
    }
    expected = [primary, *extras]
    missing = [t for t in expected if t not in staged]
    if missing:
        # Tier 2 (D-01): retry the WHOLE handoff by basename. Accept only a
        # bijective, unambiguous mapping — uniqueness on both sides plus equal
        # key-sets; anything else declines to the enumerated refusal (D-02).
        exp_by_base = _by_basename(expected)
        stg_by_base = _by_basename(list(staged))
        declared_unique = all(len(v) == 1 for v in exp_by_base.values())
        staged_unique = all(len(v) == 1 for v in stg_by_base.values())
        key_sets_align = set(exp_by_base) == set(stg_by_base)
        if declared_unique and staged_unique and key_sets_align:
            remap = {exp_by_base[b][0]: staged[stg_by_base[b][0]] for b in exp_by_base}
            text = remap[primary].read_text(encoding="utf-8")
            pages = {t: remap[t].read_text(encoding="utf-8") for t in extras}
            return text, pages, _HANDOFF_MAPPED_BY_BASENAME
        raise HandoffIncompleteError(
            _handoff_incomplete_message(
                missing, exp_by_base=exp_by_base, stg_by_base=stg_by_base
            )
        )
    surplus = sorted(set(staged) - set(expected))
    if surplus:
        raise UndeclaredTargetError(_undeclared_target_message(surplus))
    text = staged[primary].read_text(encoding="utf-8")
    pages = {t: staged[t].read_text(encoding="utf-8") for t in extras}
    return text, pages, None


def read_context_report(report_file: Path) -> ContextReport:
    """Read and validate a passenger context report (``--report``, v1).

    Compose-root file IO by design (the D-03 precedent): the report is parsed
    and validated here, and only the typed :class:`ContextReport` crosses into
    ``core/``.

    The parse is lenient about *format* only (STAGE-04, D-08): the documented
    primary format is YAML (``report.yaml``), tried first with the safe loader;
    if that raises, a **silent** ``json.loads`` fallback accepts a report an
    operator authored as JSON (which stays valid under this reader without
    diverging the convention). Leniency never touches *validation* — a parsed
    report still runs the full :class:`ContextReport` validator (hex-or-empty
    commit stamps, the typed load boundary). When neither parser accepts the
    bytes, only the **YAML** parser's position is surfaced (YAML is the format
    the operator was targeting) — the JSON error is never echoed — together with
    a hint to quote any scalar containing ``::`` (the exact round-3 trap: an
    unquoted ``::`` plain scalar reads as a mapping value and rejects).

    Parameters
    ----------
    report_file : Path
        The path the operator passed as ``--report``.

    Returns
    -------
    ContextReport
        The validated report.

    Raises
    ------
    ValueError
        If the bytes parse as neither YAML nor JSON (the message names the YAML
        parser's 1-based line/column when known, plus the ``::``-quoting hint),
        or the report fails validation (v1.2: origin commit stamps must be hex
        or empty) — the CLI maps this to ``reason=bad_report``.
    """
    text = Path(report_file).read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        try:
            # Silent JSON fallback (D-08, Pitfall 5): a JSON report is accepted,
            # but its parse error is never surfaced — only the YAML mark is.
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # ``problem_mark`` is 0-indexed and may be None (Pitfall 2); guard.
            mark = getattr(exc, "problem_mark", None)
            where = (
                f" at line {mark.line + 1}, column {mark.column + 1}"
                if mark is not None
                else ""
            )
            problem = getattr(exc, "problem", None) or str(exc)
            raise ValueError(
                f"could not parse report as YAML or JSON: {problem}{where}. "
                "Hint: quote any scalar containing '::' "
                '(e.g. "a::b"), or YAML reads it as a mapping value.'
            ) from exc
    # CR-02: valid YAML/JSON that resolves to a non-mapping (a list or scalar)
    # would make ``ContextReport(**data)`` raise ``TypeError`` — which the CLI's
    # ``except (OSError, ValueError)`` does NOT catch, so it escaped as an
    # uncaught traceback and broke the D-10 ``reason=bad_report`` contract.
    # Guarantee a mapping first so the failure stays a ValueError on the
    # documented path (both the YAML and JSON-fallback arms reach here).
    if not isinstance(data, dict):
        raise ValueError(
            "report must be a YAML/JSON mapping "
            f"(got {type(data).__name__}); see `dogen report template`"
        )
    return ContextReport(**data)


def make_provider(  # noqa: PLR0913
    provider_name: str,
    *,
    draft_file: Path | None = None,
    draft_text: str | None = None,
    pages: dict[str, str] | None = None,
    model: str | None = None,
    model_version: str | None = None,
    effort: Effort | None = None,
) -> DraftingProvider:
    """Configure observability once and build the resolved provider by name.

    Parameters
    ----------
    provider_name : str
        The concrete provider name (``mock`` / ``copilot`` / ``host-harness``),
        already resolved by :func:`resolve_provider_name`.
    draft_file : Path or None
        The ``--draft-file`` path for the ``host-harness`` passenger; the
        passenger requires either this or ``draft_text``.
    draft_text : str or None
        Pre-read primary page text for the passenger (v1.2: the
        ``--draft-dir`` flow reads the staged pages via
        :func:`read_draft_dir` and passes them here).
    pages : dict of str to str or None
        Pre-read extra pages for a multi-file passenger draft (v1.2).
    model : str or None
        Optional model name threaded to the provider factory.
    model_version : str or None
        Optional host-asserted model version (passenger only).
    effort : Effort or None
        Optional reasoning effort threaded to the driver factory.

    Returns
    -------
    DraftingProvider
        The selected provider, with observability configured.

    Raises
    ------
    ValueError
        If ``host-harness`` is selected without a handoff (``--draft-file``
        or ``--draft-dir``).
    """
    configure_observability()
    if provider_name == _HOST_HARNESS_PROVIDER:
        if draft_text is not None:
            text = draft_text
        elif draft_file is not None:
            text = _read_draft_file(draft_file)
        else:
            raise ValueError(
                "the host-harness provider requires --draft-file or --draft-dir "
                "(the host agent's staged draft)"
            )
        return select_provider(
            _HOST_HARNESS_PROVIDER,
            draft_text=text,
            pages=pages,
            model=model,
            model_version=model_version,
        )
    return select_provider(provider_name, model=model, effort=effort)


def make_mock_provider(
    *, model: str | None = None, effort: Effort | None = None
) -> DraftingProvider:
    """Configure local-mode observability once and return the mock provider.

    Parameters
    ----------
    model : str or None
        Optional model name threaded to the provider factory.
    effort : Effort or None
        Optional reasoning effort threaded to the provider factory.

    Returns
    -------
    DraftingProvider
        The deterministic mock provider proving the seam swap.
    """
    return make_provider(_MOCK_PROVIDER, model=model, effort=effort)


def _strip_docs_prefix(target: str) -> str:
    """Normalize a docs-relative target by dropping one leading ``docs/`` (M1).

    Targets are docs-relative — the store joins ``<root>/docs/<target>`` — so a
    caller who passes ``docs/reference/x.rst`` instead of ``reference/x.rst``
    would otherwise land at ``docs/docs/reference/x.rst`` on disk and seal the
    draft at a slot the toctree never references. Stripping exactly one segment
    mirrors ``find_unit_by_draft``'s query-side normalization, so the write and
    lookup paths agree. A genuine page under a literal ``docs/`` subdirectory is
    the accepted casualty (surfaced by the CLI's normalization notice).
    """
    return PurePosixPath(target).as_posix().removeprefix("docs/")


def build_declare_request(  # noqa: PLR0913
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    intent: Intent | None = None,
    audience: str | None = None,
    title: str | None = None,
    sources: list[str] | None = None,
    steering_notes: str | None = None,
    sphinx_target: str | None = None,
    extra_targets: list[str] | None = None,
    force: bool = False,
    repo: RepoSeam | None = None,
) -> DeclareRequest:
    """Assemble a :class:`DeclareRequest` for the declare use-case (UNIT-01).

    Parameters
    ----------
    unit_id : str
        The identifier and per-unit directory name for the new unit.
    root : Path
        The repo root the store writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    intent : Intent or None
        Optional pre-filled Diátaxis direction.
    audience : str or None
        Optional pre-filled audience.
    title : str or None
        Optional pre-filled human-readable page title.
    sources : list of str or None
        Optional repo-relative source paths; each maps to ``SourceRef(path=…)``
        and is commit-stamped by the use-case when a seam is injected (v1).
    steering_notes : str or None
        Optional free-form steering note seeded into ``unit.md``.
    sphinx_target : str or None
        Optional docs-relative output path (``--target``); defaults to
        ``<unit_id>.<ext>`` (dominant docs format, v1.2).
    extra_targets : list of str or None
        Additional pages in the unit's change set (``--also-target``, v1.2).
    force : bool
        Overwrite an existing ``unit.md`` when ``True``.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    DeclareRequest
        The frozen request for :func:`dogen.core.orchestrator.declare`.
    """
    return DeclareRequest(
        unit_id=unit_id,
        root=root,
        store=store,
        intent=intent,
        audience=audience,
        title=title,
        sources=[SourceRef(path=s) for s in (sources or [])],
        steering_notes=steering_notes,
        sphinx_target=_strip_docs_prefix(sphinx_target) if sphinx_target else None,
        extra_targets=[_strip_docs_prefix(t) for t in (extra_targets or [])],
        force=force,
        repo=repo,
    )


def build_edit_request(  # noqa: PLR0913
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    intent: Intent | None = None,
    audience: str | None = None,
    title: str | None = None,
    add_sources: list[str] | None = None,
    remove_sources: list[str] | None = None,
    steering_notes: str | None = None,
    body: str | None = None,
    sphinx_target: str | None = None,
    add_targets: list[str] | None = None,
    drop_targets: list[str] | None = None,
    re_sign: bool = False,
    identity: Identity = git_identity,
    now: Clock = utc_now,
    repo: RepoSeam | None = None,
) -> EditRequest:
    """Assemble an :class:`EditRequest` for the amend use-case (unit edit, v1).

    Parameters
    ----------
    unit_id : str
        The unit to amend.
    root : Path
        The repo root the store writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    intent : Intent or None
        Replacement Diátaxis direction; ``None`` leaves it unchanged.
    audience : str or None
        Replacement audience; ``None`` leaves it unchanged.
    title : str or None
        Replacement title; ``None`` leaves it unchanged.
    add_sources : list of str or None
        Source paths appended to the declared set.
    remove_sources : list of str or None
        Source paths/refs removed from the declared set.
    steering_notes : str or None
        Replacement seeded steering note; ``None`` leaves it unchanged.
    body : str or None
        Replacement plan body (below the front matter); ``None`` preserves
        the existing body verbatim.
    sphinx_target : str or None
        Replacement docs-relative output path (``--target``); an existing
        draft at the old target moves with the repoint.
    add_targets : list of str or None
        Extra pages appended to the unit's change set (``--also-target``).
    drop_targets : list of str or None
        Extra pages removed from the set (``--drop-target``; de-scope only).
    re_sign : bool
        Fold a re-approval of the amended plan into the same act (v1.2).
    identity : Identity
        The identity port for the folded re-sign.
    now : Clock
        The timestamp source for the folded re-sign.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    EditRequest
        The frozen request for :func:`dogen.core.orchestrator.edit_unit`.
    """
    return EditRequest(
        unit_id=unit_id,
        root=root,
        store=store,
        intent=intent,
        audience=audience,
        title=title,
        add_sources=[SourceRef(path=s) for s in (add_sources or [])],
        remove_sources=list(remove_sources or []),
        steering_notes=steering_notes,
        body=body,
        sphinx_target=_strip_docs_prefix(sphinx_target) if sphinx_target else None,
        add_targets=[_strip_docs_prefix(t) for t in (add_targets or [])],
        drop_targets=[_strip_docs_prefix(t) for t in (drop_targets or [])],
        re_sign=re_sign,
        identity=identity,
        now=now,
        repo=repo,
    )


def build_signoff_request(  # noqa: PLR0913
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    identity: Identity = git_identity,
    now: Clock = utc_now,
    force: bool = False,
    repo: RepoSeam | None = None,
) -> SignoffRequest:
    """Assemble a :class:`SignoffRequest` for the gate act (UNIT-02, v1).

    Parameters
    ----------
    unit_id : str
        The unit to sign off.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    identity : Identity
        The injected identity port; defaults to git config capture.
    now : Clock
        The injected timestamp source; defaults to the real UTC clock.
    force : bool
        Overwrite an already-recorded signoff (re-signoff) when ``True``.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    SignoffRequest
        The frozen request for :func:`dogen.core.orchestrator.signoff`.
    """
    return SignoffRequest(
        unit_id=unit_id,
        root=root,
        store=store,
        identity=identity,
        now=now,
        force=force,
        repo=repo,
    )


def build_note_request(  # noqa: PLR0913
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    note: str,
    origin: SteeringOrigin = SteeringOrigin.manual,
    identity: Identity = git_identity,
    now: Clock = utc_now,
    repo: RepoSeam | None = None,
) -> NoteRequest:
    """Assemble a :class:`NoteRequest` for the steering stream (v1).

    Parameters
    ----------
    unit_id : str
        The unit to steer.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    note : str
        The guidance text to append.
    origin : SteeringOrigin
        Where the entry came from; defaults to ``manual``.
    identity : Identity
        The injected identity port; defaults to git config capture.
    now : Clock
        The injected timestamp source; defaults to the real UTC clock.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    NoteRequest
        The frozen request for
        :func:`dogen.core.orchestrator.add_steering_note`.
    """
    return NoteRequest(
        unit_id=unit_id,
        root=root,
        store=store,
        identity=identity,
        now=now,
        note=note,
        origin=origin,
        repo=repo,
    )


def build_draft_request(  # noqa: PLR0913
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    provider: DraftingProvider | None = None,
    provider_name: str | None = None,
    model: str | None = None,
    model_origin: str = "",
    now: Clock = utc_now,
    report: ContextReport | None = None,
    handoff_path: str = "",
    repo: RepoSeam | None = None,
) -> DraftRequest:
    """Assemble a :class:`DraftRequest` for the draft use-case (DRAFT-01/03).

    Parameters
    ----------
    unit_id : str
        The unit to draft.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    provider : DraftingProvider or None
        An explicit provider; defaults to a freshly built mock provider.
    provider_name : str or None
        The resolved provider name to stamp into provenance; defaults to
        ``"mock"`` (matching the default provider) when omitted.
    model : str or None
        The resolved model name (``--model`` flag > ``DOGEN_MODEL`` env > repo
        config): recorded onto the generation AND threaded to the default
        provider factory. ``None`` / ``""`` leaves the provider default and
        records the provider echo (Open Q1 fallback).
    model_origin : str
        The D-03 vouch-origin for the resolved model
        (``""``/``ta``/``self``/``config``/``flag``), stamped onto the generation
        (MODEL-02). Derived from resolution only, never from the provider echo.
    now : Clock
        The injected timestamp source; defaults to the real UTC clock.
    report : ContextReport or None
        The passenger's validated context report (v1), when one was supplied.
    handoff_path : str
        The repo-relative passenger handoff path recorded on the generation.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    DraftRequest
        The frozen request for :func:`dogen.core.orchestrator.draft`.
    """
    return DraftRequest(
        unit_id=unit_id,
        root=root,
        provider=provider if provider is not None else make_mock_provider(model=model),
        store=store,
        provider_name=provider_name if provider_name is not None else _MOCK_PROVIDER,
        now=now,
        report=report,
        handoff_path=handoff_path,
        repo=repo,
        model=model or "",
        model_origin=model_origin,
    )


def build_review_request(  # noqa: PLR0913
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    note: str,
    verdict: ReviewVerdict = ReviewVerdict.fix,
    identity: Identity = git_identity,
    now: Clock = utc_now,
    repo: RepoSeam | None = None,
) -> ReviewRequest:
    """Assemble a :class:`ReviewRequest` for the review use-case (REVIEW-01/02).

    Parameters
    ----------
    unit_id : str
        The unit to review.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    note : str
        The reviewer's summary of the judgment.
    verdict : ReviewVerdict
        The structured verdict (v1); defaults to ``fix``.
    identity : Identity
        The injected identity port; defaults to git config capture.
    now : Clock
        The injected timestamp source; defaults to the real UTC clock.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    ReviewRequest
        The frozen request for :func:`dogen.core.orchestrator.review`.
    """
    return ReviewRequest(
        unit_id=unit_id,
        root=root,
        store=store,
        identity=identity,
        now=now,
        note=note,
        verdict=verdict,
        repo=repo,
    )


def build_plan_steps_request(  # noqa: PLR0913
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    steps: Sequence[Step],
    now: Clock = utc_now,
    repo: RepoSeam | None = None,
) -> PlanStepsRequest:
    """Assemble a :class:`PlanStepsRequest` for the whole-plan-replace use-case.

    The typed ``steps`` (validated by :func:`_read_steps_file` at the compose
    root) are the only values that cross into :func:`plan_steps`; no ``Path`` or
    ``yaml`` reaches ``core/`` (EVID-05, D-12).

    Parameters
    ----------
    unit_id : str
        The unit whose step plan is written/replaced.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    steps : sequence of Step
        The whole validated step plan.
    now : Clock
        The injected timestamp source; defaults to the real UTC clock.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    PlanStepsRequest
        The frozen request for :func:`dogen.core.orchestrator.plan_steps`.
    """
    return PlanStepsRequest(
        unit_id=unit_id,
        root=root,
        store=store,
        now=now,
        steps=list(steps),
        repo=repo,
    )


def build_record_step_request(  # noqa: PLR0913
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    step_id: str,
    evidence: _EvidenceFileInput,
    now: Clock = utc_now,
    repo: RepoSeam | None = None,
) -> RecordStepRequest:
    """Assemble a :class:`RecordStepRequest` from validated evidence fields.

    The raw evidence fields (validated by :func:`_read_evidence_file`) are handed
    to :func:`record_step`, which binds ``step_text_sha256`` and constructs the
    persisted :class:`~dogen.core.models.StepEvidence` itself (D-02). ``exit_code``
    is carried as ``int | None`` so the micro-gate can see a *missing* code
    (EVID-02).

    Parameters
    ----------
    unit_id : str
        The unit whose step is recorded.
    root : Path
        The repo root the store reads/writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    step_id : str
        The planned step's id.
    evidence : _EvidenceFileInput
        The validated raw evidence fields.
    now : Clock
        The injected timestamp source; defaults to the real UTC clock.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    RecordStepRequest
        The frozen request for :func:`dogen.core.orchestrator.record_step`.
    """
    return RecordStepRequest(
        unit_id=unit_id,
        root=root,
        store=store,
        now=now,
        step_id=step_id,
        verdict=evidence.verdict,
        mode=evidence.mode,
        command=evidence.command,
        output_sha256=evidence.output_sha256,
        output_excerpt=evidence.output_excerpt,
        exit_code=evidence.exit_code,
        reason=evidence.reason,
        deterministic=evidence.deterministic,
        repo=repo,
    )


def build_list_request(*, root: Path, store: PlanningStore) -> ListRequest:
    """Assemble a :class:`ListRequest` for the list/status reads.

    Parameters
    ----------
    root : Path
        The repo root the store reads beneath.
    store : PlanningStore
        The injected planning-directory store.

    Returns
    -------
    ListRequest
        The frozen request for :func:`dogen.core.orchestrator.list_units` and
        :func:`dogen.core.orchestrator.unit_statuses`.
    """
    return ListRequest(root=root, store=store)


def build_remove_request(
    unit_id: str,
    *,
    root: Path,
    store: PlanningStore,
    repo: RepoSeam | None = None,
) -> RemoveRequest:
    """Assemble a :class:`RemoveRequest` for the remove use-case (unit rm).

    Parameters
    ----------
    unit_id : str
        The unit to remove.
    root : Path
        The repo root the store deletes beneath.
    store : PlanningStore
        The injected planning-directory store.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    RemoveRequest
        The frozen request for :func:`dogen.core.orchestrator.remove`.
    """
    return RemoveRequest(unit_id=unit_id, root=root, store=store, repo=repo)


def build_rename_request(
    old_id: str,
    new_id: str,
    *,
    root: Path,
    store: PlanningStore,
    repo: RepoSeam | None = None,
) -> RenameRequest:
    """Assemble a :class:`RenameRequest` for the rename use-case (unit mv).

    Parameters
    ----------
    old_id : str
        The current unit id.
    new_id : str
        The target unit id.
    root : Path
        The repo root the store operates beneath.
    store : PlanningStore
        The injected planning-directory store.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    RenameRequest
        The frozen request for :func:`dogen.core.orchestrator.rename`.
    """
    return RenameRequest(
        old_id=old_id, new_id=new_id, root=root, store=store, repo=repo
    )


def build_context_request(  # noqa: PLR0913
    name: str,
    *,
    text: str,
    root: Path,
    store: PlanningStore,
    repo: RepoSeam | None = None,
) -> ContextAddRequest:
    """Assemble a :class:`ContextAddRequest` for the landing zone (v1).

    Parameters
    ----------
    name : str
        The artifact's landing filename.
    text : str
        The artifact's full content, read at the compose root.
    root : Path
        The repo root the store writes beneath.
    store : PlanningStore
        The injected planning-directory store.
    repo : RepoSeam or None
        The injected commit seam.

    Returns
    -------
    ContextAddRequest
        The frozen request for
        :func:`dogen.core.orchestrator.add_context_artifact`.
    """
    return ContextAddRequest(name=name, text=text, root=root, store=store, repo=repo)
