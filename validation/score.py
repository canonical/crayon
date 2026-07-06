#!/usr/bin/env python3
"""Mechanical validation scorer for dogen drafts (dev-time eval tooling).

Two subcommands:

  score.py draft <path>      — register leaks, implementation identifiers,
                               coverage checklist, structure checks (format-
                               aware, v1.2: .md scored as MyST, .rst as rST)
  score.py audit <unit-id>   — traceability spine: signoff hash freshness,
                               commit-stamped context origins, sealed accept,
                               git-log phase reconstruction

Report-only: always exits 0; read the PASS/FLAG lines. Stdlib only.
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml  # available via the dogen venv the runbook puts on PATH

ROOT = Path(__file__).resolve().parents[1]

# The stance contract's banned researcher register (mirror of
# dogen.core.authoring.STANCE_CONTRACT — dev-time copy, fine to drift-check by eye).
BANNED_REGISTER = [
    "observed",
    "the fixtures show",
    "every observed use",
    "the corpus",
    "at this level",
]

# Implementation identifiers that must not appear in user-facing prose.
IMPL_IDENTIFIERS = [
    "internal/workshop",
    "workshop_file.go",
    "ValidateFile",
    "SdkRecord",
    "PlugOrBind",
    "PlugRef",
    "SlotRef",
    "ProjectSdkPath",
    "Filenames",
    "Filepath",
]
IMPL_PATH_RE = re.compile(r"\binternal/[a-z]")

# Coverage checklist: (label, any-of keyword alternatives, case-insensitive).
COVERAGE = [
    ("file locations", [".workshop/", ".workshop.yaml"]),
    ("name pattern", ["lowercase letter"]),
    ("name length limit", ["40"]),
    ("base field", ["ubuntu@"]),
    ("sdks field", ["sdks"]),
    ("channel", ["channel"]),
    ("plugs", ["plugs"]),
    ("slots", ["slots"]),
    ("bind rule", ["bind"]),
    ("bind target syntax", [":<name>", ":`<name>`", "sdk>:<", "sdk`:`"]),
    ("try- prefix", ["try-"]),
    ("project- prefix", ["project-"]),
    ("system sdk", ["system"]),
    ("implicit sdks", ["implicit"]),
    ("connections", ["connections"]),
    ("actions", ["actions"]),
    ("interface: mount", ["mount"]),
    ("mount attrs", ["workshop-target", "workshop-source", "host-target"]),
    ("read-only attr", ["read-only"]),
    ("interface: tunnel", ["tunnel"]),
    ("tunnel endpoint attr", ["endpoint"]),
    ("interface: camera", ["camera"]),
    ("interface: gpu", ["gpu"]),
    ("interface: desktop", ["desktop"]),
    ("interface: ssh-agent", ["ssh-agent"]),
    ("interface: custom-device", ["custom-device"]),
    ("custom-device subsystem", ["subsystem"]),
    ("validation summary", ["validation"]),
    ("worked example", ["```yaml", "code-block:: yaml", "literalinclude"]),
]


def _flag(ok: bool, tag: str, message: str) -> bool:
    print(f"{'PASS' if ok else 'FLAG'} [{tag}] {message}")
    return ok


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False
    )
    return done.stdout.strip()


def score_draft(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lower = text.lower()
    print(f"== draft scorecard: {path}")

    hits = [p for p in BANNED_REGISTER if p in lower]
    _flag(not hits, "reg", f"researcher register: {hits or 'clean'}")

    impl = [i for i in IMPL_IDENTIFIERS if i in text]
    if IMPL_PATH_RE.search(text):
        impl.append("internal/<pkg> path")
    _flag(not impl, "impl", f"implementation identifiers: {impl or 'clean'}")

    missing = [
        label
        for label, alts in COVERAGE
        if not any(a.lower() in lower for a in alts)
    ]
    covered = len(COVERAGE) - len(missing)
    pct = 100 * covered // len(COVERAGE)
    _flag(pct >= 90, "cov", f"coverage {covered}/{len(COVERAGE)} ({pct}%)"
          + (f"; missing: {', '.join(missing)}" if missing else ""))

    if path.suffix == ".rst":
        _score_rst_structure(text)
    else:
        _score_myst_structure(text)


def _score_myst_structure(text: str) -> None:
    h1 = len(re.findall(r"^# ", text, flags=re.M))
    _flag(h1 == 1, "struct", f"exactly one H1 (found {h1})")
    levels = [len(m.group(1)) for m in re.finditer(r"^(#{1,6}) ", text, flags=re.M)]
    skips = any(b - a > 1 for a, b in zip(levels, levels[1:]))
    _flag(not skips, "struct", "heading ladder has no skipped levels")
    tables = len(re.findall(r"^\|[-: |]+\|$", text, flags=re.M))
    ltables = text.count("{list-table}")
    _flag(tables >= 2 or ltables >= 2,
          "struct", f"field tables present ({tables} pipe / {ltables} list-table)")
    bare_rst = len(re.findall(r"^\.\. [a-z-]+::", text, flags=re.M))
    fenced = text.count("{eval-rst}")
    _flag(bare_rst == 0 or fenced > 0, "struct",
          f"no bare rST directives outside eval-rst ({bare_rst} found, "
          f"{fenced} eval-rst fences)")


def _score_rst_structure(text: str) -> None:
    lines = text.splitlines()
    # Underlined titles: a text line followed by a punctuation underline at
    # least as long. The FIRST one is the page title; count its underline char
    # reuse to approximate the ladder.
    heads: list[tuple[str, str]] = []
    for a, b in zip(lines, lines[1:]):
        if (a.strip() and b and len(set(b.strip())) == 1
                and b.strip()[0] in "=-~^\"'#*+." and len(b.strip()) >= len(a.strip())
                and not a.startswith((" ", ".."))):
            heads.append((a, b.strip()[0]))
    _flag(bool(heads), "struct", f"underlined headings found ({len(heads)})")
    title_char = heads[0][1] if heads else ""
    h1 = sum(1 for _, c in heads if c == title_char)
    _flag(h1 == 1, "struct", f"exactly one page title (found {h1} '{title_char}')")
    short = [
        a for a, b in zip(lines, lines[1:])
        if (a.strip() and b.strip() and len(set(b.strip())) == 1
            and b.strip()[0] in "=-~^" and len(b.strip()) < len(a.strip())
            and not a.startswith((" ", "..")))
    ]
    _flag(not short, "struct",
          f"no short heading underlines ({len(short)} found)")
    ltables = len(re.findall(r"^\.\. list-table::", text, flags=re.M))
    _flag(ltables >= 2, "struct", f"list-tables present ({ltables} found)")
    fences = len(re.findall(r"^(```|:::)", text, flags=re.M))
    _flag(fences == 0, "struct",
          f"no MyST fences in an rst page ({fences} found)")


def audit_unit(unit_id: str) -> None:
    unit_dir = ROOT / ".dogen" / "units" / unit_id
    print(f"== traceability audit: {unit_id}")
    unit_text = (unit_dir / "unit.md").read_text(encoding="utf-8")
    prov = yaml.safe_load((unit_dir / "provenance.yaml").read_text(encoding="utf-8"))

    signoff = prov.get("signoff")
    if _flag(bool(signoff), "sign", "signoff act recorded"):
        plan_hash = signoff.get("plan_hash", "")
        if plan_hash:
            _flag(plan_hash == _sha256(unit_text), "sign",
                  "plan hash matches current unit.md (not stale)")
        else:
            _flag(False, "sign", "plan hash empty (v0-migrated act — re-sign to fix)")
        _flag(bool(signoff.get("commit")), "sign", "signoff carries a commit stamp")
    history = prov.get("signoff_history", [])
    if history:
        print(f"INFO [sign] re-signed {len(history)} time(s); superseded plan "
              f"hash(es) archived in the tip artifact (v1.2)")

    gens = prov.get("generations", [])
    if _flag(bool(gens), "gen", f"{len(gens)} generation(s) recorded"):
        last = gens[-1]
        origins = last.get("context_origins", [])
        _flag(bool(origins), "gen",
              f"context_origins non-empty ({len(origins)} reads)")
        unstamped = [o for o in origins if not (isinstance(o, dict) and o.get("commit"))]
        _flag(not unstamped, "gen",
              f"all reads commit-stamped ({len(unstamped)} unstamped)")
        _flag(bool(last.get("source_commit")), "gen", "generation has source_commit")
        draft_rel = last.get("draft_path", "")
        if draft_rel and (ROOT / draft_rel).is_file():
            actual = _sha256((ROOT / draft_rel).read_text(encoding="utf-8"))
            _flag(actual == last.get("draft_sha256"), "gen",
                  "draft_sha256 matches the recorded draft file")

    accepts = [e for e in prov.get("reviewer_edits", []) if e.get("verdict") == "accept"]
    if accepts:
        last_accept = accepts[-1]
        sealed = last_accept.get("draft_sha256", "")
        ok = bool(gens) and sealed == gens[-1].get("draft_sha256")
        _flag(ok, "seal", "latest accept seals the latest generation's draft hash")
        files = last_accept.get("files") or []
        if files:
            gen_files = (gens[-1].get("files") or []) if gens else []
            pairs = [(f.get("path"), f.get("sha256")) for f in files]
            gen_pairs = [(f.get("path"), f.get("sha256")) for f in gen_files]
            _flag(pairs == gen_pairs, "seal",
                  f"accept seals every page digest ({len(files)} page(s), v1.2)")
    else:
        _flag(False, "seal", "no accept verdict recorded yet")

    log = _git("log", "--reverse", f"--grep=Dogen-Unit: {unit_id}",
               "--format=%(trailers:key=Dogen-Phase,valueonly)")
    phases = [line for line in log.splitlines() if line]
    print(f"INFO [git] phase sequence: {' -> '.join(phases) or '(none)'}")
    _flag("drafted" in phases and "reviewed" in phases, "git",
          "git log alone shows the drafted and reviewed transitions")


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("draft", "audit"):
        print(__doc__)
        return
    if sys.argv[1] == "draft":
        score_draft(Path(sys.argv[2]))
    else:
        audit_unit(sys.argv[2])


if __name__ == "__main__":
    main()
