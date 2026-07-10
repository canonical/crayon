"""The mock end-to-end CI loop via the core API: declare → steer → draft → review.

Rewritten from mvp-1's ``CliRunner`` driver to a core-API async test (D-03):
it drives the promoted core use-cases directly through the ``dogen.app``
composition root — no CLI, no Copilot token, no network. Every mvp-1 invariant
is preserved: the HITL refusal with zero side effects, the steering-precedes-
draft ordering (HITL-02/AC5), the WR-04/WR-05 guards, that progress ends
``reviewed`` and never ``committed``, and that the mock path loads no SDK. It
adds the PLAN-02 on-disk assertion — the written ``provenance.yaml`` records
``provider: mock`` and a non-empty ``mode``.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from dogen.adapters.mock_provider import select_provider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.app import compose
from dogen.core.models import Intent, ProgressState, derive_progress
from dogen.core.orchestrator import (
    NotDraftedError,
    SignoffExistsError,
    SignoffRequiredError,
    declare,
    draft,
    review,
)
from dogen.core.orchestrator import (
    signoff as steer,
)


class _Clock:
    """A deterministic, monotonically increasing ISO-8601 clock (no real time)."""

    def __init__(self):
        self._n = 0

    def __call__(self):
        self._n += 1
        return f"2026-01-01T00:00:{self._n:02d}Z"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tmp git repo with a configured local identity, used as the working dir.

    ``read_git_identity`` reads ``git config --get`` in the cwd, so the local
    user.name/email set here resolve deterministically with no network.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Ada Lovelace"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "ada@example.com"],
        check=True,
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _declare(store, root):
    declare(
        compose.build_declare_request(
            "u", root=root, store=store, intent=Intent.reference, audience="devs"
        )
    )


def _steer(store, root, clock, *, force=False):
    return steer(
        compose.build_signoff_request(
            "u", root=root, store=store, now=clock, force=force
        )
    )


async def _draft(store, root, clock):
    return (
        await draft(compose.build_draft_request("u", root=root, store=store, now=clock))
    ).path


def _review(store, root, clock, note):
    return review(
        compose.build_review_request("u", root=root, store=store, note=note, now=clock)
    )


@pytest.mark.asyncio
async def test_no_progress_yaml_written(repo):
    # PROV-04 (D-01/D-02): a full draft→review loop derives its state from the
    # provenance record and never writes the second stored artefact — the
    # unit dir carries unit.md + provenance.yaml but NO progress.yaml.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    await _draft(store, repo, clock)
    _review(store, repo, clock, "reworded intro")

    unit_dir = repo / ".dogen" / "units" / "u"
    assert (unit_dir / "unit.md").exists()
    assert (unit_dir / "provenance.yaml").exists()
    assert not (unit_dir / "progress.yaml").exists()
    unit = store.load_unit("u", root=repo)
    assert (repo / "docs" / unit.sphinx_target).exists()

    # State is derived from the record: one generation plus a landed reviewer
    # edit ⇒ reviewed. There is no ``committed`` state (publishing is the human's).
    provenance = store.read_provenance("u", root=repo)
    assert derive_progress(provenance) is ProgressState.reviewed


@pytest.mark.asyncio
async def test_review_twice_stays_reviewed(repo):
    # WR-05 / PROV-04: each reviewer edit is recorded on the provenance record,
    # but the derived state stays `reviewed` idempotently — the count-based rule
    # (len(reviewer_edits) > latest generation's reviewer_edit_count) needs no
    # separately-stamped transition history.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    await _draft(store, repo, clock)
    _review(store, repo, clock, "first pass")
    _review(store, repo, clock, "second pass")

    provenance = store.read_provenance("u", root=repo)
    assert len(provenance.reviewer_edits) == 2
    assert derive_progress(provenance) is ProgressState.reviewed


@pytest.mark.asyncio
async def test_draft_refuses_without_steer_with_zero_side_effects(repo):
    # HITL gate: drafting before steering raises with NO side effects — no draft
    # file, no provenance, no progress written.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    with pytest.raises(SignoffRequiredError):
        await _draft(store, repo, clock)
    assert not (repo / "docs" / "u.md").exists()
    with pytest.raises(FileNotFoundError):
        store.read_provenance("u", root=repo)
    assert not (repo / ".dogen" / "units" / "u" / "progress.yaml").exists()


def test_review_before_draft_raises_not_drafted(repo):
    # WR-05 "draft first": a steered-but-never-drafted unit has no recorded
    # generation, so review raises a clear domain error (NotDraftedError now keys
    # on empty provenance.generations) rather than a bare FileNotFoundError.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    with pytest.raises(NotDraftedError):
        _review(store, repo, clock, "premature")


@pytest.mark.asyncio
async def test_steer_records_author_and_precedes_draft(repo):
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    provenance = store.read_provenance("u", root=repo)
    assert provenance.signoff is not None
    assert provenance.signoff.author == "Ada Lovelace"
    assert provenance.signoff.intent is Intent.reference

    await _draft(store, repo, clock)
    after = store.read_provenance("u", root=repo)
    assert after.signoff is not None
    # HITL-02/AC5: steering provably precedes the draft.
    assert after.signoff.at < after.generations[0].at
    generation = after.generations[0]
    assert generation.model == "mock-model"
    assert generation.model_version == "mock-1"


@pytest.mark.asyncio
async def test_review_appends_single_reviewer_edit(repo):
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    await _draft(store, repo, clock)
    _review(store, repo, clock, "reworded intro")
    provenance = store.read_provenance("u", root=repo)
    assert len(provenance.reviewer_edits) == 1
    edit = provenance.reviewer_edits[0]
    assert edit.summary == "reworded intro"
    assert edit.reviewer == "Ada Lovelace"
    assert edit.at


def test_steer_refuses_to_overwrite_without_force(repo):
    # WR-04: re-steering an already-steered unit without force raises and writes
    # nothing, so the recorded steering act is never silently rewritten.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    first = store.read_provenance("u", root=repo).signoff
    assert first is not None
    with pytest.raises(SignoffExistsError):
        _steer(store, repo, clock)
    again = store.read_provenance("u", root=repo).signoff
    assert again is not None
    assert again.at == first.at


def test_re_steer_flag_overwrites_steering(repo):
    # An explicit forced re-steer (no generations yet) is honoured and returns
    # the no-warn signal (False).
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    first = store.read_provenance("u", root=repo).signoff
    assert first is not None
    warn = _steer(store, repo, clock, force=True)
    assert warn is False
    replaced = store.read_provenance("u", root=repo).signoff
    assert replaced is not None
    assert replaced.author == first.author
    assert replaced.at != first.at


@pytest.mark.asyncio
async def test_re_steer_after_draft_returns_warn_signal(repo):
    # WR-04: re-steering a drafted unit with force is honoured but flags a warn
    # signal — existing generations predate the new steering act.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    await _draft(store, repo, clock)
    warn = _steer(store, repo, clock, force=True)
    assert warn is True


def test_select_provider_unknown_name_raises():
    # WR-06 (core equivalent): an unknown provider name raises ValueError — the
    # Phase-3 CLI maps it to a clean nonzero exit.
    with pytest.raises(ValueError, match="unknown provider"):
        select_provider("banana")


@pytest.mark.asyncio
async def test_draft_mock_error_path_does_not_import_copilot_adapter(repo):
    # WR-01/D-25: an error on the mock path (a unit_id/dir mismatch → ValueError)
    # must be handled WITHOUT importing adapters/copilot — the mock path stays
    # SDK-free even on the error branch.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    unit_md = repo / ".dogen" / "units" / "u" / "unit.md"
    unit_md.write_text(
        unit_md.read_text(encoding="utf-8").replace("unit_id: u\n", "unit_id: not-u\n"),
        encoding="utf-8",
    )
    sys.modules.pop("dogen.adapters.copilot", None)
    sys.modules.pop("dogen.adapters.copilot.provider", None)
    with pytest.raises(ValueError):
        await _draft(store, repo, clock)
    assert "dogen.adapters.copilot" not in sys.modules
    assert "dogen.adapters.copilot.provider" not in sys.modules


@pytest.mark.asyncio
async def test_provenance_records_provider_and_mode_on_disk(repo):
    # PLAN-02 proven end-to-end on disk: the written provenance.yaml records the
    # provider name and a non-empty run mode, not merely a span attribute.
    store = FilesystemPlanningStore()
    clock = _Clock()
    _declare(store, repo)
    _steer(store, repo, clock)
    await _draft(store, repo, clock)
    generation = store.read_provenance("u", root=repo).generations[-1]
    assert generation.provider == "mock"
    assert generation.mode
    raw = (repo / ".dogen" / "units" / "u" / "provenance.yaml").read_text(
        encoding="utf-8"
    )
    assert "provider: mock" in raw
    assert "mode:" in raw


def test_e2e_imports_no_sdk():
    # Parse this module's own import statements (not its source text, which would
    # self-match on the banned tokens) and assert no Copilot SDK is imported —
    # the CI loop runs without the SDK / token (D-24).
    tree = ast.parse(Path("tests/test_loop_mock_e2e.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "copilot" not in imported
    assert "github_copilot_sdk" not in imported
