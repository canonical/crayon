#!/usr/bin/env python3
# dogen — the documentation-drafting gate: one file, standard library only.
# Copyright (C) 2026 the dogen authors.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License version 3 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: LGPL-3.0-only
"""dogen — record a documentation unit's human-in-the-loop path and gate its writes.

The normative specification is ``docs/contract.md`` (frozen at git tag
``contract-v1``); every section below cites the contract section it implements.
State is *derived* from ``.dogen/units/<id>/ledger.jsonl`` and never stored.

Exit codes: 0 success, 1 gate refusal, 2 bad input, 3 no-op, 4 evidence
incomplete, 5 busy, 6 ledger/recovery.

Python 3.9 syntax only: no ``match``, no ``X | Y`` outside annotations, no
``dataclass(slots=)``. Standard library only: no third-party import, no venv.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import difflib
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys


# --- constants --------------------------------------------------------------

__version__ = "0.2.0"
CONTRACT = 1
DOCS_ROOT = "docs"

# Contract 5.2 caps. Byte caps are measured in UTF-8 bytes and are inclusive:
# the boundary value passes, one byte more does not.
MAX_LINE_BYTES = 262144
MAX_NOTE_BYTES = 65536
MAX_STEPS_BYTES = 65536
MAX_EXCERPT_BYTES = 4096
MAX_FILES = 64
MAX_ORIGINS = 500

# Contract 5.6 identifier shapes.
_UNIT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_STEP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
_TARGET_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")

_WHITESPACE_RE = re.compile(r"\s+")

# The three escape-sequence forms `scrub_excerpt` removes, compiled once at
# module scope so the ORDER they are applied in is visible at the call site
# rather than buried in an inlined expression. Full sequences are removed
# before bare C0 controls: strip the controls first and only the introducer
# goes, leaving the literal `[1;32m` parameter text in the committed excerpt.
_ESC_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_ESC_CSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_ESC_TWO = re.compile(r"\x1b[@-_]")

# Contract 5.6 unit.md subset: required keys, optional keys, and the flag that
# fixes each one. The subset is deliberately narrower than YAML.
INTENTS = ("tutorial", "how-to", "reference", "explanation")
ACTIONABLE_INTENTS = ("tutorial", "how-to")

# Contract 5.3's step `mode`, both wire values written out. `agent` means the
# skill runs the step and captures the output; `ta` means the author runs it in
# their own environment and hands the output back. The tuple exists because an
# unvalidated pass-through would silently break 5.4's `(text_hash, mode,
# stateful)` prefix comparison and read as a reuse bug several plans later.
STEP_MODES = ("agent", "ta")

# Contract 5.3's four step verdicts.
STEP_VERDICTS = ("pass", "fail", "skipped", "deviated")

# Contract 5.6's evidence-file row, as an ALLOW-list. Every key outside this set
# is refused by name — a deny-list of known digest spellings would miss
# `sha256`, `digest`, `hash` and the rest, and the legacy v1.2 evidence file
# carried two of them. Digests are never typed.
EVIDENCE_KEYS = ("verdict", "exit_code", "mode", "command", "reason")

# The contract caps the step plan in BYTES (5.2) and names no count cap. This
# is the tool's own backstop against a pathological entry count inside that
# byte budget (T-17-22); it is deliberately not presented as a contract cap.
MAX_STEPS = 500
_UNIT_REQUIRED_KEYS = ("title", "intent", "audience", "targets")
_UNIT_LIST_KEYS = ("targets", "sources")
_UNIT_KEY_ORDER = ("title", "intent", "audience", "targets", "sources", "notes")
_UNIT_FLAGS = {
    "title": "--title",
    "intent": "--intent",
    "audience": "--audience",
    "targets": "--target / --also-target",
    "sources": "--source",
    "notes": "--notes",
    "body": "--body-file",
}
# Contract 5.3: twelve kinds, `void` reserved. An unrecognised kind is ignored
# for derivation and warned about once — never an error.
KNOWN_KINDS = (
    "ledger",
    "unit-declared",
    "unit-edited",
    "signoff",
    "steering",
    "steps-planned",
    "step-recorded",
    "generation",
    "reviewer-edit",
    "review",
    "retired",
    "void",
)

_FRONTMATTER_RE = re.compile(r"^---[ \t]*$")
_UNIT_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$")
_UNIT_ITEM_RE = re.compile(r"^  - (.*)$")


# --- output / refusal -------------------------------------------------------

# The six exit codes of contract 5.7, named once.
EXITS = {
    "success": 0,
    "gate": 1,
    "bad_input": 2,
    "noop": 3,
    "evidence": 4,
    "busy": 5,
    "ledger": 6,
}

# ONE table: every reason in ``docs/contract.md``'s reason table mapped to its
# exit code, in the contract's own order so a row-for-row diff stays stable.
# This is phase 18's ``check_docs.py`` observable — a key added here that is not
# in the contract, or a contract row missing here, is a defect in one of the two
# and U-07 fails until they agree.
REASONS = {
    # 1 — gate refusals
    "no_signoff": 1,
    "plan_stale": 1,
    "page_drift": 1,
    "target_exists": 1,
    "target_missing": 1,
    "generation_stale": 1,
    "unapplied_steering": 1,
    "unsteered": 1,
    "no_generation": 1,
    "target_claimed": 1,
    "retired": 1,
    # 2 — bad input
    "bad_target": 2,
    "bad_write_path": 2,
    "bad_draft_path": 2,
    "bad_resolution": 2,
    "unit_invalid": 2,
    "unit_exists": 2,
    "unit_not_found": 2,
    "step_unknown": 2,
    "not_actionable": 2,
    "note_required": 2,
    "git_identity_missing": 2,
    "not_a_repo": 2,
    "legacy_unit": 2,
    # 3 — no-ops
    "identical_draft": 3,
    "already_signed": 3,
    "already_accepted": 3,
    "already_recorded": 3,
    "already_retired": 3,
    "no_edits": 3,
    "noop_unchanged": 3,
    "nothing_to_resume": 3,
    # 4 — evidence
    "steps_unresolved": 4,
    "steps_missing": 4,
    "evidence_stale": 4,
    "evidence_incomplete": 4,
    "evidence_mismatch": 4,
    # 5 — busy
    "busy": 5,
    "git_busy": 5,
    # 6 — ledger / recovery
    "ledger_corrupt": 6,
    "ledger_version_unsupported": 6,
    "unit_id_mismatch": 6,
    "uncommitted_tail": 6,
    "ledger_diverged": 6,
    "resume_ambiguous": 6,
    "recovery_unsupported": 6,
    "adopt_unsupported": 6,
    "internal_error": 6,
}

class Refusal(Exception):
    """One refusal, raised anywhere, printed as one JSON line in exactly one place.

    Deep code raises; ``main`` converts. That is what makes contract 5.7's "one
    JSON line — never zero, never two, never a stack trace" a property of the
    program rather than a habit of each call site.
    """

    def __init__(
        self,
        reason,
        unit="",
        detail="",
        hint="",
        next_token="",
        extra=None,
        report_lines=None,
    ):
        super().__init__(reason)
        self.reason = reason
        self.unit = unit
        self.detail = detail
        self.hint = hint
        self.next_token = next_token
        self.extra = dict(extra or {})
        # Contract 5.8's honest-limit block (D-08) travels WITH the refusal
        # rather than being printed where it is built, for the same reason the
        # refusal itself does: `main` is the one place that knows whether
        # `--json` moved the refusal to stdout. Empty for every other reason.
        self.report_lines = list(report_lines or [])


def refuse(reason, unit="", detail="", hint="", next_token="", as_json=False, extra=None):
    """Print the one refusal line and return its exit code (contract 5.7).

    Key order is the contract's own (``error, unit, detail, hint, next``) so the
    line is diffable; ``--json`` moves it from stderr to stdout and changes
    nothing else. A no-op payload adds its keys (existing ``seq``, ``commit``)
    through ``extra`` — the five keys are always present.
    """
    payload = {
        "error": reason,
        "unit": unit,
        "detail": detail,
        "hint": hint,
        "next": next_token,
    }
    payload.update(extra or {})
    stream = sys.stdout if as_json else sys.stderr
    stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    stream.flush()
    return REASONS[reason]


# VERB-04: the ONE separator between response segments. It is not an em dash
# on purpose — an em dash already appears INSIDE segments (the git diagnostic's
# `committed <sha> — dogen: <subject>`, a state qualifier), so reusing it would
# make the segment boundary unfindable by anything but a human.
SEGMENT = " \u00b7 "


def respond(segments, next_token, as_json=False, payload=None):
    """Print the rev8 §3.3 one-line success response on stdout.

    ONE line, fixed segment order: what changed · where · what remains ·
    ``Next: <token>``. ``segments`` is the list of content segments; the
    routing token is appended as the final segment here, in one place, so no
    verb can forget it or bury it mid-line. An empty segment is dropped —
    callers pass "" for an absent optional segment rather than branching — but
    a verb with nothing remaining is expected to pass an explicit remainder
    segment rather than omit it into ambiguity.

    Git diagnostics and hook warnings go to stderr, so this line stays exactly
    one line and stays machine-readable.
    """
    if isinstance(segments, str):
        segments = [segments]
    parts = [segment for segment in segments if segment]
    message = SEGMENT.join(parts)
    if as_json:
        body = {"ok": True, "message": message, "next": next_token}
        body.update(payload or {})
        sys.stdout.write(json.dumps(body, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(message + SEGMENT + "Next: %s\n" % next_token)
    sys.stdout.flush()
    return EXITS["success"]


def diagnostic(message):
    """One stderr diagnostic — git output, hook warnings, stage-a cleanups."""
    sys.stderr.write(message + "\n")
    sys.stderr.flush()


# --- helpers ----------------------------------------------------------------


def sha256_bytes(data):
    """Return the hex sha256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    """Digest a file: ``None`` when missing, ``""`` when zero-byte, else sha256.

    The three-valued result is the vocabulary ``read_fs()`` hands to ``derive()``
    (D-19): absence and emptiness are distinct facts the contract reasons about
    (a zero-byte target is not an adopted page).
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        return None
    if not data:
        return ""
    return sha256_bytes(data)


def test_hooks_enabled():
    """Are the D-15 fixture hooks armed? (``DOGEN_TEST_HOOKS=1``.)

    ``DOGEN_NOW`` and ``DOGEN_CRASH_AT`` are fixture-only by intent but were
    always live in the shipped executable. A provenance tool whose committed
    audit record takes its timestamps from an environment variable — and which
    can be told to abort between the append and the commit — should require the
    caller to say so out loud, once, rather than reading a stray variable in a
    developer's shell (WR-07). The suites set it in their repo fixtures.
    """
    return os.environ.get("DOGEN_TEST_HOOKS") == "1"


def utc_now():
    """The event's informational ``at``.

    ``DOGEN_NOW`` overrides it verbatim (D-15) so a fixture's ledger bytes — and
    therefore every ``prev`` digest — are reproducible. It is read ONLY under
    ``DOGEN_TEST_HOOKS=1``, so it is inert in the shipped executable rather than
    merely inert by convention.
    """
    if test_hooks_enabled() and "DOGEN_NOW" in os.environ:
        return os.environ["DOGEN_NOW"]
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def collapse_note(note, limit=400):
    """Collapse whitespace runs to single spaces for a commit body, capped."""
    collapsed = _WHITESPACE_RE.sub(" ", note).strip()
    if len(collapsed) > limit:
        return collapsed[: limit - 1] + "…"
    return collapsed


def clean_text(text, cap=MAX_NOTE_BYTES):
    """Sanitise author free text for the ledger (contract 5.6 note rule).

    ``\\r`` is refused outright; C0 controls other than ``\\n`` and ``\\t`` are
    stripped; empty or whitespace-only input is refused; and the cap is measured
    on the UTF-8 bytes *after* stripping, inclusively.

    ``|`` and newlines are ordinary characters here and round-trip verbatim as
    JSON escapes — the stated behaviour change from ``slim@357c513``, whose
    pipe-delimited ledger had to refuse them to keep its rows parseable. This is
    input hygiene, not a gate: it raises a plain exception and selects no reason
    code and no exit code.
    """
    if "\r" in text:
        raise ValueError("carriage return is refused; use a newline")
    cleaned = "".join(c for c in text if c in ("\n", "\t") or ord(c) >= 32)
    if not cleaned.strip():
        raise ValueError("text is empty or whitespace only")
    return check_byte_cap("text", cleaned, cap)


def byte_len(text):
    """Length of ``text`` in UTF-8 bytes — the unit every cap is measured in."""
    return len(text.encode("utf-8"))


def check_byte_cap(name, text, limit):
    """Return ``text`` when it fits ``limit`` UTF-8 bytes; the cap is inclusive.

    Measuring bytes rather than characters is load-bearing: a note of 65536
    two-byte characters is 128 KiB on disk and exceeds the 64 KiB note cap.
    """
    size = byte_len(text)
    if size > limit:
        raise ValueError("%s exceeds its cap: %d > %d bytes" % (name, size, limit))
    return text


def check_count_cap(name, items, limit):
    """Return ``items`` when it holds at most ``limit`` elements (inclusive)."""
    count = len(items)
    if count > limit:
        raise ValueError("%s exceeds its cap: %d > %d items" % (name, count, limit))
    return items


def step_text_hash(text):
    """Contract 5.3's ``text_hash``: sha256 over the step text's UTF-8 bytes.

    The TOOL computes it — a hash typed into a step plan would be a claim the
    record cannot corroborate. Prefix equality in contract 5.4 is byte equality
    of this digest, so nothing here normalises, case-folds or collapses
    whitespace: ``a b`` and ``a  b`` are different steps because they are
    different instructions.
    """
    return sha256_bytes(text.encode("utf-8"))


def scrub_excerpt(raw):
    """``(sha256 of the raw bytes, the committed excerpt)`` — D-02, LEDG-06.

    Captured output is NOT author free text: :func:`clean_text` refuses a
    carriage return, so a progress bar or a CRLF line ending would be turned
    away for the wrong reason. This is the separate transform, applied ONCE, at
    the cut. Four orderings are the contract, each one load-bearing:

    1. **The digest is taken first, over the raw full bytes, before any decode.**
       Decoding with the replacement handler is lossy, so a digest over the
       replaced text could not be reproduced from the file it describes.
    2. **Then decode**, replacing what is not valid UTF-8: an excerpt is text on
       the record and a capture is not guaranteed to be text.
    3. **Full escape sequences go before bare control characters.** Dropping C0
       first removes only the ``ESC`` and leaves ``[1;32m`` behind as literal
       text in something committed to git.
    4. **The marker is measured and subtracted before the slice.** Cutting at
       the full cap and appending the marker afterwards produces an excerpt the
       4096-byte cap then rejects — a fault that appears only above 4 KiB.

    The only claim this function makes is that control characters are stripped.
    It does not remove credentials and does not inspect the payload for them;
    D-02 weighed credential-shape removal for v2.0 and decided against it, so
    whatever the command printed is what reaches the ledger.
    """
    digest = sha256_bytes(raw)
    text = raw.decode("utf-8", "replace")
    for pattern in (_ESC_OSC, _ESC_CSI, _ESC_TWO):
        text = pattern.sub("", text)
    text = "".join(c for c in text if c in ("\n", "\t") or ord(c) >= 32)
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_EXCERPT_BYTES:
        return digest, check_byte_cap("excerpt", text, MAX_EXCERPT_BYTES)
    # The marker names the RAW byte count — the only figure the digest
    # corroborates. The stripped length would describe neither the file nor
    # the digest.
    marker = "\n… (%d bytes total)" % len(raw)
    budget = MAX_EXCERPT_BYTES - byte_len(marker)
    # ``ignore`` rather than ``replace``: a multi-byte character straddling the
    # cut is DROPPED, not turned into a replacement character that would claim
    # the capture held one.
    cut = encoded[:budget].decode("utf-8", "ignore")
    return digest, check_byte_cap("excerpt", cut + marker, MAX_EXCERPT_BYTES)


# --- validation / containment -----------------------------------------------


def validate_unit_id(unit):
    """Contract 5.6: ``^[a-z0-9][a-z0-9-]{0,63}$``.

    The reason table names no dedicated code for a malformed identifier, so the
    ``bad_*`` input family's ``bad_target`` carries it; inventing a code would
    put a key in ``REASONS`` that the contract does not have (GATE-04).
    """
    if not isinstance(unit, str) or not _UNIT_ID_RE.match(unit):
        raise Refusal(
            "bad_target",
            unit=unit if isinstance(unit, str) else "",
            detail="unit id does not match %s" % _UNIT_ID_RE.pattern,
            hint="use 1–64 characters: lower-case letters, digits and hyphens",
        )
    return unit


def validate_step_id(step_id, unit=""):
    """Contract 5.6: ``^[a-z0-9][a-z0-9._-]{0,31}$`` (uniqueness is the plan's)."""
    if not isinstance(step_id, str) or not _STEP_ID_RE.match(step_id):
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="step id does not match %s" % _STEP_ID_RE.pattern,
            hint="use 1–32 characters: lower-case letters, digits, '.', '_' and '-'",
        )
    return step_id


def validate_note(text, unit="", field="note", cap=MAX_NOTE_BYTES):
    """Contract 5.6's note/reason rule, as ONE stage-b entry point.

    ``clean_text`` (plan 16-02) is gate-free input hygiene: it raises a plain
    ``ValueError`` and selects neither a reason nor an exit code. This wrapper
    is the single place that choice is made, so every free-text field refuses
    identically and no call site invents its own mapping.

    The reason table names no ``bad_note``, so the note family's own code —
    ``note_required`` — carries "this note is unusable" and the detail says
    exactly why. Inventing a code would put a key in ``REASONS`` the contract
    does not have, which U-07 and phase 18's ``check_docs.py`` both read as
    drift (16-03's rule, applied again).
    """
    if not isinstance(text, str):
        text = ""
    try:
        return clean_text(text, cap)
    except ValueError as bad:
        raise Refusal(
            "note_required",
            unit=unit,
            detail="%s: %s" % (field, bad),
            hint="a %s is non-empty UTF-8, free of carriage returns, at most %d bytes"
            % (field, cap),
        )


def validate_model(model, origin, unit=""):
    """Contract 5.6's model rule: one line of ≤ 128; ``""`` iff origin unknown.

    The "iff" binds in BOTH directions — an empty model with a known origin and
    a named model with an origin of ``unknown`` are each a contradiction
    between the two fields, and ``verify``'s V11 cross-check would report the
    pair as inconsistent long after the generation that recorded them.
    """
    if not isinstance(model, str):
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="the model is not a string",
            hint="pass --model as text, or omit it with --model-origin unknown",
        )
    if "\n" in model or "\r" in model:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="the model must be a single line",
            hint="record one model identifier, not a block of text",
        )
    if len(model) > 128:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="the model is %d characters; the cap is 128" % len(model),
            hint="record the model identifier, not its description",
        )
    if model == "" and origin != "unknown":
        raise Refusal(
            "bad_target",
            unit=unit,
            detail='an empty model needs model_origin "unknown" (origin is %r)' % origin,
            hint='pass a model, or --model-origin unknown',
        )
    if model != "" and origin == "unknown":
        raise Refusal(
            "bad_target",
            unit=unit,
            detail='model_origin "unknown" needs an empty model (model is %r)' % model,
            hint="name the origin of the model you are recording",
        )
    return model


def validate_target(target, unit=""):
    """Contract 5.6's target rule, in stage b, before containment ever runs.

    Every violation is ``bad_target`` except the leading ``docs/`` trap, which
    reports ``bad_write_path``: a docs-relative ``docs/x.rst`` would be written
    to ``docs/docs/x.rst``, so the author's error is about *where* the bytes
    would land. Catching it here is what keeps containment from ever being asked
    about the ``docs/docs/`` path.
    """
    if not isinstance(target, str) or not target:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="an empty target",
            hint="pass a docs-relative path such as reference/page.rst",
        )
    if "\\" in target:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="target %r contains a backslash; paths are POSIX" % target,
            hint="use '/' separators",
        )
    if target.startswith("/") or os.path.isabs(target):
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="target %r is absolute; targets are docs-relative" % target,
            hint="drop the leading '/'",
        )
    if not _TARGET_RE.match(target):
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="target %r does not match %s" % (target, _TARGET_RE.pattern),
            hint="use letters, digits, '.', '_', '-' and '/', 1–200 characters",
        )
    for segment in target.split("/"):
        if segment in ("", ".", ".."):
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="target %r has an empty, '.' or '..' segment" % target,
                hint="write a plain relative path with no traversal",
            )
    if target == DOCS_ROOT or target.startswith(DOCS_ROOT + "/"):
        raise Refusal(
            "bad_write_path",
            unit=unit,
            detail="target %r starts with '%s/'; targets are relative to the docs root"
            % (target, DOCS_ROOT),
            hint="drop the leading '%s/' — write reference/page.rst" % DOCS_ROOT,
        )
    if not (target.endswith(".md") or target.endswith(".rst")):
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="target %r is neither .md nor rst" % target,
            hint="Sphinx pages are .md (MyST) or .rst",
        )
    return target


def validate_source(source, unit=""):
    """A ``sources:`` entry is a repo-relative POSIX path (WR-01).

    The contract states no source rule, so this is not its rule being enforced:
    it is the containment mechanism reaching the one READ path that RECORDS what
    it read. ``sign_sources`` digests every source into the signoff's ``context``
    map, which is committed — so an absolute or traversing source turns a
    provenance record into an existence-and-content oracle for a file outside
    the repository (``~/.ssh/id_rsa``, a co-worker's checkout), and makes V19
    ("context digests vs signoff") a check over paths that are not part of the
    repository at all. ``unit_invalid``/``--source`` because a source is
    frontmatter, and contract 5.6 names that flag for every sources deviation.
    """
    bad = None
    if "\\" in source:
        bad = "contains a backslash; paths are POSIX"
    elif source.startswith("/") or os.path.isabs(source):
        bad = "is absolute; sources are repo-relative"
    else:
        for segment in source.split("/"):
            if segment in ("", ".", ".."):
                bad = "has an empty, '.' or '..' segment"
                break
    if bad is not None:
        raise Refusal(
            "unit_invalid",
            unit=unit,
            detail="source %r %s" % (source, bad),
            hint="pass %s a repo-relative path such as workshop/schema.json"
            % _UNIT_FLAGS["sources"],
        )
    return source


def validate_sources(sources, unit=""):
    """Every source, in order, through :func:`validate_source`."""
    return [validate_source(source, unit) for source in sources]


def validate_targets(targets, unit=""):
    """Every target, in order, with no duplicates (contract 5.6)."""
    seen = []
    for target in targets:
        validate_target(target, unit)
        if target in seen:
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="target %r is listed twice" % target,
                hint="each target appears once",
            )
        seen.append(target)
    if not seen:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="no target",
            hint="a unit declares at least one --target",
        )
    return check_count_cap("targets", seen, MAX_FILES)


def contained(root, candidate):
    """Is ``candidate`` inside ``root`` once both are fully resolved?

    ``realpath`` resolves a symlinked *parent* even when the leaf does not exist,
    so a not-yet-created page under a symlinked docs root is caught before it is
    written. The comparison is separator-aware on purpose: a bare ``startswith``
    would accept ``/repo/docs-other`` as inside ``/repo/docs``, and a
    ``".." in path`` string check would accept a symlink that never spells
    ``..`` at all (audit defect 3). Byte paths are compared as-is — neither
    case-folded nor Unicode-normalized, so ``Docs/`` is not ``docs/`` on a
    case-sensitive filesystem.
    """
    if not root or not candidate:
        return False
    resolved_root = os.path.realpath(os.fspath(root))
    resolved = os.path.realpath(os.fspath(candidate))
    return resolved == resolved_root or resolved.startswith(resolved_root + os.sep)


# --- frontmatter subset -----------------------------------------------------


class UnitInvalid(Exception):
    """A ``unit.md`` that deviates from the contract 5.6 subset.

    Carries the structured payload only: ``line`` (1-based, counted from the
    file's first line), ``key``, and the ``flag`` that fixes it. Mapping this to
    exit 2 and a one-line JSON refusal is gate code and waits for the
    ``contract-v1`` tag (D-06).
    """

    def __init__(self, detail, line, key=None, flag=None):
        super().__init__("line %d: %s" % (line, detail))
        self.detail = detail
        self.line = line
        self.key = key
        self.flag = flag


def _parse_unit_scalar(raw, line, key):
    """Parse one contract 5.6 scalar: a JSON string, or restricted bare text."""
    flag = _UNIT_FLAGS.get(key)
    text = raw.strip()
    if text.startswith('"'):
        try:
            value = json.loads(text)
        except ValueError:
            raise UnitInvalid("not a JSON double-quoted string", line, key, flag)
        if not isinstance(value, str):
            raise UnitInvalid("not a string", line, key, flag)
        return value
    if not text:
        raise UnitInvalid(
            'empty value; write "" to mean an empty string', line, key, flag
        )
    if text[0] in "'[{":
        raise UnitInvalid(
            "a bare scalar may not start with %r" % text[0], line, key, flag
        )
    if "#" in text:
        raise UnitInvalid("a bare scalar may not contain '#'", line, key, flag)
    if ": " in text:
        raise UnitInvalid("a bare scalar may not contain ': '", line, key, flag)
    return text


def parse_unit_md(text):
    """Parse a ``unit.md`` into ``(frontmatter, body)`` per contract 5.6.

    Deliberately not YAML and deliberately hand-written: the subset is narrower
    than YAML on purpose, and a real parser would accept inputs the contract has
    to refuse. Every deviation raises :class:`UnitInvalid` naming the 1-based
    line and the flag that fixes it.
    """
    lines = text.split("\n")
    if not _FRONTMATTER_RE.match(lines[0]):
        raise UnitInvalid(
            "no frontmatter block: the first line must be '---'", 1, "frontmatter"
        )
    close = None
    for index in range(1, len(lines)):
        if _FRONTMATTER_RE.match(lines[index]):
            close = index
            break
    if close is None:
        raise UnitInvalid(
            "the frontmatter block is never closed by '---'",
            len(lines),
            "frontmatter",
        )

    frontmatter = {}
    key_lines = {}
    current = None
    for index in range(1, close):
        line = lines[index]
        number = index + 1
        if not line.strip():
            continue
        item = _UNIT_ITEM_RE.match(line)
        if item is not None:
            # A list item binds to the nearest preceding key line and never
            # merges into the key above it.
            if current is None:
                raise UnitInvalid("a list item with no preceding key", number)
            if current not in _UNIT_LIST_KEYS:
                raise UnitInvalid(
                    "%s takes a scalar, not a list item" % current,
                    number,
                    current,
                    _UNIT_FLAGS.get(current),
                )
            frontmatter[current].append(
                _parse_unit_scalar(item.group(1), number, current)
            )
            continue
        match = _UNIT_KEY_RE.match(line)
        if match is None:
            raise UnitInvalid(
                "neither a 'key:' line nor a '  - <scalar>' item", number
            )
        key = match.group(1)
        raw = match.group(2)
        flag = _UNIT_FLAGS.get(key)
        if key not in _UNIT_KEY_ORDER:
            raise UnitInvalid("unknown key %r" % key, number, key)
        if key in frontmatter:
            raise UnitInvalid("duplicate key %r" % key, number, key, flag)
        key_lines[key] = number
        if key in _UNIT_LIST_KEYS:
            if raw.strip():
                raise UnitInvalid(
                    "%s is a list: write '  - <scalar>' items below it" % key,
                    number,
                    key,
                    flag,
                )
            frontmatter[key] = []
        else:
            frontmatter[key] = _parse_unit_scalar(raw, number, key)
            if key == "intent" and frontmatter[key] not in INTENTS:
                raise UnitInvalid(
                    "intent must be one of %s" % ", ".join(INTENTS), number, key, flag
                )
        current = key

    closing_line = close + 1
    for key in _UNIT_REQUIRED_KEYS:
        if key not in frontmatter:
            raise UnitInvalid(
                "required key %r is missing" % key,
                closing_line,
                key,
                _UNIT_FLAGS.get(key),
            )
    if not frontmatter["targets"]:
        raise UnitInvalid(
            "targets needs at least one '  - <scalar>' item",
            key_lines["targets"],
            "targets",
            _UNIT_FLAGS["targets"],
        )

    return frontmatter, "\n".join(lines[close + 1 :])


def render_unit_md(frontmatter, body=""):
    """Write the contract 5.6 shape back; the tool always writes this shape.

    Key order is the contract's own; ``targets`` order is preserved verbatim
    because it is the order a generation's ``files[]`` is written in.
    """
    out = ["---"]
    for key in _UNIT_KEY_ORDER:
        if key not in frontmatter:
            continue
        value = frontmatter[key]
        if key in _UNIT_LIST_KEYS:
            out.append("%s:" % key)
            for entry in value:
                out.append("  - %s" % json.dumps(entry, ensure_ascii=False))
        else:
            out.append("%s: %s" % (key, json.dumps(value, ensure_ascii=False)))
    out.append("---")
    return "\n".join(out) + "\n" + body


# --- ledger I/O + chain -----------------------------------------------------


def _assert_no_floats(value, path="$"):
    """Raise when any ``float`` appears anywhere in ``value``.

    ``allow_nan=False`` bans only nan and inf; a *finite* float still serializes
    (RESEARCH P-6), and float repr is platform-sensitive, so one would break byte
    stability and with it every ``prev`` digest in the chain.
    """
    if isinstance(value, float):
        raise ValueError("float at %s: the ledger carries no floats" % path)
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_floats(item, "%s.%s" % (path, key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_floats(item, "%s[%d]" % (path, index))


def canonical_line(event):
    """Serialize one event to its canonical line (contract 5.2), no trailing LF.

    The contract names this exact ``json.dumps`` call. Any variant — a custom
    serializer, a key sorter, an RFC 8785 canonicalizer — changes the bytes and
    therefore breaks every chain digest, so it is written out literally here.
    """
    _assert_no_floats(event)
    # Kept on one line so the call can be grepped against the contract verbatim.
    line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return check_byte_cap("line", line, MAX_LINE_BYTES)


def chain_prev(prev_line_text):
    """``prev`` for the next line: sha256 of these exact bytes, LF excluded."""
    return sha256_bytes(prev_line_text.encode("utf-8"))


def verify_chain(lines):
    """Return every chain problem in ``lines``; an empty list means valid.

    Contract 5.2: ``seq`` contiguous from 0, ``prev`` of line n equal to the
    sha256 of line n-1's exact bytes, ``prev`` null at seq 0. A zero-line ledger
    is valid — zero events, not an error.
    """
    problems = []
    previous = None
    for index, line in enumerate(lines):
        number = index + 1
        try:
            event = json.loads(line)
        except ValueError as exc:
            problems.append("line %d: not valid JSON (%s)" % (number, exc))
            previous = line
            continue
        if not isinstance(event, dict):
            problems.append("line %d: not a JSON object" % number)
            previous = line
            continue
        if event.get("seq") != index:
            problems.append(
                "line %d: seq is %r, expected %d" % (number, event.get("seq"), index)
            )
        expected = None if previous is None else chain_prev(previous)
        if event.get("prev") != expected:
            problems.append(
                "line %d: prev is %r, expected %r"
                % (number, event.get("prev"), expected)
            )
        previous = line
    return problems


def ledger_label(path):
    """A ledger path spelled from the repository root, never absolutely.

    Every other refusal in this file names the ledger repo-relative
    (``os.path.relpath(path, root)`` in :func:`classify_stage_a`); the two
    raised from :func:`read_events` embedded the ABSOLUTE path, leaking the
    caller's filesystem layout into a diagnostic a skill is invited to paste
    into an issue or a commit message (WR-10).

    Derived from the path's own shape rather than from a ``repo`` argument
    threaded through eight call sites: a ledger always lives at
    ``<root>/.dogen/units/<id>/ledger.jsonl``, and a unit id can never be
    ``.dogen`` (``_UNIT_ID_RE``), so the LAST ``.dogen`` component is the
    repository's own even when the root itself sits under one.
    """
    parts = os.path.normpath(os.fspath(path)).split(os.sep)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == ".dogen":
            return os.path.join(*parts[index:])
    return os.path.basename(os.fspath(path))


def undecodable_ledger(path, unit=""):
    """The one ``ledger_corrupt`` for a ledger whose bytes are not UTF-8.

    Stated ONCE because three readers can meet it — :func:`read_events`,
    :func:`_read_text` and, through them, every verb — and a second opinion
    about the same fault is how it came to have three different answers.

    WR-04 widened the three helpers that read AUTHOR input and stopped there.
    The readers of the RECORD still opened with ``encoding="utf-8"`` and caught
    nothing, so the identical fault on the identical codec escaped as a bare
    ``UnicodeDecodeError`` into ``main``'s generic ``ValueError`` arm and came
    back as ``bad_target`` (2, "bad input" — the code a skill reads as "I
    mistyped an argument") with the decoder's message in ``detail`` and an
    EMPTY ``hint``. The truth is that the hash-chained record of truth is
    unreadable, whose contract reason is ``ledger_corrupt`` (6) with
    ``next: resume`` (WR-09).
    """
    relative = ledger_label(path)
    return Refusal(
        "ledger_corrupt",
        unit=unit,
        detail="%s is not UTF-8 text" % relative,
        hint="inspect %s; the ledger is UTF-8 JSONL and nothing may be appended "
        "until it is" % relative,
        next_token="resume",
    )


def unreadable_ledger(path, unit=""):
    """The one ``ledger_corrupt`` for a ledger path that is not a readable file.

    WR-20: WR-09 turned on the principle "absent and undecodable are NOT the
    same answer" and left the THIRD case split between the two readers of the
    same file. :func:`_read_text` mapped ``IsADirectoryError``/
    ``NotADirectoryError`` to ``""`` -- *absent*, derive state from nothing,
    the silent wrong answer its own docstring exists to prevent -- while
    :func:`read_events` caught neither, so the ``OSError`` escaped to ``main``
    and ``dogen show`` reported ``ledger_diverged`` ("the committed record was
    rewritten") about a record that is a directory. Stated ONCE, the way
    :func:`undecodable_ledger` is, because a second opinion about the same
    fault is how the first one came to have three different answers.
    """
    relative = ledger_label(path)
    return Refusal(
        "ledger_corrupt",
        unit=unit,
        detail="%s is not a readable file" % relative,
        hint="inspect %s; the ledger is a UTF-8 JSONL file and nothing may be "
        "appended until it is" % relative,
        next_token="resume",
    )


def read_events(path, unit=""):
    """Return ``[(event, raw_line), ...]`` for a ledger.

    ``[]`` for a missing or zero-byte file — an empty ledger is not an error.
    The raw line text is returned beside each event because the chain hashes
    bytes, not the re-serialized object.

    A line that is not valid JSON raises ``ledger_corrupt`` (6), which is the
    contract's code for it and the mechanism table's promise ("a corrupted line
    refuses loudly instead of silently deriving the wrong state"). A bare
    ``ValueError`` used to escape here and be converted by ``main`` into
    ``bad_target``/2 with a JSON-decoder message in ``detail`` — "bad input" for
    a damaged record — and it is what made WR-04's silent claim-policy bypass
    possible to write by accident (WR-10).
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        return []
    except (IsADirectoryError, NotADirectoryError):
        raise unreadable_ledger(path, unit)
    except UnicodeDecodeError:
        raise undecodable_ledger(path, unit)
    records = []
    number = 0
    for line in text.split("\n"):
        if not line:
            continue
        number += 1
        try:
            event = json.loads(line)
        except ValueError as bad:
            raise Refusal(
                "ledger_corrupt",
                unit=unit,
                detail="line %d: %s" % (number, bad),
                hint="inspect %s; the record is damaged and nothing may be appended"
                % ledger_label(path),
                next_token="resume",
            )
        records.append((event, line))
    return records


def append_batch(path, lines):
    """Append a batch with ONE ``write()`` of every line, then flush and fsync.

    The single write is what makes contract 5.8's "the tail is an exact byte
    prefix of the batch (at most one truncated final line)" classification
    decidable: an interruption can only truncate inside this one call. A
    zero-event batch is never appended; the smallest batch is one event.
    """
    if not lines:
        raise ValueError("an event batch holds at least one event")
    payload = "".join(line + "\n" for line in lines)
    directory = os.path.dirname(os.fspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return len(lines)


def ledger_path(repo, unit):
    """A unit's ledger path: ``<repo>/.dogen/units/<id>/ledger.jsonl``."""
    return os.path.join(os.fspath(repo), ".dogen", "units", unit, "ledger.jsonl")


# --- derive + routing -------------------------------------------------------
# Routing (`route()`) is a rendering of the per-verb preconditions and waits for
# the `contract-v1` tag (D-06). Only the derivation half lives here.


def contained_page(repo, unit, path):
    """The absolute path of a RECORDED docs page, or a refusal (CR-04, CR-05).

    Every WRITE path runs ``validate_target`` -- which refuses ``..`` segments,
    absolute paths and backslashes -- and ``contained()``: ``guard_targets``,
    ``guard_write_paths``, ``guard_placeable_paths``. Every READ path ran
    NEITHER. ``read_fs`` and ``read_page_bytes`` took the path straight out of
    the ledger's ``signoff.targets`` / ``basis.files[].path`` and joined it onto
    the repo root.

    ``.dogen/`` is committed, so that path is ordinary contributor input. An
    untrusted branch or PR carrying a forged ``.dogen/units/x/ledger.jsonl``
    made the REVIEWER's own ``dogen show x --diff`` print the contents of an
    arbitrary host file, ``show --json`` return its sha256 in
    ``paths[].current_sha``, and ``summary --md`` -- documented as paste-ready
    PR text -- publish what was derived from it.

    That is ``validate_source``'s own argument ("turns a provenance record into
    an existence-and-content oracle for a file outside the repository
    (``~/.ssh/id_rsa``, a co-worker's checkout)") applied to the DERIVED path as
    well as to the declared one: the rule was written for the input and not for
    what the record says about it.

    ``ledger_corrupt`` (6), not ``bad_target`` (2): nothing the caller typed is
    wrong. The RECORD names a page dogen was never allowed to write, so the
    honest reading is that the record is damaged, and ``resume`` is the route.
    """
    root = os.fspath(repo)
    docs_root = os.path.join(root, DOCS_ROOT)
    if not contained(root, docs_root):
        # CR-05: `guard_targets`' companion check (dogen:2711), restated for the
        # READ surface. Containing a recorded page WITHIN `docs` is tautological
        # when `docs` itself is a symlink out of the repository: a git tree can
        # carry `docs` as mode 120000, so the same untrusted branch that carries
        # the forged `.dogen/units/x/ledger.jsonl` carries the link that makes
        # its targets resolve. Both are ordinary committed blobs.
        #
        # `bad_write_path` (2), not `ledger_corrupt` (6): this is a fact about
        # the WORKING TREE, not about the record, and it is the very reason code
        # and wording the write surface already gives this exact condition. It
        # also keeps CR-06's cascade shut -- `find_claim` may fall through a
        # disk-shaped refusal, and must not turn one repo-wide layout fault into
        # "unit <sibling>'s record is damaged".
        raise Refusal(
            "bad_write_path",
            unit=unit,
            detail="the docs root resolves outside the repository",
            hint="%s/ must be a real directory inside the repository" % DOCS_ROOT,
            # No `next`, exactly as `guard_targets` raises it: no verb can undo
            # a symlinked docs root, and naming one would be the closed loop
            # CR-06 is filed for ("the recovery the hint names refuses
            # identically"). The hint is the whole instruction.
        )
    if not isinstance(path, str) or not path:
        raise Refusal(
            "ledger_corrupt",
            unit=unit,
            detail="a recorded path is not a non-empty string (%r)" % (path,),
            hint="inspect %s; the record is damaged"
            % ledger_label(ledger_path(repo, unit)),
            next_token="resume",
        )
    full = os.path.join(docs_root, path)
    # CR-06: the record-shaped fault and the disk-shaped one are DIFFERENT
    # conditions and they are distinguishable with one lexical test. Answering
    # both with `contained()` -- which resolves the leaf with `realpath`, so it
    # answers a question about the file on disk -- reported a working-tree
    # symlink as "the record names a page outside the docs root ... inspect the
    # ledger ... next: resume". Every clause of that was false, and the one fact
    # the author needed (the page is a link) appeared nowhere.
    lexical = os.path.normpath(full)
    normal_root = os.path.normpath(docs_root)
    if not (lexical == normal_root or lexical.startswith(normal_root + os.sep)):
        # The RECORD names an escaping path (`..`, an absolute path). Nothing on
        # disk is consulted to know that, so the ledger really is damaged.
        raise Refusal(
            "ledger_corrupt",
            unit=unit,
            detail="recorded path %r resolves outside %s/" % (path, DOCS_ROOT),
            hint="inspect %s; the record names a page outside the docs root"
            % ledger_label(ledger_path(repo, unit)),
            next_token="resume",
        )
    if not contained(docs_root, full):
        # The record is fine; the WORKING TREE puts the page outside the docs
        # root. Symlinked pages under `docs/` are an ordinary docs-repo pattern
        # (a shared CHANGELOG.rst, a `docs/api -> ../src/api-docs` Sphinx tree),
        # so this must name the link and must NOT tell the author their
        # hash-chained record is damaged. Same reason code the write surface
        # gives this exact condition (`guard_targets`).
        raise Refusal(
            "bad_write_path",
            unit=unit,
            detail="%s/%s is a link that resolves outside %s/"
            % (DOCS_ROOT, path, DOCS_ROOT),
            hint="replace the link with a real file under %s/, or drop the "
            "target from the signoff" % DOCS_ROOT,
            # No `next`, for CR-06's own reason: `show` on this unit reaches
            # this same snapshot and refuses identically, so naming it would be
            # the closed loop the finding is about. The fix is in the working
            # tree, and the hint is the whole instruction.
        )
    return full


def read_fs(repo, unit, basis_paths=(), targets=()):
    """One immutable filesystem snapshot — the only channel into ``derive()``.

    Returns exactly ``{"unit_md_sha": sha256 of the whole unit.md or None,
    "paths": {docs-relative path: sha256 | None (missing) | "" (zero-byte)}}``
    covering every basis path and every signed target, and nothing else (D-19).

    ``.git/index.lock`` is deliberately absent: that is a stage-a liveness probe
    which must be read immediately before the git call rather than once per
    invocation, and carrying it here would put a field in the snapshot that
    ``derive()`` never reads.

    Every verb takes one snapshot per invocation, so gates, no-op recognition
    and ``show`` all reason over the same instant. The residual window between
    the snapshot and the write is documented, not claimed away.
    """
    root = os.fspath(repo)
    unit_md = os.path.join(root, ".dogen", "units", unit, "unit.md")
    paths = {}
    for path in list(basis_paths) + list(targets):
        # CR-04 / CR-05: the snapshot is where a recorded path first becomes a
        # filesystem access, so it is where the shape and the containment are
        # checked -- once, for every verb, before a single byte is digested.
        full = contained_page(repo, unit, path)
        if path not in paths:
            paths[path] = sha256_file(full)
    return {"unit_md_sha": sha256_file(unit_md), "paths": paths}


def _is_h_event(event):
    """H = {steering, review fix|redraft, signoff} (contract 5.4)."""
    kind = event.get("kind")
    if kind == "steering" or kind == "signoff":
        return True
    return kind == "review" and event.get("verdict") in ("fix", "redraft")


def _last_of(events, kind):
    """The last event of ``kind`` in seq order, or ``None``."""
    found = None
    for event in events:
        if event.get("kind") == kind:
            found = event
    return found


def _later(first, second):
    """The later of two events by seq; either may be ``None``."""
    if first is None:
        return second
    if second is None:
        return first
    if second.get("seq", -1) > first.get("seq", -1):
        return second
    return first


def _h_after(events, event):
    """``h_after(x)``: does any H event carry a strictly greater seq?"""
    if event is None:
        return False
    seq = event.get("seq")
    for candidate in events:
        if _is_h_event(candidate) and candidate.get("seq") > seq:
            return True
    return False


def _basis_pairs(basis):
    """``[(path, sha256)]`` of a basis event, in the order it recorded them."""
    if basis is None:
        return []
    return [(entry.get("path"), entry.get("sha256")) for entry in basis.get("files") or []]


def _is_seq(value):
    """A ledger ``seq``: an integer that is NOT a ``bool`` (phase-16 IN-06).

    ``isinstance(True, int)`` is true in Python, so a hand-repaired, forged or
    future-tool-written record spelling ``"resolves": [true]`` had ``True``
    compare equal to seq 1 and close a steering request the reviewer never
    resolved. ``verify_chain`` checks seq contiguity and ``prev`` digests and
    nothing beneath them, so this is the only thing standing between that
    payload and the disposition rule. Stated ONCE, because five readers of the
    same two fields must not each decide separately what a seq is.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def pending_requests(events, floor):
    """Contract 5.4's ``pending``: the H events above ``floor`` nothing disposed.

    ONE implementation, because two readers need it at two different instants:
    :func:`derive` asks for the set as it stands NOW (floor = the last
    generation), and ``verify``'s V10 asks for the set as it stood at each
    historical accept. A second walk of the same rule is how the gate that
    refuses `unapplied_steering` and the report that verifies it come to hold
    different opinions of one record.
    """
    resolved = set()
    for event in events:
        if event.get("kind") != "review" or event.get("verdict") != "accept":
            continue
        accept_seq = event.get("seq")
        # CR-04: `verify_chain` checks `seq` contiguity and `prev` digests and
        # NOTHING beneath them, so `resolves[]` and `withdraws[].seq` arrive
        # exactly as a hand-repaired, forged or future-tool-written record
        # spells them. Comparing an `int` with a `None` raised a TypeError that
        # escaped every arm of `main` and exited 1 -- the contract's GATE code.
        # An entry that names no event resolves no event, which is the same
        # answer the comparison would have given had it been able to run.
        for seq in event.get("resolves") or []:
            if _is_seq(seq) and _is_seq(accept_seq) and accept_seq > seq:
                resolved.add(seq)
        for entry in event.get("withdraws") or []:
            seq = entry.get("seq") if isinstance(entry, dict) else entry
            if _is_seq(seq) and _is_seq(accept_seq) and accept_seq > seq:
                resolved.add(seq)
    pending = []
    for event in events:
        if not _is_h_event(event) or event.get("kind") == "signoff":
            continue
        seq = event.get("seq")
        if _is_seq(seq) and seq > floor and seq not in resolved:
            pending.append(seq)
    return pending


def derive(events, fs, staging=None, uncommitted_tail=False, pending_stray=False):
    """Compute contract 5.4's whole state from the ledger and one fs snapshot.

    Pure and zero-I/O (D-19): no file is read, no subprocess is run and no
    environment variable is consulted — ``fs`` is the only channel from the
    filesystem. Nothing computed here is ever stored, so state cannot desync:
    there is no ``progress``, no ``sealed`` and no cached ``next`` on disk.

    ``staging`` is the optional ``{"steps_seq": …, "files": {path: sha256}}``
    view that a ``draft`` holds. Without it the staging-dependent
    ``identical_draft`` conditions read ``None`` and the no-op can never be
    asserted — a missing staging view is not evidence of an identical draft.

    ``uncommitted_tail`` is contract 5.5's row 1, and it is a PARAMETER because
    answering it costs a ``git show`` and this function is pure: the one I/O
    caller (:func:`unit_state`) supplies it. Every key ``route()`` reads is
    produced here; a key it reads that nothing writes reads ``None`` in
    production, which is how row 1 became unreachable and rows 6/7/9 could never
    route to ``draft`` (WR-02).

    ``pending_stray`` is the same arrangement for the one situation that is NOT
    a row of the contract's table (WR-03): stage a refuses it on every verb, so
    routing anywhere but ``resume`` sends the author to a verb that refuses
    identically. Supplied by :func:`stray_pending_material` for the same purity
    reason.
    """
    ordered = list(events)
    paths = fs.get("paths") or {}

    unknown_kinds = []
    unknown_count = 0
    for event in ordered:
        kind = event.get("kind")
        if kind not in KNOWN_KINDS:
            unknown_count += 1
            if kind not in unknown_kinds:
                unknown_kinds.append(kind)
    warnings = []
    if unknown_kinds:
        warnings.append(
            "ignored %d event(s) of unknown kind (%s) — derivation uses the "
            "known kinds only" % (unknown_count, ", ".join(repr(k) for k in unknown_kinds))
        )

    so = _last_of(ordered, "signoff")
    gen = _last_of(ordered, "generation")
    edit = _last_of(ordered, "reviewer-edit")
    rev = _last_of(ordered, "review")
    retired_event = _last_of(ordered, "retired")
    basis = _later(gen, edit)
    tip = _later(basis, rev)

    targets = list(so.get("targets") or []) if so is not None else []
    intent = so.get("intent") if so is not None else None

    plan_stale = so is not None and fs.get("unit_md_sha") != so.get("plan_hash")
    generation_stale = (
        gen is not None
        and so is not None
        and gen.get("signoff_seq") != so.get("seq")
    )

    basis_pairs = _basis_pairs(basis)
    basis_files = [path for path, _ in basis_pairs]
    basis_digests = dict(basis_pairs)

    # Changed bytes only: absence is never drift.
    drifted_paths = []
    for path, recorded in basis_pairs:
        current = paths.get(path)
        if current is not None and current != recorded:
            drifted_paths.append(path)

    missing_paths = []
    for path in basis_files:
        if path in targets and paths.get(path) is None:
            missing_paths.append(path)

    existing_targets = []
    missing_targets = []
    for target in targets:
        current = paths.get(target)
        if target not in basis_digests:
            # Not in the basis: adoptable when it is on disk and non-empty, and
            # in either case not yet part of the recorded basis.
            if current is not None and current != "":
                existing_targets.append(target)
            missing_targets.append(target)
        elif current is None:
            missing_targets.append(target)

    # Reported once, never deleted: a removed path stays in basis.files until
    # the next generation, whose files[] is exactly the new target set.
    orphans = [path for path in basis_files if path not in targets]

    floor = gen.get("seq") if gen is not None else 0
    pending = pending_requests(ordered, floor)

    steered_since_gen = None
    if gen is not None:
        steered_since_gen = _h_after(ordered, gen)

    if staging is None:
        steps_match = None
        targets_match = None
    else:
        staging_files = staging.get("files") or {}
        gen_steps = gen.get("steps_seq") if gen is not None else None
        steps_match = gen_steps == staging.get("steps_seq")
        targets_match = True
        for target in targets:
            # Compared against the destination files, never a historical basis.
            if paths.get(target) != staging_files.get(target):
                targets_match = False
    identical_draft = {
        "generation_exists": gen is not None,
        "signoff_current": (
            gen is not None
            and so is not None
            and gen.get("signoff_seq") == so.get("seq")
        ),
        "steps_match": steps_match,
        "no_h_since_generation": not (gen is not None and _h_after(ordered, gen)),
        "targets_match_staging": targets_match,
    }
    identical_draft["all"] = (
        identical_draft["generation_exists"] is True
        and identical_draft["signoff_current"] is True
        and identical_draft["steps_match"] is True
        and identical_draft["no_h_since_generation"] is True
        and identical_draft["targets_match_staging"] is True
    )

    if retired_event is not None:
        state = "retired"
    elif so is None:
        state = "declared"
    elif gen is None:
        # A brownfield basis alone is still signed-off.
        state = "signed-off"
    elif (
        tip is not None
        and tip.get("kind") == "review"
        and tip.get("verdict") == "accept"
        and not _h_after(ordered, tip)
        and not generation_stale
    ):
        state = "sealed"
    elif tip is not None and tip.get("kind") == "review":
        state = "reviewed"
    else:
        state = "drafted"

    # Contract 5.5's rows 6/7/9 qualifier, and 5.4's first sentence: a
    # `step-recorded` resolves the step it names in the plan's `steps_seq`. A
    # non-actionable unit has no steps to resolve, so it is resolved; an
    # actionable unit with no plan at all is not (D-18 refuses it at
    # `steps_missing`, and `walk` is the honest route).
    plan_event = _last_of(ordered, "steps-planned")
    if intent not in ACTIONABLE_INTENTS:
        steps_resolved = True
    elif plan_event is None:
        steps_resolved = False
    else:
        steps_resolved = not unresolved_steps(ordered, plan_event)

    return {
        "state": state,
        "uncommitted_tail": bool(uncommitted_tail),
        "pending_stray": bool(pending_stray),
        "steps_resolved": steps_resolved,
        "retired": retired_event is not None,
        "so": so,
        "gen": gen,
        "edit": edit,
        "rev": rev,
        "basis": basis,
        "tip": tip,
        "so_seq": so.get("seq") if so is not None else None,
        "gen_seq": gen.get("seq") if gen is not None else None,
        "edit_seq": edit.get("seq") if edit is not None else None,
        "rev_seq": rev.get("seq") if rev is not None else None,
        "basis_seq": basis.get("seq") if basis is not None else None,
        "tip_seq": tip.get("seq") if tip is not None else None,
        "intent": intent,
        "actionable": intent in ACTIONABLE_INTENTS,
        "targets": targets,
        "basis_files": basis_files,
        "plan_stale": plan_stale,
        "generation_stale": generation_stale,
        # Routing rows 8/8b/9 turn on "is there an H event after the tip"; it is
        # derived here so route() can restate the contract's table and compute
        # nothing of its own.
        "h_after_tip": _h_after(ordered, tip),
        "page_drift": bool(drifted_paths),
        "drifted_paths": drifted_paths,
        "page_missing": bool(missing_paths),
        "missing_paths": missing_paths,
        "target_exists": bool(existing_targets),
        "existing_targets": existing_targets,
        "target_missing": bool(missing_targets),
        "missing_targets": missing_targets,
        "orphans": orphans,
        "pending": pending,
        "steered_since_gen": steered_since_gen,
        "identical_draft": identical_draft,
        "warnings": warnings,
    }


def _walk_or_draft(state):
    """Routing rows 6, 7 and 9 share one qualifier (contract 5.5)."""
    if state.get("actionable") and not state.get("steps_resolved"):
        return "walk"
    return "draft"


def route(state):
    """Contract 5.5's ordered table: rows 1–10 including 8b, first match wins.

    This is the ONLY place a ``next`` token is chosen; every surface prints what
    it returns and never re-derives direction. It restates no precondition — the
    preconditions are defined in 5.7 and the table is their rendering — and it is
    exhaustive: a state matching no earlier row falls to row 10, so a derivable
    state never routes to ``None``. Row order is the contract's order and is
    evaluated top to bottom, so two rows that hold at once resolve by table
    position and never by recency.
    """
    if state.get("uncommitted_tail"):
        return "resume"  # 1
    if state.get("pending_stray"):
        # NOT a contract row: `pending_stray` is a fact about this build, in
        # which stage a refuses every verb on it and `resume` is the only thing
        # that could ever clear it (WR-03). It sits beside row 1 because it
        # means the same thing — the record needs recovery before any verb can
        # proceed — and routing it anywhere else names a verb that refuses
        # identically. Phase 17 implements `resume` and this becomes row 1's
        # second half rather than an exception to the table.
        return "resume"
    if state.get("retired"):
        return "retired"  # 2
    if state.get("so") is None:
        return "sign_off"  # 3
    if state.get("plan_stale"):
        return "re_sign"  # 4
    if state.get("page_drift") or state.get("target_exists"):
        return "record_edits"  # 5
    if state.get("gen") is None:
        return _walk_or_draft(state)  # 6 — brownfield basis or none
    if state.get("generation_stale"):
        return _walk_or_draft(state)  # 7 — qualifier: plan amended
    tip = state.get("tip")
    tip_kind = tip.get("kind") if tip is not None else None
    accepted = tip_kind == "review" and tip.get("verdict") == "accept"
    if accepted and not state.get("h_after_tip"):
        if state.get("target_missing"):
            return "steer"  # 8b — record the restoration request
        return "publish"  # 8
    if tip_kind == "review":
        return _walk_or_draft(state)  # 9 — accept with H after, or fix/redraft
    return "review"  # 10 — tip is a generation or a reviewer-edit


# --- git --------------------------------------------------------------------


#: git's messages are parsed in exactly one place (``guard_ignored_paths``), so
#: that one call pins the language. Without it the refusal's text is whatever
#: the author's LC_MESSAGES happens to be (WR-01).
IPC_LOCALE = {"LC_ALL": "C", "LANGUAGE": ""}


def git(args, cwd, env=None):
    """Run git with an argv LIST — never ``shell=True``, never interpolation.

    Author text (unit ids, notes, targets) reaches this function as list
    elements, so no quoting bug can turn it into a command.

    ``env`` overlays the inherited environment (it does not replace it), for the
    one caller that needs git's messages in a fixed language.
    """
    overlaid = None
    if env:
        overlaid = dict(os.environ)
        overlaid.update(env)
    return subprocess.run(
        ["git"] + list(args),
        cwd=os.fspath(cwd),
        capture_output=True,
        text=True,
        env=overlaid,
    )


def git_root(start=None):
    """The repository root containing ``start`` (default: the cwd)."""
    where = os.fspath(start) if start else os.getcwd()
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=where,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise Refusal(
            "not_a_repo",
            detail="not inside a git repository",
            hint="run dogen from inside the documentation repository",
        )
    return proc.stdout.strip()


def git_dir(repo):
    """The absolute ``.git`` directory (a file in a worktree, hence git's answer)."""
    proc = git(["rev-parse", "--absolute-git-dir"], repo)
    if proc.returncode != 0:
        return os.path.join(os.fspath(repo), ".git")
    return proc.stdout.strip()


def git_head(repo):
    """HEAD before the transition, or ``None`` in a repository with no commit."""
    proc = git(["rev-parse", "HEAD"], repo)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def git_identity(repo):
    """``{name, email}`` from git config; either missing is 2 ``git_identity_missing``."""
    name = git(["config", "user.name"], repo).stdout.strip()
    email = git(["config", "user.email"], repo).stdout.strip()
    if not name or not email:
        raise Refusal(
            "git_identity_missing",
            detail="git user.name and user.email are not both configured",
            hint='git config user.name "…" && git config user.email "…"',
        )
    return {"name": name, "email": email}


def git_add(repo, pathspecs):
    """Stage exactly these files — a LIST of per-file paths, never a directory."""
    return git(["add", "--"] + list(pathspecs), repo)


def git_commit(repo, subject, body, trailers, pathspecs):
    """One commit, explicit per-file pathspecs, trailers via ``--trailer``.

    Hand-appending trailer lines to the message would work until a body ends
    without a blank line; ``--trailer`` is git's own parser and keeps the block
    well-formed. Pathspecs are per-file on both ``add`` and ``commit`` so an
    unrelated in-``docs/`` edit is never swept in (audit defect 4).
    """
    args = ["commit", "-q", "-m", subject]
    if body:
        args += ["-m", body]
    for key, value in trailers:
        args += ["--trailer", "%s: %s" % (key, value)]
    args += ["--"] + list(pathspecs)
    return git(args, repo)


def git_show_blob(repo, rev, path):
    """The raw bytes of ``<rev>:<path>``, or ``None`` when it is not there.

    Bytes, not text: the post-commit check compares digests, so a hook that only
    rewrote line endings must still be visible.
    """
    proc = subprocess.run(
        ["git", "show", "%s:%s" % (rev, path)],
        cwd=os.fspath(repo),
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def index_snapshot(repo):
    """The set of staged path names (``git diff --cached --name-only``)."""
    proc = git(["diff", "--cached", "--name-only"], repo)
    return set(line for line in proc.stdout.splitlines() if line)


def committed_names(repo):
    """The set of paths in HEAD's own commit (``git show --name-only``)."""
    proc = git(["show", "--name-only", "--format=", "HEAD"], repo)
    return set(line for line in proc.stdout.splitlines() if line)


# --- lock -------------------------------------------------------------------


def acquire_lock(repo, unit=""):
    """One repo-wide ``flock`` at ``.dogen/staging/lock``; held across all six steps.

    ``LOCK_NB`` makes a second invocation refuse rather than queue, and the
    kernel releases the lock when the process dies, so an interrupted run leaves
    no stale lock to clean up.

    :func:`guard_dogen_root` runs FIRST, before the ``makedirs``: the lock is the
    earliest thing every mutating verb writes, so a ``.dogen/staging`` symlink
    would otherwise put the repository's own write mutex outside the repository
    before any later guard got a turn (CR-02).

    The lock file is then guarded BY NAME, because :data:`DOGEN_ROOTS` names
    three *directories* and ``os.open`` follows symlinks: a link at
    ``.dogen/staging/lock`` itself cleared every directory check and still
    created the repository's write mutex at an arbitrary absolute path, on the
    exit-0 success path, with no diagnostic (CR-03). ``O_NOFOLLOW`` closes the
    window between the ``islink`` check and the open, so a link introduced in
    between cannot win the race either.
    """
    guard_dogen_root(repo, unit)
    path = os.path.join(os.fspath(repo), ".dogen", "staging", "lock")
    if os.path.islink(path):
        raise Refusal(
            "bad_write_path",
            unit=unit,
            detail=".dogen/staging/lock is a symlink",
            hint=".dogen/staging/lock must be a real file inside the repository",
        )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o644)
    except OSError as bad:
        # WR-15: only these three errnos mean "the path is not a real file" --
        # ELOOP is O_NOFOLLOW refusing a symlink, EISDIR and ENOTDIR are the
        # other two shapes CR-03 is about. A blanket `except OSError` here
        # answered permissions, a read-only filesystem, ENOSPC and EMFILE with
        # the same sentence, INVENTING a cause that is false -- and strictly
        # worse than what `main`'s OSError backstop already said. That is the
        # defect WR-01 and WR-12 were filed for, one function over.
        if bad.errno in (errno.ELOOP, errno.EISDIR, errno.ENOTDIR):
            raise Refusal(
                "bad_write_path",
                unit=unit,
                detail=".dogen/staging/lock is not a real file (%s)"
                % errno.errorcode.get(bad.errno, bad.errno),
                hint=".dogen/staging/lock must be a real file inside the repository",
            )
        raise  # main's OSError arm names the real fault, errno and all
    # IN-01 (phase 16): the guard above reads "not a symlink", but both it and
    # the docstring MEAN "a real file". `O_NOFOLLOW` rejects only ELOOP, EISDIR
    # and ENOTDIR, so a FIFO, a socket or a device node planted at the lock path
    # opened cleanly and `flock` "succeeded" on an object the six steps' mutual
    # exclusion does not hold over. Asked of the FD, so the answer is about the
    # object actually opened rather than about a path that could change between
    # the check and the open.
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise Refusal(
            "bad_write_path",
            unit=unit,
            detail=".dogen/staging/lock is not a real file (not a regular file)",
            hint=".dogen/staging/lock must be a real file inside the repository",
        )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as bad:
        os.close(fd)
        # WR-21: the WR-15 fix narrowed the `os.open` arm eleven lines above and
        # stopped short of this one. "Another dogen invocation holds the lock"
        # is true of EWOULDBLOCK/EAGAIN (and EACCES, which some platforms return
        # for a contended lock) and of nothing else. ENOLCK -- an NFS or overlay
        # mount with no lock manager -- EBADF, EINTR and EINVAL got the same
        # sentence, which sends a skill into a wait-and-retry loop against a
        # condition that will never clear. A cause dogen cannot identify is one
        # it may not invent.
        if bad.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
            raise Refusal(
                "busy",
                # WR-10: `unit` is right there in the signature and this raiser
                # omitted it, so the single most likely refusal a second
                # concurrent skill sees could not name what it had just refused.
                unit=unit,
                detail="another dogen invocation holds .dogen/staging/lock",
                hint="wait for it to finish and retry",
            )
        raise  # main's OSError arm names the real fault, errno and all
    return fd


def release_lock(fd):
    """Release and close; safe to call once per successful acquire."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


@contextlib.contextmanager
def unit_lock(repo, unit=""):
    """Hold ``.dogen/staging/lock`` for the body, and release it whatever happens.

    Ten verbs spelled the acquire/``try``/``finally``/release by hand. A
    ``with`` cannot forget the release, and a lock a refusal path leaks is
    indistinguishable from a concurrent invocation to every later one.
    """
    fd = acquire_lock(repo, unit)
    try:
        yield fd
    finally:
        release_lock(fd)


def index_lock_present(repo):
    """Is another git process holding ``.git/index.lock``?

    Probed, never deleted: a stale lock is indistinguishable from an active one,
    and deleting a live one corrupts someone else's commit. ``git_busy`` is a
    refuse-and-retry outcome by design (contract 5.11 T22).
    """
    return os.path.exists(os.path.join(git_dir(repo), "index.lock"))


def git_busy_guard(repo, unit=""):
    """Contract 5.7 stage a's first question, asked once instead of eleven times.

    Every mutating verb opened with a byte-identical copy of this refusal, and
    ``resume`` needs it WITHOUT the classification that used to follow it — so
    the two halves of stage a are two functions (see :func:`stage_a_guard`).
    """
    if index_lock_present(repo):
        raise Refusal(
            "git_busy",
            unit=unit,
            detail=".git/index.lock is present",
            hint="another git process is running; retry — dogen never deletes it",
        )


# --- pending / manifest -----------------------------------------------------


def crash_point(name):
    """Fixture-only interruption at a named write-protocol point (D-15).

    Six names: ``manifest`` (a durable manifest, nothing appended), ``append``,
    ``place:<n>``, ``commit``, ``cleanup``, and ``adopt`` (the durable adopt
    copies are on disk and the revised manifest is not yet published).

    ``os._exit`` — not ``sys.exit`` — because it skips ``finally`` blocks, atexit
    handlers and buffer flushing, which is what an interruption actually does.
    Armed only under ``DOGEN_TEST_HOOKS=1``; unset ``DOGEN_CRASH_AT`` makes it a
    no-op on every path even then (WR-07).
    """
    if test_hooks_enabled() and os.environ.get("DOGEN_CRASH_AT") == name:
        os._exit(137)


def publish_atomic(path, data):
    """Temp write + ``fsync`` + ``os.replace`` + directory ``fsync``.

    The directory ``fsync`` is what makes the rename itself durable; without it
    step 1 is not a recovery boundary at all — the manifest's contents would be
    on disk but the name pointing at them could still be lost.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    dir_fd = os.open(directory, os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def read_bytes(path):
    """A file's raw bytes, or ``None`` when it is absent."""
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        return None


def digest_file(path):
    """sha256 of a file's raw bytes, or ``None`` when it is absent.

    Distinct from :func:`sha256_file`, whose three-valued result feeds
    ``derive()``: recovery material is compared against recorded digests, and a
    zero-byte file has the digest of the empty string, not ``""``.
    """
    data = read_bytes(path)
    return None if data is None else sha256_bytes(data)


def after_copy(pending, entry):
    """Where one manifest entry's intended bytes live under ``pending/``.

    ``after/<path>`` for everything :func:`publish_pending` wrote, and whatever
    ``after_path`` names for an entry ``resume --adopt`` revised. The ONE place
    that indirection is resolved, so stage a's digest check, pass 1's
    classification and step 3's placement cannot look in three different
    directories for the same file — which is the shape of bug that would make
    an adopted transition place the bytes the author asked to discard.
    """
    named = entry.get("after_path")
    if named:
        return os.path.join(pending, *named.replace(os.sep, "/").split("/"))
    return os.path.join(pending, "after", entry["path"])


def classify_file(entry, intended, disk, placed=False):
    """Contract 5.8's three per-file classes for one manifest entry.

    ``done`` (disk == after), ``recoverable`` (disk == before and step 3 had
    not yet placed this file, or absent with a null before digest — both read
    ``None`` here, which is why one comparison covers both), ``unexpected``
    (anything else). ``intended`` and ``disk`` are raw bytes or ``None``.

    ``done`` is tested FIRST and the order is the answer for a file whose
    before and after digests are equal: calling that ``recoverable`` would put
    it on pass 2's placement list, where it cannot change a byte, and the
    transition would report work it did not do. One definition, shared by
    ``resume``'s pass 1 and the findings renderer, so the two surfaces can
    never disagree about the same file.

    ``placed`` is what step 3 recorded in ``pending/progress.json``, and it is
    what makes ``recoverable`` mean what the contract says it means. Without
    it, a formatting hook that rewrites a target back to its PRE-transition
    bytes — the steady state once the hook has been adopted once — restores
    ``before_sha`` and reads as "nothing was placed yet", so `resume` re-places
    the tool's bytes, the still-installed hook rewrites and rejects again, and
    every mode loops forever with no escape. This tool WROTE ``after_sha``
    here; anything else on disk afterwards is someone else's rewrite, even when
    it happens to equal ``before_sha``, and ``unexpected`` is the class that
    exists for exactly that. It is what routes the author to `resume_ambiguous`
    and the two answers contract 5.8's hook paragraph promises.
    """
    disk_sha = None if disk is None else sha256_bytes(disk)
    if disk_sha == entry.get("after_sha"):
        return "done"
    if placed:
        return "unexpected"
    if disk_sha == entry.get("before_sha"):
        return "recoverable"
    return "unexpected"


def classify_manifest_files(repo, unit, manifest):
    """One ``{path, class, intended, disk}`` row per file, in ``files[]`` order.

    The bytes travel with the class because every consumer needs them: pass 1
    diffs the unexpected ones and the findings renderer compares them against
    HEAD. Read once, here, from the ONE filesystem snapshot the caller takes.
    """
    if manifest is None:
        return []
    root = os.fspath(repo)
    pending = pending_dir(repo, unit)
    placed = set(read_progress(repo, unit)["placed"])
    rows = []
    for entry in manifest["files"]:
        name = entry["path"]
        intended = read_bytes(after_copy(pending, entry))
        disk = read_bytes(os.path.join(root, name))
        rows.append(
            {
                "path": name,
                "class": classify_file(entry, intended, disk, name in placed),
                "intended": intended,
                "disk": disk,
            }
        )
    return rows


def staging_dir(repo, unit):
    """``<repo>/.dogen/staging/<id>``."""
    return os.path.join(os.fspath(repo), ".dogen", "staging", unit)


def pending_dir(repo, unit):
    """``<repo>/.dogen/staging/<id>/pending`` — transient, gitignored."""
    return os.path.join(staging_dir(repo, unit), "pending")


def cleanup_pending(repo, unit):
    """Delete ``pending/`` — step 6, and stage a's cleanup in write mode."""
    path = pending_dir(repo, unit)
    if os.path.isdir(path):
        shutil.rmtree(path)


def progress_path(repo, unit):
    """``pending/progress.json`` — what steps 3 and 4 of THIS batch already did.

    Deliberately a second, separate artefact rather than two more keys on the
    manifest: the manifest is the recovery MATERIAL, it is published once and
    read back byte-for-byte by ``resume --adopt``'s re-read check, and a file
    that step 3 rewrites on every attempt has no business in it. It lives
    inside ``pending/``, so step 6's single ``rmtree`` retires it with the rest
    of the batch and no state survives into the next transition.
    """
    return os.path.join(pending_dir(repo, unit), "progress.json")


def read_progress(repo, unit):
    """``{"placed": [paths], "transition_attempts": n}``, defaulting to "nothing yet".

    WR-03: the counter was ``commit_attempts`` and counted three different
    things — ``git add`` failures, commit refusals, and interrupted runs, since
    it is persisted BEFORE either git call, so a kill between the write and the
    commit consumes one. Its name asserted "a commit was attempted and
    refused", which is false for two of the three. Renamed to what it counts:
    attempts to complete the transition. A ``pending/`` written by an older
    build reads the old key as absent and restarts at zero, which costs one
    extra retry on an interrupted upgrade and nothing else — ``pending/`` exists
    only between a failed transition and its resume.

    Absent, unreadable and malformed all read as the empty record, because
    every consumer's safe answer is "assume step 3 has not run": that is the
    pre-existing behaviour, and a progress file is an optimisation over the
    recovery material, never a substitute for it.

    WR-03: ``OSError`` whole, not a hand-listed three of its subclasses. A
    ``PermissionError`` used to escape into ``classify_manifest_files`` and out
    through ``main``'s ``OSError`` arm as 2 ``bad_target`` — on the read-only
    verbs too, so an unreadable HINT FILE turned ``show``, ``summary`` and
    ``verify`` into bad-input refusals. "Unreadable reads as empty" is the
    sentence above; listing subclasses is how it stopped being true.
    """
    empty = {"placed": [], "transition_attempts": 0}
    try:
        with open(progress_path(repo, unit), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict):
        return empty
    placed = data.get("placed")
    if not isinstance(placed, list):
        placed = []
    attempts = data.get("transition_attempts")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
        attempts = 0
    return {
        "placed": [name for name in placed if isinstance(name, str)],
        "transition_attempts": attempts,
    }


def write_progress(repo, unit, progress):
    """Publish the progress record atomically, same discipline as the manifest."""
    publish_atomic(
        progress_path(repo, unit),
        json.dumps(progress, sort_keys=True, ensure_ascii=False).encode("utf-8"),
    )


def publish_pending(repo, unit, files, event_lines):
    """Step 1: publish the recovery material, then the manifest that names it.

    ``files`` is ``[(repo-relative path, intended bytes)]``. Every file gets an
    ``after/`` copy and either a ``before/`` copy or a ``before/<path>.absent``
    marker, mirroring the destination's directory structure so two same-named
    files in different directories never collide. The manifest is published LAST
    and atomically, which is what makes "a complete manifest" mean "all of its
    material is already durable".
    """
    if not event_lines:
        raise ValueError("a zero-event batch is never published")
    root = os.fspath(repo)
    pending = pending_dir(repo, unit)
    if not contained(os.path.join(root, ".dogen", "staging"), pending):
        raise Refusal(
            "bad_write_path",
            unit=unit,
            detail="the pending directory resolves outside .dogen/staging/",
            hint=".dogen/staging/ must be a real directory inside the repository",
        )
    if os.path.isdir(pending):
        shutil.rmtree(pending)
    entries = []
    for path, after_bytes in files:
        destination = os.path.join(root, path)
        before_sha = None
        if os.path.exists(destination):
            with open(destination, "rb") as handle:
                before_bytes = handle.read()
            before_sha = sha256_bytes(before_bytes)
            publish_atomic(os.path.join(pending, "before", path), before_bytes)
        else:
            publish_atomic(os.path.join(pending, "before", path + ".absent"), b"")
        publish_atomic(os.path.join(pending, "after", path), after_bytes)
        entries.append(
            {
                "path": path,
                "before_sha": before_sha,
                "after_sha": sha256_bytes(after_bytes),
            }
        )
    manifest = {"events": list(event_lines), "files": entries}
    publish_atomic(
        os.path.join(pending, "manifest.json"),
        json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8"),
    )
    return manifest


def read_manifest(repo, unit):
    """The pending manifest, or ``None`` when it is absent or incomplete.

    "Complete" is deliberately strict, and STRUCTURALLY so: a dict with a
    non-empty list of string event lines, and a list of file entries that each
    name a repo-relative path with the digests stage a compares against.
    Anything less is the "pending without a complete manifest" row of contract
    5.8's table — delete and proceed — or, when there is a tail,
    `recovery_unsupported`/`material_invalid`. Validating shape HERE rather than
    at each consumer is what keeps a hand-mangled manifest from crashing
    `classify_stage_a`, which runs first on EVERY verb including the read-only
    `show` the author reaches for to diagnose it.
    """
    path = os.path.join(pending_dir(repo, unit), "manifest.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    events = data.get("events")
    files = data.get("files")
    if not isinstance(events, list) or not events:
        return None
    if not all(isinstance(line, str) for line in events):
        return None
    if not isinstance(files, list):
        return None
    for entry in files:
        if not isinstance(entry, dict):
            return None
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            return None
        if not isinstance(entry.get("after_sha"), str):
            return None
        before_sha = entry.get("before_sha")
        if before_sha is not None and not isinstance(before_sha, str):
            return None
        # A manifest path is joined onto the repo root and onto pending/after/
        # and pending/before/. `../../../etc/foo` would read outside the
        # repository today and, once `resume` lands, PLACE there.
        if os.path.isabs(path) or ".." in path.replace(os.sep, "/").split("/"):
            return None
        # `resume --adopt` is the ONE writer that revises a manifest, and an
        # `after_path` is joined onto pending/ and then READ as the bytes a
        # placement writes. It is held to the same rule the destination is.
        named = entry.get("after_path")
        if named is not None and safe_relative(named) is None:
            return None
    return data


def place_files(repo, unit, entries):
    """Step 3: place each file from its ``after/`` copy; pending is not consumed."""
    root = os.fspath(repo)
    pending = pending_dir(repo, unit)
    placed = []
    for index, entry in enumerate(entries):
        path = entry["path"]
        with open(after_copy(pending, entry), "rb") as handle:
            data = handle.read()
        publish_atomic(os.path.join(root, path), data)
        placed.append(path)
        crash_point("place:%d" % (index + 1))
    return placed


def post_commit_check(repo, entries, pathspecs, before_index):
    """Step 5: what did a hook change after we recorded it?

    Returns ``(changed, extra)``. ``changed`` holds every manifest path whose
    HEAD bytes or disk bytes no longer digest to ``after_sha``. ``extra`` holds
    paths outside the verb's own pathspecs that a hook got into the commit or
    left staged — computed from BOTH ``git show --name-only`` and the
    before/after index snapshots, because a hook can stage without committing
    (only the index sees it) and can commit without leaving the index dirty
    (only ``git show`` sees it). Neither source alone is evidence.

    Nothing here is undone. The transition is committed and it stands; a
    formatter is not a reviewer.
    """
    root = os.fspath(repo)
    changed = []
    for entry in entries:
        path = entry["path"]
        blob = git_show_blob(repo, "HEAD", path)
        head_sha = sha256_bytes(blob) if blob is not None else None
        disk_sha = digest_file(os.path.join(root, path))
        if head_sha != entry["after_sha"] or disk_sha != entry["after_sha"]:
            changed.append(path)
    own = set(pathspecs)
    committed = committed_names(repo)
    after_index = index_snapshot(repo)
    extra = sorted((committed | (after_index - set(before_index))) - own)
    return changed, extra


def _split_ledger(text):
    """``(complete lines, partial tail)`` — a file not ending in LF has a partial."""
    if not text:
        return [], ""
    parts = text.split("\n")
    return parts[:-1], parts[-1]


def _read_text(path, unit=""):
    """A ledger's text, or ``""`` when it is absent.

    Absent and undecodable are NOT the same answer: ``""`` for a file that
    exists but cannot be decoded makes stage a believe the ledger is empty and
    derive state from nothing, which is the silent wrong answer the whole
    ``ledger_corrupt`` row exists to prevent (WR-09).
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""
    except (IsADirectoryError, NotADirectoryError):
        # WR-20: the two readers of this file now give the SAME answer here.
        raise unreadable_ledger(path, unit)
    except UnicodeDecodeError:
        raise undecodable_ledger(path, unit)


def ledger_split(repo, unit):
    """``(complete, partial, committed, relative)`` for a unit's ledger.

    The one place the lines on disk are split from the lines HEAD already
    holds. ``classify_stage_a``, :func:`uncommitted_ledger_tail` and
    :func:`stray_pending_material` each carried a byte-identical copy of the
    ladder, and three readings of "what is committed" is two too many.
    """
    path = ledger_path(repo, unit)
    relative = os.path.relpath(path, os.fspath(repo))
    complete, partial = _split_ledger(_read_text(path, unit))
    committed = []
    blob = git_show_blob(repo, "HEAD", relative)
    if blob is not None:
        head_complete, head_partial = _split_ledger(blob.decode("utf-8", "replace"))
        committed = list(head_complete)
        if head_partial:
            committed.append(head_partial)
    return complete, partial, committed, relative


def _is_batch_prefix(tail, partial, events):
    """Is the tail an exact byte-prefix of the batch (contract 5.8)?

    At most one truncated final line, itself a byte-prefix of the next expected
    line — which is decidable only because the batch is appended in one
    ``write()``.
    """
    if len(tail) > len(events):
        return False
    if tail != events[: len(tail)]:
        return False
    if partial:
        if len(tail) >= len(events):
            return False
        return events[len(tail)].startswith(partial)
    return True



# --- contract 5.8's honest limit (D-08) --------------------------------------

#: The safety boundary, printed verbatim on every `recovery_unsupported`. It is
#: a constant rather than a formatted sentence because it is the same promise in
#: every situation, and because a boundary composed per branch is a boundary a
#: future branch can forget to state (T-17-26).
SAFETY_BOUNDARY = (
    "the unit directory and every file whose bytes cannot be attributed are preserved",
    "nothing is restored from committed history, because committed history is not "
    "necessarily the pre-operation bytes: a unit plan may carry legitimate "
    "uncommitted author changes, and a placed page may have replaced uncommitted work",
)


def safe_relative(name):
    """A manifest- or event-supplied path, or ``None`` when it may not be used.

    :func:`read_manifest` already applies this rule to a COMPLETE manifest. The
    findings block reads paths from two surfaces that reader rejects — a
    manifest it judged incomplete, and the tail's own events — so the rule is
    stated once here and applied at both. A path that is absolute or climbs out
    of the repository is dropped rather than reported: reporting it would mean
    reading bytes the record has no business naming (T-17-24).
    """
    if not isinstance(name, str) or not name:
        return None
    if os.path.isabs(name) or ".." in name.replace(os.sep, "/").split("/"):
        return None
    return name


def salvaged_manifest_paths(repo, unit):
    """What ``pending/manifest.json`` still names, when it is not a valid manifest.

    :func:`read_manifest` is all-or-nothing on purpose — a consumer must never
    half-read a mangled manifest. But contract 5.8 prints the paths it can
    identify "from the manifest if any part of it is readable", and an author
    staring at `material_invalid` is owed whatever that file still says. Read
    defensively, entry by entry, and used for REPORTING only: nothing here
    reaches a write path.
    """
    path = os.path.join(pending_dir(repo, unit), "manifest.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        return []
    rows = []
    for entry in data["files"]:
        if not isinstance(entry, dict):
            continue
        name = safe_relative(entry.get("path"))
        if name is None:
            continue
        recorded = entry.get("after_sha")
        rows.append((name, recorded if isinstance(recorded, str) else None))
    return rows


def tail_event_paths(tail):
    """The paths the uncommitted tail's own events name, with their digests.

    The only path evidence left when there is no manifest at all. An event's
    ``files[]`` names a DOCS-relative target — the shape :func:`describe_paths`
    reads — so it is joined onto the docs root HERE, once, rather than at the
    comparison, where a repo-relative manifest path and a docs-relative event
    path would silently become the same namespace.
    """
    rows = []
    for line in tail:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or not isinstance(event.get("files"), list):
            continue
        for entry in event["files"]:
            if not isinstance(entry, dict):
                continue
            name = safe_relative(entry.get("path"))
            if name is None:
                continue
            recorded = entry.get("sha256")
            rows.append(
                (
                    os.path.join(DOCS_ROOT, name),
                    recorded if isinstance(recorded, str) else None,
                )
            )
    return rows


def path_verdict(repo, path, recorded_sha):
    """Contract 5.8's four verdicts for one path, first match in the fixed order.

    The comparison is :func:`drift_status`'s, not a second vocabulary for the
    same question: HEAD's blob bytes digested and compared against the disk
    file's digest. The ORDER is the answer for a path matching both — the
    recorded digest wins, because it is the fact the interrupted operation
    produced, where HEAD's agreement with it is a coincidence of timing.

    ``unaccounted`` is reserved for a path the tool has no recorded digest for
    AND whose bytes are not HEAD's: there is nothing to compare it against, so
    calling it ``neither`` would claim a comparison that never happened.
    """
    disk = digest_file(os.path.join(os.fspath(repo), path))
    if recorded_sha is not None and disk is not None and disk == recorded_sha:
        return "matches recorded digest"
    blob = git_show_blob(repo, "HEAD", path)
    if blob is not None and disk is not None and sha256_bytes(blob) == disk:
        return "matches HEAD"
    return "neither" if recorded_sha is not None else "unaccounted"


def findings_paths(repo, unit, facts):
    """One verdict row per identifiable path, each path reported exactly once.

    The manifest first — it is the interrupted operation's own account of what
    it meant to write — then the salvageable remains of an invalid one, then
    any path only the tail's events name. A path two sources name is reported
    once, under the first, so two runs over the same state print the same rows
    in the same order (:func:`describe_paths`'s rule).
    """
    manifest = facts.get("manifest")
    if manifest is not None:
        sources = [(entry["path"], entry.get("after_sha")) for entry in manifest["files"]]
    else:
        sources = salvaged_manifest_paths(repo, unit)
    sources = sources + tail_event_paths(facts.get("tail") or [])
    rows = []
    seen = set()
    for name, recorded in sources:
        if name in seen:
            continue
        seen.add(name)
        rows.append({"path": name, "verdict": path_verdict(repo, name, recorded)})
    return rows


def findings_steps(repo, unit, facts, paths):
    """The expert steps contract 5.8 supports FOR THIS SITUATION, and no others.

    Each of the three the contract names is gated on its own evidence, and the
    gate is the whole point: a step printed without it is a recipe the tool
    cannot back, and the failure mode is an author destroying uncommitted work
    on the tool's advice (T-17-27). Where no step is derivable the section is
    the single terminal line the contract fixes.

    Deliberately absent: any instruction to restore a path from committed
    history, and any suggestion that an unrecoverable record can be recorded
    over. Both are prohibited by the plan and grep-gated in the tool.
    """
    steps = []
    seqs = facts.get("seqs") or []
    committed = facts.get("committed") or 0
    if committed and seqs:
        steps.append(
            "the tail was never committed: after inspecting seq %s of %s, removing "
            "those lines returns the record to its committed prefix"
            % (", ".join(str(seq) for seq in seqs),
               os.path.relpath(ledger_path(repo, unit), os.fspath(repo)))
        )
    for row in paths:
        if row["verdict"] == "matches recorded digest":
            steps.append(
                "%s holds the bytes the interrupted operation recorded as its "
                "output: evidence, not proof, that the operation wrote it — the "
                "author decides whether to keep it" % row["path"]
            )
    if not committed:
        steps.append(
            "no ledger for %s is in HEAD, so the declaration itself never landed: "
            "move the unit directory aside for inspection "
            "(mv .dogen/units/%s .dogen/staging/recovery-<ts>/) and read it there"
            % (unit, unit)
        )
    return steps or ["expert intervention required"]


def findings_lines(repo, unit, facts, paths):
    """The block itself: four headings, in contract 5.8's order, never omitted.

    An empty section prints its heading and no rows. That is the point of a
    FIXED block rather than a composed one — a missing section reads as
    "nothing to report", and 5.8's whole claim is that the tool says what it
    actually found (T-17-26).
    """
    seqs = facts.get("seqs") or []
    lines = ["uncommitted tail:"]
    if seqs:
        lines.append("  seq %s" % ", ".join(str(seq) for seq in seqs))
    lines.append("paths:")
    lines.extend("  %s: %s" % (row["path"], row["verdict"]) for row in paths)
    lines.append("safety boundary:")
    lines.extend("  " + sentence for sentence in SAFETY_BOUNDARY)
    lines.append("supported steps:")
    lines.extend("  " + step for step in findings_steps(repo, unit, facts, paths))
    return lines


def findings(repo, unit, facts):
    """The honest-limit block and its structured half, built at the raise site.

    Returns ``(stdout lines, refusal extra)``. Deep code raises and ``main``
    converts (:class:`Refusal`), and this follows that split rather than
    fighting it: the block is BUILT here, against the one filesystem snapshot
    the refusal describes, and WRITTEN by ``main``, which is the only place
    ``--json`` is authoritative. Writing it at the raise site would corrupt a
    ``--json`` document — contract 5.7 moves the refusal ITSELF to stdout — or
    need a second opinion about a flag stage a never sees. Either way the block
    still reaches stdout before the refusal's one stderr line, which is the
    property GATE-04 and the acceptance harness actually assert.
    """
    paths = findings_paths(repo, unit, facts)
    return findings_lines(repo, unit, facts, paths), {"paths": paths}


def classify_stage_a(repo, unit, write_mode=True, report_only=False):
    """Stage a: the lock's siblings — chain, committed prefix, tail and ``pending/``.

    Implements contract 5.8's situation table verbatim and runs BEFORE input
    validation, so a `busy` or a recovery refusal always beats a bad-input one
    (GATE-01 order). Harmless ``pending/`` states are deleted and the verb
    proceeds; everything else raises, having written nothing.

    **Write boundary:** ``write_mode=False`` classifies identically and deletes
    nothing — it reports what write mode would delete. The read-only verbs use
    it.

    **Report mode:** ``report_only=True`` RETURNS the classification record for
    every row instead of raising it, and implies the write boundary. It exists
    because the two rows this classifier raises for — `uncommitted_tail` and
    `recovery_unsupported` — are precisely the two situations ``resume`` exists
    to resolve, so wiring that verb through the ordinary front door made
    ``dogen resume <id>`` refuse with the hint ``dogen resume <id>``. It is a
    third MODE, not a second classifier: the table, its order and its messages
    are stated once, and `verify` reuses it in plan 17-09 to report V1–V4 on a
    unit whose tail is uncommitted rather than refusing before any check runs.

    The record carries the §5.8 situation name, the reason/detail/hint the
    raising mode would have used (``reason`` is ``None`` for a row that is not
    a refusal), the tail's raw lines and seq range, the manifest as
    :func:`read_manifest` read it, and the per-file classification.
    """
    root = os.fspath(repo)
    path = ledger_path(repo, unit)
    facts = {
        "situation": "clean",
        "deleted": False,
        "tail": [],
        "partial": "",
        "seqs": [],
        "manifest": None,
        "files": [],
        "committed": 0,
        "findings": [],
        "extra": None,
        "reason": None,
        "detail": "",
        "hint": "",
        "next": "resume",
    }

    def answer(situation, reason=None, detail="", hint="", next_token="resume"):
        """The ONE branch point between reporting and raising.

        Every row below funnels through here, so the two modes cannot drift:
        the report mode names exactly the reason the raising mode raises.
        """
        facts.update(
            situation=situation, reason=reason, detail=detail, hint=hint,
            next=next_token,
        )
        if reason == "recovery_unsupported":
            # The five rows that reach contract 5.8's honest limit reach it
            # through here, so the findings block is built ONCE — against the
            # one filesystem snapshot this refusal describes — and both modes
            # carry it: the raising one on the Refusal, the report mode on the
            # record, where `resume` picks it up before raising its own.
            facts["findings"], facts["extra"] = findings(repo, unit, facts)
        if reason is not None and not report_only:
            raise Refusal(
                reason, unit=unit, detail=detail, hint=hint, next_token=next_token,
                extra=facts["extra"], report_lines=facts["findings"],
            )
        return dict(facts)

    if not contained(os.path.join(root, ".dogen", "units"), path):
        # A malformed id cannot escape: stage b refuses it a moment later.
        return answer("clean")

    # Contract 5.10: a unit written by the legacy pipe-delimited scripts is
    # refused, never half-read. There is no in-place migration — the legacy
    # file is not read, not converted and not deleted. A directory holding
    # BOTH is a JSONL unit and the legacy file is ignored in silence: the five
    # bash scripts still write `ledger.md` beside it through phase 16 (D-13),
    # so coexistence is the normal state, not a defect.
    legacy = os.path.join(os.path.dirname(path), "ledger.md")
    if os.path.exists(legacy) and not os.path.exists(path):
        return answer(
            "legacy_unit",
            "legacy_unit",
            "%s is a legacy pipe-delimited ledger and there is no ledger.jsonl"
            % os.path.relpath(legacy, root),
            "archive the unit directory (move %s aside) and declare the unit "
            "again — dogen never migrates a ledger in place"
            % os.path.relpath(os.path.dirname(path), root),
            "",
        )

    complete, partial, committed_lines, relative = ledger_split(repo, unit)
    facts["partial"] = partial

    problems = verify_chain(complete)
    if problems:
        return answer(
            "ledger_corrupt",
            "ledger_corrupt",
            problems[0],
            "inspect %s; the chain is broken and nothing may be appended" % relative,
        )

    # The header event names the unit its directory must hold. A ledger copied
    # or moved into another directory is a recovery situation, not a bad
    # argument — exit 6, and it beats every later classification because the
    # record being read is not this unit's record.
    if complete:
        try:
            header = json.loads(complete[0])
        except ValueError:
            header = {}
        recorded = header.get("unit")
        if header.get("kind") == "ledger" and recorded != unit:
            return answer(
                "unit_id_mismatch",
                "unit_id_mismatch",
                "%s records unit %r, not %r" % (relative, recorded, unit),
                "the record belongs to %r; move the directory back rather than "
                "editing the ledger" % recorded,
                "show",
            )
        # WR-03: contract 5.10 says a legacy or future-contract record must not
        # be half-read, and `ledger_version_unsupported` sat in the reason table
        # with no raiser. Only the read-only `verify` noticed (V1), so a `v: 2`
        # ledger was parsed, derived from, and APPENDED TO by a contract-1 tool
        # — the exact half-read 5.10 forbids. Checked HERE, beside the
        # unit-id check, because stage a is the one preamble every verb runs.
        if header.get("kind") == "ledger" and header.get("v") != CONTRACT:
            return answer(
                "ledger_version_unsupported",
                "ledger_version_unsupported",
                "%s records ledger version %r; this tool reads v%d"
                % (relative, header.get("v"), CONTRACT),
                "archive the unit directory; dogen never migrates a ledger in "
                "place",
                "",
            )

    if complete[: len(committed_lines)] != committed_lines:
        return answer(
            "ledger_diverged",
            "ledger_diverged",
            "the committed prefix of %s no longer matches HEAD" % relative,
            "git log -- %s; the committed record was rewritten" % relative,
        )
    tail = complete[len(committed_lines) :]
    first = len(committed_lines)
    # Zero means HEAD holds no ledger for this unit at all — a lost `unit new`,
    # which is the one situation 5.8 gives a concrete expert step for.
    facts["committed"] = len(committed_lines)
    facts["tail"] = list(tail)
    facts["seqs"] = list(range(first, first + len(tail) + (1 if partial else 0)))

    pending = pending_dir(repo, unit)
    has_pending = os.path.isdir(pending)
    manifest = read_manifest(repo, unit)
    facts["manifest"] = manifest
    if report_only:
        facts["files"] = classify_manifest_files(repo, unit, manifest)

    if tail or partial:
        if manifest is None:
            # A manifest that is PRESENT but not a complete contract 5.8
            # manifest is invalid material, not absent material. Distinguishing
            # them matters: `no_material` says "there is nothing to resume
            # from", `material_invalid` says "what is here cannot be trusted".
            if os.path.exists(os.path.join(pending, "manifest.json")):
                return answer(
                    "recovery_unsupported",
                    "recovery_unsupported",
                    "material_invalid",
                    "pending/manifest.json is not a complete manifest; nothing "
                    "is restored and the unit directory is preserved",
                )
            return answer(
                "recovery_unsupported",
                "recovery_unsupported",
                "no_material",
                "%d uncommitted event(s) with no manifest; inspect %s — nothing is "
                "restored from HEAD and the unit directory is preserved"
                % (len(tail) + (1 if partial else 0), relative),
            )
        events = manifest["events"]
        for line in events:
            try:
                parsed = json.loads(line)
            except ValueError:
                return answer(
                    "recovery_unsupported",
                    "recovery_unsupported",
                    "event_invalid",
                    "a manifest event line is not valid JSON; nothing written",
                )
            if canonical_line(parsed) != line:
                return answer(
                    "recovery_unsupported",
                    "recovery_unsupported",
                    "event_invalid",
                    "a manifest event line is not canonical; nothing written",
                )
        for entry in manifest["files"]:
            name = entry.get("path")
            if digest_file(after_copy(pending, entry)) != entry.get("after_sha"):
                return answer(
                    "recovery_unsupported",
                    "recovery_unsupported",
                    "material_invalid",
                    "the pending copy of %s does not match its manifest digest"
                    % name,
                )
            before_sha = entry.get("before_sha")
            if before_sha is None:
                marker = os.path.join(pending, "before", name + ".absent")
                if not os.path.exists(marker):
                    return answer(
                        "recovery_unsupported",
                        "recovery_unsupported",
                        "material_invalid",
                        "pending/before/%s.absent is missing" % name,
                    )
            elif digest_file(os.path.join(pending, "before", name)) != before_sha:
                return answer(
                    "recovery_unsupported",
                    "recovery_unsupported",
                    "material_invalid",
                    "pending/before/%s does not match its manifest digest" % name,
                )
        if not _is_batch_prefix(tail, partial, events):
            return answer(
                "recovery_unsupported",
                "recovery_unsupported",
                "tail_unknown",
                "the uncommitted tail of %s is not a prefix of the pending batch; "
                "nothing written" % relative,
            )
        return answer(
            "uncommitted_tail",
            "uncommitted_tail",
            "uncommitted event(s) at seq %d–%d" % (first, facts["seqs"][-1]),
            "dogen resume %s" % unit,
        )

    if not has_pending:
        return answer("clean")

    situation = pending_situation(manifest, complete, committed_lines)
    if situation == PENDING_STRAY:
        # WR-05: NOT a row of contract 5.8's situation table. Some but not all
        # of the manifest's events are in the ledger and none of them is
        # uncommitted, so the material is the only evidence of what a
        # half-applied batch intended — and deleting it silently in write mode
        # contradicts 5.8's honest limit ("every file whose bytes it cannot
        # attribute is preserved"). Classification is identical in read-only
        # mode by the same rule, so the refusal is raised before the write
        # boundary and `show` reports it rather than a would-delete line.
        #
        # WR-03: preserving the material is right; leaving the author with no
        # way out is not. Every verb refuses here, and the routed token used to
        # be `review` — a verb that refuses identically, so the author was
        # routed in a circle. The hint names the one escape this build has, and
        # routing answers `resume` (see :func:`stray_pending_material`), which
        # since plan 17-06 is a real verb that reports the §5.8 honest limit
        # here rather than the transitional stub refusal.
        return answer(
            PENDING_STRAY,
            "recovery_unsupported",
            "material_invalid",
            "pending/ holds a batch only partly present in %s and none of it "
            "uncommitted; the material is preserved and nothing is written — "
            "inspect %s and remove it once its contents are accounted for"
            % (relative, os.path.relpath(pending, os.fspath(repo))),
        )
    if write_mode and not report_only:
        # Silent on purpose: the invocation may still refuse at stage b or c,
        # and GATE-04 allows a non-zero exit exactly one line on stderr and
        # nothing else. Routine recovery housekeeping is not that line. The
        # dry-run path below is where the classification is reportable output.
        cleanup_pending(repo, unit)
        facts["deleted"] = True
        return answer(situation)
    if not report_only:
        # Report mode prints nothing here: `resume --dry-run` renders the same
        # sentence on STDOUT, where its report lives, and the diagnostic helper
        # is stderr-only.
        diagnostic("would delete pending/: %s" % situation)
    return answer(situation)


def stage_a_guard(repo, unit):
    """Contract 5.7 stage a for a mutating verb, stated once (VERB-09).

    Ten verbs opened with a byte-identical copy of these two calls. The order
    is load-bearing and is the reason they stay two functions: an index lock
    another process holds makes every classification below it provisional, so
    ``git_busy`` is asked first — and ``resume`` asks it WITHOUT the raising
    classification that follows here (Pitfall 6).
    """
    git_busy_guard(repo, unit)
    classify_stage_a(repo, unit)


def found_guard(repo, unit, present):
    """``unit_not_found`` (2) when neither a ledger event nor a ``unit.md`` exists.

    Stage c's first row for seven mutating verbs and for the read preamble;
    ``present`` is whatever the caller already read (the event records, or the
    bare existence of the ledger), consulted for truth alone.
    """
    if not present and not os.path.exists(unit_md_path(repo, unit)):
        raise Refusal(
            "unit_not_found",
            unit=unit,
            detail="no unit %r" % unit,
            hint="dogen unit new %s …" % unit,
        )


#: The situation :func:`pending_situation` reports for the one case that is NOT
#: a row of contract 5.8's table: a batch only partly present in the ledger with
#: none of it uncommitted. Named because two places must agree about it.
PENDING_STRAY = "pending_stray"


def pending_situation(manifest, complete, committed_lines):
    """Contract 5.8's situation table for a ``pending/`` with no uncommitted tail.

    Stated ONCE (WR-03): ``classify_stage_a`` decides whether to refuse, and
    :func:`stray_pending_material` decides where to route, and a second opinion
    about the same fact would let the refusal and the routed token disagree —
    which is exactly how the author ended up in a circle.
    """
    if manifest is None:
        return "pending_without_manifest"
    events = set(manifest["events"])
    if events.issubset(set(committed_lines)):
        return "committed_batch_awaiting_cleanup"
    if not events.intersection(set(complete)):
        return "manifest_without_events"
    return PENDING_STRAY


def stray_pending_material(repo, unit):
    """Is this unit in the terminal ``pending_stray`` state? (WR-03)

    Asked separately from ``classify_stage_a`` for the same reason
    :func:`uncommitted_ledger_tail` is: ``derive()`` is pure, so the one I/O
    caller supplies the fact and ``route()`` can restate it. Without it the
    routed ``next`` fell to row 10 and said ``review`` — a verb that refuses
    with the very same refusal, which made the state a loop.

    Since plan 17-06 the routed ``resume`` reaches a real verb, which reports
    this row through the §5.8 honest limit instead of the transitional stub
    refusal. The circle is closed at both ends now: the token names a verb that
    answers, and the answer names the manual escape.

    Never raises: it is consulted on the refusal path, where an exception would
    replace a diagnosable refusal with a crash.
    """
    try:
        complete, partial, committed, _rel = ledger_split(repo, unit)
        if partial:
            return False
        if not os.path.isdir(pending_dir(repo, unit)):
            return False
        if complete[len(committed) :]:
            return False  # an uncommitted tail is row 1's business, not this
        manifest = read_manifest(repo, unit)
        return pending_situation(manifest, complete, committed) == PENDING_STRAY
    except Exception:  # noqa: BLE001 — a refusal's `next` must never itself fail
        return False


def build_event(kind, seq, prev, actor, commit, payload):
    """One contract 5.2 envelope plus the kind's payload."""
    event = {
        "kind": kind,
        "seq": seq,
        "prev": prev,
        "at": utc_now(),
        "actor": {"name": actor["name"], "email": actor["email"]},
        "tool_version": __version__,
        "contract": CONTRACT,
        "commit": commit,
    }
    event.update(payload)
    return event


def next_event(kind, records, actor, commit, payload):
    """The next event in a unit's chain: ``seq`` and ``prev`` read off ``records``.

    Seven verbs computed both from the same two expressions. Deriving them in
    one place is what keeps a future verb from appending at the wrong seq or
    chaining to the wrong line — neither of which ``verify_chain`` could then
    tell apart from a hand edit.
    """
    return build_event(
        kind, len(records), chain_prev(records[-1][1]), actor, commit, payload
    )


def chain_lines(events):
    """Serialize a batch, wiring each ``prev`` to the previous line's bytes."""
    lines = []
    previous = None
    for event in events:
        if previous is not None:
            event["prev"] = chain_prev(previous)
        line = canonical_line(event)
        lines.append(line)
        previous = line
    return lines


#: Contract 5.6's write-destination row, in repo-relative form: the record
#: (``.dogen/units/``) and the pending/evidence material (``.dogen/staging/``)
#: are named explicitly, not just their parent. Checking only ``.dogen`` left
#: the two children reachable through a link of their own (CR-02).
DOGEN_ROOTS = (
    ".dogen",
    os.path.join(".dogen", "staging"),
    os.path.join(".dogen", "units"),
)


def guard_dogen_root(repo, unit=""):
    """Contract 5.6: ``.dogen/`` and its two children are real dirs inside the repo.

    Stated ONCE, so no verb can hold a different opinion of it. ``islink`` is
    checked as well as ``contained`` because a link that happens to point back
    inside the repository still breaks the "the record lives here" invariant the
    rest of the containment reasoning rests on.

    Every level of :data:`DOGEN_ROOTS` is checked, because a containment test
    that resolves BOTH of its operands through the link being tested cancels
    itself out: ``contained(root/.dogen/staging, pending)`` passes for every
    ``pending`` when ``.dogen/staging`` is itself the link. Only a check that
    names the link's own path — ``islink`` — can see it.
    """
    root = os.fspath(repo)
    for relative in DOGEN_ROOTS:
        path = os.path.join(root, relative)
        if os.path.islink(path) or (
            os.path.exists(path) and not contained(repo, path)
        ):
            raise Refusal(
                "bad_write_path",
                unit=unit,
                detail="%s/ is a symlink or resolves outside the repository"
                % relative,
                hint="%s/ must be a real directory inside the repository"
                % relative,
            )


def guard_write_paths(repo, unit, files):
    """Contract 5.6 containment for every destination a verb is about to write.

    The ONE choke point: ``perform_write`` calls this before step 1, so a verb
    cannot forget it and a path that was checked at declaration time but has
    since been re-pointed through a symlink is caught before the append, the
    place and the commit — all three of which precede git ever seeing the
    pathspec, which is what makes a late refusal a durable escape rather than a
    refusal (the transition would already be unrecoverable).

    ``files`` is every destination, the ledger included (WR-02). The second
    element of each tuple is the intended bytes and is ignored here, which is
    what lets the ledger — appended, not placed — be passed as ``(path, None)``.
    """
    root = os.fspath(repo)
    guard_dogen_root(repo, unit)
    docs_root = os.path.join(root, DOCS_ROOT)
    for path, _ in files:
        destination = os.path.join(root, path)
        if not contained(repo, destination):
            raise Refusal(
                "bad_write_path",
                unit=unit,
                detail="%r resolves outside the repository" % path,
                hint="every write destination stays inside the repository",
            )
        if path.startswith(DOCS_ROOT + os.sep) and not contained(
            docs_root, destination
        ):
            raise Refusal(
                "bad_write_path",
                unit=unit,
                detail="%r resolves outside the docs root" % path,
                hint="pages stay inside %s/" % DOCS_ROOT,
            )


def guard_placeable_paths(repo, unit, files):
    """Refuse before step 1 what the FILESYSTEM would refuse at step 3 (CR-01).

    ``guard_ignored_paths`` asks git's opinion of the pathspecs; this asks the
    filesystem's opinion of the same destinations, and the two are independent.
    ``place_files`` runs at step 3 — AFTER the append at step 2 — so every
    ``OSError`` ``publish_atomic``'s ``makedirs``/``open`` can raise arrives once
    the ledger has already been mutated: the unit is left with an uncommitted
    tail that only ``resume`` (a D-16 stub in this build) could clear, and the
    backstop reports it as ``bad_target``/2, the one exit code a skill reads as
    "I mistyped an argument, nothing happened".

    Two ordinary layouts reach it with no crash fixture — a path component that
    is a regular file rather than a directory, and a docs subdirectory that is
    not writable — so this is the same "needs no crash fixture" class the ignore
    probe was added for, asked one syscall earlier while a refusal is still free.

    ``os.access`` is an effective-permission check and therefore over-permissive
    for root, which can create a file in a 0500 directory; the acceptance suite
    skips that case as root for exactly that reason. The over-permissive
    direction is the safe one — it falls back to today's behaviour rather than
    refusing a destination that would in fact have worked.
    """
    root = os.fspath(repo)
    for path, _ in files:
        destination = os.path.join(root, path)
        if os.path.isdir(destination):
            raise Refusal(
                "bad_write_path",
                unit=unit,
                detail="%r is a directory, not a file" % path,
                hint="a write destination is a file; remove the directory or "
                "declare a different target",
            )
        probe = os.path.dirname(destination) or root
        while not os.path.exists(probe):
            above = os.path.dirname(probe)
            if above == probe:  # reached the filesystem root; stop, never loop
                break
            probe = above
        if not os.path.isdir(probe):
            raise Refusal(
                "bad_write_path",
                unit=unit,
                detail="%r cannot be created: %s is not a directory"
                % (path, _relative_to(probe, root)),
                hint="every path component above a destination must be a "
                "directory",
            )
        if not os.access(probe, os.W_OK | os.X_OK):
            raise Refusal(
                "bad_write_path",
                unit=unit,
                detail="%r cannot be created: %s is not writable"
                % (path, _relative_to(probe, root)),
                hint="make the destination's parent directory writable and "
                "retry",
            )


#: git's own UI lines on stderr, which are never paths it named (WR-16).
_GIT_UI_PREFIXES = ("hint:", "warning:", "error:", "fatal:")

#: How many offenders the detail names before it states a count instead. Five
#: keeps the single stderr line readable; the count keeps it honest (WR-16).
_GIT_DETAIL_OFFENDERS = 5


def _git_add_detail(stderr):
    """``git add``'s own words about a refusal, INCLUDING the paths it named.

    The stderr scrape this replaced invented an offender from arbitrary stderr,
    so the hint came back as ``git check-ignore -v fatal: pathspec ... is beyond
    a symbolic link`` — not a command anyone could run (WR-01). Taking only the
    verbatim FIRST line over-corrected: for the ignore case git's first line is
    the constant header ("The following paths are ignored by one of your
    .gitignore files:") and the offenders are on the lines AFTER it, so with
    more than one destination the author was told nothing about which one was
    ignored — and the detail became a constant string for every ignore refusal
    in the tool (WR-12).

    So: git's first line verbatim, plus the lines between it and its ``hint:``
    advice, reported AS GIT'S OWN OUTPUT rather than as an invented "offender".
    Safe to read positionally because the probe pins :data:`IPC_LOCALE`, which
    makes the header ``C``-locale-stable. Single-line stderr — ``fatal:
    pathspec ... is beyond a symbolic link`` — is unchanged, because there is
    nothing after the first line to add.
    """
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    if not lines:
        return "git add failed"
    # WR-16, half one: the positional read ("lines[0] is the header, the rest
    # are paths") holds only while the ignore block is ALONE on stderr. git
    # appends its own diagnostics freely, and filtering `hint:` alone presented
    # `error:`/`fatal:`/`warning:` lines inside the parenthesised list as though
    # they were paths git had named. The prefix set is C-locale-stable because
    # `guard_ignored_paths` pins IPC_LOCALE (phase-16 IN-03).
    named = [line for line in lines[1:] if not line.startswith(_GIT_UI_PREFIXES)]
    if not named:
        return lines[0]
    # WR-16, half two: `named[:3]` dropped the rest in silence, so an author
    # with five ignored destinations fixed three, retried and was refused again
    # -- WR-12's "told nothing about WHICH one", moved from none to the first
    # three. An unbounded list is the worse answer (GATE-04 wants ONE stderr
    # line), so the omission is STATED rather than hidden.
    shown = named[:_GIT_DETAIL_OFFENDERS]
    if len(named) > len(shown):
        shown = shown + ["and %d more" % (len(named) - len(shown))]
    return "%s (%s)" % (lines[0], ", ".join(shown))


def _relative_to(path, root):
    """``path`` spelled from ``root`` when it is inside it, else verbatim."""
    try:
        relative = os.path.relpath(path, root)
    except ValueError:  # different drive on Windows
        return path
    return path if relative.startswith(os.pardir) else relative


def guard_ignored_paths(repo, unit, pathspecs):
    """Refuse before step 1 what ``git add`` would refuse after step 3 (WR-03).

    The contract's write order (append+fsync -> place -> commit) makes every
    failure at step 4 a tail for ``resume``, which this build stubs (D-16) — so
    a target under a gitignored directory, which is an ordinary repo layout and
    needs no crash fixture to reach, wedged the unit for EVERY verb, including
    the read-only ``show`` an author would use to see what happened. Contract
    V17 already names ignore patterns as something ``verify`` checks, so the
    fact is knowable; this asks it one subprocess earlier, while a refusal is
    still free and nothing has been written.

    The probe is ``git add --dry-run``, not ``git check-ignore``, because only
    the former is git's OWN decision. They disagree in both directions: a
    tracked file matching a file-level pattern is reported ignored by
    ``check-ignore --no-index`` and added happily by ``git add``, while a
    tracked file under an ignored DIRECTORY is reported unignored by a bare
    ``check-ignore`` and refused by ``git add``. ``--ignore-missing`` is what
    lets a not-yet-placed destination be asked about at all.

    A non-zero exit is NOT synonymous with "ignored" (WR-01). The probe used to
    scrape stderr for "offenders" — every line that was not blank, not
    ``hint:``-prefixed and did not end in ``:`` — and present whatever it found
    as a path, which turned "pathspec is beyond a symbolic link" into a path and
    produced a ``hint`` that was not a runnable command. The scrape also assumed
    English: under any other ``LC_MESSAGES`` the ``hint:`` filter stops matching
    and git's whole message becomes the "path". So: pin the locale, report git's
    own first line verbatim, and hand back a hint that reproduces the refusal.

    ``index.lock`` is re-probed first because ``git add --dry-run`` takes the
    index lock, so a concurrent git process makes this exit 128 — the contract's
    answer to which is ``git_busy`` (5), not ``bad_write_path`` (2). It is
    checked at stage a too; this narrows the window rather than closing it.

    ``git_busy``, not ``busy``, and WORDED like the seven stage-a sites so the
    two answers cannot drift: ``REASONS`` carries both on exit 5, and this
    codebase uses them for two different things — ``busy`` is dogen's own
    ``.dogen/staging/lock``, ``git_busy`` is ``.git/index.lock`` (which
    :func:`index_lock_present`'s docstring states outright). The exit code
    coincides, so nothing failed; a skill that branches on ``error`` — the field
    contract 5.7 makes the machine-readable one — was told dogen held its own
    lock while the detail said the opposite (WR-11).
    """
    proc = git(
        ["add", "--dry-run", "--ignore-missing", "--"] + list(pathspecs),
        repo,
        env=IPC_LOCALE,
    )
    if proc.returncode == 0:
        return
    git_busy_guard(repo, unit)
    raise Refusal(
        "bad_write_path",
        unit=unit,
        detail="git will not stage this write: %s" % _git_add_detail(proc.stderr),
        hint="`git add --dry-run --ignore-missing -- %s` reproduces this; dogen "
        "commits every path it writes, so a destination git refuses to stage "
        "cannot be recorded" % " ".join(pathspecs),
    )


def seq_range(seqs):
    """``"4"`` for one event, ``"4-7"`` for a batch — the ``Dogen-Seq`` trailer."""
    return str(seqs[0]) if seqs[0] == seqs[-1] else "%d-%d" % (seqs[0], seqs[-1])


#: Shared qualification for all three CLI adoption offers. A new reviewer
#: edit needs an eligible last event that is not itself an adoption, changed
#: bytes, and current bytes for every unexpected file. Unchanged files take a
#: plain resume; a batch already carrying one adoption does NOT — it is
#: completed by a repeated `--adopt` or by `--overwrite`, and a bare `resume`
#: refuses `resume_ambiguous` there. WR-03: the fourth condition
#: used to live only in this comment, so an author was offered `--adopt` on a
#: batch whose last event was already an adoption and got a plain resume that
#: recorded nothing and dropped their note. WR-01 (iteration 9): the sentence
#: below is interpolated into the very `resume_ambiguous` hint the routing
#: tables tell the skills to relay verbatim, so calling the already-adopted
#: case "a plain resume" contradicted the row the operator is routed by — and
#: `test_wr02_already_adopted_batch_requires_an_explicit_choice` proves the
#: tool's own wording wrong: a bare resume there exits 6. S-13 checks
#: inspectability and necessary wording, and now pins this clause against the
#: rows; lifecycle tests exercise the choices against real pending batches.
ADOPT_PRECONDITION = (
    "`--adopt` is an escape ONLY when the batch's last event is a generation "
    "or a reviewer edit THAT WAS NOT ITSELF AN ADOPTION, something REWROTE "
    "the placed bytes, and every unexpected file's current bytes are still on "
    "disk. A deleted file has "
    "no bytes to adopt: it refuses `adopt_unsupported` too; use `--overwrite` "
    "to restore the intended bytes after removing any remaining blocker. "
    "On any other batch it refuses `adopt_unsupported`; with the placed bytes "
    "unchanged it is a plain resume that retries the same transition and "
    "records nothing. A batch already carrying one adoption is completed by a "
    "repeated `--adopt`, which appends no event and records no note, or by "
    "`--overwrite`, which restores the saved adoption bytes; a bare `resume` "
    "refuses `resume_ambiguous` there while any file is still `unexpected`, "
    "and completes the batch only once none is"
)


def escape_hint(repo, unit, otherwise):
    """Add historical context without inferring a present git obstruction.

    transition_attempts is persisted BEFORE git runs, including successful or
    interrupted calls. It cannot tell whether a blocker exists now. Keep the
    caller's remedy at every count: removing a hook does not reset history,
    and plain resume can still require an explicit overwrite decision.

    WR-02(a): the blocker-removal sentence is emitted at EVERY count, and only
    the history clause is conditional. Returning ``otherwise`` verbatim below
    two attempts meant the escape S-13 credited every calling site with was
    absent from the string the operator actually read, at the commonest count
    of all — so a first-attempt refusal on a batch a hook is still rejecting
    named the one command that cannot work, with no warning and no way out.
    The counter is the only thing history can honestly claim; whether
    something is refusing the batch right now is put as a condition, never as
    an assertion.
    """
    attempts = read_progress(repo, unit)["transition_attempts"]
    return (
        "%s remove what is refusing the transition before retrying — a "
        "pre-commit hook, an unstageable pathspec. With nothing refusing it, "
        "%s."
        % (
            "this batch has been attempted %d times; if something is still "
            "refusing it," % attempts
            if attempts > 1
            else "If something is refusing this batch,",
            otherwise,
        )
    )


def refuse_transition(repo, unit, attempts, step, stderr):
    """Step 4's shared failure arm, for BOTH of its git calls (WR-02).

    First failure on a batch: ``uncommitted_tail``, hinting ``dogen resume
    <id>``. One retry is a reasonable thing to offer, and a transient fault is
    the common case.

    Second failure on the SAME batch: the honest limit. Re-raising
    ``uncommitted_tail`` would hand back the hint that just produced this
    refusal — a closed loop with no escape — so the refusal says what is
    blocking the transition and names the way out.

    That way out is REMOVING what is refusing the transition, and both arms'
    hints say so first. The two arms' hints are otherwise SEPARATE sentences
    (WR-06), because they diagnose different faults and only one of them can
    offer ``--adopt``.

    On ``git commit``: a hook ran, so ``--adopt`` is named second and WITH its
    precondition, because the tool applies one — :func:`resume_adopt` refuses
    ``adopt_unsupported`` unless the batch's last event is a generation or a
    reviewer edit that is not itself an adoption, and degrades to a plain
    resume when nothing on disk classifies ``unexpected``. Offered unqualified
    — as it was after the first CR-01 fix — the escape reproduces the very
    refusal it is routed from on every batch except the one shape
    ``hook_restored_draft`` models: a hook that REWROTE the placed bytes of a
    generation or a reviewer edit. A hint that names a command which cannot
    work is the same closed loop one hop longer.

    On ``git add``: no hook ran, nothing on disk is ``unexpected``, and
    ``--adopt`` would degrade to the plain resume that just refused — so it is
    not offered at all, and the hint names the causes that can produce an add
    failure instead.

    The function, counter, preamble and closer stay shared; only the diagnosis
    and conditional escape differ. The two arms drifted once: CR-01(b) added
    the attempt counter to the commit arm only, on the reading that "a pre-commit hook is
    what rejects a batch, and it only ever runs here". ``git add`` also fails
    deterministically — an index that will not lock, a pathspec a ``.gitignore``
    change excluded after :func:`guard_ignored_paths` ran, a read-only ``.git``
    — and there the unconditional hint reproduced its own refusal (WR-02).

    Never returns.
    """
    detail = _first_line(stderr) or "no git output"
    if attempts > 1:
        # WR-03: the two arms are not the same event and must not carry the
        # same `detail`. `detail` is what the four routing mirrors and
        # `dogen-review/SKILL.md` step_10 branch on, and `commit_rejected` sent
        # every one of them to "only the commit was refused — inspect the
        # repository's commit hooks". On a `git add` failure the commit was
        # never attempted: the cause is an index that will not lock, an
        # unstageable pathspec, a read-only `.git`. Right routing, wrong
        # diagnosis, routed BY NAME.
        committing = step == "git commit"
        raise Refusal(
            "recovery_unsupported",
            unit=unit,
            detail="commit_rejected" if committing else "stage_rejected",
            hint=(
                "git has failed to complete this batch %d times (%s: %s); "
                "resuming again would re-place the same bytes and fail the "
                "same way. " % (attempts, step, detail)
                + (
                    "Inspect the repository's commit hooks and `git status`. "
                    if committing else
                    "Inspect `git status` and the index — no hook has run, "
                    "because the commit was never attempted, so what is "
                    "refusing the transition is an unstageable pathspec, an "
                    "index that will not lock, or a read-only `.git`. "
                )
                + "Then remove what is refusing the transition and run `dogen resume "
                "%s` once more — that is the escape that always works. " % unit
                + (
                    '`dogen resume %s --adopt --note "<why>"` keeps the '
                    "current bytes — %s. " % (unit, ADOPT_PRECONDITION)
                    if committing else
                    "`--adopt` is not an answer here and is not offered: it "
                    "adopts bytes a hook rewrote, no hook ran, and with nothing "
                    "on disk `unexpected` it degrades to the plain resume "
                    "that just refused. "
                )
                + "The batch is on the record and the files are placed; %s, "
                "so %s is preserved and holds the recovery material."
                % (
                    "only the commit was refused" if committing else
                    "git could not stage them and nothing was committed",
                    os.path.relpath(pending_dir(repo, unit), os.fspath(repo)),
                )
            ),
            next_token="resume",
            extra={"git": detail, "step": step},
        )
    raise Refusal(
        "uncommitted_tail",
        unit=unit,
        detail="%s failed: %s" % (step, detail),
        hint="dogen resume %s" % unit,
        next_token="resume",
    )


def write_tail(
    repo, unit, phase, entries, pathspecs, seqs, note, head, verdict=None, place=None
):
    """Contract 5.8 steps 3–6: the ONE implementation both writers share.

    :func:`perform_write` reaches it having published and appended its own
    batch; ``resume``'s pass 2 reaches it having truncated and appended what an
    interruption left missing. A second copy of these four steps would drift —
    the trailers, the pathspec discipline, the post-commit check — and the
    drift would only ever show on the RECOVERY path, which by definition runs
    when something has already gone wrong.

    ``entries`` is the manifest's complete ``files[]``, which is what step 5
    checks; ``place`` is the subset step 3 actually writes and defaults to all
    of them. Pass 2 passes only the ``recoverable`` rows: a ``done`` file
    already holds the intended bytes, and re-placing it would move its mtime
    for nothing.

    ``pathspecs`` is a LIST of per-file paths, never a directory and never the
    whole tree. During a recovery the working tree holds whatever the
    interruption left behind, and a sweeping add would commit it in the
    author's name under this tool's trailers (T-17-31).

    Returns the post-commit check's report, so both callers render the same
    hook warnings from the same facts.
    """
    written = place_files(repo, unit, entries if place is None else place)
    # CR-01: step 3 is recorded BEFORE step 4 can fail, because the whole point
    # of the record is to survive a failed commit. `classify_file` reads it to
    # tell "the interruption never got this far" from "this tool wrote the
    # intended bytes here and something else has since replaced them".
    progress = read_progress(repo, unit)
    progress["placed"] = sorted(set(progress["placed"]) | set(written))
    write_progress(repo, unit, progress)
    crash_point("commit")

    before_index = index_snapshot(repo)

    # WR-02: counted BEFORE either git call, so an attempt that dies inside a
    # hook is still an attempt — and so is one that dies in `git add`. The
    # earlier reading, that only a commit can be rejected because "a pre-commit
    # hook is what rejects a batch and it only ever runs here", is too narrow:
    # `git add` fails deterministically for reasons that are not hooks (an
    # index that will not lock, a pathspec a `.gitignore` change excluded after
    # `guard_ignored_paths` ran, a read-only `.git`), and in every one of them
    # the unconditional `dogen resume <id>` hint reproduces its own refusal —
    # the closed loop CR-01(b) exists to break.
    #
    # WR-03: which is why it is `transition_attempts` and not `commit_attempts`.
    # Counted here it covers the add failure, the commit refusal AND the run
    # that dies between the two, so the old name asserted of every increment
    # something that is true of only one. The refusal's own text says "failed to
    # complete this batch %d times", not "git refused it %d times".
    progress["transition_attempts"] = progress["transition_attempts"] + 1
    write_progress(repo, unit, progress)
    attempts = progress["transition_attempts"]

    added = git_add(repo, pathspecs)
    if added.returncode != 0:
        refuse_transition(repo, unit, attempts, "git add", added.stderr)
    seqs_text = seq_range(seqs)
    trailers = [
        ("Dogen-Unit", unit),
        ("Dogen-Phase", phase),
        ("Dogen-Seq", seqs_text),
        ("Dogen-Head", (head or "0" * 40)[:16]),
    ]
    if verdict:
        trailers.append(("Dogen-Verdict", verdict))
    committed = git_commit(
        repo,
        "dogen: %s %s" % (phase, unit),
        collapse_note(note) if note else "",
        trailers,
        pathspecs,
    )
    if committed.returncode != 0:
        refuse_transition(repo, unit, attempts, "git commit", committed.stderr)
    diagnostic(
        "git: committed %s — dogen: %s %s"
        % (git(["rev-parse", "--short", "HEAD"], repo).stdout.strip(), phase, unit)
    )

    changed, extra = post_commit_check(repo, entries, pathspecs, before_index)
    crash_point("cleanup")
    cleanup_pending(repo, unit)
    return {
        "changed": changed,
        "extra": extra,
        "pathspecs": pathspecs,
        "seq_range": seqs_text,
    }


def perform_write(repo, unit, phase, batch_lines, seqs, files, note, head, verdict=None):
    """Contract 5.8 steps 1–6, in order, with the lock held across all of them.

    Step 2 (the append) is the recovery boundary: a crash before it leaves a
    complete manifest with none of its events in the ledger and nothing placed,
    because 2 precedes 3; a crash after it leaves a tail stage a can classify.
    """
    root = os.fspath(repo)
    # WR-02: the ledger is the destination EVERY write appends to, and it used
    # to appear only as a pathspec — never in the set `contained()` sees. The
    # record of truth was the one write destination the containment function was
    # never shown; it survived on the side effect that `git add --dry-run`
    # refuses a pathspec beyond a symlink, which is not a containment check and
    # would stop catching it the moment the probe were relaxed or reordered.
    # One list, all three guards, no destination excepted.
    relative_ledger = os.path.relpath(ledger_path(repo, unit), root)
    destinations = list(files) + [(relative_ledger, None)]
    guard_write_paths(repo, unit, destinations)
    guard_placeable_paths(repo, unit, destinations)
    pathspecs = [path for path, _ in destinations]
    guard_ignored_paths(repo, unit, pathspecs)
    manifest = publish_pending(repo, unit, files, batch_lines)
    entries = manifest["files"]
    crash_point("manifest")

    append_batch(ledger_path(repo, unit), batch_lines)
    crash_point("append")

    return write_tail(
        repo, unit, phase, entries, pathspecs, seqs, note, head, verdict=verdict
    )


#: The commit-subject phase each event kind belongs to. ``resume`` has only the
#: batch to go on — the verb that started the transition is long gone — so the
#: recovery commit is named from the record itself rather than from a fixed
#: "resumed" word that would make a recovered transition unfindable by the same
#: ``git log --grep`` that finds every other one.
PHASE_BY_KIND = {
    "ledger": "declared",
    "unit-declared": "declared",
    "unit-edited": "edited",
    "signoff": "signed-off",
    "steering": "steered",
    "steps-planned": "steps-planned",
    "step-recorded": "step-recorded",
    "generation": "drafted",
    "reviewer-edit": "reviewer-edited",
    "review": "reviewed",
    "retired": "retired",
}


def recovery_phase(events):
    """The phase a recovered batch's commit carries, read off its own kinds.

    The batch's LAST kind names the transition, with one composite: ``unit
    edit --re-sign`` writes a ``unit-edited`` and a ``signoff`` in one batch and
    calls itself ``re-signed``, which neither kind says on its own.
    """
    kinds = [event.get("kind") for event in events]
    if not kinds:
        return "resumed"
    if "unit-edited" in kinds and "signoff" in kinds:
        return "re-signed"
    return PHASE_BY_KIND.get(kinds[-1], "resumed")


def truncate_partial_line(path):
    """Drop a ledger's half-written final line (contract 5.8 pass 2, step 1).

    An interruption can only ever truncate inside :func:`append_batch`'s single
    ``write()``, so everything up to the last LF is whole and everything after
    it is the fragment. A ledger with no LF at all is entirely fragment, and
    ``rfind`` answering ``-1`` truncates it to zero — which is right: seq 0 was
    never completely written, so there is no record yet.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    with open(path, "r+b") as handle:
        handle.truncate(data.rfind(b"\n") + 1)
        handle.flush()
        os.fsync(handle.fileno())


def _first_line(text):
    """The first non-empty line of a subprocess's stderr, for a refusal detail."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def report_hook_changes(result, repo, existing_drift=None):
    """Warn about what a hook did, by name, and never undo any of it (5.8 step 5).

    IN-01 (phase 17): ``repo`` is REQUIRED. It used to default to ``None``
    while ``digest_file(os.path.join(os.fspath(repo), path))`` ran for every
    path in ``existing_drift`` — and this code runs AFTER the commit, so a
    future caller passing drift without a repo would crash a transition that
    had already landed. Ten of the eleven call sites passed neither argument,
    which is exactly what kept the trap invisible.

    ``existing_drift`` maps paths to their pre-resume disk digests. Only bytes
    unchanged in BOTH HEAD and on disk are carried drift; a new rewrite on
    that same path still needs the hook warning. With no mismatches or extra
    paths, stay silent.
    """
    existing_drift = existing_drift or {}
    for path in result["changed"]:
        carried = False
        if path in existing_drift:
            blob = git_show_blob(repo, "HEAD", path)
            head_sha = sha256_bytes(blob) if blob is not None else None
            disk_sha = digest_file(os.path.join(os.fspath(repo), path))
            carried = head_sha == disk_sha == existing_drift[path]
        if carried:
            diagnostic("%s still differs from the recorded bytes after resume" % path)
        else:
            diagnostic("hook changed %s after recording" % path)
    if result["extra"]:
        diagnostic("hook staged unrelated paths: %s" % ", ".join(result["extra"]))


# --- verbs ------------------------------------------------------------------


def unit_dir(repo, unit):
    """``<repo>/.dogen/units/<id>``."""
    return os.path.join(os.fspath(repo), ".dogen", "units", unit)


def unit_md_path(repo, unit):
    """``<repo>/.dogen/units/<id>/unit.md``."""
    return os.path.join(unit_dir(repo, unit), "unit.md")


def uncommitted_ledger_tail(repo, unit):
    """Is any of the unit's ledger on disk but not in HEAD? (contract 5.5 row 1)

    The same comparison ``classify_stage_a`` makes, asked separately so the
    derived state can CARRY the fact. ``derive()`` is pure (D-19), so the one
    I/O caller has to supply it — and without it ``route()``'s first row was
    unreachable and a wedged unit routed a skill at ``review`` (WR-02).
    """
    complete, partial, committed, _rel = ledger_split(repo, unit)
    return bool(complete[len(committed) :] or partial)


def unit_state(repo, unit, staging=None):
    """Derive one unit's whole state from its ledger and one fs snapshot."""
    records = read_events(ledger_path(repo, unit), unit)
    events = [event for event, _ in records]
    targets = []
    basis_paths = []
    partial = derive(events, {"unit_md_sha": None, "paths": {}})
    targets = partial["targets"]
    basis_paths = partial["basis_files"]
    snapshot = read_fs(repo, unit, basis_paths, targets)
    return derive(
        events,
        snapshot,
        staging,
        uncommitted_tail=uncommitted_ledger_tail(repo, unit),
        pending_stray=stray_pending_material(repo, unit),
    )


def next_token_for(repo, unit):
    """The routed token for a unit, or ``show`` when it cannot be derived."""
    try:
        return route(unit_state(repo, unit))
    except Exception:  # noqa: BLE001 — a refusal's `next` must never itself fail
        return "show"


def derivation_failure(error):
    """One short phrase naming why a post-commit state derivation failed (CR-01).

    A `Refusal` carries the machine-readable `reason` the author will look up;
    anything else is a bug or an environment failure and only its type is
    dependable. Either way this is prose in a stderr diagnostic, never the
    refusal line — the transition it follows has already committed.
    """
    if isinstance(error, Refusal):
        return "%s: %s" % (error.reason, error.detail) if error.detail else error.reason
    return "%s: %s" % (type(error).__name__, error)


def unit_claims(repo, unit):
    """A sibling's claim-relevant state, derived from its LEDGER alone (CR-06).

    ``retired`` and ``targets`` are both read out of the ledger by ``derive()``;
    neither consults the filesystem snapshot. So a unit whose *page* dogen
    declines to digest still has a knowable claim set, and :func:`find_claim`
    can answer contract 5.1 without it -- which is what keeps one symlinked page
    in one unit from wedging ``unit new`` / ``signoff`` for every other unit.
    """
    records = read_events(ledger_path(repo, unit), unit)
    return derive(
        [event for event, _ in records], {"unit_md_sha": None, "paths": {}}
    )


def find_claim(repo, unit, targets):
    """Contract 5.1's claim policy: is any target held by another live unit?"""
    units = os.path.join(os.fspath(repo), ".dogen", "units")
    if not os.path.isdir(units):
        return None
    wanted = set(targets)
    for other in sorted(os.listdir(units)):
        if other == unit:
            continue
        if not os.path.exists(ledger_path(repo, other)):
            continue
        try:
            state = unit_state(repo, other)
        except Refusal as unreadable:
            # WR-04: this used to be `except ValueError: continue`, and the only
            # ValueError that reached it was `json.loads` failing inside
            # `read_events` — exactly the corrupt or half-written sibling the
            # contract's first mechanism promises will refuse loudly. Swallowing
            # it made that sibling's targets vanish from the claim set, so
            # `unit new` / `unit edit` / `signoff` happily claimed a target
            # another live unit holds (contract 5.1). A record we cannot read is
            # a record whose claims we cannot rule out.
            #
            # CR-06: that argument is about a record we cannot READ, and the
            # CR-05 fix silently widened the input to "any page dogen declines
            # to digest", which is not the same set. `bad_write_path` from
            # `contained_page` means the signoff WAS read and only the page's
            # digest was withheld — the claim set is knowable, so fall through
            # rather than take out every other unit's `unit new` / `signoff`.
            # The whitelist is deliberately one reason wide: anything else,
            # named or not yet invented, still fails closed.
            if unreadable.reason == "bad_write_path":
                state = unit_claims(repo, other)
            else:
                raise Refusal(
                    "ledger_corrupt",
                    unit=unit,
                    detail="unit %s cannot be read, so its claims cannot be checked (%s)"
                    % (other, unreadable.detail),
                    hint="dogen show %s — the claim policy needs every live unit's "
                    "current signoff" % other,
                    next_token="show",
                )
        if state["retired"]:
            continue
        overlap = sorted(wanted.intersection(state["targets"]))
        if overlap:
            return (other, overlap)
    return None


def unit_invalid_refusal(invalid, unit=""):
    """Map a :class:`UnitInvalid` to contract 5.6's exit-2 refusal.

    The 1-based line and the flag that fixes it are the whole point of the
    structured error: "line 7: intent must be one of …" plus "fix it with
    --intent" is an instruction, where "invalid unit.md" is a riddle. This is
    the ONE mapping site, so every verb that reads a ``unit.md`` refuses
    identically.
    """
    return Refusal(
        "unit_invalid",
        unit=unit,
        detail="line %d: %s" % (invalid.line, invalid.detail),
        hint="fix it with %s" % (invalid.flag or "--body-file"),
    )


def load_unit(repo, unit):
    """Read and parse a unit's ``unit.md`` into ``(text, frontmatter, body)``.

    An absent file is 2 ``unit_not_found``; a file outside the contract 5.6
    subset is 2 ``unit_invalid`` naming the line and the flag.
    """
    path = unit_md_path(repo, unit)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        raise Refusal(
            "unit_not_found",
            unit=unit,
            detail="no unit %r (expected %s)"
            % (unit, os.path.relpath(path, os.fspath(repo))),
            hint="dogen unit new %s …" % unit,
        )
    try:
        frontmatter, body = parse_unit_md(text)
    except UnitInvalid as invalid:
        raise unit_invalid_refusal(invalid, unit)
    return text, frontmatter, body


def guard_targets(repo, unit, targets):
    """Contract 5.6's target rule, then containment for every destination."""
    root = os.fspath(repo)
    checked = validate_targets(targets, unit)
    docs_root = os.path.join(root, DOCS_ROOT)
    if not contained(repo, docs_root):
        raise Refusal(
            "bad_write_path",
            unit=unit,
            detail="the docs root resolves outside the repository",
            hint="%s/ must be a real directory inside the repository" % DOCS_ROOT,
        )
    for target in checked:
        if not contained(docs_root, os.path.join(docs_root, target)):
            raise Refusal(
                "bad_write_path",
                unit=unit,
                detail="target %r resolves outside the docs root" % target,
                hint="targets stay inside %s/" % DOCS_ROOT,
            )
    return checked


def claim_guard(repo, unit, targets):
    """Contract 5.1's claim policy — ONE check on every claiming path.

    ``unit new``, ``unit edit`` and ``signoff`` all call this and nothing else.
    A second implementation is exactly how the three paths would drift apart,
    and the contract states the rule once for that reason.
    """
    claim = find_claim(repo, unit, targets)
    if claim is None:
        return
    holder, overlap = claim
    raise Refusal(
        "target_claimed",
        unit=unit,
        detail="%s is claimed by unit %s" % (", ".join(overlap), holder),
        hint='dogen unit retire %s --note "…"' % holder,
    )


def retired_guard(state, unit):
    """Contract 5.7: `retired` is the first precondition of every mutating verb."""
    if state.get("retired"):
        raise Refusal(
            "retired",
            unit=unit,
            detail="unit %s is retired" % unit,
            hint="a retired unit records nothing further",
            next_token="retired",
        )


def signoff_guard(state, unit):
    """Contract 5.7: `no_signoff` follows `retired` for every gated write verb.

    The symmetric sibling of :func:`retired_guard`. Five verbs asked the same
    question with the same detail, hint and routed token; stating it once is
    what keeps a later wording change from reaching four call sites and missing
    the fifth.
    """
    if state.get("so") is None:
        raise Refusal(
            "no_signoff",
            unit=unit,
            detail="unit %s has no recorded signoff" % unit,
            hint="dogen signoff %s" % unit,
            next_token=route(state),
        )


def actionable_guard(state, unit):
    """Contract 5.7 c: a step walk belongs to an actionable unit (WR-04).

    The third sibling of :func:`retired_guard` and :func:`signoff_guard`, and
    the raiser `not_actionable` never had. The reason sat in ``REASONS`` and in
    the contract's table at exit 2 while `plan-steps` and `step` recorded step
    evidence for a `reference` unit quite happily — and the three skills' own
    routing tables already told the author what the refusal means and where it
    routes, so the surface documented a gate the tool did not have.

    Reached only after :func:`signoff_guard`, so the signoff exists and its
    ``intent`` is the declared direction contract 5.4 derives everything else
    from.
    """
    intent = (state.get("so") or {}).get("intent")
    if intent in ACTIONABLE_INTENTS:
        return
    raise Refusal(
        "not_actionable",
        unit=unit,
        detail="unit %s declares intent %r; a step walk belongs to a tutorial "
        "or a how-to" % (unit, intent),
        hint="reference and explanation pages are drafted straight from the "
        "declared sources: dogen draft %s <staging file|dir>" % unit,
        next_token=route(state),
    )


def guard_source_files(repo, sources, unit=""):
    """The FILESYSTEM half of the source rule, asked by every verb that reads it.

    WR-17: the declaring verbs applied only the STRING rules
    (:func:`validate_source`) while the filesystem ones lived in
    :func:`sign_sources` alone, so ``unit new --source docs/absent.rst`` committed
    a plan ``signoff`` could never sign -- and `--source` REPLACES the list
    rather than clearing it, so the hint's own instruction ("remove it") named
    an action no verb performs. Asked in stage b, the refusal happens before
    anything is written and the dead end is never recorded.

    ``signoff`` asks again rather than trusting the declaration, because
    ``unit.md`` is a plain file an author may hand-edit and a source can be
    deleted between the two calls. Declaration-time validation is the earlier
    guard on the same door, never the only one.

    ``unit_invalid``/``--source``, the answer both declaring verbs already give
    for a bad source STRING, so the two halves of one rule cannot drift apart.
    """
    root = os.fspath(repo)
    for path in sources:
        full = os.path.join(root, path)
        # The rule a string check cannot see: a repo-relative source whose own
        # parent is a symlink out of the tree.
        if not contained(repo, full):
            raise Refusal(
                "unit_invalid",
                unit=unit,
                detail="source %r resolves outside the repository" % path,
                hint="%s takes a repo-relative path inside the repository; a "
                "source dogen cannot read is a source it cannot record"
                % _UNIT_FLAGS["sources"],
            )
        # Checked BEFORE `git log`, because `git log -- <dir>` pins a directory
        # happily: recording that hash for a path nothing digested is an
        # assertion of provenance for something never read (WR-13).
        if not os.path.isfile(full):
            raise Refusal(
                "unit_invalid",
                unit=unit,
                detail="source %r is not a readable file in the repository" % path,
                hint="%s names an existing regular file; point it at one with "
                "dogen unit edit -- a source dogen cannot read is a source it "
                "cannot record" % _UNIT_FLAGS["sources"],
            )
    return list(sources)


def sign_sources(repo, frontmatter, unit=""):
    """``sources[{path, commit|null}]`` and ``context:{path: sha256}`` for a signoff.

    ``commit`` is the last commit to touch the source, or ``None`` when nothing
    pins it — a recorded ``null`` states that fact rather than hiding it.

    The loop's contract is that EVERY declared source is a readable regular
    file, or the signoff refuses. So ``sources`` and ``context`` are the same
    key set by construction, which is the invariant V19 ("context digests vs
    signoff") wants, and ``commit: null`` means exactly one thing.

    A source dogen cannot read REFUSES (WR-05, WR-13). It used to be recorded as
    ``{"path": …, "commit": None}`` with no digest and the loop simply
    ``continue``d, so the signoff succeeded with no indication that a declared
    source had never been read — and ``commit: null`` is already this record's
    encoding for "an in-repo source nothing pins", so one value carried two
    incompatible meanings and V19 saw an absence it could not attribute.
    Silently downgrading a PROVENANCE record is the failure mode the whole
    design is against.

    WR-05's fix closed the out-of-repo STRING and stopped there, leaving the two
    in-repo cases that reach this loop and read nothing (WR-13). A MISSING
    source signed as ``{"commit": null}`` with no digest — the same overloading,
    unchanged. A source naming a DIRECTORY was worse: ``git log`` pins a
    directory happily, so it recorded a real commit hash — an assertion of
    provenance — for something ``digest_file`` never read at all. Declaration-time validation cannot be the only guard,
    because ``unit.md`` is a plain file an author may hand-edit and ``signoff``
    re-reads it fresh — so the answer here is the one ``unit new`` and
    ``unit edit`` already give for the same string: ``unit_invalid``/``--source``.
    """
    root = os.fspath(repo)
    sources = []
    context = {}
    for path in frontmatter.get("sources") or []:
        # The same string rules the declaring verbs apply — absolute, traversing
        # or backslashed — refused with the identical message.
        validate_source(path, unit)
        # WR-17: the same two filesystem rules the declaring verbs now apply,
        # asked again here because unit.md is hand-editable and a source can be
        # deleted between the declaration and the signature.
        guard_source_files(repo, [path], unit)
        full = os.path.join(root, path)
        proc = git(["log", "-1", "--format=%H", "--", path], repo)
        commit = proc.stdout.strip() if proc.returncode == 0 else ""
        # `commit: null` now means exactly one thing: an in-repo source nothing
        # pins. Neither an out-of-repo, a missing nor a directory source can
        # reach this line.
        sources.append({"path": path, "commit": commit or None})
        digest = digest_file(full)
        if digest is None:
            # isfile() said yes and the read still failed — a permission or I/O
            # fault. Refusing keeps `sources` and `context` the same key set;
            # `continue` would put the overloading straight back.
            raise Refusal(
                "unit_invalid",
                unit=unit,
                detail="source %r cannot be digested" % path,
                hint="%s names a readable regular file" % _UNIT_FLAGS["sources"],
            )
        context[path] = digest
    return sources, context


def _scalar(text, key, unit=""):
    """Sanitise one frontmatter scalar; a deviation names the flag that fixes it."""
    if "\r" in text:
        raise Refusal(
            "unit_invalid",
            unit=unit,
            detail="%s contains a carriage return" % key,
            hint="pass %s without \\r" % _UNIT_FLAGS.get(key, key),
        )
    cleaned = "".join(c for c in text if c in ("\n", "\t") or ord(c) >= 32)
    if not cleaned.strip():
        raise Refusal(
            "unit_invalid",
            unit=unit,
            detail="%s is empty or whitespace only" % key,
            hint="pass a value to %s" % _UNIT_FLAGS.get(key, key),
        )
    return cleaned


def read_body(spec, unit=""):
    """``--body-file -`` reads stdin; anything else is a path."""
    if spec == "-":
        try:
            # Read bytes and decode explicitly: Python's stdin text wrapper can
            # use ``surrogateescape`` for invalid bytes, so ``read()`` need not
            # raise the UnicodeDecodeError this refusal is meant to catch.
            text = sys.stdin.buffer.read().decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise Refusal(
                "unit_invalid",
                unit=unit,
                detail="the body read from stdin is not UTF-8 text",
                hint="pass a UTF-8 body, or --body-file F naming a UTF-8 file",
            )
    else:
        try:
            with open(spec, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError as bad:
            # OSError, not the three-member tuple: a permission-denied or
            # full-disk read is "cannot be read" just as much as an absent one,
            # and the narrow tuple let it escape main() as a traceback (CR-04).
            raise Refusal(
                "unit_invalid",
                unit=unit,
                detail="--body-file %s cannot be read (%s)"
                % (spec, type(bad).__name__),
                hint="pass an existing readable file, or - to read the body from stdin",
            )
        except UnicodeDecodeError:
            # NOT an OSError — it is a ValueError — so the single most common
            # "this file cannot be read as text" sailed past the specific
            # refusal and landed in main's generic ValueError arm as
            # `bad_target` with an EMPTY hint, where contract 5.6 says a body
            # deviation is `unit_invalid` with the flag that fixes it (WR-04).
            raise Refusal(
                "unit_invalid",
                unit=unit,
                detail="--body-file %s is not UTF-8 text" % spec,
                hint="pass a UTF-8 file, or - to read the body from stdin",
            )
    if "\r" in text:
        raise Refusal(
            "unit_invalid",
            unit=unit,
            detail="the body contains a carriage return",
            hint="pass --body-file content with LF line endings",
        )
    return text


def read_note(args, unit=""):
    """``--note TEXT`` or ``--note-file -|F``, then contract 5.6's note rule.

    The bytes are recorded verbatim: no trailing newline is stripped and no
    whitespace is folded, because the round-trip claim ("what the author wrote
    re-reads byte for byte") is only true if nothing quietly edits it.
    """
    spec = getattr(args, "note_file", None)
    if spec is None:
        return validate_note(getattr(args, "note", None), unit)
    if spec == "-":
        try:
            text = sys.stdin.read()
        except UnicodeDecodeError:
            raise Refusal(
                "note_required",
                unit=unit,
                detail="the note read from stdin is not UTF-8 text",
                hint="pass a UTF-8 note, or --note-file F naming a UTF-8 file",
            )
    else:
        try:
            with open(spec, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError as bad:
            raise Refusal(
                "note_required",
                unit=unit,
                detail="--note-file %s cannot be read (%s)"
                % (spec, type(bad).__name__),
                hint="pass an existing readable file, or - to read the note from stdin",
            )
        except UnicodeDecodeError:  # a ValueError, not an OSError (WR-04)
            raise Refusal(
                "note_required",
                unit=unit,
                detail="--note-file %s is not UTF-8 text" % spec,
                hint="pass a UTF-8 file, or - to read the note from stdin",
            )
    return validate_note(text, unit)


def cmd_unit_new(args):
    """``unit new`` — stages a–f in order (contract 5.7), then one response line."""
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()
    root = os.fspath(repo)

    # acquire_lock() now guards this itself (CR-02), which is what covers the
    # other six mutating verbs; the explicit call is kept because this verb is
    # the one that CREATES .dogen/, and the refusal reads better from here.
    guard_dogen_root(repo, unit)

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ---------------------------------------------
        validate_unit_id(unit)
        targets = guard_targets(repo, unit, [args.target] + list(args.also_target or []))
        if args.intent not in INTENTS:
            raise Refusal(
                "unit_invalid",
                unit=unit,
                detail="intent must be one of %s" % ", ".join(INTENTS),
                hint="pass %s" % _UNIT_FLAGS["intent"],
            )
        identity = git_identity(repo)
        frontmatter = {
            "title": _scalar(args.title, "title", unit),
            "intent": args.intent,
            "audience": _scalar(args.audience, "audience", unit),
            "targets": targets,
        }
        sources = list(args.source or [])
        if sources:
            frontmatter["sources"] = guard_source_files(
                repo,
                check_count_cap(
                    "sources",
                    validate_sources(
                        [_scalar(s, "sources", unit) for s in sources], unit
                    ),
                    MAX_ORIGINS,
                ),
                unit,
            )
        if args.notes:
            frontmatter["notes"] = check_byte_cap(
                "notes", _scalar(args.notes, "notes", unit), MAX_NOTE_BYTES
            )
        body = read_body(args.body_file, unit)
        unit_text = render_unit_md(frontmatter, body)
        try:
            parse_unit_md(unit_text)
        except UnitInvalid as invalid:
            raise unit_invalid_refusal(invalid, unit)

        # --- c: per-verb preconditions, in the listed order -------------------
        if os.path.exists(unit_md_path(repo, unit)) or os.path.exists(
            ledger_path(repo, unit)
        ):
            raise Refusal(
                "unit_exists",
                unit=unit,
                detail="a unit named %r already exists" % unit,
                hint="dogen unit edit %s" % unit,
                next_token=next_token_for(repo, unit),
            )
        claim_guard(repo, unit, targets)

        # --- d: no-op recognition — none for unit new -------------------------
        # --- e: content gates — none for unit new -----------------------------
        # --- f: write ---------------------------------------------------------
        head = git_head(repo)
        unit_bytes = unit_text.encode("utf-8")
        events = [
            build_event(
                "ledger",
                0,
                None,
                identity,
                head,
                {"v": CONTRACT, "unit": unit, "docs_root": DOCS_ROOT},
            ),
            build_event(
                "unit-declared",
                1,
                None,
                identity,
                head,
                {
                    "unit_hash": sha256_bytes(unit_bytes),
                    "frontmatter": frontmatter,
                },
            ),
        ]
        batch_lines = chain_lines(events)
        files = [
            (os.path.relpath(unit_md_path(repo, unit), root), unit_bytes),
        ]
        attributes = os.path.join(root, ".dogen", ".gitattributes")
        if not os.path.exists(attributes):
            # LEDG-03: the chain hashes raw bytes, so git must never apply a
            # text filter to a ledger. This pin is load-bearing, not cosmetic.
            files.append((os.path.join(".dogen", ".gitattributes"), b"*.jsonl -text\n"))
        result = perform_write(
            repo,
            unit,
            "declared",
            batch_lines,
            (0, 1),
            files,
            args.notes or frontmatter["title"],
            head,
        )
        report_hook_changes(result, repo)

        # State is re-derived after the commit, so a hook that rewrote a recorded
        # file routes the author at what is now true rather than at what we meant.
        next_token = next_token_for(repo, unit)
        segments = [
            "declared %s" % unit,
            os.path.relpath(unit_md_path(repo, unit), root),
            "%d target(s) recorded, none signed off yet" % len(targets),
        ]
        return respond(segments, next_token, as_json)



def cmd_signoff(args):
    """``signoff`` — the HITL gate act: freeze sha256 of the WHOLE ``unit.md``.

    Stages a–f in contract 5.7's order. Stage c is `retired` then the claim
    policy, exactly as the verb's row lists them; stage d is `already_signed`
    keyed on an unchanged ``plan_hash``. ``--force`` is deliberately absent:
    ``slim@357c513``'s ``dogen-signoff.sh --force`` wrote a second signoff row,
    VERB-01 removes the flag, and the replacement is this no-op plus
    ``unit edit --re-sign``.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()
    root = os.fspath(repo)

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ---------------------------------------------
        validate_unit_id(unit)
        text, frontmatter, _ = load_unit(repo, unit)
        targets = guard_targets(repo, unit, frontmatter["targets"])
        identity = git_identity(repo)
        # GATE-06: the whole file, frontmatter and body together, so any byte a
        # hand edit changes sets plan_stale.
        plan_hash = sha256_bytes(text.encode("utf-8"))

        # --- c: per-verb preconditions, in the listed order -------------------
        records = read_events(ledger_path(repo, unit), unit)
        state = unit_state(repo, unit)
        retired_guard(state, unit)
        claim_guard(repo, unit, targets)

        # --- d: no-op recognition ---------------------------------------------
        so = state["so"]
        if so is not None and so.get("plan_hash") == plan_hash:
            raise Refusal(
                "already_signed",
                unit=unit,
                detail="unit.md is unchanged since the signoff at seq %s" % so.get("seq"),
                hint="dogen unit edit %s … --re-sign amends a signed plan" % unit,
                next_token=route(state),
                extra={"seq": so.get("seq"), "commit": so.get("commit")},
            )

        # --- e: content gates — none for signoff ------------------------------
        # --- f: write ---------------------------------------------------------
        head = git_head(repo)
        events = []
        if not records:
            # Adoption: a unit directory with no ledger is brought under the
            # record by ONE batch — ledger + unit-declared(adopted) + signoff.
            events.append(
                build_event(
                    "ledger",
                    0,
                    None,
                    identity,
                    head,
                    {"v": CONTRACT, "unit": unit, "docs_root": DOCS_ROOT},
                )
            )
            events.append(
                build_event(
                    "unit-declared",
                    1,
                    None,
                    identity,
                    head,
                    {
                        "unit_hash": plan_hash,
                        "frontmatter": frontmatter,
                        "adopted": True,
                    },
                )
            )
        events.append(
            signoff_event(
                repo,
                unit,
                len(records) + len(events),
                identity,
                head,
                frontmatter,
                targets,
                plan_hash,
                so,
            )
        )
        events[0]["prev"] = chain_prev(records[-1][1]) if records else None
        seqs = [event["seq"] for event in events]

        # unit.md travels with every signoff: the commit then carries the exact
        # bytes the plan_hash froze, even when the author edited it by hand.
        files = [(os.path.relpath(unit_md_path(repo, unit), root), text.encode("utf-8"))]
        attributes = os.path.join(root, ".dogen", ".gitattributes")
        if not os.path.exists(attributes):
            files.append((os.path.join(".dogen", ".gitattributes"), b"*.jsonl -text\n"))

        result = perform_write(
            repo,
            unit,
            "signed-off",
            chain_lines(events),
            seqs,
            files,
            frontmatter["title"],
            head,
        )
        report_hook_changes(result, repo)

        next_token = next_token_for(repo, unit)
        segments = [
            "signed off %s" % unit,
            "plan_hash %s" % plan_hash[:12],
            "%d target(s) frozen" % len(targets),
            describe_orphans(so, targets),
        ]
        return respond(segments, next_token, as_json)


def signoff_event(repo, unit, seq, identity, head, frontmatter, targets, plan_hash, previous):
    """The contract 5.3 `signoff` payload, built in ONE place.

    Both `signoff` and `unit edit --re-sign` append this event, so the payload
    has exactly one builder: two would drift on the day a field is added.
    """
    sources, context = sign_sources(repo, frontmatter, unit)
    return build_event(
        "signoff",
        seq,
        None,
        identity,
        head,
        {
            "plan_hash": plan_hash,
            "intent": frontmatter["intent"],
            "audience": frontmatter["audience"],
            "title": frontmatter["title"],
            "targets": list(targets),
            "sources": sources,
            "context": context,
            "supersedes": previous.get("seq") if previous is not None else None,
        },
    )


def cmd_unit_edit(args):
    """``unit edit`` — amend the plan; ``--re-sign`` lands it as ONE commit.

    Stage c is the contract's order: `unit_not_found` (2), `retired`, then the
    claim policy when the targets change. Stage d is `noop_unchanged` — both
    the frontmatter and the body unchanged — or, under ``--re-sign`` with a
    plan that is already signed at these bytes, `already_signed`. Stage f
    appends `unit-edited` and, with ``--re-sign``, the `signoff` in the SAME
    batch: one command, one commit, one `Dogen-Seq: n-m`.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()
    root = os.fspath(repo)

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ----------------------------------------------
        validate_unit_id(unit)
        for supplied in ([args.target] if args.target is not None else []) + list(
            args.also_target or []
        ):
            validate_target(supplied, unit)
        text, frontmatter, body = load_unit(repo, unit)
        records = read_events(ledger_path(repo, unit), unit)
        if not records:
            # A plan file with no record: adoption is `signoff`'s 3-event batch
            # (contract 5.3), never an edit, so the tool says which verb adopts.
            raise Refusal(
                "unit_not_found",
                unit=unit,
                detail="unit %s has a unit.md but no ledger" % unit,
                hint="dogen signoff %s adopts an existing plan file" % unit,
            )
        identity = git_identity(repo)

        updated = dict(frontmatter)
        if args.title is not None:
            updated["title"] = _scalar(args.title, "title", unit)
        if args.intent is not None:
            if args.intent not in INTENTS:
                raise Refusal(
                    "unit_invalid",
                    unit=unit,
                    detail="intent must be one of %s" % ", ".join(INTENTS),
                    hint="pass %s" % _UNIT_FLAGS["intent"],
                )
            updated["intent"] = args.intent
        if args.audience is not None:
            updated["audience"] = _scalar(args.audience, "audience", unit)
        if args.notes is not None:
            updated["notes"] = check_byte_cap(
                "notes", _scalar(args.notes, "notes", unit), MAX_NOTE_BYTES
            )
        if args.source is not None:
            updated["sources"] = guard_source_files(
                repo,
                check_count_cap(
                    "sources",
                    validate_sources(
                        [_scalar(source, "sources", unit) for source in args.source],
                        unit,
                    ),
                    MAX_ORIGINS,
                ),
                unit,
            )
        if args.target is not None or args.also_target:
            # --target replaces the list; --also-target appends to whatever the
            # list is after that, so `--also-target` alone adds to the plan.
            base = [args.target] if args.target is not None else list(frontmatter["targets"])
            updated["targets"] = base + list(args.also_target or [])
        targets = guard_targets(repo, unit, updated["targets"])
        updated["targets"] = targets
        new_body = read_body(args.body_file, unit) if args.body_file is not None else body
        new_text = render_unit_md(updated, new_body)
        try:
            parse_unit_md(new_text)
        except UnitInvalid as invalid:
            raise unit_invalid_refusal(invalid, unit)
        plan_hash = sha256_bytes(new_text.encode("utf-8"))

        # --- c: per-verb preconditions, in the listed order -------------------
        state = unit_state(repo, unit)
        retired_guard(state, unit)
        if args.re_sign or targets != list(frontmatter["targets"]):
            claim_guard(repo, unit, targets)

        # --- d: no-op recognition ---------------------------------------------
        so = state["so"]
        changed = updated != frontmatter or new_body != body
        if not changed:
            if not args.re_sign:
                seen = [event for event, _ in records]
                existing = _later(
                    _last_of(seen, "unit-edited"), _last_of(seen, "unit-declared")
                )
                raise Refusal(
                    "noop_unchanged",
                    unit=unit,
                    detail="neither the frontmatter nor the body changed",
                    hint="pass a flag that changes the plan, or drop the command",
                    next_token=route(state),
                    extra={
                        "seq": existing.get("seq") if existing is not None else None,
                        "commit": existing.get("commit") if existing is not None else None,
                    },
                )
            if so is not None and so.get("plan_hash") == plan_hash:
                raise Refusal(
                    "already_signed",
                    unit=unit,
                    detail="unit.md is unchanged since the signoff at seq %s"
                    % so.get("seq"),
                    hint="edit the plan first — a re-sign records an amendment",
                    next_token=route(state),
                    extra={"seq": so.get("seq"), "commit": so.get("commit")},
                )

        # --- e: content gates — none for unit edit -----------------------------
        # --- f: write ----------------------------------------------------------
        head = git_head(repo)
        batch = []
        if changed:
            batch.append(
                build_event(
                    "unit-edited",
                    len(records),
                    None,
                    identity,
                    head,
                    {
                        "unit_hash_before": sha256_bytes(text.encode("utf-8")),
                        "unit_hash_after": plan_hash,
                        "frontmatter": updated,
                    },
                )
            )
        if args.re_sign:
            batch.append(
                signoff_event(
                    repo,
                    unit,
                    len(records) + len(batch),
                    identity,
                    head,
                    updated,
                    targets,
                    plan_hash,
                    so,
                )
            )
        batch[0]["prev"] = chain_prev(records[-1][1])
        seqs = [event["seq"] for event in batch]
        files = [(os.path.relpath(unit_md_path(repo, unit), root), new_text.encode("utf-8"))]

        result = perform_write(
            repo,
            unit,
            "re-signed" if args.re_sign else "edited",
            chain_lines(batch),
            seqs,
            files,
            updated["title"],
            head,
        )
        report_hook_changes(result, repo)

        next_token = next_token_for(repo, unit)
        if args.re_sign:
            segments = [
                "re-signed %s" % unit,
                "plan_hash %s" % plan_hash[:12],
                "%d target(s) frozen" % len(targets),
                describe_orphans(so, targets),
            ]
        else:
            segments = [
                "edited %s" % unit,
                os.path.relpath(unit_md_path(repo, unit), root),
                "%d target(s) recorded, the signoff is now stale" % len(targets),
            ]
        return respond(segments, next_token, as_json)


def cmd_steer(args):
    """``steer`` — record one steering request into the stream later gates read.

    Stage c is the contract's order for this row: `retired` then `no_signoff`.
    Steering is an H event, which is precisely why it — and not
    ``--unsteered-reason`` — is what satisfies the steering gate: the author
    states what changed, on the record, before the next draft.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ----------------------------------------------
        validate_unit_id(unit)
        note = read_note(args, unit)
        records = read_events(ledger_path(repo, unit), unit)
        found_guard(repo, unit, records)
        identity = git_identity(repo)

        # --- c: per-verb preconditions, in the listed order -------------------
        state = unit_state(repo, unit)
        retired_guard(state, unit)
        signoff_guard(state, unit)

        # --- d: no-op recognition — none for steer ----------------------------
        # --- e: content gates — none for steer --------------------------------
        # --- f: write ---------------------------------------------------------
        head = git_head(repo)
        event = next_event(
            "steering", records, identity, head, {"note": note, "origin": args.origin}
        )
        result = perform_write(
            repo,
            unit,
            "steered",
            chain_lines([event]),
            [event["seq"]],
            [],
            note,
            head,
        )
        report_hook_changes(result, repo)

        # A steering event is always later than the last generation, so it joins
        # `pending` by construction — counted here rather than re-derived.
        segments = [
            "steered %s" % unit,
            os.path.relpath(ledger_path(repo, unit), os.fspath(repo)),
            "%d pending request(s), origin %s"
            % (len(state["pending"]) + 1, args.origin),
        ]
        return respond(segments, next_token_for(repo, unit), as_json)


def describe_orphans(previous_signoff, targets):
    """Name each dropped target once: reported, never deleted (contract 5.4).

    A removed path stays in ``basis.files`` until the next generation and the
    file is kept on disk; the author is told once, by name, which is the whole
    obligation the contract places on a re-sign.
    """
    if previous_signoff is None:
        return ""
    return describe_orphan_paths(
        [path for path in (previous_signoff.get("targets") or []) if path not in targets]
    )


# --- draft ------------------------------------------------------------------


def describe_orphan_paths(paths):
    """The contract 5.4 orphan phrase, worded in ONE place.

    Both the re-sign response (which diffs the previous signoff's targets) and
    the draft response (which reads the basis) name each dropped path once, and
    they must say the same thing: the tool never deletes a page.
    """
    if not paths:
        return ""
    return "no longer a target; kept on disk: %s" % ", ".join(paths)


def resolve_draft_source(repo, unit, source):
    """Contract 5.6's draft-source rule — stage b, before any target is known.

    The source must resolve inside ``.dogen/staging/<id>/draft/``. ``contained``
    does the work through ``realpath``, so writing ``docs/<target>`` first and
    handing it back as the source is refused before the page is read, let alone
    written (T23/N-31) — and so is a symlink in the staging tree pointing out of
    it. This check needs no signoff, which is why it can run in stage b; the
    "a directory holds exactly the signed targets" half cannot, and waits for
    stage c to establish that there ARE signed targets.
    """
    draft_root = os.path.join(staging_dir(repo, unit), "draft")
    if not source:
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="no draft source",
            hint="pass a file or directory under .dogen/staging/%s/draft/" % unit,
        )
    candidate = os.path.abspath(source)
    if not contained(draft_root, candidate):
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="the draft source %r resolves outside .dogen/staging/%s/draft/"
            % (source, unit),
            hint="a draft is drawn from the staging tree, never from the docs root",
        )
    if not os.path.exists(candidate):
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="the draft source %r does not exist" % source,
            hint="stage the draft under .dogen/staging/%s/draft/ first" % unit,
        )
    return candidate


def map_draft_files(unit, source, targets):
    """Map a resolved source onto EXACTLY the signed targets (contract 5.6).

    A directory source contains exactly the signed targets, no more and no
    fewer — an extra page would be an unsigned write and a missing one would
    leave a signed target unwritten, and the generation's ``files[]`` has to be
    the whole target set either way. A file source draws a single-target unit
    and nothing else; there is no rule that would say which target it is.
    """
    if os.path.isdir(source):
        found = []
        # followlinks=False is the default and is spelled out because the
        # invariant is load-bearing: a linked subdirectory must be visible as a
        # link to refuse, never descended into as if it were staged material.
        for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
            for name in sorted(dirnames):
                member = os.path.join(dirpath, name)
                if os.path.islink(member):
                    raise Refusal(
                        "bad_draft_path",
                        unit=unit,
                        detail="the draft directory holds a symlinked subdirectory %r"
                        % os.path.relpath(member, source),
                        hint="a draft is drawn from the staging tree, never through "
                        "a symlink",
                    )
            for name in filenames:
                found.append(os.path.relpath(os.path.join(dirpath, name), source))
        if sorted(found) != sorted(targets):
            raise Refusal(
                "bad_draft_path",
                unit=unit,
                detail="the draft directory holds [%s]; the signed targets are [%s]"
                % (", ".join(sorted(found)), ", ".join(sorted(targets))),
                hint="a directory source contains exactly the signed targets",
            )
        mapping = [(target, os.path.join(source, target)) for target in targets]
        # Every MEMBER, not only the source: `resolve_draft_source` contains the
        # directory, and a symlinked file inside it then drew bytes from
        # anywhere on the filesystem into a signed target — the T23/N-31 bypass,
        # spelled `draft/<target>` -> `docs/<target>`.
        for target, path in mapping:
            if os.path.islink(path) or not contained(source, path):
                raise Refusal(
                    "bad_draft_path",
                    unit=unit,
                    detail="the staged page for %r resolves outside the draft "
                    "directory" % target,
                    hint="a draft is drawn from the staging tree, never through "
                    "a symlink",
                )
        return mapping
    if len(targets) != 1:
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="a file source draws one page, but %d targets are signed"
            % len(targets),
            hint="pass the staging directory holding all %d signed targets" % len(targets),
        )
    return [(targets[0], source)]


def read_draft_bytes(unit, mapping):
    """Read every staged page once, refusing a zero-byte one.

    An empty file is not a draft: ``read_fs`` reports a zero-byte page as ``""``
    rather than a digest (the three-valued vocabulary ``derive`` reasons over),
    so a generation recording the real sha256 of no bytes would read back as
    drift the moment it landed. Refusing here keeps the recorded digest and the
    snapshot's digest the same fact.
    """
    staged = []
    for target, path in mapping:
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as bad:
            raise Refusal(
                "bad_draft_path",
                unit=unit,
                detail="the staged page for %r cannot be read (%s)"
                % (target, type(bad).__name__),
                hint="stage a readable file under the unit's draft directory",
            )
        if not data:
            raise Refusal(
                "bad_draft_path",
                unit=unit,
                detail="the staged page for %r is zero bytes" % target,
                hint="an empty file is not a draft",
            )
        staged.append((target, data))
    return staged


def read_report(spec, unit=""):
    """The optional ``--report F``: the drafting skill's JSON side-car.

    It carries claims about the draft, never bytes: ``origins`` (what was read),
    ``gaps``/``gaps_note`` (what could not be covered) and ``steps_seq`` (which
    step plan the draft was produced against). Absent, every one of them is
    simply not recorded — the generation never carries a null placeholder.
    """
    if spec is None:
        return {}
    try:
        with open(spec, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as bad:
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="--report %s cannot be read (%s)" % (spec, type(bad).__name__),
            hint="pass an existing readable JSON report, or omit --report",
        )
    except UnicodeDecodeError:
        # Before ValueError, which it subclasses: "not UTF-8" is a different
        # thing to tell the author than "not valid JSON" (WR-04).
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="--report %s is not UTF-8 text" % spec,
            hint="the report is one UTF-8 JSON object",
        )
    except ValueError as bad:
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="--report %s is not valid JSON (%s)" % (spec, bad),
            hint="the report is one JSON object",
        )
    if not isinstance(data, dict):
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="--report %s is not a JSON object" % spec,
            hint="the report is one JSON object",
        )
    return data


def report_claims(report, unit=""):
    """``(origins, gaps, gaps_note, steps_seq)`` out of a ``--report`` payload."""
    origins = []
    for entry in report.get("origins") or []:
        origins.append(_scalar(str(entry), "sources", unit))
    check_count_cap("origins", origins, MAX_ORIGINS)
    gaps = []
    for entry in report.get("gaps") or []:
        gaps.append(_scalar(str(entry), "notes", unit))
    check_count_cap("gaps", gaps, MAX_ORIGINS)
    gaps_note = report.get("gaps_note")
    if gaps_note:
        gaps_note = validate_note(str(gaps_note), unit, "gaps_note")
    else:
        gaps_note = ""
    steps_seq = report.get("steps_seq")
    if steps_seq is not None and not _is_seq(steps_seq):
        raise Refusal(
            "bad_draft_path",
            unit=unit,
            detail="the report's steps_seq is not an integer",
            hint="steps_seq names a steps-planned event's seq",
        )
    return origins, gaps, gaps_note, steps_seq


def step_resolves(event):
    """Does one ``step-recorded`` event resolve the step it names? (5.4)

    ``pass`` + a digest, ``skipped`` + a reason, and ``deviated`` + exit 0 + a
    digest resolve; ``fail`` never resolves, at any exit code. The verdict alone
    is never the answer: a `pass` with no captured output is a claim with no
    evidence behind it, which is the whole point of LEDG-06.
    """
    verdict = event.get("verdict")
    if verdict == "pass":
        return bool(event.get("output_sha256"))
    if verdict == "skipped":
        return bool(event.get("reason"))
    if verdict == "deviated":
        return event.get("exit_code") == 0 and bool(event.get("output_sha256"))
    return False


def step_reason_required(event):
    """Contract 5.3: when a ``step-recorded`` must carry a ``reason``.

    Skipped and deviated, a pass at a non-zero exit, and a fail at exit 0 —
    every case where the verdict and the exit code disagree, or where there is
    nothing to look at. Extracted because TWO places must agree about it: the
    evidence gate refuses a record without one, and ``verify``'s V8 reports an
    older record that is missing one. A second reading of the same rule is how
    the gate and the report come to disagree about the same event.
    """
    verdict = event.get("verdict")
    exit_code = event.get("exit_code")
    return bool(
        verdict in ("skipped", "deviated")
        or (verdict == "pass" and exit_code != 0)
        or (verdict == "fail" and exit_code == 0)
    )


def _step_prefix_key(step):
    """Contract 5.4's prefix identity: ``(text_hash, mode, stateful)``.

    The step id is deliberately absent. Renaming a step does not invalidate the
    evidence captured for it; changing what it says, who runs it or whether it
    mutates state does.
    """
    return (step.get("text_hash"), step.get("mode"), step.get("stateful"))


def step_answers(events, plan):
    """Per step id of ``plan``, the ``step-recorded`` event that answers it.

    Contract 5.4's step rule in full, and the ONE place the carry-forward walk
    lives: the unresolved set and the tally both read it, so the two can never
    hold different opinions of the same record. A ``step-recorded`` answers the
    step it names in the plan ``steps_seq``, **and** carries forward "only along
    consecutive ``reuse:true`` plans and only for steps whose prefix ``[0..i]``
    is identical in ``(text_hash, mode, stateful)`` across every hop".

    The walk follows ``replaces`` backwards — the seq of the ``steps-planned``
    this plan supersedes — and stops at the first plan that does not reuse. At
    each hop the shared prefix is re-measured and can only SHRINK, which is what
    makes one differing element break that step and every step after it, and
    only those. Position, not identity, links the hops: the previous plan's step
    at index ``i`` answers this plan's step at index ``i``, because that is the
    pair the tuple comparison just proved identical. Only a RESOLVING record
    carries, and a record made against this plan always wins — a `fail` recorded
    now is the latest word and must not be overridden by an older pass.

    Pure — events in, a mapping out, no filesystem — so ``derive()`` stays pure
    (D-19) and the whole rule is driven from literal dicts in the unit suite.
    """
    steps = plan.get("steps") or []
    ids = [step.get("id") for step in steps]
    plans_by_seq = {}
    records_by_seq = {}
    for event in events:
        kind = event.get("kind")
        if kind == "steps-planned":
            plans_by_seq[event.get("seq")] = event
        elif kind == "step-recorded":
            # Last one wins: a re-record with a different verdict supersedes.
            records_by_seq.setdefault(event.get("steps_seq"), {})[
                event.get("step_id")
            ] = event

    own = records_by_seq.get(plan.get("seq"), {})
    answers = dict((step_id, own[step_id]) for step_id in ids if step_id in own)

    current = plan
    reach = len(steps)
    # A ledger is contributor input (CR-04): a forged or truncated `replaces`
    # must terminate the walk, never loop it.
    seen = {plan.get("seq")}
    while reach > 0 and current.get("reuse"):
        previous = plans_by_seq.get(current.get("replaces"))
        if previous is None or previous.get("seq") in seen:
            break
        seen.add(previous.get("seq"))
        previous_steps = previous.get("steps") or []
        shared = 0
        while (
            shared < reach
            and shared < len(previous_steps)
            and _step_prefix_key(steps[shared])
            == _step_prefix_key(previous_steps[shared])
        ):
            shared += 1
        reach = shared
        earlier = records_by_seq.get(previous.get("seq"), {})
        for index in range(reach):
            step_id = ids[index]
            if step_id in answers:
                continue
            candidate = earlier.get(previous_steps[index].get("id"))
            if candidate is not None and step_resolves(candidate):
                answers[step_id] = candidate
        current = previous
    return answers


def unresolved_steps(events, plan):
    """Step ids of ``plan`` that no record resolves — contract 5.4, via 5.4."""
    answers = step_answers(events, plan)
    return [
        step.get("id")
        for step in (plan.get("steps") or [])
        if not step_resolves(answers.get(step.get("id")) or {})
    ]


def cmd_draft(args):
    """``draft`` — record a generation and write every signed target.

    Stages a–f in contract 5.7's order. Stage c is the `draft` row verbatim:
    `retired` → `no_signoff` → `plan_stale` → `page_drift` (changed bytes only;
    absence never blocks) → `target_exists` → `steps_unresolved`/`steps_missing`.
    The order is load-bearing, not stylistic — T9b turns on `generation_stale`
    being read before drift, and T26c on absence NOT being drift.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()
    root = os.fspath(repo)

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ----------------------------------------------
        validate_unit_id(unit)
        source = resolve_draft_source(repo, unit, args.source)
        model = validate_model(args.model, args.model_origin, unit)
        origins, gaps, gaps_note, report_steps_seq = report_claims(
            read_report(args.report, unit), unit
        )
        reason = (
            validate_note(args.unsteered_reason, unit, "unsteered reason")
            if args.unsteered_reason is not None
            else ""
        )
        records = read_events(ledger_path(repo, unit), unit)
        events = [event for event, _ in records]
        found_guard(repo, unit, records)
        identity = git_identity(repo)

        # --- c: per-verb preconditions, in the listed order -------------------
        # `retired` and `no_signoff` are ledger-only facts, so they are answered
        # from a snapshot-free derive: the signed target set they establish is
        # what the rest of stage b and every later stage needs.
        ledger_only = derive(events, {"unit_md_sha": None, "paths": {}})
        retired_guard(ledger_only, unit)
        signoff_guard(ledger_only, unit)

        # The deferred half of stage b: a directory source holds exactly the
        # signed targets — a question that cannot be asked before there is a
        # signoff to ask it about.
        targets = ledger_only["targets"]
        # The signed target set is re-checked against the filesystem as it is
        # NOW: a target that was containable at signoff and has since been
        # re-pointed (a symlinked docs subdirectory) is refused here rather than
        # at `git add`, which is four irreversible steps too late.
        guard_targets(repo, unit, targets)
        staged = read_draft_bytes(unit, map_draft_files(unit, source, targets))

        plan_event = _last_of(events, "steps-planned")
        steps_seq = report_steps_seq
        if steps_seq is None and plan_event is not None:
            steps_seq = plan_event.get("seq")
        staging = {
            "steps_seq": steps_seq,
            "files": dict((target, sha256_bytes(data)) for target, data in staged),
        }
        # ONE filesystem snapshot for the whole invocation: the preconditions
        # below, stage d's no-op and stage e's gate all read this instant.
        state = unit_state(repo, unit, staging)

        if state["plan_stale"]:
            raise Refusal(
                "plan_stale",
                unit=unit,
                detail="unit.md no longer matches the plan_hash signed at seq %s"
                % state["so_seq"],
                hint="dogen unit edit %s --re-sign records the amendment" % unit,
                next_token=route(state),
            )
        if state["page_drift"]:
            raise Refusal(
                "page_drift",
                unit=unit,
                detail="changed outside dogen since the basis: %s"
                % ", ".join(state["drifted_paths"]),
                hint='dogen edits %s --note "…" records the hand edit' % unit,
                next_token=route(state),
            )
        if state["target_exists"]:
            raise Refusal(
                "target_exists",
                unit=unit,
                detail="a signed target exists on disk and is not in the basis: %s"
                % ", ".join(state["existing_targets"]),
                hint='dogen edits %s --note "…" adopts the existing page' % unit,
                next_token=route(state),
            )
        if state["actionable"]:
            # D-18: an actionable unit declares and signs off normally; there is
            # no flag that treats one as reference. `plan-steps` and `step`
            # arrive in phase 17 (D-16), so `walk` is the honest route.
            if plan_event is None:
                raise Refusal(
                    "steps_missing",
                    unit=unit,
                    detail="unit %s is %s and has no recorded step plan"
                    % (unit, state["intent"]),
                    hint="dogen plan-steps %s --steps-file …" % unit,
                    next_token="walk",
                )
            pending_steps = unresolved_steps(events, plan_event)
            if pending_steps:
                raise Refusal(
                    "steps_unresolved",
                    unit=unit,
                    detail="unresolved step(s): %s" % ", ".join(pending_steps),
                    hint="dogen step %s <step-id> --steps-seq %s --evidence-file …"
                    % (unit, plan_event.get("seq")),
                    next_token="walk",
                )

        # --- d: no-op recognition ---------------------------------------------
        # STATE-05: the condition set is READ, never re-derived. `derive`
        # computed all five from the single snapshot above, and the comparison
        # is against the destination files — so a missing destination, a
        # hook-rewritten one, or a brownfield basis with no generation can never
        # make a draft a no-op.
        if state["identical_draft"]["all"]:
            gen = state["gen"]
            raise Refusal(
                "identical_draft",
                unit=unit,
                detail="every signed target already holds these bytes, recorded by "
                "the generation at seq %s" % gen.get("seq"),
                hint="steer %s first if the page should change" % unit,
                next_token=route(state),
                extra={"seq": gen.get("seq"), "commit": gen.get("commit")},
            )

        # --- e: content gates --------------------------------------------------
        # STATE-06: the steering gate applies only once a generation exists — a
        # first draft has nothing to have re-drafted. Defeating the no-op above
        # never waives it (T11b/T26e), and `--unsteered-reason` overrides THIS
        # generation and nothing else: it is not an H event, it never enters
        # `pending`, and the next draft with nothing newly recorded is refused
        # again (D5/AC5).
        if state["gen"] is not None and not state["steered_since_gen"] and not reason:
            raise Refusal(
                "unsteered",
                unit=unit,
                detail="nothing has been recorded since the generation at seq %s"
                % state["gen_seq"],
                hint="a STOP, not a retry: ask the author what should change, then "
                'dogen steer %s --note "<their words>"; only when the author '
                "authorises a redraft with nothing to change, `dogen draft %s "
                '<staged-file> --unsteered-reason "<why>"`' % (unit, unit),
                next_token=route(state),
            )

        # --- f: write ---------------------------------------------------------
        head = git_head(repo)
        payload = {
            "files": [
                {"path": target, "sha256": sha256_bytes(data), "bytes": len(data)}
                for target, data in staged
            ],
            "signoff_seq": state["so_seq"],
            "plan_hash": state["so"].get("plan_hash"),
            "model": model,
            "model_origin": args.model_origin,
            "basis_seq": state["basis_seq"],
            "unsteered": bool(reason),
        }
        if reason:
            payload["unsteered_reason"] = reason
        if steps_seq is not None:
            payload["steps_seq"] = steps_seq
        if origins:
            payload["origins"] = origins
        if gaps:
            payload["gaps"] = gaps
        if gaps_note:
            payload["gaps_note"] = gaps_note
        check_count_cap("files", payload["files"], MAX_FILES)

        event = next_event("generation", records, identity, head, payload)
        files = [
            (os.path.join(DOCS_ROOT, target), data) for target, data in staged
        ]
        result = perform_write(
            repo,
            unit,
            "drafted",
            chain_lines([event]),
            [event["seq"]],
            files,
            reason or state["so"].get("title") or unit,
            head,
        )
        report_hook_changes(result, repo)

        next_token = next_token_for(repo, unit)
        # The walk's tally, for a unit that has one. `step_tally` returns None
        # with no step plan and `respond` drops an empty segment, so a reference
        # or explanation unit reports no tally at all rather than an all-zero
        # one. The rendered text says what resolved and never that anything was
        # run or checked — contract 5.4 makes resolution a derivation result.
        tally = render_step_tally(step_tally(events))
        segments = [
            "drafted %s" % unit,
            ", ".join(target for target, _ in staged),
            "%d file(s) written" % len(staged),
            "steps: %s" % tally if tally else "",
            describe_orphan_paths(state["orphans"]),
        ]
        return respond(segments, next_token, as_json)


# --- edits ------------------------------------------------------------------


def complete_basis_set(previous, targets, paths):
    """VERB-05's **complete** basis set, computed from one ``read_fs`` snapshot.

    ``previous`` is the previous basis event's ``files[]`` (empty when there is
    none), ``targets`` the current signed targets in their signed order, and
    ``paths`` the snapshot's ``{path: sha256 | None (missing) | "" (zero-byte)}``.

    The rule, in the contract's own order: start from the previous basis with
    each path's recorded digest; replace the digest of any path whose disk bytes
    changed; add any signed target that is on disk, non-empty and not yet in the
    basis (brownfield adoption); drop any path that is missing from disk **and**
    is no longer a signed target; keep a path that is missing but is still a
    current signed target, with its LAST RECORDED digest — no placeholder file
    is written and no digest is invented.

    Order is the current signoff's ``targets`` order, then basis paths that are
    no longer signed in their basis order, so two runs over the same state emit
    the same bytes. Pure, so U-05 drives it with literal dicts; the one caller
    reads it from the same snapshot every other stage of the verb reads.
    """
    recorded = {}
    basis_order = []
    for entry in previous or []:
        path = entry.get("path")
        if path in recorded:
            continue
        recorded[path] = entry.get("sha256")
        basis_order.append(path)

    resolved = {}
    for path in basis_order:
        current = paths.get(path)
        if current is None:
            # Missing from disk: dropped only when it is no longer a target.
            if path in targets:
                resolved[path] = recorded[path]
            continue
        # "Changed" is read exactly as ``derive``'s ``page_drift`` reads it, so
        # recording an edit always clears the drift that routed the author here.
        # That includes a page truncated to zero bytes, whose snapshot token is
        # ``""``: recording the snapshot's own token keeps the two agreeing,
        # where recording a digest of no bytes would report drift forever.
        if current != recorded[path]:
            resolved[path] = current
        else:
            resolved[path] = recorded[path]
    for target in targets:
        if target in resolved:
            continue
        current = paths.get(target)
        if current is not None and current != "":
            resolved[target] = current

    ordered = [target for target in targets if target in resolved]
    ordered += [path for path in basis_order if path not in targets and path in resolved]
    return [{"path": path, "sha256": resolved[path]} for path in ordered]


def cmd_edits(args):
    """``edits`` — record what the author already did, as the complete basis set.

    Stage c is the contract's order for this row and is deliberately SHORT:
    `retired` then `no_signoff`, and nothing else. There is no `page_drift`,
    `plan_stale` or `generation_stale` precondition on `edits`, because
    recording what the author already did must never be blocked by the very
    state that recording it resolves (T9/T9b).

    The verb records; it never writes a page and never deletes one. Its only
    pathspec is the ledger, so `git add -- <a path that is not there>` cannot be
    reached (RESEARCH P-5).
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ----------------------------------------------
        validate_unit_id(unit)
        note = read_note(args, unit)
        records = read_events(ledger_path(repo, unit), unit)
        events = [event for event, _ in records]
        found_guard(repo, unit, records)
        identity = git_identity(repo)

        # --- c: per-verb preconditions, in the listed order -------------------
        # ONE snapshot, taken here under the lock and read by every stage below:
        # a file changed mid-verb cannot be half-adopted, because the whole
        # complete basis set comes from this single instant.
        ledger_only = derive(events, {"unit_md_sha": None, "paths": {}})
        snapshot = read_fs(
            repo, unit, ledger_only["basis_files"], ledger_only["targets"]
        )
        state = derive(events, snapshot)
        retired_guard(state, unit)
        signoff_guard(state, unit)

        # --- d: no-op recognition ---------------------------------------------
        # Absence alone is never an edit: a deleted page leaves the basis
        # carrying its last recorded digest and routes to `steer`, not here.
        files = complete_basis_set(
            (state["basis"] or {}).get("files") or [],
            state["targets"],
            snapshot["paths"],
        )
        if not state["page_drift"] and not state["target_exists"]:
            basis = state["basis"]
            raise Refusal(
                "no_edits",
                unit=unit,
                detail="no basis page has changed and no signed target is waiting "
                "to be adopted",
                hint="edit a page by hand first, or drop the command",
                next_token=route(state),
                extra={
                    "seq": basis.get("seq") if basis is not None else None,
                    "commit": basis.get("commit") if basis is not None else None,
                },
            )
        if not files:
            # An edit whose complete basis set would be empty is the no-op too:
            # the event is never written with an empty files[].
            raise Refusal(
                "no_edits",
                unit=unit,
                detail="the complete basis set is empty",
                hint="there is nothing on disk to record",
                next_token=route(state),
            )

        # --- e: content gates — none for edits ---------------------------------
        # --- f: write ----------------------------------------------------------
        head = git_head(repo)
        check_count_cap("files", files, MAX_FILES)
        payload = {
            "files": files,
            "generation_seq": state["gen_seq"],
            "note": note,
        }
        event = next_event("reviewer-edit", records, identity, head, payload)
        result = perform_write(
            repo,
            unit,
            "reviewer-edited",
            chain_lines([event]),
            [event["seq"]],
            [],
            note,
            head,
        )
        report_hook_changes(result, repo)

        segments = [
            "recorded edits on %s" % unit,
            os.path.relpath(ledger_path(repo, unit), os.fspath(repo)),
            "%d file(s) in the basis" % len(files),
            describe_orphan_paths(
                [
                    entry["path"]
                    for entry in files
                    if entry["path"] not in state["targets"]
                ]
            ),
        ]
        return respond(segments, next_token_for(repo, unit), as_json)


# --- review -----------------------------------------------------------------


def parse_resolves(values, unit=""):
    """``--resolves a,b`` (repeatable) into a list of integer seqs.

    A value that is not an integer refuses `bad_resolution` rather than
    `bad_target`: the contract names ONE code for everything the disposition
    rule turns away, and "``four`` is not a seq" is a disposition the tool
    cannot record, not a malformed identifier.
    """
    seqs = []
    for value in values or []:
        for piece in str(value).split(","):
            text = piece.strip()
            if not text:
                continue
            try:
                seqs.append(int(text))
            except ValueError:
                raise Refusal(
                    "bad_resolution",
                    unit=unit,
                    detail="%r is not a seq" % text,
                    hint="--resolves takes the seq numbers of pending requests",
                )
    return seqs


def parse_withdraws(values, unit=""):
    """``--withdraw <seq> "<reason>"`` (repeatable) into ``[(seq, raw reason)]``.

    The reason travels UNVALIDATED to :func:`validate_dispositions`, which is
    the single place the disposition rule chooses its reason code; validating
    it here would refuse an empty reason as `note_required` instead of the
    `bad_resolution` contract 5.6 and T30 name.
    """
    parsed = []
    for entry in values or []:
        raw_seq = entry[0]
        reason = entry[1] if len(entry) > 1 else ""
        try:
            seq = int(str(raw_seq).strip())
        except ValueError:
            raise Refusal(
                "bad_resolution",
                unit=unit,
                detail="%r is not a seq" % raw_seq,
                hint='--withdraw takes a pending seq and a reason: --withdraw 12 "…"',
            )
        parsed.append((seq, reason))
    return parsed


def validate_dispositions(resolves, withdraws, pending, unit=""):
    """Contract 5.6's disposition rule — the ONE place `bad_resolution` is chosen.

    Every seq must be in the CURRENT ``pending`` set, no seq may appear twice,
    the two sets must be disjoint, and every withdrawal must carry a non-empty
    reason; anything else is 2 `bad_resolution` (T30).

    ``pending`` is derived from the single ledger + ``read_fs()`` snapshot the
    verb took under the repo-wide lock, so a `steer` landing concurrently
    either precedes that snapshot — and must be disposed — or follows the
    commit and becomes pending against the new tip. It can never slip past an
    accept unnoticed.

    `resolves` records the reviewer's **judgment** that a request is satisfied.
    It is never evidence that a byte changed, which is why this rule is about
    naming each request exactly once and never about comparing pages.

    Returns ``(sorted resolves, sorted [{seq, reason}])`` so two runs over the
    same arguments record the same bytes.
    """
    known = set(pending)
    seen = {}

    def claim(seq, flag):
        if seq not in known:
            raise Refusal(
                "bad_resolution",
                unit=unit,
                detail="seq %d is not a pending request (pending: %s)"
                % (seq, ", ".join(str(item) for item in pending) or "none"),
                hint="dispositions name the requests dogen show lists as pending",
            )
        if seq in seen:
            if seen[seq] == flag:
                detail = "seq %d is named twice by --%s" % (seq, flag)
            else:
                detail = "seq %d is both resolved and withdrawn" % seq
            raise Refusal(
                "bad_resolution",
                unit=unit,
                detail=detail,
                hint="--resolves and --withdraw are disjoint and name each request once",
            )
        seen[seq] = flag

    for seq in resolves:
        claim(seq, "resolves")
    checked = []
    for seq, reason in withdraws:
        claim(seq, "withdraw")
        try:
            text = clean_text(reason if isinstance(reason, str) else "")
        except ValueError as bad:
            raise Refusal(
                "bad_resolution",
                unit=unit,
                detail="the withdrawal of seq %d carries no usable reason: %s" % (seq, bad),
                hint="a withdrawal states why the request is dropped, on the record",
            )
        checked.append({"seq": seq, "reason": text})
    return sorted(resolves), sorted(checked, key=lambda entry: entry["seq"])


def cmd_review(args):
    """``review`` — record one verdict and close pending requests by disposition.

    Stages a–f in contract 5.7's order. Stage c is the verb's two rows verbatim:
    `retired` → `no_signoff` → `no_generation` → `plan_stale` → `generation_stale`
    for every verdict, and for accept then `page_drift` → `target_missing`. The
    order of those last two is load-bearing: an untouched deleted page reports
    `target_missing` and not `page_drift`, because absence is not drift (T26c).

    Stage d is `already_accepted`; stage e is `unapplied_steering` for accept and
    `note_required` for fix and redraft. d precedes e, and d's "no H event after
    the tip" is what turns an accept retry after a later `steer` into
    `unapplied_steering` rather than a no-op (T10).
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ----------------------------------------------
        validate_unit_id(unit)
        verdict = args.verdict
        note = ""
        if getattr(args, "note", None) is not None or getattr(args, "note_file", None) is not None:
            note = read_note(args, unit)
        resolves = parse_resolves(args.resolves, unit)
        withdraws = parse_withdraws(args.withdraw, unit)
        if verdict != "accept" and (resolves or withdraws):
            raise Refusal(
                "bad_resolution",
                unit=unit,
                detail="dispositions close requests on an accept; this verdict is %r"
                % verdict,
                hint="record --resolves / --withdraw on the accept that closes them",
            )
        records = read_events(ledger_path(repo, unit), unit)
        found_guard(repo, unit, records)
        identity = git_identity(repo)

        # ONE snapshot for the whole invocation: the disposition rule, every
        # precondition, the no-op and the content gate all read this instant.
        state = unit_state(repo, unit)
        resolves, withdrawals = validate_dispositions(
            resolves, withdraws, state["pending"], unit
        )

        # --- c: per-verb preconditions, in the listed order -------------------
        retired_guard(state, unit)
        signoff_guard(state, unit)
        if state["gen"] is None:
            raise Refusal(
                "no_generation",
                unit=unit,
                detail="unit %s has no generation to review" % unit,
                hint="dogen draft %s <staging path> records one" % unit,
                next_token=route(state),
            )
        if state["plan_stale"]:
            raise Refusal(
                "plan_stale",
                unit=unit,
                detail="unit.md no longer matches the plan_hash signed at seq %s"
                % state["so_seq"],
                hint="dogen unit edit %s --re-sign records the amendment" % unit,
                next_token=route(state),
            )
        if state["generation_stale"]:
            raise Refusal(
                "generation_stale",
                unit=unit,
                detail="the generation at seq %s cites the signoff at seq %s, which is "
                "no longer current (seq %s)"
                % (state["gen_seq"], state["gen"].get("signoff_seq"), state["so_seq"]),
                hint="dogen draft %s <staging path> records a generation against the "
                "amended plan" % unit,
                next_token=route(state),
            )
        if verdict == "accept":
            if state["page_drift"]:
                raise Refusal(
                    "page_drift",
                    unit=unit,
                    detail="changed outside dogen since the basis: %s"
                    % ", ".join(state["drifted_paths"]),
                    hint='dogen edits %s --note "…" records the hand edit' % unit,
                    next_token=route(state),
                )
            if state["target_missing"]:
                raise Refusal(
                    "target_missing",
                    unit=unit,
                    detail="signed target(s) not in the basis or missing from disk: %s"
                    % ", ".join(state["missing_targets"]),
                    hint='dogen steer %s --note "restore …" records the request; the '
                    "next draft writes it" % unit,
                    next_token=route(state),
                )

        # --- d: no-op recognition ---------------------------------------------
        # `target_missing` is already excluded by stage c, so the no-op's own
        # "not target_missing" condition is established rather than re-asked.
        rev = state["rev"]
        if (
            verdict == "accept"
            and rev is not None
            and state["tip_seq"] == state["rev_seq"]
            and rev.get("verdict") == "accept"
            and not state["h_after_tip"]
            and rev.get("basis_seq") == state["basis_seq"]
        ):
            raise Refusal(
                "already_accepted",
                unit=unit,
                detail="the basis at seq %s was already accepted at seq %s"
                % (state["basis_seq"], rev.get("seq")),
                hint="nothing has been recorded since; the unit is sealed",
                next_token=route(state),
                extra={"seq": rev.get("seq"), "commit": rev.get("commit")},
            )

        # --- e: content gates --------------------------------------------------
        if verdict == "accept":
            disposed = set(resolves)
            disposed.update(entry["seq"] for entry in withdrawals)
            outstanding = [seq for seq in state["pending"] if seq not in disposed]
            if outstanding:
                raise Refusal(
                    "unapplied_steering",
                    unit=unit,
                    detail="pending request(s) with no recorded disposition: %s"
                    % ", ".join(str(seq) for seq in outstanding),
                    hint="put each pending seq to the reviewer, then dogen review %s "
                    '--verdict accept --note "…" with --resolves <seq> or --withdraw '
                    '<seq> "<reason>" for every one' % unit,
                    next_token=route(state),
                )
        elif not note:
            raise Refusal(
                "note_required",
                unit=unit,
                detail="a %s verdict says what should change" % verdict,
                hint='dogen review %s --verdict %s --note "…"' % (unit, verdict),
                next_token=route(state),
            )

        # --- f: write ----------------------------------------------------------
        head = git_head(repo)
        payload = {
            "verdict": verdict,
            "generation_seq": state["gen_seq"],
            "note": note,
        }
        if verdict == "accept":
            # `files` is the basis verbatim — V6 reads "accept files == basis",
            # so the accept copies the recorded entries rather than recomputing
            # digests it would then be asserting against itself.
            payload["basis_seq"] = state["basis_seq"]
            payload["files"] = [
                dict(entry) for entry in ((state["basis"] or {}).get("files") or [])
            ]
            payload["resolves"] = list(resolves)
            payload["withdraws"] = [dict(entry) for entry in withdrawals]
            check_count_cap("files", payload["files"], MAX_FILES)

        event = next_event("review", records, identity, head, payload)
        result = perform_write(
            repo,
            unit,
            "reviewed",
            chain_lines([event]),
            [event["seq"]],
            [],
            note or verdict,
            head,
            verdict=verdict,
        )
        report_hook_changes(result, repo)

        if verdict == "accept":
            segments = [
                "reviewed %s: accept" % unit,
                "%d file(s) sealed" % len(payload["files"]),
                "%d request(s) judged satisfied, %d withdrawn (a recorded judgment, "
                "never proof that the bytes changed)"
                % (len(resolves), len(withdrawals)),
            ]
        else:
            segments = [
                "reviewed %s: %s" % (unit, verdict),
                os.path.relpath(ledger_path(repo, unit), os.fspath(repo)),
                "the request is recorded and pending",
            ]
        return respond(segments, next_token_for(repo, unit), as_json)


# --- read surfaces ----------------------------------------------------------


def unit_view(repo, unit, events=None):
    """One ledger read and ONE ``read_fs()`` snapshot, shared by every reader.

    ``show``, ``summary`` and ``verify`` derive and route from this single
    instant; none re-derives direction and none forms a second opinion of the
    state.

    ``events`` is the ledger a caller has ALREADY read. ``verify`` supplies it
    because :func:`read_events` refuses a line that is not a JSON object — the
    right answer for every verb about to act on the record, and the wrong one
    for the reader whose job is to report that line (:func:`lenient_events`).
    """
    if events is None:
        records = read_events(ledger_path(repo, unit), unit)
        events = [event for event, _ in records]
    ledger_only = derive(events, {"unit_md_sha": None, "paths": {}})
    snapshot = read_fs(repo, unit, ledger_only["basis_files"], ledger_only["targets"])
    return events, snapshot, derive(events, snapshot)


def read_only_unit(repo, unit):
    """Stage a in read-only mode, then the view — the readers' shared preamble.

    No lock is taken: a read surface writes nothing, and queueing behind another
    invocation would refuse the author the very answer they are asking for.
    Contract 5.8's write boundary is honoured instead — classify identically,
    print what write mode would delete, delete nothing.
    """
    classify_stage_a(repo, unit, write_mode=False)
    validate_unit_id(unit)
    found_guard(repo, unit, os.path.exists(ledger_path(repo, unit)))
    return unit_view(repo, unit)


def unit_headline(events, state, unit):
    """``(title, intent, audience)`` from the signoff, else the declared plan."""
    so = state["so"]
    if so is not None:
        return (so.get("title") or unit, so.get("intent") or "", so.get("audience") or "")
    declared = _later(
        _last_of(events, "unit-edited"), _last_of(events, "unit-declared")
    )
    frontmatter = (declared or {}).get("frontmatter") or {}
    return (
        frontmatter.get("title") or unit,
        frontmatter.get("intent") or "",
        frontmatter.get("audience") or "",
    )


def state_qualifier(state):
    """The qualifier VERB-02 prints whenever the state alone would mislead.

    An accept that a later amendment or request has overtaken derives as
    `reviewed`, which on its own looks like any other review. The qualifier says
    which accept it was and what overtook it, so an accept-then-redraft unit can
    never be read as sealed.
    """
    bits = []
    rev = state["rev"]
    if rev is not None and rev.get("verdict") == "accept" and state["state"] != "sealed":
        bits.append("accepted at seq %s" % rev.get("seq"))
    if state["generation_stale"]:
        bits.append("plan amended at seq %s" % state["so_seq"])
    if state["plan_stale"]:
        bits.append("unit.md edited since the signoff at seq %s" % state["so_seq"])
    count = len(state["pending"])
    if count:
        bits.append("%d request%s pending" % (count, "" if count == 1 else "s"))
    return ", ".join(bits)


def drift_status(repo, path):
    """`drifted (committed in <sha7>)` when HEAD already holds the changed bytes.

    The distinction is the author's next move: an uncommitted hand edit is still
    theirs to keep or discard, where a committed one is already in the
    repository's history and `edits` is the only honest way to record it.
    """
    relative = os.path.join(DOCS_ROOT, path)
    blob = git_show_blob(repo, "HEAD", relative)
    disk = digest_file(os.path.join(os.fspath(repo), relative))
    if blob is not None and disk is not None and sha256_bytes(blob) == disk:
        proc = git(["log", "-1", "--format=%H", "--", relative], repo)
        sha = proc.stdout.strip()[:7] if proc.returncode == 0 else ""
        return "drifted (committed in %s)" % sha if sha else "drifted (committed)"
    return "drifted (uncommitted)"


def describe_paths(repo, state, paths):
    """One row per path, in the contract's order, each path named exactly once.

    Current signoff targets first in their signed order, then basis paths that
    are no longer signed in basis order, so two runs over the same state print
    the same rows in the same order. `missing` (absent) and `drifted` (changed
    bytes) are distinct statuses and never merge: absence is not drift.

    A unit with no basis yields no rows at all — the caller prints no section
    rather than an empty one.
    """
    basis = state["basis"]
    if basis is None:
        return []
    recorded = dict(_basis_pairs(basis))
    targets = state["targets"]
    ordered = list(targets) + [
        path for path in state["basis_files"] if path not in targets
    ]
    rows = []
    for path in ordered:
        current = paths.get(path)
        if path not in recorded:
            status = "new"
        elif path not in targets:
            status = (
                "no longer a target (file kept)"
                if current is not None
                else "no longer a target (file gone)"
            )
        elif current is None:
            status = "missing"
        elif current == recorded[path]:
            status = "current"
        else:
            status = drift_status(repo, path)
        rows.append(
            {
                "path": path,
                "status": status,
                "recorded_sha": recorded.get(path),
                "current_sha": current,
            }
        )
    return rows


def describe_requests(events, floor):
    """Recorded requests since the last generation, each with its disposition.

    `pending`, `resolved` or `withdrawn: <reason>`. `resolved` is the reviewer's
    recorded judgment that the request is satisfied and never a claim that a
    byte changed — which is why the disposition is reported beside the request
    rather than folded into a single "steering was applied" line.
    """
    disposed = {}
    for event in events:
        if event.get("kind") != "review" or event.get("verdict") != "accept":
            continue
        accept_seq = event.get("seq")
        # CR-04: the same shape `derive()`'s resolves/withdraws loop guards
        # against, restated here because this is a SECOND reader of the same
        # two payload fields -- and the one `show` reaches. An entry that names
        # no event disposes of no event.
        if not _is_seq(accept_seq):
            continue
        for seq in event.get("resolves") or []:
            if _is_seq(seq) and accept_seq > seq and seq not in disposed:
                disposed[seq] = ("resolved", "")
        for entry in event.get("withdraws") or []:
            if isinstance(entry, dict):
                seq, reason = entry.get("seq"), entry.get("reason") or ""
            else:
                seq, reason = entry, ""
            if _is_seq(seq) and accept_seq > seq and seq not in disposed:
                disposed[seq] = ("withdrawn", reason)
    rows = []
    for event in events:
        if not _is_h_event(event) or event.get("kind") == "signoff":
            continue
        seq = event.get("seq")
        if seq <= floor:
            continue
        disposition, reason = disposed.get(seq, ("pending", ""))
        if event.get("kind") == "review":
            origin = "review %s" % event.get("verdict")
        else:
            origin = "steering (%s)" % (event.get("origin") or "manual")
        rows.append(
            {
                "seq": seq,
                "origin": origin,
                "note": event.get("note") or "",
                "disposition": disposition,
                "reason": reason,
            }
        )
    return rows


def reviewer_edits_since(events, floor):
    """Reviewer edits recorded after the last generation, with their notes."""
    return [
        {"seq": event.get("seq"), "note": event.get("note") or ""}
        for event in events
        if event.get("kind") == "reviewer-edit" and event.get("seq") > floor
    ]


def step_tally(events):
    """The step counts both read surfaces report, or ``None`` with no step plan.

    A reference or explanation unit has no walk, and an all-zero tally would be
    noise rather than information, so the caller omits the line entirely. The
    counts are per STEP, not per event, and read :func:`step_answers`, so
    evidence carried forward under `--keep-evidence` is counted where it
    resolves rather than vanishing because it names an earlier plan's seq.

    ``plan`` lists the recorded steps themselves — id, text, mode, stateful
    marker, the step's verdict (``unresolved`` while it has none) and whether it
    resolves — so a session that did not propose the plan can walk it from the
    read surface, without reading the ledger.
    """
    plan = _last_of(events, "steps-planned")
    if plan is None:
        return None
    answers = step_answers(events, plan)
    counts = {"pass": 0, "skipped": 0, "deviated": 0, "fail": 0}
    reasons = []
    unresolved = []
    rows = []
    for step in plan.get("steps") or []:
        step_id = step.get("id")
        event = answers.get(step_id) or {}
        verdict = event.get("verdict")
        if verdict in counts:
            counts[verdict] += 1
        if verdict == "skipped" and event.get("reason"):
            reasons.append(event.get("reason"))
        resolves = step_resolves(event)
        if not resolves:
            unresolved.append(step_id)
        rows.append(
            {
                "id": step_id,
                "text": step.get("text"),
                "mode": step.get("mode"),
                "stateful": bool(step.get("stateful")),
                "status": verdict if verdict in counts else "unresolved",
                "resolved": resolves,
            }
        )
    return {
        "steps_seq": plan.get("seq"),
        "passed": counts["pass"],
        "skipped": counts["skipped"],
        "skipped_reasons": reasons,
        "deviated": counts["deviated"],
        "failed": counts["fail"],
        "unresolved": unresolved,
        "plan": rows,
    }


def render_step_tally(tally):
    """`passed N · skipped N (<reason>) · deviated N · unresolved N: <id>`."""
    if tally is None:
        return ""
    text = "passed %d · skipped %d" % (tally["passed"], tally["skipped"])
    if tally["skipped_reasons"]:
        text += " (%s)" % "; ".join(
            collapse_note(reason, 80) for reason in tally["skipped_reasons"]
        )
    text += " · deviated %d · unresolved %d" % (
        tally["deviated"],
        len(tally["unresolved"]),
    )
    if tally["unresolved"]:
        text += ": %s" % ", ".join(tally["unresolved"])
    return text


def render_step_plan(tally):
    """One line per recorded step: `  1. <id> [<mode>, stateful] — <status>: <text>`."""
    lines = []
    for number, row in enumerate((tally or {}).get("plan") or [], 1):
        marks = [str(row["mode"])] + (["stateful"] if row["stateful"] else [])
        lines.append(
            "  %d. %s [%s] — %s: %s"
            % (
                number,
                row["id"],
                ", ".join(marks),
                row["status"],
                collapse_note(str(row["text"] or ""), 200),
            )
        )
    return lines


def seq_commit_ranges(repo, unit):
    """``[(low, high, commit, order)]`` for a unit, from ONE ``git log`` walk.

    ``order`` is the position in git's own newest-first walk, which is what lets
    V15 say whether the trailer commits appear in seq order at all. The
    ``Dogen-Seq`` trailer is parsed HERE and nowhere else: :func:`find_seq_commit`
    and V15 read this list, so the two cannot come to spell the same trailer
    format differently. Ranges are kept as ranges rather than expanded, so a
    forged ``Dogen-Seq: 0-999999999`` costs nothing.
    """
    proc = git(
        [
            "log",
            "--format=%H%x1f%(trailers:key=Dogen-Unit,valueonly,separator=%x2c)"
            "%x1f%(trailers:key=Dogen-Seq,valueonly,separator=%x2c)",
        ],
        repo,
    )
    ranges = []
    if proc.returncode != 0:
        return ranges
    for order, line in enumerate(proc.stdout.splitlines()):
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        commit, owner, span = parts[0], parts[1].strip(), parts[2].strip()
        if owner != unit or not span:
            continue
        first, _, last = span.partition("-")
        try:
            low = int(first)
            high = int(last) if last else low
        except ValueError:
            continue
        if high < low:
            continue
        ranges.append((low, high, commit, order))
    return ranges


def seq_commit_entry(ranges, seq):
    """``(commit, order)`` for ``seq``, newest match first, or ``None``."""
    for low, high, commit, order in ranges:
        if low <= seq <= high:
            return commit, order
    return None


def find_seq_commit(repo, unit, seq):
    """The commit whose ``Dogen-Seq`` range covers ``seq`` for this unit.

    The trailer is the only link from a recorded event back to the bytes its
    transition committed. History rewriting can remove it, and that is exactly
    the case ``--diff`` reports rather than guesses at — and that ``verify``'s
    V15 reports as ``history_squashed`` over the same parsed ranges.
    """
    if seq is None:
        return None
    entry = seq_commit_entry(seq_commit_ranges(repo, unit), seq)
    return entry[0] if entry else None


def read_page_bytes(repo, path, unit):
    """The current bytes of a docs page, or ``b""`` when it is not there.

    IN-05 (phase 16): ``unit`` has no default. This function raises through
    :func:`contained_page`, and a refusal that names ``""`` as its unit is a
    refusal no skill can route on — so forgetting the argument is a loud
    ``TypeError`` here rather than a quietly misattributed refusal there.

    CR-05: it refuses an escaping path rather than returning ``b""``, so
    ``render_diff`` can never reach a file ``read_fs`` was not allowed to
    digest. The snapshot refuses first on every current caller, which is what
    makes this the second lock on the same door rather than the only one.
    """
    try:
        with open(contained_page(repo, unit, path), "rb") as handle:
            return handle.read()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        return b""


def render_diff(repo, unit, state, path):
    """``--diff``: a drifted path against the RECORDED basis bytes, or an honest no.

    When history rewriting has removed the commit the ``Dogen-Seq`` trailer
    pointed at, the recorded bytes are simply not reachable. A digest cannot be
    inverted and HEAD is not the same fact, so presenting either as the basis
    would be a guess in the record's own voice. The tool says so and shows the
    current content instead.
    """
    current = read_page_bytes(repo, path, unit)
    relative = os.path.join(DOCS_ROOT, path)
    commit = find_seq_commit(repo, unit, state["basis_seq"])
    recorded = git_show_blob(repo, commit, relative) if commit else None
    if recorded is None:
        lines = [
            "  the recorded basis bytes for %s are unavailable (the commit that "
            "recorded them is not reachable); the current content follows" % path
        ]
        return lines + [
            "  %s" % line for line in current.decode("utf-8", "replace").splitlines()
        ]
    return [
        "  %s" % line
        for line in difflib.unified_diff(
            recorded.decode("utf-8", "replace").splitlines(),
            current.decode("utf-8", "replace").splitlines(),
            fromfile="basis:%s" % path,
            tofile="disk:%s" % path,
            lineterm="",
        )
    ]


def cmd_show(args):
    """``show`` — the whole derived state, computed here and stored nowhere.

    One ``read_fs()`` snapshot, one ``derive()`` and one ``route()``: the state
    the author sees is the state every gate would read, and the ``Next:`` token
    is the one ``route()`` chose, never a second reading of the same table.

    Read-only under contract 5.8's write boundary — it classifies stage a
    identically to a mutating verb, prints what write mode would delete, and
    leaves ``ledger.jsonl``, every page, ``pending/`` and the git index
    byte-identical.
    """
    as_json = bool(getattr(args, "json", False))
    with_diff = bool(getattr(args, "diff", False))
    unit = args.unit
    repo = git_root()
    events, snapshot, state = read_only_unit(repo, unit)

    title, intent, _audience = unit_headline(events, state, unit)
    qualifier = state_qualifier(state)
    rows = describe_paths(repo, state, snapshot["paths"])
    floor = state["gen_seq"] if state["gen_seq"] is not None else 0
    requests = describe_requests(events, floor)
    edits = reviewer_edits_since(events, floor)
    tally = step_tally(events)
    token = route(state)

    if as_json:
        payload = {
            "unit": unit,
            "title": title,
            "intent": intent,
            "state": state["state"],
            "qualifier": qualifier,
            "paths": rows,
            "requests": requests,
            "reviewer_edits": edits,
            "steps": tally,
            "orphans": state["orphans"],
            "pending": state["pending"],
            "seqs": {
                "signoff": state["so_seq"],
                "generation": state["gen_seq"],
                "reviewer_edit": state["edit_seq"],
                "review": state["rev_seq"],
                "basis": state["basis_seq"],
                "tip": state["tip_seq"],
            },
            "next": token,
        }
        if with_diff:
            payload["diff"] = dict(
                (row["path"], "\n".join(render_diff(repo, unit, state, row["path"])))
                for row in rows
                if row["status"].startswith("drifted")
            )
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return EXITS["success"]

    out = [title]
    if intent:
        out.append("intent: %s" % intent)
    out.append(
        "state: %s%s" % (state["state"], " — %s" % qualifier if qualifier else "")
    )
    if rows:
        out.append("paths:")
        for row in rows:
            out.append("  %s — %s" % (row["path"], row["status"]))
            if with_diff and row["status"].startswith("drifted"):
                out.extend(render_diff(repo, unit, state, row["path"]))
    if requests:
        out.append("requests:")
        for row in requests:
            disposition = row["disposition"]
            if disposition == "withdrawn":
                disposition = "withdrawn: %s" % collapse_note(row["reason"], 200)
            out.append(
                "  seq %s — %s — %s: %s"
                % (
                    row["seq"],
                    disposition,
                    row["origin"],
                    collapse_note(row["note"], 200),
                )
            )
    if tally is not None:
        out.append("steps: %s" % render_step_tally(tally))
        out.extend(render_step_plan(tally))
    if edits:
        out.append("reviewer edits:")
        for entry in edits:
            out.append(
                "  edit at seq %s — %s"
                % (entry["seq"], collapse_note(entry["note"], 200))
            )
    out.append("Next: %s" % token)
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()
    return EXITS["success"]


# --- verify (contract 5.9) --------------------------------------------------

#: Contract 5.9 fixes the LEVEL of every check, and the level — not a judgment
#: at the call site — is what the exit rule keys off (T-17-41). V1–V13 are
#: record integrity and are the only ones that can report a FAIL. V14 is a
#: status. V15–V19 corroborate with git, which is tamper-EVIDENCE and never
#: tamper-proofing, so the worst they can report is a warning: a maintenance
#: edit or a squash merge reported as a failure trains the reader to ignore the
#: one signal that means the record is actually broken.
CHECK_LEVELS = {
    "V1": "fail",
    "V2": "fail",
    "V3": "fail",
    "V4": "fail",
    "V5": "fail",
    "V6": "fail",
    "V7": "fail",
    "V8": "fail",
    "V9": "fail",
    "V10": "fail",
    "V11": "fail",
    "V12": "fail",
    "V13": "fail",
    "V14": "status",
    "V15": "warn",
    "V16": "warn",
    "V17": "info",
    "V18": "warn",
    "V19": "warn",
}

#: Contract 5.3's ``step-recorded`` payload, required half. V8 reads it.
STEP_RECORD_KEYS = (
    "step_id",
    "steps_seq",
    "text_hash",
    "mode",
    "verdict",
    "exit_code",
    "output_sha256",
    "output_excerpt",
)


def check_record(vid, ok, detail):
    """One check record: ``{id, level, status, detail}``.

    The level comes from :data:`CHECK_LEVELS` and the status is DERIVED from it,
    so a call site cannot decide that its own finding is "only a warning" — the
    contract decided that, per id, in one table.
    """
    level = CHECK_LEVELS[vid]
    return {
        "id": vid,
        "level": level,
        "status": "ok" if ok else ("fail" if level == "fail" else "warn"),
        "detail": detail,
    }


def _finding(vid, problems, clean):
    """``clean`` when nothing was found, else the first problem and a count."""
    if not problems:
        return check_record(vid, True, clean)
    detail = problems[0]
    if len(problems) > 1:
        detail += " (and %d more)" % (len(problems) - 1)
    return check_record(vid, False, detail)


def _seq_of(event):
    """An event's ``seq`` as an int, or ``-1``.

    A ledger is contributor input (CR-04): every comparison below runs against
    whatever a forged, hand-repaired or future-tool-written record spells, and
    an ``int`` against a ``None`` is a ``TypeError`` that would escape as an
    exit-1 gate refusal. An unusable seq sorts before every real one, which is
    the same answer the comparison would have given had it been able to run.
    """
    seq = (event or {}).get("seq")
    return seq if _is_seq(seq) else -1


def _seq_list(seqs):
    """``"3, 4, 5"`` — a seq list in one voice, for details that name several."""
    return ", ".join(str(seq) for seq in seqs)


def lenient_events(lines):
    """Parsed events for ``verify``, skipping any line that is not an object.

    :func:`read_events` REFUSES such a line, correctly, for every verb that is
    about to act on the record. ``verify`` is the one reader whose job is to
    REPORT it, and it cannot report from behind a refusal — so it parses what it
    can and lets V2 and V3 name the rest over the exact bytes.
    """
    events = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def verify_integrity(unit, lines, committed, partial=""):
    """V1–V4 — the four checks that read the ledger's own bytes.

    Pure: lines in, records out. No repository, no snapshot and no derivation,
    because none of the four is a question about derived state.
    """
    rows = []
    parsed = []
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except ValueError:
            parsed.append(None)

    # V1 — the header
    if not lines:
        rows.append(check_record("V1", True, "the ledger holds no event yet"))
    else:
        header = parsed[0] if isinstance(parsed[0], dict) else None
        if header is None:
            rows.append(
                check_record("V1", False, "line 1 is not a JSON object, so there is no header")
            )
        elif header.get("kind") != "ledger" or header.get("seq") != 0:
            rows.append(
                check_record(
                    "V1",
                    False,
                    "the first event is %r at seq %r, not the ledger header"
                    % (header.get("kind"), header.get("seq")),
                )
            )
        elif header.get("v") != CONTRACT:
            rows.append(
                check_record(
                    "V1",
                    False,
                    "ledger version %r is not supported; this tool reads v%d"
                    % (header.get("v"), CONTRACT),
                )
            )
        elif header.get("unit") != unit:
            rows.append(
                check_record(
                    "V1",
                    False,
                    "the header records unit %r, not %r" % (header.get("unit"), unit),
                )
            )
        else:
            rows.append(
                check_record("V1", True, "the header is a v%d ledger event for %r at seq 0" % (CONTRACT, unit))
            )

    # V2 — every line parses, re-serializes canonically and sits within the caps
    problems = []
    for index, line in enumerate(lines):
        number = index + 1
        size = byte_len(line)
        if size > MAX_LINE_BYTES:
            problems.append(
                "line %d is %d bytes; the cap is %d" % (number, size, MAX_LINE_BYTES)
            )
            continue
        event = parsed[index]
        if event is None:
            problems.append("line %d is not valid JSON" % number)
            continue
        try:
            canonical = canonical_line(event)
        except (ValueError, Refusal):
            problems.append("line %d does not re-serialize canonically" % number)
            continue
        if canonical != line:
            problems.append(
                "line %d is not the canonical serialization of its own event" % number
            )
    clean = "%d line(s) parse, re-serialize canonically and sit within the %d-byte cap" % (
        len(lines),
        MAX_LINE_BYTES,
    )
    if partial:
        # A truncated FINAL line is contract 5.8's `uncommitted_tail`, whose
        # answer is `resume` — not `ledger_corrupt`. Failing V2 on it would exit
        # 6 with the wrong reason on exactly the unit this verb was widened to
        # report on (RESEARCH Pitfall 7), so it is named and not counted.
        clean += SEGMENT + "a truncated final line is present; dogen resume %s" % unit
    rows.append(_finding("V2", problems, clean))

    # V3 — seq contiguity and the prev chain, over `verify_chain`'s findings.
    # Phase 16 changed that function from a boolean to a findings list FOR this
    # consumer; re-walking the same bytes here would be a second opinion.
    chain = verify_chain(lines)
    rows.append(
        _finding(
            "V3",
            chain,
            "seq is contiguous from 0 over %d line(s) and every prev matches the "
            "previous line's bytes" % len(lines),
        )
    )

    # V4 — the committed prefix
    if not committed:
        rows.append(
            check_record(
                "V4",
                True,
                "HEAD holds no ledger for this unit, so there is no committed prefix to match",
            )
        )
    elif list(lines[: len(committed)]) != list(committed):
        differs = next(
            (
                index + 1
                for index, line in enumerate(committed)
                if index >= len(lines) or lines[index] != line
            ),
            len(committed),
        )
        rows.append(
            check_record(
                "V4",
                False,
                "the committed prefix no longer matches HEAD's copy; line %d differs"
                % differs,
            )
        )
    else:
        rows.append(
            check_record(
                "V4",
                True,
                "the first %d line(s) are byte-identical to HEAD's copy" % len(committed),
            )
        )
    return rows


def verify_derivation(events):
    """V5–V13 — contract 5.4's derivation invariants, restated per event.

    Pure and repository-free. Every clause below is HISTORICAL — "the signoff
    current at this generation's seq", "the pending set at this accept's seq" —
    which :func:`derive` does not carry, because derive answers about the record
    as it stands NOW. So these read the event list rather than re-deriving
    state, and the one place a whole-record fact is needed (the pending set) is
    :func:`pending_requests`, which derive itself calls.

    Contract 5.9: the gates run over KNOWN kinds only. An unrecognised kind is
    ignored here exactly as derive ignores it, and the single WARN it earns is
    derive's, reported once by the caller. 5.9's ``superseded_by`` is reserved
    and NOT evaluated: no clause reads it, so a record carrying it verifies
    exactly as one that does not.
    """
    known = [
        event
        for event in events
        if isinstance(event, dict) and event.get("kind") in KNOWN_KINDS
    ]
    signoffs = [e for e in known if e.get("kind") == "signoff"]
    generations = [e for e in known if e.get("kind") == "generation"]
    edits = [e for e in known if e.get("kind") == "reviewer-edit"]
    reviews = [e for e in known if e.get("kind") == "review"]
    accepts = [e for e in reviews if e.get("verdict") == "accept"]
    plans = [e for e in known if e.get("kind") == "steps-planned"]
    records = [e for e in known if e.get("kind") == "step-recorded"]
    plans_by_seq = dict((plan.get("seq"), plan) for plan in plans)

    def current(candidates, seq):
        """The last event of ``candidates`` strictly before ``seq``."""
        found = None
        for event in candidates:
            if _seq_of(event) < seq:
                found = event
        return found

    def before(seq):
        """Every known event strictly before ``seq``, in order."""
        return [event for event in known if _seq_of(event) < seq]

    rows = []

    # V5 — every generation cites the signoff current at its seq with an equal
    # plan_hash; every accept's generation cites the signoff current at the
    # ACCEPT's seq (a re-sign after the draft un-seals it).
    problems = []
    for gen in generations:
        so = current(signoffs, _seq_of(gen))
        if so is None:
            problems.append(
                "the generation at seq %s has no signoff before it" % _seq_of(gen)
            )
        elif gen.get("signoff_seq") != so.get("seq"):
            problems.append(
                "the generation at seq %s cites signoff %r; the signoff current at "
                "its seq is %r" % (_seq_of(gen), gen.get("signoff_seq"), so.get("seq"))
            )
        elif gen.get("plan_hash") != so.get("plan_hash"):
            problems.append(
                "the generation at seq %s records a plan_hash its signoff at seq %r "
                "does not" % (_seq_of(gen), so.get("seq"))
            )
    for rev in accepts:
        gen = next(
            (g for g in generations if g.get("seq") == rev.get("generation_seq")), None
        )
        so = current(signoffs, _seq_of(rev))
        if gen is None:
            problems.append(
                "the accept at seq %s names generation %r, which is not in the record"
                % (_seq_of(rev), rev.get("generation_seq"))
            )
        elif so is None or gen.get("signoff_seq") != so.get("seq"):
            problems.append(
                "the accept at seq %s seals a generation citing signoff %r; the "
                "signoff current at the accept is %r"
                % (
                    _seq_of(rev),
                    gen.get("signoff_seq"),
                    so.get("seq") if so is not None else None,
                )
            )
    total = len(generations) + len(accepts)
    rows.append(
        _finding(
            "V5",
            problems,
            "%d generation(s) and accept(s) cite the signoff current at their seq"
            % total
            if total
            else "no generation and no accept to check",
        )
    )

    # V6 — review / reviewer-edit citation, and accept files == basis
    problems = []
    for rev in reviews:
        last_gen = current(generations, _seq_of(rev))
        expected = last_gen.get("seq") if last_gen is not None else None
        if rev.get("generation_seq") != expected:
            problems.append(
                "the review at seq %s cites generation %r; the last generation at "
                "its seq is %r" % (_seq_of(rev), rev.get("generation_seq"), expected)
            )
    for edit in edits:
        last_gen = current(generations, _seq_of(edit))
        expected = last_gen.get("seq") if last_gen is not None else None
        if edit.get("generation_seq") != expected:
            problems.append(
                "the reviewer edit at seq %s cites generation %r; the last "
                "generation at its seq is %r (null iff none existed)"
                % (_seq_of(edit), edit.get("generation_seq"), expected)
            )
    for rev in accepts:
        basis = _later(
            current(generations, _seq_of(rev)), current(edits, _seq_of(rev))
        )
        if _basis_pairs(rev) != _basis_pairs(basis):
            problems.append(
                "the accept at seq %s seals files that are not the basis at seq %r"
                % (_seq_of(rev), basis.get("seq") if basis is not None else None)
            )
    total = len(reviews) + len(edits)
    rows.append(
        _finding(
            "V6",
            problems,
            "%d review(s) and reviewer edit(s) cite the basis they were made against"
            % total
            if total
            else "no review and no reviewer edit to check",
        )
    )

    # V7 — no two generations without an intervening H event, unless the later
    # one carries `unsteered: true` WITH a reason.
    problems = []
    for index in range(1, len(generations)):
        previous, gen = generations[index - 1], generations[index]
        low, high = _seq_of(previous), _seq_of(gen)
        if any(_is_h_event(event) and low < _seq_of(event) < high for event in known):
            continue
        if gen.get("unsteered") is True and gen.get("unsteered_reason"):
            continue
        problems.append(
            "the generation at seq %s follows the one at seq %s with no intervening "
            "steering, review fix or redraft and no unsteered reason" % (high, low)
        )
    rows.append(
        _finding(
            "V7",
            problems,
            "%d consecutive generation pair(s) are separated by an H event or "
            "declared unsteered" % max(len(generations) - 1, 0)
            if len(generations) > 1
            else "fewer than two generations, so no pair to check",
        )
    )

    # V8 — step text hashes against their plan, and the evidence shape 5.3 fixes
    problems = []
    for rec in records:
        plan = plans_by_seq.get(rec.get("steps_seq"))
        if plan is None:
            problems.append(
                "the step record at seq %s names steps-planned %r, which is not in "
                "the record" % (_seq_of(rec), rec.get("steps_seq"))
            )
            continue
        step = next(
            (
                entry
                for entry in (plan.get("steps") or [])
                if entry.get("id") == rec.get("step_id")
            ),
            None,
        )
        if step is None:
            problems.append(
                "the step record at seq %s names step %r, which the plan at seq %r "
                "does not carry"
                % (_seq_of(rec), rec.get("step_id"), plan.get("seq"))
            )
            continue
        if rec.get("text_hash") != step.get("text_hash"):
            problems.append(
                "the step record at seq %s records a text_hash the plan's step %r "
                "does not" % (_seq_of(rec), rec.get("step_id"))
            )
        # WR-02: the same divergence `cmd_step` now refuses at record time,
        # reported over records written before that gate existed. `mode` is
        # half of contract 5.4's reuse prefix key, so a record that contradicts
        # its plan makes the carry-forward walk reason over a mode the evidence
        # denies.
        if rec.get("mode") != step.get("mode"):
            problems.append(
                "the step record at seq %s claims mode %r; the plan's step %r "
                "declares %r"
                % (_seq_of(rec), rec.get("mode"), rec.get("step_id"), step.get("mode"))
            )
        missing = [key for key in STEP_RECORD_KEYS if key not in rec]
        if missing:
            problems.append(
                "the step record at seq %s is missing %s"
                % (_seq_of(rec), ", ".join(missing))
            )
        elif step_reason_required(rec) and not rec.get("reason"):
            problems.append(
                "the step record at seq %s is a %r at exit %r and carries no reason"
                % (_seq_of(rec), rec.get("verdict"), rec.get("exit_code"))
            )
    rows.append(
        _finding(
            "V8",
            problems,
            "%d step record(s) match their plan's hash and mode and carry 5.3's "
            "fields" % len(records)
            if records
            else "no step record to check",
        )
    )

    # V9 — an actionable generation had every step resolved at its seq
    problems = []
    actionable = 0
    for gen in generations:
        so = current(signoffs, _seq_of(gen))
        if so is None or so.get("intent") not in ACTIONABLE_INTENTS:
            continue
        actionable += 1
        plan = plans_by_seq.get(gen.get("steps_seq")) or current(plans, _seq_of(gen))
        if plan is None:
            problems.append(
                "the actionable generation at seq %s names no step plan" % _seq_of(gen)
            )
            continue
        outstanding = unresolved_steps(before(_seq_of(gen)), plan)
        if outstanding:
            problems.append(
                "the actionable generation at seq %s was recorded with step(s) %s "
                "unresolved" % (_seq_of(gen), ", ".join(str(s) for s in outstanding))
            )
    rows.append(
        _finding(
            "V9",
            problems,
            "%d actionable generation(s) had every step resolved at their seq"
            % actionable
            if actionable
            else "no actionable generation to check",
        )
    )

    # V10 — every accept's dispositions against the pending set at its seq
    problems = []
    for rev in accepts:
        floor_event = current(generations, _seq_of(rev))
        floor = _seq_of(floor_event) if floor_event is not None else 0
        pending = set(pending_requests(before(_seq_of(rev)), floor))
        resolves = set(
            seq for seq in (rev.get("resolves") or []) if _is_seq(seq)
        )
        entries = [
            entry for entry in (rev.get("withdraws") or []) if isinstance(entry, dict)
        ]
        withdraws = set(
            entry.get("seq") for entry in entries if _is_seq(entry.get("seq"))
        )
        seq = _seq_of(rev)
        if pending - (resolves | withdraws):
            problems.append(
                "the accept at seq %s leaves request(s) %s with no disposition"
                % (seq, _seq_list(sorted(pending - (resolves | withdraws))))
            )
        if resolves - pending:
            problems.append(
                "the accept at seq %s resolves seq(s) %s, which were not pending"
                % (seq, _seq_list(sorted(resolves - pending)))
            )
        if withdraws - pending:
            problems.append(
                "the accept at seq %s withdraws seq(s) %s, which were not pending"
                % (seq, _seq_list(sorted(withdraws - pending)))
            )
        if resolves & withdraws:
            problems.append(
                "the accept at seq %s both resolves and withdraws seq(s) %s"
                % (seq, _seq_list(sorted(resolves & withdraws)))
            )
        for entry in entries:
            if not entry.get("reason"):
                problems.append(
                    "the accept at seq %s withdraws seq %r with no reason"
                    % (seq, entry.get("seq"))
                )
    rows.append(
        _finding(
            "V10",
            problems,
            "%d accept(s) dispose of exactly the requests pending at their seq"
            % len(accepts)
            if accepts
            else "no accept to check",
        )
    )

    # V11 — model / origin consistency, through the validator the write side uses
    problems = []
    for gen in generations:
        try:
            validate_model(gen.get("model"), gen.get("model_origin"))
        except Refusal as inconsistent:
            problems.append(
                "the generation at seq %s: %s" % (_seq_of(gen), inconsistent.detail)
            )
    rows.append(
        _finding(
            "V11",
            problems,
            "%d generation(s) record a model consistent with its origin" % len(generations)
            if generations
            else "no generation to check",
        )
    )

    # V12 — a reuse plan states why it reuses
    problems = [
        "the step plan at seq %s carries reuse:true with no reuse_note" % _seq_of(plan)
        for plan in plans
        if plan.get("reuse") and not plan.get("reuse_note")
    ]
    rows.append(
        _finding(
            "V12",
            problems,
            "%d step plan(s) carry a reuse_note wherever they reuse" % len(plans)
            if plans
            else "no step plan to check",
        )
    )

    # V13 — files against the signed targets
    problems = []
    for gen in generations:
        so = current(signoffs, _seq_of(gen))
        targets = sorted(so.get("targets") or []) if so is not None else []
        files = sorted(path for path, _ in _basis_pairs(gen))
        if files != targets:
            problems.append(
                "the generation at seq %s records files %s; the signoff current at "
                "its seq targets %s" % (_seq_of(gen), files, targets)
            )
    for edit in edits:
        previous = _later(
            current(generations, _seq_of(edit)), current(edits, _seq_of(edit))
        )
        if previous is None:
            continue
        so = current(signoffs, _seq_of(edit))
        targets = set(so.get("targets") or []) if so is not None else set()
        # "a superset of the previous basis minus missing non-targets" — the
        # decidable half. Whether a dropped path was missing FROM DISK at the
        # time is not in the record, so what is checked is the part that is: a
        # path may be dropped only if it is no longer a signed target.
        kept = set(path for path, _ in _basis_pairs(previous)) & targets
        dropped = sorted(kept - set(path for path, _ in _basis_pairs(edit)))
        if dropped:
            problems.append(
                "the reviewer edit at seq %s drops still-signed basis path(s) %s"
                % (_seq_of(edit), ", ".join(dropped))
            )
    total = len(generations) + len(edits)
    rows.append(
        _finding(
            "V13",
            problems,
            "%d generation(s) and reviewer edit(s) record the files their signoff "
            "targets" % total
            if total
            else "no generation and no reviewer edit to check",
        )
    )
    return rows


def verify_currency(repo, state, paths):
    """V14 — page currency, through the renderer ``show`` already calls.

    :func:`describe_paths` — and through it :func:`drift_status` — owns the four
    status words (``current``, ``drifted (…)``, ``missing``, the orphan
    wording). ``show``'s text and ``summary``'s golden pin them, so V14
    RE-LABELS those rows rather than growing a second vocabulary for the same
    comparison: that is how two surfaces start disagreeing about whether a page
    is current. A path whose disk bytes equal the recorded digest therefore
    reports ``current`` here by construction, not by a second comparison.
    """
    if state.get("basis") is None:
        return [
            check_record(
                "V14", True, "no basis is recorded, so no page has a currency to report"
            )
        ]
    rows = describe_paths(repo, state, paths)
    if not rows:
        return [check_record("V14", True, "the basis records no path")]
    unsettled = [
        row
        for row in rows
        if row["status"] in ("missing", "new") or row["status"].startswith("drifted")
    ]
    detail = SEGMENT.join("%s: %s" % (row["path"], row["status"]) for row in rows)
    return [check_record("V14", not unsettled, detail)]


def verify_summary(checks, notes=()):
    """The report's verdict and counts — the one place the exit rule reads.

    ``failed`` is the ids of the record-integrity checks that FAILED, and by
    construction it can hold nothing else: only a ``fail``-level check can carry
    a ``fail`` status (:func:`check_record`). ``warn`` counts every warning the
    report carries — a warn-status check and a note line alike, because 5.9's
    unknown-kind WARN is a note rather than a check.
    """
    failed = [row["id"] for row in checks if row["status"] == "fail"]
    warn = len([row for row in checks if row["status"] == "warn"]) + len(list(notes))
    return {
        "verdict": "fail" if failed else ("warn" if warn else "ok"),
        "checks": len(checks),
        "warn": warn,
        "fail": len(failed),
        "failed": failed,
    }


def verify_report_lines(head, checks, notes=()):
    """The text report: the notes, one line per check in V order, one summary.

    The summary line's short sha is the same 7 characters every other read
    surface prints, so ``TestSummaryGolden``'s ``<sha7>`` substitution
    normalises this line too and a WORDING change stays a deliberate edit.
    """
    out = ["note: %s" % note for note in notes]
    out += ["%s %s — %s" % (row["id"], row["status"], row["detail"]) for row in checks]
    counts = verify_summary(checks, notes)
    out.append(
        SEGMENT.join(
            [
                "verdict: %s" % counts["verdict"],
                "head %s" % (head[:7] if head else "no commit"),
                "%d checks" % counts["checks"],
                "%d warn" % counts["warn"],
                "%d fail" % counts["fail"],
            ]
        )
    )
    return out


def verify_corroboration(repo, unit, events, state, committed):
    """V15–V19 — what git can corroborate, at the levels contract 5.9 fixes.

    None of the five can report a FAIL, and that is the point rather than an
    oversight: git history is rewritable, so it is tamper-EVIDENCE and never
    tamper-proofing (T-17-40). A maintenance edit or a squash merge reported as
    a failure trains the reader to ignore the one signal — a record-integrity
    FAIL — that means the record is actually broken.

    ``committed`` is the number of ledger lines HEAD already holds, which is
    exactly the range V15 can ask about: a line that is not committed has no
    commit to look for.
    """
    rows = []
    ranges = seq_commit_ranges(repo, unit)

    # V15 — a trailer commit behind every committed seq, in seq order
    missing = []
    out_of_order = []
    previous_order = None
    for seq in range(committed):
        entry = seq_commit_entry(ranges, seq)
        if entry is None:
            missing.append(seq)
            continue
        order = entry[1]
        # git logs newest first, so a later seq must sit at an EARLIER position.
        if previous_order is not None and order > previous_order:
            out_of_order.append(seq)
        previous_order = order
    problems = []
    if missing:
        problems.append(
            "history_squashed: the ledger line(s) at seq %s are committed and no "
            "commit carries their Dogen-Seq trailer" % _seq_list(missing)
        )
    if out_of_order:
        problems.append(
            "history_squashed: the trailer commits for seq %s do not appear in seq "
            "order in this history" % _seq_list(out_of_order)
        )
    rows.append(
        _finding(
            "V15",
            problems,
            "%d committed seq(s) have their Dogen-Seq trailer commit, in order"
            % committed
            if committed
            else "no committed event to corroborate",
        )
    )

    # V16 — the recorded pre-transition HEAD, in this history
    head = git_head(repo)
    problems = []
    checked = 0
    if head is None:
        clean = "the repository has no commit, so no recorded commit can be placed"
    elif missing:
        # The rewrite V15 just named is the reason this ancestry cannot hold, so
        # reporting it a SECOND time under another name would double-count one
        # fact — and contract 5.9's history policy is explicit that a squash
        # merge is green except `history_squashed`.
        clean = (
            "not evaluated: V15 reports this history as squashed, and a rewrite is "
            "reported once under its own name"
        )
    else:
        ancestry = {}
        for event in events:
            commit = event.get("commit")
            if not isinstance(commit, str) or not commit:
                continue
            if commit not in ancestry:
                probe = git(["merge-base", "--is-ancestor", commit, head], repo)
                ancestry[commit] = probe.returncode == 0
            checked += 1
            if not ancestry[commit]:
                problems.append(
                    "ledger_diverged: the commit recorded at seq %s (%s) is not an "
                    "ancestor of HEAD" % (_seq_of(event), commit[:7])
                )
        clean = (
            "%d recorded commit(s) are ancestors of HEAD" % checked
            if checked
            else "no event records a commit to place in this history"
        )
    rows.append(_finding("V16", problems, clean))

    # V17 — the ignore pattern that scopes the staging path and the attribute
    # that pins the ledger's text handling. Both asked of GIT, through the
    # locale-pinned wrapper, rather than read out of the two files by hand: a
    # second parser of .gitignore/.gitattributes is a second opinion about
    # patterns git already owns (WR-01's argument, applied to the read surface).
    staging = os.path.join(".dogen", "staging")
    ignored = git(
        ["check-ignore", "-q", "--", os.path.join(staging, "lock")],
        repo,
        env=IPC_LOCALE,
    )
    relative = os.path.relpath(ledger_path(repo, unit), os.fspath(repo))
    attribute = git(["check-attr", "text", "--", relative], repo, env=IPC_LOCALE)
    pinned = attribute.returncode == 0 and attribute.stdout.strip().endswith(": unset")
    problems = []
    if ignored.returncode != 0:
        problems.append("%s/ is not gitignored" % staging)
    if not pinned:
        problems.append(
            "%s is not pinned -text; contract 5.2 puts `*.jsonl -text` in "
            ".dogen/.gitattributes" % relative
        )
    rows.append(
        _finding(
            "V17",
            [SEGMENT.join(problems)] if problems else [],
            "%s/ is gitignored and the ledger is pinned -text" % staging,
        )
    )

    # V18 — one target, more than one live unit. No single invocation can
    # produce this (the claim policy refuses it); a merge can.
    mine = set(state.get("targets") or [])
    problems = []
    if mine:
        units = os.path.join(os.fspath(repo), ".dogen", "units")
        names = sorted(os.listdir(units)) if os.path.isdir(units) else []
        for other in names:
            if other == unit or not os.path.exists(ledger_path(repo, other)):
                continue
            try:
                sibling = unit_claims(repo, other)
            except Refusal:
                # A sibling this tool cannot read is a fact about that unit's
                # record, not about this one's. `find_claim` fails closed on the
                # WRITE side, where a claim that cannot be ruled out must block;
                # a REPORT that refuses because a neighbour is damaged tells the
                # author nothing about the unit they asked about.
                continue
            if sibling["retired"]:
                continue
            shared = sorted(mine.intersection(sibling["targets"]))
            if shared:
                problems.append(
                    "%s and %s both claim %s" % (unit, other, ", ".join(shared))
                )
    rows.append(
        _finding(
            "V18",
            problems,
            "no other live unit claims any of %s's %d target(s)" % (unit, len(mine))
            if mine
            else "no signed target to claim",
        )
    )

    # V19 — the context digests the signoff recorded, and the plan
    so = state.get("so")
    problems = []
    if so is None:
        clean = "no signoff, so there is no recorded context to compare"
    else:
        context = so.get("context") or {}
        root = os.fspath(repo)
        for path in sorted(context):
            full = os.path.join(root, path)
            digest = digest_file(full) if contained(root, full) else None
            if digest is None:
                problems.append(
                    "the source %s recorded at the signoff cannot be read now" % path
                )
            elif digest != context[path]:
                problems.append("the source %s has changed since the signoff" % path)
        if state.get("plan_stale"):
            problems.append(
                "plan_stale: unit.md has changed since the signoff at seq %s"
                % state.get("so_seq")
            )
        clean = (
            "%d recorded context digest(s) still match and the plan is current"
            % len(context)
        )
    rows.append(_finding("V19", problems, clean))
    return rows


def run_verify(repo, unit, events, snapshot, state, split=None):
    """Contract 5.9's V1–V19 over one unit, as an ordered list of check records.

    ONE ledger split, ONE ``read_fs`` snapshot and ONE :func:`derive` result
    come in; nothing here re-derives routing or state. That is what keeps the
    record's story single-valued — a verifier that recomputes what the tool
    computes can disagree with the tool the author is actually driving, which is
    also why phase 19's scorer keeps its independent oracle to four checks.

    Two reuses are load-bearing rather than incidental:

    * V2 and V3 consume :func:`verify_chain`'s findings list. Phase 16 changed
      that function from returning a boolean to returning findings FOR this
      consumer; re-walking the same bytes here would be a second opinion.
    * V14 renders through :func:`describe_paths`, and with it
      :func:`drift_status` — the same four status words ``show``'s text and
      ``summary``'s golden already pin.

    Every check runs and reports, vacuous or not: a check with nothing to
    examine says so rather than falling silent. Silence and success are
    indistinguishable to a reader, and this report exists to be read (T-17-39).
    """
    complete, partial, committed, _relative = (
        split if split is not None else ledger_split(repo, unit)
    )
    rows = []
    rows += verify_integrity(unit, complete, committed, partial)
    rows += verify_derivation(events)
    rows += verify_currency(repo, state, snapshot.get("paths") or {})
    rows += verify_corroboration(repo, unit, events, state, len(committed))
    return rows


# --- summary ----------------------------------------------------------------


def md_value(text):
    """The two properties EVERY ``summary --md`` value needs, before position.

    Non-strings are rendered rather than refused — this is a report, and the
    reader is better served by seeing what the record holds than by a crash on
    the read-only verb. ``.dogen/`` is committed and the chain is an unkeyed
    sha256, so a forged ``note`` really is contributor input: before WR-01
    ``md_cell`` reached ``str.replace`` on it directly and raised
    ``AttributeError`` out of :func:`summary_markdown` into ``main``'s
    catch-all, reporting ``ledger_corrupt`` (6) — "the record could not be
    derived" — for a record that derives perfectly well.

    ``\r`` goes with it because no position wants one.
    """
    if not isinstance(text, str):
        text = "%s" % (text,)
    return text.replace("\r", "")


def md_bound(text, limit=400):
    """The cap, for a position that keeps its newlines.

    :func:`collapse_note` caps too, but only as part of flattening to one line.
    A table cell is the one position whose contract REQUIRES the newlines
    (T-16-39: they become ``<br>`` and the table keeps its column count), so it
    needs the cap without the flattening.
    """
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def md_cell(text, limit=400):
    """Escape a value that lands inside a Markdown table cell — and only there.

    Everywhere else the author's text is reproduced verbatim, ``|`` and
    newlines included: the ledger carries them as ordinary JSON characters and
    the round-trip claim is only true if nothing quietly edits them. A table
    cell is the one place those characters would break the document's own
    structure, so here a pipe is escaped and a newline becomes a ``<br>``. The
    characters stay visible; the table keeps its column count (T-16-39).

    ``&``/``<``/``>`` are escaped for the reason :func:`md_text` states — this
    document is pasted into a pull request and Markdown renders raw HTML — and
    the two rules are independent, so the cell keeps its ``<br>`` AND loses its
    live elements (CR-03). The order is load-bearing: the HTML escaping runs
    first, so the ``<br>`` this function emits afterwards is a real break rather
    than the text ``&lt;br&gt;``. Steering notes and withdrawal reasons land in
    this position, and they are the most common contributor-controlled strings
    in the whole report.

    WR-01: the position also takes :func:`md_value` and :func:`md_bound`, which
    is what its two siblings get from :func:`md_flat`. CR-03 added the HTML
    escaping here and left both out, so the ONE render whose threat model is "a
    reviewer pastes this into a PR" was the UNCAPPED one — a legitimate 60 KiB
    steering note, well inside ``MAX_NOTE_BYTES``, produced a 60 KiB
    ``summary --md`` against a 388-byte ``summary``, exactly inverting the
    invariant :func:`md_flat` states. Like its siblings the cap is measured on
    the value BEFORE escaping: the escaping can only expand it by a constant
    factor, and capping afterwards would cut an entity in half.
    """
    return (
        md_bound(md_value(text), limit)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", "<br>")
    )


def md_flat(text, limit=400):
    """One capped line — a value can never open a block of its own (WR-11).

    The ONE property every contributor-controlled value needs before it is
    interpolated into ``summary --md``: no newline, so a forged note cannot
    close the sentence it is in and open a ``## Provenance`` of its own, and a
    cap, so it cannot bury the reviewer's own text under 64 KiB of anything.

    The non-string guard and the ``\r`` strip are :func:`md_value`'s, shared
    with :func:`md_cell` — which is a cell, not a line, and so cannot use this
    function itself.
    """
    return collapse_note(md_value(text), limit)


def md_text(text, limit=400):
    """A contributor value in PROSE position: flat, and with no raw HTML.

    ``.dogen/`` is committed, so every note, title and gap in it is ordinary
    contributor input (the threat model :func:`contained_page` states), and
    ``summary --md`` is documented as text a reviewer PASTES INTO A PR. Markdown
    renders raw HTML, so ``<img src=…>`` in a forged note is a live element in
    the reviewer's own pull request. ``&`` is escaped with it so the escaping
    round-trips: a note that literally says ``&lt;`` still reads ``&lt;``.

    Only the non-cell positions use this. A table cell keeps :func:`md_cell`,
    whose ``<br>`` is deliberate and whose contract is the table's column count
    — it does the same HTML escaping, for the same reason, before emitting that
    ``<br>``.
    """
    return (
        md_flat(text, limit)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def md_code(text, limit=400):
    """A contributor value inside a CODE SPAN: flat, with no way out of it.

    A code span renders its content literally, so HTML needs no escaping here —
    but a backtick ends the span, and everything after it is document again.
    Every legitimate value in this position (a validated target path, a model
    name) has none, so the removal is a no-op on the real input and a defused
    one on a forged record.
    """
    return md_flat(text, limit).replace("`", "")


def sphinx_result(repo):
    """The external Sphinx result, when a ``validation/RUN-*.json`` records one.

    Reported, never produced: dogen does not build, and the RUN file is written
    by whoever ran Sphinx. With no such file the section is simply absent.

    WR-11: the RUN file is UNTRACKED, unvalidated working-tree input, and its
    ``sphinx`` value was ``%s``-formatted into the document whatever it was —
    a dict, a list, or a megabyte of text. Only a non-empty string is reported,
    and only its first 120 collapsed characters: a result this tool did not
    produce and cannot check gets the space of a result line, not the space of
    a document.
    """
    directory = os.path.join(os.fspath(repo), "validation")
    try:
        names = sorted(
            name
            for name in os.listdir(directory)
            if name.startswith("RUN-") and name.endswith(".json")
        )
    except OSError:
        return ""
    for name in names:
        try:
            with open(os.path.join(directory, name), "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        result = data.get("sphinx", data.get("status"))
        if not isinstance(result, str) or not result.strip():
            continue
        return "%s (validation/%s)" % (collapse_note(result, 120), name)
    return ""


def provenance_line(repo, unit, state, checks):
    """`record: … · page: …` — two halves, each claiming only what was checked.

    The record half is `verify`'s OWN verdict over `checks`, computed by
    :func:`run_verify` in this same invocation, over the same snapshot and the
    same derivation. Through phase 16 it said the verifier had not run, because
    V1–V19 were phase-17 work (T-16-37, broken window 9); now it quotes the
    verdict, the short head sha and the counts, and a failing record names the
    ids that failed. The page half compares the recorded basis digests with the
    bytes on disk — the one thing the record settles on its own — and it stays
    separate because the two answer different questions.
    """
    head = git(["rev-parse", "--short=7", "HEAD"], repo).stdout.strip() or "no commit"
    counts = verify_summary(checks, state.get("warnings") or [])
    record = "verify %s at %s (%d checks, %d warn, %d fail%s)" % (
        counts["verdict"],
        head,
        counts["checks"],
        counts["warn"],
        counts["fail"],
        (": " + ", ".join(counts["failed"])) if counts["failed"] else "",
    )
    if state["basis"] is None:
        page = "no basis recorded"
    elif state["page_missing"]:
        page = "missing"
    elif state["page_drift"]:
        commit = find_seq_commit(repo, unit, state["basis_seq"])
        sha = (commit or state["basis"].get("commit") or "")[:7] or "unknown"
        page = "drifted since %s" % sha
    else:
        page = "current"
    return "record: %s · page: %s" % (record, page)


def summary_data(repo, unit, events, snapshot, state):
    """Everything §3.3 says `summary` reports, gathered once and rendered thrice.

    ``snapshot`` is the caller's own ``read_fs`` result, threaded through rather
    than re-taken: the provenance half runs :func:`run_verify` over it, so the
    record's verdict and the page's status describe ONE instant. A second
    snapshot here would let `summary` report a page as current and drifted in
    the same breath.
    """
    title, intent, audience = unit_headline(events, state, unit)
    checks = run_verify(repo, unit, events, snapshot, state)
    gen = state["gen"]
    floor = state["gen_seq"] if state["gen_seq"] is not None else 0
    gaps = list((gen or {}).get("gaps") or [])
    gaps_note = (gen or {}).get("gaps_note") or ""
    if gaps_note:
        gaps.append(gaps_note)
    return {
        "unit": unit,
        "title": title,
        "intent": intent,
        "audience": audience,
        "files": [path for path, _ in _basis_pairs(state["basis"])],
        "requests": describe_requests(events, floor),
        "reviewer_edits": reviewer_edits_since(events, floor),
        "gaps": gaps,
        "steps": step_tally(events),
        "sphinx": sphinx_result(repo),
        "model": (gen or {}).get("model") or "",
        "model_origin": (gen or {}).get("model_origin") or "",
        "provenance": provenance_line(repo, unit, state, checks),
        "state": state["state"],
        "next": route(state),
    }


def _disposition_text(row, verbatim):
    """`pending` / `resolved` / `withdrawn: <reason>` for one request row."""
    if row["disposition"] != "withdrawn":
        return row["disposition"]
    reason = row["reason"] if verbatim else collapse_note(row["reason"], 200)
    return "withdrawn: %s" % reason


def summary_text(data):
    """The plain report: one section per §3.3 heading, empty ones omitted."""
    out = [data["title"]]
    if data["files"]:
        out.append("files changed:")
        out += ["  %s" % path for path in data["files"]]
    if data["intent"]:
        out.append("intent: %s" % data["intent"])
    if data["audience"]:
        out.append("audience: %s" % data["audience"])
    if data["requests"]:
        out.append("recorded requests:")
        for row in data["requests"]:
            out.append(
                "  seq %s — %s — %s: %s"
                % (
                    row["seq"],
                    _disposition_text(row, False),
                    row["origin"],
                    collapse_note(row["note"], 200),
                )
            )
    if data["reviewer_edits"]:
        out.append("reviewer edits:")
        for entry in data["reviewer_edits"]:
            out.append(
                "  seq %s — %s" % (entry["seq"], collapse_note(entry["note"], 200))
            )
    if data["gaps"]:
        out.append("known gaps:")
        out += ["  - %s" % collapse_note(gap, 200) for gap in data["gaps"]]
    if data["steps"] is not None:
        out.append("validation: %s" % render_step_tally(data["steps"]))
    if data["sphinx"]:
        out.append("sphinx: %s" % data["sphinx"])
    if data["model"]:
        out.append("model: %s (%s)" % (data["model"], data["model_origin"]))
    out.append(data["provenance"])
    return "\n".join(out) + "\n"


def summary_markdown(data):
    """The paste-ready PR text: the same sections, as Markdown.

    WR-11: every contributor-controlled value goes through an escaper chosen
    for its position — :func:`md_cell` in a table cell, :func:`md_code` inside
    a code span, :func:`md_text` everywhere else. EVERY value, with no
    exceptions left to remember: the rule is checkable by reading the function
    only if reading it finds no bare interpolation (WR-13). It used to be only the first
    of the three, so a forged title, audience, reviewer-edit note, known gap or
    Sphinx result was emitted verbatim into text a reviewer pastes into a PR.

    All three escapers enforce the SAME three properties, which is what makes
    "pick the one for the position" a rule rather than three rules: the
    non-string guard and the cap from :func:`md_value` / :func:`md_bound`, and
    no live HTML. They differ only in what the position additionally forbids —
    a newline, a backtick, a pipe. WR-01: ``md_cell`` carried the HTML rule
    alone for one iteration, which made the table position the one place a
    value could still be unbounded or crash the render.
    The characters stay VISIBLE, which is the same rule ``md_cell`` follows:
    what is removed is the value's ability to forge the document's structure,
    never the reader's ability to see what the record holds. The plain
    (:func:`summary_text`) render is unescaped on purpose — it is terminal
    output, not a document.
    """
    out = ["# %s" % md_text(data["title"])]
    if data["files"]:
        out += ["", "## Files changed", ""]
        out += ["- `%s`" % md_code(path) for path in data["files"]]
    if data["intent"] or data["audience"]:
        out += ["", "## Intent and audience", ""]
        if data["intent"]:
            out.append("- **Intent:** %s" % md_text(data["intent"]))
        if data["audience"]:
            out.append("- **Audience:** %s" % md_text(data["audience"]))
    if data["requests"]:
        out += [
            "",
            "## Recorded requests",
            "",
            "| seq | disposition | request |",
            "| --- | --- | --- |",
        ]
        for row in data["requests"]:
            out.append(
                "| %s | %s | %s |"
                % (
                    row["seq"],
                    md_cell(_disposition_text(row, True)),
                    md_cell(row["note"]),
                )
            )
    if data["reviewer_edits"]:
        out += ["", "## Reviewer edits", ""]
        for index, entry in enumerate(data["reviewer_edits"]):
            if index:
                out.append("")
            out.append("**seq %s** — %s" % (entry["seq"], md_text(entry["note"])))
    if data["gaps"]:
        out += ["", "## Known gaps", ""]
        out += ["- %s" % md_text(gap) for gap in data["gaps"]]
    if data["steps"] is not None:
        out += [
            "",
            "## Validation",
            "",
            md_text(render_step_tally(data["steps"])),
        ]
    if data["sphinx"]:
        out += ["", "## Sphinx", "", md_text(data["sphinx"])]
    if data["model"]:
        out += [
            "",
            "## Model",
            "",
            "`%s` (origin: `%s`)"
            % (md_code(data["model"]), md_code(data["model_origin"])),
        ]
    # WR-13: the last raw interpolation. It is tool-derived today — `git
    # rev-parse` output, verify counts, check ids — but `state["basis"]`'s
    # `commit` is a LEDGER value and therefore forgeable, and WR-11's rule is
    # "every contributor-controlled value goes through an escaper chosen for
    # its position". One exception means the next reader cannot verify the rule
    # by reading the function, which is the whole point of stating it that way.
    out += ["", "## Provenance", "", md_text(data["provenance"])]
    return "\n".join(out) + "\n"


def cmd_summary(args):
    """``summary`` — the §3.3 report, and with ``--md`` the paste-ready PR text.

    Over the same single ``read_fs()`` + ``derive()`` + ``route()`` as ``show``
    and under the same read-only write boundary — the snapshot is threaded into
    :func:`summary_data` so that ``run_verify``'s verdict and the page half both
    describe that one instant. A section with no content is omitted rather than
    printed as an empty heading.

    The report says a request was **recorded** and then **disposed**; it never
    says steering was applied, because `resolves` is the reviewer's judgment and
    not proof that any byte changed (T-16-36).
    """
    as_json = bool(getattr(args, "json", False))
    as_md = bool(getattr(args, "md", False))
    unit = args.unit
    repo = git_root()
    events, snapshot, state = read_only_unit(repo, unit)
    data = summary_data(repo, unit, events, snapshot, state)

    if as_json:
        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    elif as_md:
        sys.stdout.write(summary_markdown(data))
    else:
        sys.stdout.write(summary_text(data))
    sys.stdout.flush()
    return EXITS["success"]


# --- argparse ---------------------------------------------------------------


# --- version (contract 5.10) -------------------------------------------------


def cmd_version(args):
    """``version`` — the compatibility handshake every skill opens with (5.10).

    ``--json`` emits EXACTLY ``{"tool", "contract"}``. A third key would be an
    unannounced contract change: phase 17's skills read this object to decide
    whether to run at all, and they stop on two INDEPENDENT conditions — a
    `contract` that is not equal to theirs, or a `tool` older than their
    `min_tool`. Neither number is derived from the other.

    No repository is required: a skill asks what tool it is talking to before
    it knows where it is.
    """
    if bool(getattr(args, "json", False)):
        sys.stdout.write(json.dumps({"tool": __version__, "contract": CONTRACT}) + "\n")
    else:
        sys.stdout.write("dogen %s — contract %d\n" % (__version__, CONTRACT))
    sys.stdout.flush()
    return EXITS["success"]


def cmd_unit_retire(args):
    """``unit retire`` — record the event that releases a unit's claims.

    Stages a–f in contract 5.7's order. This verb's row is the shortest in the
    table: stage c is ``unit_not_found`` (2) alone and stage d is
    ``already_retired``. There is deliberately NO ``retired`` precondition row,
    so :func:`retired_guard` — the first row of every OTHER mutating verb — is
    absent here on purpose: for this one verb a retired unit is the no-op, not
    the refusal. Calling the guard would turn contract 5.7's exit 3 into an
    exit 1 and take the seq and commit of the existing event off the wire.

    Stage b precedes stage d, so an unusable ``--note`` refuses
    ``note_required`` even on an already-retired unit: a note that could never
    be recorded is bad input whichever state the unit is in, and the contract
    fixes that order once rather than per verb.

    The commit takes the unit's ``ledger.jsonl`` as its only pathspec (CONTEXT
    discretion). Retiring writes no page and edits no line: contract 5.1's claim
    is released by an appended, committed event read back through
    :func:`derive`, because no claim is stored anywhere to clear.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ----------------------------------------------
        validate_unit_id(unit)
        note = read_note(args, unit)
        records = read_events(ledger_path(repo, unit), unit)
        found_guard(repo, unit, records)
        identity = git_identity(repo)

        # ONE snapshot for the whole invocation: the no-op and the released
        # target list both read this instant.
        state = unit_state(repo, unit)

        # --- c: per-verb preconditions — `unit_not_found` only, raised above ---
        # --- d: no-op recognition ---------------------------------------------
        if state["retired"]:
            existing = _last_of([event for event, _ in records], "retired") or {}
            raise Refusal(
                "already_retired",
                unit=unit,
                detail="unit %s was retired at seq %s" % (unit, existing.get("seq")),
                hint="a retired unit records nothing further",
                next_token=route(state),
                extra={"seq": existing.get("seq"), "commit": existing.get("commit")},
            )

        # --- e: content gates — none for retire --------------------------------
        # --- f: write ----------------------------------------------------------
        released = list(state["targets"])
        head = git_head(repo)
        event = next_event("retired", records, identity, head, {"note": note})
        result = perform_write(
            repo,
            unit,
            "retired",
            chain_lines([event]),
            [event["seq"]],
            [],
            note,
            head,
        )
        report_hook_changes(result, repo)

        commit = git(["rev-parse", "--short=7", "HEAD"], repo).stdout.strip()
        segments = [
            "retired %s" % unit,
            os.path.relpath(ledger_path(repo, unit), os.fspath(repo)),
            "%s released, recorded in %s"
            % (
                "%d target(s) (%s)" % (len(released), ", ".join(released))
                if released
                else "no target",
                commit or "no commit",
            ),
        ]
        # State is re-derived after the commit, so the routed token is what is
        # now true (row 2, `retired`) rather than what we meant to make true.
        return respond(segments, next_token_for(repo, unit), as_json)


#: The step plan's shape, worded once for every refusal that has to state it.
STEPS_SHAPE = 'one JSON array: [{"id": …, "text": …, "mode": …, "stateful": …}]'


def read_sidecar(spec, flag, unit, shape):
    """The UTF-8 text of an agent-authored JSON side-car; ``-`` is stdin.

    Unreadable or not-UTF-8 is stage-b bad input (2) and carries ``bad_target``
    per 16-03's rule; what the bytes MEAN is the caller's question. Shared by
    ``--steps-file`` and ``--evidence-file`` so the two cannot drift.
    """
    try:
        if spec == "-":
            return sys.stdin.read()
        with open(spec, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as bad:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="%s %s cannot be read (%s)" % (flag, spec, type(bad).__name__),
            hint="pass an existing readable file, or - to read it from stdin",
        )
    except UnicodeDecodeError:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="%s %s is not UTF-8 text" % (flag, spec),
            hint="%s is %s" % (flag, shape),
        )


def read_steps_file(spec, unit=""):
    """``--steps-file F|-`` into the validated step list (D-01, contract 5.6).

    The plan is a JSON array of objects carrying exactly ``id``, ``text``,
    ``mode`` and ``stateful``; the tool adds ``text_hash``. There is no markdown
    parser and the plan is never mirrored into ``unit.md`` — D-01 forbids that
    by name, because a second copy of the plan re-opens the ``plan_stale``
    friction the frontmatter hash exists to make rare.

    Every shape, id and vocabulary fault refuses ``bad_target`` (2), which is
    16-03's rule: the reason table names no code for "this input is malformed",
    so the ``bad_*`` family's own code carries it and no key is invented. The
    one exception is unusable free text, which the note family already owns.
    """
    raw = read_sidecar(spec, "--steps-file", unit, STEPS_SHAPE)
    try:
        check_byte_cap("steps", raw, MAX_STEPS_BYTES)
    except ValueError as bad:
        raise Refusal("bad_target", unit=unit, detail=str(bad),
                      hint="a step plan is at most %d bytes" % MAX_STEPS_BYTES)
    try:
        parsed = json.loads(raw)
    except ValueError as bad:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="the step plan is not valid JSON (%s)" % bad,
            hint="the step plan is %s" % STEPS_SHAPE,
        )
    if not isinstance(parsed, list):
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="the step plan is a %s, not a JSON array" % type(parsed).__name__,
            hint="the step plan is %s" % STEPS_SHAPE,
        )
    if not parsed:
        # STATE-03 probe 3: the contract does not pin this case, and the tool
        # decides it here. A plan with no steps can never resolve and would
        # route an actionable unit to `walk` for ever; refusing it says so at
        # the moment it could still be fixed.
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="the step plan is empty",
            hint="an actionable unit's step plan names at least one step; "
            "dogen unit retire %s --note \"…\" abandons the unit instead" % unit,
        )
    try:
        check_count_cap("steps", parsed, MAX_STEPS)
    except ValueError as bad:
        raise Refusal("bad_target", unit=unit, detail=str(bad),
                      hint="a step plan names at most %d steps" % MAX_STEPS)

    steps = []
    seen = set()
    expected = ("id", "text", "mode", "stateful")
    for index, entry in enumerate(parsed):
        where = "step %d" % (index + 1)
        if not isinstance(entry, dict):
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="%s is a %s, not a JSON object"
                % (where, type(entry).__name__),
                hint="each step is an object with exactly %s" % ", ".join(expected),
            )
        # `text_hash` lands on the extra-key branch by design: the tool
        # computes it, so a typed one is a claim the record cannot corroborate.
        extra = sorted(key for key in entry if key not in expected)
        missing = [key for key in expected if key not in entry]
        if extra or missing:
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="%s carries %s and is missing %s"
                % (where, ", ".join(extra) or "no stray key", ", ".join(missing) or "nothing"),
                hint="a step is exactly %s; the tool computes text_hash"
                % ", ".join(expected),
            )
        step_id = entry["id"]
        validate_step_id(step_id, unit)
        if step_id in seen:
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="step id %r appears twice in the plan" % step_id,
                hint="step ids are unique within one plan (contract 5.6)",
            )
        seen.add(step_id)
        mode = entry["mode"]
        if mode not in STEP_MODES:
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="%s has mode %r" % (where, mode),
                hint="mode is 'agent' (the skill runs the step) or 'ta' "
                "(the author runs it)",
            )
        stateful = entry["stateful"]
        if not isinstance(stateful, bool):
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="%s has a non-boolean stateful: %r" % (where, stateful),
                hint="stateful is true when the step mutates real state",
            )
        text = validate_note(
            entry["text"] if isinstance(entry["text"], str) else "",
            unit,
            "%s text" % where,
        )
        steps.append(
            {
                "id": step_id,
                "text": text,
                "text_hash": step_text_hash(text),
                "mode": mode,
                "stateful": stateful,
            }
        )
    return steps


def cmd_plan_steps(args):
    """``plan-steps`` — record the step plan an actionable unit's walk answers.

    Stages a–f in contract 5.7's order. Stage c is this verb's row verbatim:
    `retired` then `no_signoff`. There is no no-op — a re-plan that repeats the
    previous plan word for word is still a new plan, because `replaces` and
    `reuse` are what the carry-forward walk reads and a skipped event would
    leave the chain with a hole in it.

    `replaces` is pinned here: **the seq of the ``steps-planned`` this plan
    supersedes, or null for the first plan of a unit.** Contract 5.3 requires
    the field and defines it nowhere; this is the only reading 5.4's
    consecutive-reuse hop walking supports, because the walk needs the previous
    plan's seq to reach it.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ----------------------------------------------
        validate_unit_id(unit)
        reuse = bool(getattr(args, "keep_evidence", False))
        note = ""
        if getattr(args, "note", None) is not None:
            note = validate_note(args.note, unit, "note")
        if reuse and not note:
            # Contract 5.3 makes `reuse_note` required whenever `reuse` is set,
            # and V12 verifies it. argparse registers the two flags
            # independently, so the pairing is checked here or nowhere.
            raise Refusal(
                "note_required",
                unit=unit,
                detail="--keep-evidence carries evidence forward onto steps that "
                "have not been re-run; the contract requires the reason on the record",
                hint='dogen plan-steps %s --steps-file … --keep-evidence --note "…"'
                % unit,
            )
        steps = read_steps_file(args.steps_file, unit)
        records = read_events(ledger_path(repo, unit), unit)
        events = [event for event, _ in records]
        found_guard(repo, unit, records)
        identity = git_identity(repo)

        # --- c: per-verb preconditions, in the listed order -------------------
        state = unit_state(repo, unit)
        retired_guard(state, unit)
        signoff_guard(state, unit)
        actionable_guard(state, unit)

        # --- d: no-op recognition — none for plan-steps -----------------------
        # --- e: content gates — none for plan-steps ---------------------------
        # --- f: write ---------------------------------------------------------
        previous = _last_of(events, "steps-planned")
        payload = {
            "steps": steps,
            "replaces": previous.get("seq") if previous is not None else None,
            "reuse": reuse,
        }
        if reuse:
            payload["reuse_note"] = note
        head = git_head(repo)
        event = next_event("steps-planned", records, identity, head, payload)
        result = perform_write(
            repo,
            unit,
            "steps-planned",
            chain_lines([event]),
            [event["seq"]],
            [],
            note or "step plan: %d step(s)" % len(steps),
            head,
        )
        report_hook_changes(result, repo)

        # The tally is re-derived from the committed record, so the line reports
        # what is now true rather than what this call meant to make true. It
        # says what resolves, never what ran: contract 5.4 makes resolution a
        # derivation result, not an observation.
        events.append(event)
        segments = [
            "planned %d step(s) for %s" % (len(steps), unit),
            os.path.relpath(ledger_path(repo, unit), os.fspath(repo)),
            render_step_tally(step_tally(events)),
        ]
        return respond(segments, next_token_for(repo, unit), as_json)


def evidence_path(repo, unit, steps_seq, step_id):
    """The tool's own copy of a step's captured output (D-04).

    ``.dogen/staging/<id>/scratch/evidence/<steps_seq>-<step_id>.out``. The seq
    is in the name because the same step id is re-run against a later plan and
    the two captures are different evidence for different instructions.
    """
    return os.path.join(
        staging_dir(repo, unit),
        "scratch",
        "evidence",
        "%s-%s.out" % (steps_seq, step_id),
    )


def read_evidence_file(spec, unit=""):
    """``--evidence-file F`` as an ALLOW-list against contract 5.6's key set.

    The rule is ``{verdict, exit_code, mode, command, reason}`` and **digests
    are never typed**. A deny-list of known digest names would miss ``sha256``,
    ``digest``, ``hash`` and the rest, and the legacy v1.2 evidence file carried
    ``output_sha256`` and ``step_text_sha256`` literally — so a TA copying an
    old recipe lands on a loud refusal rather than a silent acceptance. The same
    allow-list catches a typed ``text_hash``, which the tool takes from the plan.

    An unreadable or non-object file is stage-b bad input (2); an object whose
    CONTENT is wrong is the evidence gate's own ``evidence_incomplete`` (4).
    """
    shape = "one JSON object: {%s}" % ", ".join(EVIDENCE_KEYS)
    raw = read_sidecar(spec, "--evidence-file", unit, shape)
    try:
        payload = json.loads(raw)
    except ValueError as bad:
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="--evidence-file %s is not valid JSON (%s)" % (spec, bad),
            hint="the evidence file is %s" % shape,
        )
    if not isinstance(payload, dict):
        raise Refusal(
            "bad_target",
            unit=unit,
            detail="--evidence-file %s is not a JSON object" % spec,
            hint="the evidence file is %s" % shape,
        )

    extra = sorted(key for key in payload if key not in EVIDENCE_KEYS)
    if extra:
        raise Refusal(
            "evidence_incomplete",
            unit=unit,
            detail="the evidence file carries a key that is not evidence: %s"
            % ", ".join(extra),
            hint="the evidence file is exactly {%s}; digests are never typed — "
            "the tool hashes the bytes it copied, and the text hash comes from "
            "the step plan" % ", ".join(EVIDENCE_KEYS),
        )
    verdict = payload.get("verdict")
    if verdict not in STEP_VERDICTS:
        raise Refusal(
            "evidence_incomplete",
            unit=unit,
            detail="verdict %r is not one of the four the contract names" % verdict,
            hint="verdict is one of %s" % ", ".join(STEP_VERDICTS),
        )
    exit_code = payload.get("exit_code")
    # A bool is an int in Python; `true` is not an exit code.
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise Refusal(
            "evidence_incomplete",
            unit=unit,
            detail="exit_code %r is not an integer" % exit_code,
            hint="exit_code is the command's own status, as an integer",
        )
    mode = payload.get("mode")
    if mode not in STEP_MODES:
        raise Refusal(
            "evidence_incomplete",
            unit=unit,
            detail="mode %r is not one of the two wire values" % mode,
            hint="mode is 'agent' (the skill ran the step) or 'ta' "
            "(the author ran it)",
        )
    # `command` is recorded as data: the tool never runs it, and every git call
    # it makes is an argv list with no shell (T-17-23).
    command = payload.get("command")
    command = validate_note(str(command), unit, "command") if command is not None else ""
    reason = payload.get("reason")
    reason = validate_note(str(reason), unit, "reason") if reason is not None else ""
    # Contract 5.3: `reason` is required for skipped and deviated, for a pass
    # with a non-zero exit, and for a fail with exit 0 — every case where the
    # verdict and the exit code disagree, or where there is nothing to look at.
    if step_reason_required({"verdict": verdict, "exit_code": exit_code}) and not reason:
        raise Refusal(
            "evidence_incomplete",
            unit=unit,
            detail="a %s verdict at exit %d says why, on the record"
            % (verdict, exit_code),
            hint='add "reason" to the evidence file',
        )
    evidence = {"verdict": verdict, "exit_code": exit_code, "mode": mode}
    if command:
        evidence["command"] = command
    if reason:
        evidence["reason"] = reason
    return evidence


def cmd_step(args):
    """``step`` — record one step's evidence, computed by the tool.

    Stages a–f in contract 5.7's order. Stage c is this verb's row verbatim:
    `retired`, `no_signoff`, then `not_actionable`. Stage d is
    `already_recorded` on the same ``(steps_seq, step_id, verdict, exit_code,
    output_sha256, reason)``, recognised only against the CURRENT plan, only
    for a complete submission, and only when the evidence's ``mode`` is the
    plan's — a superseded ``--steps-seq``, a capture-less non-``skipped``
    verdict and a divergent ``mode`` all three belong to stage e, and letting d
    answer any of them would shadow the refusal that names the real problem.
    Stage e is `evidence_stale`, then `evidence_incomplete`, then
    `evidence_mismatch`.

    The third exclusion is WR-02's and is the same defect as the other two one
    field along: ``mode`` is not in the no-op tuple and is not compared, so an
    identical capture resubmitted under the wrong mode matched field for field
    and was refused ``already_recorded`` — "already on the record, field for
    field", which is false about the one field that differs.

    Two properties the verb exists for. The digest is taken over the tool's OWN
    copy under ``.dogen/staging/``, written with ``publish_atomic``, so a later
    mutation of the caller's source cannot change what was recorded (T-17-21).
    And the source path is checked against ``.dogen/staging/<id>/scratch/``
    BEFORE it is opened, so ``--output-file /etc/shadow`` — and
    ``--output-file .env.local`` or ``--output-file .git/config``, which the
    repository-wide check this replaced let straight through (CR-03) — is
    refused with nothing read and nothing written rather than having its first
    4 KiB committed (T-17-18).

    The narrow scope is the honest one, because of what happens next:
    :func:`scrub_excerpt` copies up to ``MAX_EXCERPT`` bytes VERBATIM into the
    event, its own docstring says plainly that it does not remove credentials,
    and every transition commits ``ledger.jsonl``. A step's output is something
    the walk just produced into its own scratch directory; anything else in the
    repository is a file that happens to be readable, and an LLM following
    ``walk-protocol.md`` is the caller.

    The response says what resolved, never that a step ran or was checked:
    contract 5.4 makes resolution a derivation result, not an observation.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()
    root = os.fspath(repo)

    with unit_lock(repo, unit):
        # --- a: lock, .git/index.lock, chain, committed prefix, tail/pending ---
        stage_a_guard(repo, unit)

        # --- b: input validation ----------------------------------------------
        validate_unit_id(unit)
        step_id = validate_step_id(args.step_id, unit)
        records = read_events(ledger_path(repo, unit), unit)
        events = [event for event, _ in records]
        found_guard(repo, unit, records)
        steps_seq = args.steps_seq
        plans = [e for e in events
                 if e.get("kind") == "steps-planned" and e.get("seq") == steps_seq]
        plan = plans[0] if plans else None
        if plan is None:
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="--steps-seq %s does not name a steps-planned event of %s"
                % (steps_seq, unit),
                hint="dogen show %s names the current step plan's seq" % unit,
            )
        planned = [e for e in (plan.get("steps") or []) if e.get("id") == step_id]
        planned_step = planned[0] if planned else None
        if planned_step is None:
            raise Refusal(
                "step_unknown",
                unit=unit,
                detail="step %r is not in the plan at seq %s" % (step_id, steps_seq),
                hint="the plan at seq %s names: %s"
                % (
                    steps_seq,
                    ", ".join(
                        str(entry.get("id")) for entry in (plan.get("steps") or [])
                    )
                    or "no step",
                ),
            )
        evidence = read_evidence_file(args.evidence_file, unit)
        identity = git_identity(repo)

        source = getattr(args, "output_file", None)
        if source is not None:
            # BEFORE the open: a path pointing at an arbitrary file would
            # otherwise have its first 4 KiB committed into the ledger.
            guard_dogen_root(repo, unit)
            # WR-01: `guard_dogen_root` names `.dogen`, `.dogen/staging` and
            # `.dogen/units` — one level short of the two directories THIS
            # check resolves through. `contained` resolves BOTH operands with
            # `realpath`, so a symlinked `<staging>/<id>` or
            # `<staging>/<id>/scratch` cancels the containment test out exactly
            # as `guard_dogen_root`'s own docstring describes, and every target
            # passes. Only a check that names the link's own path can see it,
            # and it has to run BEFORE the containment test it protects.
            unit_staging = staging_dir(repo, unit)
            scratch = os.path.join(unit_staging, "scratch")
            for part in (unit_staging, scratch):
                if os.path.islink(part):
                    raise Refusal(
                        "bad_write_path",
                        unit=unit,
                        detail="%s/ is a symlink"
                        % os.path.relpath(part, os.fspath(repo)),
                        hint="the unit's staging tree must be real directories "
                        "inside the repository; its bytes are excerpted "
                        "verbatim into the committed record",
                    )
            if not contained(scratch, source):
                raise Refusal(
                    "bad_write_path",
                    unit=unit,
                    detail="--output-file %r resolves outside "
                    ".dogen/staging/%s/scratch/" % (source, unit),
                    hint="capture the step's output under .dogen/staging/%s/"
                    "scratch/; its bytes are excerpted verbatim into the "
                    "committed record" % unit,
                )
            try:
                with open(source, "rb") as handle:
                    captured = handle.read()
            except OSError as bad:
                raise Refusal(
                    "bad_target",
                    unit=unit,
                    detail="--output-file %s cannot be read (%s)"
                    % (source, type(bad).__name__),
                    hint="pass the file the step's output was captured into",
                )
        else:
            captured = None

        # --- c: per-verb preconditions, in the listed order -------------------
        state = unit_state(repo, unit)
        retired_guard(state, unit)
        signoff_guard(state, unit)
        actionable_guard(state, unit)

        # The copy and the digest, before stage d: contract 5.7's step no-op is
        # defined on a tuple that INCLUDES `output_sha256`, so the digest has to
        # exist before the no-op can be recognised. The copy is transient
        # gitignored scratch under `.dogen/staging/`, never a recorded write and
        # never a pathspec, so producing it here changes nothing a refusal would
        # have to undo.
        #
        # WR-04: the digest stays here; the REFUSAL for a missing capture moved
        # down into stage e, where 5.7 puts it — after `evidence_stale`. Raised
        # here it reported `evidence_incomplete` for a superseded `--steps-seq`
        # where the contract says `evidence_stale`, and the two share exit 4 so
        # nothing noticed. D-03: `skipped` is the one verdict that needs no
        # bytes; its reason carries the why, and the digest of zero bytes says
        # plainly that nothing was captured rather than leaving the field
        # absent.
        missing_capture = captured is None and evidence["verdict"] != "skipped"
        if captured is None:
            digest, excerpt = scrub_excerpt(b"")
            copy_relative = ""
        else:
            copy = evidence_path(repo, unit, steps_seq, step_id)
            publish_atomic(copy, captured)
            with open(copy, "rb") as handle:
                digest, excerpt = scrub_excerpt(handle.read())
            copy_relative = os.path.relpath(copy, root)

        # --- d: no-op recognition ---------------------------------------------
        # Contract 5.7 d defines the no-op on the tuple `(steps_seq, step_id,
        # verdict, exit_code, output_sha256, reason)` with NO recency
        # qualifier. WR-01: this loop used to `break` at the first
        # `step-recorded` it reached whatever step that event named, so in a
        # multi-step walk a re-run of an EARLIER step saw a later step's record,
        # failed the comparison, and appended a duplicate event and a duplicate
        # commit for one fact. Skip past the other steps' records, and `break`
        # only on THIS step's latest one — a later record for this same step
        # that differs is an append, and an older one says nothing.
        #
        # Scoped to the CURRENT plan on purpose. A `--steps-seq` the current
        # plan has superseded is never a no-op: stage e refuses it
        # `evidence_stale` (T14), and now that d finds the matching record
        # wherever it sits, d would otherwise shadow that refusal with
        # `already_recorded` for evidence the tool is telling the caller to
        # re-run.
        #
        # WR-05: `current_plan` is never None here — stage b already refused
        # `bad_target` unless `--steps-seq` names a `steps-planned` event of
        # this unit, so at least one exists. The disjunct that tested for it
        # was dead.
        #
        # WR-04: an incomplete submission is never a no-op either. With the
        # `evidence_incomplete` raise moved to stage e, a non-`skipped` verdict
        # with no `--output-file` reaches d carrying the digest of zero bytes,
        # and a step genuinely recorded from an EMPTY capture would match it —
        # reporting `already_recorded` for evidence the caller never supplied.
        #
        # WR-02 (iteration 3): the THIRD e-gate, and the same shape as the two
        # above. `mode` is not in 5.7's no-op tuple, and it is not on the two
        # sides of the comparison either, so a resubmission of the SAME capture
        # under a divergent `mode` matches field for field and d answers
        # `already_recorded` — "already on the record, field for field", which
        # is false: `mode` differs, and the `evidence_mismatch` that names the
        # real problem never fires. The tuple stays as the contract defines it;
        # what is excluded is a submission that belongs to e.
        current_plan = _last_of(events, "steps-planned")
        # `planned_step` is never None here: stage b raises `step_unknown`
        # above unless the plan at `--steps-seq` names this step. A guard for it
        # would be the dead disjunct WR-05 removed from this same block.
        mode_diverges = evidence["mode"] != planned_step.get("mode")
        if (
            not missing_capture
            and not mode_diverges
            and current_plan.get("seq") == steps_seq
        ):
            for event in reversed(events):
                if event.get("kind") != "step-recorded":
                    continue
                if (
                    event.get("steps_seq") != steps_seq
                    or event.get("step_id") != step_id
                ):
                    continue
                if (
                    event.get("verdict") == evidence["verdict"]
                    and event.get("exit_code") == evidence["exit_code"]
                    and event.get("output_sha256") == digest
                    and (event.get("reason") or "") == (evidence.get("reason") or "")
                ):
                    raise Refusal(
                        "already_recorded",
                        unit=unit,
                        detail="step %s at plan seq %s is already on the record, "
                        "field for field" % (step_id, steps_seq),
                        hint="nothing was appended; move to the next step",
                        next_token=route(state),
                        extra={
                            "seq": event.get("seq"),
                            "commit": event.get("commit"),
                        },
                    )
                break

        # --- e: content gates --------------------------------------------------
        # 5.7's order, verbatim: `evidence_stale`, then `evidence_incomplete`,
        # then `evidence_mismatch`.
        if current_plan.get("seq") != steps_seq:
            raise Refusal(
                "evidence_stale",
                unit=unit,
                detail="the plan at seq %s was superseded by the plan at seq %s"
                % (steps_seq, current_plan.get("seq")),
                hint="re-run the step against the current plan: dogen step %s %s "
                "--steps-seq %s --evidence-file …"
                % (unit, step_id, current_plan.get("seq")),
                next_token=route(state),
            )

        if missing_capture:
            raise Refusal(
                "evidence_incomplete",
                unit=unit,
                detail="a %s verdict is a claim about bytes; none were given"
                % evidence["verdict"],
                hint="capture the command's output and pass it with "
                "--output-file, or record the step as skipped with a reason",
            )

        # WR-02: `read_evidence_file` checks that `mode` is one of the two the
        # contract names and stops there, so the record could claim a `ta`
        # execution for a step the plan declares `agent` — while `text_hash` is
        # taken from the PLAN, which made the event internally consistent and
        # silently wrong. Contract 5.4's reuse prefix key is `(text_hash, mode,
        # stateful)` OF THE PLAN, so the divergence also corrupts the
        # carry-forward walk. This is the gate `evidence_mismatch` was in the
        # reason table for and never had.
        if evidence["mode"] != planned_step.get("mode"):
            raise Refusal(
                "evidence_mismatch",
                unit=unit,
                detail="the plan at seq %s declares step %s as %r; the evidence "
                "claims %r"
                % (
                    steps_seq,
                    step_id,
                    planned_step.get("mode"),
                    evidence["mode"],
                ),
                hint="record the step in the mode the plan declares (%r), or "
                "re-plan it with dogen plan-steps %s --steps-file …"
                % (planned_step.get("mode"), unit),
                next_token=route(state),
            )

        # --- f: write ----------------------------------------------------------
        head = git_head(repo)
        payload = {
            "step_id": step_id,
            "steps_seq": steps_seq,
            # The plan's hash, not a typed one: it is what makes this evidence
            # traceable to the instruction it answers.
            "text_hash": planned_step.get("text_hash"),
            "mode": evidence["mode"],
            "verdict": evidence["verdict"],
            "exit_code": evidence["exit_code"],
            "output_sha256": digest,
            "output_excerpt": excerpt,
        }
        if evidence.get("command"):
            payload["command"] = evidence["command"]
        if evidence.get("reason"):
            payload["reason"] = evidence["reason"]
        event = next_event("step-recorded", records, identity, head, payload)
        result = perform_write(
            repo,
            unit,
            "step-recorded",
            chain_lines([event]),
            [event["seq"]],
            [],
            evidence.get("reason") or "step %s: %s" % (step_id, evidence["verdict"]),
            head,
        )
        report_hook_changes(result, repo)

        events.append(event)
        segments = [
            "recorded step %s on %s: %s" % (step_id, unit, evidence["verdict"]),
            copy_relative or os.path.relpath(ledger_path(repo, unit), root),
            render_step_tally(step_tally(events)),
        ]
        return respond(segments, next_token_for(repo, unit), as_json)


def report(lines, as_json):
    """Write a multi-line report to STDOUT, or nothing at all under ``--json``.

    Two rules in one place. The diagnostic helper is stderr-only and GATE-04
    allows a non-zero exit exactly one line there, so every report this file
    prints goes to stdout — and under ``--json`` contract 5.7 moves the refusal
    ITSELF to stdout, where a text block before it would leave the caller
    parsing a document that is not JSON. The structured half of each report
    travels in the refusal's ``extra`` instead.
    """
    if as_json or not lines:
        return
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


def resume_diff(row):
    """A unified diff of one unexpected file: intended bytes against disk bytes.

    ``render_diff``'s call shape, labels apart: two-space indent, ``lineterm``
    empty. The author is being asked to choose between two byte strings, so
    both sides are named — ``intended:`` is what the interrupted transition
    would have written, ``disk:`` is what is there now.
    """
    return [
        "  %s" % line
        for line in difflib.unified_diff(
            (row["intended"] or b"").decode("utf-8", "replace").splitlines(),
            (row["disk"] or b"").decode("utf-8", "replace").splitlines(),
            fromfile="intended:%s" % row["path"],
            tofile="disk:%s" % row["path"],
            lineterm="",
        )
    ]


#: Contract 5.8's fixed suffix on an adopted note. The author's own words say
#: WHY the bytes were kept; this says WHAT happened, in the tool's words, every
#: time — a note carrying only the author's sentence would leave the record
#: unable to state that the bytes were not the tool's own.
ADOPT_NOTE_SUFFIX = (
    "(bytes changed outside dogen after recording; retained by the author)"
)


def adopt_dir(repo, unit):
    """``pending/adopt/`` — the durable copies a revised manifest points at."""
    return os.path.join(pending_dir(repo, unit), "adopt")


def adopt_referenced(manifest):
    """Does ``manifest`` point at any copy under ``adopt/``?

    A manifest that does not is authoritative over an ``adopt/`` tree on disk,
    so that tree PREDATES it: the leftovers of a crash before contract 5.8's
    step (ii), which the next write-mode run sweeps as stray.
    """
    if manifest is None:
        return False
    return any(
        (entry.get("after_path") or "").replace(os.sep, "/").startswith("adopt/")
        for entry in manifest["files"]
    )


def prior_generation_seq(repo, unit, events, tail):
    """A reviewer edit's ``generation_seq``: the batch's, else the record's.

    Contract 5.3 makes the field nullable, and null is the honest answer for a
    unit whose interrupted transition preceded any draft. Inventing a seq would
    be a lie in the one field a reader joins edits to drafts on.
    """
    for event in reversed(events):
        if event.get("kind") == "generation":
            return event["seq"]
    complete, _partial, _committed, _relative = ledger_split(repo, unit)
    for line in reversed(complete[: len(complete) - len(tail)]):
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if parsed.get("kind") == "generation":
            return parsed["seq"]
    return None


def basis_path(repo, unit, path):
    """One manifest entry's repo-relative path in the BASIS vocabulary.

    The manifest records `docs/reference/a.rst`; a basis event records
    `reference/a.rst`. `cmd_generate` builds the manifest by joining
    ``DOCS_ROOT`` onto each signed target, so this is that join inverted —
    and the only place `resume --adopt` crosses between the two (CR-01).

    A manifest entry outside ``docs/`` — the `unit.md` of an interrupted
    ``unit edit --re-sign`` — has no basis form at all. `resume_adopt`'s first
    arm already refuses that batch, because its last event is a signoff rather
    than a generation or a reviewer edit; this refuses it again at the point of
    conversion rather than emitting `../.dogen/units/<id>/unit.md` as a target.
    Asserted rather than assumed: the cost of being wrong is a target path no
    verb can resolve, written into an append-only record.
    """
    normalized = path.replace(os.sep, "/")
    prefix = DOCS_ROOT + "/"
    if not normalized.startswith(prefix) or normalized == prefix:
        raise Refusal(
            "recovery_unsupported",
            unit=unit,
            detail="material_invalid: the pending manifest names %r, which is "
            "outside %s/ and has no basis path" % (path, DOCS_ROOT),
            hint=escape_hint(
                repo,
                unit,
                "dogen resume %s --overwrite places the intended bytes; "
                "`dogen show %s` reads the batch back" % (unit, unit),
            ),
            next_token="resume",
        )
    return normalized[len(prefix):]


def revise_manifest_entries(entries, adopted):
    """The revised manifest's ``files[]`` — contract 5.8's adopt step (ii).

    An adopted entry's after copy MOVES to ``adopt/`` and carries the disk
    bytes' digest; every other entry is carried over byte for byte, because the
    original ``after/`` copies are the only evidence of what the interrupted
    verb intended and a recovery that rewrote them would destroy it.

    Pure, so U-11 drives it with literal dicts; the one caller reads ``adopted``
    from the same classification pass 1 printed, so the rows it revises are
    exactly the rows the author saw.
    """
    current = {row["path"]: row for row in adopted}
    revised = []
    for entry in entries:
        row = current.get(entry["path"])
        if row is None:
            revised.append(entry)
            continue
        entry = dict(entry)
        entry["after_sha"] = sha256_bytes(row["disk"])
        entry["after_path"] = "adopt/" + entry["path"].replace(os.sep, "/")
        revised.append(entry)
    return revised


def resume_adopt(repo, unit, found, rows, args):
    """Contract 5.8's ``--adopt``, in the contract's three numbered steps.

    The ORDER is the whole difficulty, because the crash semantics of every
    intermediate state depend on it. (i) the durable copies; (ii) the atomic
    publication of the revised manifest; (iii) the append, which pass 2 does.
    A crash before (ii) leaves the old manifest authoritative and the copies
    stray; a crash after (ii) leaves a tail that is a byte-prefix of the
    revised batch, which a PLAIN ``resume`` completes.

    **Persistence invariant: every published manifest references durable copies
    matching all of its recovery digests.** That is why (i) precedes (ii), and
    why the copies go through :func:`publish_atomic`, which fsyncs the file and
    its parent directory both.

    This is an EDIT, never a review. A formatter is not a reviewer and no
    verdict is recorded (T-17-33).

    Returns the classification pass 2 continues with — the caller's own,
    unchanged, when this is a plain resume.
    """
    manifest = found["manifest"]
    entries = manifest["files"]
    events = [json.loads(line) for line in manifest["events"]]
    last = events[-1]

    # The precondition, asked FIRST: the flag is allowed on the two kinds whose
    # files[] a reviewer edit can restate. The common refusal is an interrupted
    # re-sign whose unit plan a hook rewrote, and for a plan file the way out is
    # the intended bytes — which is what the hint names.
    if last.get("kind") not in ("generation", "reviewer-edit"):
        # History can explain repeated attempts, but cannot rule out the
        # overwrite decision after the author removes a blocker.
        raise Refusal(
            "adopt_unsupported",
            unit=unit,
            detail="the batch's last event is a %s; only a generation or a "
            "reviewer edit can be adopted" % last.get("kind"),
            hint=escape_hint(
                repo,
                unit,
                "dogen resume %s --overwrite restores the intended bytes" % unit,
            ),
            next_token="resume",
        )
    # A repeated adopt after a crash between (ii) and (iii) finds its own line
    # already in the batch. Behave as a plain resume: a duplicate would record
    # one human decision twice in a record whose whole value is that each line
    # is one decision (T-17-32).
    if last.get("kind") == "reviewer-edit" and last.get("hook") is True:
        # WR-03: say so. This arm records NO event, so a `--note` handed to it
        # is dropped — and the batch already satisfies all three published
        # conditions, so the author reasonably believed the words they wrote
        # were about to become the reviewer edit's note. `read_note` cannot
        # move above this return (a plain resume with nothing to adopt has no
        # note to require, which is why it sits below both early returns), so
        # the silence is broken here instead of refusing a run that is
        # otherwise correct and completes the batch.
        notices = []
        if getattr(args, "note", None) is not None or (
            getattr(args, "note_file", None) is not None
        ):
            notices.append(
                "--note was not recorded: this batch's last event at seq %s is "
                "already an adoption, so repeated `--adopt` completes the "
                "existing batch with no new event. The note on seq %s stands unchanged."
                % (last.get("seq"), last.get("seq"))
            )
        # Carry notices until pass 2 knows whether the transition succeeded.
        # A rejecting hook needs one JSON refusal; a restoring hook may clear
        # the drift before there is any reason to recommend `edits`.
        return dict(found, notices=notices, repeated_adoption=last.get("seq")), rows

    adopted = [row for row in rows if row["class"] == "unexpected"]
    if not adopted:
        return found, rows  # contract 5.8: a plain resume

    # WR-09: BELOW both early returns, not above them. Contract 5.8 ends with
    # "`--adopt` with zero `unexpected` files is a plain resume", and a plain
    # resume has no reviewer edit to write a note onto — but `read_note` ran
    # first and refused `note_required` (2) for a run that was going to record
    # no note at all. The note is required for the edit this function is about
    # to build, so it is asked for exactly where that edit is about to exist.
    note = read_note(args, unit)
    absent = [row["path"] for row in adopted if row["disk"] is None]
    if absent:
        # There are no current bytes to make durable, so the invariant cannot
        # be satisfied for this manifest. Say so rather than adopting nothing
        # under the digest of no bytes.
        raise Refusal(
            "adopt_unsupported",
            unit=unit,
            detail="%s is not on disk and has no current bytes to adopt" % absent[0],
            hint=escape_hint(
                repo,
                unit,
                "dogen resume %s --overwrite places the intended bytes" % unit,
            ),
            next_token="resume",
        )

    # CR-01: cross into the basis vocabulary HERE, before step (i), so a batch
    # with no basis form refuses without leaving stray copies in adopt/.
    basis_paths = {
        entry["path"]: basis_path(repo, unit, entry["path"]) for entry in entries
    }

    # (i) the durable copies, fsynced, BEFORE any manifest names their digests.
    for row in adopted:
        publish_atomic(os.path.join(adopt_dir(repo, unit), row["path"]), row["disk"])
    crash_point("adopt")

    # (ii) the revised manifest: the adopted entries' after copies move to
    # adopt/ with their new digests, every other entry is carried over byte for
    # byte, and the batch GAINS one line — the generation's own event bytes are
    # never rewritten, because every chain link after them digests those bytes.
    revised_entries = revise_manifest_entries(entries, adopted)
    edit = build_event(
        "reviewer-edit",
        last["seq"] + 1,
        chain_prev(manifest["events"][-1]),
        git_identity(repo),
        git_head(repo),
        {
            # The COMPLETE batch file set: unchanged paths with their recorded
            # digests, adopted ones with their current digests. Recording only
            # the changed path would shrink the basis to whatever a formatter
            # happened to touch.
            #
            # CR-01: in the BASIS vocabulary, which is not the manifest's. A
            # manifest entry names a repo-relative path (`docs/reference/a.rst`
            # — `perform_write` joins it onto the repo root); every basis event
            # names a docs-root-relative target (`reference/a.rst`), which is
            # what the signoff's `targets[]`, the generation's `files[]` and
            # `cmd_edits`' `complete_basis_set` all spell. V13 compares the two
            # sets directly, so recording the manifest form makes every signed
            # target look DROPPED and `verify` calls the record damaged.
            "files": [
                {"path": basis_paths[entry["path"]], "sha256": entry["after_sha"]}
                for entry in revised_entries
            ],
            "generation_seq": prior_generation_seq(repo, unit, events, found["tail"]),
            "note": "%s %s" % (note, ADOPT_NOTE_SUFFIX),
            "hook": True,
        },
    )
    revised_manifest = {
        "events": list(manifest["events"]) + [canonical_line(edit)],
        "files": revised_entries,
    }
    publish_atomic(
        os.path.join(pending_dir(repo, unit), "manifest.json"),
        json.dumps(revised_manifest, sort_keys=True, ensure_ascii=False).encode(
            "utf-8"
        ),
    )
    crash_point("manifest")

    # Pitfall 8 / T-17-30: RE-READ through the single reader that rejects an
    # absolute path or a parent-directory segment. Adopt is the only code path
    # that writes a manifest from existing data, so skipping the re-read would
    # bypass that check exactly where a mangled entry would then be PLACED.
    reread = read_manifest(repo, unit)
    if reread != revised_manifest:
        raise Refusal(
            "recovery_unsupported",
            unit=unit,
            detail="material_invalid",
            hint="the revised manifest does not read back as it was built; "
            "inspect %s and nothing else was written"
            % os.path.relpath(pending_dir(repo, unit), os.fspath(repo)),
            next_token="resume",
        )
    # (iii) is pass 2's append, over the classification the revised manifest
    # implies: every adopted file now matches its after digest, so it is `done`
    # and will not be re-placed.
    return dict(found, manifest=reread), classify_manifest_files(repo, unit, reread)


def batch_drift(rows, state):
    """The drifted paths THIS BATCH touched (phase-17 IN-04).

    The resume drift notice's condition and its wording have to describe the
    same thing. The condition was ``state["page_drift"]`` — any drifted basis
    path or signed target of the unit — while the sentence says "completing
    THIS BATCH leaves <id> drifted" and recommends ``edits`` at the adoption's
    own seq, so a drifted path OUTSIDE the batch would have produced a notice
    naming a file the batch never touched. Intersected with the batch's own
    rows, the sentence and its condition are one statement again.

    ``rows`` spells a page repo-relatively and ``drifted_paths`` spells it
    docs-relatively, so both are tried; a comparison that matched neither would
    suppress the notice as silently as the wrong condition raised it.

    Latent rather than reproduced — ``draft`` refuses a file source when more
    than one target is signed, so a generation batch spans every signed target
    today — which is exactly why it is worth a name and a test rather than a
    comment.
    """
    if state is None:
        return []
    # The two spellings of one page: `rows` carries the manifest's REPO-relative
    # pathspecs (they go to `git add`), `drifted_paths` the snapshot's
    # DOCS-relative keys (`read_fs` keys on `basis.files[].path`). Comparing
    # them raw silently matched nothing, which is the same "the notice never
    # fires" answer as a wrong condition, arrived at differently.
    drifted = set(state.get("drifted_paths") or [])
    prefix = DOCS_ROOT + "/"
    hits = []
    for row in rows:
        path = row.get("path") or ""
        relative = path[len(prefix) :] if path.startswith(prefix) else path
        if path in drifted or relative in drifted:
            hits.append(path)
    return hits


def resume_pass_two(repo, unit, found, rows, as_json):
    """Contract 5.8 pass 2: truncate, append, then the shared write tail.

    Reached only after the decision, so every byte written here is written with
    the author's answer in hand. The steps are the contract's, in its order:
    truncate the partial line, append what is missing BYTE FOR BYTE from the
    manifest, re-verify the chain, then hand the rest to :func:`write_tail` —
    the same four steps every uninterrupted transition runs.
    """
    root = os.fspath(repo)
    manifest = found["manifest"]
    entries = manifest["files"]
    events = [json.loads(line) for line in manifest["events"]]
    path = ledger_path(repo, unit)
    relative_ledger = os.path.relpath(path, root)

    # Exactly the paths the manifest names, plus the ledger this batch is
    # appended to. Never a directory and never the working tree: a recovery
    # runs with whatever the interruption left lying around (T-17-31).
    pathspecs = [entry["path"] for entry in entries] + [relative_ledger]
    destinations = [(name, None) for name in pathspecs]
    guard_write_paths(repo, unit, destinations)
    guard_placeable_paths(repo, unit, destinations)
    guard_ignored_paths(repo, unit, pathspecs)

    if found["partial"]:
        truncate_partial_line(path)
    # The manifest's own recorded lines, never re-serialised: a re-serialisation
    # that differs by a single byte breaks every chain link after it.
    missing = manifest["events"][len(found["tail"]) :]
    if missing:
        append_batch(path, missing)
    crash_point("append")

    problems = verify_chain(_split_ledger(_read_text(path, unit))[0])
    if problems:
        # A chain that does not verify after the append is a refusal, not a
        # warning: placing and committing on top of it would legitimise it.
        raise Refusal(
            "ledger_corrupt",
            unit=unit,
            detail="the chain does not verify after the recovery append: %s"
            % problems[0],
            hint="inspect %s; nothing was placed and nothing was committed"
            % relative_ledger,
        )

    # Only `recoverable` files are placed. A `done` file already holds the
    # intended bytes, and `--overwrite` has already re-read the author's
    # `unexpected` files as recoverable by their recorded decision.
    place = [entry for entry, row in zip(entries, rows) if row["class"] == "recoverable"]
    last = events[-1]
    result = write_tail(
        repo,
        unit,
        recovery_phase(events),
        entries,
        pathspecs,
        [event["seq"] for event in events],
        last.get("note") or "",
        git_head(repo),
        verdict=last.get("verdict"),
        place=place,
    )
    report_hook_changes(
        result,
        repo,
        existing_drift={
            row["path"]: sha256_bytes(row["disk"]) if row["disk"] is not None else None
            for row in rows if row["class"] == "unexpected"
        },
    )
    # CR-01: this derivation runs AFTER `write_tail` has committed, so it must
    # never be able to unmake the transition. `unit_state` -> `read_fs` ->
    # `contained_page` raises `Refusal` by design (`bad_write_path` on a `docs`
    # that no longer resolves inside the repository, `ledger_corrupt` on a
    # damaged chain) and those are exactly the states a post-commit hook can
    # leave behind. Letting the refusal escape turned a landed commit into a
    # non-zero exit with no success line at all — the caller, routing on the
    # exit code plus the `Next:` token, could not tell that the batch had
    # committed. Contract 5.7 step 5 says the opposite for this very step: "the
    # transition stands (it is committed); the verb exits 0 with the warning ...
    # and then re-derives state and prints the routed `Next:`". So the guard is
    # `next_token_for`'s (fall back to `show`), except that here the failure is
    # SAID rather than silently swallowed: the author needs to know why the
    # route degraded, and the repository is in a state that needs their hands.
    # WR-04: ONE list, printed to stderr and carried in the `--json` document
    # both. These notices used to exist as structured data only on the refusal
    # path (`refusal.extra["notices"]`), so contract 5.8's "an unused note is
    # reported after success, or in the refusal's structured `notices` field if
    # completion fails" read as parity and was not: on success the three
    # skills, which consume `--json`, got no machine-readable signal that the
    # note their author had just written was discarded. That is the iteration-7
    # WR-03 failure — "the only signal was silence" — re-opened for the machine
    # surface.
    notices = []
    try:
        state = unit_state(repo, unit)
    except Exception as error:  # noqa: BLE001 — a committed transition must still report
        state = None
        notices.append(
            "state could not be re-derived after the commit (%s); the "
            "transition stands — inspect the repository, then `dogen show %s`."
            % (derivation_failure(error), unit)
        )
    notices.extend(found.get("notices", []))
    if "repeated_adoption" in found and batch_drift(rows, state):
        notices.append(
            "The bytes on disk differ from the digest seq %s records; "
            "completing this batch leaves %s drifted; "
            '`dogen edits %s --note "<why>"` records them as a reviewer edit.'
            % (found["repeated_adoption"], unit, unit)
        )
    for notice in notices:
        diagnostic(notice)
    segments = [
        "resumed %s" % unit,
        "seq %s" % result["seq_range"],
        git(["rev-parse", "--short", "HEAD"], repo).stdout.strip(),
        "%d file(s) placed" % len(place),
    ]
    return respond(
        segments,
        route(state) if state is not None else "show",
        as_json,
        payload={"notices": notices} if notices else None,
    )


def cmd_resume(args):
    """``resume`` — complete an interrupted write (contract 5.8). Pass 1.

    Pass 1 is read-only and always runs: classify every manifest file, print
    the classification, and stop at the decision. ``--dry-run`` stops one step
    earlier, having written nothing at all — stage a's cleanup included, which
    is why the classification runs in report mode rather than write mode.

    Pass 2 (truncate, append, place, commit, clean up) runs only after the
    decision, through the same write tail every uninterrupted transition uses.

    Contract 5.7 exempts this verb from the `retired` precondition: a retired
    unit's interrupted transition still has to be completable.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()
    with unit_lock(repo, unit):
        git_busy_guard(repo, unit)
        # Report mode, never the raising one: the two rows stage a raises for
        # are precisely the two this verb exists to resolve, and the first of
        # them raises with the hint `dogen resume <id>` (RESEARCH Pitfall 6).
        found = classify_stage_a(repo, unit, report_only=True)
        validate_unit_id(unit)
        found_guard(repo, unit, os.path.exists(ledger_path(repo, unit)))

        # WR-09, the mirror of the check above: argparse puts `--note` outside
        # the `--overwrite`/`--adopt` mutually exclusive group, so
        # `resume <id> --note "…"` parsed fine and the note was discarded
        # without a word. A note is the record of a decision; a note with no
        # decision to attach it to is a mistake, and saying so is the same
        # discipline `plan-steps` applies to `--keep-evidence` / `--note`.
        if getattr(args, "note", None) is not None and not args.adopt:
            raise Refusal(
                "bad_target",
                unit=unit,
                detail="--note records the reviewer edit --adopt writes; this "
                "run records no edit, so the note has nothing to attach to",
                # CR-02 (iteration 4): the third place the tool names
                # `--adopt`, found by walking the offer sites rather than the
                # ones a review reproduced. Unqualified it routes a mistyped
                # flag straight into `adopt_unsupported`.
                hint='dogen resume %s --adopt --note "…" keeps the bytes on '
                "disk; drop --note to resume without one — %s"
                % (unit, ADOPT_PRECONDITION),
                next_token="resume",
            )

        reason = found["reason"]
        if reason is not None and reason != "uncommitted_tail":
            # Everything else stage a classified — a broken chain, a rewritten
            # committed prefix, a legacy ledger, a record that belongs to
            # another unit — is refused here exactly as it is refused for every
            # other verb. `resume` completes an interrupted write; it does not
            # repair a record whose damage predates one.
            raise Refusal(
                reason,
                unit=unit,
                detail=found["detail"],
                hint=found["hint"],
                next_token=found["next"],
                extra=found["extra"],
                report_lines=found["findings"],
            )

        if reason is None:
            if found["situation"] != "clean":
                report(["would delete pending/: %s" % found["situation"]], as_json)
            return refuse(
                "nothing_to_resume",
                unit=unit,
                detail="no uncommitted tail in %s"
                % os.path.relpath(ledger_path(repo, unit), os.fspath(repo)),
                hint="dogen show %s" % unit,
                next_token=next_token_for(repo, unit),
                as_json=as_json,
            )

        # --- pass 1: one line per file, then a diff for each unexpected one ---
        rows = found["files"]
        lines = ["%s %s" % (row["class"], row["path"]) for row in rows]
        for row in rows:
            if row["class"] == "unexpected":
                lines.extend(resume_diff(row))
        stray_adopt = os.path.isdir(adopt_dir(repo, unit)) and not adopt_referenced(
            found["manifest"]
        )
        if stray_adopt:
            lines.append(
                "would delete pending/adopt/: copies no manifest references"
            )
        report(lines, as_json)

        listed = [{"path": r["path"], "class": r["class"]} for r in rows]
        if args.dry_run:
            segments = ["resumable %s" % unit, found["detail"], "%d file(s)" % len(rows)]
            return respond(segments, "resume", as_json, payload={"files": listed})

        # A crash before contract 5.8's step (ii) leaves the adopt copies behind
        # with the OLD manifest still authoritative. They are stray: the next
        # write-mode run deletes them, and the dry-run above reported them.
        # `resume` is the only verb that reaches write mode with a live tail —
        # every other one refuses at stage a — so this is where the sweep lives.
        if stray_adopt:
            shutil.rmtree(adopt_dir(repo, unit))

        # --- the decision (contract 5.8) --------------------------------------
        unexpected = [r for r in rows if r["class"] == "unexpected"]
        if unexpected and not (args.overwrite or args.adopt):
            # WR-01 (iteration 9): WHICH two choices this batch has is not one
            # sentence. `resume_adopt` reads the same last event and takes a
            # different arm when it is already an adoption — no new reviewer
            # edit is written there, so `--note` is dropped, and `--overwrite`
            # restores the bytes that adoption saved rather than "discarding"
            # anything the author put on disk. Offering `--note '<why>'` on
            # that batch is the iteration-7 WR-03 defect said out loud by the
            # tool: the docs were corrected and this hint was not. Two raise
            # sites rather than one branched string, so each hint stays a
            # single contiguous literal that the S-13 walk reads whole.
            last_event = json.loads(found["manifest"]["events"][-1])
            unexpected_files = [f for f in listed if f["class"] == "unexpected"]
            detail = (
                "%d file(s) hold bytes the interrupted transition did not write"
                % len(unexpected)
            )
            if (
                last_event.get("kind") == "reviewer-edit"
                and last_event.get("hook") is True
            ):
                # Read out here, not inside the hint expression: S-13's walk
                # fails closed on any call it cannot read inside prose, and
                # rightly — a call there could be prose. This one is a seq
                # number, so it is fetched as data first and interpolated like
                # `unit`.
                adopted_seq = last_event.get("seq")
                raise Refusal(
                    "resume_ambiguous",
                    unit=unit,
                    detail=detail,
                    hint="this batch's last event at seq %s is already an "
                    "adoption, so there is no new reviewer edit to write and "
                    "no note to record: dogen resume %s --adopt retains the "
                    "bytes on disk and completes the existing batch, appending "
                    "nothing; dogen resume %s --overwrite restores the bytes "
                    "that adoption saved — %s. Either choice re-places the "
                    "bytes, so if git has already refused this batch, remove "
                    "what is refusing the commit first."
                    % (adopted_seq, unit, unit, ADOPT_PRECONDITION),
                    next_token="resume",
                    extra={"files": unexpected_files},
                )
            raise Refusal(
                "resume_ambiguous",
                unit=unit,
                detail=detail,
                # CR-02: `resume_adopt`'s precondition applies here
                # identically — this refusal is raised on ANY batch whose placed
                # files were rewritten, including the `signoff`, `unit edit`,
                # `plan-steps`, `step`, `review`, `edits` and `unit retire`
                # batches that write `unit.md`, none of which `--adopt` can
                # take. The second clause is the refused-batch warning
                # `escape_hint` would otherwise replace this hint with: both
                # choices re-run the transition, so on a batch git has already
                # refused, removing the blocker comes first. Said rather than
                # substituted, because this refusal is where that escape LANDS.
                hint="dogen resume %s --overwrite discards them; dogen resume "
                "%s --adopt --note '<why>' keeps them as a recorded reviewer "
                "edit — %s. Either choice re-places the bytes, so if git has "
                "already refused this batch, remove what is refusing the "
                "commit first." % (unit, unit, ADOPT_PRECONDITION),
                next_token="resume",
                extra={"files": unexpected_files},
            )
        if args.overwrite:
            # The author's recorded decision to discard, and nothing else about
            # pass 2 changes: an `unexpected` file simply joins the placement
            # list the `recoverable` ones are already on.
            for row in unexpected:
                row["class"] = "recoverable"
        elif args.adopt:
            found, rows = resume_adopt(repo, unit, found, rows, args)
        try:
            return resume_pass_two(repo, unit, found, rows, as_json)
        except Refusal as refusal:
            if found.get("notices"):
                refusal.extra["notices"] = found["notices"]
            raise


def cmd_verify(args):
    """``verify`` — contract 5.9's V1–V19 over one unit, read-only.

    Built on ``cmd_show``'s dual-render shape, with one deliberate difference in
    the preamble: the readers' :func:`read_only_unit` refuses at exit 6 on a
    unit with an uncommitted tail or damaged recovery material, and those are
    precisely the units whose V1–V4 results the author needs (RESEARCH Pitfall
    7). So stage a runs in the REPORT mode plan 17-06 added — the same table,
    the same order, the same messages, returned instead of raised.

    The report is written and FLUSHED before any refusal, because a refusal is
    exactly one JSON line on stderr and that count is a harness assertion.

    D-05's exit rule: any FAIL among V1–V13 raises the EXISTING
    ``ledger_corrupt`` refusal, naming the failing ids, with ``next: show``.
    No new reason key is introduced — contract 5.7's reason table has no verify
    row, U-07 asserts the tool's keys equal that table exactly, and phase 18's
    docs check reads the same equality. Choosing between existing codes rather
    than adding one is the discipline three phase-16 plans already applied.
    WARN and INFO alone exit 0, with the full report still on stdout.
    """
    as_json = bool(getattr(args, "json", False))
    unit = args.unit
    repo = git_root()
    classify_stage_a(repo, unit, report_only=True)
    validate_unit_id(unit)
    found_guard(repo, unit, os.path.exists(ledger_path(repo, unit)))

    split = ledger_split(repo, unit)
    events, snapshot, state = unit_view(repo, unit, lenient_events(split[0]))
    checks = run_verify(repo, unit, events, snapshot, state, split)
    notes = list(state.get("warnings") or [])
    counts = verify_summary(checks, notes)
    head = git_head(repo)

    if as_json:
        payload = {
            "unit": unit,
            "head": head,
            "verdict": counts["verdict"],
            "checks": checks,
            "warnings": notes,
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write("\n".join(verify_report_lines(head, checks, notes)) + "\n")
    sys.stdout.flush()

    if counts["failed"]:
        raise Refusal(
            "ledger_corrupt",
            unit=unit,
            detail="record integrity failed: %s" % ", ".join(counts["failed"]),
            hint="the report above names each failing check; %s is damaged and "
            "nothing may be appended" % ledger_label(ledger_path(repo, unit)),
            next_token="show",
        )
    return EXITS["success"]


class _Parser(argparse.ArgumentParser):
    """An argparse parser whose usage errors keep GATE-04's one-JSON-line rule."""

    def error(self, message):
        raise Refusal(
            "bad_target",
            detail=message,
            hint="dogen %s --help" % (self.prog.split(" ", 1)[-1] if " " in self.prog else ""),
        )


# --- context (contract 5.1, repo-level) -------------------------------------

#: The well-known context artefacts, contract 5.1: the ONE definition site.
#: ``dogen-plan`` grounds itself in these; `dogen-onboard` authors the first
#: three from a walk over the repository's own docs; `dogen-fetch` authors any
#: of them from declared external sources; an external code-to-docs mapper's
#: output reaches the record through the same two verbs. A staged name outside
#: this tuple is refused, so no skill can smuggle an arbitrary write into
#: ``.dogen/context/`` through the staging directory.
CONTEXT_ARTIFACTS = (
    "doc-style.md",
    "glossary.md",
    "structure.md",
    "code-to-docs-map.md",
    "doc-gaps.md",
)

#: The subset `dogen-onboard` produces. `context show` routes ``onboard`` while
#: any of these is absent; the other two are optional and never route on their
#: own — they come from tooling outside dogen, when the author has it.
CONTEXT_ONBOARD_SET = CONTEXT_ARTIFACTS[:3]

CONTEXT_MANIFEST = "manifest.json"
CONTEXT_PHASE = "context-recorded"

#: ``.dogen/staging/_context``: the underscore is outside the unit-id alphabet
#: (5.6), so this directory can never collide with a unit's own staging.
CONTEXT_STAGING_NAME = "_context"

#: The sidecar `context stage --source` writes beside a staged artefact.
_CONTEXT_SOURCES_SUFFIX = ".sources.json"


def context_dir(repo):
    """``<repo>/.dogen/context`` — the published, committed artefacts."""
    return os.path.join(os.fspath(repo), ".dogen", "context")


def context_staging(repo):
    """``<repo>/.dogen/staging/_context`` — tool-owned, gitignored, transient."""
    return staging_dir(repo, CONTEXT_STAGING_NAME)


def context_manifest_path(repo):
    """``<repo>/.dogen/context/manifest.json``."""
    return os.path.join(context_dir(repo), CONTEXT_MANIFEST)


def validate_context_name(name):
    """Contract 5.1: a context artefact is one of :data:`CONTEXT_ARTIFACTS`.

    The reason table names no dedicated code for an unrecognised artefact, so
    the ``bad_*`` input family's ``bad_target`` carries it (the rule
    ``validate_unit_id`` already applies).
    """
    if not isinstance(name, str) or name not in CONTEXT_ARTIFACTS:
        raise Refusal(
            "bad_target",
            detail="%r is not a context artefact" % name,
            hint="stage one of: %s" % ", ".join(CONTEXT_ARTIFACTS),
        )
    return name


def read_context_body(spec):
    """``--body-file -`` reads stdin; anything else is a path. UTF-8 bytes, kept raw.

    The artefact's bytes are what the manifest digests, so they are read as
    bytes and only CHECKED to be UTF-8 — never re-encoded, so the digest is of
    what the author handed over.
    """
    if spec == "-":
        data = sys.stdin.buffer.read()
        label = "stdin"
    else:
        try:
            with open(spec, "rb") as handle:
                data = handle.read()
        except OSError as bad:
            raise Refusal(
                "bad_target",
                detail="--body-file %s cannot be read (%s)" % (spec, type(bad).__name__),
                hint="pass an existing readable file, or - to read the body from stdin",
            )
        label = "--body-file %s" % spec
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise Refusal(
            "bad_target",
            detail="the body read from %s is not UTF-8 text" % label,
            hint="pass a UTF-8 body, or --body-file F naming a UTF-8 file",
        )
    if not data.strip():
        raise Refusal(
            "bad_target",
            detail="the body read from %s is empty" % label,
            hint="a context artefact carries prose; stage nothing for an empty one",
        )
    return data


def validate_context_sources(sources):
    """``--source`` locators: one line each, non-empty, capped at MAX_ORIGINS.

    A locator is a CLAIM the skill records — a path, a URL, a tool-result id.
    The tool digests nothing behind it (a URL is not on this filesystem), which
    is why it is recorded verbatim in the manifest rather than as a digest.
    """
    cleaned = []
    for source in sources:
        if not isinstance(source, str) or "\n" in source or "\r" in source:
            raise Refusal(
                "bad_target",
                detail="a --source locator must be a single line",
                hint="pass one --source per origin: a path, a URL or a tool-result id",
            )
        text = source.strip()
        if not text:
            raise Refusal(
                "bad_target",
                detail="a --source locator is empty",
                hint="pass one --source per origin: a path, a URL or a tool-result id",
            )
        cleaned.append(check_byte_cap("source", text, 1024))
    if len(cleaned) > MAX_ORIGINS:
        raise Refusal(
            "bad_target",
            detail="%d sources exceed the cap of %d" % (len(cleaned), MAX_ORIGINS),
            hint="declare the origins that matter, not every file you looked at",
        )
    return cleaned


def context_sidecar_path(repo, name):
    """The staged sources sidecar for ``name``."""
    return os.path.join(context_staging(repo), name + _CONTEXT_SOURCES_SUFFIX)


def staged_context(repo):
    """``{name: bytes}`` of every recognised artefact staged under ``_context/``.

    A file in the staging directory that is neither a recognised artefact nor
    one's sources sidecar is refused by name: the tool owns this directory, so
    anything else there was put there by hand, and promoting around it would
    silently drop the author's intent.
    """
    staging = context_staging(repo)
    if not os.path.isdir(staging):
        return {}
    staged = {}
    for entry in sorted(os.listdir(staging)):
        path = os.path.join(staging, entry)
        if not os.path.isfile(path):
            continue
        if entry in CONTEXT_ARTIFACTS:
            with open(path, "rb") as handle:
                staged[entry] = handle.read()
            continue
        if entry.endswith(_CONTEXT_SOURCES_SUFFIX) and (
            entry[: -len(_CONTEXT_SOURCES_SUFFIX)] in CONTEXT_ARTIFACTS
        ):
            continue
        raise Refusal(
            "bad_target",
            detail="%s is staged under .dogen/staging/%s/ and is not a context artefact"
            % (entry, CONTEXT_STAGING_NAME),
            hint="remove it; a context artefact is staged with dogen context stage",
        )
    return staged


def staged_context_sources(repo, name):
    """The declared sources of a staged artefact, ``[]`` when none were declared."""
    path = context_sidecar_path(repo, name)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            sources = json.load(handle)
    except (OSError, ValueError):
        raise Refusal(
            "bad_target",
            detail="the staged sources of %s cannot be read" % name,
            hint="re-run dogen context stage %s to restage it" % name,
        )
    if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
        raise Refusal(
            "bad_target",
            detail="the staged sources of %s are not a list of locators" % name,
            hint="re-run dogen context stage %s to restage it" % name,
        )
    return sources


def read_context_manifest(repo):
    """The published manifest, or ``None`` when no context was ever recorded."""
    path = context_manifest_path(repo)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as bad:
        raise Refusal(
            "bad_target",
            detail=".dogen/context/%s is not a readable JSON document (%s)"
            % (CONTEXT_MANIFEST, type(bad).__name__),
            hint="restore it from git, or re-record the artefacts with dogen context record",
        )
    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), dict):
        raise Refusal(
            "bad_target",
            detail=".dogen/context/%s does not carry an artifacts map" % CONTEXT_MANIFEST,
            hint="restore it from git, or re-record the artefacts with dogen context record",
        )
    return manifest


def context_state(repo):
    """The derived state of every context artefact — computed, never stored.

    Per name: ``present`` (a file is on disk), ``recorded`` (the manifest names
    it), ``sha256`` (the current bytes, ``None`` when absent) and ``drifted``
    (present and recorded, and the bytes are not the recorded ones — a hand
    edit after the record; reported, never refused, per 5.1's guarantee).
    """
    manifest = read_context_manifest(repo)
    recorded = manifest["artifacts"] if manifest else {}
    artifacts = {}
    for name in CONTEXT_ARTIFACTS:
        current = digest_file(os.path.join(context_dir(repo), name))
        entry = recorded.get(name) if isinstance(recorded.get(name), dict) else None
        artifacts[name] = {
            "present": current is not None,
            "recorded": entry is not None,
            "sha256": current,
            "drifted": bool(
                entry is not None and current is not None and entry.get("sha256") != current
            ),
        }
    return {
        "artifacts": artifacts,
        "staged": sorted(staged_context(repo)),
        "manifest": (
            {
                "recorded_at": manifest.get("recorded_at"),
                "commit": manifest.get("commit"),
                "model": manifest.get("model"),
                "model_origin": manifest.get("model_origin"),
            }
            if manifest
            else None
        ),
    }


def context_next(repo, state=None):
    """Contract 5.5's context routing: ``record`` → ``onboard`` → ``plan``.

    Something staged and not yet recorded comes first — finish the act that
    was begun — then the absence of any onboarding artefact, then the plan.
    """
    state = state or context_state(repo)
    if state["staged"]:
        return "record"
    for name in CONTEXT_ONBOARD_SET:
        if not state["artifacts"][name]["present"]:
            return "onboard"
    return "plan"


def render_context_manifest(manifest):
    """The manifest's bytes: canonical JSON, the ledger writer's own shape (5.2)."""
    return (
        json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def cmd_context_stage(args):
    """``context stage`` — one artefact into the tool-owned staging directory.

    Nothing is recorded and nothing is committed: this is how a skill that
    holds no write-capable tool hands the tool a body, exactly as ``unit new
    --body-file -`` hands it a plan. ``context record`` is the act.
    """
    as_json = bool(getattr(args, "json", False))
    repo = git_root()
    root = os.fspath(repo)
    name = validate_context_name(args.name)
    sources = validate_context_sources(list(args.source or []))
    data = read_context_body(args.body_file)
    with unit_lock(repo):
        staging = context_staging(repo)
        os.makedirs(staging, exist_ok=True)
        publish_atomic(os.path.join(staging, name), data)
        sidecar = context_sidecar_path(repo, name)
        if sources:
            publish_atomic(
                sidecar,
                (json.dumps(sources, ensure_ascii=False) + "\n").encode("utf-8"),
            )
        elif os.path.exists(sidecar):
            os.remove(sidecar)
    segments = [
        "staged %s" % name,
        os.path.relpath(os.path.join(staging, name), root),
        "%d source(s) declared" % len(sources) if sources else "no source declared",
    ]
    return respond(segments, context_next(repo), as_json)


def cmd_context_record(args):
    """``context record`` — promote the staged artefacts and commit them.

    Stages a–f in contract 5.7's shape for a repo-level verb: **a** lock and
    ``.git/index.lock`` (there is no unit ledger, so no chain to classify);
    **b** the model claim, the note, the staged set, the identity; **c** at
    least one artefact staged; **d** ``noop_unchanged`` when every staged
    artefact already holds these bytes in HEAD; **f** place, freeze the
    manifest, one commit with explicit pathspecs and no ``Dogen-Unit`` — the
    context belongs to the repository, not to a unit.
    """
    as_json = bool(getattr(args, "json", False))
    repo = git_root()
    root = os.fspath(repo)

    with unit_lock(repo):
        # --- a: lock, .git/index.lock ------------------------------------------
        git_busy_guard(repo)

        # --- b: input validation ----------------------------------------------
        model = validate_model(args.model, args.model_origin)
        note = validate_note(args.note) if args.note is not None else ""
        staged = staged_context(repo)
        identity = git_identity(repo)
        manifest_before = read_context_manifest(repo)

        # --- c: per-verb preconditions ----------------------------------------
        if not staged:
            raise Refusal(
                "bad_target",
                detail="nothing is staged under .dogen/staging/%s/" % CONTEXT_STAGING_NAME,
                hint="dogen context stage <name> --body-file - stages one artefact; then record",
                next_token=context_next(repo),
            )

        # --- d: no-op recognition ---------------------------------------------
        # A staged artefact is unchanged only when HEAD already holds these
        # bytes at the published path: a record whose commit failed leaves the
        # placed file on disk and the manifest beside it, and comparing against
        # disk alone would call the retry a no-op and never commit.
        relative_dir = os.path.relpath(context_dir(repo), root)
        unchanged = manifest_before is not None
        for name, data in staged.items():
            blob = git_show_blob(repo, "HEAD", os.path.join(relative_dir, name))
            if blob is None or sha256_bytes(blob) != sha256_bytes(data):
                unchanged = False
                break
        if unchanged:
            # The staged copies are redundant with the record, so they are
            # discarded here: left in place they would route `show` at `record`
            # for an act that can never do anything.
            shutil.rmtree(context_staging(repo), ignore_errors=True)
            raise Refusal(
                "noop_unchanged",
                detail="every staged artefact (%s) already holds the recorded bytes"
                % ", ".join(sorted(staged)),
                hint="the record already says this; the staged copies are discarded",
                next_token=context_next(repo),
                extra={"commit": manifest_before.get("commit")},
            )

        # --- f: write -----------------------------------------------------------
        head = git_head(repo)
        recorded = manifest_before["artifacts"] if manifest_before else {}
        artifacts = {}
        for name in CONTEXT_ARTIFACTS:
            if name in staged:
                artifacts[name] = {
                    "sha256": sha256_bytes(staged[name]),
                    "sources": staged_context_sources(repo, name),
                }
                continue
            current = digest_file(os.path.join(context_dir(repo), name))
            if current is None:
                continue
            # A published artefact this act does not touch keeps its row; its
            # digest is re-read from disk so the frozen set is what is there.
            previous = recorded.get(name) if isinstance(recorded.get(name), dict) else {}
            artifacts[name] = {
                "sha256": current,
                "sources": list(previous.get("sources") or []),
            }
        manifest = {
            "actor": identity,
            "artifacts": artifacts,
            "commit": head,
            "contract": CONTRACT,
            "model": model,
            "model_origin": args.model_origin,
            "note": note,
            "recorded_at": utc_now(),
            "tool_version": __version__,
        }
        files = [
            (os.path.join(relative_dir, name), data) for name, data in sorted(staged.items())
        ]
        files.append((os.path.join(relative_dir, CONTEXT_MANIFEST), render_context_manifest(manifest)))
        guard_write_paths(repo, "", files)
        guard_placeable_paths(repo, "", files)
        pathspecs = [path for path, _ in files]
        guard_ignored_paths(repo, "", pathspecs)

        before_index = index_snapshot(repo)
        for path, data in files:
            publish_atomic(os.path.join(root, path), data)
        entries = [{"path": path, "after_sha": sha256_bytes(data)} for path, data in files]

        added = git_add(repo, pathspecs)
        if added.returncode != 0:
            raise Refusal(
                "bad_write_path",
                detail="git add refused the context artefacts: %s"
                % (added.stderr.strip().splitlines() or ["(no message)"])[0],
                hint="fix what git reports; the staged artefacts are kept, re-run dogen context record",
                next_token="record",
            )
        trailers = [
            ("Dogen-Phase", CONTEXT_PHASE),
            ("Dogen-Head", (head or "0" * 40)[:16]),
        ]
        if model:
            trailers.append(("Dogen-Model", model))
        committed = git_commit(
            repo,
            "dogen: %s" % CONTEXT_PHASE.replace("-", " "),
            collapse_note(note) if note else "",
            trailers,
            pathspecs,
        )
        if committed.returncode != 0:
            raise Refusal(
                "bad_write_path",
                detail="git commit refused the context artefacts: %s"
                % (committed.stderr.strip().splitlines() or ["(no message)"])[0],
                hint="fix what git reports; the staged artefacts are kept, re-run dogen context record",
                next_token="record",
            )
        diagnostic(
            "git: committed %s — dogen: %s"
            % (git(["rev-parse", "--short", "HEAD"], repo).stdout.strip(), CONTEXT_PHASE.replace("-", " "))
        )
        changed, extra = post_commit_check(repo, entries, pathspecs, before_index)
        report_hook_changes({"changed": changed, "extra": extra}, repo)
        shutil.rmtree(context_staging(repo), ignore_errors=True)

    segments = [
        "recorded %d context artefact(s): %s" % (len(staged), ", ".join(sorted(staged))),
        relative_dir + os.sep,
        "%d artefact(s) frozen in %s" % (len(artifacts), CONTEXT_MANIFEST),
    ]
    return respond(segments, context_next(repo), as_json)


def cmd_context_show(args):
    """``context show`` — read-only: what is published, staged, drifted; and ``Next:``."""
    as_json = bool(getattr(args, "json", False))
    repo = git_root()
    state = context_state(repo)
    next_token = context_next(repo, state)
    artifacts = state["artifacts"]
    present = [n for n in CONTEXT_ARTIFACTS if artifacts[n]["present"]]
    missing = [n for n in CONTEXT_ARTIFACTS if not artifacts[n]["present"]]
    drifted = [n for n in CONTEXT_ARTIFACTS if artifacts[n]["drifted"]]
    unrecorded = [n for n in present if not artifacts[n]["recorded"]]
    segments = [
        "context: %d of %d artefact(s) present%s"
        % (
            len(present),
            len(CONTEXT_ARTIFACTS),
            " (%s)" % ", ".join(present) if present else "",
        ),
        "missing: %s" % (", ".join(missing) if missing else "none"),
        "drifted: %s" % (", ".join(drifted) if drifted else "none"),
        "unrecorded: %s" % (", ".join(unrecorded) if unrecorded else "none"),
        "staged: %s" % (", ".join(state["staged"]) if state["staged"] else "none"),
    ]
    return respond(segments, next_token, as_json, state)


# --- argparse (the §6 verb table) -----------------------------------------


def build_parser():
    """The contract's §6 verb table, complete — every verb, every argument.

    ``dogen --help`` is a machine-diffed observable, not documentation: phase
    18's ``check_docs.py`` compares it row for row with §6, and U-08 makes the
    same comparison now so the two cannot drift during this phase. Every verb
    was registered with its full signature from day one (D-16) and every one of
    them now has a body: `verify` was the last stub, and the transitional
    machinery went with it.

    ``--force`` is registered nowhere. ``slim@357c513``'s
    ``dogen-signoff.sh --force`` wrote a second signoff row; VERB-01 removes
    the flag rather than renaming it, and the replacement is the `already_signed`
    no-op plus ``unit edit --re-sign``.
    """
    common = _Parser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable output; refusals move to stdout",
    )

    parser = _Parser(
        prog="dogen",
        description="Record a documentation unit's human-in-the-loop path and "
        "gate its writes. The normative specification is docs/contract.md.",
        parents=[common],
    )
    verbs = parser.add_subparsers(dest="verb")

    unit = verbs.add_parser("unit", help="declare, edit or retire a unit")
    unit_verbs = unit.add_subparsers(dest="unit_verb")

    new = unit_verbs.add_parser(
        "new", parents=[common], help="declare a new documentation unit"
    )
    new.add_argument("unit", help="unit id: ^[a-z0-9][a-z0-9-]{0,63}$")
    new.add_argument("--intent", required=True, help=" | ".join(INTENTS))
    new.add_argument("--audience", required=True, help="who the page is for")
    new.add_argument("--title", required=True, help="the page title")
    new.add_argument("--target", required=True, help="docs-relative .md or .rst path")
    new.add_argument(
        "--also-target", action="append", default=[], help="an additional target"
    )
    new.add_argument("--source", action="append", default=[], help="a source path")
    new.add_argument("--notes", help="free-text plan notes")
    new.add_argument(
        "--body-file", required=True, help="the plan outline: a file, or - for stdin"
    )
    new.set_defaults(func=cmd_unit_new)

    edit = unit_verbs.add_parser(
        "edit", parents=[common], help="amend a declared unit's plan"
    )
    edit.add_argument("unit", help="unit id")
    edit.add_argument("--intent", help=" | ".join(INTENTS))
    edit.add_argument("--audience", help="who the page is for")
    edit.add_argument("--title", help="the page title")
    edit.add_argument("--target", help="replace the target list with this path")
    edit.add_argument("--also-target", action="append", help="add one more target")
    edit.add_argument("--source", action="append", help="replace the source list")
    edit.add_argument("--notes", help="free-text plan notes")
    edit.add_argument("--body-file", help="replace the body: a file, or - for stdin")
    edit.add_argument(
        "--re-sign",
        action="store_true",
        help="record the signoff in the same commit (one command, one commit)",
    )
    edit.set_defaults(func=cmd_unit_edit)

    retire = unit_verbs.add_parser(
        "retire", parents=[common], help="retire a unit (phase 17)"
    )
    retire.add_argument("unit", help="unit id")
    retire.add_argument("--note", required=True, help="why the unit is retired")
    retire.set_defaults(func=cmd_unit_retire)

    context = verbs.add_parser(
        "context", help="stage, record or show the repository's context artefacts"
    )
    context_verbs = context.add_subparsers(dest="context_verb")

    stage = context_verbs.add_parser(
        "stage", parents=[common], help="stage one context artefact from a body"
    )
    stage.add_argument("name", help="one of: %s" % ", ".join(CONTEXT_ARTIFACTS))
    stage.add_argument(
        "--body-file", required=True, help="the artefact's text: a file, or - for stdin"
    )
    stage.add_argument(
        "--source",
        action="append",
        default=[],
        help="a declared origin of this artefact: a path, a URL or a tool-result id",
    )
    stage.set_defaults(func=cmd_context_stage)

    record = context_verbs.add_parser(
        "record",
        parents=[common],
        help="promote the staged artefacts into .dogen/context/ and commit them",
    )
    record.add_argument(
        "--model", default="", help="the model that produced the artefacts (a claim)"
    )
    record.add_argument(
        "--model-origin",
        default="unknown",
        help="where the model claim came from (default: unknown, the honest default)",
    )
    record.add_argument("--note", help="what this record is about; the commit body")
    record.set_defaults(func=cmd_context_record)

    context_show = context_verbs.add_parser(
        "show", parents=[common], help="read-only: the published, staged and drifted artefacts"
    )
    context_show.set_defaults(func=cmd_context_show)

    sign = verbs.add_parser(
        "signoff",
        parents=[common],
        help="record the human signoff that freezes the plan",
    )
    sign.add_argument("unit", help="unit id")
    sign.set_defaults(func=cmd_signoff)

    steer = verbs.add_parser(
        "steer", parents=[common], help="record one steering request"
    )
    steer.add_argument("unit", help="unit id")
    request = steer.add_mutually_exclusive_group(required=True)
    request.add_argument("--note", help="the steering request")
    request.add_argument(
        "--note-file", help="read the request from a file, or - for stdin"
    )
    steer.add_argument(
        "--origin",
        choices=("plan", "manual"),
        default="manual",
        help="who asked: plan | manual (default: manual)",
    )
    steer.set_defaults(func=cmd_steer)

    plan_steps = verbs.add_parser(
        "plan-steps",
        parents=[common],
        help="record the step plan of an actionable unit",
    )
    plan_steps.add_argument("unit", help="unit id")
    plan_steps.add_argument(
        "--steps-file", required=True, help="the step plan: a file, or - for stdin"
    )
    plan_steps.add_argument(
        "--keep-evidence",
        action="store_true",
        help="carry the resolved prefix forward from the previous plan",
    )
    plan_steps.add_argument("--note", help="why the plan changed")
    plan_steps.set_defaults(func=cmd_plan_steps)

    step = verbs.add_parser(
        "step", parents=[common], help="record one step's evidence"
    )
    step.add_argument("unit", help="unit id")
    step.add_argument(
        "step_id", metavar="step-id", help="step id: ^[a-z0-9][a-z0-9._-]{0,31}$"
    )
    step.add_argument(
        "--steps-seq",
        required=True,
        type=int,
        metavar="N",
        help="the seq of the steps-planned event this evidence answers",
    )
    step.add_argument(
        "--evidence-file", required=True, help="the step's evidence JSON"
    )
    step.add_argument("--output-file", help="the command output the evidence cites")
    step.set_defaults(func=cmd_step)

    draft = verbs.add_parser(
        "draft",
        parents=[common],
        help="record a generation and write every signed target",
    )
    draft.add_argument("unit", help="unit id")
    draft.add_argument(
        "source", help="a file or directory under .dogen/staging/<id>/draft/"
    )
    draft.add_argument(
        "--model", default="", help='the model that produced the bytes (a claim)'
    )
    draft.add_argument(
        "--model-origin",
        default="unknown",
        help='where the model claim came from (default: unknown, the honest default)',
    )
    draft.add_argument("--report", help="the drafting skill's JSON report")
    draft.add_argument(
        "--unsteered-reason",
        help="record an override for the unsteered gate on THIS generation",
    )
    draft.set_defaults(func=cmd_draft)

    edits = verbs.add_parser(
        "edits",
        parents=[common],
        help="record a hand edit or a brownfield adoption as the complete basis set",
    )
    edits.add_argument("unit", help="unit id")
    recorded = edits.add_mutually_exclusive_group(required=True)
    recorded.add_argument("--note", help="what the author changed, and why")
    recorded.add_argument(
        "--note-file", help="read the note from a file, or - for stdin"
    )
    edits.set_defaults(func=cmd_edits)

    review = verbs.add_parser(
        "review",
        parents=[common],
        help="record a verdict and close pending requests by recorded disposition",
    )
    review.add_argument("unit", help="unit id")
    review.add_argument(
        "--verdict",
        required=True,
        choices=("accept", "fix", "redraft"),
        help="accept | fix | redraft",
    )
    reviewed = review.add_mutually_exclusive_group()
    reviewed.add_argument("--note", help="the verdict's note (required for fix/redraft)")
    reviewed.add_argument(
        "--note-file", help="read the note from a file, or - for stdin"
    )
    review.add_argument(
        "--resolves",
        action="append",
        default=[],
        metavar="A,B",
        help="seqs this accept judges satisfied (a judgment, not proof of a change)",
    )
    review.add_argument(
        "--withdraw",
        action="append",
        nargs=2,
        default=[],
        metavar=("SEQ", "REASON"),
        help="withdraw one pending request, with a reason (repeatable)",
    )
    review.set_defaults(func=cmd_review)

    resume = verbs.add_parser(
        "resume",
        parents=[common],
        help="complete an interrupted write in two passes (phase 17)",
    )
    resume.add_argument("unit", help="unit id")
    decision = resume.add_mutually_exclusive_group()
    decision.add_argument(
        "--dry-run", action="store_true", help="classify and report; write nothing"
    )
    decision.add_argument(
        "--overwrite", action="store_true", help="discard the author's later edits"
    )
    decision.add_argument(
        "--adopt", action="store_true", help="keep the author's later edits"
    )
    resume.add_argument("--note", help="what --adopt records as the reviewer edit")
    resume.set_defaults(func=cmd_resume)

    show = verbs.add_parser(
        "show",
        parents=[common],
        help="report the derived state, read-only",
    )
    show.add_argument("unit", help="unit id")
    show.add_argument(
        "--diff",
        action="store_true",
        help="diff each drifted path against the recorded basis bytes",
    )
    show.set_defaults(func=cmd_show)

    summary = verbs.add_parser(
        "summary",
        parents=[common],
        help="report the unit for a human reviewer; --md is paste-ready PR text",
    )
    summary.add_argument("unit", help="unit id")
    summary.add_argument(
        "--md", action="store_true", help="render paste-ready Markdown"
    )
    summary.set_defaults(func=cmd_summary)

    verify = verbs.add_parser(
        "verify",
        parents=[common],
        help="report contract 5.9's V1-V19 over the whole record",
    )
    verify.add_argument("unit", help="unit id")
    verify.set_defaults(func=cmd_verify)

    version = verbs.add_parser(
        "version",
        parents=[common],
        help="report the tool version and the contract number",
    )
    version.set_defaults(func=cmd_version)

    return parser


def _argv_unit(args):
    """The unit the parsed command line names, or ``""`` (CR-01).

    Every unit-scoped verb takes the id as its first positional, so the parsed
    namespace is the one place ``main`` can attribute a refusal raised below the
    verb — which is what the generic backstops need to stop reporting ``""``.
    """
    unit = getattr(args, "unit", "") if args is not None else ""
    return unit if isinstance(unit, str) else ""


def main(argv=None):
    """Entry point: parse, dispatch, and convert any refusal to its one line."""
    # Pre-scan, then let parse_args refine it. `as_json` used to be assigned
    # only AFTER parse_args, so every refusal raised from `_Parser.error` — the
    # class of error a skill is most likely to hit while wiring up arguments —
    # was printed with as_json=False, i.e. to stderr, while contract 5.7 says
    # `--json`: stdout. The skill read stdout as JSON and saw an empty
    # document (WR-06).
    raw = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in raw
    # CR-01: the generic backstops below reported `"unit": ""`, so the one line
    # a skill gets could not name what it had just refused (or, before the
    # placeability guard, wedged). `args` carries the unit for every unit-scoped
    # verb; it is bound before the try so an exception from parse_args itself
    # still leaves a defined name.
    args = None
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        as_json = bool(getattr(args, "json", False))
        handler = getattr(args, "func", None)
        if handler is None:
            parser.print_help(sys.stderr)
            return EXITS["success"]
        return handler(args)
    except Refusal as refusal:
        # Contract 5.8's honest limit, D-08: the findings on stdout FIRST, then
        # the refusal. Under `--json` `report` prints nothing — 5.7 moves the
        # refusal itself to stdout, where a text block before it would leave the
        # caller parsing a document that is not JSON, and the same facts ride in
        # `extra.paths` instead.
        report(refusal.report_lines, as_json)
        return refuse(
            refusal.reason,
            # WR-10: the fallback, not `refusal.unit` verbatim. CR-01 threaded
            # the unit into the three GENERIC backstops and left this arm --
            # the one every STRUCTURED refusal comes through -- reading a field
            # seven `read_events` call sites did not populate, so the common
            # case reported `""` while the rare one was attributable. Those
            # call sites are fixed above; this keeps a future raiser that
            # forgets the argument from regressing it silently.
            unit=refusal.unit or _argv_unit(args),
            detail=refusal.detail,
            hint=refusal.hint,
            next_token=refusal.next_token,
            as_json=as_json,
            extra=refusal.extra,
        )
    except UnitInvalid as invalid:
        return refuse(
            "unit_invalid",
            unit=_argv_unit(args),
            detail="line %d: %s" % (invalid.line, invalid.detail),
            hint="fix it with %s" % (invalid.flag or "--body-file"),
            as_json=as_json,
        )
    except json.JSONDecodeError as bad:
        # WR-10: a `JSONDecodeError` IS a `ValueError`, so it used to land in
        # the arm below and report a damaged RECORD as `bad_target` (2, "bad
        # input") — telling a skill the caller typed something wrong when the
        # truth is that a recorded line will not parse. `read_events` and
        # `verify_chain` guard their own `json.loads`; `resume_adopt`,
        # `resume_pass_two` and `prior_generation_seq` parse the manifest's
        # event lines with no local guard, and stage a's `event_invalid` row
        # catches that shape today only because it runs first. Naming the
        # record here keeps a future path that reaches one of those parses from
        # exiting 2 for a recovery situation.
        return refuse(
            "ledger_corrupt",
            unit=_argv_unit(args),
            detail="a recorded line is not valid JSON: %s" % bad,
            hint="inspect the unit's ledger.jsonl and pending/manifest.json; "
            "nothing was written",
            next_token="resume",
            as_json=as_json,
        )
    except ValueError as bad:
        return refuse(
            "bad_target",
            unit=_argv_unit(args),
            detail=str(bad),
            hint="",
            as_json=as_json,
        )
    except OSError as bad:
        # Contract 5.7: every non-zero exit is ONE JSON line, never a stack
        # trace — and an uncaught exception exits 1, which is the contract's
        # code for a GATE refusal, so a skill reading the exit code would read
        # "no signoff / plan stale / drift" where the truth is "I could not
        # read the file". `bad_target` keeps REASONS row-for-row with the
        # contract's reason table (the rule GATE-04 already applies to
        # validate_unit_id); a distinct io_error code belongs in the contract
        # first.
        #
        # WR-22: `str(OSError)` embeds the ABSOLUTE filename, and the WR-15
        # re-raise made the common permission / read-only-filesystem case newly
        # reachable through this arm. `ledger_label` exists (dogen:895) exactly
        # because WR-10 filed that leak: a diagnostic a skill is invited to
        # paste into an issue or a commit message may not carry the caller's
        # filesystem layout. Rebuilt field by field rather than from `str(bad)`,
        # and repo-relativised HERE rather than at every raiser, so a future
        # raiser cannot regress it.
        cause = bad.strerror or str(bad)
        if bad.errno is not None:
            cause = "[Errno %s] %s" % (bad.errno, cause)
        detail = "%s: %s" % (type(bad).__name__, cause)
        if bad.filename:
            detail += ": %s" % ledger_label(bad.filename)
        return refuse(
            "bad_target",
            unit=_argv_unit(args),
            detail=detail,
            hint="check the path's permissions and the filesystem",
            as_json=as_json,
        )
    except Exception as bad:  # noqa: BLE001 - contract 5.7 admits no traceback
        # CR-04: the four arms above are the exceptions this file RAISES. The
        # invariant is about every exception it can REACH: an uncaught one
        # prints a Python traceback and exits 1, which contract 5.7 and REASONS
        # define as a gate refusal ("no signoff / plan stale / drift"), so a
        # skill reading the exit code is told the gate said no when the truth
        # is that dogen fell over. Exit 6 is the record-and-recovery code, and
        # `detail` names the real exception rather than inventing a cause.
        #
        # WR-23: the SHAPE is right and the exit code stays; the SENTENCE was a
        # cause this arm never established. It fires for a `KeyError` in
        # `route()`, an `AttributeError` in `summary_markdown`, a `TypeError` in
        # repository discovery before any ledger is opened -- and it can fire
        # AFTER a mutating verb has appended and committed correctly. "The
        # record could not be derived; inspect the ledger" told all of them
        # their hash-chained record is damaged, and routed them to a verb that
        # was a stub, so the route went nowhere either. `next` is `show` for
        # that reason and STAYS `show` now that plan 17-06 has landed the verb:
        # this arm has established no interruption, and sending an internal
        # fault to the recovery verb would be the same wrong diagnosis with a
        # working destination. `error`, `hint` and `next` are the three fields a
        # skill routes on. `internal_error` is this arm's own reason; exit 6 is
        # unchanged, because 6 is the record-and-recovery code, not the gate's.
        return refuse(
            "internal_error",
            unit=_argv_unit(args),
            detail="unexpected internal fault: %s: %s" % (type(bad).__name__, bad),
            hint="this is a dogen defect, not a diagnosis of your record; run "
            "dogen show on the unit, then re-run the same command unchanged and "
            "report the detail above",
            next_token="show",
            as_json=as_json,
        )


if __name__ == "__main__":
    raise SystemExit(main())
