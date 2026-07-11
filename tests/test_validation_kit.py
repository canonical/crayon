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
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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


def test_absolute_include_traversal_is_confined(tmp_path):
    """A leading-``/`` include with ``..`` escaping the source root is refused (D-08).

    The resolver confines an absolute-style target under the located Sphinx source
    root: an embedded ``../`` walk out of ``root`` collapses to a path outside it,
    so the target is treated as unresolvable — it FLAGs and its bytes never appear
    in the expanded text (arbitrary-file-read guard). A well-behaved
    ``/shared/inc.rst`` under the same root still resolves.
    """
    (tmp_path / "conf.py").write_text("", encoding="utf-8")
    # A sentinel file OUTSIDE the source root (sibling of tmp_path).
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("TRAVERSAL_SENTINEL\n", encoding="utf-8")
    # A benign shared include INSIDE the source root.
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "inc.rst").write_text("Benign shared marker OKKW.\n", encoding="utf-8")

    subdir = tmp_path / "reference"
    subdir.mkdir()
    draft = subdir / "draft.rst"
    draft.write_text(
        "Title\n=====\n\n"
        ".. include:: /" + "../" * 20 + "outside-secret.txt\n\n"
        ".. include:: /shared/inc.rst\n",
        encoding="utf-8",
    )

    expanded, flags = score.expand_includes(draft.read_text(encoding="utf-8"), draft)
    # The traversal target is FLAGged, never inlined.
    assert flags != []
    assert "TRAVERSAL_SENTINEL" not in expanded
    # The well-behaved absolute include still resolves.
    assert "OKKW" in expanded


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


# --- VAL-02: the audit reads provenance schema v2 only -----------------------
#
# * ``files[]`` is the sole digest authority — audit verifies EVERY page digest
#   of the latest generation and the latest accept seal against on-disk bytes
#   (D-12); the deleted v1 fields (draft_path/draft_sha256) are never read;
# * a ``schema_version: 1`` sidecar prints a clean FLAG and returns without
#   crashing on absent v2 fields (D-12);
# * ``audit`` targets an arbitrary repo via a threaded ``root`` param — the
#   module ROOT global is never reassigned (D-13);
# * ``model-amended`` is a legal, non-required phase token (D-14).
#
# The fixture is a self-contained v2 unit git repo built in pytest ``tmp_path``
# (mirrors tests/test_v1_traceability.py's git init/config pattern), so its
# trailer commits never pollute dogen-mvp-1's own history (Pitfall 4 / T-11-06).


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _build_v2_fixture(
    root: Path,
    unit_id: str = "u",
    *,
    schema_version: int = 2,
    extra_phases: tuple[str, ...] = (),
) -> None:
    """Materialize a v2 unit git repo under ``root`` (a pytest tmp_path).

    Writes ``unit.md``, a page, and a ``schema_version: 2`` provenance.yaml whose
    ``generations[-1].files[]`` and ``reviewer_edits[-1].files[]`` digests match
    the committed page bytes (via score._sha256, the digest authority), a signoff
    whose plan_hash = sha256(unit.md), and a commit-stamped context_origin. Makes
    real ``drafted`` then ``reviewed`` trailer commits (Dogen-Unit/Dogen-Phase),
    inserting any ``extra_phases`` (e.g. ``model-amended``) between them.

    Pass ``schema_version=1`` to exercise the v1-sidecar clean-bail path — the
    provenance is then intentionally missing the v2 fields.
    """
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "config", "user.name", "Ada Lovelace")
    _git(root, "config", "user.email", "ada@example.com")

    unit_dir = root / ".dogen" / "units" / unit_id
    unit_dir.mkdir(parents=True)
    unit_md = unit_dir / "unit.md"
    unit_md.write_text("# unit u\n\nintent & scope\n", encoding="utf-8")

    page = root / "docs" / f"{unit_id}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# A page\n\nbody\n", encoding="utf-8")
    page_rel = f"docs/{unit_id}.md"
    page_sha = score._sha256(page.read_text(encoding="utf-8"))

    if schema_version == 2:
        files = [{"path": page_rel, "sha256": page_sha}]
        prov = {
            "schema_version": 2,
            "signoff": {
                "plan_hash": score._sha256(unit_md.read_text(encoding="utf-8")),
                "commit": "0" * 40,
            },
            "generations": [
                {
                    "run_id": "run-1",
                    "source_commit": "0" * 40,
                    "context_origins": [{"path": "README.md", "commit": "abc1234"}],
                    "files": files,
                }
            ],
            "reviewer_edits": [{"verdict": "accept", "files": files}],
        }
    else:
        # v1 sidecar: no v2 fields present — audit must bail cleanly, not crash.
        prov = {
            "schema_version": schema_version,
            "signoff": {"plan_hash": "deadbeef", "draft_path": page_rel},
        }
    (unit_dir / "provenance.yaml").write_text(
        yaml.safe_dump(prov, sort_keys=False), encoding="utf-8"
    )

    _git(root, "add", "-A")
    _git(
        root,
        "commit",
        "-q",
        "-m",
        f"dogen({unit_id}): drafted — page\n\n"
        f"Dogen-Unit: {unit_id}\nDogen-Phase: drafted",
    )
    for phase in extra_phases:
        _git(
            root,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            f"dogen({unit_id}): {phase}\n\n"
            f"Dogen-Unit: {unit_id}\nDogen-Phase: {phase}",
        )
    _git(
        root,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        f"dogen({unit_id}): reviewed — accept\n\n"
        f"Dogen-Unit: {unit_id}\nDogen-Phase: reviewed",
    )


def test_audit_passes_on_v2_fixture(tmp_path, capsys):
    """audit on a self-contained v2 fixture emits only PASS lines (D-12/D-13).

    Every seal/gen/digest check passes and no FLAG line is printed, proving
    ``files[]`` is read as the sole digest authority, each page digest is verified
    on disk, and ``audit`` targets an arbitrary ``root`` without touching the
    module ROOT global.
    """
    _build_v2_fixture(tmp_path, "u")
    score.audit_unit("u", root=tmp_path)
    out = capsys.readouterr().out
    assert "FLAG" not in out, out
    # The digest, seal and git-reconstruction checks all reported PASS.
    assert "page digest matches on disk: docs/u.md" in out
    assert "accept seals every page digest" in out
    assert "drafted and reviewed transitions" in out


def test_v2_fixture_leaves_host_repo_clean(tmp_path):
    """The fixture builds in tmp_path only — no host-repo artifacts (T-11-06)."""
    _build_v2_fixture(tmp_path, "u")
    host_status = _git(ROOT, "status", "--porcelain")
    assert "validation/fixtures" not in host_status
    assert ".dogen/units/u" not in host_status


def test_v1_sidecar_clean_flag(tmp_path, capsys):
    """A schema_version=1 sidecar prints a clean FLAG and returns, no crash (D-12)."""
    _build_v2_fixture(tmp_path, "u", schema_version=1)
    # Must NOT raise a KeyError/AttributeError on the absent v2 fields.
    score.audit_unit("u", root=tmp_path)
    out = capsys.readouterr().out
    assert (
        "FLAG [schema] v1 sidecar (schema_version=1) — not auditable by this kit"
        in out
    )
    # The audit bailed before touching v2-only checks (no gen/seal lines emitted).
    assert "page digest matches on disk" not in out
    assert "accept seals every page digest" not in out


def test_model_amended_is_legal(tmp_path, capsys):
    """model-amended is a legal, non-required phase token (D-14).

    * with model-amended between drafted and reviewed the drafted+reviewed git
      assertion still PASSes and model-amended is NOT surfaced as unknown;
    * a fixture WITHOUT model-amended also passes (it is not required);
    * a genuinely unknown token DOES surface as a non-failing INFO line — proving
      model-amended's silence is because it is a KNOWN phase, not because the
      machinery is inert.
    """
    _build_v2_fixture(tmp_path / "a", "u", extra_phases=("model-amended",))
    score.audit_unit("u", root=tmp_path / "a")
    out = capsys.readouterr().out
    assert "PASS [git] git log alone shows the drafted and reviewed transitions" in out
    assert "unrecognized phase tokens" not in out  # model-amended is known

    _build_v2_fixture(tmp_path / "b", "u")  # no model-amended
    score.audit_unit("u", root=tmp_path / "b")
    out = capsys.readouterr().out
    assert "PASS [git] git log alone shows the drafted and reviewed transitions" in out
    assert "unrecognized phase tokens" not in out  # not required

    _build_v2_fixture(tmp_path / "c", "u", extra_phases=("mystery-token",))
    score.audit_unit("u", root=tmp_path / "c")
    out = capsys.readouterr().out
    assert "PASS [git] git log alone shows the drafted and reviewed transitions" in out
    unknown_info = "unrecognized phase tokens (not a failure): ['mystery-token']"
    assert unknown_info in out


# --- VAL-03: the `protocol` conformance gate --------------------------------
#
# * `protocol` is the ONE verb whose exit code is load-bearing — it exits
#   NON-ZERO on any naming/RESULTS violation (D-04); draft/audit stay exit 0;
# * it enforces the `SESSION-<name>.md` shape and FLAGs non-conformant siblings
#   like the round-3 offenders `copilot-session-<uuid>.md` / `session-ses_0d1b.md`
#   (D-05);
# * it discovers legs by globbing `SESSION-*.md` and, per leg <name>, requires a
#   markdown heading naming it in RESULTS.md — missing heading = FLAG (D-06).


def test_protocol_catches_round3_names(tmp_path, capsys, monkeypatch):
    """protocol FLAGs the round-3 non-conformant session names and exits non-zero.

    A conformant ``SESSION-claude.md`` sits beside the two round-3 offenders
    (``copilot-session-<uuid>.md`` and lowercase ``session-ses_0d1b.md``); each
    non-conformant sibling is a violation (D-05), so ``protocol_check`` returns
    ``False`` and ``main()`` exits non-zero (D-04).
    """
    (tmp_path / "SESSION-claude.md").write_text("claude transcript\n", encoding="utf-8")
    (tmp_path / "copilot-session-abcd.md").write_text("copilot\n", encoding="utf-8")
    (tmp_path / "session-ses_0d1b.md").write_text("opencode\n", encoding="utf-8")
    (tmp_path / "RESULTS.md").write_text(
        "# results\n\n## claude\n\nok\n", encoding="utf-8"
    )

    assert score.protocol_check(tmp_path) is False
    out = capsys.readouterr().out
    assert "FLAG [name] non-conformant session file: copilot-session-abcd.md" in out
    assert "FLAG [name] non-conformant session file: session-ses_0d1b.md" in out

    # main() dispatches `protocol <dir>` to a NON-ZERO exit on any violation.
    monkeypatch.setattr(sys, "argv", ["score.py", "protocol", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        score.main()
    assert exc.value.code != 0


def test_protocol_session_ish_scan_is_bounded(tmp_path, capsys):
    """The session-ish sibling scan is word-bounded, not a raw substring (WR-01).

    A filename that merely *contains* the letters "session" (``obsession-notes.md``)
    is NOT swept into the naming gate, while the round-3 offender shapes
    (``copilot-session-<uuid>.md`` and leading-lowercase ``session-ses_0d1b.md``)
    still FLAG. A conformant ``SESSION-<name>.md`` remains conformant.
    """
    (tmp_path / "SESSION-claude.md").write_text("claude transcript\n", encoding="utf-8")
    (tmp_path / "obsession-notes.md").write_text("unrelated file\n", encoding="utf-8")
    (tmp_path / "copilot-session-abcd.md").write_text("copilot\n", encoding="utf-8")
    (tmp_path / "session-ses_0d1b.md").write_text("opencode\n", encoding="utf-8")
    (tmp_path / "RESULTS.md").write_text(
        "# r\n\n## claude\n\nok\n", encoding="utf-8"
    )

    assert score.protocol_check(tmp_path) is False
    out = capsys.readouterr().out
    # Incidental substring is not flagged.
    assert "obsession-notes.md" not in out
    # Genuine offenders still flag.
    assert "FLAG [name] non-conformant session file: copilot-session-abcd.md" in out
    assert "FLAG [name] non-conformant session file: session-ses_0d1b.md" in out
    # The conformant SESSION- file is never named as a violation.
    assert "non-conformant session file: SESSION-claude.md" not in out


def test_protocol_requires_results_heading(tmp_path, capsys, monkeypatch):
    """Each discovered leg needs a markdown heading in RESULTS.md (D-06).

    A dir whose RESULTS.md names ``claude`` but not ``copilot`` fails with a FLAG
    naming the missing copilot heading; a dir where RESULTS.md carries BOTH
    headings and only conformant SESSION files passes and ``main()`` exits 0.
    """
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "SESSION-claude.md").write_text("c\n", encoding="utf-8")
    (bad / "SESSION-copilot.md").write_text("p\n", encoding="utf-8")
    (bad / "RESULTS.md").write_text(
        "# r\n\n## claude\n\nonly claude\n", encoding="utf-8"
    )

    assert score.protocol_check(bad) is False
    out = capsys.readouterr().out
    assert "FLAG [results] RESULTS.md has a heading for copilot" in out

    good = tmp_path / "good"
    good.mkdir()
    (good / "SESSION-claude.md").write_text("c\n", encoding="utf-8")
    (good / "SESSION-copilot.md").write_text("p\n", encoding="utf-8")
    (good / "RESULTS.md").write_text(
        "# r\n\n## claude\n\nok\n\n## copilot\n\nok\n", encoding="utf-8"
    )

    assert score.protocol_check(good) is True

    monkeypatch.setattr(sys, "argv", ["score.py", "protocol", str(good)])
    with pytest.raises(SystemExit) as exc:
        score.main()
    assert exc.value.code == 0


# --- VAL-03: export.sh verbatim transcript writer ---------------------------
#
# export.sh writes a raw transcript byte-for-byte to SESSION-<harness>.md under
# the script's OWN directory — raw, never distilled (D-07). It is copied into a
# tmp dir so its self-resolved output dir is the tmp dir, not the real kit dir.


def test_export_writes_verbatim(tmp_path):
    """export.sh writes the canonical SESSION-<h>.md byte-identical to input (D-07)."""
    script = tmp_path / "export.sh"
    script.write_bytes((ROOT / "validation" / "export.sh").read_bytes())
    script.chmod(0o755)

    # A payload with indentation, blank lines, tabs and unicode — any
    # transformation (reflow, strip, re-encode) would change the bytes.
    payload = (
        "line one\n  indented two\n\nfinal line\n"
        "tab\tinside\nunicode: café ✓\n"
    )
    src = tmp_path / "raw.txt"
    src.write_text(payload, encoding="utf-8")

    # From a file argument.
    subprocess.run(["sh", str(script), "demo", str(src)], check=True)
    from_file = tmp_path / "SESSION-demo.md"
    assert from_file.read_bytes() == src.read_bytes()

    # From stdin (default source `-`).
    subprocess.run(
        ["sh", str(script), "stdin", "-"], check=True, input=src.read_bytes()
    )
    from_stdin = tmp_path / "SESSION-stdin.md"
    assert from_stdin.read_bytes() == src.read_bytes()


# --- VAL-04: sync.sh idempotent one-directional kit mirror ------------------
#
# sync.sh copies EXACTLY score.py/rubric.md/export.sh from validation/ into the
# mirror, overwrite + one-directional + idempotent (D-02). DOGEN_SYNC_DST is a
# test seam pointing the copy at a tmp dir instead of the real sibling repo, so
# the test lands ZERO writes in ../DOCPR-2845 (D-01). It errors loudly if the
# mirror dir is absent (Pitfall 6 / T-11-09).

SYNC_KIT_FILES = ("score.py", "rubric.md", "export.sh")


def test_sync_is_idempotent(tmp_path):
    """sync.sh mirrors the three kit files byte-identically, re-runnable (D-02)."""
    sync = ROOT / "validation" / "sync.sh"
    dst = tmp_path / "mirror"
    dst.mkdir()
    env = {**os.environ, "DOGEN_SYNC_DST": str(dst)}

    # First run: the mirror gains all three kit files, byte-identical to source.
    subprocess.run(["sh", str(sync)], check=True, env=env)
    for f in SYNC_KIT_FILES:
        assert (dst / f).read_bytes() == (ROOT / "validation" / f).read_bytes()

    # Second run: overwrite leaves them byte-identical (idempotent).
    subprocess.run(["sh", str(sync)], check=True, env=env)
    for f in SYNC_KIT_FILES:
        assert (dst / f).read_bytes() == (ROOT / "validation" / f).read_bytes()


def test_sync_errors_loudly_on_missing_mirror(tmp_path):
    """A nonexistent mirror dir exits non-zero with a loud message (Pitfall 6)."""
    sync = ROOT / "validation" / "sync.sh"
    missing = tmp_path / "does-not-exist"
    env = {**os.environ, "DOGEN_SYNC_DST": str(missing)}

    completed = subprocess.run(
        ["sh", str(sync)], capture_output=True, text=True, env=env, check=False
    )
    assert completed.returncode != 0
    assert "mirror not found" in completed.stderr
