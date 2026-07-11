"""Validation-kit behaviours (dev-time eval tooling in ``validation/score.py``).

Phase 11 / VAL-01: include resolution in the draft scorer.

``score.py`` is a standalone stdlib script (not an importable package member), so
it is loaded by path here — mirroring nothing in the app import graph on purpose.

* ``.. include:: sub/file.rst`` resolves relative to the draft's own directory and
  its content is scanned (D-08);
* a leading-``/`` include resolves from the located Sphinx source root, never ``/``
  (D-08);
* an unresolvable include emits a ``FLAG [cov] unresolved include:`` line and
  ``draft`` still exits 0 (D-09);
* includes expand exactly one level — a directive inside an included file is NOT
  further expanded (D-11).
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORE_PATH = ROOT / "validation" / "score.py"


def _load_score():
    spec = importlib.util.spec_from_file_location("validation_score", SCORE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


score = _load_score()


def test_include_resolves(tmp_path, capsys):
    """A dir-relative include resolves and its text is scanned (D-08)."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "inc.rst").write_text(
        "This documents the ssh-agent interface.\n", encoding="utf-8"
    )
    draft = tmp_path / "draft.rst"
    draft.write_text("Title\n=====\n\n.. include:: sub/inc.rst\n", encoding="utf-8")

    expanded, flags = score.expand_includes(draft.read_text(encoding="utf-8"), draft)
    assert flags == []
    assert "ssh-agent" in expanded

    # And the coverage scan sees it: "interface: ssh-agent" is no longer missing.
    score.score_draft(draft)
    out = capsys.readouterr().out
    assert "interface: ssh-agent" not in out


def test_unresolved_include_flags_but_exits_zero(tmp_path, capsys, monkeypatch):
    """An unresolvable include FLAGs but ``draft`` stays report-only (D-09)."""
    draft = tmp_path / "draft.rst"
    draft.write_text("Title\n=====\n\n.. include:: missing.rst\n", encoding="utf-8")

    score.score_draft(draft)  # must not raise
    out = capsys.readouterr().out
    assert "FLAG [cov] unresolved include: missing.rst" in out

    # main() for the draft verb must not exit non-zero.
    monkeypatch.setattr(sys, "argv", ["score.py", "draft", str(draft)])
    score.main()  # returns normally (no SystemExit)


def test_absolute_include_from_source_root(tmp_path):
    """A leading-``/`` include resolves from the nearest conf.py, never ``/`` (D-08)."""
    (tmp_path / "conf.py").write_text("", encoding="utf-8")
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "inc.rst").write_text(
        "Absolute include marker UNIQUEKW.\n", encoding="utf-8"
    )
    subdir = tmp_path / "reference"
    subdir.mkdir()
    draft = subdir / "draft.rst"
    draft.write_text("Title\n=====\n\n.. include:: /shared/inc.rst\n", encoding="utf-8")

    expanded, flags = score.expand_includes(draft.read_text(encoding="utf-8"), draft)
    assert flags == []
    assert "UNIQUEKW" in expanded


def test_include_one_level_only(tmp_path):
    """A directive inside an included file is NOT further expanded (D-11)."""
    (tmp_path / "outer.rst").write_text(
        "Outer content.\n\n.. include:: inner.rst\n", encoding="utf-8"
    )
    (tmp_path / "inner.rst").write_text(
        "INNERKEYWORD should not appear.\n", encoding="utf-8"
    )
    draft = tmp_path / "draft.rst"
    draft.write_text("Title\n=====\n\n.. include:: outer.rst\n", encoding="utf-8")

    expanded, flags = score.expand_includes(draft.read_text(encoding="utf-8"), draft)
    assert flags == []
    assert "Outer content." in expanded
    assert "INNERKEYWORD" not in expanded


def test_round3_claude_rescores_include_aware(capsys):
    """The frozen round-3 claude draft re-scores with all 7 includes resolved.

    The shared ``_interfaces/*.rst`` snippets are staged beside the frozen draft
    (Task 2), so its 7 dir-relative includes now resolve — turning the old
    keyword-on-directive-line artifact into a genuine include-aware score
    (Pitfall 1). Copilot (0 includes) and opencode (doubled docs/docs path)
    deliberately stay real misses and are not staged.
    """
    draft = (
        ROOT
        / "validation/round-3/claude/docs/reference/definition-files"
        / "workshop-definition.rst"
    )
    score.score_draft(draft)
    out = capsys.readouterr().out
    assert "unresolved include" not in out
