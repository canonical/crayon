"""Seam guardrail as a pytest test, single-sourcing the import-linter gate.

This invokes the exact ``lint-imports`` command CI and pre-commit run (D-29),
so the test and the build gate share one source of truth — the contract in
``pyproject.toml``. It is the declarative counterpart to ``test_seam.py``, which
single-sources the Phase-1 AST check; the two run together (belt-and-braces,
RESEARCH Pitfall 4).
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_lint_imports() -> subprocess.CompletedProcess[str]:
    """Run the project's import-linter gate as a subprocess.

    Returns
    -------
    subprocess.CompletedProcess of str
        The completed ``lint-imports`` console-script invocation (the exact
        command CI and pre-commit run), with captured stdout/stderr, executed
        from the repository root so it reads the contract in ``pyproject.toml``.
    """
    lint_imports = Path(sys.executable).with_name("lint-imports")
    return subprocess.run(
        [str(lint_imports)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_seam_contract_is_kept() -> None:
    """The import-linter forbidden contract passes on the clean tree (D-29).

    A zero exit proves ``dogen.core`` imports none of the banned vendor or
    backend packages (``copilot``, ``github_copilot_sdk``, ``logfire``,
    ``opentelemetry.sdk``) nor ``dogen.adapters`` — the provider seam.
    """
    result = _run_lint_imports()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Contracts: 1 kept" in result.stdout
