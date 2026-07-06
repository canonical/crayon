"""Static AST guardrail: no Copilot SDK imports outside adapters/copilot/.

This is the pure-stdlib enforcement of the provider seam (SEAM-02). It walks
every module under ``src/dogen`` except the sanctioned ``adapters/copilot``
subtree and fails the build if any ``copilot`` or ``github_copilot_sdk`` import
appears. It is AST-based, not regex-based (D-09), so it resists aliasing,
submodule imports, and ``importlib.import_module`` by string constant.

The same :func:`main` is invoked by the pytest test, the pre-commit hook, and
the CI step, so there is a single source of truth with no drift.
"""

import ast
import sys
from pathlib import Path

BANNED_ROOTS = {"copilot", "github_copilot_sdk"}
PKG_ROOT = Path(__file__).resolve().parents[1] / "src" / "dogen"
ADAPTER_DIR = PKG_ROOT / "adapters" / "copilot"


def _is_banned(module: str) -> bool:
    """Return whether a module's top-level package is banned.

    Parameters
    ----------
    module : str
        The dotted module name from an import statement.

    Returns
    -------
    bool
        ``True`` if the top-level package is in :data:`BANNED_ROOTS`.
    """
    return module.split(".", 1)[0] in BANNED_ROOTS


def _check_call(node: ast.Call) -> list[tuple[int, str]]:
    """Flag an ``importlib.import_module`` call with a banned string constant.

    Parameters
    ----------
    node : ast.Call
        A call node encountered while walking the tree.

    Returns
    -------
    list of (int, str)
        A single-element list if the call is a banned dynamic import, else
        an empty list.
    """
    name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
    if name != "import_module" or not node.args:
        return []
    arg = node.args[0]
    is_banned_constant = (
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and _is_banned(arg.value)
    )
    if not is_banned_constant:
        return []
    return [(node.lineno, f"import_module({arg.value!r})")]


def find_violations(path: Path) -> list[tuple[int, str]]:
    """Return every banned-import occurrence in a single source file.

    Parameters
    ----------
    path : Path
        The Python source file to scan.

    Returns
    -------
    list of (int, str)
        ``(lineno, description)`` for each banned import or dynamic import.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [
                (node.lineno, f"import {alias.name}")
                for alias in node.names
                if _is_banned(alias.name)
            ]
        elif (
            isinstance(node, ast.ImportFrom) and node.module and _is_banned(node.module)
        ):
            hits.append((node.lineno, f"from {node.module} import ..."))
        elif isinstance(node, ast.Call):
            hits += _check_call(node)
    return hits


def main() -> int:
    """Scan src/dogen (excluding the adapter) and report any seam violation.

    Returns
    -------
    int
        ``0`` when clean, ``1`` on any violation, ``2`` when the scan root is
        misconfigured and zero files were found (guards the vacuous pass).
    """
    scanned = 0
    bad: list[str] = []
    for py in PKG_ROOT.rglob("*.py"):
        if ADAPTER_DIR in py.parents:
            continue
        scanned += 1
        bad += [f"{py}:{ln}: {what}" for ln, what in find_violations(py)]
    if scanned == 0:
        print(
            "seam-check: ERROR - scanned 0 files (path misconfigured)",
            file=sys.stderr,
        )
        return 2
    if bad:
        print("seam-check: VIOLATION(S):", *bad, sep="\n  ", file=sys.stderr)
        return 1
    print(
        f"seam-check: OK - {scanned} files, no vendor imports outside adapters/copilot/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
