"""The publishability proof, as a test (D-07 / DRAFT-01 AC3).

Single-source companion to the CI ``sphinx-build -W`` gate. It asserts the MyST
config is wired (``myst_parser`` + ``colon_fence``, Pitfall 6) and — when Sphinx
is installed (CI runs it under ``--extra docs``) — that a real warnings-as-errors
build of *the mock's drafted MyST* succeeds offline (no token, no network). The
drafted page is produced by the deterministic mock at build time and named in the
docs toctree, so ``-W`` genuinely compiles the loop's output (Pitfall 3) rather
than a vacuous empty tree. This is purely a build-of-a-draft test — it performs
no commit/stage/push/publish action (REVIEW-02 boundary intact).
"""

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from dogen.adapters.mock_provider import select_provider
from dogen.adapters.planning_fs import FilesystemPlanningStore
from dogen.core.models import Intent
from dogen.core.orchestrator import (
    DeclareRequest,
    DraftRequest,
    SignoffRequest,
    declare,
    draft,
)
from dogen.core.orchestrator import (
    signoff as steer,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _REPO_ROOT / "docs"

# The canonical reference unit the committed docs/index.md toctree names; the
# mock drafts it to docs/dogen-reference.md at build time (scaffold sets
# sphinx_target = "<unit_id>.md").
_UNIT_ID = "dogen-reference"


def _stamp() -> str:
    return "2026-01-01T00:00:00Z"


def _identity() -> tuple[str, str]:
    # A stub Identity port so the docs build needs no git repo (offline).
    return ("Ada Lovelace", "ada@example.com")


def test_conf_enables_myst_and_colon_fence() -> None:
    conf = (_DOCS / "conf.py").read_text(encoding="utf-8")
    # Without myst_parser in extensions, .md pages are not parsed as MyST and a
    # -W build "passes" without ever exercising the publishability path.
    assert '"myst_parser"' in conf
    assert "myst_enable_extensions" in conf
    assert '"colon_fence"' in conf


def test_index_toctrees_the_drafted_unit() -> None:
    # Pitfall 3: the drafted unit's target must be named in the toctree, or -W
    # fails with "document isn't included in any toctree".
    index = (_DOCS / "index.md").read_text(encoding="utf-8")
    assert "toctree" in index
    assert _UNIT_ID in index


@pytest.mark.skipif(
    shutil.which("sphinx-build") is None,
    reason="sphinx-build not installed (docs extra); CI runs it with --extra docs",
)
def test_sphinx_build_compiles_mock_draft_warnings_as_errors(tmp_path: Path) -> None:
    # Assemble a docs tree = the committed conf.py + index.md + the mock's
    # drafted page, then run a real -W build over it. The mock provider is the
    # only backend — no Copilot token, no network.
    root = tmp_path
    docs_dir = root / "docs"
    docs_dir.mkdir()
    shutil.copy(_DOCS / "conf.py", docs_dir / "conf.py")
    shutil.copy(_DOCS / "index.md", docs_dir / "index.md")

    store = FilesystemPlanningStore()
    declare(
        DeclareRequest(
            unit_id=_UNIT_ID,
            root=root,
            store=store,
            intent=Intent.reference,
            audience="devs",
        )
    )
    steer(
        SignoffRequest(
            unit_id=_UNIT_ID, root=root, store=store, identity=_identity, now=_stamp
        )
    )
    asyncio.run(
        draft(
            DraftRequest(
                unit_id=_UNIT_ID,
                root=root,
                provider=select_provider("mock"),
                store=store,
                provider_name="mock",
                now=_stamp,
            )
        )
    )

    drafted = docs_dir / f"{_UNIT_ID}.md"
    # The mock's MyST must exist and be the page the toctree references, so -W
    # compiles the loop's real output rather than an empty tree (Pitfall 3).
    assert drafted.exists()

    out = tmp_path / "_out"
    result = subprocess.run(  # noqa: S603
        ["sphinx-build", "-W", "-b", "html", str(docs_dir), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
