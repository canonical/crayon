#!/usr/bin/env python3
"""Mechanical validation scorer and independent oracle for crayon (dev-time eval tooling).

Subcommands:

  score.py audit <unit-id> [--root <repo>]
                                     — the independent oracle over
                                       ``.crayon/units/<id>/ledger.jsonl`` plus ONE
                                       ``crayon verify --json`` reading, compared
  score.py protocol [dir]            — conformance gate over one dogfood leg's RUN file: the
                                       four checks a RUN file alone can answer, over the
                                       RUN file in ``dir`` (default ``<ROOT>/validation``),
                                       reporting EVERY failing one

Both subcommands are gates, and their exit codes are load-bearing.

The exit contract, in the repo's uniform vocabulary (tests/check_traces.py, and
tests/install_smoke.sh for the bash side):

    0   clean
    1   violation
    2   NOTHING was checked — the vacuous-pass guard, so a retargeted root or a reshaped
        tree can never masquerade as a clean run

For ``audit``, 0 additionally requires that the ``[verify]`` arm agreed and that no
DISAGREE line was printed.

``audit`` gates on an ENUMERATED subset of its output, never on all of it:

    (a) any of the four oracle checks FLAGs;
    (b) the ``[verify]`` arm reports ``verdict == "fail"``;
    (c) any DISAGREE line was printed (checks 1-3);
    (d) any of exactly three GATING report lines FLAGs — ``[unsteered]``, ``[requests]``
        and ``[sphinx]``.

The other five report lines — ``[edits]``, ``[model]``, ``[report]``, ``[context]`` and
``[steps]`` — are INFORMATIONAL and never gate. Blanket-gating all eight would make
``[steps]`` fail every reference unit (a reference unit has no step plan) and ``[model]``
fail every honest-default draft, which is a gate that reports the shape of the unit rather
than its health.

The paragraph above is the ONLY place the gating enumeration is written down as a list. In
the code each report line carries its own ``gating`` flag and there is no second list to
drift from this one; ``validation/fixtures.sh`` reads both and asserts they agree.

Three verdicts, not two
-----------------------

``_flag`` prints ``PASS``/``FLAG`` — the rule was checked and held, or was checked and did
not. ``_note`` prints ``SKIP``, which says something neither of those can: the EVIDENCE the
rule needs is not here. A unit with no signoff yet has no ``plan_hash`` for oracle check 2 to
compare, and a leg with no RUN file has no Sphinx numbers for ``[sphinx]`` to score. Reporting
either as a PASS would be a claim the run is not entitled to make, and reporting it as a FLAG
would make a declared-but-unsigned unit look damaged. A ``SKIP`` never gates.

"Green" on the ``[verify]`` arm means ``verdict != "fail"``, NOT ``verdict == "ok"``. V14
(level ``status``) and V15/V16/V18/V19 (level ``warn``) results are legitimate on a live
repository — a maintenance edit, a squash merge — so requiring ``ok`` would make a green
audit hostage to facts the validation leg does not control.

Independence — a rule, not a comment on one line
------------------------------------------------

The oracle reaches the tool ONLY by running ``crayon verify <unit> --json`` in a subprocess,
and reads the ledger with its own reader (``read_ledger`` below), which restates contract
§5.2's envelope and serialization rule from the CONTRACT, not from the implementation. It
never imports the ``crayon`` module and never calls ``canonical_line``, ``chain_prev`` or any
other tool primitive, because an oracle that shares code with the tool goes green on the very
bug it exists to catch. The kit is stdlib-only: every parse here is ``json.loads``.

WHICH program that subprocess runs is part of the same rule. ``_crayon_executable`` resolves it
from the KIT's side only — ``CRAYON``, then ``<ROOT>/crayon``, then ``PATH``, each made absolute
— and never from the tree under audit, which would let the audited repository write the reading
the oracle trusts.

The cap is part of the rule. There are EXACTLY FOUR oracle checks:

    oracle-1   chain recompute          — ``seq`` and ``prev`` over the ledger's bytes
    oracle-2   signoff freshness        — the last signoff's ``plan_hash`` vs ``unit.md``
    oracle-3   seal digests vs disk     — the basis ``files[]`` vs ``<root>/docs/<path>``
    oracle-4   sealed path shape        — the recorded ``path`` vs the signoff's ``targets``

and there is no fifth. A fifth check would be a second ``verify``.

Every path taken from the ledger is joined under the RESOLVED ``--root`` before use, and the
scorer never opens a ledger-supplied path directly; every subprocess call uses a
list argv and never a shell string, so a retargeted root or a crafted unit id cannot inject
arguments. Oracle check 3 is the one place the oracle reaches the filesystem with a
path the AUDITED RECORD chose, so the rule is enforced there rather than assumed:
``_resolved_under`` resolves the join and refuses to return a path that leaves
``<root>/docs``, which covers an absolute ``path``, a ``..`` traversal and a symlinked target
alike, and a path that escapes FLAGs without ever being opened.

The DISAGREE matrix
-------------------

    | oracle check            | verify counterpart            | level    | DISAGREE  |
    | ----------------------- | ----------------------------- | -------- | --------- |
    | 1 chain recompute       | V3 (seq + chain), partly V2   | fail     | defined   |
    | 2 signoff freshness     | V19's ``plan_stale`` clause   | warn     | defined   |
    | 3 seal digests vs disk  | V14 (current/drifted/missing) | status   | defined   |
    | 4 sealed path shape     | none                          | —        | UNDEFINED |

Check 4 emits nothing: silence there means "no counterpart exists", NOT "the two readings
agreed", and the row above is where a reader is told so.

DISAGREE is a PER-CHECK-PAIR predicate over the UNDERLYING FINDING — did the check's
condition hold? — and never a comparison of the two exit codes or the two verdicts. ``verify``
exits 0 on a V19 or a V14 finding because their levels are ``warn`` and ``status``, so reading
its exit as agreement would silently bless a stale plan hash or a drifted page. Comparing
VERDICTS instead would make every ``pending-unresolved`` case DISAGREE — V10 FAILs there while
the oracle is silent by design — and so mislabel "the oracle checks a subset of what verify
checks" as "the two readings conflict".

Each pair is read off the CLAUSE of its counterpart that overlaps the oracle check, not off
the counterpart row's status, because V19 and V14 each report more than one thing. V19 covers
the signoff's recorded source digests AND ``plan_stale``; V14 covers ``drifted`` / ``missing``
AND ``new`` (a target on disk that no basis records, which oracle check 3 does not look at).
Pairing on the row's status would manufacture a split whenever the non-overlapping half of a
row fired — the same class of misreading as pairing oracle 1 with V2 separately, and the
reason ``audit`` reads ``plan_stale`` / ``drifted`` / ``missing`` out of the row's own detail.

Reading a clause is not the same as grepping for its NAME, and the difference was a defect.
``V14``'s detail is ``"<path>: <status>"`` joined over every row, so a bare substring
test over the whole string sees the PAGE PATHS as well as the status words: a healthy sealed
unit whose target is ``reference/missing-fields.rst`` made ``audit`` print a DISAGREE and exit
1, and the symmetric case — the oracle FLAGs, V14 is genuinely ``ok``, the path contains
``missing`` — SUPPRESSED a true one. Both directions are wrong on the one line whose whole
point is that neither reading is authoritative. The clause predicates below therefore read the
STATUS TOKEN of each row rather than the detail as one blob.

When the two readings split, neither side is treated as authoritative: ``audit`` prints a
distinct DISAGREE line naming which check split and in which direction, and gates on it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The keys a COMPLETE RUN file carries, and the six session metrics inside `metrics`. Both
# lists exist once, here, and `validation/runmeta.sh` is what writes them; a RUN missing any is
# refused rather than scored, which is the whole of the "incomplete RUN" refusal.
REQUIRED_RUN_KEYS = ("leg", "harness", "model", "tool", "skills", "baseline", "context",
                     "metrics", "transcript", "sphinx", "sphinx_before", "sphinx_after")
REQUIRED_METRIC_KEYS = ("install", "time_to_usable_draft", "avoidable_questions",
                        "manual_crayon_commands", "help_requests", "resume_invocations")


# The docs root, fixed by contract §5.1 and carried on the ledger header as
# ``docs_root: "docs"``. Deliberately a CONSTANT here rather than a value read back out of the
# ledger: the ledger is the artefact under audit, and a root taken from it would let whoever
# rewrote the digests also choose which directory the oracle compares them against.
DOCS_ROOT = "docs"
UNIT_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")

# The number of `audit` checks that run over ANY readable ledger, whatever it holds: oracle
# check 1 (the chain recompute, which needs only bytes) and the `[verify]` arm (which needs only
# the tool). Everything else — oracle checks 2-4 and all eight report lines — needs EVIDENCE on
# the record and SKIPs without it. `checks_run` at this floor therefore means "nothing with unit
# evidence was checked", which is the 2 the exit contract reserves.
ALWAYS_RUN_CHECKS = 2

# Contract §5.4's H set — the events that count as "something was recorded" between two
# generations, and (minus `signoff`) the events that can be pending at a seal.
H_KINDS = ("steering", "review", "signoff")
H_REVIEW_VERDICTS = ("fix", "redraft")

# An ABSOLUTE path of two or more segments, at a word boundary — the shape the Sphinx
# build-output directory takes in the build's own output, and the only absolute path left in a
# diagnostic once the source root has been stripped (normalisation rule 2). Two segments are
# required so an ordinary `and/or` or a `WARNING:` colon-clause is not mistaken for a path.
_ABSOLUTE_PATH_RE = re.compile(r"(?:(?<=\s)|^)/[^\s:]+(?:/[^\s:]+)+")
BUILD_OUTPUT_TOKEN = "<build-output>"


def _flag(ok: bool, tag: str, message: str) -> bool:
    print(f"{'PASS' if ok else 'FLAG'} [{tag}] {message}")
    return ok


def _note(tag: str, message: str) -> None:
    """The third verdict: the EVIDENCE a rule needs is absent, so the rule was not read.

    Absence of the evidence is not a pass of the rule, and a reader has to be able to tell the
    two apart — ``PASS [sphinx]`` over a leg whose RUN file was never written would report the
    Sphinx before/after rule as satisfied by a run that never looked at it. It is not a FLAG
    either: a unit that has been declared but not signed off has no ``plan_hash`` to compare, and
    reporting that as a violation would make an ordinary mid-lifecycle unit look damaged.

    A SKIP never gates, which is safe here only because something else catches the case it
    covers: ``score.py protocol`` is the gate over an INCOMPLETE RUN file, so a
    leg that skipped ``[sphinx]`` because it wrote no RUN file is refused there rather than
    waved through. The two halves of that argument are kept together on purpose.
    """
    print(f"SKIP [{tag}] {message}")


def _events_of(events: list, kind: str) -> list:
    return [event for event in events if event.get("kind") == kind]


def _last(events: list, kind: str):
    found = _events_of(events, kind)
    return found[-1] if found else None


def _seq_of(event: dict) -> int:
    """An event's ``seq`` as an orderable integer; a damaged ``seq`` sorts first, never raises."""
    seq = event.get("seq")
    return seq if isinstance(seq, int) else -1


def _latest_of(events: list, kinds: tuple) -> dict | None:
    candidates = [event for event in events if event.get("kind") in kinds]
    return max(candidates, key=_seq_of) if candidates else None


def _basis(events: list) -> dict | None:
    """Contract §5.4: ``basis = latest of {generation, reviewer-edit} by seq``.

    A ``reviewer-edit`` may be the basis with no generation before it (a brownfield adoption),
    and its ``files[]`` entries carry ``path`` and ``sha256`` and NEVER ``bytes`` (§5.3). Any
    reader here that required ``bytes`` would break on every hand-edit adoption.
    """
    return _latest_of(events, ("generation", "reviewer-edit"))


def _tip(events: list) -> dict | None:
    """Contract §5.4: ``tip = latest of {generation, reviewer-edit, review} by seq``."""
    return _latest_of(events, ("generation", "reviewer-edit", "review"))


def _is_h(event: dict) -> bool:
    """Contract §5.4's H: steering, a fix/redraft review, or a signoff."""
    kind = event.get("kind")
    if kind == "review":
        return event.get("verdict") in H_REVIEW_VERDICTS
    return kind in ("steering", "signoff")


def _is_sealed(events: list) -> bool:
    """Contract §5.4's ``sealed``: an accepting tip, no H after it, no stale generation.

    This is the narrowest derivation the oracle performs, and it is here because ``[requests]``
    needs it: an open request while the page is still being worked is the ordinary state of a
    unit mid-loop, and only an open request at a SEALED tip is a finding.
    """
    tip = _tip(events)
    if tip is None or tip.get("kind") != "review" or tip.get("verdict") != "accept":
        return False
    if any(_is_h(event) and _seq_of(event) > _seq_of(tip) for event in events):
        return False
    generation = _last(events, "generation")
    signoff = _last(events, "signoff")
    if generation is not None and signoff is not None:
        if generation.get("signoff_seq") != signoff.get("seq"):
            return False
    return True


def _sha256_file(path: Path) -> tuple:
    """``(digest, problem)`` over a file's bytes. Never raises — a problem string, or a digest."""
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest(), None
    except OSError as exc:
        return None, str(exc)


def _resolved_under(directory: Path, relative: str) -> Path | None:
    """``directory / relative``, resolved, or ``None`` when the result leaves ``directory``.

    The containment control for oracle check 3 and the independent second
    reading of the property the tool enforces with ``contained()`` + ``realpath``. ``Path.__truediv__``
    DISCARDS the left side when the right is absolute, and ``resolve()`` collapses ``..`` and
    follows symlinks, so an absolute ``path``, a traversal and a link pointing out of ``docs/``
    are all caught by the same comparison. The caller FLAGs on ``None`` and never opens it.
    """
    candidate = (directory / relative).resolve()
    try:
        candidate.relative_to(directory.resolve())
    except ValueError:
        return None
    return candidate


def read_ledger(path: Path) -> tuple[list[dict], list[str]]:
    """Read ``ledger.jsonl`` and recompute its chain — the oracle's OWN §5.2 restatement.

    Returns ``(events, problems)`` and NEVER raises. A missing file, an unreadable file, an
    empty file, a line that is not valid UTF-8, a line that is not valid JSON, a line that is
    not a JSON object and a truncated final line all come back as problem strings. Every
    problem names the line number, what was found and what was expected — the repo's "name
    what you compared" convention, because a checker that reports a violation without naming
    the two sides it compared is the failure mode this tree lints against.

    The rule being restated, from ``docs/contract.md`` §5.2 and deliberately NOT from the
    tool's own ``canonical_line`` / ``chain_prev`` (the independence rule): ``seq`` is
    contiguous from 0; ``prev`` is the sha256 of the PREVIOUS LINE'S EXACT BYTES with the
    trailing LF excluded, and is ``null`` at seq 0. The digest is taken over the bytes read
    from disk and never over a re-serialisation of the parsed object, so a key-order or
    whitespace difference that survives ``json.loads`` still FLAGs.

    One bad line does not invalidate the reader's account of the lines after it: the walk
    continues with that line's RAW BYTES as the new ``previous``, which is what the writer
    would have hashed, so a single corrupt line produces one finding rather than a cascade.
    """
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        return [], ["%s: cannot read the ledger (%s)" % (path, exc)]

    problems: list[str] = []
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()  # the writer always ends with exactly one LF
    elif raw:
        # The pop above is the ONLY place the trailing LF is read, and it used to be
        # silent when there wasn't one — so a file ending mid-line at a line BOUNDARY (the last
        # event written whole, its LF never reached) came back with every event parsed and no
        # problem at all, and `audit` printed `chain recomputes clean`. Contract §5.2 fixes the
        # writer as `json.dumps(...) + "\n"`, so a final line with no LF is the signature of an
        # interrupted `write()` — the case §5.8's manifest recovery boundary exists for. The
        # docstring below already claimed a truncated final line is caught; it was caught only
        # when the truncation happened to land mid-token.
        problems.append("line %d: the final line has no trailing LF; contract §5.2's writer "
                        "always ends a ledger with exactly one, so this is a truncated write"
                        % len(lines))
    if not lines:
        return [], ["line 1: the ledger is empty; expected at least the seq 0 "
                    "'ledger' header event"]

    events: list[dict] = []
    previous: bytes | None = None
    for index, line in enumerate(lines):
        expected_prev = (None if previous is None
                         else hashlib.sha256(previous).hexdigest())
        try:
            event = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            problems.append("line %d: not valid JSON (%s)" % (index + 1, exc))
            previous = line
            continue
        if not isinstance(event, dict):
            problems.append("line %d: not a JSON object, found %s"
                            % (index + 1, type(event).__name__))
        else:
            if event.get("seq") != index:
                problems.append("line %d: seq is %r, expected %d"
                                % (index + 1, event.get("seq"), index))
            if event.get("prev") != expected_prev:
                problems.append("line %d: prev is %r, expected %r"
                                % (index + 1, event.get("prev"), expected_prev))
            events.append(event)
        previous = line
    return events, problems


def _json_documents(text: str) -> list:
    """Every top-level JSON document embedded in ``text``, in order.

    ``verify --json`` writes its full report to stdout and, on a FAIL among V1-V13, ALSO
    writes its one-line refusal object there (contract §5.7 moves the refusal to stdout under
    ``--json``) before exiting 6. Scanning for documents rather than parsing the whole stream
    is what lets the report be read on the refusing path as well as the clean one.
    """
    decoder = json.JSONDecoder()
    found: list = []
    index = 0
    while index < len(text):
        if text[index] not in "{[":
            index += 1
            continue
        try:
            document, end = decoder.raw_decode(text, index)
        except ValueError:
            index += 1
            continue
        found.append(document)
        index = end
    return found


#: The separator ``verify`` joins one check row's segments with. Restated here from the
#: OBSERVED report rather than imported from ``crayon``'s ``SEGMENT`` (the oracle never
#: imports the tool), and used for exactly one thing — splitting ``V14``'s detail back into the
#: ``"<path>: <status>"`` rows it was built from, so the pair predicate reads a STATUS and not
#: a page path. A drift here degrades to "the whole detail is one row", which reads a status
#: token of the wrong shape and matches nothing: it can make the oracle's own reading look
#: unpaired, never make a finding disappear.
SEGMENT_SEPARATOR = " · "


def _v14_finding_ok(detail: str) -> bool:
    """V14's ``drifted`` / ``missing`` clause — the half oracle check 3 overlaps. ``(ok)``.

    One row is ``"<path>: <status>"``; the STATUS is what is read, taken after the LAST
    ``": "`` so a path carrying a colon cannot move the boundary. ``new`` is deliberately NOT
    a finding here: it is a target on disk that no basis records, which oracle check 3 does not
    look at, and counting it would manufacture the very split the docstring's matrix argues
    against. A detail that is not a row list at all (``"no basis is recorded…"``) carries no
    status token and is read as ok, which is what those two V14 details mean.
    """
    for row in detail.split(SEGMENT_SEPARATOR):
        status = row.rsplit(": ", 1)[-1].strip()
        if status == "missing" or status.startswith("drifted"):
            return False
    return True


def _v19_finding_ok(detail: str) -> bool:
    """V19's ``plan_stale`` clause — the half oracle check 2 overlaps. ``(ok)``.

    V19 renders the FIRST problem it found plus a count, and its ``plan_stale`` problem is
    written as a labelled clause (``plan_stale: unit.md has changed since…``). Matching the
    label WITH its colon is what keeps a recorded source path that happens to contain the word
    from being read as the clause — the same defect ``_v14_finding_ok`` exists for.
    """
    return "plan_stale: " not in detail


def _crayon_executable() -> str | None:
    """The tool to run for the ``[verify]`` arm, resolved from the KIT's side only.

    ``CRAYON`` in the environment wins — ``crayon`` is not checked into a target documentation
    repository, so the environment variable is the path the validation legs actually use —
    then this KIT's own ``<ROOT>/crayon``, then the bare name on ``PATH``. Returns ``None`` when
    the tool cannot be found at all, which the caller reports as a FLAG rather than a crash.

    NEVER ``<root>/crayon``, where ``root`` is the tree under audit. That fallback let
    the audited repository choose the program whose reading the oracle trusts: a three-line
    ``crayon`` shipped in the target made ``audit`` print ``PASS [verify] … verdict 'ok'`` and
    exit 0, and ran as the auditing user besides. The ``[verify]`` arm is the oracle's single
    point of contact with the tool and its whole value is that it is an INDEPENDENT reading;
    an executable the audited tree supplies is not one. This is the argument ``DOCS_ROOT``
    already makes one screen up, applied to the program rather than to the directory:

        the ledger is the artefact under audit, and a root taken from it would let whoever
        rewrote the digests also choose which directory the oracle compares them against

    The list-argv claim ("a retargeted root … cannot inject arguments") is about argv SHAPE
    and never covered which program is executed, so it is not the guard here.

    Both resolved paths are made ABSOLUTE: ``audit`` runs the subprocess with ``cwd=root``, and
    a relative ``CRAYON`` (or a ``which`` hit from a ``PATH`` carrying ``.``) would otherwise be
    resolved by ``subprocess`` against the audited tree — the same defect one indirection out.
    """
    from_env = os.environ.get("CRAYON")
    if from_env:
        return str(Path(from_env).resolve())
    in_kit = ROOT / "crayon.py"
    if in_kit.is_file():
        return str(in_kit)
    found = shutil.which("crayon")
    return str(Path(found).resolve()) if found else None


def _oracle_2(events: list, root: Path, unit_id: str) -> tuple:
    """Oracle check 2 of 4 — signoff freshness. Returns ``(ran, ok)``.

    ``unit_hash`` on the ``unit-declared`` event and ``plan_hash`` on the ``signoff`` event are
    the SAME digest — ``sha256(unit.md)`` — taken at two different instants. This check
    compares the LAST signoff's ``plan_hash`` against the CURRENT file, which is the question a
    reader of the record actually has: is the plan that was signed still the plan on disk?
    """
    signoff = _last(events, "signoff")
    unit_md = root / ".crayon" / "units" / unit_id / "unit.md"
    if signoff is None:
        _note("oracle-2", "no signoff event on record, so there is no plan_hash to compare "
                          f"against {unit_md}")
        return False, True
    recorded = signoff.get("plan_hash")
    computed, problem = _sha256_file(unit_md)
    if computed is None:
        return True, _flag(False, "oracle-2",
                           f"the signoff at seq {signoff.get('seq')} records plan_hash "
                           f"{recorded!r}, and {unit_md} cannot be read to compare it "
                           f"({problem})")
    return True, _flag(
        recorded == computed, "oracle-2",
        f"the signoff at seq {signoff.get('seq')} records plan_hash {recorded!r}; "
        f"sha256({unit_md}) is {computed!r}"
        + ("" if recorded == computed else " — the signed plan is not the plan on disk"))


def _oracle_3(events: list, root: Path, unit_id: str) -> tuple:
    """Oracle check 3 of 4 — the seal's digests against the bytes on disk. ``(ran, ok)``.

    The basis is determined the way contract §5.4 determines it, and the ``docs/`` join is the
    ORACLE's own: a basis event records ``reference/demo.rst``, never ``docs/reference/demo.rst``
    (``basis_path()`` documents the inverse). Every entry is type-guarded
    before use, so a ``path`` of ``null`` or a non-mapping entry FLAGs with the entry printed
    rather than raising.

    Where the tip is an accepting review, its ``files[]`` is compared against the basis event's
    too: contract V6 requires them equal, and a difference is a finding. It is reported HERE,
    under check 3, rather than as a check of its own — the oracle is capped at four.
    """
    basis = _basis(events)
    if basis is None:
        _note("oracle-3", "no generation or reviewer-edit on record, so no page has been "
                          "sealed and there is no digest to compare against disk")
        return False, True
    docs_root = root / DOCS_ROOT
    entries = basis.get("files")
    if not isinstance(entries, list) or not entries:
        return True, _flag(False, "oracle-3",
                           f"the basis at seq {basis.get('seq')} records files {entries!r}, "
                           "expected a non-empty list of {path, sha256} mappings")

    problems: list[str] = []
    compared = 0
    for index, entry in enumerate(entries):
        where = f"the basis at seq {basis.get('seq')} files[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{where} is not a mapping, found {entry!r}")
            continue
        recorded_path = entry.get("path")
        recorded_digest = entry.get("sha256")
        if not isinstance(recorded_path, str) or not recorded_path:
            problems.append(f"{where} records path {recorded_path!r}, expected a non-empty "
                            "string in the basis vocabulary (no 'docs/' prefix)")
            continue
        joined = _resolved_under(docs_root, recorded_path)
        if joined is None:
            problems.append(f"{where} records path {recorded_path!r}, which leaves "
                            f"{docs_root} when the oracle joins it — refused unread")
            continue
        computed, problem = _sha256_file(joined)
        if computed is None:
            problems.append(f"{where} seals {DOCS_ROOT}/{recorded_path} with sha256 "
                            f"{recorded_digest!r}, and that file cannot be read ({problem})")
            continue
        compared += 1
        if computed != recorded_digest:
            problems.append(f"{where} seals {DOCS_ROOT}/{recorded_path} with sha256 "
                            f"{recorded_digest!r}; the bytes on disk hash to {computed!r}")

    tip = _tip(events)
    if (tip is not None and tip is not basis and tip.get("kind") == "review"
            and tip.get("verdict") == "accept" and tip.get("files") != basis.get("files")):
        problems.append(f"the accepting review at seq {tip.get('seq')} records a files[] that "
                        f"differs from the basis at seq {basis.get('seq')}; contract V6 "
                        "requires them equal")

    return True, _flag(
        not problems, "oracle-3",
        (f"{compared} sealed page(s) under {docs_root} hash to the digest the basis at seq "
         f"{basis.get('seq')} recorded" if not problems
         else "; ".join(problems)))


def _oracle_4(events: list, root: Path, unit_id: str) -> tuple:
    """Oracle check 4 of 4 — the shape of the sealed path. ``(ran, ok)``.

    Two assertions over the same ``files[]`` and the last signoff's ``targets``: the recorded
    ``path`` is a signoff target exactly, and joining ``docs/`` onto it yields no ``docs/docs/``
    segment. ``crayon signoff`` REFUSES a ``docs/``-prefixed target outright — ``bad_write_path``,
    with a hint telling the author to drop the leading prefix — so a ledger carrying one cannot
    have been produced by the tool. That is what makes this an independent tamper signal and
    not a style check, and it is why check 4 has no ``verify`` counterpart to disagree with.

    A ``reviewer-edit`` basis is allowed paths outside ``targets``: contract V13 makes it a
    superset of the previous basis, so a path that is no longer a signed target is an ORPHAN —
    reported, never a FLAG. Only a ``generation``, whose ``files[]`` V13 requires to equal the
    current targets, makes an unlisted path a finding.
    """
    basis = _basis(events)
    signoff = _last(events, "signoff")
    if basis is None or signoff is None:
        _note("oracle-4", "no signoff or no sealed files[] on record, so there is no recorded "
                          "path to compare against the signed targets")
        return False, True
    targets = signoff.get("targets")
    if not isinstance(targets, list):
        targets = []
    entries = basis.get("files")
    if not isinstance(entries, list):
        entries = []

    prefix = DOCS_ROOT + "/"
    problems: list[str] = []
    orphans: list[str] = []
    for index, entry in enumerate(entries):
        where = f"the basis at seq {basis.get('seq')} files[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{where} is not a mapping, found {entry!r}")
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            problems.append(f"{where} records path {path!r}, expected a non-empty string")
            continue
        if path == DOCS_ROOT or path.startswith(prefix):
            problems.append(
                f"{where} records path {path!r}, which already carries the {prefix!r} prefix: "
                f"joining the docs root onto it yields {prefix + path!r}, a "
                f"{prefix + DOCS_ROOT}/ segment. crayon signoff refuses such a target, so this "
                "path was not written by the tool")
        elif path not in targets:
            if basis.get("kind") == "reviewer-edit":
                orphans.append(path)
            else:
                problems.append(f"{where} records path {path!r}, which is not one of the "
                                f"signoff's targets {targets!r}")

    for orphan in orphans:
        print(f"INFO [oracle-4] {orphan!r} is carried by the reviewer-edit basis and is no "
              f"longer a signed target — an orphan, reported and never deleted")
    return True, _flag(
        not problems, "oracle-4",
        (f"{len(entries)} recorded path(s) are signoff targets in the basis vocabulary and "
         f"carry no {prefix!r} prefix" if not problems else "; ".join(problems)))


def _line_unsteered(events: list, root: Path, unit_id: str) -> tuple:
    """``[unsteered]`` — the generations' ``unsteered`` claim and its reason. ``(gating, ran, ok)``."""
    gating = True
    generations = _events_of(events, "generation")
    if not generations:
        _note("unsteered", "no generation on record, so there is no unsteered claim to read")
        return gating, False, True

    problems: list[str] = []
    overridden = []
    for event in generations:
        reason = event.get("unsteered_reason")
        has_reason = isinstance(reason, str) and reason.strip() != ""
        if event.get("unsteered") is True:
            overridden.append(event.get("seq"))
            if not has_reason:
                problems.append(f"the generation at seq {event.get('seq')} records "
                                f"unsteered: true with unsteered_reason {reason!r}")
    h_seqs = [_seq_of(event) for event in events if _is_h(event)]
    for earlier, later in zip(generations, generations[1:]):
        between = [seq for seq in h_seqs
                   if _seq_of(earlier) < seq < _seq_of(later)]
        reason = later.get("unsteered_reason")
        overrode = (later.get("unsteered") is True
                    and isinstance(reason, str) and reason.strip() != "")
        if not between and not overrode:
            problems.append(
                f"the generations at seq {earlier.get('seq')} and {later.get('seq')} have no "
                "steering, fix, redraft or signoff recorded between them, and the later one "
                "records no unsteered override")
    return gating, True, _flag(
        not problems, "unsteered",
        (f"{len(generations)} generation(s), {len(overridden)} with a recorded override"
         if not problems else "; ".join(problems)))


def _line_edits(events: list, root: Path, unit_id: str) -> tuple:
    """``[edits]`` — the reviewer edits on record. Informational. ``(gating, ran, ok)``.

    A ``reviewer-edit``'s ``files[]`` entries carry ``path`` and ``sha256`` and NEVER ``bytes``
    (contract §5.3 puts ``bytes`` on ``generation`` alone), so nothing here asks for it — a
    reader that required ``bytes`` would break on every hand-edit adoption, which is the one
    known hazard on this line.
    """
    gating = False
    edits = _events_of(events, "reviewer-edit")
    if not edits:
        _note("edits", "no reviewer-edit on record: nothing has been adopted by hand")
        return gating, False, True
    described = []
    for event in edits:
        entries = event.get("files") if isinstance(event.get("files"), list) else []
        paths = [entry.get("path") for entry in entries if isinstance(entry, dict)]
        described.append(
            "seq %s over %d file(s) %r, against generation_seq %r%s: %r"
            % (event.get("seq"), len(entries), paths, event.get("generation_seq"),
               " [hook-adopted]" if event.get("hook") is True else "", event.get("note")))
    return gating, True, _flag(True, "edits",
                         "%d reviewer edit(s): %s" % (len(edits), "; ".join(described)))


def _line_model(events: list, root: Path, unit_id: str) -> tuple:
    """``[model]`` — the last generation's model claim. Informational. ``(gating, ran, ok)``.

    There is no ``crayon model set`` in v2.0 and no configured model identity to read: the model
    is a PER-GENERATION CLAIM, passed as ``draft --model`` / ``--model-origin`` and defaulting
    to ``""`` / ``"unknown"``. That default is the HONEST one — it records that nobody claimed a
    model rather than guessing one — so it is reported and never FLAGged, which is exactly why
    this line does not gate. Consistency between the pair is V11's job, at ``fail`` level.
    """
    gating = False
    generation = _last(events, "generation")
    if generation is None:
        _note("model", "no generation on record, so no model has been claimed")
        return gating, False, True
    model = generation.get("model")
    origin = generation.get("model_origin")
    honest_default = (model == "" and origin == "unknown")
    return gating, True, _flag(
        True, "model",
        "the generation at seq %s claims model %r with model_origin %r%s"
        % (generation.get("seq"), model, origin,
           " — the honest default: no model was claimed" if honest_default else ""))


def _line_report(events: list, root: Path, unit_id: str) -> tuple:
    """``[report]`` — the drafting skill's own claims. Informational. ``(gating, ran, ok)``.

    ``origins``, ``gaps`` and ``gaps_note`` reach the generation event only when ``draft
    --report`` was used, and ``origins[]`` are plain strings capped at ``MAX_ORIGINS``. Their
    ABSENCE is reported, never FLAGged — a draft made without a report is a legitimate draft.
    A declared GAP is a different thing: it is the skill's own statement that the page is
    incomplete, which a reader of the audit should see. It is still informational, because a
    gap the author knowingly accepted must not fail the leg.
    """
    gating = False
    generation = _last(events, "generation")
    if generation is None:
        _note("report", "no generation on record, so there are no drafting claims to read")
        return gating, False, True
    origins = generation.get("origins")
    gaps = generation.get("gaps")
    gaps_note = generation.get("gaps_note")
    if origins is None and gaps is None and not gaps_note:
        _note("report", "the generation at seq %s records no origins, gaps or gaps_note: "
                        "draft --report was not used" % generation.get("seq"))
        return gating, False, True
    declared = gaps if isinstance(gaps, list) else []
    return gating, True, _flag(
        not declared, "report",
        "the generation at seq %s reports %d origin(s) %r and %d declared gap(s) %r%s"
        % (generation.get("seq"), len(origins or []), origins or [],
           len(declared), declared,
           ", gaps_note %r" % (gaps_note,) if gaps_note else ""))


def _line_context(events: list, root: Path, unit_id: str) -> tuple:
    """``[context]`` — the sources the plan was signed against. Informational. ``(gating, ran, ok)``.

    This is the SIGNOFF event's ``context``: a ``{path: sha256}`` map populated from
    ``unit new --source``. It is NOT the RUN file's ``context`` key (the leg's origins
    digests) — two different things carrying one name — and the line's own text says so,
    because a reader who conflates them will read a leg's environment record as the plan's
    source provenance.
    """
    gating = False
    signoff = _last(events, "signoff")
    if signoff is None:
        _note("context", "no signoff on record, so no sources were frozen with a plan")
        return gating, False, True
    recorded = signoff.get("context")
    if not isinstance(recorded, dict):
        return gating, True, _flag(False, "context",
                             "the signoff at seq %s records context %r, expected a "
                             "{path: sha256} mapping" % (signoff.get("seq"), recorded))
    if not recorded:
        return gating, True, _flag(
            True, "context",
            "no recorded source digests: the signoff at seq %s froze an empty context map "
            "(unit new --source was not used). This is the signoff event's `context`, not "
            "the RUN file's `context` key — two different things with one name"
            % signoff.get("seq"))

    problems = []
    for path in sorted(recorded):
        joined = _resolved_under(root, path)
        if joined is None:
            problems.append("%r leaves %s when joined — refused unread" % (path, root))
            continue
        computed, failure = _sha256_file(joined)
        if computed is None:
            problems.append("%s cannot be read now (%s)" % (path, failure))
        elif computed != recorded[path]:
            problems.append("%s was signed at %r and now hashes to %r"
                            % (path, recorded[path], computed))
    return gating, True, _flag(
        not problems, "context",
        ("%d recorded source digest(s) at the signoff's `context` — not the RUN file's "
         "`context` key — still match" % len(recorded) if not problems
         else "; ".join(problems)))


def _line_steps(events: list, root: Path, unit_id: str) -> tuple:
    """``[steps]`` — the step plan and its records. Informational. ``(gating, ran, ok)``.

    A reference unit has neither a ``steps-planned`` nor a ``step-recorded`` event, and that is
    its ORDINARY shape rather than a defect — so the line renders "no step plan" and does not
    FLAG. Gating this line would fail every reference unit in the kit, which is a gate that
    reports the shape of a unit rather than its health.
    """
    gating = False
    planned = _events_of(events, "steps-planned")
    recorded = _events_of(events, "step-recorded")
    if not planned and not recorded:
        _note("steps", "no step plan: this unit records neither a steps-planned nor a "
                       "step-recorded event, which is the ordinary shape of a reference unit")
        return gating, False, True
    failed = [event.get("step_id") for event in recorded if event.get("verdict") == "fail"]
    described = []
    for event in planned:
        steps = event.get("steps") if isinstance(event.get("steps"), list) else []
        described.append("seq %s plans %d step(s), reuse %r"
                         % (event.get("seq"), len(steps), event.get("reuse")))
    return gating, True, _flag(
        not failed, "steps",
        "%s; %d step record(s)%s"
        % ("; ".join(described) or "no steps-planned event", len(recorded),
           ", failing: %r" % (failed,) if failed else ""))


# A diagnostic BEGINS at a severity marker (`path:line: WARNING: …`, or a bare `WARNING: …`) or at
# one of Sphinx's own top-level error headers. Everything else is a continuation of the diagnostic
# above it — the quoted source line, its underline, a traceback frame. See rule 4 in
# `normalise_diagnostics`: continuations are joined to their header, never dropped.
_DIAGNOSTIC_START_RE = re.compile(
    r"(?:\b(?:WARNING|ERROR|SEVERE|CRITICAL)\b\s*:)"
    r"|(?:^(?:Extension|Config|Configuration|Theme|Application|Sphinx|Builder) error\b)"
)


def normalise_diagnostics(text: str, root: Path) -> list:
    """The Sphinx diagnostics blob as a list of comparable lines.

    Three rules, and they are the whole of it:

    1. Strip the resolved ``root`` prefix, with and without a trailing separator, wherever it
       appears. The absolute prefix differs between the primary checkout and any worktree and
       says nothing about the diagnostic.
    2. Replace any remaining ABSOLUTE path with a fixed token. After rule 1 the only absolute
       paths left are outside the source tree — the build-output directory above all, whose
       depth varies with where the output was placed.
    3. Do NOT normalise line numbers. A diagnostic that moved lines is a DIFFERENT item and the
       author should account for it; erasing the number would silently accept a warning that
       migrated to a page nobody looked at.
    4. One DIAGNOSTIC is one item, not one line. Sphinx prints the offending source line and its
       underline beneath a warning, so splitting on newlines turned a single `Title underline too
       short.` into three items — the warning, a section title, and a run of dashes — and asked the
       author to account for a row of dashes as though it were a finding. Continuation lines are
       JOINED to the header above them.

       Joining is not filtering, and rule 4 does not weaken the prohibition below: every byte that
       arrives still appears in the comparison, in the same order. What changes is which item owns
       it. A continuation line that is dropped, and a continuation line that is attributed to its
       header, are different things; only the first would be the defect this docstring warns about.

    And one prohibition, which is why this function is short: nothing here filters, drops or
    reorders lines by filename, by severity or by text. The whole normalised line list is the
    comparison. Filtering the evidence so a claim comes out clean is the exact failure this
    comparison exists to prevent, and a reader who finds a filename test added below should read
    it as the defect it would be, not as an optimisation.
    """
    if not isinstance(text, str):
        return []
    resolved = str(Path(root).resolve())
    items: list = []
    for line in text.split("\n"):
        line = line.replace(resolved + os.sep, "").replace(resolved, "")
        line = _ABSOLUTE_PATH_RE.sub(BUILD_OUTPUT_TOKEN, line)
        line = line.strip()
        if not line:
            continue
        if _DIAGNOSTIC_START_RE.search(line) or not items:
            items.append(line)
        else:
            items[-1] = items[-1] + " | " + line
    return items


def diff_diagnostics(before: list, after: list) -> tuple:
    """``(new_items, resolved_items)`` as MULTISET differences, each sorted.

    A multiset, not a set: two byte-identical diagnostics after where there was one before is
    exactly ONE new item, and a set difference would report zero and wave the second one
    through. ``Counter`` subtraction keeps only positive counts, which is the arithmetic that
    statement describes.

    Sorted, because that is what makes two runs over the same pair of builds print
    byte-identical output — a gate whose output reordered between honest runs could not be
    diffed, and a leg's evidence is read by diffing it.
    """
    before_counts = Counter(before)
    after_counts = Counter(after)
    return (sorted((after_counts - before_counts).elements()),
            sorted((before_counts - after_counts).elements()))


def _line_sphinx(events: list, root: Path, unit_id: str) -> tuple:
    """``[sphinx]`` — the leg's Sphinx before/after diff and its attribution. GATING.

    The Sphinx rule's machine half. It normalises both diagnostics blocks, takes the multiset
    difference, and checks every NEW item against the RUN file's ``sphinx_attribution`` list. The
    JUDGEMENT — is this new warning acceptable? — stays with the author; the BOOKKEEPING does
    not, so an item nobody accounted for FLAGs and gates.

    The counts and both builds' exit codes print on a PASS as well as on a FLAG. A gate that
    shows its working only when it fails leaves a green run unreadable, and the two exit codes
    are half of what the Sphinx rule asks for: a build that CRASHED with no diagnostics is not
    the same fact as a build that emitted none.

    Printing them is not enough, and used not to be: the verdict was the diagnostics
    diff alone, so two builds that never ran produced two equal empty blobs, an empty diff and
    a PASS on a GATING line. A non-zero ``exit`` on either half is therefore a FLAG in its own
    right, reported ALONGSIDE any unaccounted item rather than instead of it — an author whose
    build crashed AND whose diff moved has two things to fix and should be told both. An
    ``exit`` that is absent or is not an integer is treated the same way: a RUN file that does
    not say the build finished is not evidence that it did.

    The RUN file is UNTRACKED, unvalidated working-tree input that both this kit and
    ``crayon summary`` read. Every read below is behind an explicit type guard and every
    malformed shape FLAGs naming what was missing — a traceback at the reader is the outcome
    these guards exist to prevent. The file scanned is the FIRST by sorted name, the same one
    ``crayon``'s ``sphinx_result`` would pick.
    """
    gating = True
    run_directory = root / "validation"
    run_files = sorted(run_directory.glob("RUN-*.json"))
    if not run_files:
        _note("sphinx", "no RUN file under %s/ — not scored" % run_directory)
        return gating, False, True

    run_path = run_files[0]
    label = "validation/%s" % run_path.name
    try:
        with open(run_path, "r", encoding="utf-8") as handle:
            data = json.loads(handle.read())
    except (OSError, ValueError) as problem:
        return gating, True, _flag(False, "sphinx",
                             "%s is not readable JSON (%s)" % (label, problem))
    if not isinstance(data, dict):
        return gating, True, _flag(False, "sphinx",
                             "%s is a %s, expected a JSON object"
                             % (label, type(data).__name__))

    # Every shape problem, not the first: a RUN file missing both halves has two things wrong
    # with it, and a reader told about one of them fixes one and comes back.
    blocks = {}
    problems = []
    for key in ("sphinx_before", "sphinx_after"):
        block = data.get(key)
        if not isinstance(block, dict):
            problems.append("%s is %r, expected an object with an `exit` and a "
                            "`diagnostics` string" % (key, block))
            continue
        if not isinstance(block.get("diagnostics"), str):
            problems.append("%s.diagnostics is %r, expected a string"
                            % (key, block.get("diagnostics")))
            continue
        blocks[key] = block
    if problems:
        return gating, True, _flag(False, "sphinx", "%s: %s" % (label, "; ".join(problems)))

    before = normalise_diagnostics(blocks["sphinx_before"]["diagnostics"], root)
    after = normalise_diagnostics(blocks["sphinx_after"]["diagnostics"], root)
    new_items, resolved_items = diff_diagnostics(before, after)

    # The attribution list names NORMALISED lines — the strings this line prints — so the
    # author copies a FLAG's own output into the RUN file rather than retyping a build's.
    # MEMBERSHIP used to be the whole test, so `--attribute "<item>="` — or a
    # hand-written `{"item": "…", "account": ""}` — silenced a new warning with no account at
    # all, while the INFO line printed `accounted: ` followed by nothing. The bookkeeping half
    # of the Sphinx rule IS this list; an empty entry is a bookkeeping no-op that reads as done.
    # An entry whose account is blank is recorded separately so the FLAG can say which kind
    # of nothing it found, rather than reporting it as an item nobody had noticed.
    accounts = {}
    blank = set()
    for entry in data.get("sphinx_attribution") or []:
        if isinstance(entry, dict) and isinstance(entry.get("item"), str):
            account = str(entry.get("account") or "").strip()
            if account:
                accounts.setdefault(entry["item"], account)
            else:
                blank.add(entry["item"])

    unaccounted = [item for item in new_items if item not in accounts]
    for item in new_items:
        if item in accounts:
            note = "accounted: %s" % accounts[item]
        elif item in blank:
            note = "UNACCOUNTED (its sphinx_attribution entry has an EMPTY account)"
        else:
            note = "UNACCOUNTED"
        print("INFO [sphinx] new: %s — %s" % (item, note))
    for item in resolved_items:
        print("INFO [sphinx] resolved: %s" % item)

    reading = ("%s: before exit %r (%d item(s)), after exit %r (%d item(s)); %d new, "
               "%d resolved"
               % (label, blocks["sphinx_before"].get("exit"), len(before),
                  blocks["sphinx_after"].get("exit"), len(after),
                  len(new_items), len(resolved_items)))

    # Every failing half, not the first: a leg whose build crashed AND whose diff moved has two
    # findings, and a reader told about one of them fixes one and comes back.
    findings = []
    crashed = [name for name in ("sphinx_before", "sphinx_after")
               if blocks[name].get("exit") != 0]
    if crashed:
        findings.append(
            "%s exited non-zero or recorded no exit (%s): a build that did not complete is "
            "not a build that emitted no diagnostics, and an empty diff over two builds that "
            "never ran is not evidence"
            % (", ".join(crashed),
               ", ".join("%s=%r" % (name, blocks[name].get("exit")) for name in crashed)))
    if unaccounted:
        empty = [item for item in unaccounted if item in blank]
        findings.append("%d new item(s) accounted for by nobody: %s%s"
                        % (len(unaccounted), "; ".join(unaccounted),
                           " — %d of them carry a sphinx_attribution entry with an EMPTY "
                           "account, which is not an account" % len(empty) if empty else ""))
    if findings:
        return gating, True, _flag(False, "sphinx", "%s; %s" % (reading, "; ".join(findings)))
    return gating, True, _flag(True, "sphinx",
                         "%s; both builds exited 0 and every new item is accounted for in "
                         "sphinx_attribution" % reading)


def _line_requests(events: list, root: Path, unit_id: str) -> tuple:
    """``[requests]`` — steering pending at the tip. ``(gating, ran, ok)``.

    ``pending`` is DERIVED by contract §5.4 and is not a stored field, so it is computed here:
    the H events after the last generation (signoff excluded), minus every seq any later accept
    names in ``resolves`` or ``withdraws``. A pending request while the page is still being
    worked is the ordinary state of a unit mid-loop; a pending request at a SEALED tip is the
    finding, because that is a page sealed over a request nobody ever judged.

    LATER is load-bearing and was once not implemented. The dispositions were collected from
    EVERY accept in any position, so a hand-appended accept could name a seq that did not exist
    when it was written and silence a request recorded after it: an accept at seq 4 carrying
    ``"resolves": [5]`` disposed of the steering at seq 5 and this GATING line passed. On a
    well-formed ledger the two readings agree — the tool only ever resolves requests already on
    record — and the forged case is the one V-04 exists for, so agreeing on the honest input is
    not evidence the rule was implemented. A disposition naming a seq at or after its own accept
    is reported as the tamper signal it is, and never silently dropped.

    A unit with NO generation and NO request on record reports SKIP rather than "0 request(s)
    pending". There is neither a request to count nor a generation to count it from, so
    the zero is a count of nothing, and this line is one of the three that gate: a claim over no
    evidence is precisely what ``checks_run`` must not be allowed to count.
    """
    gating = True
    generation = _last(events, "generation")
    floor = _seq_of(generation) if generation is not None else 0
    requests = [event for event in events
                if _is_h(event) and event.get("kind") != "signoff" and _seq_of(event) > floor]
    if generation is None and not requests:
        _note("requests", "no generation and no steering, fix or redraft on record, so there "
                          "is no request to count and nothing to count it from")
        return gating, False, True

    disposed = set()
    out_of_order = []
    for review in _events_of(events, "review"):
        if review.get("verdict") != "accept":
            continue
        review_seq = _seq_of(review)
        named = [(field, seq if not isinstance(seq, dict) else seq.get("seq"))
                 for field in ("resolves", "withdraws")
                 for seq in review.get(field) or []]
        for field, seq in named:
            if isinstance(seq, int) and seq < review_seq:
                disposed.add(seq)
            else:
                out_of_order.append((review_seq, field, seq))

    for review_seq, field, seq in out_of_order:
        print("INFO [requests] the accept at seq %s names %r in %s, which is not a seq recorded "
              "BEFORE it; contract §5.4 subtracts only what a LATER accept disposed of, so this "
              "disposition is disregarded and is itself a tamper signal"
              % (review_seq, seq, field))

    pending = [_seq_of(event) for event in requests if _seq_of(event) not in disposed]
    sealed = _is_sealed(events)
    return gating, True, _flag(
        not (pending and sealed), "requests",
        (f"request(s) {pending} are still pending at a sealed tip with no disposition in any "
         "accept's resolves or withdraws" if pending and sealed
         else f"{len(pending)} request(s) pending since the last generation "
              f"({'sealed' if sealed else 'not sealed'})"))


#: The eight report lines, in output order. Each takes ``(events, root, unit_id)`` and returns
#: ``(gating, ran, ok)``, so whether a line gates is a property of the line ITSELF: there is no
#: second list of gating tags anywhere in this file to drift from the module docstring's, and
#: `validation/fixtures.sh` reads the docstring and these functions separately and compares
#: them. This tuple fixes the ORDER lines are printed in and nothing else.
REPORT_LINES = (
    _line_unsteered,
    _line_edits,
    _line_requests,
    _line_model,
    _line_report,
    _line_context,
    _line_steps,
    _line_sphinx,
)


def audit(unit_id: str, root: Path = ROOT) -> int:
    """The independent oracle over one unit, plus one ``crayon verify`` reading.

    Returns the process exit code and never calls ``sys.exit`` itself, so ``main`` stays the
    single place this program decides how to leave: 0 clean, 1 violation, 2 nothing checked.
    """
    # Resolve the root BEFORE any use: every subsequent path is joined under the
    # resolved value, and the module-level ROOT global is never reassigned.
    root = Path(root).resolve()
    print(f"== independent audit: {unit_id} (root: {root})")

    if not root.is_dir():
        # The vacuous-pass guard: no ledger can be read and `verify` cannot be reached, so
        # reporting 0 or 1 here would both be claims this run is not entitled to make.
        print(f"NOTE [io] root is not a directory: {root}; NOTHING was checked")
        return 2

    if not UNIT_ID_RE.fullmatch(unit_id):
        _flag(False, "io", f"invalid unit id {unit_id!r}; expected {UNIT_ID_RE.pattern}")
        return 1
    ledger_path = _resolved_under(root, f".crayon/units/{unit_id}/ledger.jsonl")
    if ledger_path is None:
        _flag(False, "io", f"ledger path for unit {unit_id!r} leaves audit root {root}")
        return 1
    if not ledger_path.is_file():
        # A missing unit FLAGs by name, exits 1, and returns cleanly rather than raising a
        # traceback at the reader.
        _flag(False, "io", f"no ledger for unit {unit_id}: expected a file at "
                           f"{ledger_path}, found none")
        return 1

    checks_run = 0
    violation = False

    # --- oracle check 1 of 4: chain recompute (contract §5.2) ------------------------
    events, problems = read_ledger(ledger_path)
    checks_run += 1
    if problems:
        message = ("chain recompute FAILED over %s: %s (%d problem(s) in total)"
                   % (ledger_path, problems[0], len(problems)))
    else:
        message = ("chain recomputes clean over %s: seq contiguous from 0 and every prev "
                   "is the sha256 of the previous line's bytes" % ledger_path)
    oracle_1_ok = _flag(not problems, "oracle-1", message)
    violation = violation or not oracle_1_ok
    for extra in problems[1:]:
        print(f"INFO [oracle-1] also: {extra}")

    # --- oracle checks 2, 3 and 4 of 4 -----------------------------------------------
    # A check that could not be read (no signoff yet, no sealed files[] yet) reports SKIP and
    # is NOT counted in `checks_run`: counting it would let a unit with nothing on record but
    # a header report three checks it never performed.
    oracle_2_ran, oracle_2_ok = _oracle_2(events, root, unit_id)
    oracle_3_ran, oracle_3_ok = _oracle_3(events, root, unit_id)
    oracle_4_ran, oracle_4_ok = _oracle_4(events, root, unit_id)
    for ran, ok in ((oracle_2_ran, oracle_2_ok), (oracle_3_ran, oracle_3_ok),
                    (oracle_4_ran, oracle_4_ok)):
        if ran:
            checks_run += 1
            violation = violation or not ok

    # --- the [verify] arm: the ONE point of contact with the tool --------------------
    # List argv, never a shell string, so a retargeted root or a crafted unit id cannot
    # inject arguments. Both streams are captured: `verify` exits 6 on a FAIL
    # among V1-V13 with the full report already flushed to stdout.
    tool = _crayon_executable()
    verify_payload = None
    if tool is None:
        verify_ok = _flag(False, "verify",
                          "no crayon executable to read with: CRAYON unset, "
                          f"{ROOT / 'crayon'} absent, and none on PATH. The tree under audit "
                          "is deliberately not searched")
    else:
        done = subprocess.run(
            [str(tool), "verify", unit_id, "--json"],
            cwd=str(root), capture_output=True, text=True, check=False,
        )
        documents = _json_documents(done.stdout) + _json_documents(done.stderr)
        for document in documents:
            if isinstance(document, dict) and "checks" in document:
                verify_payload = document
                break
        if verify_payload is None:
            # No report at all: the tool refused BEFORE it could build one, which is a
            # different fact from "the report says fail" and has to be reported as one.
            # Name the refusal the tool actually printed — contract §5.7's five-key object,
            # `error` first — rather than only the absence of a report, because the
            # refusal IS the tool's account of the damage and an audit that swallows it
            # leaves its reader with nothing to act on. A damaged ledger is exactly the
            # case where the two readings are most worth comparing.
            refusal = next(
                (document for document in documents
                 if isinstance(document, dict) and "error" in document), None)
            if refusal is not None:
                found = ("refused with %r: %s"
                         % (refusal.get("error"), refusal.get("detail")))
            else:
                streams = (done.stdout + done.stderr).strip()
                found = "printed no JSON object at all: %r" % (streams[:200] or "(nothing)")
            verify_ok = _flag(
                False, "verify",
                "crayon verify produced no report to compare against (exit "
                f"{done.returncode}); expected a JSON document carrying a 'checks' key, "
                f"{found}")
        else:
            verdict = verify_payload.get("verdict")
            rows = [row for row in (verify_payload.get("checks") or [])
                    if isinstance(row, dict)]
            failed = [str(row.get("id")) for row in rows if row.get("status") == "fail"]
            # Green means `verdict != "fail"`, not `verdict == "ok"`: warn- and
            # status-level findings are legitimate on a live repository.
            verify_ok = _flag(
                verdict != "fail", "verify",
                "crayon verify reports verdict %r over %d check(s); failing: %s"
                % (verdict, len(rows), ", ".join(failed) if failed else "none"))
    checks_run += 1
    violation = violation or not verify_ok

    # --- DISAGREE: per-check-pair, over the UNDERLYING FINDING -----------------------
    # Never a comparison of the two exit codes or the two verdicts. Oracle 1 pairs with V3
    # (seq + chain) and, partly, with V2 (lines parse, canonical, within caps); both are
    # level `fail`, so this pair is a true head-to-head. Checks 2 and 3 pair below.
    #
    # The pair's verify-side finding is the CONJUNCTION "V3 (and V2) reported status ok",
    # evaluated once — not one comparison per counterpart. Comparing each counterpart
    # separately manufactures a split on the canonical V-02 tamper, where V3 correctly FAILs
    # and V2 correctly reports ok because the rewritten line still parses and is still
    # canonical: V2 does not read the chain, so "V2 is ok" is not a claim that the chain
    # recomputed. A DISAGREE line on that case would report a conflict where the two
    # readings in fact agree, which is the exact misreading this matrix exists to prevent.
    if verify_payload is not None:
        statuses = {row.get("id"): row.get("status")
                    for row in (verify_payload.get("checks") or [])
                    if isinstance(row, dict)}
        details = {row.get("id"): str(row.get("detail") or "")
                   for row in (verify_payload.get("checks") or [])
                   if isinstance(row, dict)}
        pair = [counterpart for counterpart in ("V3", "V2") if counterpart in statuses]
        if pair:
            split = [counterpart for counterpart in pair if statuses[counterpart] != "ok"]
            verify_finding_ok = not split
            if verify_finding_ok != oracle_1_ok:
                print("DISAGREE [oracle-1 vs %s] oracle %s, verify %s — neither reading is "
                      "authoritative; the split is the finding"
                      % (", ".join(split or pair),
                         "ok" if oracle_1_ok else "flag",
                         "ok" if verify_finding_ok else "flag"))
                violation = True

        # Oracle 2 pairs with V19's `plan_stale` CLAUSE and oracle 3 with V14's `drifted` /
        # `missing` ones — matched in the row's own detail, not on the row's status, because
        # each row reports more than the oracle check looks at (V19 also covers the signoff's
        # recorded source digests; V14 also reports `new`). Both counterparts sit below `fail`
        # level, so `verify` EXITS 0 where the oracle FLAGs: that is a split about severity,
        # and reading the exit code as agreement is exactly what would bless a stale plan hash
        # or a drifted page. Check 4 has no counterpart and deliberately emits nothing — the
        # docstring's matrix is where a reader is told that silence is not agreement.
        for tag, ran, oracle_ok, counterpart, predicate, clauses in (
            ("oracle-2", oracle_2_ran, oracle_2_ok, "V19", _v19_finding_ok, ("plan_stale",)),
            ("oracle-3", oracle_3_ran, oracle_3_ok, "V14", _v14_finding_ok,
             ("drifted", "missing")),
        ):
            if not ran or counterpart not in details:
                continue
            verify_finding_ok = predicate(details[counterpart])
            if verify_finding_ok != oracle_ok:
                print("DISAGREE [%s vs %s] oracle %s, verify %s over %s — neither reading is "
                      "authoritative; the split is the finding"
                      % (tag, counterpart,
                         "ok" if oracle_ok else "flag",
                         "ok" if verify_finding_ok else "flag",
                         "/".join(clauses)))
                violation = True

    # --- the report lines: each one owns whether it gates ----------------------------
    # A line that SKIPped is NOT counted, for the same reason a SKIPping oracle check is not:
    # counting it would let a unit with nothing on record but a header report checks it never
    # performed. These eight used to increment unconditionally, which put the floor at 10
    # and made the guard below unreachable — the code did the one thing the comment above the
    # oracle block says it must not.
    for line in REPORT_LINES:
        gating, line_ran, line_ok = line(events, root, unit_id)
        if line_ran:
            checks_run += 1
            violation = violation or (gating and not line_ok)

    # A violation outranks the vacuous guard: something WAS checked and it did not hold, and
    # reporting that as "nothing was checked" would lose the finding. 2 is reserved for the run
    # that has nothing to say, never for the run that has something bad to say — an empty
    # ledger FLAGs oracle-1 and is a 1.
    if violation:
        return 1
    if checks_run <= ALWAYS_RUN_CHECKS:
        # The vacuous-pass guard, now reachable. Exactly two checks run over ANY readable
        # ledger — the chain recompute, which needs only bytes, and the one `verify` reading,
        # which needs only the tool — so `checks_run` at that floor means nothing with unit
        # EVIDENCE was checked. A ledger holding only its seq-0 header used to exit 0 here with
        # three of the four oracle checks SKIPped, which is the exact shape a retargeted root or
        # a reshaped tree produces and the one outcome the 0/1/2 contract exists to make
        # impossible. The count is named rather than returned silently, because "nothing was
        # checked" is only actionable once a reader knows how much did run.
        print("NOTE [audit] only %d check(s) had evidence to read — the chain recompute and the "
              "one `verify` reading are the %d that run over any readable ledger, so NOTHING "
              "with unit evidence was checked" % (checks_run, ALWAYS_RUN_CHECKS))
        return 2
    return 0


def protocol(directory: Path = ROOT / "validation") -> int:
    """The FOUR conformance checks over one dogfood leg's RUN file.

    Returns the process exit code and never calls ``sys.exit`` itself, so ``main`` stays the
    single place this program decides how to leave:

        0   every check passed
        1   at least one check FLAGged
        2   NOTHING was checked — zero ``RUN-*.json`` under the directory. This is the
            vacuous-pass guard, and it is the reason the exit code can be trusted at all: a
            retargeted directory, a leg that never wrote a RUN file, or a reshaped tree would
            otherwise report exactly what a conformant leg reports.

    Every check reads the RUN file and nothing else, apart from the one ``crayon version
    --json`` reading the third check takes. The four, in this fixed order, each on its own
    line and NONE of them short-circuiting the others — a gate that stops at the first
    violation makes an author fix one thing, re-run, and find the next, and the point of a
    conformance report is to hand back the whole list:

        1 ``[run]``        the RUN file is complete — every key in ``REQUIRED_RUN_KEYS`` and
                           every one of the six ``REQUIRED_METRIC_KEYS`` — and there is exactly
                           ONE RUN file, because ``crayon``'s ``sphinx_result`` takes the first
                           by sorted name and says nothing about a second
        2 ``[transcript]`` ``transcript.sha256`` is present and non-null. ``runmeta.sh end``
                           writes ``null`` BY DESIGN and the AUTHOR fills it from
                           outside the session, so this check is the two-step's second half
                           made enforceable rather than hoped for
        3 ``[compat]``     ``tool.contract`` and ``tool.min_tool`` against ``crayon version
                           --json``, read through the same list-argv subprocess form the
                           ``[verify]`` arm uses. ``min_tool`` is the tool's own ``__version__``,
                           which ``version --json`` reports as ``tool`` — exactly the pairing
                           ``tests/check_docs.py`` already pins README's COMPAT region against,
                           so this is a second reading of ONE source and not a third opinion
        4 ``[context]``    ``context.origins_sha256`` equals ``baseline.origins_sha256``, as
                           exact hex strings, with BOTH named on a difference, and the
                           NUMBER of paths digested named on either outcome. With no origins
                           recorded at all the check SKIPs rather than passing: both sides are
                           then sha256 of the empty list and the comparison asserts nothing,
                           so a run may print three PASS or FLAG lines and one SKIP line

    The RUN file is untracked, unvalidated working-tree input. Invalid JSON, a non-object,
    and a wrong-typed nested value each FLAG naming what was found; a traceback at the reader
    is the outcome these guards exist to prevent. When the contents cannot be read at all,
    every check still prints its line, and each one FLAGs because its evidence is absent.
    """
    directory = Path(directory).resolve()
    print(f"== protocol conformance: {directory}")

    run_files = sorted(directory.glob("RUN-*.json"))
    if not run_files:
        print(f"NOTE [protocol] no RUN-*.json under {directory}; NOTHING was checked")
        return 2

    run_path = run_files[0]
    data = None
    read_problem = None
    try:
        with open(run_path, "r", encoding="utf-8") as handle:
            loaded = json.loads(handle.read())
        if isinstance(loaded, dict):
            data = loaded
        else:
            read_problem = "is a %s, expected a JSON object" % type(loaded).__name__
    except (OSError, ValueError) as problem:
        read_problem = "is not readable JSON (%s)" % problem

    violation = False

    # --- check 1 of 4: the RUN file is complete -------------------------------------------
    problems = []
    if len(run_files) > 1:
        problems.append("%d RUN files are present (%s); crayon's sphinx_result takes %s, the "
                        "first by sorted name, and says nothing about the rest"
                        % (len(run_files), ", ".join(path.name for path in run_files),
                           run_path.name))
    if data is None:
        problems.append("validation/%s %s" % (run_path.name, read_problem))
    else:
        missing = [key for key in REQUIRED_RUN_KEYS if key not in data]
        if missing:
            problems.append("missing key(s): %s" % ", ".join(missing))
        metrics = data.get("metrics")
        if "metrics" in data and not isinstance(metrics, dict):
            problems.append("metrics is %r, expected an object carrying the six session "
                            "measurements" % (metrics,))
        elif isinstance(metrics, dict):
            absent = [key for key in REQUIRED_METRIC_KEYS if key not in metrics]
            if absent:
                problems.append("the metrics object is missing session metric(s): %s"
                                % ", ".join(absent))
    violation |= not _flag(
        not problems, "run",
        "; ".join(problems) if problems
        else "validation/%s carries all %d required keys and all six session metrics"
             % (run_path.name, len(REQUIRED_RUN_KEYS)))

    # --- check 2 of 4: the transcript sha -------------------------------------------------
    transcript = data.get("transcript") if isinstance(data, dict) else None
    if not isinstance(transcript, dict):
        violation |= not _flag(False, "transcript",
                               "no transcript object on the RUN file (found %r); "
                               "`runmeta.sh end` writes the path and a null sha, and the "
                               "author fills the sha from outside the session"
                               % (transcript,))
    else:
        recorded = transcript.get("sha256")
        if recorded is None:
            violation |= not _flag(
                False, "transcript",
                "transcript.sha256 is null: `runmeta.sh end` writes it that way by design, "
                "because a sha taken inside the session being measured is stale the moment "
                "that tool call is appended to it. The author fills it from outside the "
                "session before the RUN file is committed (path: %r)" % (transcript.get("path"),))
        else:
            violation |= not _flag(isinstance(recorded, str) and len(recorded) == 64,
                                   "transcript",
                                   "transcript.sha256 is %r for %r"
                                   % (recorded, transcript.get("path")))

    # --- check 3 of 4: the compatibility numbers ------------------------------------------
    tool_record = data.get("tool") if isinstance(data, dict) else None
    reported = None
    executable = _crayon_executable()
    if executable is not None:
        # List argv, never a shell string, and the same reading the
        # `[verify]` arm takes: one subprocess, parsed with this kit's own json.
        done = subprocess.run([str(executable), "version", "--json"],
                              capture_output=True, text=True, check=False)
        for document in _json_documents(done.stdout) + _json_documents(done.stderr):
            if isinstance(document, dict) and "contract" in document:
                reported = document
                break
    if reported is None:
        violation |= not _flag(False, "compat",
                               "no `crayon version --json` reading to compare against: CRAYON "
                               "unset, %s absent, and none on PATH. The tree the RUN file sits "
                               "in is deliberately not searched" % (ROOT / "crayon.py",))
    elif not isinstance(tool_record, dict):
        violation |= not _flag(False, "compat",
                               "the RUN file records tool as %r, expected an object carrying "
                               "contract and min_tool" % (tool_record,))
    else:
        # `min_tool` is the tool's own __version__, reported as `tool` — the pairing
        # tests/check_docs.py:584-590 pins README's COMPAT region against.
        expected = {"contract": reported.get("contract"), "min_tool": reported.get("tool")}
        splits = ["%s is %r on the RUN file and %r from `crayon version --json`"
                  % (key, tool_record.get(key), value)
                  for key, value in sorted(expected.items())
                  if str(tool_record.get(key)) != str(value)]
        violation |= not _flag(
            not splits, "compat",
            "; ".join(splits) if splits
            else "contract %r and min_tool %r match the tool's own reading"
                 % (expected["contract"], expected["min_tool"]))

    # --- check 4 of 4: context == baseline ------------------------------------------------
    baseline = data.get("baseline") if isinstance(data, dict) else None
    context = data.get("context") if isinstance(data, dict) else None
    baseline_digest = baseline.get("origins_sha256") if isinstance(baseline, dict) else None
    context_digest = context.get("origins_sha256") if isinstance(context, dict) else None
    # `origins[]` reaches a generation only when `draft --report` was used. With none recorded,
    # `runmeta.sh` digests an empty list on BOTH sides and this check compared `e3b0c442…` to
    # `e3b0c442…` and PASSed — text indistinguishable from a real pass, asserting the whole of
    # this check's claim (the sources the leg read did not move under it) over no sources
    # at all. The honest outcome is the third verdict: the EVIDENCE the rule needs is not here.
    # A `_note` does not gate, which is the point — it must not read as a pass either.
    origins = baseline.get("origins") if isinstance(baseline, dict) else None
    if not isinstance(origins, list):
        origins = []
    if not isinstance(baseline_digest, str) or not isinstance(context_digest, str):
        violation |= not _flag(False, "context",
                               "the two origins digests are not both strings: baseline %r, "
                               "context %r" % (baseline_digest, context_digest))
    elif not origins:
        _note("context", "no unit recorded an origins[] (draft --report was not used), so there "
                         "is no source set to digest on either side: both digests are sha256 of "
                         "the empty list and comparing them asserts nothing")
    else:
        repo = directory.resolve().parent
        unreadable = [
            origin for origin in origins
            if not isinstance(origin, str) or not origin or Path(origin).is_absolute()
            or "\n" in origin
            or (path := _resolved_under(repo, origin)) is None
            or not path.is_file()
        ]
        if unreadable:
            violation |= not _flag(
                False, "context",
                "origins[] contains %d path(s) that are not readable repository files "
                "in the working tree: %s; matching digests of absent paths prove nothing"
                % (len(unreadable), ", ".join(repr(path) for path in unreadable)))
        else:
            violation |= not _flag(
                baseline_digest == context_digest, "context",
                "the origins digest over %d path(s) is %r at the baseline and %r in the working tree"
                % (len(origins), baseline_digest, context_digest)
                if baseline_digest != context_digest
                else "the origins digest over %d path(s) is %r on both sides"
                     % (len(origins), baseline_digest))

    return 1 if violation else 0


def main(argv: list[str] | None = None) -> int:
    """Route the two subcommands and report the 0/1/2 exit contract.

    Returns
    -------
    int
        ``0`` clean, ``1`` violation, ``2`` when NOTHING was checked. ``audit`` and
        ``protocol`` are both gates.
    """
    parser = argparse.ArgumentParser(
        prog="score.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    unit = sub.add_parser("audit", help="the independent oracle over one unit (gates)")
    unit.add_argument("unit_id", help="the unit id, as in .crayon/units/<id>/")
    unit.add_argument("--root", type=Path, default=ROOT,
                      help="repository root to audit (default: %(default)s)")

    conformance = sub.add_parser(
        "protocol", help="conformance gate over one dogfood leg's RUN file (gates)")
    conformance.add_argument("dir", nargs="?", type=Path,
                             default=Path(__file__).resolve().parent,
                             help="the directory holding the RUN file (default: %(default)s)")

    args = parser.parse_args(argv)
    if args.command == "audit":
        return audit(args.unit_id, args.root)
    return protocol(args.dir)


if __name__ == "__main__":
    raise SystemExit(main())
