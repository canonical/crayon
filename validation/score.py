#!/usr/bin/env python3
"""Mechanical validation scorer for dogen drafts (dev-time eval tooling).

Subcommands:

  score.py draft <path>              — register leaks, implementation identifiers,
                                       coverage checklist, structure checks (format-
                                       aware, v1.2: .md scored as MyST, .rst as rST;
                                       .. include:: resolved one level first)
  score.py audit <unit-id> [--root <repo>]
                                     — traceability spine: signoff hash freshness,
                                       commit-stamped context origins, sealed accept,
                                       git-log phase reconstruction (v2 provenance;
                                       --root retargets an arbitrary repo)
  score.py protocol [dir]            — conformance GATE: SESSION-<name>.md naming
                                       (D-05) + a per-leg RESULTS.md heading (D-06)

draft and audit are report-only — they always exit 0; read the PASS/FLAG lines.
protocol is the ONE verb whose exit code is load-bearing: it exits NON-ZERO on any
naming/RESULTS violation (D-04). Stdlib only (audit lazy-imports PyYAML).
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

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

# Legal lifecycle phase tokens the git-log reconstruction may see (D-14). The
# audit requires only `drafted` and `reviewed`; `model-amended` and the rest are
# legal-but-not-required, and any token OUTSIDE this set surfaces as a non-failing
# INFO line (never a FLAG).
KNOWN_PHASES = {"declared", "signed-off", "steered", "drafted", "reviewed",
                "model-amended", "step-planned", "step-recorded"}

# rST include directive (VAL-01). Matched on the ORIGINAL draft text exactly once
# so inserted content is never re-scanned — one level, recursion-guarded (D-11).
INCLUDE_RE = re.compile(r"^\s*\.\. include:: (.+?)\s*$", flags=re.M)

# The canonical session-log shape the `protocol` gate enforces (D-05):
# `SESSION-<name>.md`. Case-sensitive prefix — round-3's lowercase `session-…`
# and prefix-less `*-session-*` offenders deliberately do NOT match.
SESSION_RE = re.compile(r"^SESSION-(.+)\.md$")

# A "session-ish" sibling worth naming-checking: a `session` token bounded by
# non-letters, so the round-3 offender shapes (`*-session-*`, leading `session-`,
# and `SESSION-…` itself) are caught, but an incidental substring like
# `obsession-notes.md`/`possession.md` is NOT (WR-01).
SESSION_ISH_RE = re.compile(r"(^|[^a-z])session([^a-z]|$)", re.I)

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


def _find_source_root(start: Path) -> Path | None:
    """Nearest ancestor (inclusive) holding a conf.py — the Sphinx source root (D-08)."""
    for parent in [start, *start.parents]:
        if (parent / "conf.py").is_file():
            return parent
    return None


def expand_includes(text: str, draft_path: Path) -> tuple[str, list[str]]:
    """One-level, recursion-guarded rST include expansion (D-08/D-11).

    Dir-relative targets resolve under the draft's own directory; a leading-``/``
    target resolves under the located Sphinx source root (nearest conf.py) and is
    treated as unresolvable when no source root is found — never read from the
    filesystem root (D-08 security control). Substitution runs over the ORIGINAL
    text exactly once via a single ``INCLUDE_RE.sub`` call, so a directive sitting
    inside an included file is left verbatim and NOT further expanded (D-11).
    Unresolvable targets are collected in ``flags`` and their directive line is
    left in place; the caller emits the FLAG line (D-09).
    """
    flags: list[str] = []
    root = _find_source_root(draft_path.parent)

    def _resolve(rel: str) -> Path | None:
        if rel.startswith("/"):
            if root is None:
                return None
            # Confine the absolute-style target under the located source root:
            # `.resolve()` collapses any embedded `..` and a target that escapes
            # `root` is treated as unresolvable (-> FLAG), never read (D-08).
            candidate = (root / rel.lstrip("/")).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                return None  # escapes the source root — treat as unresolvable
            return candidate
        return draft_path.parent / rel

    def _sub(match: "re.Match[str]") -> str:
        rel = match.group(1).strip()
        target = _resolve(rel)
        if target is not None and target.is_file():
            return target.read_text(encoding="utf-8")  # inserted, never re-scanned
        flags.append(rel)
        return match.group(0)  # leave directive; FLAG emitted by caller

    expanded = INCLUDE_RE.sub(_sub, text)  # ORIGINAL text, one pass = one level
    return expanded, flags


def score_draft(path: Path) -> None:
    # Report-only contract: draft always exits 0. A missing/unreadable path FLAGs
    # and returns cleanly instead of crashing with a traceback (WR-03).
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        _flag(False, "io", f"cannot read draft {path}: {exc}")
        return
    # Resolve rST includes once, before any scan, so all four scans run on the
    # expanded page (D-10). Gate to rST-bearing content — MyST-native {include}/
    # literalinclude stay out of scope this cycle (D-11).
    if path.suffix == ".rst" or "{eval-rst}" in text:
        text, unresolved = expand_includes(text, path)
        for missing_include in unresolved:
            _flag(False, "cov", f"unresolved include: {missing_include}")
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
        # Strict D-10: structure scans the expanded page too. Title-less include
        # fragments (a lone subheading, no page title) are a known tolerated edge;
        # if a spurious [struct] FLAG surfaces on a real re-score, narrow this call
        # to the pre-expansion text and record the deviation here.
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


def audit_unit(unit_id: str, root: Path = ROOT) -> None:
    # Lazy-import yaml so `draft`/`protocol` run without PyYAML on PATH — it is a
    # transitive-only dependency, not a declared one (RESEARCH Pitfall 5, T-11-04).
    import yaml

    # Route the git trailer grep through the resolved `root` (D-13) — never
    # reassign the module ROOT global (RESEARCH Pitfall 3). Preserve the list-argv
    # form (never a shell string) so a retargeted root can't inject args (T-11-05).
    def _git_at(*args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, check=False,
        )
        return done.stdout.strip()

    unit_dir = root / ".dogen" / "units" / unit_id
    print(f"== traceability audit: {unit_id}")
    # Report-only contract: audit always exits 0. A missing unit dir / sidecar
    # FLAGs and returns cleanly instead of crashing with a traceback (WR-03).
    # safe_load only (never yaml.load) — the sidecar is untrusted on-disk YAML.
    try:
        unit_text = (unit_dir / "unit.md").read_text(encoding="utf-8")
        prov = yaml.safe_load((unit_dir / "provenance.yaml").read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError) as exc:
        _flag(False, "io", f"cannot read unit {unit_id}: {exc}")
        return

    # v2-only guard (D-12): a v1 sidecar bails cleanly with a FLAG rather than
    # crashing on the deleted v2 fields (files[]/signoff.commit/source_commit).
    if prov.get("schema_version") != 2:
        _flag(False, "schema",
              f"v1 sidecar (schema_version={prov.get('schema_version')}) — "
              "not auditable by this kit")
        return

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
        # v2: files[] is the sole digest authority (PROV-01). Verify EVERY page
        # of the latest generation hashes to its recorded digest on disk (D-12).
        for f in (last.get("files") or []):
            # A null/missing path (`path: null`, hand-edited/upstream malformation)
            # is a digest-mismatch FLAG, not a `root / None` TypeError crash (WR-05).
            rel = f.get("path") or ""
            page = root / rel
            ok = (bool(rel) and page.is_file()
                  and _sha256(page.read_text(encoding="utf-8")) == f.get("sha256"))
            _flag(ok, "gen", f"page digest matches on disk: {f.get('path')}")

    accepts = [e for e in prov.get("reviewer_edits", []) if e.get("verdict") == "accept"]
    if accepts:
        last_accept = accepts[-1]
        # The latest accept seal is the files[] pair list of the latest generation
        # (v2 — no draft_sha256 fallback). Verify the accept seals every page.
        acc_files = last_accept.get("files") or []
        gen_files = (gens[-1].get("files") or []) if gens else []
        acc_pairs = [(f.get("path"), f.get("sha256")) for f in acc_files]
        gen_pairs = [(f.get("path"), f.get("sha256")) for f in gen_files]
        # Order-insensitive (WR-06): the same page set emitted in a different order
        # by the upstream provenance writer must not FLAG a sealed generation.
        _flag(bool(acc_pairs) and sorted(acc_pairs) == sorted(gen_pairs), "seal",
              f"accept seals every page digest ({len(acc_files)} page(s), v2)")
    else:
        _flag(False, "seal", "no accept verdict recorded yet")

    log = _git_at("log", "--reverse", f"--grep=Dogen-Unit: {unit_id}",
                  "--format=%(trailers:key=Dogen-Phase,valueonly)")
    phases = [line for line in log.splitlines() if line]
    print(f"INFO [git] phase sequence: {' -> '.join(phases) or '(none)'}")
    _flag("drafted" in phases and "reviewed" in phases, "git",
          "git log alone shows the drafted and reviewed transitions")
    # model-amended (and the rest of KNOWN_PHASES) is legal and never required;
    # any token outside the known set surfaces as INFO, never a failure (D-14).
    unknown = [p for p in phases if p not in KNOWN_PHASES]
    if unknown:
        print(f"INFO [git] unrecognized phase tokens (not a failure): {unknown}")


def protocol_check(dir: Path) -> bool:
    r"""Conformance GATE for session-log naming + per-leg RESULTS headings (D-04).

    Unlike the report-only `draft`/`audit` verbs, this returns the aggregate ok so
    `main()` can map it to a NON-ZERO exit — the one verb whose exit code is
    load-bearing. It prints PASS/FLAG lines like the others.

    Two checks:

    * name shape (D-05): legs are discovered with `SESSION-*.md`; any `*session*`
      sibling that does NOT match the exact `SESSION-<name>.md` shape (lowercase
      `session-`, `*-session-*`, UUID-suffixed — the round-3 offenders) is a
      violation, not merely absence of a conformant file;
    * RESULTS headings (D-06): `RESULTS.md` in the SAME dir must carry a markdown
      heading naming each discovered leg (`re.search(r"^#{1,6}\s+<name>\b", ...)`);
      a missing heading (or a missing RESULTS.md) FLAGs.
    """
    dir = Path(dir)
    print(f"== protocol conformance: {dir}")
    ok = True

    legs = sorted(dir.glob("SESSION-*.md"))
    leg_names = [m.group(1) for p in legs if (m := SESSION_RE.match(p.name))]

    # D-05: a non-conformant session-ish sibling is itself a violation.
    session_ish = sorted(p for p in dir.glob("*.md") if SESSION_ISH_RE.search(p.name))
    for p in session_ish:
        if not SESSION_RE.match(p.name):
            ok &= _flag(False, "name", f"non-conformant session file: {p.name}")

    # D-06: per discovered leg, RESULTS.md must have a heading naming it.
    results_path = dir / "RESULTS.md"
    results_text = (
        results_path.read_text(encoding="utf-8") if results_path.is_file() else ""
    )
    if leg_names and not results_path.is_file():
        ok &= _flag(False, "results", "RESULTS.md present")
    for name in leg_names:
        found = bool(
            re.search(rf"^#{{1,6}}\s+{re.escape(name)}\b", results_text, re.M | re.I)
        )
        ok &= _flag(found, "results", f"RESULTS.md has a heading for {name}")

    return ok


def main() -> None:
    argv = sys.argv[1:]
    # `protocol` is the one verb that exits non-zero on a violation (D-04); it
    # takes an OPTIONAL dir positional, defaulting to this kit's own directory.
    if argv and argv[0] == "protocol":
        d = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent
        sys.exit(0 if protocol_check(d) else 1)
    # `audit <unit-id> [--root <repo>]` — report-only (exit 0); --root retargets.
    if argv and argv[0] == "audit":
        rest = argv[1:]
        root = ROOT
        if "--root" in rest:
            i = rest.index("--root")
            if i + 1 < len(rest):
                root = Path(rest[i + 1]).resolve()
                rest = rest[:i] + rest[i + 2:]
        if len(rest) == 1:
            audit_unit(rest[0], root=root)
            return
        print(__doc__)
        return
    # `draft <path>` — report-only (exit 0).
    if argv and argv[0] == "draft" and len(argv) == 2:
        score_draft(Path(argv[1]))
        return
    print(__doc__)


if __name__ == "__main__":
    main()
