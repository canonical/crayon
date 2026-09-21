"""Unit tests for the gate-free core of ``dogen`` (U-01, U-02, U-03 caps slice).

Runner (D-12): ``python3 -m unittest tests/test_dogen_unit.py`` — never
``discover`` (the repo has no ``tests/__init__.py``, RESEARCH P-11) and never
pytest. The suite imports the extension-less repo-root ``dogen`` through a
``SourceFileLoader`` shim, so it needs no package, venv or path hack.

Organising principle, mirrored from ``tests/test_planning_lint.py``: a positive
gate (the contract's own shapes round-trip), a negative keystone (a rule
violation MUST be detected, never silently accepted) and a vacuous-pass guard
(an empty input cannot masquerade as valid).

Coverage:
  U-01  canonical line — byte stability, verbatim free text, the float ban
  U-02  chain and ledger I/O — ``prev`` over exact bytes, contiguity, round trip
  U-03  caps — every contract section 5.2 cap, inclusive, in UTF-8 bytes
  U-09  stage a's report mode and the per-file done/recoverable/unexpected
  U-10  the tool's own guards — line budget, 3.9 hazards, packaging, and this
        suite's own wholeness: the ``__main__`` block is the LAST statement in
        the file and the loaded count meets ``EXPECTED_MIN_TESTS``, because
        ``unittest.main()`` exits and a block placed higher up silently drops
        every class below it behind a green ``OK`` (CR-06)
  U-11  contract 5.9's V1–V19 verification report
"""

from __future__ import annotations

import argparse
import ast
import errno
import hashlib
import io
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOGEN_PATH = ROOT / "dogen.py"


def _load_dogen():
    """Import the extension-less repo-root ``dogen`` as a module (RESEARCH P7).

    A plain ``import dogen`` cannot find a file with no ``.py`` extension, and
    the file's entry point is guarded, so loading it executes no verb.
    """
    loader = importlib.machinery.SourceFileLoader("dogen", str(DOGEN_PATH))
    spec = importlib.util.spec_from_loader("dogen", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


dogen = _load_dogen()


def make_event(kind="steering", seq=0, prev=None, **payload):
    """Build a contract section 5.2 envelope with a fixed, byte-stable ``at``."""
    event = {
        "kind": kind,
        "seq": seq,
        "prev": prev,
        "at": "2026-01-01T00:00:00+00:00",
        "actor": {"name": "Test Author", "email": "test@example.com"},
        "tool_version": dogen.__version__,
        "contract": dogen.CONTRACT,
        "commit": "0" * 40,
    }
    event.update(payload)
    return event


def build_chain(payloads):
    """Return ``(events, lines)`` for a valid chain of ``len(payloads)`` events."""
    events = []
    lines = []
    prev = None
    for seq, payload in enumerate(payloads):
        event = make_event(seq=seq, prev=prev, **payload)
        line = dogen.canonical_line(event)
        events.append(event)
        lines.append(line)
        prev = dogen.chain_prev(line)
    return events, lines


class TempRepoTestCase(unittest.TestCase):
    """A hermetic temp git repo, mirroring ``setup_repo`` in the bash suite.

    ``GIT_CONFIG_GLOBAL``/``GIT_CONFIG_SYSTEM`` are neutralised so the
    developer's global ``commit.gpgsign=true`` cannot leak into a test repo
    (RESEARCH P-9); without that the suite is machine-dependent.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        self.env = dict(os.environ)
        self.env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        self.env["GIT_CONFIG_SYSTEM"] = "/dev/null"
        # WR-07: the D-15 fixture hooks are armed only by this explicit switch.
        self.env["DOGEN_TEST_HOOKS"] = "1"
        self.env.pop("DOGEN_NOW", None)
        self.git("init", "-q", "-b", "main", ".")
        self.git("config", "user.name", "Test Author")
        self.git("config", "user.email", "test@example.com")
        (self.repo / "source.md").write_text("# Test source\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "initial")

    def git(self, *args):
        """Run git inside the temp repo with the hermetic environment."""
        return subprocess.run(
            ["git"] + list(args),
            cwd=str(self.repo),
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )


class TestScaffold(unittest.TestCase):
    """The file itself: executable, 3.9 syntax, stdlib-only, no gate code yet."""

    def test_dogen_is_executable_with_a_python3_shebang(self):
        self.assertTrue(os.access(str(DOGEN_PATH), os.X_OK), "dogen must be executable")
        first = DOGEN_PATH.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, "#!/usr/bin/env python3")

    def test_dogen_parses_as_python_39(self):
        ast.parse(DOGEN_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_dogen_declares_future_annotations(self):
        self.assertIn(
            "from __future__ import annotations",
            DOGEN_PATH.read_text(encoding="utf-8"),
        )

    def test_importing_dogen_runs_no_verb_and_prints_nothing(self):
        code = (
            "import importlib.machinery, importlib.util\n"
            "loader = importlib.machinery.SourceFileLoader('dogen', %r)\n"
            "spec = importlib.util.spec_from_loader('dogen', loader)\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "loader.exec_module(module)\n" % str(DOGEN_PATH)
        )
        proc = subprocess.run(
            [sys.executable, "-I", "-c", code], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    def test_core_symbols_are_exposed(self):
        for name in (
            "canonical_line",
            "chain_prev",
            "verify_chain",
            "read_events",
            "append_batch",
            "ledger_path",
            "utc_now",
            "sha256_bytes",
            "sha256_file",
            "collapse_note",
        ):
            with self.subTest(symbol=name):
                self.assertTrue(hasattr(dogen, name), "missing %s" % name)

    def test_the_refusal_surface_exists_now_that_the_contract_is_tagged(self):
        """D-06, post-tag: the gate surface the tag released is present.

        Before ``contract-v1`` this assertion ran inverted — no symbol that
        refuses or writes was allowed to exist. The tag is the event that
        flipped it, and the assertion is kept rather than deleted so the file
        still records that the boundary was real.
        """
        for name in ("refuse", "respond", "REASONS", "EXITS", "Refusal", "route"):
            with self.subTest(symbol=name):
                self.assertTrue(
                    hasattr(dogen, name),
                    "%s is gate code released by the contract-v1 tag" % name,
                )


class TestCanonicalLine(unittest.TestCase):
    """U-01 — the serializer contract section 5.2 names, byte for byte."""

    def test_free_text_round_trips_verbatim(self):
        event = make_event(note="has | pipe\nand newline\ttab, plus café — em")
        line = dogen.canonical_line(event)
        self.assertNotIn("\n", line, "a line must never contain a raw newline")
        self.assertEqual(json.loads(line), event)

    def test_non_ascii_is_written_as_raw_utf8(self):
        line = dogen.canonical_line(make_event(note="café — em"))
        self.assertIn("café — em", line)
        self.assertNotIn("\\u", line)

    def test_key_order_is_independent_of_insertion_order(self):
        forwards = {"a": 1, "b": 2, "c": {"x": 1, "y": 2}}
        backwards = {"c": {"y": 2, "x": 1}, "b": 2, "a": 1}
        self.assertEqual(
            dogen.canonical_line(forwards), dogen.canonical_line(backwards)
        )

    def test_separators_carry_no_whitespace(self):
        self.assertEqual(dogen.canonical_line({"a": 1, "b": [1, 2]}), '{"a":1,"b":[1,2]}')

    def test_finite_float_is_refused(self):
        """A finite float is banned: ``allow_nan=False`` alone permits it (P-6)."""
        with self.assertRaises(ValueError):
            dogen.canonical_line({"x": 1.5})

    def test_nan_is_refused(self):
        with self.assertRaises(ValueError):
            dogen.canonical_line({"x": float("nan")})

    def test_nested_float_is_refused(self):
        with self.assertRaises(ValueError):
            dogen.canonical_line({"files": [{"path": "a.md", "bytes": 1.0}]})

    def test_bool_and_int_are_not_mistaken_for_floats(self):
        line = dogen.canonical_line({"flag": True, "count": 3})
        self.assertEqual(json.loads(line), {"flag": True, "count": 3})


class TestChain(unittest.TestCase):
    """U-02 — ``prev`` is sha256 of the previous line's exact bytes, no LF."""

    def test_chain_prev_hashes_the_exact_bytes_without_the_lf(self):
        line = dogen.canonical_line(make_event(note="first"))
        expected = hashlib.sha256(line.encode("utf-8")).hexdigest()
        self.assertEqual(dogen.chain_prev(line), expected)

    def test_appending_the_lf_changes_the_digest(self):
        line = dogen.canonical_line(make_event(note="first"))
        self.assertNotEqual(dogen.chain_prev(line), dogen.chain_prev(line + "\n"))

    def test_first_event_has_seq_zero_and_null_prev(self):
        events, lines = build_chain([{"note": "first"}])
        self.assertEqual(events[0]["seq"], 0)
        self.assertIsNone(events[0]["prev"])
        self.assertEqual(dogen.verify_chain(lines), [])

    def test_three_line_chain_verifies(self):
        _, lines = build_chain([{"note": "a"}, {"note": "b"}, {"note": "c"}])
        self.assertEqual(dogen.verify_chain(lines), [])

    def test_empty_chain_verifies(self):
        """A zero-line ledger is zero events, not an error."""
        self.assertEqual(dogen.verify_chain([]), [])

    def test_seq_gap_is_rejected(self):
        _, lines = build_chain([{"note": "a"}, {"note": "b"}])
        broken = json.loads(lines[1])
        broken["seq"] = 2
        lines[1] = dogen.canonical_line(broken)
        self.assertNotEqual(dogen.verify_chain(lines), [])

    def test_wrong_prev_is_rejected(self):
        _, lines = build_chain([{"note": "a"}, {"note": "b"}])
        broken = json.loads(lines[1])
        broken["prev"] = "0" * 64
        lines[1] = dogen.canonical_line(broken)
        self.assertNotEqual(dogen.verify_chain(lines), [])

    def test_non_null_prev_at_seq_zero_is_rejected(self):
        _, lines = build_chain([{"note": "a"}])
        broken = json.loads(lines[0])
        broken["prev"] = "0" * 64
        self.assertNotEqual(dogen.verify_chain([dogen.canonical_line(broken)]), [])

    def test_adjacent_equal_payloads_never_merge(self):
        """Two events equal on every payload field still differ in ``seq``."""
        _, lines = build_chain([{"note": "same"}, {"note": "same"}])
        self.assertNotEqual(lines[0], lines[1])
        self.assertEqual(dogen.verify_chain(lines), [])


class TestLedgerIO(TempRepoTestCase):
    """U-02 — read/append primitives over a real file in a temp repo."""

    def test_ledger_path_is_under_the_unit_directory(self):
        path = dogen.ledger_path(self.repo, "validate-workshop")
        self.assertEqual(
            str(path),
            os.path.join(
                str(self.repo), ".dogen", "units", "validate-workshop", "ledger.jsonl"
            ),
        )

    def test_read_events_on_a_missing_file_returns_empty(self):
        self.assertEqual(dogen.read_events(self.repo / "nope.jsonl"), [])

    def test_read_events_on_a_zero_byte_file_returns_empty(self):
        path = self.repo / "ledger.jsonl"
        path.write_bytes(b"")
        self.assertEqual(dogen.read_events(path), [])

    def test_append_batch_issues_exactly_one_write_and_round_trips(self):
        events, lines = build_chain([{"note": "first"}, {"note": "second"}])
        path = self.repo / "ledger.jsonl"
        writes = []
        real_open = open

        class _CountingHandle:
            def __init__(self, handle):
                self._handle = handle

            def write(self, text):
                writes.append(text)
                return self._handle.write(text)

            def __enter__(self):
                self._handle.__enter__()
                return self

            def __exit__(self, *exc):
                return self._handle.__exit__(*exc)

            def __getattr__(self, name):
                return getattr(self._handle, name)

        def _counting_open(*args, **kwargs):
            return _CountingHandle(real_open(*args, **kwargs))

        with mock.patch.object(dogen, "open", _counting_open, create=True):
            dogen.append_batch(path, lines)

        self.assertEqual(len(writes), 1, "the batch must be one write() call")
        self.assertEqual(
            path.read_bytes().decode("utf-8"),
            "".join(line + "\n" for line in lines),
        )
        self.assertEqual([event for event, _ in dogen.read_events(path)], events)
        self.assertEqual([raw for _, raw in dogen.read_events(path)], lines)

    def test_append_batch_appends_rather_than_truncating(self):
        _, lines = build_chain([{"note": "a"}, {"note": "b"}, {"note": "c"}])
        path = self.repo / "ledger.jsonl"
        dogen.append_batch(path, lines[:1])
        dogen.append_batch(path, lines[1:])
        self.assertEqual(len(dogen.read_events(path)), 3)
        self.assertEqual(dogen.verify_chain([raw for _, raw in dogen.read_events(path)]), [])

    def test_single_line_ledger_verifies(self):
        _, lines = build_chain([{"note": "only"}])
        path = self.repo / "ledger.jsonl"
        dogen.append_batch(path, lines)
        self.assertEqual(dogen.verify_chain([raw for _, raw in dogen.read_events(path)]), [])


class TestCaps(unittest.TestCase):
    """U-03 (caps slice) — every cap is inclusive and measured in UTF-8 bytes."""

    def test_byte_caps_are_inclusive(self):
        cases = (
            ("note", dogen.MAX_NOTE_BYTES),
            ("steps", dogen.MAX_STEPS_BYTES),
            ("excerpt", dogen.MAX_EXCERPT_BYTES),
        )
        for name, limit in cases:
            with self.subTest(cap=name):
                at_cap = "a" * limit
                self.assertEqual(dogen.check_byte_cap(name, at_cap, limit), at_cap)
                with self.assertRaises(ValueError):
                    dogen.check_byte_cap(name, "a" * (limit + 1), limit)

    def test_byte_caps_measure_bytes_not_characters(self):
        """65536 two-byte characters exceed a 65536-byte cap."""
        text = "é" * dogen.MAX_NOTE_BYTES
        with self.assertRaises(ValueError):
            dogen.check_byte_cap("note", text, dogen.MAX_NOTE_BYTES)

    def test_count_caps_are_inclusive(self):
        cases = (("files", dogen.MAX_FILES), ("origins", dogen.MAX_ORIGINS))
        for name, limit in cases:
            with self.subTest(cap=name):
                at_cap = ["x"] * limit
                self.assertEqual(dogen.check_count_cap(name, at_cap, limit), at_cap)
                with self.assertRaises(ValueError):
                    dogen.check_count_cap(name, ["x"] * (limit + 1), limit)

    def test_canonical_line_enforces_the_line_cap_inclusively(self):
        base = make_event(note="")
        overhead = len(dogen.canonical_line(base).encode("utf-8"))
        padding = dogen.MAX_LINE_BYTES - overhead
        at_cap = dict(base, note="a" * padding)
        self.assertEqual(
            len(dogen.canonical_line(at_cap).encode("utf-8")), dogen.MAX_LINE_BYTES
        )
        with self.assertRaises(ValueError):
            dogen.canonical_line(dict(base, note="a" * (padding + 1)))

    def test_cap_constants_match_the_contract(self):
        self.assertEqual(dogen.MAX_LINE_BYTES, 262144)
        self.assertEqual(dogen.MAX_NOTE_BYTES, 65536)
        self.assertEqual(dogen.MAX_STEPS_BYTES, 65536)
        self.assertEqual(dogen.MAX_EXCERPT_BYTES, 4096)
        self.assertEqual(dogen.MAX_FILES, 64)
        self.assertEqual(dogen.MAX_ORIGINS, 500)


class TestHelpers(TempRepoTestCase):
    """U-01/U-02 support: digests, the ``DOGEN_NOW`` override, note collapsing."""

    def test_sha256_bytes_matches_hashlib(self):
        self.assertEqual(
            dogen.sha256_bytes(b"abc"), hashlib.sha256(b"abc").hexdigest()
        )

    def test_sha256_file_returns_none_for_a_missing_path(self):
        self.assertIsNone(dogen.sha256_file(self.repo / "nope.md"))

    def test_sha256_file_returns_empty_string_for_a_zero_byte_file(self):
        path = self.repo / "empty.md"
        path.write_bytes(b"")
        self.assertEqual(dogen.sha256_file(path), "")

    def test_sha256_file_digests_content(self):
        path = self.repo / "page.md"
        path.write_bytes(b"hello\n")
        self.assertEqual(dogen.sha256_file(path), hashlib.sha256(b"hello\n").hexdigest())

    def test_dogen_now_is_returned_verbatim(self):
        with mock.patch.dict(
            os.environ,
            {"DOGEN_NOW": "2026-01-01T00:00:00+00:00", "DOGEN_TEST_HOOKS": "1"},
        ):
            self.assertEqual(dogen.utc_now(), "2026-01-01T00:00:00+00:00")

    def test_utc_now_without_the_override_is_an_iso_utc_stamp(self):
        env = dict(os.environ)
        env.pop("DOGEN_NOW", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertRegex(
                dogen.utc_now(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$"
            )

    def test_dogen_now_is_inert_without_the_test_hook_switch(self):
        # WR-07: an always-live env hook let an environment variable dictate the
        # timestamps of a committed audit record. Both hooks now need
        # DOGEN_TEST_HOOKS=1, so the shipped executable ignores a stray
        # DOGEN_NOW in a developer's shell.
        env = dict(os.environ)
        env.pop("DOGEN_TEST_HOOKS", None)
        env["DOGEN_NOW"] = "1999-12-31T23:59:59+00:00"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertNotEqual(dogen.utc_now(), "1999-12-31T23:59:59+00:00")
            self.assertRegex(
                dogen.utc_now(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$"
            )

    def test_crash_point_is_inert_without_the_test_hook_switch(self):
        env = dict(os.environ)
        env.pop("DOGEN_TEST_HOOKS", None)
        env["DOGEN_CRASH_AT"] = "manifest"
        with mock.patch.dict(os.environ, env, clear=True):
            # os._exit would take the test runner down with it; reaching the
            # next statement IS the assertion.
            dogen.crash_point("manifest")
            self.assertFalse(dogen.test_hooks_enabled())

    def test_collapse_note_flattens_whitespace_and_caps_length(self):
        self.assertEqual(dogen.collapse_note("a\n\n  b\tc  "), "a b c")
        self.assertLessEqual(len(dogen.collapse_note("x " * 500)), 400)


UNIT_EXAMPLE = """---
title: "Validate a workshop definition"
intent: how-to
audience: "Workshop maintainers who edit workshop.yaml"
targets:
  - "how-to/validate-workshop-definition.rst"
sources:
  - "workshop/schema.json"
notes: "Steps must run offline."
---
# Validate a workshop definition

The plan outline, free Markdown.
"""

UNIT_EXAMPLE_BODY = (
    "# Validate a workshop definition\n\nThe plan outline, free Markdown.\n"
)

# (source, 1-based line the error names, the flag that fixes it).
# A new validation rule is one row here, not one method.
UNIT_INVALID_CASES = (
    (
        "missing_title",
        '---\nintent: how-to\naudience: "A"\ntargets:\n  - "a.rst"\n---\nbody\n',
        6,
        "--title",
    ),
    (
        "missing_intent",
        '---\ntitle: "T"\naudience: "A"\ntargets:\n  - "a.rst"\n---\nbody\n',
        6,
        "--intent",
    ),
    (
        "missing_audience",
        '---\ntitle: "T"\nintent: how-to\ntargets:\n  - "a.rst"\n---\nbody\n',
        6,
        "--audience",
    ),
    (
        "missing_targets",
        '---\ntitle: "T"\nintent: how-to\naudience: "A"\n---\nbody\n',
        5,
        "--target / --also-target",
    ),
    (
        "empty_targets_list",
        '---\ntitle: "T"\nintent: how-to\naudience: "A"\ntargets:\n---\nbody\n',
        5,
        "--target / --also-target",
    ),
    (
        "bad_intent",
        '---\ntitle: "T"\nintent: tutorial-ish\naudience: "A"\ntargets:\n  - "a.rst"\n---\n',
        3,
        "--intent",
    ),
    (
        "bare_scalar_with_colon_space",
        '---\ntitle: Validate: a workshop\nintent: how-to\naudience: "A"\ntargets:\n  - "a.rst"\n---\n',
        2,
        "--title",
    ),
    (
        "bare_scalar_with_hash",
        '---\ntitle: Validate # not a comment\nintent: how-to\naudience: "A"\ntargets:\n  - "a.rst"\n---\n',
        2,
        "--title",
    ),
    (
        "bare_scalar_leading_bracket",
        '---\ntitle: "T"\nintent: how-to\naudience: [not, a, list]\ntargets:\n  - "a.rst"\n---\n',
        4,
        "--audience",
    ),
    (
        "bare_scalar_leading_brace",
        '---\ntitle: "T"\nintent: how-to\naudience: "A"\ntargets:\n  - "a.rst"\nnotes: {a: b}\n---\n',
        7,
        "--notes",
    ),
    (
        "bare_scalar_leading_single_quote",
        "---\ntitle: 'T'\nintent: how-to\naudience: \"A\"\ntargets:\n  - \"a.rst\"\n---\n",
        2,
        "--title",
    ),
    (
        "unterminated_json_scalar",
        '---\ntitle: "T\nintent: how-to\naudience: "A"\ntargets:\n  - "a.rst"\n---\n',
        2,
        "--title",
    ),
    (
        "empty_bare_scalar",
        '---\ntitle:\nintent: how-to\naudience: "A"\ntargets:\n  - "a.rst"\n---\n',
        2,
        "--title",
    ),
    (
        "list_item_under_a_scalar_key",
        '---\ntitle: "T"\n  - "not mine"\nintent: how-to\naudience: "A"\ntargets:\n  - "a.rst"\n---\n',
        3,
        "--title",
    ),
    (
        "list_item_in_a_target_list_is_not_a_scalar",
        '---\ntitle: "T"\nintent: how-to\naudience: "A"\ntargets:\n  - [a, b]\n---\n',
        6,
        "--target / --also-target",
    ),
)


class TestFrontmatterSubset(unittest.TestCase):
    """U-04 — the contract section 5.6 subset, hand-written on purpose.

    No YAML parser is used: the subset is deliberately narrower than YAML and a
    real parser would accept inputs the contract must refuse.
    """

    def test_the_contract_example_parses(self):
        frontmatter, body = dogen.parse_unit_md(UNIT_EXAMPLE)
        self.assertEqual(
            set(frontmatter),
            {"title", "intent", "audience", "targets", "sources", "notes"},
        )
        self.assertEqual(frontmatter["title"], "Validate a workshop definition")
        self.assertEqual(frontmatter["intent"], "how-to")
        self.assertEqual(
            frontmatter["audience"], "Workshop maintainers who edit workshop.yaml"
        )
        self.assertEqual(
            frontmatter["targets"], ["how-to/validate-workshop-definition.rst"]
        )
        self.assertEqual(frontmatter["sources"], ["workshop/schema.json"])
        self.assertEqual(frontmatter["notes"], "Steps must run offline.")

    def test_the_body_is_returned_verbatim_after_the_closing_delimiter(self):
        _, body = dogen.parse_unit_md(UNIT_EXAMPLE)
        self.assertEqual(body, UNIT_EXAMPLE_BODY)

    def test_every_intent_is_accepted(self):
        for intent in ("tutorial", "how-to", "reference", "explanation"):
            with self.subTest(intent=intent):
                text = (
                    '---\ntitle: "T"\nintent: %s\naudience: "A"\n'
                    'targets:\n  - "a.rst"\n---\n' % intent
                )
                frontmatter, _ = dogen.parse_unit_md(text)
                self.assertEqual(frontmatter["intent"], intent)

    def test_bare_scalars_are_accepted(self):
        text = (
            "---\ntitle: Validate a workshop definition\nintent: how-to\n"
            'audience: Workshop maintainers\ntargets:\n  - "a.rst"\n---\n'
        )
        frontmatter, _ = dogen.parse_unit_md(text)
        self.assertEqual(frontmatter["title"], "Validate a workshop definition")
        self.assertEqual(frontmatter["audience"], "Workshop maintainers")

    def test_invalid_frontmatter_names_its_line_and_flag(self):
        for name, text, line, flag in UNIT_INVALID_CASES:
            with self.subTest(case=name):
                with self.assertRaises(dogen.UnitInvalid) as caught:
                    dogen.parse_unit_md(text)
                self.assertEqual(caught.exception.line, line)
                self.assertEqual(caught.exception.flag, flag)

    def test_a_list_item_binds_to_the_nearest_preceding_key(self):
        text = (
            '---\ntitle: "T"\nintent: how-to\naudience: "A"\n'
            'sources:\n  - "s1"\ntargets:\n  - "t1"\n---\n'
        )
        frontmatter, _ = dogen.parse_unit_md(text)
        self.assertEqual(frontmatter["sources"], ["s1"])
        self.assertEqual(frontmatter["targets"], ["t1"])

    def test_adjacent_key_lines_parse_independently(self):
        text = (
            '---\ntitle: "T"\nintent: reference\naudience: "A"\n'
            'notes: "N"\ntargets:\n  - "a.rst"\n---\n'
        )
        frontmatter, _ = dogen.parse_unit_md(text)
        self.assertEqual(frontmatter["title"], "T")
        self.assertEqual(frontmatter["notes"], "N")

    def test_an_orphan_list_item_is_refused(self):
        text = '---\n  - "orphan"\ntitle: "T"\n---\n'
        with self.assertRaises(dogen.UnitInvalid) as caught:
            dogen.parse_unit_md(text)
        self.assertEqual(caught.exception.line, 2)

    def test_target_order_is_preserved_verbatim(self):
        text = (
            '---\ntitle: "T"\nintent: reference\naudience: "A"\n'
            'targets:\n  - "z.rst"\n  - "a.rst"\n  - "m.rst"\n---\n'
        )
        frontmatter, _ = dogen.parse_unit_md(text)
        self.assertEqual(frontmatter["targets"], ["z.rst", "a.rst", "m.rst"])

    def test_top_level_key_order_is_not_significant(self):
        shuffled = (
            '---\ntargets:\n  - "a.rst"\naudience: "A"\nintent: reference\n'
            'title: "T"\n---\nbody\n'
        )
        straight = (
            '---\ntitle: "T"\nintent: reference\naudience: "A"\n'
            'targets:\n  - "a.rst"\n---\nbody\n'
        )
        self.assertEqual(
            dogen.parse_unit_md(shuffled)[0], dogen.parse_unit_md(straight)[0]
        )

    def test_an_empty_string_scalar_is_a_present_value(self):
        text = (
            '---\ntitle: "T"\nintent: reference\naudience: "A"\n'
            'targets:\n  - "a.rst"\nnotes: ""\n---\n'
        )
        frontmatter, _ = dogen.parse_unit_md(text)
        self.assertIn("notes", frontmatter)
        self.assertEqual(frontmatter["notes"], "")

    def test_a_missing_frontmatter_block_is_refused(self):
        with self.assertRaises(dogen.UnitInvalid):
            dogen.parse_unit_md("# just a body\n")

    def test_an_unclosed_frontmatter_block_is_refused(self):
        with self.assertRaises(dogen.UnitInvalid):
            dogen.parse_unit_md('---\ntitle: "T"\n')

    def test_an_unknown_key_is_refused(self):
        text = (
            '---\ntitle: "T"\nintent: reference\naudience: "A"\n'
            'targets:\n  - "a.rst"\nunit_id: legacy\n---\n'
        )
        with self.assertRaises(dogen.UnitInvalid) as caught:
            dogen.parse_unit_md(text)
        self.assertEqual(caught.exception.line, 7)

    def test_a_duplicate_key_is_refused(self):
        text = (
            '---\ntitle: "T"\ntitle: "T2"\nintent: reference\naudience: "A"\n'
            'targets:\n  - "a.rst"\n---\n'
        )
        with self.assertRaises(dogen.UnitInvalid) as caught:
            dogen.parse_unit_md(text)
        self.assertEqual(caught.exception.line, 3)

    def test_render_round_trips_through_parse(self):
        frontmatter, body = dogen.parse_unit_md(UNIT_EXAMPLE)
        rendered = dogen.render_unit_md(frontmatter, body)
        reparsed, reparsed_body = dogen.parse_unit_md(rendered)
        self.assertEqual(reparsed, frontmatter)
        self.assertEqual(reparsed_body, body)
        self.assertEqual(dogen.render_unit_md(reparsed, reparsed_body), rendered)

    def test_render_writes_the_canonical_shape(self):
        frontmatter = {
            "title": "T",
            "intent": "reference",
            "audience": "A",
            "targets": ["a.rst", "b.rst"],
        }
        rendered = dogen.render_unit_md(frontmatter, "body\n")
        self.assertTrue(rendered.startswith("---\n"))
        self.assertIn('targets:\n  - "a.rst"\n  - "b.rst"\n', rendered)
        self.assertTrue(rendered.endswith("---\nbody\n"))


class TestCleanText(unittest.TestCase):
    """U-03 (notes) — free text is sanitised, never reinterpreted as a field."""

    def test_pipe_newline_and_tab_survive_verbatim(self):
        text = "has | pipe\nand newline\ttab"
        self.assertEqual(dogen.clean_text(text), text)

    def test_carriage_return_is_refused(self):
        with self.assertRaises(ValueError):
            dogen.clean_text("a\rb")

    def test_other_c0_controls_are_stripped(self):
        self.assertEqual(dogen.clean_text("a\x07b\x00c"), "abc")

    def test_empty_input_is_refused(self):
        with self.assertRaises(ValueError):
            dogen.clean_text("")

    def test_whitespace_only_input_is_refused(self):
        with self.assertRaises(ValueError):
            dogen.clean_text("   ")

    def test_the_note_cap_is_inclusive(self):
        at_cap = "a" * dogen.MAX_NOTE_BYTES
        self.assertEqual(dogen.clean_text(at_cap), at_cap)
        with self.assertRaises(ValueError):
            dogen.clean_text("a" * (dogen.MAX_NOTE_BYTES + 1))

    def test_the_note_cap_counts_bytes_not_characters(self):
        with self.assertRaises(ValueError):
            dogen.clean_text("é" * dogen.MAX_NOTE_BYTES)

    def test_the_cap_is_measured_after_stripping(self):
        text = "a" * dogen.MAX_NOTE_BYTES + "\x07"
        self.assertEqual(dogen.clean_text(text), "a" * dogen.MAX_NOTE_BYTES)

    def test_a_note_cannot_forge_a_ledger_field(self):
        """A pipe-delimited record let free text forge a row; JSON does not."""
        note = dogen.clean_text("| verdict: accept |")
        event = make_event(kind="review", note=note)
        parsed = json.loads(dogen.canonical_line(event))
        self.assertEqual(parsed["note"], "| verdict: accept |")
        self.assertNotIn("verdict", parsed)


class TestExcerptScrub(unittest.TestCase):
    """U-03 (LEDG-06, D-02) — the digest is over the RAW bytes; the excerpt is
    stripped and cut, and stripping and truncation are exercised TOGETHER.

    D-02's only honest claim is that control characters are stripped. Nothing
    here asserts the excerpt is redacted or free of secrets, because the tool
    cannot back that claim and saying it would be false provenance.
    """

    @staticmethod
    def _colourised_payload():
        """Over 4 KiB, with real CSI colour, a real OSC, non-ASCII and ``\\r``."""
        chunk = (
            "\x1b[1;32mPASS\x1b[0m café — naïve \x1b]0;window-title\x07"
            "downloading\r 50%\r100%\tcolumn\n"
        )
        return (chunk * 200).encode("utf-8")

    def test_stripping_and_truncation_happen_together(self):
        raw = self._colourised_payload()
        self.assertGreater(len(raw), dogen.MAX_EXCERPT_BYTES)
        digest, excerpt = dogen.scrub_excerpt(raw)
        # 1. the digest is over the raw full bytes, computed independently here
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        # 2. the cap is bytes, and the marker lives INSIDE it (Pitfall 4.3)
        self.assertLessEqual(len(excerpt.encode("utf-8")), 4096)
        self.assertLessEqual(len(excerpt.encode("utf-8")), dogen.MAX_EXCERPT_BYTES)
        # 3. no C0 control below 32 survives except newline and tab
        self.assertEqual(
            [c for c in excerpt if ord(c) < 32 and c not in ("\n", "\t")], []
        )
        # 4. Pitfall 3: dropping C0 first would remove only the ESC and leave
        #    the bracket-and-parameter text behind in the committed excerpt.
        self.assertNotRegex(excerpt, r"\[[0-9;?]*[mK]")
        self.assertNotIn("window-title", excerpt)
        self.assertIn("café", excerpt)

    def test_a_carriage_return_is_stripped_rather_than_refused(self):
        """The author free-text rule refuses ``\\r``; captured output is not that."""
        digest, excerpt = dogen.scrub_excerpt(b"a\rb")
        self.assertEqual(excerpt, "ab")
        self.assertEqual(digest, hashlib.sha256(b"a\rb").hexdigest())

    def test_invalid_utf8_is_replaced_and_the_digest_is_still_over_raw_bytes(self):
        raw = b"before \xff\xfe after"
        digest, excerpt = dogen.scrub_excerpt(raw)
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        self.assertIn("�", excerpt)
        # Reproducible from the file, not from the excerpt: decoding is lossy.
        self.assertNotEqual(excerpt.encode("utf-8"), raw)

    def test_a_multibyte_character_straddling_the_cut_is_dropped_not_split(self):
        raw = ("é" * 4000).encode("utf-8")
        digest, excerpt = dogen.scrub_excerpt(raw)
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        encoded = excerpt.encode("utf-8")
        self.assertLessEqual(len(encoded), dogen.MAX_EXCERPT_BYTES)
        self.assertEqual(encoded.decode("utf-8"), excerpt)
        self.assertNotIn("�", excerpt)

    def test_exactly_the_cap_of_plain_ascii_is_returned_unchanged(self):
        raw = b"a" * dogen.MAX_EXCERPT_BYTES
        digest, excerpt = dogen.scrub_excerpt(raw)
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        self.assertEqual(excerpt, "a" * dogen.MAX_EXCERPT_BYTES)
        self.assertNotIn("…", excerpt)

    def test_one_byte_past_the_cap_is_marked_and_still_fits(self):
        raw = b"a" * (dogen.MAX_EXCERPT_BYTES + 1)
        _, excerpt = dogen.scrub_excerpt(raw)
        self.assertIn("…", excerpt)
        self.assertLessEqual(len(excerpt.encode("utf-8")), dogen.MAX_EXCERPT_BYTES)

    def test_the_marker_reports_the_raw_byte_count(self):
        """The only figure the digest corroborates is the RAW byte count."""
        raw = self._colourised_payload()
        _, excerpt = dogen.scrub_excerpt(raw)
        self.assertTrue(
            excerpt.endswith("… (%d bytes total)" % len(raw)),
            "the marker names the raw byte count; got %r" % excerpt[-40:],
        )

    def test_zero_bytes_in_is_the_empty_digest_and_an_empty_excerpt(self):
        digest, excerpt = dogen.scrub_excerpt(b"")
        self.assertEqual(digest, hashlib.sha256(b"").hexdigest())
        self.assertEqual(excerpt, "")


AT = "2026-01-01T00:00:00+00:00"
#: A stand-in captured-output digest. Contract 5.4 resolves a `pass` only
#: WITH one, so a fixture that omits it is asserting the wrong thing.
STEP_DIGEST = hashlib.sha256(b"captured").hexdigest()
ACTOR = {"name": "Test Author", "email": "test@example.com"}


def ev(kind, seq, **payload):
    """A derivation-shaped event. ``prev`` is irrelevant to a pure derive()."""
    event = {
        "kind": kind,
        "seq": seq,
        "prev": None,
        "at": AT,
        "actor": ACTOR,
        "tool_version": "0.2.0",
        "contract": 1,
        "commit": "0" * 40,
    }
    event.update(payload)
    return event


def signoff(seq, targets, plan_hash="P1", intent="reference"):
    return ev(
        "signoff",
        seq,
        plan_hash=plan_hash,
        intent=intent,
        audience="A",
        title="T",
        targets=list(targets),
        sources=[],
        context={},
        supersedes=None,
    )


def generation(seq, files, signoff_seq, plan_hash="P1", basis_seq=None, steps_seq=None):
    event = ev(
        "generation",
        seq,
        files=[{"path": p, "sha256": h, "bytes": 1} for p, h in files],
        signoff_seq=signoff_seq,
        plan_hash=plan_hash,
        model="m",
        model_origin="config",
        basis_seq=basis_seq,
        unsteered=False,
    )
    if steps_seq is not None:
        event["steps_seq"] = steps_seq
    return event


def reviewer_edit(seq, files, generation_seq=None, note="hand edit"):
    return ev(
        "reviewer-edit",
        seq,
        files=[{"path": p, "sha256": h, "bytes": 1} for p, h in files],
        generation_seq=generation_seq,
        note=note,
    )


def review(seq, verdict, generation_seq, resolves=None, withdraws=None, note="n"):
    event = ev("review", seq, verdict=verdict, generation_seq=generation_seq, note=note)
    if verdict == "accept":
        event["basis_seq"] = generation_seq
        event["files"] = []
        event["resolves"] = list(resolves or [])
        event["withdraws"] = list(withdraws or [])
    return event


def steering(seq, note="S", origin="manual"):
    return ev("steering", seq, note=note, origin=origin)


def opening(unit="u"):
    """The two events every unit opens with: ``ledger`` then ``unit-declared``."""
    return [
        ev("ledger", 0, v=1, unit=unit, docs_root="docs"),
        ev("unit-declared", 1, unit_hash="U1", frontmatter={}),
    ]


def fs_of(unit_md_sha, **paths):
    return {"unit_md_sha": unit_md_sha, "paths": dict(paths)}


# One row per contract 5.11 trace this plan implements: (trace id, events, fs,
# staging or None, expected subset of derive()'s result). Plan 16-03 adds the
# `next` token column to this same table.
DERIVE_TRACES = (
    (
        "T3",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            steering(4),
            generation(5, [("a.rst", "H2")], signoff_seq=2),
            review(6, "accept", generation_seq=5),
        ],
        fs_of("P1", **{"a.rst": "H2"}),
        None,
        {
            "state": "sealed",
            "pending": [],
            "generation_stale": False,
            "plan_stale": False,
            "next": "publish",
        },
    ),
    (
        "T4",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            review(4, "accept", generation_seq=3),
            steering(5),
        ],
        fs_of("P1", **{"a.rst": "H1"}),
        None,
        {"state": "reviewed", "pending": [5], "next": "draft"},
    ),
    (
        "T5",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            steering(4),
        ],
        fs_of("P1", **{"a.rst": "H2"}),
        None,
        {
            "state": "drafted",
            "page_drift": True,
            "drifted_paths": ["a.rst"],
            "pending": [4],
            "next": "record_edits",
        },
    ),
    (
        "T6",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            reviewer_edit(4, [("a.rst", "H2")], generation_seq=3),
        ],
        fs_of("P1", **{"a.rst": "H2"}),
        None,
        {
            "state": "drafted",
            "basis_seq": 4,
            "page_drift": False,
            "pending": [],
            "steered_since_gen": False,
            "next": "review",
        },
    ),
    (
        "T7",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            reviewer_edit(4, [("a.rst", "H2")], generation_seq=3),
            steering(5),
        ],
        fs_of("P1", **{"a.rst": "H2"}),
        None,
        {"basis_seq": 4, "pending": [5], "steered_since_gen": True, "page_drift": False, "next": "review"},
    ),
    (
        "T8",
        opening()
        + [
            signoff(2, ["a.rst"], plan_hash="P1"),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            signoff(4, ["a.rst"], plan_hash="P2"),
        ],
        fs_of("P2", **{"a.rst": "H1"}),
        None,
        {"state": "drafted", "generation_stale": True, "plan_stale": False, "pending": [], "next": "draft"},
    ),
    (
        "T9b",
        opening()
        + [
            signoff(2, ["a.rst"], plan_hash="P1"),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            signoff(4, ["a.rst"], plan_hash="P2"),
        ],
        fs_of("P2", **{"a.rst": "H2"}),
        None,
        {"generation_stale": True, "page_drift": True, "drifted_paths": ["a.rst"], "next": "record_edits"},
    ),
    (
        "T11",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
        ],
        fs_of("P1", **{"a.rst": "H1"}),
        {"steps_seq": None, "files": {"a.rst": "H1"}},
        {
            "state": "drafted",
            "identical_draft": {
                "generation_exists": True,
                "signoff_current": True,
                "steps_match": True,
                "no_h_since_generation": True,
                "targets_match_staging": True,
                "all": True,
            },
            "next": "review",
        },
    ),
    (
        "T11b",
        opening()
        + [
            signoff(2, ["a.rst", "b.rst"]),
            generation(3, [("a.rst", "H1"), ("b.rst", "H2")], signoff_seq=2),
        ],
        fs_of("P1", **{"a.rst": "H1", "b.rst": None}),
        {"steps_seq": None, "files": {"a.rst": "H1", "b.rst": "H2"}},
        {
            "page_missing": True,
            "missing_paths": ["b.rst"],
            "identical_draft": {
                "generation_exists": True,
                "signoff_current": True,
                "steps_match": True,
                "no_h_since_generation": True,
                "targets_match_staging": False,
                "all": False,
            },
            "next": "review",
        },
    ),
    (
        "T24",
        opening() + [signoff(2, ["a.rst"])],
        fs_of("P1", **{"a.rst": "HB"}),
        None,
        {
            "state": "signed-off",
            "basis_seq": None,
            "target_exists": True,
            "existing_targets": ["a.rst"],
            "orphans": [],
            "next": "record_edits",
        },
    ),
    (
        "T24-after-edits",
        opening() + [signoff(2, ["a.rst"]), reviewer_edit(3, [("a.rst", "HB")])],
        fs_of("P1", **{"a.rst": "HB"}),
        None,
        {
            "state": "signed-off",
            "basis_seq": 3,
            "basis_files": ["a.rst"],
            "target_exists": False,
            "gen_seq": None,
            "next": "draft",
        },
    ),
    (
        "T24b",
        opening()
        + [signoff(2, ["a.rst", "b.rst"]), reviewer_edit(3, [("a.rst", "HB")])],
        fs_of("P1", **{"a.rst": "HB", "b.rst": None}),
        None,
        {
            "state": "signed-off",
            "basis_files": ["a.rst"],
            "target_exists": False,
            "target_missing": True,
            "missing_targets": ["b.rst"],
            "orphans": [],
            "next": "draft",
        },
    ),
    (
        "T24c",
        opening() + [signoff(2, ["a.rst"]), reviewer_edit(3, [("a.rst", "HB")])],
        fs_of("P1", **{"a.rst": "HB"}),
        None,
        {"page_drift": False, "target_exists": False, "state": "signed-off", "next": "draft"},
    ),
    (
        "T24d",
        opening() + [signoff(2, ["a.rst"]), reviewer_edit(3, [("a.rst", "HB")])],
        fs_of("P1", **{"a.rst": "HB"}),
        {"steps_seq": None, "files": {"a.rst": "HB"}},
        {
            "identical_draft": {
                "generation_exists": False,
                "signoff_current": False,
                "steps_match": True,
                "no_h_since_generation": True,
                "targets_match_staging": True,
                "all": False,
            },
            "next": "draft",
        },
    ),
    (
        "T25",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            ev("mystery-kind", 4, whatever="x"),
            generation(5, [("a.rst", "H2")], signoff_seq=2),
        ],
        fs_of("P1", **{"a.rst": "H2"}),
        None,
        {"state": "drafted", "gen_seq": 5, "pending": [], "next": "review"},
    ),
    (
        "T26",
        opening()
        + [
            signoff(2, ["old.rst"], plan_hash="P1"),
            generation(3, [("old.rst", "H1")], signoff_seq=2),
            signoff(4, ["new.rst"], plan_hash="P2"),
        ],
        fs_of("P2", **{"old.rst": "H1", "new.rst": None}),
        None,
        {
            "page_drift": False,
            "page_missing": False,
            "target_exists": False,
            "orphans": ["old.rst"],
            "generation_stale": True,
            "next": "draft",
        },
    ),
    (
        "T26b",
        opening()
        + [
            signoff(2, ["old.rst"], plan_hash="P1"),
            generation(3, [("old.rst", "H1")], signoff_seq=2),
            signoff(4, ["new.rst"], plan_hash="P2"),
        ],
        fs_of("P2", **{"old.rst": None, "new.rst": "H1"}),
        None,
        {
            "page_drift": False,
            "page_missing": False,
            "target_exists": True,
            "existing_targets": ["new.rst"],
            "orphans": ["old.rst"],
            "next": "record_edits",
        },
    ),
    (
        "T26c",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
        ],
        fs_of("P1", **{"a.rst": None}),
        None,
        {
            "page_drift": False,
            "page_missing": True,
            "target_missing": True,
            "missing_targets": ["a.rst"],
            "next": "review",
        },
    ),
    (
        "T26d",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            review(4, "accept", generation_seq=3),
        ],
        fs_of("P1", **{"a.rst": None}),
        None,
        {
            "state": "sealed",
            "page_missing": True,
            "target_missing": True,
            "pending": [],
            "next": "steer",
        },
    ),
    (
        "T26d-after-steer",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            review(4, "accept", generation_seq=3),
            steering(5, note="restore"),
        ],
        fs_of("P1", **{"a.rst": None}),
        None,
        {"state": "reviewed", "pending": [5], "next": "draft"},
    ),
    (
        "T26e",
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
        ],
        fs_of("P1", **{"a.rst": None}),
        {"steps_seq": None, "files": {"a.rst": "H1"}},
        {
            "page_drift": False,
            "target_exists": False,
            "steered_since_gen": False,
            "identical_draft": {
                "generation_exists": True,
                "signoff_current": True,
                "steps_match": True,
                "no_h_since_generation": True,
                "targets_match_staging": False,
                "all": False,
            },
            "next": "review",
        },
    ),
)


class TestDeriveTraces(unittest.TestCase):
    """U-05 — contract 5.4 derivation, table-driven over the 5.11 traces."""

    def test_traces(self):
        for trace, events, fs, staging, expected in DERIVE_TRACES:
            with self.subTest(trace=trace):
                if staging is None:
                    result = dogen.derive(events, fs)
                else:
                    result = dogen.derive(events, fs, staging)
                for key, value in expected.items():
                    if key == "next":
                        # The `next` column: the token contract 5.5 routes this
                        # very state to, asserted from the same row that fixes
                        # the derivation it is routed from.
                        self.assertEqual(
                            dogen.route(result), value, "%s: next" % trace
                        )
                        continue
                    self.assertEqual(result[key], value, "%s: %s" % (trace, key))


class TestDerive(unittest.TestCase):
    """U-05 — the derivation properties the trace table does not carry."""

    def test_empty_history_derives_a_declared_unit(self):
        result = dogen.derive([], {"unit_md_sha": None, "paths": {}})
        self.assertEqual(result["state"], "declared")
        self.assertEqual(result["orphans"], [])
        self.assertEqual(result["pending"], [])
        self.assertIsNone(result["basis"])
        self.assertEqual(result["targets"], [])

    def test_a_retired_unit_is_retired_whatever_else_happened(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            ev("retired", 4, note="done"),
        ]
        result = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))
        self.assertEqual(result["state"], "retired")
        self.assertTrue(result["retired"])

    def test_plan_stale_compares_unit_md_against_the_signed_plan_hash(self):
        events = opening() + [signoff(2, ["a.rst"])]
        self.assertFalse(dogen.derive(events, fs_of("P1"))["plan_stale"])
        self.assertTrue(dogen.derive(events, fs_of("P9"))["plan_stale"])

    def test_basis_is_the_latest_of_generation_and_reviewer_edit(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            reviewer_edit(3, [("a.rst", "HB")]),
            generation(4, [("a.rst", "H1")], signoff_seq=2),
        ]
        result = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))
        self.assertEqual(result["basis_seq"], 4)
        self.assertEqual(result["tip_seq"], 4)

    def test_tip_also_considers_the_last_review(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            review(4, "fix", generation_seq=3),
        ]
        result = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))
        self.assertEqual(result["basis_seq"], 3)
        self.assertEqual(result["tip_seq"], 4)
        self.assertEqual(result["state"], "reviewed")

    def test_a_resolved_request_leaves_pending(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            steering(4),
            steering(5),
            review(6, "accept", generation_seq=3, resolves=[4]),
        ]
        self.assertEqual(dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))["pending"], [5])

    def test_a_withdrawn_request_leaves_pending(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            steering(4),
            review(5, "accept", generation_seq=3, withdraws=[{"seq": 4, "reason": "moot"}]),
        ]
        self.assertEqual(dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))["pending"], [])

    def test_a_fix_verdict_is_itself_pending(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            review(4, "fix", generation_seq=3),
        ]
        self.assertEqual(dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))["pending"], [4])

    def test_a_signoff_is_an_h_event_but_never_pending(self):
        events = opening() + [
            signoff(2, ["a.rst"], plan_hash="P1"),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            signoff(4, ["a.rst"], plan_hash="P2"),
        ]
        result = dogen.derive(events, fs_of("P2", **{"a.rst": "H1"}))
        self.assertEqual(result["pending"], [])
        self.assertTrue(result["steered_since_gen"])

    def test_h_since_the_generation_is_a_strict_comparison(self):
        """An H event at exactly the generation's seq is not 'since'."""
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(2, [("a.rst", "H1")], signoff_seq=2),
        ]
        result = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))
        self.assertFalse(result["steered_since_gen"])
        self.assertTrue(result["identical_draft"]["no_h_since_generation"])

    def test_steered_since_gen_is_undefined_without_a_generation(self):
        events = opening() + [signoff(2, ["a.rst"]), steering(3)]
        self.assertIsNone(dogen.derive(events, fs_of("P1"))["steered_since_gen"])

    def test_a_zero_byte_target_does_not_count_as_existing(self):
        events = opening() + [signoff(2, ["a.rst"])]
        result = dogen.derive(events, fs_of("P1", **{"a.rst": ""}))
        self.assertFalse(result["target_exists"])

    def test_an_unknown_kind_produces_exactly_one_warning(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            ev("mystery-kind", 3),
            ev("mystery-kind", 4),
        ]
        warnings = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))["warnings"]
        self.assertEqual(len(warnings), 1)
        self.assertIn("mystery-kind", warnings[0])

    def test_no_warning_when_every_kind_is_known(self):
        events = opening() + [signoff(2, ["a.rst"])]
        self.assertEqual(dogen.derive(events, fs_of("P1"))["warnings"], [])

    def test_steps_seq_mismatch_defeats_the_no_op(self):
        events = opening() + [
            signoff(2, ["a.rst"], intent="how-to"),
            generation(3, [("a.rst", "H1")], signoff_seq=2, steps_seq=9),
        ]
        result = dogen.derive(
            events,
            fs_of("P1", **{"a.rst": "H1"}),
            {"steps_seq": 10, "files": {"a.rst": "H1"}},
        )
        self.assertFalse(result["identical_draft"]["steps_match"])
        self.assertFalse(result["identical_draft"]["all"])

    def test_identical_draft_is_unknown_without_staging(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
        ]
        conditions = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))["identical_draft"]
        self.assertIsNone(conditions["targets_match_staging"])
        self.assertFalse(conditions["all"])

    def test_derive_is_pure_and_repeatable(self):
        events = opening() + [
            signoff(2, ["nowhere/on/disk.rst"]),
            generation(3, [("nowhere/on/disk.rst", "H1")], signoff_seq=2),
        ]
        fs = fs_of("P1", **{"nowhere/on/disk.rst": "H2"})
        first = dogen.derive(events, fs)
        second = dogen.derive(events, fs)
        self.assertEqual(first, second)
        self.assertTrue(first["page_drift"])
        self.assertFalse(pathlib.Path("nowhere/on/disk.rst").exists())

    def test_derive_makes_no_io_call(self):
        """D-19: the fs snapshot is the only channel into derive()."""
        tree = ast.parse(DOGEN_PATH.read_text(encoding="utf-8"))
        node = None
        for candidate in ast.walk(tree):
            if isinstance(candidate, ast.FunctionDef) and candidate.name == "derive":
                node = candidate
        self.assertIsNotNone(node, "derive is missing")
        banned = {"open", "run", "check_output", "getenv", "read_text", "read_bytes"}
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                name = getattr(inner.func, "id", None) or getattr(
                    inner.func, "attr", None
                )
                self.assertNotIn(name, banned, "derive calls %s" % name)


class TestIdenticalDraftConditions(unittest.TestCase):
    """U-05 — STATE-05's five conditions, each pinned on its own.

    ``derive`` computes the condition SET; ``draft``'s stage d reads it and never
    re-derives it. Pinning each condition separately is what makes a regression
    name itself: a single ``all`` assertion would say only "the no-op broke".
    """

    BASE = (
        opening()
        + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
        ]
    )
    STAGING = {"steps_seq": None, "files": {"a.rst": "H1"}}

    def conditions(self, events=None, fs=None, staging=None):
        return dogen.derive(
            events if events is not None else list(self.BASE),
            fs if fs is not None else fs_of("P1", **{"a.rst": "H1"}),
            staging if staging is not None else dict(self.STAGING),
        )["identical_draft"]

    def test_all_five_conditions_hold_on_an_identical_retry(self):
        conditions = self.conditions()
        self.assertEqual(
            conditions,
            {
                "generation_exists": True,
                "signoff_current": True,
                "steps_match": True,
                "no_h_since_generation": True,
                "targets_match_staging": True,
                "all": True,
            },
        )

    def test_no_generation_defeats_the_no_op(self):
        events = opening() + [signoff(2, ["a.rst"]), reviewer_edit(3, [("a.rst", "H1")])]
        conditions = self.conditions(events=events)
        self.assertFalse(conditions["generation_exists"])
        self.assertFalse(conditions["all"])

    def test_a_re_signed_plan_defeats_the_no_op(self):
        events = list(self.BASE) + [signoff(4, ["a.rst"], plan_hash="P2")]
        conditions = self.conditions(events=events, fs=fs_of("P2", **{"a.rst": "H1"}))
        self.assertFalse(conditions["signoff_current"])
        self.assertFalse(conditions["all"])

    def test_a_changed_steps_context_defeats_the_no_op(self):
        events = opening() + [
            signoff(2, ["a.rst"], intent="how-to"),
            generation(3, [("a.rst", "H1")], signoff_seq=2, steps_seq=9),
        ]
        conditions = self.conditions(
            events=events, staging={"steps_seq": 11, "files": {"a.rst": "H1"}}
        )
        self.assertFalse(conditions["steps_match"])
        self.assertFalse(conditions["all"])

    def test_an_h_event_since_the_generation_defeats_the_no_op(self):
        events = list(self.BASE) + [steering(4)]
        conditions = self.conditions(events=events)
        self.assertFalse(conditions["no_h_since_generation"])
        self.assertFalse(conditions["all"])

    def test_a_missing_destination_defeats_the_no_op(self):
        """T11b: comparison is against the destination, never a historical basis."""
        conditions = self.conditions(fs=fs_of("P1", **{"a.rst": None}))
        self.assertFalse(conditions["targets_match_staging"])
        self.assertFalse(conditions["all"])

    def test_a_hook_rewritten_destination_defeats_the_no_op(self):
        """The generation's recorded digest still matches; the destination does not."""
        conditions = self.conditions(fs=fs_of("P1", **{"a.rst": "HOOKBYTES"}))
        self.assertFalse(conditions["targets_match_staging"])
        self.assertFalse(conditions["all"])

    def test_one_unwritten_target_of_two_defeats_the_no_op(self):
        events = opening() + [
            signoff(2, ["a.rst", "b.rst"]),
            generation(3, [("a.rst", "H1"), ("b.rst", "H2")], signoff_seq=2),
        ]
        conditions = self.conditions(
            events=events,
            fs=fs_of("P1", **{"a.rst": "H1", "b.rst": None}),
            staging={"steps_seq": None, "files": {"a.rst": "H1", "b.rst": "H2"}},
        )
        self.assertFalse(conditions["targets_match_staging"])
        self.assertFalse(conditions["all"])

    def test_the_steps_condition_is_vacuously_true_for_a_reference_unit(self):
        """RESEARCH Open Questions 5, pinned so phase 17 cannot change it silently.

        A reference or explanation unit never carries a step plan, so both sides
        of the comparison are ``None`` and the condition is satisfied without any
        step machinery existing. J1–J5 and J8 all run through this branch.
        """
        events = opening() + [
            signoff(2, ["a.rst"], intent="reference"),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
        ]
        self.assertNotIn("steps_seq", events[-1])
        conditions = self.conditions(
            events=events, staging={"steps_seq": None, "files": {"a.rst": "H1"}}
        )
        self.assertTrue(conditions["steps_match"])
        self.assertTrue(conditions["all"])

    def test_the_condition_set_is_never_asserted_without_a_staging_view(self):
        conditions = dogen.derive(list(self.BASE), fs_of("P1", **{"a.rst": "H1"}))[
            "identical_draft"
        ]
        self.assertIsNone(conditions["steps_match"])
        self.assertIsNone(conditions["targets_match_staging"])
        self.assertFalse(conditions["all"])


class TestCompleteBasisSet(unittest.TestCase):
    """U-05 — VERB-05's complete basis set, pure over one fs snapshot.

    The event is never a delta: every path of the previous basis survives with
    its recorded digest unless its bytes changed, adopted targets join, and the
    ONLY path that is dropped is one that is both missing from disk and no
    longer a signed target.
    """

    def entries(self, pairs):
        return [{"path": path, "sha256": digest} for path, digest in pairs]

    def test_an_unchanged_basis_path_keeps_its_recorded_digest(self):
        result = dogen.complete_basis_set(
            self.entries([("a.rst", "H1")]), ["a.rst"], {"a.rst": "H1"}
        )
        self.assertEqual(result, [{"path": "a.rst", "sha256": "H1"}])

    def test_a_changed_basis_path_takes_the_disk_digest(self):
        result = dogen.complete_basis_set(
            self.entries([("a.rst", "H1")]), ["a.rst"], {"a.rst": "H2"}
        )
        self.assertEqual(result, [{"path": "a.rst", "sha256": "H2"}])

    def test_the_set_is_complete_not_a_delta(self):
        result = dogen.complete_basis_set(
            self.entries([("a.rst", "H1"), ("b.rst", "H2")]),
            ["a.rst", "b.rst"],
            {"a.rst": "EDITED", "b.rst": "H2"},
        )
        self.assertEqual(
            result,
            [
                {"path": "a.rst", "sha256": "EDITED"},
                {"path": "b.rst", "sha256": "H2"},
            ],
        )

    def test_a_missing_but_still_signed_path_keeps_its_last_recorded_digest(self):
        """No placeholder file, no fabricated digest — the historical basis stands."""
        result = dogen.complete_basis_set(
            self.entries([("a.rst", "H1")]), ["a.rst"], {"a.rst": None}
        )
        self.assertEqual(result, [{"path": "a.rst", "sha256": "H1"}])

    def test_only_a_missing_and_unsigned_path_is_dropped(self):
        result = dogen.complete_basis_set(
            self.entries([("old.rst", "H1")]), ["new.rst"], {"old.rst": None, "new.rst": "H1"}
        )
        self.assertEqual(result, [{"path": "new.rst", "sha256": "H1"}])

    def test_a_present_but_unsigned_path_is_kept(self):
        """The tool never deletes a page, and an orphan stays in the basis."""
        result = dogen.complete_basis_set(
            self.entries([("old.rst", "H1")]), ["new.rst"], {"old.rst": "H1", "new.rst": "HB"}
        )
        self.assertEqual(
            result,
            [{"path": "new.rst", "sha256": "HB"}, {"path": "old.rst", "sha256": "H1"}],
        )

    def test_a_non_empty_unadopted_target_joins_the_basis(self):
        result = dogen.complete_basis_set([], ["a.rst"], {"a.rst": "HB"})
        self.assertEqual(result, [{"path": "a.rst", "sha256": "HB"}])

    def test_a_basis_path_truncated_to_zero_bytes_is_a_change(self):
        """Read exactly as ``page_drift`` reads it, so the drift always clears."""
        result = dogen.complete_basis_set(
            self.entries([("a.rst", "H1")]), ["a.rst"], {"a.rst": ""}
        )
        self.assertEqual(result, [{"path": "a.rst", "sha256": ""}])

    def test_a_zero_byte_target_is_not_adoptable(self):
        self.assertEqual(dogen.complete_basis_set([], ["a.rst"], {"a.rst": ""}), [])

    def test_an_absent_target_is_not_adoptable(self):
        self.assertEqual(dogen.complete_basis_set([], ["a.rst"], {"a.rst": None}), [])

    def test_order_is_the_signed_target_order_then_unsigned_basis_order(self):
        result = dogen.complete_basis_set(
            self.entries([("z.rst", "H1"), ("a.rst", "H2")]),
            ["a.rst", "m.rst"],
            {"a.rst": "H2", "m.rst": "HB", "z.rst": "H1"},
        )
        self.assertEqual(
            [entry["path"] for entry in result], ["a.rst", "m.rst", "z.rst"]
        )

    def test_two_runs_over_the_same_state_emit_the_same_order(self):
        args = (
            self.entries([("z.rst", "H1"), ("a.rst", "H2")]),
            ["a.rst", "m.rst"],
            {"a.rst": "H2", "m.rst": "HB", "z.rst": "H1"},
        )
        self.assertEqual(dogen.complete_basis_set(*args), dogen.complete_basis_set(*args))

    def test_an_empty_state_yields_an_empty_set(self):
        """The no-op, never an event with an empty files[]."""
        self.assertEqual(dogen.complete_basis_set([], [], {}), [])


class TestReadFs(TempRepoTestCase):
    """U-05 support — the D-19 snapshot, the only channel derive() reads."""

    def test_snapshot_has_exactly_the_two_documented_keys(self):
        snapshot = dogen.read_fs(self.repo, "u", [], [])
        self.assertEqual(set(snapshot), {"unit_md_sha", "paths"})

    def test_snapshot_digests_present_missing_and_empty_paths(self):
        docs = self.repo / "docs"
        docs.mkdir()
        (docs / "present.rst").write_bytes(b"page\n")
        (docs / "empty.rst").write_bytes(b"")
        snapshot = dogen.read_fs(
            self.repo, "u", ["present.rst"], ["empty.rst", "gone.rst"]
        )
        self.assertEqual(
            snapshot["paths"]["present.rst"], hashlib.sha256(b"page\n").hexdigest()
        )
        self.assertEqual(snapshot["paths"]["empty.rst"], "")
        self.assertIsNone(snapshot["paths"]["gone.rst"])

    def test_snapshot_covers_basis_paths_and_targets_only(self):
        docs = self.repo / "docs"
        docs.mkdir()
        (docs / "unrelated.rst").write_bytes(b"x\n")
        snapshot = dogen.read_fs(self.repo, "u", ["a.rst"], ["b.rst", "a.rst"])
        self.assertEqual(sorted(snapshot["paths"]), ["a.rst", "b.rst"])

    def test_snapshot_reads_unit_md(self):
        unit_dir = self.repo / ".dogen" / "units" / "u"
        unit_dir.mkdir(parents=True)
        (unit_dir / "unit.md").write_bytes(b"---\n---\n")
        snapshot = dogen.read_fs(self.repo, "u", [], [])
        self.assertEqual(
            snapshot["unit_md_sha"], hashlib.sha256(b"---\n---\n").hexdigest()
        )

    def test_snapshot_unit_md_is_none_when_the_unit_has_no_plan(self):
        self.assertIsNone(dogen.read_fs(self.repo, "u", [], [])["unit_md_sha"])


class TestChainValidButStructurallyUnexpected(TempRepoTestCase):
    """CR-04 — a ledger that passes ``verify_chain`` but is shaped wrong.

    ``verify_chain`` checks ``seq`` contiguity and ``prev`` digests and nothing
    beneath them, so every payload field — ``withdraws[].seq``,
    ``files[].path`` — reaches ``derive()`` and ``read_fs()`` exactly as a
    hand-repaired, forged or future-tool-written record spells it. Those two
    used to raise ``TypeError``, which escaped all four of ``main``'s arms,
    printed a Python traceback and exited **1** — contract 5.7's code for a
    GATE refusal ("no signoff / plan stale / drift"). ``derive()`` runs on every
    verb including the read-only ``show`` an author reaches for precisely when
    the record is damaged, so the tool's loudest invariant ("one JSON line —
    never zero, never two, never a stack trace") is asserted here rather than
    hoped for.
    """

    def test_a_withdraws_entry_without_a_seq_derives_instead_of_raising(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            review(4, "accept", generation_seq=3, withdraws=[{"note": "no seq"}]),
        ]
        state = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))
        self.assertEqual(state["state"], "sealed")

    def test_a_withdraws_entry_without_a_seq_resolves_nothing(self):
        """An entry that names no event may not silently resolve one."""
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            steering(4),
            review(5, "accept", generation_seq=3, withdraws=[{"note": "no seq"}]),
        ]
        state = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))
        self.assertEqual(state["pending"], [4])

    def test_a_withdraws_entry_that_does_name_a_seq_still_resolves_it(self):
        """Vacuous-pass guard: ignoring the bad entry must not gut the loop."""
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            steering(4),
            review(5, "accept", generation_seq=3, withdraws=[{"seq": 4}]),
        ]
        state = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))
        self.assertEqual(state["pending"], [])

    def test_a_resolves_entry_that_is_not_an_int_derives_instead_of_raising(self):
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
            steering(4),
            review(5, "accept", generation_seq=3, resolves=[None]),
        ]
        state = dogen.derive(events, fs_of("P1", **{"a.rst": "H1"}))
        self.assertEqual(state["pending"], [4])

    def test_read_fs_refuses_a_recorded_path_that_is_not_a_string(self):
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_fs(self.repo, "u", [None], [])
        self.assertEqual(caught.exception.reason, "ledger_corrupt")
        self.assertEqual(caught.exception.next_token, "resume")

    def test_read_fs_refuses_an_empty_recorded_path(self):
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_fs(self.repo, "u", [], [""])
        self.assertEqual(caught.exception.reason, "ledger_corrupt")

    def test_read_fs_still_digests_an_ordinary_recorded_path(self):
        """Vacuous-pass guard: the refusal must not swallow the happy path."""
        docs = self.repo / "docs"
        docs.mkdir()
        (docs / "ok.rst").write_bytes(b"page\n")
        snapshot = dogen.read_fs(self.repo, "u", ["ok.rst"], [])
        self.assertEqual(
            snapshot["paths"]["ok.rst"], hashlib.sha256(b"page\n").hexdigest()
        )

    def _main_backstop(self, exception):
        """``main`` with one unexpected exception raised below the verb."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(dogen, "git_root", side_effect=exception):
            with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
                code = dogen.main(["show", "u", "--json"])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_an_unexpected_exception_never_exits_the_gate_code(self):
        code, _, _ = self._main_backstop(TypeError("boom"))
        self.assertNotEqual(
            code,
            dogen.EXITS["gate"],
            "exit 1 is contract 5.7's GATE code; an internal fault is not a gate refusal",
        )
        self.assertEqual(code, dogen.EXITS["ledger"])

    def test_an_unexpected_exception_prints_exactly_one_json_line(self):
        _, out, err = self._main_backstop(TypeError("boom"))
        self.assertEqual(err, "", "--json puts the refusal on stdout (contract 5.7)")
        self.assertEqual(len(out.splitlines()), 1, out)
        payload = json.loads(out)
        self.assertEqual(
            sorted(payload), ["detail", "error", "hint", "next", "unit"]
        )
        self.assertEqual(payload["error"], "internal_error")
        self.assertEqual(payload["unit"], "u")
        self.assertIn("TypeError", payload["detail"])

    def test_the_backstop_does_not_diagnose_the_record(self):
        """WR-23 — a fault in repository discovery is not a damaged ledger.

        The commit that added this arm proved the misdiagnosis in its own test:
        it patches ``git_root`` to raise ``TypeError``, a failure BEFORE any
        ledger is opened, and asserted the author is told to inspect the ledger
        and run ``resume`` — which is ``not_implemented`` in this phase, so the
        route was a dead end as well. ``error``, ``hint`` and ``next`` are the
        three fields a skill routes on, and all three were wrong.
        """
        _, out, _ = self._main_backstop(TypeError("boom"))
        payload = json.loads(out)
        self.assertNotIn("inspect the ledger", payload["hint"])
        self.assertNotIn("could not be derived", payload["hint"])
        self.assertNotEqual(
            payload["next"],
            "resume",
            "`resume` is not_implemented in this phase; a dead-end route is not a route",
        )
        self.assertIn("defect", payload["hint"])
        self.assertIn("unexpected internal fault", payload["detail"])
        self.assertIn("TypeError: boom", payload["detail"])

    def test_the_backstop_keeps_the_exit_code_the_wording_no_longer_claims(self):
        """Vacuous-pass guard: the arm names its own fault and keeps exit 6.

        `internal_error` is the arm's own reason now that the contract carries
        the row (phase 18, D-14). The exit code is unchanged and deliberately
        so: 6 is the record-and-recovery code, and a fault reached below the
        verb is reported there rather than on the gate code that would tell a
        skill the gate said no. A future move of the code IS a contract change.
        """
        code, out, _ = self._main_backstop(TypeError("boom"))
        self.assertEqual(code, dogen.EXITS["ledger"])
        self.assertEqual(dogen.REASONS["internal_error"], dogen.EXITS["ledger"])
        self.assertEqual(json.loads(out)["error"], "internal_error")

    def test_the_backstop_does_not_swallow_a_structured_refusal(self):
        """Vacuous-pass guard: the four named arms still win over the blanket."""
        code, out, _ = self._main_backstop(
            dogen.Refusal("not_a_repo", unit="u", detail="nope")
        )
        self.assertEqual(code, dogen.REASONS["not_a_repo"])
        self.assertEqual(json.loads(out)["error"], "not_a_repo")

    def test_the_backstop_does_not_swallow_an_oserror(self):
        code, out, _ = self._main_backstop(PermissionError(13, "Permission denied"))
        self.assertEqual(code, dogen.REASONS["bad_target"])
        self.assertIn("PermissionError", json.loads(out)["detail"])

    def test_the_oserror_arm_never_leaks_the_absolute_path(self):
        """WR-22 — ``OSError.__str__`` embeds the ABSOLUTE filename.

        ``ledger_label`` exists (WR-10) precisely because a diagnostic a skill
        is invited to paste into an issue or a commit message may not carry the
        caller's filesystem layout. The WR-15 re-raise is right, but it made the
        common permission / read-only-filesystem case newly reachable through
        the one arm that still violated WR-10's own rule.
        """
        absolute = "/home/someone/private-project/.dogen/staging/lock"
        code, out, _ = self._main_backstop(
            PermissionError(errno.EACCES, "Permission denied", absolute)
        )
        payload = json.loads(out)
        self.assertEqual(code, dogen.REASONS["bad_target"])
        self.assertEqual(payload["error"], "bad_target")
        self.assertNotIn("/home/someone/private-project", payload["detail"])
        self.assertEqual(
            payload["detail"],
            "PermissionError: [Errno %d] Permission denied: .dogen/staging/lock"
            % errno.EACCES,
        )

    def test_the_oserror_arm_still_names_the_errno_without_a_filename(self):
        """Vacuous-pass guard: dropping the path may not drop the diagnosis."""
        _, out, _ = self._main_backstop(OSError(errno.EROFS, "Read-only file system"))
        detail = json.loads(out)["detail"]
        self.assertEqual(
            detail, "OSError: [Errno %d] Read-only file system" % errno.EROFS
        )

    def test_the_oserror_arm_survives_an_errno_less_oserror(self):
        """Not every OSError carries an errno; the arm may not crash on one."""
        _, out, _ = self._main_backstop(OSError("something went sideways"))
        self.assertEqual(
            json.loads(out)["detail"], "OSError: something went sideways"
        )

    def test_a_damaged_record_is_not_reported_as_bad_input(self):
        """WR-10 — ``JSONDecodeError`` IS a ``ValueError``.

        ``read_events`` and ``verify_chain`` guard their own ``json.loads``,
        but ``resume_adopt``, ``resume_pass_two`` and ``prior_generation_seq``
        parse the manifest's event lines with no local guard. Reaching the
        ``ValueError`` arm told a skill `bad_target` (2, "bad input") — the
        caller typed something wrong — for a recorded line that will not parse,
        which is the opposite diagnosis and the opposite route.
        """
        code, out, _ = self._main_backstop(
            json.JSONDecodeError("Expecting value", "not json", 0)
        )
        payload = json.loads(out)
        self.assertNotEqual(
            code,
            dogen.REASONS["bad_target"],
            "a damaged record is not bad input from the caller",
        )
        self.assertEqual(code, dogen.REASONS["ledger_corrupt"])
        self.assertEqual(payload["error"], "ledger_corrupt")
        self.assertEqual(payload["next"], "resume")
        self.assertIn("not valid JSON", payload["detail"])

    def test_an_ordinary_value_error_is_still_bad_input(self):
        """Vacuous-pass guard: narrowing the arm may not empty it."""
        code, out, _ = self._main_backstop(ValueError("a bad argument"))
        self.assertEqual(code, dogen.REASONS["bad_target"])
        self.assertEqual(json.loads(out)["error"], "bad_target")
        self.assertEqual(json.loads(out)["detail"], "a bad argument")


class TestContainmentOnRead(TempRepoTestCase):
    """CR-05 — the read surfaces contain what the ledger names.

    Every WRITE path runs ``validate_target`` and ``contained()``; every READ
    path ran neither, so ``read_fs`` and ``read_page_bytes`` joined
    ``signoff.targets`` / ``basis.files[].path`` onto the repo root verbatim.
    ``.dogen/`` is committed, so that path is ordinary contributor input.
    """

    def setUp(self):
        super().setUp()
        self.docs = self.repo / "docs"
        self.docs.mkdir()
        (self.docs / "ok.rst").write_bytes(b"page\n")
        self.outside = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.outside), True)
        self.secret = self.outside / "secret.txt"
        self.secret.write_bytes(b"SECRET\n")
        self.escaping = os.path.relpath(str(self.secret), str(self.docs))

    def test_the_escaping_path_really_does_reach_the_host_file(self):
        """Vacuous-pass guard: the fixture must be a live escape, not a typo."""
        self.assertTrue(
            os.path.isfile(os.path.join(str(self.docs), self.escaping)),
            "the fixture path must resolve to the host file for the test to mean anything",
        )

    def test_read_fs_refuses_a_recorded_path_outside_the_docs_root(self):
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_fs(self.repo, "u", [], [self.escaping])
        self.assertEqual(caught.exception.reason, "ledger_corrupt")
        self.assertEqual(caught.exception.next_token, "resume")

    def test_read_fs_never_digests_the_escaping_file(self):
        digest = hashlib.sha256(b"SECRET\n").hexdigest()
        # IN-07: the refusal's own text is the only thing the caller gets back,
        # and it may not carry the oracle it was raised to withhold. One
        # `assertRaises` proves both halves; the duplicate block that stood here
        # had no `as caught` and nothing read its result.
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_fs(self.repo, "u", [self.escaping], [])
        self.assertNotIn(digest, caught.exception.detail)

    def test_read_page_bytes_refuses_rather_than_returning_empty(self):
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_page_bytes(self.repo, self.escaping, "u")
        self.assertEqual(caught.exception.reason, "ledger_corrupt")

    def test_read_page_bytes_still_returns_an_in_root_page(self):
        """Vacuous-pass guard: refusing everything would satisfy the test above."""
        self.assertEqual(dogen.read_page_bytes(self.repo, "ok.rst", "u"), b"page\n")

    def test_read_page_bytes_still_reports_a_missing_in_root_page_as_empty(self):
        self.assertEqual(dogen.read_page_bytes(self.repo, "gone.rst", "u"), b"")

    def test_read_fs_still_digests_an_in_root_page(self):
        snapshot = dogen.read_fs(self.repo, "u", [], ["ok.rst"])
        self.assertEqual(
            snapshot["paths"]["ok.rst"], hashlib.sha256(b"page\n").hexdigest()
        )

    def test_a_symlinked_page_inside_the_docs_root_cannot_point_out_of_it(self):
        """``contained`` resolves the leaf, so a link is not a second door."""
        os.symlink(str(self.secret), str(self.docs / "link.rst"))
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_fs(self.repo, "u", [], ["link.rst"])
        # CR-06: it still refuses — but as the WORKING-TREE fault it is, not as
        # a damaged record. See the two tests below for the whole distinction.
        self.assertEqual(caught.exception.reason, "bad_write_path")

    def test_the_record_shaped_fault_still_blames_the_record(self):
        """CR-06 — an escaping path in the LEDGER is decided lexically."""
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_fs(self.repo, "u", [], [self.escaping])
        self.assertEqual(caught.exception.reason, "ledger_corrupt")
        self.assertEqual(caught.exception.next_token, "resume")
        self.assertIn("the record names a page", caught.exception.hint)

    def test_the_disk_shaped_fault_names_the_link_and_not_the_ledger(self):
        """CR-06 — the two conditions must be distinguishable, and distinguished.

        Before this, `contained()` answered both: it resolves the leaf with
        `realpath`, so an ordinary shared `CHANGELOG.rst` symlinked under
        `docs/` was reported as "recorded path 'reference/ok.rst' resolves
        outside docs/ ... inspect the ledger ... next: resume". Every clause was
        false — the recorded path is inside `docs/`, the chain is valid, and
        `resume` cannot rewrite a symlink — and the one fact the author needed
        appeared nowhere.
        """
        os.symlink(str(self.secret), str(self.docs / "link.rst"))
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_fs(self.repo, "u", [], ["link.rst"])
        refusal = caught.exception
        self.assertEqual(refusal.reason, "bad_write_path")
        self.assertIn("link", refusal.detail)
        self.assertIn("docs/link.rst", refusal.detail)
        self.assertNotIn("ledger", refusal.hint)
        self.assertNotIn("record", refusal.hint)
        self.assertNotEqual(
            refusal.next_token,
            "resume",
            "`resume` cannot rewrite a symlink, and is not implemented here",
        )
        self.assertNotIn(
            hashlib.sha256(b"SECRET\n").hexdigest(),
            refusal.detail,
            "naming the link may not leak what refusing withheld",
        )

    def _symlink_the_docs_root(self):
        """Commit-shaped attack: `docs` itself is the link (git mode 120000)."""
        shutil.rmtree(str(self.docs))
        os.symlink(str(self.outside), str(self.docs))

    def test_the_symlinked_docs_root_fixture_really_reaches_the_host_file(self):
        """Vacuous-pass guard: a dead link would make the two tests below free."""
        self._symlink_the_docs_root()
        with open(str(self.docs / "secret.txt"), "rb") as handle:
            self.assertEqual(handle.read(), b"SECRET\n")

    def test_read_fs_refuses_when_the_docs_root_itself_escapes(self):
        """CR-05: containing within `docs` is tautological when `docs` escapes.

        The recorded path is an ordinary in-root ``secret.txt``; the escape is
        the second committed blob, ``docs`` as mode 120000. Every containment
        test below it then measures the attacker's own directory against itself.
        """
        self._symlink_the_docs_root()
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_fs(self.repo, "u", [], ["secret.txt"])
        self.assertEqual(caught.exception.reason, "bad_write_path")
        self.assertNotIn(
            hashlib.sha256(b"SECRET\n").hexdigest(),
            caught.exception.detail,
            "the refusal may not carry the oracle it was raised to withhold",
        )

    def test_read_page_bytes_refuses_when_the_docs_root_itself_escapes(self):
        self._symlink_the_docs_root()
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_page_bytes(self.repo, "secret.txt", "u")
        self.assertEqual(caught.exception.reason, "bad_write_path")


class TestLockOpenReportsTheRealFault(TempRepoTestCase):
    """WR-15 — ``acquire_lock`` names the errno it identified, or gets out of the way.

    The CR-03 fix wrapped ``os.open`` in a blanket ``except OSError`` whose
    wording (".dogen/staging/lock cannot be opened as a real file") is only true
    for ``ELOOP``/``EISDIR``/``ENOTDIR``. For permissions, a read-only
    filesystem, ``ENOSPC`` or ``EMFILE`` it reported a cause that is false — and
    strictly worse than what ``main``'s ``OSError`` backstop already said.
    """

    def _acquire_with(self, error):
        """``acquire_lock`` with ``os.open`` failing exactly once, on the lock."""
        real_open = os.open
        lock = os.path.join(str(self.repo), ".dogen", "staging", "lock")

        def fake_open(path, *args, **kwargs):
            if os.fspath(path) == lock:
                raise error
            return real_open(path, *args, **kwargs)

        with mock.patch.object(os, "open", fake_open):
            return dogen.acquire_lock(self.repo, "u")

    def test_eisdir_is_still_reported_as_a_path_that_is_not_a_real_file(self):
        with self.assertRaises(dogen.Refusal) as caught:
            self._acquire_with(OSError(errno.EISDIR, "Is a directory"))
        self.assertEqual(caught.exception.reason, "bad_write_path")
        self.assertIn("EISDIR", caught.exception.detail)

    def test_eloop_and_enotdir_are_reported_the_same_way(self):
        for code in (errno.ELOOP, errno.ENOTDIR):
            with self.subTest(errno=errno.errorcode[code]):
                with self.assertRaises(dogen.Refusal) as caught:
                    self._acquire_with(OSError(code, "nope"))
                self.assertEqual(caught.exception.reason, "bad_write_path")
                self.assertIn(errno.errorcode[code], caught.exception.detail)

    def test_every_other_errno_propagates_to_mains_oserror_backstop(self):
        """A cause dogen cannot identify is one it may not invent."""
        for code in (errno.EACCES, errno.EROFS, errno.ENOSPC, errno.EMFILE):
            with self.subTest(errno=errno.errorcode[code]):
                with self.assertRaises(OSError) as caught:
                    self._acquire_with(OSError(code, "nope"))
                self.assertNotIsInstance(caught.exception, dogen.Refusal)
                self.assertEqual(caught.exception.errno, code)

    def test_an_ordinary_lock_is_still_acquired(self):
        """Vacuous-pass guard: the branch must not have broken the happy path."""
        fd = dogen.acquire_lock(self.repo, "u")
        self.addCleanup(dogen.release_lock, fd)
        self.assertTrue(
            os.path.isfile(os.path.join(str(self.repo), ".dogen", "staging", "lock"))
        )


class TestLockFlockReportsTheRealFault(TempRepoTestCase):
    """WR-21 — the OTHER blanket ``except OSError`` in ``acquire_lock``.

    The WR-15 fix narrowed the ``os.open`` arm and stopped one ``try`` block
    short. "Another dogen invocation holds .dogen/staging/lock" is true of
    ``EWOULDBLOCK`` and of nothing else: ``ENOLCK`` (an NFS or overlay mount
    with no lock manager), ``EBADF``, ``EINTR`` and ``EINVAL`` all got the same
    sentence, which sends a skill into a wait-and-retry loop against a condition
    that will never clear.
    """

    def _flock_with(self, error):
        """``acquire_lock`` with ``fcntl.flock`` failing on the real lock fd."""

        def fake_flock(fd, operation):
            raise error

        with mock.patch.object(dogen.fcntl, "flock", fake_flock):
            return dogen.acquire_lock(self.repo, "u")

    def test_a_contended_lock_is_still_reported_as_busy(self):
        for code in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
            with self.subTest(errno=errno.errorcode[code]):
                with self.assertRaises(dogen.Refusal) as caught:
                    self._flock_with(OSError(code, "would block"))
                self.assertEqual(caught.exception.reason, "busy")
                self.assertEqual(caught.exception.unit, "u")

    def test_every_other_errno_propagates_to_mains_oserror_backstop(self):
        """A cause dogen cannot identify is one it may not invent."""
        for code in (errno.ENOLCK, errno.EBADF, errno.EINTR, errno.EINVAL):
            with self.subTest(errno=errno.errorcode[code]):
                with self.assertRaises(OSError) as caught:
                    self._flock_with(OSError(code, "nope"))
                self.assertNotIsInstance(caught.exception, dogen.Refusal)
                self.assertEqual(caught.exception.errno, code)

    def test_the_lock_fd_is_closed_on_every_arm(self):
        """Both arms run `os.close(fd)`; a leaked fd would outlive the refusal."""
        closed = []
        real_close = os.close

        def spy_close(fd):
            closed.append(fd)
            return real_close(fd)

        for code, expected in (
            (errno.EWOULDBLOCK, dogen.Refusal),
            (errno.ENOLCK, OSError),
        ):
            with self.subTest(errno=errno.errorcode[code]):
                closed.clear()
                with mock.patch.object(os, "close", spy_close):
                    with self.assertRaises(expected):
                        self._flock_with(OSError(code, "nope"))
                self.assertEqual(len(closed), 1, "the lock fd is closed exactly once")


def routing_state(**overrides):
    """A derived-state shape carrying only what ``route()`` reads.

    Literal dicts, exactly as U-05 feeds ``derive()``: ``route`` is pure over the
    derived state, so the table can be exercised row by row without building a
    ledger for each one.
    """
    state = {
        "uncommitted_tail": False,
        "retired": False,
        "so": {"seq": 2},
        "plan_stale": False,
        "page_drift": False,
        "target_exists": False,
        "gen": {"seq": 3},
        "generation_stale": False,
        "tip": {"kind": "generation", "seq": 3},
        "h_after_tip": False,
        "target_missing": False,
        "actionable": False,
        "steps_resolved": False,
    }
    state.update(overrides)
    return state


class TestRoutingStateIsProduced(unittest.TestCase):
    """WR-02 — every key ``route()`` reads is a key ``derive()`` writes.

    ``routing_state()`` is a hand-built dict, so the table above can assert a
    row against a state shape its only producer never emits. It did: neither
    ``uncommitted_tail`` nor ``steps_resolved`` was in ``derive()``'s return,
    so row 1 was unreachable and every actionable unit routed to ``walk``
    regardless of whether its steps were resolved. This is the guard that makes
    a fabricated key impossible to add again.
    """

    def test_derive_produces_every_key_routing_state_carries(self):
        derived = dogen.derive([], {"unit_md_sha": None, "paths": {}})
        self.assertLessEqual(set(routing_state()), set(derived))

    def test_uncommitted_tail_defaults_to_false_and_is_carried_when_passed(self):
        fs = {"unit_md_sha": None, "paths": {}}
        self.assertFalse(dogen.derive([], fs)["uncommitted_tail"])
        self.assertTrue(
            dogen.derive([], fs, None, uncommitted_tail=True)["uncommitted_tail"]
        )
        self.assertEqual(
            dogen.route(dogen.derive([], fs, None, uncommitted_tail=True)), "resume"
        )

    def test_pending_stray_defaults_to_false_and_is_carried_when_passed(self):
        """WR-03 — routing's second recovery fact travels the same channel."""
        fs = {"unit_md_sha": None, "paths": {}}
        self.assertFalse(dogen.derive([], fs)["pending_stray"])
        self.assertTrue(
            dogen.derive([], fs, None, pending_stray=True)["pending_stray"]
        )
        self.assertEqual(
            dogen.route(dogen.derive([], fs, None, pending_stray=True)), "resume"
        )

    def test_a_stray_pending_unit_never_routes_to_a_verb_that_refuses_it(self):
        """WR-03 — the state used to fall to row 10 and answer `review`."""
        fs = {"unit_md_sha": None, "paths": {}}
        events = opening() + [signoff(2, ["a.rst"], intent="reference")]
        looped = dogen.route(dogen.derive(events, fs_of("P1")))
        self.assertNotEqual(looped, "resume")  # the pre-fix answer
        self.assertEqual(
            dogen.route(dogen.derive(events, fs_of("P1"), None, pending_stray=True)),
            "resume",
        )

    def test_steps_resolved_is_true_for_a_unit_with_no_steps_to_resolve(self):
        events = opening() + [signoff(2, ["a.rst"], intent="reference")]
        result = dogen.derive(events, fs_of("P1"))
        self.assertTrue(result["steps_resolved"])
        self.assertFalse(result["actionable"])

    def test_an_actionable_unit_with_no_plan_has_unresolved_steps(self):
        events = opening() + [signoff(2, ["a.rst"], intent="how-to")]
        result = dogen.derive(events, fs_of("P1"))
        self.assertTrue(result["actionable"])
        self.assertFalse(result["steps_resolved"])
        self.assertEqual(dogen.route(result), "walk")

    def test_an_actionable_unit_whose_steps_are_resolved_routes_to_draft(self):
        events = opening() + [
            signoff(2, ["a.rst"], intent="how-to"),
            ev("steps-planned", 3, steps=[{"id": "s1"}]),
            ev(
                "step-recorded",
                4,
                steps_seq=3,
                step_id="s1",
                verdict="pass",
                exit_code=0,
                output_sha256=STEP_DIGEST,
            ),
        ]
        result = dogen.derive(events, fs_of("P1"))
        self.assertTrue(result["steps_resolved"])
        self.assertEqual(dogen.route(result), "draft")

    def test_an_actionable_unit_with_a_failed_step_still_walks(self):
        events = opening() + [
            signoff(2, ["a.rst"], intent="how-to"),
            ev("steps-planned", 3, steps=[{"id": "s1"}, {"id": "s2"}]),
            ev(
                "step-recorded",
                4,
                steps_seq=3,
                step_id="s1",
                verdict="fail",
                exit_code=1,
                output_sha256=STEP_DIGEST,
            ),
        ]
        result = dogen.derive(events, fs_of("P1"))
        self.assertFalse(result["steps_resolved"])
        self.assertEqual(dogen.route(result), "walk")


ACCEPT_TIP = {"kind": "review", "verdict": "accept", "seq": 5}
FIX_TIP = {"kind": "review", "verdict": "fix", "seq": 5}
EDIT_TIP = {"kind": "reviewer-edit", "seq": 5}


class TestPendingSituation(unittest.TestCase):
    """WR-03 — contract 5.8's situation table, stated once for both callers.

    ``classify_stage_a`` decides whether to refuse and ``stray_pending_material``
    decides where to route; a second opinion about the same fact is what let the
    refusal and the routed token disagree and put the author in a circle.
    """

    def test_no_manifest_is_pending_without_manifest(self):
        self.assertEqual(
            dogen.pending_situation(None, ["a"], ["a"]), "pending_without_manifest"
        )

    def test_a_fully_committed_batch_awaits_cleanup(self):
        manifest = {"events": ["a", "b"]}
        self.assertEqual(
            dogen.pending_situation(manifest, ["a", "b"], ["a", "b"]),
            "committed_batch_awaiting_cleanup",
        )

    def test_a_batch_with_no_events_in_the_ledger_is_manifest_without_events(self):
        manifest = {"events": ["x", "y"]}
        self.assertEqual(
            dogen.pending_situation(manifest, ["a"], ["a"]), "manifest_without_events"
        )

    def test_a_partly_present_batch_is_the_stray_situation(self):
        manifest = {"events": ["a", "y"]}
        self.assertEqual(
            dogen.pending_situation(manifest, ["a"], ["a"]), dogen.PENDING_STRAY
        )

    def test_the_stray_situation_is_not_a_contract_row(self):
        """Vacuous-pass guard: the four answers are four distinct strings."""
        self.assertEqual(
            len(
                {
                    "pending_without_manifest",
                    "committed_batch_awaiting_cleanup",
                    "manifest_without_events",
                    dogen.PENDING_STRAY,
                }
            ),
            4,
        )


class TestRouting(unittest.TestCase):
    """U-06 — contract 5.5's ordered table: rows 1–10, first match wins."""

    def test_every_row_returns_its_token(self):
        rows = (
            ("1 uncommitted tail", {"uncommitted_tail": True}, "resume"),
            ("2 retired", {"retired": True}, "retired"),
            ("3 no signoff", {"so": None, "gen": None}, "sign_off"),
            ("4 plan_stale", {"plan_stale": True}, "re_sign"),
            ("5 page_drift", {"page_drift": True}, "record_edits"),
            ("5 target_exists", {"target_exists": True}, "record_edits"),
            ("6 no generation", {"gen": None, "tip": None}, "draft"),
            (
                "6 actionable with unresolved steps",
                {"gen": None, "tip": None, "actionable": True},
                "walk",
            ),
            ("7 generation_stale", {"generation_stale": True}, "draft"),
            ("8 sealed", {"tip": ACCEPT_TIP}, "publish"),
            ("8b sealed with a missing target", {"tip": ACCEPT_TIP, "target_missing": True}, "steer"),
            ("9 accept with H after", {"tip": ACCEPT_TIP, "h_after_tip": True}, "draft"),
            ("9 fix verdict", {"tip": FIX_TIP}, "draft"),
            ("10 tip is a generation", {}, "review"),
            ("10 tip is a reviewer-edit", {"tip": EDIT_TIP}, "review"),
        )
        for label, overrides, expected in rows:
            with self.subTest(row=label):
                self.assertEqual(dogen.route(routing_state(**overrides)), expected)

    def test_an_earlier_row_wins_over_a_later_one(self):
        # page_drift (5) and generation_stale (7) hold at once: table order
        # decides, never recency.
        self.assertEqual(
            dogen.route(routing_state(page_drift=True, generation_stale=True)),
            "record_edits",
        )
        # An uncommitted tail outranks even `retired`, which outranks the rest.
        self.assertEqual(
            dogen.route(routing_state(uncommitted_tail=True, retired=True, plan_stale=True)),
            "resume",
        )
        self.assertEqual(
            dogen.route(routing_state(retired=True, plan_stale=True, page_drift=True)),
            "retired",
        )

    def test_row_8b_is_evaluated_before_row_9_and_after_row_8(self):
        sealed = routing_state(tip=ACCEPT_TIP)
        self.assertEqual(dogen.route(sealed), "publish")
        sealed_missing = routing_state(tip=ACCEPT_TIP, target_missing=True)
        self.assertEqual(dogen.route(sealed_missing), "steer")
        # An H event after the accept defeats both: row 9.
        self.assertEqual(
            dogen.route(routing_state(tip=ACCEPT_TIP, target_missing=True, h_after_tip=True)),
            "draft",
        )

    def test_the_table_is_exhaustive(self):
        """A derivable state never routes to ``None`` — it falls to row 10."""
        self.assertEqual(dogen.route(routing_state()), "review")
        self.assertIsNotNone(dogen.route({}))
        for state in (
            {},
            {"so": None},
            {"tip": None, "gen": None, "so": {"seq": 0}},
            dogen.derive([], {"unit_md_sha": None, "paths": {}}),
        ):
            with self.subTest(state=sorted(state)):
                self.assertIsNotNone(dogen.route(state))

    def test_routing_is_stable_across_invocations(self):
        state = routing_state(tip=ACCEPT_TIP)
        self.assertEqual(dogen.route(state), dogen.route(state))
        self.assertEqual(dogen.route(dict(state)), "publish")

    def test_a_declared_unit_routes_to_signoff(self):
        """The tracer's own conclusion, derived rather than asserted."""
        state = dogen.derive(opening(), {"unit_md_sha": "P1", "paths": {}})
        self.assertEqual(dogen.route(state), "sign_off")

    def test_a_hook_rewritten_page_routes_to_record_edits(self):
        """T29: the post-commit re-derive's conclusion for a changed page."""
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
        ]
        state = dogen.derive(events, fs_of("P1", **{"a.rst": "HOOKBYTES"}))
        self.assertTrue(state["page_drift"])
        self.assertEqual(dogen.route(state), "record_edits")

    def test_a_hook_rewritten_unit_md_routes_to_re_sign(self):
        """T29b: a changed ``unit.md`` is ``plan_stale``, and row 4 owns it."""
        events = opening() + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "H1")], signoff_seq=2),
        ]
        state = dogen.derive(events, fs_of("HOOKPLAN", **{"a.rst": "H1"}))
        self.assertTrue(state["plan_stale"])
        self.assertEqual(dogen.route(state), "re_sign")


_REASON_ROW_RE = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*([0-9])\s*\|$")


def contract_reason_table():
    """The reason table out of ``docs/contract.md``, in the contract's order.

    Parsed the same way phase 18's ``check_docs.py`` will parse it, so the two
    readers cannot drift apart during this phase.
    """
    text = (ROOT / "docs" / "contract.md").read_text(encoding="utf-8")
    start = text.index("Reason table:")
    rows = []
    for line in text[start:].split("\n"):
        match = _REASON_ROW_RE.match(line.strip())
        if match is not None:
            rows.append((match.group(1), int(match.group(2))))
        elif rows and not line.strip().startswith("|"):
            break
    return rows


class TestReasonTable(unittest.TestCase):
    """U-07 — ``REASONS`` is the contract's reason table, row for row."""

    def test_the_contract_table_is_parseable_and_non_empty(self):
        rows = contract_reason_table()
        self.assertGreater(len(rows), 40, "the contract's reason table did not parse")

    def test_no_reason_is_missing_and_none_is_invented(self):
        contract = dict(contract_reason_table())
        self.assertEqual(
            sorted(dogen.REASONS), sorted(contract), "REASONS and the contract disagree"
        )

    def test_every_exit_code_matches_the_contract(self):
        for reason, code in contract_reason_table():
            with self.subTest(reason=reason):
                self.assertEqual(dogen.REASONS[reason], code)

    def test_key_order_is_the_contracts_order(self):
        self.assertEqual(
            list(dogen.REASONS), [reason for reason, _ in contract_reason_table()]
        )

    def test_every_value_is_one_of_the_six_exit_codes(self):
        codes = set(dogen.EXITS.values())
        self.assertEqual(codes, {0, 1, 2, 3, 4, 5, 6})
        for reason, code in dogen.REASONS.items():
            with self.subTest(reason=reason):
                self.assertIn(code, {1, 2, 3, 4, 5, 6})

    def test_the_table_has_no_duplicate_rows(self):
        rows = contract_reason_table()
        self.assertEqual(len(rows), len(set(reason for reason, _ in rows)))


# --- U-08 — the §6 verb table, as the parser renders it and as the contract states it ---

_HELP_FLAG_RE = re.compile(r"--[a-z][a-z0-9-]*")
_PLACEHOLDER_RE = re.compile(r"<[^>]+>")

# The contract's `unit edit` row writes `[flags]` for "the same declaration
# flags `unit new` takes". Expanding the placeholder here keeps that row
# readable in the contract without making this comparison approximate.
_FLAGS_PLACEHOLDER = "[flags]"

# `--json` is contract 5.7 / GATE-04's global output-inversion flag: EVERY verb
# accepts it, because every refusal must be movable to stdout. The §6 table
# lists it only on the read-only verbs, where it also changes *successful*
# output. Comparing it row by row would measure that documentation choice
# rather than drift, so it is excluded from the flag sets and asserted
# separately, on every verb, by ``test_json_is_accepted_by_every_verb``.
_GLOBAL_FLAGS = frozenset({"--json"})


def contract_verb_table():
    """The §6 verb table out of ``docs/contract.md``, one entry per signature.

    Returns ``{verb path: {"flags": frozenset, "positionals": int}}``. Parsed
    the same way phase 18's ``check_docs.py`` will parse it, so the two readers
    cannot drift apart during this phase.
    """
    text = (ROOT / "docs" / "contract.md").read_text(encoding="utf-8")
    heading = "## 6 Verb table"
    body = text[text.index(heading) + len(heading) :]
    end = body.find("\n## ")
    if end != -1:
        body = body[:end]
    table = {}
    declaration_flags = frozenset()
    for line in body.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = re.split(r"(?<!\\)\|", line)
        if len(cells) < 2:
            continue
        cell = cells[1].replace("\\|", "|")
        for signature in re.findall(r"`([^`]+)`", cell):
            path = []
            for token in signature.split():
                if re.match(r"^[a-z][a-z0-9-]*$", token):
                    path.append(token)
                else:
                    break
            if not path:
                continue
            flags = set(_HELP_FLAG_RE.findall(signature))
            if _FLAGS_PLACEHOLDER in signature:
                flags |= set(declaration_flags)
            verb = " ".join(path)
            # Positionals are the `<…>` placeholders BEFORE the first flag; a
            # `<…>` after one is a flag's metavar (`--withdraw <seq> "<reason>"`).
            head = signature.split("--", 1)[0]
            table[verb] = {
                "flags": frozenset(flags) - _GLOBAL_FLAGS,
                "positionals": len(_PLACEHOLDER_RE.findall(head)),
            }
            if verb == "unit new":
                declaration_flags = frozenset(flags)
    return table


def parser_verb_table(parser, prefix=""):
    """The same shape as :func:`contract_verb_table`, read off ``build_parser()``.

    The parser is what argparse renders ``--help`` from, so reading it is
    reading the help output without re-parsing argparse's own formatting.
    """
    table = {}
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, sub in action.choices.items():
            verb = (prefix + " " + name).strip()
            nested = parser_verb_table(sub, verb)
            if nested:
                table.update(nested)
                continue
            table[verb] = {
                "flags": frozenset(
                    option
                    for sub_action in sub._actions
                    for option in sub_action.option_strings
                    if option not in ("-h", "--help")
                )
                - _GLOBAL_FLAGS,
                "positionals": len(
                    [
                        sub_action
                        for sub_action in sub._actions
                        if not sub_action.option_strings
                        and not isinstance(sub_action, argparse._SubParsersAction)
                    ]
                ),
            }
    return table


class TestVerbTable(unittest.TestCase):
    """U-08 — ``dogen --help`` is the contract's §6 verb table, row for row.

    The help output is a machine-diffed observable (phase 18's
    ``check_docs.py``), not documentation: a verb registered here and absent
    there, or an argument renamed on one side, is a defect in one of the two.
    """

    def setUp(self):
        self.contract = contract_verb_table()
        self.parser = parser_verb_table(dogen.build_parser())

    def test_the_contract_table_is_parseable_and_non_empty(self):
        self.assertEqual(
            sorted(self.contract),
            [
                "draft",
                "edits",
                "plan-steps",
                "resume",
                "review",
                "show",
                "signoff",
                "steer",
                "step",
                "summary",
                "unit edit",
                "unit new",
                "unit retire",
                "verify",
                "version",
            ],
            "the contract's §6 verb table did not parse",
        )

    def test_no_verb_is_missing_and_none_is_invented(self):
        self.assertEqual(
            sorted(self.parser), sorted(self.contract), "--help and §6 disagree"
        )

    def test_every_verbs_arguments_match_the_contract(self):
        for verb in sorted(self.contract):
            with self.subTest(verb=verb):
                self.assertIn(verb, self.parser)
                self.assertEqual(
                    sorted(self.parser[verb]["flags"]),
                    sorted(self.contract[verb]["flags"]),
                )

    def test_every_verbs_positional_count_matches_the_contract(self):
        for verb in sorted(self.contract):
            with self.subTest(verb=verb):
                self.assertIn(verb, self.parser)
                self.assertEqual(
                    self.parser[verb]["positionals"],
                    self.contract[verb]["positionals"],
                )

    def test_json_is_accepted_by_every_verb(self):
        """The global flag §6 lists only where it changes successful output."""
        for verb in sorted(self.parser):
            with self.subTest(verb=verb):
                argv = verb.split() + ["--help"]
                with self.assertRaises(SystemExit):
                    with mock.patch("sys.stdout", io.StringIO()):
                        dogen.build_parser().parse_args(argv)
        parser = dogen.build_parser()
        for verb in sorted(self.parser):
            with self.subTest(verb=verb):
                options = _subparser_for(parser, verb)
                self.assertIn(
                    "--json",
                    [
                        option
                        for action in options._actions
                        for option in action.option_strings
                    ],
                )

    def test_force_is_registered_nowhere(self):
        """VERB-01: ``slim@357c513``'s ``--force`` is removed, not renamed."""
        parser = dogen.build_parser()
        for verb in sorted(self.parser):
            with self.subTest(verb=verb):
                options = [
                    option
                    for action in _subparser_for(parser, verb)._actions
                    for option in action.option_strings
                ]
                self.assertNotIn("--force", options)
        self.assertNotIn(
            "--force",
            [
                option
                for action in parser._actions
                for option in action.option_strings
            ],
        )

    def test_the_rendered_help_lists_every_top_level_verb(self):
        proc = subprocess.run(
            [sys.executable, str(DOGEN_PATH), "--help"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for verb in sorted(set(name.split()[0] for name in self.contract)):
            with self.subTest(verb=verb):
                self.assertIn(verb, proc.stdout)
        self.assertNotIn("--force", proc.stdout)


def _subparser_for(parser, verb):
    """Walk ``build_parser()`` down a space-separated verb path."""
    current = parser
    for name in verb.split():
        action = [
            candidate
            for candidate in current._actions
            if isinstance(candidate, argparse._SubParsersAction)
        ][0]
        current = action.choices[name]
    return current


class TestTheTransitionalReasonIsGone(unittest.TestCase):
    """D-16 / T-16-45 — `not_implemented` existed for the phase-17 stubs only.

    `verify` was the last stub, so the reason, the helper that built it and the
    shared stub body are deleted (plan 17-09). What remains is the guard: the
    reason was never a row of the contract's table and never a key of
    ``REASONS``, and it must not come back through either door — U-07 keeps
    requiring the two tables to be equal, and these two checks name which side
    would have leaked.
    """

    def test_the_transitional_reason_is_not_an_exported_reason(self):
        self.assertNotIn("not_implemented", dogen.REASONS)

    def test_the_transitional_reason_is_not_in_the_contracts_reason_table(self):
        self.assertNotIn(
            "not_implemented", [reason for reason, _ in contract_reason_table()]
        )

    def test_the_stub_machinery_is_gone_from_the_tool(self):
        source = DOGEN_PATH.read_text(encoding="utf-8")
        body = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        for symbol in ("stub_verb", "refuse_unimplemented", "STUB_REASON"):
            self.assertNotIn(symbol, body, symbol)


class TestEveryDestinationReachesTheChokePoint(TempRepoTestCase):
    """WR-02 — the ledger is a checked destination, not just a pathspec.

    ``guard_write_paths``'s docstring calls itself "the ONE choke point", but it
    only ever saw ``files`` — the pages and ``unit.md``. The ledger, which every
    single write appends to, reached git as a pathspec and ``contained()`` never.
    Containment for the record of truth was therefore incidental: it held only
    because ``git add --dry-run`` happens to refuse a pathspec beyond a symlink.
    These tests pin the invariant on the guard itself, so it stops depending on
    git's error text.
    """

    def _perform_write_destinations(self):
        """Every ``(path, bytes)`` tuple ``perform_write`` hands to the guard."""
        seen = []

        def spy(repo, unit, files):
            seen.append([path for path, _ in files])
            raise dogen.Refusal("bad_write_path", unit=unit, detail="stop here")

        with mock.patch.object(dogen, "guard_write_paths", spy):
            with self.assertRaises(dogen.Refusal):
                dogen.perform_write(
                    self.repo,
                    "led-unit",
                    "declared",
                    ["{}"],
                    [0],
                    [("docs/reference/led.rst", b"body\n")],
                    None,
                    None,
                )
        self.assertEqual(len(seen), 1)
        return seen[0]

    def test_the_ledger_is_among_the_destinations_the_guard_is_shown(self):
        paths = self._perform_write_destinations()
        self.assertIn(
            os.path.join(".dogen", "units", "led-unit", "ledger.jsonl"),
            paths,
            "the ledger must reach guard_write_paths, not only the pathspecs",
        )

    def test_the_pages_still_reach_the_guard_too(self):
        """Vacuous-pass guard: an empty list would satisfy the test above's twin."""
        self.assertIn("docs/reference/led.rst", self._perform_write_destinations())

    def test_the_guard_rejects_a_ledger_that_resolves_outside_the_repository(self):
        """The ledger tuple is refused on its own merits, with no git involved."""
        outside = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(outside), True)
        (self.repo / ".dogen").mkdir()
        os.symlink(str(outside), str(self.repo / ".dogen" / "units"))
        relative = os.path.join(".dogen", "units", "led-unit", "ledger.jsonl")
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.guard_write_paths(self.repo, "led-unit", [(relative, None)])
        self.assertEqual(caught.exception.reason, "bad_write_path")


class TestIndexLockReasonDoesNotDrift(TempRepoTestCase):
    """WR-11 — ``.git/index.lock`` is ``git_busy``, never ``busy``.

    ``REASONS`` carries both on exit 5 and this codebase uses them for two
    different things: ``busy`` is dogen's own ``.dogen/staging/lock``,
    ``git_busy`` is ``.git/index.lock`` (which ``index_lock_present``'s
    docstring states outright). ``guard_ignored_paths`` re-probed the index lock
    and raised ``busy``, so a skill that branches on ``error`` — the field
    contract 5.7 makes the machine-readable one — was told dogen held its own
    lock while the ``detail`` said the opposite. The exit code coincides, so no
    assertion in either suite could see it.

    Driven directly: stage a's ``index_lock_present`` check fires first on every
    deterministic path, so the arm is reachable only in a genuine race and only
    the guard itself can be asked what it answers.
    """

    def _refuse_with_index_lock(self):
        """``guard_ignored_paths``'s refusal when the index lock is present."""
        lock = self.repo / ".git" / "index.lock"
        lock.write_text("", encoding="utf-8")
        self.addCleanup(lambda: lock.exists() and lock.unlink())
        # A destination git will not stage, so the probe's returncode is
        # non-zero and the index-lock arm is the one that answers.
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.guard_ignored_paths(self.repo, "lk-unit", ["../outside.rst"])
        return caught.exception

    def test_the_index_lock_arm_raises_git_busy(self):
        self.assertEqual(self._refuse_with_index_lock().reason, "git_busy")

    def test_the_index_lock_arm_never_raises_dogens_own_busy(self):
        """Negative keystone: ``busy`` means ``.dogen/staging/lock`` and only that."""
        self.assertNotEqual(self._refuse_with_index_lock().reason, "busy")

    def test_the_two_answers_are_worded_identically_to_stage_a(self):
        """The seven stage-a sites and this one must not drift apart."""
        refusal = self._refuse_with_index_lock()
        self.assertEqual(refusal.detail, ".git/index.lock is present")
        self.assertIn("dogen never deletes it", refusal.hint)

    def test_both_reasons_still_exist_and_share_exit_5(self):
        """Vacuous-pass guard: the test above would also pass if `busy` were gone."""
        self.assertEqual(dogen.REASONS["busy"], 5)
        self.assertEqual(dogen.REASONS["git_busy"], 5)


class TestPostCommitCheck(TempRepoTestCase):
    """WRITE-02 — both git vantage points, because neither alone is evidence."""

    def setUp(self):
        super().setUp()
        # dogen.git() inherits the process environment, so the hermetic config
        # has to be in os.environ for these tests, not only in self.env.
        patcher = mock.patch.dict(
            os.environ,
            {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _entry(self, path, data):
        (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / path).write_bytes(data)
        return {
            "path": path,
            "before_sha": None,
            "after_sha": hashlib.sha256(data).hexdigest(),
        }

    def test_an_unchanged_file_reports_no_mismatch_and_no_extra(self):
        entry = self._entry("page.md", b"bytes\n")
        dogen.git_add(self.repo, ["page.md"])
        dogen.git_commit(self.repo, "s", "", [], ["page.md"])
        changed, extra = dogen.post_commit_check(
            self.repo, [entry], ["page.md"], set()
        )
        self.assertEqual(changed, [])
        self.assertEqual(extra, [])

    def test_bytes_rewritten_after_recording_are_reported(self):
        entry = self._entry("page.md", b"bytes\n")
        dogen.git_add(self.repo, ["page.md"])
        dogen.git_commit(self.repo, "s", "", [], ["page.md"])
        # Stand in for a hook: the recorded digest no longer matches the bytes.
        entry["after_sha"] = hashlib.sha256(b"what we meant to write\n").hexdigest()
        changed, _ = dogen.post_commit_check(self.repo, [entry], ["page.md"], set())
        self.assertEqual(changed, ["page.md"])

    def test_a_path_committed_outside_the_pathspecs_is_extra(self):
        entry = self._entry("page.md", b"bytes\n")
        self._entry("smuggled.md", b"not ours\n")
        dogen.git_add(self.repo, ["page.md", "smuggled.md"])
        dogen.git_commit(self.repo, "s", "", [], ["page.md", "smuggled.md"])
        _, extra = dogen.post_commit_check(self.repo, [entry], ["page.md"], set())
        self.assertEqual(extra, ["smuggled.md"])

    def test_a_path_staged_but_not_committed_is_extra(self):
        entry = self._entry("page.md", b"bytes\n")
        dogen.git_add(self.repo, ["page.md"])
        dogen.git_commit(self.repo, "s", "", [], ["page.md"])
        before = dogen.index_snapshot(self.repo)
        self._entry("staged-only.md", b"staged\n")
        dogen.git_add(self.repo, ["staged-only.md"])
        _, extra = dogen.post_commit_check(self.repo, [entry], ["page.md"], before)
        self.assertEqual(extra, ["staged-only.md"])

    def test_a_path_staged_before_the_transition_is_not_the_hooks_doing(self):
        entry = self._entry("page.md", b"bytes\n")
        dogen.git_add(self.repo, ["page.md"])
        dogen.git_commit(self.repo, "s", "", [], ["page.md"])
        self._entry("authors-own.md", b"the author staged this\n")
        dogen.git_add(self.repo, ["authors-own.md"])
        before = dogen.index_snapshot(self.repo)
        _, extra = dogen.post_commit_check(self.repo, [entry], ["page.md"], before)
        self.assertEqual(extra, [])


class TestClaimPolicy(TempRepoTestCase):
    """U-06 support — contract 5.1's claim policy, the one shared predicate.

    A target is blocked when another unit that is **not retired** lists it in
    its CURRENT SIGNOFF — in flight or sealed, both block. A merely declared
    unit claims nothing, because the claim attaches to the signoff.
    """

    def _ledger(self, unit, kinds, targets):
        """Write a unit's ledger through the tool's own writer."""
        path = pathlib.Path(dogen.ledger_path(self.repo, unit))
        actor = {"name": "Test Author", "email": "test@example.com"}
        events = []
        seq = 0
        for kind in kinds:
            if kind == "signoff":
                payload = {
                    "plan_hash": "P" * 64,
                    "intent": "reference",
                    "audience": "TAs",
                    "title": "Demo",
                    "targets": list(targets),
                    "sources": [],
                    "context": {},
                    "supersedes": None,
                }
            elif kind == "retired":
                payload = {"note": "abandoned"}
            else:
                payload = {"v": 1, "unit": unit, "docs_root": "docs"}
            events.append(dogen.build_event(kind, seq, None, actor, None, payload))
            seq += 1
        dogen.append_batch(str(path), dogen.chain_lines(events))

    def test_a_signed_target_is_claimed_by_its_unit(self):
        self._ledger("holder", ["ledger", "signoff"], ["reference/shared.rst"])
        claim = dogen.find_claim(self.repo, "other", ["reference/shared.rst"])
        self.assertEqual(claim, ("holder", ["reference/shared.rst"]))

    def test_a_declared_but_unsigned_unit_claims_nothing(self):
        self._ledger("holder", ["ledger"], ["reference/shared.rst"])
        self.assertIsNone(
            dogen.find_claim(self.repo, "other", ["reference/shared.rst"])
        )

    def test_a_retired_unit_releases_its_claim(self):
        self._ledger("holder", ["ledger", "signoff", "retired"], ["reference/shared.rst"])
        self.assertIsNone(
            dogen.find_claim(self.repo, "other", ["reference/shared.rst"])
        )

    def test_a_unit_never_claims_against_itself(self):
        self._ledger("holder", ["ledger", "signoff"], ["reference/shared.rst"])
        self.assertIsNone(
            dogen.find_claim(self.repo, "holder", ["reference/shared.rst"])
        )

    def test_a_disjoint_target_set_is_free(self):
        self._ledger("holder", ["ledger", "signoff"], ["reference/shared.rst"])
        self.assertIsNone(dogen.find_claim(self.repo, "other", ["reference/free.rst"]))

    def _symlink_the_holders_page(self):
        """An ordinary docs-repo pattern: a shared page linked in under docs/."""
        outside = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(outside), True)
        (outside / "CHANGELOG.rst").write_bytes(b"shared\n")
        docs = self.repo / "docs" / "reference"
        docs.mkdir(parents=True, exist_ok=True)
        os.symlink(str(outside / "CHANGELOG.rst"), str(docs / "shared.rst"))

    def test_a_siblings_symlinked_page_does_not_wedge_every_other_unit(self):
        """CR-06 — one unit's link may not take out the whole repository.

        ``find_claim`` turned ANY refusal from a sibling's ``unit_state`` into a
        repo-wide ``ledger_corrupt``. That is right for a record it cannot read;
        the CR-05 fix widened the input to "any page dogen declines to digest",
        so one symlinked page in unit A refused ``unit new`` and ``signoff`` for
        every unit in the repository — and the recovery it named
        (``dogen show A``) refused identically.
        """
        self._ledger("holder", ["ledger", "signoff"], ["reference/shared.rst"])
        self._symlink_the_holders_page()
        self.assertIsNone(
            dogen.find_claim(self.repo, "other", ["reference/free.rst"]),
            "an unrelated unit's claim check may not fail on a sibling's link",
        )

    def test_falling_through_does_not_lose_the_siblings_claim(self):
        """Vacuous-pass guard: `continue` would also satisfy the test above.

        WR-04's argument still binds — a sibling whose targets vanish from the
        claim set is how two live units end up holding the same page. The claim
        set is derived from the LEDGER, so it is knowable without the snapshot.
        """
        self._ledger("holder", ["ledger", "signoff"], ["reference/shared.rst"])
        self._symlink_the_holders_page()
        self.assertEqual(
            dogen.find_claim(self.repo, "other", ["reference/shared.rst"]),
            ("holder", ["reference/shared.rst"]),
        )

    def test_a_retired_sibling_with_a_symlinked_page_still_releases_its_claim(self):
        """The fall-through derives the whole state, not just the targets."""
        self._ledger(
            "holder", ["ledger", "signoff", "retired"], ["reference/shared.rst"]
        )
        self._symlink_the_holders_page()
        self.assertIsNone(
            dogen.find_claim(self.repo, "other", ["reference/shared.rst"])
        )

    def test_a_sibling_whose_record_cannot_be_read_still_fails_closed(self):
        """WR-04's case is untouched: the whitelist is one reason wide."""
        self._ledger("holder", ["ledger", "signoff"], ["reference/shared.rst"])
        path = pathlib.Path(dogen.ledger_path(self.repo, "holder"))
        path.write_text("not json at all\n", encoding="utf-8")
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.find_claim(self.repo, "other", ["reference/free.rst"])
        self.assertEqual(caught.exception.reason, "ledger_corrupt")
        self.assertEqual(caught.exception.unit, "other")


class TestValidateNote(unittest.TestCase):
    """U-03 — ``validate_note`` is stage b's entry point for every free text.

    ``clean_text`` (plan 16-02) is gate-free input hygiene and raises a plain
    ``ValueError``; the stage-b wrapper is what turns that into ONE reason from
    the contract's table, so no call site has to choose an exit code.
    """

    def test_a_pipe_a_newline_and_a_tab_survive_verbatim(self):
        text = "has | pipe\nand newline\ttab"
        self.assertEqual(dogen.validate_note(text), text)

    def test_a_carriage_return_is_refused(self):
        with self.assertRaises(dogen.Refusal):
            dogen.validate_note("a\rb")

    def test_an_empty_note_is_refused(self):
        with self.assertRaises(dogen.Refusal):
            dogen.validate_note("")

    def test_a_whitespace_only_note_is_refused(self):
        with self.assertRaises(dogen.Refusal):
            dogen.validate_note("   ")

    def test_the_note_cap_is_inclusive_and_measured_in_bytes(self):
        at_cap = "a" * dogen.MAX_NOTE_BYTES
        self.assertEqual(dogen.validate_note(at_cap), at_cap)
        with self.assertRaises(dogen.Refusal):
            dogen.validate_note("a" * (dogen.MAX_NOTE_BYTES + 1))
        with self.assertRaises(dogen.Refusal):
            dogen.validate_note("é" * dogen.MAX_NOTE_BYTES)

    def test_the_refusal_is_a_contract_reason_that_exits_2(self):
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.validate_note("")
        self.assertIn(caught.exception.reason, dogen.REASONS)
        self.assertEqual(dogen.REASONS[caught.exception.reason], 2)


class TestValidateModel(unittest.TestCase):
    """U-03 — contract 5.6's model rule: one line ≤ 128; ``""`` iff unknown."""

    def test_a_plain_model_line_is_accepted(self):
        self.assertEqual(
            dogen.validate_model("claude-opus-5", "configured"), "claude-opus-5"
        )

    def test_the_128_character_cap_is_inclusive(self):
        at_cap = "m" * 128
        self.assertEqual(dogen.validate_model(at_cap, "configured"), at_cap)
        with self.assertRaises(dogen.Refusal):
            dogen.validate_model("m" * 129, "configured")

    def test_a_multi_line_model_is_refused(self):
        with self.assertRaises(dogen.Refusal):
            dogen.validate_model("first\nsecond", "configured")

    def test_an_empty_model_is_accepted_only_when_the_origin_is_unknown(self):
        self.assertEqual(dogen.validate_model("", "unknown"), "")
        with self.assertRaises(dogen.Refusal):
            dogen.validate_model("", "configured")

    def test_a_named_model_contradicts_an_unknown_origin(self):
        """The rule is an "iff", so both directions are enforced."""
        with self.assertRaises(dogen.Refusal):
            dogen.validate_model("claude-opus-5", "unknown")

    def test_the_refusal_is_a_contract_reason_that_exits_2(self):
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.validate_model("m" * 129, "configured")
        self.assertIn(caught.exception.reason, dogen.REASONS)
        self.assertEqual(dogen.REASONS[caught.exception.reason], 2)


class TestValidateStepId(unittest.TestCase):
    """U-03 — the step-id regex lives in ONE place for the phase-17 verbs."""

    def test_the_contract_shape_is_accepted(self):
        for step_id in ("a", "step-1", "step_1", "step.1", "0", "a" * 32):
            with self.subTest(step_id=step_id):
                self.assertEqual(dogen.validate_step_id(step_id), step_id)

    def test_a_deviating_step_id_is_refused(self):
        for step_id in ("", "-leading", "Step1", "a" * 33, "step/1"):
            with self.subTest(step_id=step_id):
                with self.assertRaises(dogen.Refusal):
                    dogen.validate_step_id(step_id)


class TestMarkdownCell(unittest.TestCase):
    """U-08 support — the ONE place a value is escaped, and why (T-16-39)."""

    def test_a_pipe_is_escaped_and_a_newline_becomes_a_break(self):
        self.assertEqual(
            dogen.md_cell("mention the | flag\nand a second line"),
            "mention the \\| flag<br>and a second line",
        )

    def test_ordinary_text_is_untouched(self):
        self.assertEqual(dogen.md_cell("tighten the intro"), "tighten the intro")

    def test_a_carriage_return_never_reaches_a_cell(self):
        self.assertEqual(dogen.md_cell("a\rb"), "ab")

    def test_a_cell_escapes_html_for_the_same_reason_prose_does(self):
        # CR-03: this is the position steering notes and withdrawal reasons
        # land in — the most common contributor-controlled strings in the
        # report — and `summary --md` is pasted into a pull request.
        self.assertEqual(
            dogen.md_cell("<script>evil()</script> & more"),
            "&lt;script&gt;evil()&lt;/script&gt; &amp; more",
        )
        rendered = dogen.md_cell("<img src=x onerror=alert(1)> & <b>bold</b>")
        self.assertNotIn("<img", rendered)
        self.assertNotIn("<b>", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("&amp;", rendered)
        # The characters stay visible — nothing is deleted, only neutralised.
        self.assertIn("onerror=alert(1)", rendered)

    def test_the_break_is_emitted_after_the_html_escaping(self):
        # Order is the whole fix: escaping after the substitution would turn
        # this function's own `<br>` into the literal text `&lt;br&gt;` and
        # the cell would lose its column count.
        self.assertEqual(dogen.md_cell("one\ntwo"), "one<br>two")
        self.assertNotIn("&lt;br&gt;", dogen.md_cell("one\ntwo"))

    def test_the_cell_escaper_is_not_vacuous(self):
        # A `str.replace` chain that lost its subject would return the input
        # unchanged and every assertion above would still pass on plain text.
        self.assertNotEqual(dogen.md_cell("<x>"), "<x>")


class TestMarkdownProseEscapers(unittest.TestCase):
    """WR-11 — the two escapers the non-cell positions of ``--md`` needed.

    ``summary --md`` is documented as text a reviewer PASTES INTO A PR, and
    ``.dogen/`` is committed, so every title, audience, note and gap in it is
    ordinary contributor input — the threat model ``contained_page``'s own
    docstring states. Only the table cells were escaped.
    """

    def test_a_forged_note_cannot_open_a_section_of_its_own(self):
        forged = "looks fine\n\n## Provenance\n\nrecord: verify ok"
        rendered = dogen.md_text(forged)
        self.assertNotIn("\n", rendered)
        self.assertIn("## Provenance", rendered, "the text is kept, visibly")

    def test_raw_html_is_neutralised_not_deleted(self):
        rendered = dogen.md_text('<img src="http://x/beacon">')
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)

    def test_the_escaping_round_trips_an_ampersand(self):
        self.assertEqual(dogen.md_text("a &lt; b"), "a &amp;lt; b")

    def test_a_value_is_capped(self):
        rendered = dogen.md_text("x" * 5000)
        self.assertLessEqual(len(rendered), 400)

    def test_a_non_string_is_rendered_rather_than_crashing(self):
        # A report is better served by showing what the record holds than by
        # falling over on it.
        self.assertEqual(dogen.md_text(["a", "b"]), "[&#x27;a&#x27;, &#x27;b&#x27;]"
                         .replace("&#x27;", "'"))
        self.assertEqual(dogen.md_text(None), "None")

    def test_a_code_span_value_cannot_escape_its_span(self):
        self.assertEqual(dogen.md_code("ok`  ` then **bold**"), "ok  then **bold**")

    def test_a_code_span_value_keeps_its_html_literal(self):
        # A code span renders literally, so escaping `<` there would show the
        # entity rather than the character.
        self.assertEqual(dogen.md_code("a<b"), "a<b")

    def test_an_ordinary_value_is_untouched(self):
        """Vacuous-pass guard: the escapers may not mangle the real input."""
        self.assertEqual(dogen.md_text("TAs onboarding to the docs repo"),
                         "TAs onboarding to the docs repo")


class TestSummaryMarkdownEscapesEveryPosition(unittest.TestCase):
    """WR-13 — the rule is "every value", so the function must show it.

    WR-11 stated the invariant as "every contributor-controlled value goes
    through an escaper chosen for its position" and then left
    ``data["provenance"]`` appended raw. Tool-derived today — `git rev-parse`
    output, verify counts, check ids — but the basis ``commit`` it interpolates
    is a ledger value and therefore forgeable, and an invariant with one
    remembered exception cannot be checked by reading the function.

    Driven over ``summary_markdown`` itself rather than the escapers: the claim
    is about the DOCUMENT, and only a whole-document assertion catches the next
    section someone appends without an escaper.
    """

    BEACON = '<img src="http://attacker.example/b">'

    def forged(self):
        """Every value in the payload forged with the same beacon."""
        return {
            "unit": "u1",
            "title": "Title " + self.BEACON,
            "intent": "Intent " + self.BEACON,
            "audience": "Audience " + self.BEACON,
            "files": ["reference/a.rst"],
            "requests": [
                {
                    "seq": 3,
                    "origin": "steering (manual)",
                    "note": "Note " + self.BEACON,
                    "disposition": "withdrawn",
                    "reason": "Reason " + self.BEACON,
                }
            ],
            "reviewer_edits": [{"seq": 5, "note": "Edit " + self.BEACON}],
            "gaps": ["Gap " + self.BEACON],
            "steps": {
                "passed": 1,
                "skipped": 1,
                "skipped_reasons": ["Skipped " + self.BEACON],
                "deviated": 0,
                "unresolved": [],
            },
            "sphinx": "Sphinx " + self.BEACON,
            "model": "model-x",
            "model_origin": "flag",
            "provenance": "record: verify ok at 0000000 " + self.BEACON,
            "state": "reviewed",
            "next": "review",
        }

    def test_no_raw_element_survives_any_position(self):
        rendered = dogen.summary_markdown(self.forged())
        self.assertNotIn("<img", rendered)
        # The attribute text stays, visibly — a quote needs no escaping once
        # the tag around it cannot open. What is removed is the value's ability
        # to BE an element, never the reader's ability to see what it says.
        self.assertIn('src="http://attacker.example/b"', rendered)

    def test_the_only_raw_angle_brackets_are_the_ones_the_tool_emits(self):
        # `md_cell` emits `<br>` for a newline in a table cell; nothing else in
        # the document may carry a raw `<`. Asserting on the WHOLE document is
        # what makes this survive a new section being added later.
        rendered = dogen.summary_markdown(self.forged()).replace("<br>", "")
        self.assertNotIn("<", rendered)
        self.assertNotIn(">", rendered)

    def test_every_forged_position_is_actually_reached(self):
        # Vacuous-pass guard: an assertion over a document that never rendered
        # the provenance line would pass without proving anything.
        rendered = dogen.summary_markdown(self.forged())
        for heading in (
            "## Files changed",
            "## Intent and audience",
            "## Recorded requests",
            "## Reviewer edits",
            "## Known gaps",
            "## Validation",
            "## Sphinx",
            "## Model",
            "## Provenance",
        ):
            with self.subTest(section=heading):
                self.assertIn(heading, rendered)
        self.assertEqual(rendered.count("&lt;img"), 10, rendered)

    def test_the_text_stays_visible(self):
        rendered = dogen.summary_markdown(self.forged())
        for word in ("Title", "Note", "Reason", "Edit", "Gap", "Sphinx", "record:"):
            with self.subTest(word=word):
                self.assertIn(word, rendered)
        self.assertEqual(dogen.md_code("reference/fixture.rst"),
                         "reference/fixture.rst")

    # --- WR-01: the other two properties the invariant claims ---------------
    #
    # The escaping above is CR-03's. The cap and the non-string guard are
    # `md_flat`'s, and `md_cell` never called it — so for one iteration the
    # table position had the HTML rule and neither of the other two, and the
    # `summary --md` render (the one whose threat model is "a reviewer pastes
    # this into a PR") was the UNCAPPED one.

    def test_every_escaper_caps_the_value_it_is_given(self):
        long = "A" * 5000
        for name in ("md_cell", "md_text", "md_code", "md_flat"):
            with self.subTest(escaper=name):
                self.assertLessEqual(len(getattr(dogen, name)(long)), 400)

    def test_a_max_length_note_cannot_bury_the_document(self):
        # The document-level claim, not the function-level one: a legitimate
        # note as long as `MAX_NOTE_BYTES` allows (65536) renders a report a
        # reviewer can still read. Measured before the fix at 60272 characters
        # for a 60000-byte note, against 388 for the plain render.
        data = self.forged()
        data["requests"][0]["note"] = "B" * 60000
        data["requests"][0]["reason"] = "C" * 60000
        rendered = dogen.summary_markdown(data)
        self.assertLess(len(rendered), 4000, len(rendered))
        # Vacuous-pass guard: the note really did reach the table.
        self.assertIn("BBBB", rendered)

    def test_a_forged_non_string_renders_instead_of_crashing(self):
        # `.dogen/` is committed and the chain is an unkeyed sha256, so a
        # `note` that is a number is contributor input. Before the fix
        # `md_cell` reached `str.replace` on it and raised `AttributeError`,
        # which `main` reports as `ledger_corrupt` (6) — "the record could not
        # be derived" — on the READ-ONLY verb, for a derivable record.
        data = self.forged()
        data["requests"][0]["note"] = 42
        data["requests"][0]["reason"] = None
        rendered = dogen.summary_markdown(data)
        self.assertIn("42", rendered)
        # And the table keeps its column count with a rendered non-string in it.
        row = [ln for ln in rendered.splitlines() if ln.startswith("| 3 |")]
        self.assertEqual(len(row), 1, rendered)
        self.assertEqual(row[0].count("|"), 4, row[0])


# --- U-05 (STATE-03) — contract 5.4's step status and reuse-prefix rule ------
#
# The derivation is PURE — events in, unresolved step ids out — so the whole
# rule is driven here with literal dicts and the lifecycle suite only has to
# prove the wiring. Every case carries the contract sentence it pins.


def planned(seq, steps, replaces=None, reuse=False):
    """A ``steps-planned`` event. ``steps`` is ``[(id, text, mode, stateful)]``."""
    return make_event(
        "steps-planned",
        seq=seq,
        steps=[
            {
                "id": step_id,
                "text": text,
                "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "mode": mode,
                "stateful": stateful,
            }
            for step_id, text, mode, stateful in steps
        ],
        replaces=replaces,
        reuse=reuse,
    )


DIGEST = hashlib.sha256(b"captured").hexdigest()


def recorded(seq, steps_seq, step_id, verdict, **payload):
    """A ``step-recorded`` event; ``exit_code`` defaults to 0."""
    payload.setdefault("exit_code", 0)
    return make_event(
        "step-recorded",
        seq=seq,
        steps_seq=steps_seq,
        step_id=step_id,
        verdict=verdict,
        **payload
    )


class TestStepTextHash(unittest.TestCase):
    """STATE-03 probe 4 — the text hash is sha256 over the UTF-8 encoding."""

    def test_the_hash_is_sha256_of_the_utf8_bytes(self):
        for text in ("build the html", "café — naïve", "  spaced  ", "日本語"):
            with self.subTest(text=text):
                self.assertEqual(
                    dogen.step_text_hash(text),
                    hashlib.sha256(text.encode("utf-8")).hexdigest(),
                )

    def test_nothing_is_normalised_case_folded_or_whitespace_collapsed(self):
        self.assertNotEqual(dogen.step_text_hash("Build"), dogen.step_text_hash("build"))
        self.assertNotEqual(dogen.step_text_hash("a b"), dogen.step_text_hash("a  b"))
        self.assertNotEqual(dogen.step_text_hash("a b"), dogen.step_text_hash("a\tb"))


class TestStepResolution(unittest.TestCase):
    """STATE-03 — ``pass``+sha, ``skipped``+reason, ``deviated``+exit 0+sha resolve;
    ``fail`` never. A verdict is not a resolution on its own."""

    def _unresolved(self, record_payload):
        plan = planned(0, [("s1", "one", "agent", False)])
        events = [plan, recorded(1, 0, "s1", **record_payload)]
        return dogen.unresolved_steps(events, plan)

    def test_the_resolution_table(self):
        cases = (
            ("pass with a digest resolves", {"verdict": "pass",
             "output_sha256": DIGEST}, []),
            ("pass without a digest does not", {"verdict": "pass"}, ["s1"]),
            ("skipped with a reason resolves", {"verdict": "skipped",
             "reason": "no network"}, []),
            ("skipped without a reason does not", {"verdict": "skipped"}, ["s1"]),
            ("deviated at exit 0 with a digest resolves", {"verdict": "deviated",
             "exit_code": 0, "output_sha256": DIGEST, "reason": "flag differed"}, []),
            ("deviated at a non-zero exit does not", {"verdict": "deviated",
             "exit_code": 3, "output_sha256": DIGEST, "reason": "flag differed"},
             ["s1"]),
            ("deviated without a digest does not", {"verdict": "deviated",
             "exit_code": 0, "reason": "flag differed"}, ["s1"]),
            ("fail at exit 0 never resolves", {"verdict": "fail", "exit_code": 0,
             "output_sha256": DIGEST, "reason": "wrong output"}, ["s1"]),
            ("fail at a non-zero exit never resolves", {"verdict": "fail",
             "exit_code": 1, "output_sha256": DIGEST}, ["s1"]),
            ("an unknown verdict never resolves", {"verdict": "ok",
             "output_sha256": DIGEST}, ["s1"]),
        )
        for label, payload, expected in cases:
            with self.subTest(case=label):
                self.assertEqual(self._unresolved(payload), expected, label)

    def test_a_record_naming_another_plans_seq_does_not_resolve_here(self):
        plan = planned(4, [("s1", "one", "agent", False)], replaces=None, reuse=False)
        events = [plan, recorded(5, 99, "s1", "pass", output_sha256=DIGEST)]
        self.assertEqual(dogen.unresolved_steps(events, plan), ["s1"])


class TestReusePrefixCarryForward(unittest.TestCase):
    """STATE-03 — evidence carries forward ONLY along consecutive reusing plans
    and ONLY for the longest prefix identical in ``(text_hash, mode, stateful)``.

    One differing element stops the walk for that step and for every step after
    it in the prefix, and only for them.
    """

    THREE = (
        ("s1", "one", "agent", False),
        ("s2", "two", "agent", False),
        ("s3", "three", "agent", True),
    )

    def _chain(self, later_steps, reuse, earlier_steps=None):
        """P1 with every step resolved, then P2 over ``later_steps``."""
        earlier = planned(0, earlier_steps or self.THREE)
        events = [earlier]
        for index, step in enumerate(earlier_steps or self.THREE):
            events.append(
                recorded(index + 1, 0, step[0], "pass", output_sha256=DIGEST)
            )
        later = planned(10, later_steps, replaces=0, reuse=reuse)
        events.append(later)
        return events, later

    def test_without_reuse_nothing_carries_forward(self):
        events, later = self._chain(self.THREE, reuse=False)
        self.assertEqual(dogen.unresolved_steps(events, later), ["s1", "s2", "s3"])

    def test_with_reuse_and_an_identical_prefix_everything_carries_forward(self):
        events, later = self._chain(self.THREE, reuse=True)
        self.assertEqual(dogen.unresolved_steps(events, later), [])

    def test_a_differing_element_breaks_that_step_and_every_step_after_it(self):
        cases = (
            ("the text differs at step 2", (
                ("s1", "one", "agent", False),
                ("s2", "TWO CHANGED", "agent", False),
                ("s3", "three", "agent", True),
            )),
            ("the mode differs at step 2", (
                ("s1", "one", "agent", False),
                ("s2", "two", "ta", False),
                ("s3", "three", "agent", True),
            )),
            ("statefulness differs at step 2", (
                ("s1", "one", "agent", False),
                ("s2", "two", "agent", True),
                ("s3", "three", "agent", True),
            )),
        )
        for label, steps in cases:
            with self.subTest(case=label):
                events, later = self._chain(steps, reuse=True)
                self.assertEqual(
                    dogen.unresolved_steps(events, later), ["s2", "s3"], label
                )

    def test_a_renamed_step_still_carries_because_the_tuple_has_no_id(self):
        renamed = (
            ("first", "one", "agent", False),
            ("s2", "two", "agent", False),
            ("s3", "three", "agent", True),
        )
        events, later = self._chain(renamed, reuse=True)
        self.assertEqual(dogen.unresolved_steps(events, later), [])

    def test_a_longer_later_plan_carries_only_the_prefix_it_shares(self):
        longer = self.THREE + (("s4", "four", "agent", False),)
        events, later = self._chain(longer, reuse=True)
        self.assertEqual(dogen.unresolved_steps(events, later), ["s4"])

    def test_t13_a_change_two_hops_back_is_still_seen_three_plans_later(self):
        """T13: P1 → P2 (reuse) → P3 (reuse) with step 3 changed in P2."""
        p2_steps = (
            ("s1", "one", "agent", False),
            ("s2", "two", "agent", False),
            ("s3", "three CHANGED", "agent", True),
        )
        p1 = planned(0, self.THREE)
        events = [p1]
        for index, step in enumerate(self.THREE):
            events.append(recorded(index + 1, 0, step[0], "pass", output_sha256=DIGEST))
        p2 = planned(10, p2_steps, replaces=0, reuse=True)
        p3 = planned(20, p2_steps, replaces=10, reuse=True)
        events += [p2, p3]
        # P3 == P2, so the first hop carries the whole prefix; the P2 → P1 hop
        # matches only steps 1–2, and the only evidence on the record is P1's.
        self.assertEqual(dogen.unresolved_steps(events, p3), ["s3"])

    def test_one_non_reusing_hop_stops_the_walk_for_everything(self):
        p1 = planned(0, self.THREE)
        events = [p1]
        for index, step in enumerate(self.THREE):
            events.append(recorded(index + 1, 0, step[0], "pass", output_sha256=DIGEST))
        p2 = planned(10, self.THREE, replaces=0, reuse=False)
        p3 = planned(20, self.THREE, replaces=10, reuse=True)
        events += [p2, p3]
        self.assertEqual(
            dogen.unresolved_steps(events, p3), ["s1", "s2", "s3"]
        )

    def test_evidence_recorded_against_the_middle_plan_carries_one_hop(self):
        p1 = planned(0, self.THREE)
        p2 = planned(10, self.THREE, replaces=0, reuse=True)
        p3 = planned(20, self.THREE, replaces=10, reuse=True)
        events = [p1, p2]
        for index, step in enumerate(self.THREE):
            events.append(recorded(index + 11, 10, step[0], "pass",
                                   output_sha256=DIGEST))
        events.append(p3)
        self.assertEqual(dogen.unresolved_steps(events, p3), [])

    def test_an_empty_plan_has_nothing_unresolved(self):
        plan = planned(0, ())
        self.assertEqual(dogen.unresolved_steps([plan], plan), [])

    def test_a_dangling_replaces_terminates_the_walk(self):
        plan = planned(5, self.THREE, replaces=999, reuse=True)
        self.assertEqual(
            dogen.unresolved_steps([plan], plan), ["s1", "s2", "s3"]
        )

    def test_a_replaces_cycle_terminates_the_walk(self):
        first = planned(0, self.THREE, replaces=10, reuse=True)
        second = planned(10, self.THREE, replaces=0, reuse=True)
        self.assertEqual(
            dogen.unresolved_steps([first, second], second), ["s1", "s2", "s3"]
        )


class TestStepTally(unittest.TestCase):
    """U-05/U-08 support — the tally both read surfaces print, or nothing."""

    def test_a_unit_with_no_step_plan_has_no_tally(self):
        self.assertIsNone(dogen.step_tally([]))

    def test_the_tally_counts_each_verdict_and_names_the_unresolved(self):
        events = [
            make_event(
                "steps-planned",
                seq=0,
                steps=[
                    {"id": "one", "text": "a", "text_hash": "h1", "mode": "run",
                     "stateful": False},
                    {"id": "two", "text": "b", "text_hash": "h2", "mode": "run",
                     "stateful": False},
                    {"id": "three", "text": "c", "text_hash": "h3", "mode": "run",
                     "stateful": False},
                ],
                replaces=None,
                reuse=False,
            ),
            make_event(
                "step-recorded",
                seq=1,
                step_id="one",
                steps_seq=0,
                verdict="pass",
                exit_code=0,
                output_sha256=STEP_DIGEST,
            ),
            make_event(
                "step-recorded",
                seq=2,
                step_id="two",
                steps_seq=0,
                verdict="skipped",
                reason="no network in this environment",
            ),
        ]
        tally = dogen.step_tally(events)
        self.assertEqual(tally["passed"], 1)
        self.assertEqual(tally["skipped"], 1)
        self.assertEqual(tally["skipped_reasons"], ["no network in this environment"])
        self.assertEqual(tally["unresolved"], ["three"])
        self.assertEqual(
            dogen.render_step_tally(tally),
            "passed 1 · skipped 1 (no network in this environment) · deviated 0 · "
            "unresolved 1: three",
        )


# U-08 — the paste-ready PR text for a fixed fixture, pinned byte for byte.
#
# Commit shas are the one thing pinning ``DOGEN_NOW`` and the git dates cannot
# fix: a ``tool_version`` bump changes the ledger bytes and therefore the tree
# the commit names. They are normalised to ``<sha7>`` and everything else is
# compared literally, so a later change to the WORDING — which is what this
# golden exists to protect — is a deliberate edit of this constant and never a
# silent drift.
#
# WR-11: every contributor-controlled value here is escaped for the position it
# lands in. The reviewer edit's note therefore reads as ONE line — `.dogen/` is
# committed, so a note is ordinary contributor input, and this document is
# documented as text a reviewer pastes into a PR, where a note free to contain
# a blank line and a `## Provenance` of its own is a note free to forge the
# report. The characters stay visible; only the line breaks are collapsed.
GOLDEN_SUMMARY_MD = """# Demo

## Files changed

- `reference/fixture.rst`

## Intent and audience

- **Intent:** reference
- **Audience:** TAs onboarding to the docs repo

## Recorded requests

| seq | disposition | request |
| --- | --- | --- |
| 4 | resolved | mention the \\| flag<br>and a second line |

## Reviewer edits

**seq 5** — hand edit | with a pipe and a second line

## Model

`fixture-model` (origin: `configured`)

## Provenance

record: verify ok at <sha7> (19 checks, 0 warn, 0 fail) · page: current
"""


class TestSummaryGolden(TempRepoTestCase):
    """U-08 — ``summary --md`` over a fixed fixture equals the checked-in text."""

    def dogen(self, *args, **kwargs):
        env = dict(self.env)
        env["DOGEN_TEST_HOOKS"] = "1"
        env["DOGEN_NOW"] = "2026-01-01T00:00:00+00:00"
        env["GIT_AUTHOR_DATE"] = "2026-01-01T00:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = "2026-01-01T00:00:00+00:00"
        proc = subprocess.run(
            [sys.executable, str(DOGEN_PATH)] + list(args),
            cwd=str(self.repo),
            env=env,
            capture_output=True,
            text=True,
            input=kwargs.get("stdin"),
        )
        if kwargs.get("check", True):
            self.assertEqual(proc.returncode, 0, "%s\n%s" % (args, proc.stderr))
        return proc

    def build_fixture(self):
        """`unit new` -> `signoff` -> `draft` -> `steer` -> `edits` -> `accept`."""
        (self.repo / "docs" / "reference").mkdir(parents=True)
        (self.repo / "docs" / "index.md").write_text("# Docs\n", encoding="utf-8")
        # V17 asks git whether the transient staging path is ignored. It is the
        # repository's pattern, not the tool's, so the fixture carries it — a
        # golden that reported a missing .gitignore would be pinning the
        # fixture's hygiene rather than the unit's provenance.
        (self.repo / ".gitignore").write_text(".dogen/staging/\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "docs")
        self.dogen(
            "unit", "new", "fixture-unit",
            "--intent", "reference",
            "--audience", "TAs onboarding to the docs repo",
            "--title", "Demo",
            "--target", "reference/fixture.rst",
            "--body-file", "-",
            stdin="# Plan\n\nAn outline.\n",
        )
        self.dogen("signoff", "fixture-unit")
        staged = self.repo / ".dogen/staging/fixture-unit/draft/reference"
        staged.mkdir(parents=True)
        (staged / "fixture.rst").write_text(
            "Fixture\n=======\n\nThe drafted body.\n", encoding="utf-8"
        )
        self.dogen(
            "draft", "fixture-unit",
            ".dogen/staging/fixture-unit/draft/reference/fixture.rst",
            "--model", "fixture-model", "--model-origin", "configured",
        )
        self.dogen(
            "steer", "fixture-unit", "--note-file", "-",
            stdin="mention the | flag\nand a second line",
        )
        (self.repo / "docs" / "reference" / "fixture.rst").write_text(
            "Fixture\n=======\n\nEdited by hand.\n", encoding="utf-8"
        )
        self.dogen(
            "edits", "fixture-unit", "--note-file", "-",
            stdin="hand edit | with a pipe\nand a second line",
        )
        self.dogen(
            "review", "fixture-unit", "--verdict", "accept",
            "--note", "ship it", "--resolves", "4",
        )

    def test_summary_md_matches_the_golden(self):
        self.build_fixture()
        proc = self.dogen("summary", "fixture-unit", "--md")
        rendered = re.sub(r"\b[0-9a-f]{7}\b", "<sha7>", proc.stdout)
        self.assertEqual(rendered, GOLDEN_SUMMARY_MD)

    def test_the_record_half_names_the_verdict_and_the_short_head_sha(self):
        self.build_fixture()
        proc = self.dogen("summary", "fixture-unit")
        line = [row for row in proc.stdout.splitlines() if row.startswith("record: ")][0]
        head = self.git("rev-parse", "--short=7", "HEAD").stdout.strip()
        self.assertIn("verify ok", line)
        self.assertIn(head, line)

    def test_the_phase_16_placeholder_is_gone(self):
        self.build_fixture()
        for flags in ((), ("--md",), ("--json",)):
            proc = self.dogen("summary", "fixture-unit", *flags)
            self.assertNotIn("verify has not run", proc.stdout)

    def test_a_failing_record_names_the_failure(self):
        """A V5–V13 failure, which is the only kind `summary` can ever render.

        `summary` opens with the readers' preamble, and stage a's chain and
        committed-prefix rows ARE V2/V3/V4: a broken chain or a rewritten prefix
        refuses at exit 6 before a single check runs. What stage a does not
        check is contract 5.4's derivation invariants — so the record here is
        re-linked and COMMITTED, leaving a ledger that is structurally perfect
        and semantically wrong, which is exactly what V5 is for.
        """
        self.build_fixture()
        ledger = self.repo / ".dogen/units/fixture-unit/ledger.jsonl"
        events = [
            json.loads(row)
            for row in ledger.read_text(encoding="utf-8").split("\n")
            if row
        ]
        for event in events:
            if event.get("kind") == "signoff":
                event["plan_hash"] = "0" * 64
        lines = dogen.chain_lines(events)
        ledger.write_text("".join(row + "\n" for row in lines), encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "a hand repair of the record")

        proc = self.dogen("summary", "fixture-unit", check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        line = [row for row in proc.stdout.splitlines() if row.startswith("record: ")]
        self.assertTrue(line, proc.stderr)
        self.assertIn("verify fail", line[0])
        self.assertIn("V5", line[0])

    def test_summary_takes_exactly_one_filesystem_snapshot(self):
        """`cmd_summary`'s docstring promise, now that it also verifies."""
        self.build_fixture()
        events, snapshot, state = dogen.unit_view(self.repo, "fixture-unit")
        with mock.patch.object(dogen, "read_fs", wraps=dogen.read_fs) as spy:
            dogen.summary_data(self.repo, "fixture-unit", events, snapshot, state)
        self.assertEqual(spy.call_count, 0, "run_verify took a second snapshot")

    def test_the_golden_never_claims_that_steering_was_applied(self):
        self.build_fixture()
        proc = self.dogen("summary", "fixture-unit", "--md")
        self.assertNotIn("steering applied", proc.stdout)
        self.assertIn("## Recorded requests", proc.stdout)


# --- U-10 — the tool's own guards: line budget, 3.9 hazards, packaging -------
#
# VERB-09's budget is a REVIEW TRIGGER, not a design goal (rev8 section 2.1):
# behaviour is never deleted to fit it. The guard FAILS above ``BUDGET_FAIL`` and
# REPORTS above ``BUDGET_ANNOTATE``, mirroring what phase-18 CI's size-guard job
# will annotate and fail on, so the number is visible here first.
#
# Recalibrated at 16-07 by the author, at a blocking-human checkpoint, after the
# finished file measured 4,748 lines against rev8's 925-line phase-16 slice — a
# 5.13x miss in the ESTIMATE, not in the file. rev8's own 1,000/1,300 ratios are
# scaled by that measured factor; the alternative was deleting behaviour to fit,
# which section 2.1 and the plan both forbid. ``.planning/REQUIREMENTS.md``
# VERB-09 carries the same two numbers and is checked against them below, so the
# guard and the requirement phase-18 CI reads cannot drift apart.
#
# Recalibrated again at 17-08 (maintainer checkpoint, 2026-09-15),
# which supersedes the 2026-09-14 temporary lift of the failing threshold. The
# measurement: after plans 17-01/05/06/07 landed, ``dogen`` was 7,445 lines —
# already 745 past the 6,700 the 16-07 pair set, so returning to it meant
# deleting landed, tested behaviour — and the remaining ``verify`` block
# projected to ~8,090 lines (range 8,046-8,210) at this phase's own measured
# 1.61x estimate-to-actual ratio, crossing the temporary 8,000 too. The pair
# moves to 8,000 annotate / 9,500 fail: the trigger is restored to a number
# that carries information (5,000 had fired on every run since 17-01) and the
# projected v2.0 ceiling of ~8,600, review-fix allowance included, stays below
# the failing threshold.
#
# Recalibrated a third time at 18-13 (maintainer checkpoint, 2026-09-18,
# checkpoint), raised by WR-07 in ``18-REVIEW.md``. The measurement: ``dogen``
# is 9,472 lines against the 8,000 / 9,500 pair, so the trigger has fired on
# every run for 263 commits — the same information-free state the 17-08 note
# above gives as its own reason for moving off 5,000 — and only 28 lines of
# headroom remain below the failing threshold. The pair moves to 10,000
# annotate / 12,000 fail, applying the +7.5% / +27.6% offsets 17-08 itself
# used. WR-07's proposed 9,500 / 11,000 was rejected because it restores the
# annotate verdict after 29 lines of growth — the very state being escaped.
# ``dogen`` has not changed in 134 commits and v2.0 is feature-complete, so
# 528 lines to the trigger and 2,528 to the failing threshold is headroom, not
# over-provisioning.
BUDGET_ANNOTATE = 10000
BUDGET_FAIL = 12000

# The 3.9 runtime hazards ``ast.parse(feature_version=(3, 9))`` cannot see
# (RESEARCH P-10). It *does* reject ``match`` and ``except*`` as syntax errors,
# but ``int | None`` in a runtime position and ``@dataclass(slots=True)`` parse
# cleanly on every version and only raise TypeError when the line executes on
# 3.9. These names are what makes a ``|`` read as a type union rather than as an
# integer flag: ``dogen`` legitimately ORs bit flags and unions sets.
_TYPE_NAMES = frozenset(
    {
        "Any", "AnyStr", "BinaryIO", "Callable", "Dict", "FrozenSet", "IO",
        "Iterable", "Iterator", "List", "Mapping", "Optional", "Path",
        "Sequence", "Set", "TextIO", "Tuple", "Type", "Union",
        "bool", "bytearray", "bytes", "complex", "dict", "float", "frozenset",
        "int", "list", "object", "set", "str", "tuple", "type",
    }
)


def _annotation_node_ids(tree):
    """Ids of every node sitting inside an annotation — where PEP 604 is free.

    ``from __future__ import annotations`` keeps annotations unevaluated strings
    at runtime, so ``x: int | None`` never executes on 3.9. Anywhere else, the
    same expression is a TypeError the moment the line runs.
    """
    inside = set()
    for node in ast.walk(tree):
        annotations = []
        if isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
        elif isinstance(node, ast.arg) and node.annotation is not None:
            annotations.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                annotations.append(node.returns)
        for annotation in annotations:
            for inner in ast.walk(annotation):
                inside.add(id(inner))
    return inside


def _reads_as_a_type(node):
    """True when ``node`` reads as a type rather than as an integer or a set."""
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in _TYPE_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _TYPE_NAMES
    if isinstance(node, ast.Subscript):
        return _reads_as_a_type(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _reads_as_a_type(node.left) or _reads_as_a_type(node.right)
    return False


def type_unions_outside_annotations(source):
    """Line numbers of every ``X | Y`` TYPE union in a runtime position.

    Deliberately narrower than "any ``BinOp`` with ``BitOr``": that scan would
    flag three correct 3.9 lines in ``dogen`` — ``os.O_CREAT | os.O_RDWR``,
    ``fcntl.LOCK_EX | fcntl.LOCK_NB`` and a set union — and a guard that cries
    wolf on correct code gets relaxed rather than obeyed.
    """
    tree = ast.parse(source)
    inside = _annotation_node_ids(tree)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.BitOr):
            continue
        if id(node) in inside:
            continue
        if _reads_as_a_type(node.left) or _reads_as_a_type(node.right):
            hits.append(node.lineno)
    return sorted(hits)


def bitwise_or_lines(source):
    """Line numbers of every ``|`` BinOp, type union or not."""
    return sorted(
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)
    )


def pattern_match_lines(source):
    """Line numbers of every ``match`` statement (a 3.10 construct)."""
    match_node = getattr(ast, "Match", ())
    return sorted(
        node.lineno for node in ast.walk(ast.parse(source))
        if isinstance(node, match_node)
    )


def dataclass_slots_lines(source):
    """Line numbers of every ``dataclass(...)`` call carrying ``slots=``."""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "dataclass":
            continue
        if any(keyword.arg == "slots" for keyword in node.keywords):
            hits.append(node.lineno)
    return sorted(hits)


def budget_verdict(lines):
    """``"ok"``, ``"annotate"`` or ``"fail"`` for a line count, per VERB-09.

    Extracted from the assertion so the ANNOTATE branch is exercised at its
    boundary rather than only on the days ``dogen`` happens to sit above the
    trigger — a reporting path that runs only by accident is untested code.

    The two thresholds are deliberately asymmetric, matching the plan's verify
    block: the review trigger is strictly *above* ``BUDGET_ANNOTATE``, while the
    failing threshold is reached *at* ``BUDGET_FAIL``.
    """
    if lines >= BUDGET_FAIL:
        return "fail"
    if lines > BUDGET_ANNOTATE:
        return "annotate"
    return "ok"


class TestStageAReportMode(TempRepoTestCase):
    """U-09 — ``classify_stage_a``'s report mode, case by case against the raise.

    Phase 16 left the classification complete and the REPORTING missing: the
    two situations ``resume`` exists to resolve are the two the classifier
    raises for, so wiring ``cmd_resume`` through the ordinary front door makes
    ``dogen resume <id>`` refuse with the hint ``dogen resume <id>`` (RESEARCH
    Pitfall 6). The fix is a third mode, not a second classifier — so every
    case below is driven through BOTH modes and the two answers are asserted to
    agree. That equality is the whole point: it is what keeps the reporting
    surface from drifting away from the refusal surface on the one code path
    nobody exercises until something has already gone wrong.
    """

    UNIT = "u"

    def build(self, batch=2, files=((".dogen/units/u/unit.md", b"AFTER", None),)):
        """A unit whose opening is committed and whose ``batch`` events pend.

        Returns ``(lines, manifest_path)`` where ``lines`` is the whole chain;
        ``lines[:2]`` are committed and ``lines[2:]`` are the pending batch.
        """
        events = opening(self.UNIT) + [steering(2 + i) for i in range(batch)]
        lines = dogen.chain_lines(events)
        ledger = self.repo / ".dogen" / "units" / self.UNIT / "ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("".join(line + "\n" for line in lines[:2]), encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "opening")

        pending = self.repo / ".dogen" / "staging" / self.UNIT / "pending"
        pending.mkdir(parents=True, exist_ok=True)
        entries = []
        for path, after, before in files:
            self._write(pending / "after" / path, after)
            if before is None:
                self._write(pending / "before" / (path + ".absent"), b"")
            else:
                self._write(pending / "before" / path, before)
            entries.append(
                {
                    "path": path,
                    "before_sha": None if before is None else dogen.sha256_bytes(before),
                    "after_sha": dogen.sha256_bytes(after),
                }
            )
        manifest = pending / "manifest.json"
        manifest.write_text(
            json.dumps({"events": lines[2:], "files": entries}, sort_keys=True),
            encoding="utf-8",
        )
        return lines, manifest

    def _write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def append_tail(self, lines, partial=""):
        """Put ``lines`` (plus an optional partial final line) after the commit."""
        ledger = self.repo / ".dogen" / "units" / self.UNIT / "ledger.jsonl"
        text = ledger.read_text(encoding="utf-8")
        ledger.write_text(
            text + "".join(line + "\n" for line in lines) + partial, encoding="utf-8"
        )

    def report(self):
        return dogen.classify_stage_a(self.repo, self.UNIT, report_only=True)

    def raised(self):
        """The reason the raising mode raises here, or ``None`` when it returns."""
        try:
            dogen.classify_stage_a(self.repo, self.UNIT, write_mode=False)
        except dogen.Refusal as refusal:
            return refusal.reason
        return None

    def both(self, situation, reason, detail=None):
        """Assert the report mode's answer and the raising mode's agree."""
        found = self.report()
        self.assertEqual(found["situation"], situation)
        self.assertEqual(found["reason"], reason)
        if detail is not None:
            self.assertEqual(found["detail"], detail)
        self.assertEqual(self.raised(), reason)
        return found

    # --- the resumable row ---------------------------------------------------

    def test_u09_a_tail_that_is_a_byte_prefix_is_resumable(self):
        lines, _ = self.build(batch=2)
        self.append_tail(lines[2:3])
        found = self.both("uncommitted_tail", "uncommitted_tail")
        self.assertEqual(found["tail"], lines[2:3])
        self.assertEqual(found["seqs"], [2])

    def test_u09_the_whole_batch_with_the_commit_missing_is_resumable(self):
        lines, _ = self.build(batch=2)
        self.append_tail(lines[2:])
        found = self.both("uncommitted_tail", "uncommitted_tail")
        self.assertEqual(found["seqs"], [2, 3])

    def test_u09_a_truncated_final_line_is_resumable(self):
        lines, _ = self.build(batch=2)
        self.append_tail(lines[2:3], partial=lines[3][:20])
        found = self.both("uncommitted_tail", "uncommitted_tail")
        self.assertEqual(found["partial"], lines[3][:20])
        self.assertEqual(found["seqs"], [2, 3])

    def test_u09_a_zero_file_manifest_classifies_and_lists_no_files(self):
        lines, _ = self.build(batch=2, files=())
        self.append_tail(lines[2:3])
        found = self.both("uncommitted_tail", "uncommitted_tail")
        self.assertEqual(found["files"], [])

    # --- the unsupported row, one case per detail code -----------------------

    def test_u09_one_differing_byte_is_tail_unknown(self):
        lines, manifest = self.build(batch=2)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["events"] = payload["events"][1:]
        manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        self.append_tail(lines[2:3])
        self.both("recovery_unsupported", "recovery_unsupported", "tail_unknown")

    def test_u09_a_tail_with_no_manifest_is_no_material(self):
        lines, manifest = self.build(batch=2)
        shutil.rmtree(str(manifest.parent))
        self.append_tail(lines[2:3])
        self.both("recovery_unsupported", "recovery_unsupported", "no_material")

    def test_u09_a_copy_failing_its_digest_is_material_invalid(self):
        lines, manifest = self.build(batch=2)
        copy = manifest.parent / "after" / ".dogen" / "units" / "u" / "unit.md"
        copy.write_bytes(b"TAMPERED")
        self.append_tail(lines[2:3])
        self.both("recovery_unsupported", "recovery_unsupported", "material_invalid")

    def test_u09_a_non_canonical_event_line_is_event_invalid(self):
        lines, manifest = self.build(batch=2)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["events"][0] = " " + payload["events"][0]
        manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        self.append_tail(lines[2:3])
        self.both("recovery_unsupported", "recovery_unsupported", "event_invalid")

    def test_u09_a_rewritten_committed_prefix_is_diverged(self):
        lines, _ = self.build(batch=2)
        ledger = self.repo / ".dogen" / "units" / self.UNIT / "ledger.jsonl"
        text = ledger.read_text(encoding="utf-8").splitlines()
        text[1] = text[1].replace("2026-01-01", "2026-01-02")
        ledger.write_text("".join(line + "\n" for line in text), encoding="utf-8")
        self.both("ledger_diverged", "ledger_diverged")

    # --- the rows that are not refusals --------------------------------------

    def test_u09_no_pending_and_no_tail_reports_clean_and_no_reason(self):
        self.build(batch=2)
        shutil.rmtree(str(self.repo / ".dogen" / "staging"))
        found = self.both("clean", None)
        self.assertEqual(found["files"], [])
        self.assertFalse(found["deleted"])

    def test_u09_report_mode_never_deletes_what_write_mode_would(self):
        """The write boundary: report mode is read-only by construction."""
        lines, manifest = self.build(batch=2)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["events"] = ["not in this ledger at all"]
        manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        found = self.report()
        self.assertEqual(found["situation"], "manifest_without_events")
        self.assertIsNone(found["reason"])
        self.assertFalse(found["deleted"])
        self.assertTrue(manifest.exists())

    # --- the per-file classifier ---------------------------------------------

    def test_u09_the_report_classifies_every_manifest_file(self):
        lines, _ = self.build(
            batch=2,
            files=(
                ("done.rst", b"AFTER", b"BEFORE"),
                ("recoverable.rst", b"AFTER", b"BEFORE"),
                ("absent.rst", b"AFTER", None),
                ("unexpected.rst", b"AFTER", b"BEFORE"),
            ),
        )
        self._write(self.repo / "done.rst", b"AFTER")
        self._write(self.repo / "recoverable.rst", b"BEFORE")
        self._write(self.repo / "unexpected.rst", b"AUTHOR EDIT")
        self.append_tail(lines[2:3])
        found = self.report()
        self.assertEqual(
            [(row["path"], row["class"]) for row in found["files"]],
            [
                ("done.rst", "done"),
                ("recoverable.rst", "recoverable"),
                ("absent.rst", "recoverable"),
                ("unexpected.rst", "unexpected"),
            ],
        )
        row = found["files"][3]
        self.assertEqual(row["intended"], b"AFTER")
        self.assertEqual(row["disk"], b"AUTHOR EDIT")


class TestClassifyFile(unittest.TestCase):
    """U-09 — contract 5.8's three per-file classes, as a pure function.

    One definition of ``done`` / ``recoverable`` / ``unexpected``, shared by
    ``resume``'s pass 1 and the findings renderer, so the two surfaces can
    never hold different opinions about the same file.
    """

    @staticmethod
    def entry(before, after):
        return {
            "path": "p",
            "before_sha": None if before is None else dogen.sha256_bytes(before),
            "after_sha": dogen.sha256_bytes(after),
        }

    def test_disk_equal_to_the_after_digest_is_done(self):
        self.assertEqual(
            dogen.classify_file(self.entry(b"B", b"A"), b"A", b"A"), "done"
        )

    def test_disk_equal_to_the_before_digest_is_recoverable(self):
        self.assertEqual(
            dogen.classify_file(self.entry(b"B", b"A"), b"A", b"B"), "recoverable"
        )

    def test_absent_with_a_null_before_digest_is_recoverable(self):
        self.assertEqual(
            dogen.classify_file(self.entry(None, b"A"), b"A", None), "recoverable"
        )

    def test_anything_else_is_unexpected(self):
        self.assertEqual(
            dogen.classify_file(self.entry(b"B", b"A"), b"A", b"X"), "unexpected"
        )

    def test_absent_with_a_recorded_before_digest_is_unexpected(self):
        self.assertEqual(
            dogen.classify_file(self.entry(b"B", b"A"), b"A", None), "unexpected"
        )

    def test_equal_before_and_after_digests_report_done_not_recoverable(self):
        """``done`` is tested first, and that order is the answer here.

        Calling it ``recoverable`` would schedule a placement that cannot
        change a byte, and pass 2 would report work it did not do.
        """
        self.assertEqual(
            dogen.classify_file(self.entry(b"A", b"A"), b"A", b"A"), "done"
        )

    def test_the_three_classes_are_three_distinct_strings(self):
        """Vacuous-pass guard: one collapsed class would pass every row above."""
        answers = {
            dogen.classify_file(self.entry(b"B", b"A"), b"A", b"A"),
            dogen.classify_file(self.entry(b"B", b"A"), b"A", b"B"),
            dogen.classify_file(self.entry(b"B", b"A"), b"A", b"X"),
        }
        self.assertEqual(answers, {"done", "recoverable", "unexpected"})


class TestAdoptRevisedManifest(TempRepoTestCase):
    """U-11 — the revised-manifest builder and the complete-batch-set rule.

    ``resume --adopt`` is the ONLY code path in this tool that writes a
    manifest from existing data. Everything else publishes one from bytes it
    just produced, so every other manifest is trustworthy by construction and
    this one is not. These cases drive the rule from literal dicts, where the
    bash suite can only reach it through a rejecting hook and a real crash.
    """

    ENTRIES = [
        {"path": "docs/a.rst", "before_sha": None, "after_sha": "a" * 64},
        {"path": "docs/b.rst", "before_sha": "b" * 64, "after_sha": "c" * 64},
    ]

    def rows(self, *paths):
        """Classification rows shaped like ``classify_manifest_files``'."""
        return [
            {"path": path, "class": "unexpected", "intended": b"", "disk": b"HOOK"}
            for path in paths
        ]

    def test_u11_an_adopted_entry_moves_its_after_copy_and_keeps_its_before(self):
        revised = dogen.revise_manifest_entries(self.ENTRIES, self.rows("docs/b.rst"))
        adopted = revised[1]
        self.assertEqual(adopted["after_path"], "adopt/docs/b.rst")
        self.assertEqual(adopted["after_sha"], dogen.sha256_bytes(b"HOOK"))
        # The before digest is what makes the entry classifiable afterwards;
        # rewriting it would erase what the file held before the transition.
        self.assertEqual(adopted["before_sha"], "b" * 64)

    def test_u11_every_other_entry_is_carried_over_byte_for_byte(self):
        revised = dogen.revise_manifest_entries(self.ENTRIES, self.rows("docs/b.rst"))
        self.assertEqual(revised[0], self.ENTRIES[0])
        self.assertNotIn("after_path", revised[0])
        # And the input is not mutated: the original `after/` copies stay the
        # evidence of what the interrupted verb intended.
        self.assertEqual(self.ENTRIES[1]["after_sha"], "c" * 64)

    def test_u11_the_revised_set_is_the_COMPLETE_batch_file_set(self):
        """Contract 5.8: unchanged paths keep recorded digests, adopted ones current."""
        revised = dogen.revise_manifest_entries(self.ENTRIES, self.rows("docs/b.rst"))
        files = [
            {"path": entry["path"], "sha256": entry["after_sha"]} for entry in revised
        ]
        self.assertEqual([row["path"] for row in files], ["docs/a.rst", "docs/b.rst"])
        self.assertEqual(files[0]["sha256"], "a" * 64)
        self.assertEqual(files[1]["sha256"], dogen.sha256_bytes(b"HOOK"))

    def test_u11_adopting_nothing_returns_the_entries_unchanged(self):
        self.assertEqual(dogen.revise_manifest_entries(self.ENTRIES, []), self.ENTRIES)

    def test_u11_basis_path_inverts_the_join_cmd_generate_makes(self):
        """CR-01 — the manifest and a basis event do not speak the same paths.

        `cmd_generate` builds the manifest by joining `DOCS_ROOT` onto each
        signed target; every basis event — the signoff's `targets[]`, the
        generation's `files[]`, `cmd_edits`' `complete_basis_set` — records the
        unjoined target. V13 compares those two sets DIRECTLY, so an `--adopt`
        that recorded the manifest form made every signed target look dropped
        and left the unit `ledger_corrupt` on the next `verify`.
        """
        self.assertEqual(
            dogen.basis_path(str(self.repo), "u", "docs/reference/a.rst"),
            "reference/a.rst",
        )
        self.assertEqual(
            dogen.basis_path(str(self.repo), "u", os.path.join("docs", "a.rst")),
            "a.rst",
        )

    def test_u11_basis_path_refuses_an_entry_with_no_basis_form(self):
        """The `unit.md` of an interrupted `--re-sign`, asserted not assumed.

        `resume_adopt`'s first arm already refuses that batch (its last event is
        a signoff), so this is unreachable today — which is exactly why it is
        driven here. Emitting `../.dogen/units/u/unit.md` as a target would put
        a path no verb can resolve into an append-only record.
        """
        for path in (
            ".dogen/units/u/unit.md",
            "README.md",
            "docsy/a.rst",
            "docs/",
            "docs",
        ):
            with self.subTest(path=path):
                with self.assertRaises(dogen.Refusal) as caught:
                    dogen.basis_path(str(self.repo), "u", path)
                self.assertEqual(caught.exception.reason, "recovery_unsupported")
                self.assertIn("material_invalid", caught.exception.detail)
                self.assertIn("dogen resume u --overwrite", caught.exception.hint)
                self.assertIn("dogen show u", caught.exception.hint)
                self.assertNotIn("--discard", caught.exception.hint)

    def test_u11_after_copy_resolves_both_shapes(self):
        pending = "/p"
        self.assertEqual(
            dogen.after_copy(pending, {"path": "docs/a.rst"}),
            os.path.join("/p", "after", "docs/a.rst"),
        )
        self.assertEqual(
            dogen.after_copy(
                pending, {"path": "docs/a.rst", "after_path": "adopt/docs/a.rst"}
            ),
            os.path.join("/p", "adopt", "docs", "a.rst"),
        )

    def test_u11_adopt_referenced_sees_only_a_copy_under_adopt(self):
        self.assertFalse(dogen.adopt_referenced(None))
        self.assertFalse(dogen.adopt_referenced({"files": self.ENTRIES}))
        revised = dogen.revise_manifest_entries(self.ENTRIES, self.rows("docs/b.rst"))
        self.assertTrue(dogen.adopt_referenced({"files": revised}))

    def write_manifest(self, files):
        """Publish a manifest by hand, the way only adopt otherwise would."""
        pending = self.repo / ".dogen" / "staging" / "u" / "pending"
        pending.mkdir(parents=True, exist_ok=True)
        (pending / "manifest.json").write_text(
            json.dumps({"events": ["{}"], "files": files}), encoding="utf-8"
        )
        return dogen.read_manifest(str(self.repo), "u")

    def test_u11_read_manifest_holds_after_path_to_the_destination_rule(self):
        """T-17-30: the re-read is only a check if the reader checks THIS field.

        ``after_path`` is joined onto ``pending/`` and then READ as the bytes a
        placement writes, so an absolute path or a parent-directory segment
        there is the same hazard as one in ``path`` — and adopt is the one
        writer that could introduce it.
        """
        ok = self.write_manifest(
            [{"path": "docs/a.rst", "before_sha": None, "after_sha": "a" * 64,
              "after_path": "adopt/docs/a.rst"}]
        )
        self.assertIsNotNone(ok)
        for bad in ("/etc/passwd", "../../etc/passwd", "adopt/../../etc/passwd", ""):
            with self.subTest(after_path=bad):
                self.assertIsNone(
                    self.write_manifest(
                        [{"path": "docs/a.rst", "before_sha": None,
                          "after_sha": "a" * 64, "after_path": bad}]
                    ),
                    "an after_path of %r must be rejected" % bad,
                )


class TestRecoveryCommitNaming(unittest.TestCase):
    """U-11 — the phase a recovered commit carries, read off the batch itself.

    ``resume`` has only the batch to go on; the verb that started the
    transition is long gone. Naming the commit from the record is what keeps a
    recovered transition findable by the same ``git log`` that finds every
    other one.
    """

    def phases_perform_write_uses(self):
        """Every literal `phase` argument in the file's `perform_write` calls."""
        source = DOGEN_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        found = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None)
            if name != "perform_write" or len(node.args) < 3:
                continue
            for literal in ast.walk(node.args[2]):
                if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                    found.add(literal.value)
        return found

    def test_u11_every_phase_it_can_name_is_one_a_verb_already_uses(self):
        """A recovery must not invent a phase word no other commit carries."""
        used = self.phases_perform_write_uses()
        self.assertTrue(used, "the scan found no perform_write phase literals")
        self.assertTrue(
            set(dogen.PHASE_BY_KIND.values()) <= used,
            "recovery would name a phase no verb uses: %s"
            % sorted(set(dogen.PHASE_BY_KIND.values()) - used),
        )
        self.assertIn("re-signed", used)

    def test_u11_the_batch_last_kind_names_the_phase(self):
        self.assertEqual(
            dogen.recovery_phase([{"kind": "ledger"}, {"kind": "unit-declared"}]),
            "declared",
        )
        self.assertEqual(dogen.recovery_phase([{"kind": "generation"}]), "drafted")
        self.assertEqual(dogen.recovery_phase([{"kind": "reviewer-edit"}]),
                         "reviewer-edited")

    def test_u11_a_re_sign_is_the_one_composite(self):
        """Neither kind says `re-signed` on its own; the pair does."""
        self.assertEqual(
            dogen.recovery_phase([{"kind": "unit-edited"}, {"kind": "signoff"}]),
            "re-signed",
        )
        self.assertEqual(dogen.recovery_phase([{"kind": "unit-edited"}]), "edited")
        self.assertEqual(dogen.recovery_phase([{"kind": "signoff"}]), "signed-off")

    def test_u11_an_unknown_kind_never_crashes_the_recovery(self):
        self.assertEqual(dogen.recovery_phase([{"kind": "void"}]), "resumed")
        self.assertEqual(dogen.recovery_phase([]), "resumed")


class TestTruncatePartialLine(TempRepoTestCase):
    """U-11 — pass 2 step 1: the half-written final line, and only it."""

    def ledger(self, text):
        path = self.repo / "ledger.jsonl"
        path.write_text(text, encoding="utf-8")
        return path

    def test_u11_a_fragment_is_dropped_and_the_whole_lines_are_kept(self):
        path = self.ledger('{"a":1}\n{"b":2}\n{"c":')
        dogen.truncate_partial_line(str(path))
        self.assertEqual(path.read_text(encoding="utf-8"), '{"a":1}\n{"b":2}\n')

    def test_u11_a_file_that_ends_in_lf_is_left_alone(self):
        path = self.ledger('{"a":1}\n')
        dogen.truncate_partial_line(str(path))
        self.assertEqual(path.read_text(encoding="utf-8"), '{"a":1}\n')

    def test_u11_a_file_that_is_all_fragment_becomes_empty(self):
        """Seq 0 was never completely written, so there is no record yet."""
        path = self.ledger('{"a":')
        dogen.truncate_partial_line(str(path))
        self.assertEqual(path.read_text(encoding="utf-8"), "")


class TestLineBudget(unittest.TestCase):
    """U-10 — VERB-09's line budget, measured rather than estimated."""

    def test_the_file_is_below_the_failing_threshold(self):
        lines = len(DOGEN_PATH.read_text(encoding="utf-8").splitlines())
        verdict = budget_verdict(lines)
        if verdict == "annotate":
            sys.stderr.write(
                "\nANNOTATE: dogen is %d lines, over VERB-09's %d-line review "
                "trigger (the guard fails at %d)\n"
                % (lines, BUDGET_ANNOTATE, BUDGET_FAIL)
            )
            sys.stderr.flush()
        self.assertNotEqual(
            verdict,
            "fail",
            "dogen is %d lines, at or above VERB-09's %d-line failing threshold; "
            "the budget is a review trigger, so recalibrate it deliberately "
            "rather than deleting behaviour to fit (rev8 section 2.1)"
            % (lines, BUDGET_FAIL),
        )

    def test_the_review_trigger_sits_below_the_failing_threshold(self):
        self.assertLess(BUDGET_ANNOTATE, BUDGET_FAIL)

    def test_a_count_under_the_trigger_is_silent(self):
        self.assertEqual(budget_verdict(0), "ok")
        self.assertEqual(budget_verdict(BUDGET_ANNOTATE), "ok")

    def test_a_count_past_the_trigger_is_reported_but_still_passes(self):
        self.assertEqual(budget_verdict(BUDGET_ANNOTATE + 1), "annotate")
        self.assertEqual(budget_verdict(BUDGET_FAIL - 1), "annotate")

    def test_a_count_at_or_past_the_failing_threshold_fails(self):
        self.assertEqual(budget_verdict(BUDGET_FAIL), "fail")
        self.assertEqual(budget_verdict(BUDGET_FAIL + 1), "fail")

    def test_the_measured_file_is_the_one_the_guard_reports_on(self):
        """Vacuous-pass guard: an empty read would pass every threshold."""
        self.assertGreater(len(DOGEN_PATH.read_text(encoding="utf-8").splitlines()), 100)

    def test_the_guard_agrees_with_the_recorded_requirement(self):
        """VERB-09 is the number phase-18 CI's size-guard job will read.

        ``.planning/`` lives on the ``gsd`` branch only, so this degrades to a
        skip wherever the requirement register is not checked out.
        """
        register = ROOT / ".planning" / "REQUIREMENTS.md"
        if not register.is_file():
            self.skipTest("no .planning/REQUIREMENTS.md on this branch")
        stated = [
            line for line in register.read_text(encoding="utf-8").splitlines()
            if "**VERB-09**" in line
        ]
        self.assertEqual(len(stated), 1, "VERB-09 must be stated exactly once")
        numbers = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", stated[0])]
        self.assertIn(BUDGET_ANNOTATE, numbers, stated[0])
        self.assertIn(BUDGET_FAIL, numbers, stated[0])


class TestSizeGuardEntryPoint(unittest.TestCase):
    """U-10 — phase-18 CI's size-guard entry point is this module's own guard.

    D-06 asks for one authoring site for the pair of thresholds. The strongest
    reading of it is that the CI job and the local guard become the same *code*
    rather than merely the same numbers: ``tests/size_guard.py`` loads
    :func:`budget_verdict` from this module and exits on what it returns, so the
    four boundary counts pinned by :class:`TestLineBudget` settle CI's behaviour
    too, and the asymmetric relation cannot be restated one line off.

    Driven through a subprocess rather than an import because the exit code is
    the artefact CI reads: D-07 makes the job summary a report and never the
    verdict, since a summary upload failure does not fail a job.
    """

    SCRIPT = ROOT / "tests" / "size_guard.py"

    def run_guard(self, lines, summary=None):
        """Run the script over a throwaway file of exactly ``lines`` lines.

        The measured path is an argument so the boundary counts can be staged
        without touching ``dogen``; CI passes none and the script measures the
        tool itself.
        """
        env = dict(os.environ)
        env.pop("GITHUB_STEP_SUMMARY", None)
        if summary is not None:
            env["GITHUB_STEP_SUMMARY"] = str(summary)
        with tempfile.TemporaryDirectory() as tmp:
            measured = pathlib.Path(tmp) / "measured"
            measured.write_text("x\n" * lines, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(self.SCRIPT), str(measured)],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

    def test_u10_the_script_exit_code_agrees_with_budget_verdict_at_the_boundaries(self):
        """The four counts of Pitfall 3, answered by the shared function."""
        for lines in (
            BUDGET_ANNOTATE,
            BUDGET_ANNOTATE + 1,
            BUDGET_FAIL - 1,
            BUDGET_FAIL,
        ):
            verdict = budget_verdict(lines)
            expected = 1 if verdict == "fail" else 0
            with self.subTest(lines=lines, verdict=verdict):
                proc = self.run_guard(lines)
                self.assertEqual(
                    proc.returncode,
                    expected,
                    "size_guard.py exited %d at %d lines; budget_verdict() says "
                    "%r, so the gate expects %d. stdout=%r stderr=%r"
                    % (proc.returncode, lines, verdict, expected,
                       proc.stdout, proc.stderr),
                )
                self.assertIn(
                    verdict,
                    proc.stdout,
                    "the verdict must be printed whether or not a job summary "
                    "is being written; stdout=%r" % proc.stdout,
                )

    def test_u10_the_summary_table_is_written_when_the_variable_names_a_path(self):
        """D-07's report: five facts, as a markdown table the job renders."""
        with tempfile.TemporaryDirectory() as tmp:
            summary = pathlib.Path(tmp) / "step-summary.md"
            proc = self.run_guard(BUDGET_ANNOTATE + 1, summary=summary)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = summary.read_text(encoding="utf-8")
        rows = [line for line in written.splitlines() if line.startswith("|")]
        self.assertGreaterEqual(
            len(rows),
            6,
            "expected a header, a separator and four fact rows; got %r" % rows,
        )
        self.assertIn("annotate", written)

    def test_u10_an_unwritable_summary_path_does_not_change_the_exit_code(self):
        """A reporting channel that can fail must not carry the verdict."""
        with tempfile.TemporaryDirectory() as tmp:
            unwritable = pathlib.Path(tmp) / "no-such-directory" / "summary.md"
            proc = self.run_guard(BUDGET_ANNOTATE + 1, summary=unwritable)
        self.assertEqual(
            proc.returncode,
            0,
            "a summary that could not be written changed the verdict; "
            "stdout=%r stderr=%r" % (proc.stdout, proc.stderr),
        )
        self.assertIn("annotate", proc.stdout)


class TestPython39Hazards(unittest.TestCase):
    """U-10 — the 3.9 hazards ``feature_version`` does not catch (P-10)."""

    def setUp(self):
        self.source = DOGEN_PATH.read_text(encoding="utf-8")

    def test_the_source_parses_under_the_39_feature_version(self):
        ast.parse(self.source, feature_version=(3, 9))

    def test_future_annotations_is_the_first_statement(self):
        body = ast.parse(self.source).body
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            first = body[1]
        self.assertIsInstance(first, ast.ImportFrom)
        self.assertEqual(first.module, "__future__")
        self.assertIn("annotations", [alias.name for alias in first.names])

    def test_no_pattern_matching_statement(self):
        self.assertEqual(pattern_match_lines(self.source), [])

    def test_no_type_union_outside_an_annotation(self):
        self.assertEqual(type_unions_outside_annotations(self.source), [])

    def test_no_dataclass_carries_a_slots_keyword(self):
        self.assertEqual(dataclass_slots_lines(self.source), [])

    def test_the_union_scanner_catches_a_runtime_alias(self):
        """Negative keystone: ``int | None`` outside an annotation is DETECTED."""
        self.assertEqual(type_unions_outside_annotations("Alias = int | None\n"), [1])

    def test_the_union_scanner_catches_a_default_argument(self):
        source = "def f(kind=str | bytes):\n    return kind\n"
        self.assertEqual(type_unions_outside_annotations(source), [1])

    def test_the_union_scanner_catches_an_isinstance_union(self):
        source = "def f(x):\n    return isinstance(x, int | str)\n"
        self.assertEqual(type_unions_outside_annotations(source), [2])

    def test_the_union_scanner_leaves_annotations_alone(self):
        source = (
            "from __future__ import annotations\n"
            "def f(x: int | None, y: dict | None = None) -> str | None:\n"
            "    z: list | None = None\n"
            "    return z\n"
        )
        self.assertEqual(type_unions_outside_annotations(source), [])

    def test_the_union_scanner_leaves_bit_flags_and_set_unions_alone(self):
        source = (
            "import fcntl\n"
            "import os\n"
            "flags = os.O_CREAT | os.O_RDWR\n"
            "mode = fcntl.LOCK_EX | fcntl.LOCK_NB\n"
            "def names(committed, after, before):\n"
            "    return committed | after - set(before)\n"
        )
        self.assertEqual(type_unions_outside_annotations(source), [])

    def test_the_union_scan_is_not_vacuous(self):
        """dogen really does use ``|``; a scan with nothing to look at proves nothing."""
        self.assertNotEqual(bitwise_or_lines(self.source), [])

    def test_the_dataclass_scanner_catches_slots(self):
        source = (
            "from dataclasses import dataclass\n"
            "@dataclass(slots=True)\n"
            "class C:\n"
            "    x: int\n"
        )
        self.assertEqual(dataclass_slots_lines(source), [2])

    def test_the_pattern_match_scanner_catches_a_match_statement(self):
        if not hasattr(ast, "Match"):
            self.skipTest("this interpreter cannot parse `match` at all")
        source = "def f(x):\n    match x:\n        case 1:\n            return 2\n"
        self.assertEqual(pattern_match_lines(source), [2])


#: Deleted by plan 17-10. Every one is still named in `README.md` and
#: `AGENTS.md`, whose rewrite is phase 18's.
DELETED_SCRIPT_PATHS = (
    "scripts/dogen-common.sh",
    "scripts/dogen-record-draft.sh",
    "scripts/dogen-record-review.sh",
    "scripts/dogen-record-step.sh",
    "scripts/dogen-signoff.sh",
    "tests/test_dogen_scripts.sh",
)

#: The marker both tombstones carry. Literal so a paraphrase goes red.
TOMBSTONE_MARKER = "**were deleted in phase 17**"

#: The two repo-root documents a reader meets first. `docs/before-after.md` is
#: deliberately out of scope twice over: it is not in the release tree at all
#: (phase 18 decision (d), and see `UNSHIPPED_PATHS`), and on the branches where
#: it does exist it is a narrative comparison of the v1.x and v2.0 shapes, so
#: naming the old scripts is its subject rather than an instruction.
TOMBSTONED_DOCS = ("README.md", "AGENTS.md")


class TestDeletedScriptsAreTombstoned(unittest.TestCase):
    """U-10 — the deleted v1.x layer is gone, and says so where it is still named.

    WR-09: plan 17-10 deleted the five `scripts/dogen-*.sh` and
    `tests/test_dogen_scripts.sh`. `README.md`'s install step copies a glob that
    matches nothing, its smoke-test section invokes commands that do not exist,
    and `AGENTS.md` names the deleted suite twice as part of the green gate. The
    rewrite is phase 18's; until then a reader who follows either file is
    following a tree that does not exist.

    Self-retiring on purpose: the tombstone is required only while a document
    still names a deleted path. When phase 18's rewrite removes the last
    mention, this class stops asking for anything rather than pinning a
    paragraph nobody needs.
    """

    def test_every_deleted_path_is_really_gone(self):
        for relative in DELETED_SCRIPT_PATHS:
            with self.subTest(path=relative):
                self.assertFalse(
                    (ROOT / relative).exists(),
                    "%s is back; either the deletion was reverted or this "
                    "fixture is stale" % relative,
                )

    def test_scripts_holds_only_the_stdlib_utilities(self):
        # The vacuous-pass guard for the assertion above: a mis-rooted ROOT
        # would make every `exists()` false.
        found = sorted(p.name for p in (ROOT / "scripts").glob("*.py"))
        self.assertEqual(found, ["planning_lint.py", "skill_lint.py", "wiki_lint.py"])
        self.assertEqual(sorted((ROOT / "scripts").glob("*.sh")), [])

    def test_a_document_that_still_names_one_carries_the_tombstone(self):
        for relative in TOMBSTONED_DOCS:
            path = ROOT / relative
            text = path.read_text(encoding="utf-8")
            named = [name for name in DELETED_SCRIPT_PATHS if name in text]
            # A bare basename counts too: AGENTS.md writes `dogen-signoff.sh`.
            named += [
                name.split("/")[-1]
                for name in DELETED_SCRIPT_PATHS
                if name.split("/")[-1] in text
            ]
            if not named:
                continue
            with self.subTest(document=relative):
                self.assertIn(
                    TOMBSTONE_MARKER,
                    text,
                    "%s still names %s, which phase 17 deleted, and carries no "
                    "tombstone saying so — a reader following it is following a "
                    "tree that does not exist"
                    % (relative, ", ".join(sorted(set(named)))),
                )

    #: The gate, as the project actually runs it. WR-08 (iteration 3): the pin
    #: used to name six commands and call them "in full" while omitting
    #: `scripts/planning_lint.py`, which every fix report's gate table runs —
    #: and `tests/test_planning_lint.py`, which was a pytest module on a branch
    #: with no pytest, so it errored under the module runner and no gate ran it.
    #: A completeness claim that hides a test nobody executes is the "silently
    #: green" shape the rest of this phase's infrastructure exists against.
    #: `bash tests/install_smoke.sh` proves what no other command here does:
    #: that the tool is reachable through `PATH` after the documented install,
    #: and that docs/install.md's marked INSTALL region is runnable as written.
    GATE_COMMANDS = (
        "python3 -m unittest tests.test_dogen_unit",
        "python3 tests/test_dogen_unit.py",
        "python3 -m unittest tests.test_skill_text",
        "python3 -m unittest tests.test_planning_lint",
        "python3 -m unittest tests.test_check_docs",
        "bash tests/test_dogen_lifecycle.sh",
        "bash tests/test_dogen_acceptance.sh",
        "bash tests/install_smoke.sh",
        "bash validation/fixtures.sh",
        "python3 scripts/skill_lint.py",
        "python3 tests/check_traces.py",
        "python3 tests/check_docs.py",
        "python3 scripts/planning_lint.py",
        "python3 tests/size_guard.py",
        "python3 -m unittest tests.test_wiki_lint",
        "python3 scripts/wiki_lint.py",
    )

    #: CR-01 — the gate command that deliberately has no separate CI step,
    #: carrying the reason `.github/workflows/ci.yml` states for it. An
    #: exemption is data here rather than prose in a review report, so a
    #: future reader meets it where the assertion is.
    CI_EXEMPT = {
        # The `docs-check` job's comment: `tests/check_docs.py` calls
        # `check_traces.main()` itself, so that job already runs the trace
        # checker and a second step for it would run it twice.
        "python3 tests/check_traces.py",
    }
    #: CR-01 — the mirror of the above: a `run:` body CI executes that
    #: `GATE_COMMANDS` does not declare. AGENTS.md pins the shell suites at
    #: warning level in prose ("that exact command, with that exact file
    #: scope, is what CI's `shellcheck` job runs") rather than as a tuple
    #: entry, because the binary is preinstalled on the image and the command
    #: is not one a developer runs as part of the fourteen.
    CI_EXTRA = {"shellcheck -S warning install.sh tests/*.sh validation/*.sh"}

    def test_ci_runs_every_gate_command(self):
        """CR-01 — `ci.yml` is a hand copy of the gate unless something pins it.

        `GATE_COMMANDS` is pinned to `AGENTS.md`, to the tree and to the test
        modules in `tests/`, and the workflow that claims (ci.yml line 1) "one
        job per command that already runs locally" was pinned to nothing at
        all. It had already drifted: `python3 tests/test_dogen_unit.py` — the
        script form that exists because the two runners once reported
        different counts (CR-06) — was in the gate and in no job, so the one
        regression class the second invocation form exists to catch was the
        one class CI could not see.

        Both directions are asserted. A gate command with no job means CI is
        weaker than the declared gate; a job the gate does not declare means
        CI silently runs more than the gate, which is drift in the direction
        nobody looks.
        """
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        bodies = set(re.findall(r"^\s*- run:\s*(.+?)\s*$", workflow, re.MULTILINE))
        # Vacuous-pass guard: a parse that finds zero bodies agrees with every
        # gate command by construction, and would read as the loudest possible
        # green. Assert the scan still matches before either comparison.
        self.assertTrue(
            bodies,
            "parsed 0 `run:` bodies out of .github/workflows/ci.yml; the "
            "workflow shape changed and this test is asserting against an "
            "empty set",
        )
        missing = set(self.GATE_COMMANDS) - bodies - self.CI_EXEMPT
        self.assertEqual(
            missing,
            set(),
            "gate commands with no CI job: %s; the workflow moves to the "
            "gate, never the gate to the workflow" % sorted(missing),
        )
        unpinned = bodies - set(self.GATE_COMMANDS) - self.CI_EXTRA
        self.assertEqual(
            unpinned,
            set(),
            "CI runs commands the gate does not declare: %s" % sorted(unpinned),
        )

    #: The gate's two reader-facing homes. `AGENTS.md` is the operating
    #: contract; `docs/development.md` explains each command. Both carry every
    #: string of the tuple verbatim, so neither is a hand copy that can drift.
    GATE_DOCS = ("AGENTS.md", "docs/development.md")

    def test_the_tombstone_states_the_real_gate(self):
        # A tombstone that says "these are gone" and leaves the reader without
        # a gate to run has moved the problem rather than answered it.
        for relative in self.GATE_DOCS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for command in self.GATE_COMMANDS:
                with self.subTest(document=relative, command=command):
                    self.assertIn(command, text)

    def test_every_test_module_in_tests_is_in_the_gate(self):
        """WR-08 — a test module no command runs is worse than no module.

        `tests/test_planning_lint.py` sat in `tests/` for the whole phase as a
        pytest module on a branch with no pyproject, no pytest and no uv: it
        errored under `python3 -m unittest tests.test_planning_lint` and nothing
        in the tombstone, `AGENTS.md`, `run_matrix.sh` or either bash suite
        invoked it. It failed when executed and was never executed, so it read
        as green. This pins the general rule rather than that one file.
        """
        gate = "\n".join(self.GATE_COMMANDS)
        modules = sorted(
            path.stem
            for path in (ROOT / "tests").glob("test_*.py")
        )
        self.assertGreaterEqual(
            len(modules), 3, "found %r; this assertion would be vacuous" % modules
        )
        for module in modules:
            with self.subTest(module=module):
                self.assertIn(
                    "tests.%s" % module,
                    gate,
                    "tests/%s.py is in the tree and no gate command runs it"
                    % module,
                )

    def test_the_install_smoke_is_declared_in_the_gate(self):
        """CI-01 — the smoke is a gate command, so the tuple must name it.

        `tests/install_smoke.sh` is the only gate command that reaches `dogen`
        through `PATH` rather than through the in-tree file, and the only one
        that executes `docs/install.md`'s marked INSTALL region. A gate that omits
        it is green on a tree whose documented install does not work, which is
        the one failure this suite's tombstone machinery exists to make loud.
        """
        self.assertIn("bash tests/install_smoke.sh", self.GATE_COMMANDS)
        # The nine that were already there are not displaced by the addition,
        # and no command is listed twice. Phase 18's docs check adds two more
        # (plan 18-06) — its own suite and the checker itself — and plan 18-07
        # adds the size guard, which is CI's size-guard job's local dry-run
        # command (D-02: every job body is a command a developer already runs),
        # so the tuple was thirteen. Phase 19 adds the validation kit's fixture
        # suite, which is CI's `validation` job's local dry-run command under
        # that same D-02 rule — and a kit the local gate does not run is exactly
        # the WR-08 orphan defect this tuple exists against — so it is fourteen.
        self.assertEqual(len(self.GATE_COMMANDS), 16)
        self.assertEqual(len(set(self.GATE_COMMANDS)), 16)

    def test_no_gate_command_names_a_path_the_tree_does_not_have(self):
        """T-18-25 — the declared gate may never outrun the tree.

        `test_every_test_module_in_tests_is_in_the_gate` pins the tree → gate
        direction: nothing in `tests/` may go unrun. This pins the other one.
        A tuple entry naming a file that does not exist yet turns the whole
        local gate red for every developer who runs it, and reports the same
        "declared gate and real gate disagree" defect the tuple exists to
        prevent, inverted. Both the path form (`tests/check_traces.py`) and the
        module form (`tests.test_skill_text`) are resolved, because the tuple
        uses both. `validation/` joined the prefixes in phase 19 with
        `bash validation/fixtures.sh`: without it the scan skips that command's
        path entirely and the vacuous-pass guard below fails on the count, which
        is the trap rather than the check firing.
        """
        checked = []
        for command in self.GATE_COMMANDS:
            for token in command.split():
                if token.startswith(("tests/", "scripts/", "validation/")):
                    relative = token
                elif token.startswith(("tests.", "scripts.")):
                    relative = token.replace(".", "/") + ".py"
                else:
                    continue
                checked.append(relative)
                with self.subTest(command=command, path=relative):
                    self.assertTrue(
                        (ROOT / relative).exists(),
                        "the gate declares %r, and %s is not in the tree; "
                        "declare a command only once the file it runs exists"
                        % (command, relative),
                    )
        # Vacuous-pass guard: every gate command names exactly one file, so a
        # scan that found fewer paths than commands has stopped matching and
        # every assertion above would be silently empty.
        self.assertGreaterEqual(
            len(checked),
            len(self.GATE_COMMANDS),
            "found %d path(s) across %d gate command(s); the scan has stopped "
            "matching" % (len(checked), len(self.GATE_COMMANDS)),
        )

    def test_no_test_module_in_tests_needs_a_third_party_runner(self):
        """WR-08 — the orphan also imported a runner this branch does not have.

        Stdlib only: no pyproject, no third-party test runner, no uv. A module
        that imports one is a module the gate cannot run, which is how the
        orphan stayed invisible. Checked over the parsed IMPORTS rather than as
        a substring, so this test's own prose cannot match itself.
        """
        third_party = {"pytest", "hypothesis", "nose"}
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(a.name.split(".")[0] for a in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module.split(".")[0])
                self.assertEqual(
                    sorted(imported & third_party),
                    [],
                    "%s imports %s, which this branch does not have"
                    % (path.name, sorted(imported & third_party)),
                )

    #: WR-03 / T-18-76 — the home-directory prefixes that are legitimately in
    #: the shipped tree, each with the reason it is there. Widening this tuple
    #: to make a real leak pass is the exact failure the scan below exists
    #: against: an entry names a DOCUMENTED SYNTHETIC path, never a real user.
    SYNTHETIC_HOMES = (
        # The redaction token plan 18-12 introduced, and what the five
        # previously-leaking tracked files now carry. It names nobody, and it
        # stays absolute so `validation/score.py`'s `normalise_diagnostics`
        # rule 2 collapses it to the same token the real prefix collapsed to.
        "/home/redacted/",
        # This file's own fixture for the assertion that an absolute path does
        # NOT leak into an error payload (`test_...lock_path_is_not_echoed`).
        # Synthetic, and the assertion needs an absolute path to assert on.
        "/home/someone/",
        # `validation/runmeta.sh`'s comment example for why a home component
        # may carry an `@`. A documented illustration, not a machine's path.
        "/home/user@example.com/",
    )

    #: The same leak in the form an agent harness mangles a home path into
    #: when it uses one as a directory NAME: every separator, the leading one
    #: included, rewritten to a hyphen. No worked example is spelled out here
    #: on purpose — a mangled specimen in this file would be flagged by the
    #: scan below, which is the self-flagging shape the alternation exists to
    #: avoid. It carries the username just as plainly as the slash form and no
    #: `/home/…` pattern can see it, so it is scanned separately rather than
    #: assumed away. Matched by PREFIX: the mangled token runs on past the
    #: home component into the rest of the path.
    SYNTHETIC_MANGLED_HOMES = (
        b"-home-redacted-",
        b"-home-user-example-com-",
    )

    def test_the_shipped_tree_carries_no_real_home_path(self):
        """WR-03 / T-18-70 — the tree that ships had no anonymization gate.

        `scripts/planning_lint.py` is this project's anonymization gate and
        `AGENTS.md` scopes it to `.planning/` — the one tree that does NOT
        ship. The tree that does ship carried the author's absolute home
        directory and username across five tracked files, including private
        agent-transcript locations inside the validation RUN files. This is
        the missing sibling over the tree that ships. It rides the unit suite,
        so it needs no new gate command and no new CI job.

        Read as BYTES throughout: a non-UTF-8 tracked file is then scanned
        rather than skipped, and no decode error has to be swallowed — a
        swallowed decode is a file nobody looked at.
        """
        listing = subprocess.run(
            ["git", "ls-files", "-z", "--", ".", ":(exclude).planning/"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
        tracked = [name for name in listing.split(b"\0") if name]
        # Vacuous-pass guard: a scan that enumerated nothing finds no leak by
        # construction and reads as the loudest possible green. It must FAIL,
        # never skip.
        self.assertTrue(
            tracked,
            "`git ls-files -z -- . ':(exclude).planning/'` run in %s "
            "enumerated 0 files; the scan has nothing to read and cannot be "
            "green" % ROOT,
        )
        # Both patterns are built as an ALTERNATION so the literal prefix they
        # hunt for never appears in this file. A scanner that flags its own
        # source teaches the next reader to widen the allow-list, which is the
        # one move that turns this gate into decoration.
        home = re.compile(rb"/(?:home|Users)/[A-Za-z0-9._@%+-]+/")
        mangled = re.compile(rb"-(?:home|[Uu]sers)-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-")
        allowed = tuple(entry.encode("utf-8") for entry in self.SYNTHETIC_HOMES)
        findings = []
        for name in tracked:
            path = ROOT / name.decode("utf-8", "surrogateescape")
            if not path.is_file():
                continue  # a submodule or a broken symlink has no bytes here
            blob = path.read_bytes()
            for match in home.findall(blob):
                if match not in allowed:
                    findings.append((name, match))
            for match in mangled.findall(blob):
                if not match.startswith(self.SYNTHETIC_MANGLED_HOMES):
                    findings.append((name, match))
        self.assertEqual(
            findings,
            [],
            "the tree this release publishes carries %d home path(s) naming a "
            "real user: %s — redact the prefix, and never widen "
            "SYNTHETIC_HOMES to make a real leak pass"
            % (
                len(findings),
                sorted(
                    "%s: %s"
                    % (n.decode("utf-8", "replace"), m.decode("utf-8", "replace"))
                    for n, m in findings
                ),
            ),
        )


#: Tracked on the planning branch, deliberately absent from the release tree,
#: and therefore deliberately absent from ``AGENTS.md``'s tree block. Phase 18's
#: checkpoint recorded decision (d) as "left out of the release tree" for
#: ``docs/before-after.md`` and "removed in the retire-the-v1-layer commit" for
#: ``project-timeline.html``; neither is linked from anywhere in the tree. They
#: are named here rather than merely omitted, so that an absence from the
#: listing is a statement somebody made and not a line somebody forgot.
#:
#: Neither path exists on a release checkout. Nothing below asserts that they
#: do — the tuple's job is to say they are not listed, not that they are here.
UNSHIPPED_PATHS = (
    "docs/before-after.md",
    "project-timeline.html",
)

#: The tree-block sections that enumerate their files one per line, and so can
#: be pinned against the real tree. ``skills/`` and the root block are out of
#: scope on purpose and not by omission: ``skills/*/references/`` contents are
#: summarised inside the ``<-`` comment rather than listed, and the root block
#: carries no tree glyphs to parse.
PINNED_TREE_SECTIONS = ("docs", "scripts", "tests", "validation")

#: One entry of the ASCII listing. The indent unit is four columns, either four
#: spaces or a ``|`` and three. A wrapped comment continues on a line that has
#: no ``+--``/``\--`` glyph, so it cannot match and cannot be read as an entry.
_TREE_ENTRY_RE = re.compile(
    "^(?P<indent>(?:[│ ] {3})*)(?:├|└)── (?P<name>\\S+)"
)


def _agents_tree_fence():
    """The lines inside ``AGENTS.md``'s ``## The tree`` fence."""
    lines = (ROOT / "AGENTS.md").read_text(encoding="utf-8").split("\n")
    start = lines.index("## The tree")
    opened = lines.index("```", start)
    closed = lines.index("```", opened + 1)
    return lines[opened + 1 : closed]


def _declared_tree_paths():
    """Every path ``AGENTS.md``'s tree block names under a pinned section.

    Directories keep their trailing slash, so a declared-but-not-enumerated
    directory is distinguishable from an enumerated one.
    """
    declared = set()
    stack = []
    for raw in _agents_tree_fence():
        match = _TREE_ENTRY_RE.match(raw)
        if match is None:
            # A section header sits at column 0 and ends in a slash. Every other
            # unmatched line is either root-block or a wrapped comment, and a
            # wrapped comment must not reset the section it sits inside.
            if raw[:1].isalnum():
                head = raw.split()[0]
                stack = [head[:-1]] if head.endswith("/") else []
            continue
        if not stack or stack[0] not in PINNED_TREE_SECTIONS:
            continue
        depth = len(match.group("indent")) // 4
        name = match.group("name")
        del stack[depth + 1 :]
        declared.add("/".join(stack + [name]))
        if name.endswith("/"):
            stack.append(name[:-1])
    return declared


def _real_children(relative):
    """The tree's own children of ``relative``, as the listing would write them.

    Dotfiles, ``__pycache__`` and bytecode are skipped: none is source, and none
    is listed anywhere in the block.
    """
    children = set()
    for path in sorted((ROOT / relative).iterdir()):
        if path.name.startswith(".") or path.name == "__pycache__":
            continue
        if path.suffix == ".pyc":
            continue
        child = "%s/%s" % (relative, path.name)
        children.add(child + "/" if path.is_dir() else child)
    return children


class TestTheTreeBlockIsPinnedToTheTree(unittest.TestCase):
    """The tree block is a claim about the tree, so the tree checks it.

    ``AGENTS.md``'s ``## The tree`` section says what the project ships. Nothing
    read it. ``tests/check_docs.py`` scans ``AGENTS.md``, but only through
    ``check_links()``, whose ``LINK_RE`` matches ``[text](target)`` -- and the
    listing is bare filenames inside a fence, so not one of its lines is a link.
    ``GATE_COMMANDS`` pins the *gate* fence twenty lines above in both
    directions; the *tree* fence was pinned in neither.

    It drifted four ways before anyone read it against the tree: it named
    ``docs/before-after.md``, which the release does not ship; it listed four
    session records where seven shipped; and it omitted ``check_docs.py``,
    ``test_check_docs.py`` and ``size_guard.py``, all three of which are gate
    commands declared in the fence above. Every one of those is the same defect
    as the ``GATE_COMMANDS`` orphan, in a block nothing executed.

    Both directions are pinned, because each catches a different mistake: a file
    that ships and is not listed leaves a reader with an incomplete map, and a
    listed name with no file leaves them following a tree that does not exist.
    """

    def _enumerated_directories(self, declared):
        """Directories the block lists the *contents* of, not merely the name.

        A directory named without children is not pinned; one whose children
        are listed is. The difference is visible in the parse, which is why it
        is read from the parse rather than declared.
        """
        directories = set(PINNED_TREE_SECTIONS)
        for path in declared:
            if path.endswith("/") and any(
                other.startswith(path) for other in declared if other != path
            ):
                directories.add(path[:-1])
        return directories

    def test_the_tree_block_lists_every_shipped_file(self):
        """Ships and unlisted -> red, unless the omission is declared.

        This is the direction the session records and the three test-suite files
        drifted in. The ``UNSHIPPED_PATHS`` escape is deliberately narrow: an
        absence has to be written down in the tuple to be allowed.
        """
        declared = _declared_tree_paths()
        for relative in sorted(self._enumerated_directories(declared)):
            if not (ROOT / relative).is_dir():
                continue
            for child in sorted(_real_children(relative)):
                if child.rstrip("/") in UNSHIPPED_PATHS:
                    continue
                with self.subTest(path=child):
                    self.assertIn(
                        child,
                        declared,
                        "%s is in the tree and AGENTS.md's tree block does not "
                        "list it; list it, or name it in UNSHIPPED_PATHS if it "
                        "is deliberately not part of the release tree" % child,
                    )

    def test_the_tree_block_names_nothing_the_tree_lacks(self):
        """Listed and absent -> red. The inverse, and the inverse mistake.

        This is the direction ``docs/before-after.md`` drifted in on every
        release checkout: a reader following the listing went looking for a file
        the tree they had did not contain.
        """
        for relative in sorted(_declared_tree_paths()):
            with self.subTest(path=relative):
                self.assertTrue(
                    (ROOT / relative.rstrip("/")).exists(),
                    "AGENTS.md's tree block names %s, which is not in the tree"
                    % relative,
                )

    def test_the_two_exclusions_are_not_listed(self):
        """``UNSHIPPED_PATHS`` may not excuse something the block also names.

        A path that is both declared unshipped and printed in the listing is the
        two records disagreeing, which is worse than either being wrong alone.
        """
        declared = _declared_tree_paths()
        fence = "\n".join(_agents_tree_fence())
        for relative in UNSHIPPED_PATHS:
            with self.subTest(path=relative):
                self.assertNotIn(relative, declared)
                self.assertNotIn(
                    relative.rsplit("/", 1)[-1],
                    fence,
                    "%s is named in UNSHIPPED_PATHS and printed in the tree "
                    "block; the two records disagree" % relative,
                )

    def test_the_tree_parse_is_not_vacuous(self):
        """The guard the two assertions above are worthless without.

        A regex that stopped matching -- a changed indent unit, a different tree
        glyph, a renamed heading -- makes ``declared`` empty, and an empty
        ``declared`` makes ``names_nothing_the_tree_lacks`` pass over nothing
        while ``lists_every_shipped_file`` reports every file in four
        directories at once. The count is the cheap way to tell those apart.
        Precedent: ``test_scripts_holds_only_the_stdlib_utilities``.
        """
        declared = _declared_tree_paths()
        self.assertGreaterEqual(
            len(declared),
            20,
            "parsed %d entr(ies) from AGENTS.md's tree block; the parse has "
            "stopped matching and every assertion over it is empty" % len(declared),
        )
        # Three landmarks, one per parse feature the regex has to get right: a
        # plain entry, an entry nested under a listed directory, and the entry
        # whose comment wraps onto a line that must not be read as an entry.
        for landmark in (
            "scripts/skill_lint.py",
            "docs/install.md",
            "tests/lib.sh",
        ):
            self.assertIn(landmark, declared)



class TestProgressRecordReads(unittest.TestCase):
    """U-09 — ``read_progress``'s "absent, unreadable and malformed read as
    empty" is the whole of its contract with every consumer (WR-03).

    The record is an optimisation over the recovery material and never a
    substitute for it, so the safe answer to any unreadable state is "assume
    step 3 has not run". A subclass that escaped the ``except`` broke that: it
    surfaced through ``classify_manifest_files`` and ``main``'s ``OSError`` arm
    as 2 ``bad_target``, on the READ-ONLY verbs too — an unreadable hint file
    turning ``show``, ``summary`` and ``verify`` into bad-input refusals.
    """

    EMPTY = {"placed": [], "transition_attempts": 0}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        self.path = pathlib.Path(dogen.progress_path(self.repo, "u1"))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def test_a_well_formed_record_reads_back(self):
        # The vacuous-pass guard: without this, a `read_progress` that always
        # returned the empty record would satisfy every case below.
        self.path.write_text(
            '{"placed": ["docs/a.rst"], "transition_attempts": 2}', encoding="utf-8"
        )
        self.assertEqual(
            dogen.read_progress(self.repo, "u1"),
            {"placed": ["docs/a.rst"], "transition_attempts": 2},
        )

    def test_an_absent_record_reads_as_empty(self):
        self.assertEqual(dogen.read_progress(self.repo, "u1"), self.EMPTY)

    def test_a_malformed_record_reads_as_empty(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(dogen.read_progress(self.repo, "u1"), self.EMPTY)

    def test_a_directory_in_its_place_reads_as_empty(self):
        self.path.mkdir()
        self.assertEqual(dogen.read_progress(self.repo, "u1"), self.EMPTY)

    def test_an_unreadable_record_reads_as_empty(self):
        # WR-03: `PermissionError` is an `OSError`, not one of the three
        # subclasses the `except` used to name, so it escaped.
        self.path.write_text('{"placed": [], "transition_attempts": 0}', encoding="utf-8")
        self.path.chmod(0o000)
        self.addCleanup(self.path.chmod, 0o600)
        if os.access(str(self.path), os.R_OK):  # pragma: no cover - root
            self.skipTest("running as root: file modes do not deny reads")
        self.assertEqual(dogen.read_progress(self.repo, "u1"), self.EMPTY)

    def test_no_read_of_it_ever_raises(self):
        # The property stated as the consumers see it: `classify_manifest_files`
        # is called from the read-only verbs, and none of them may turn a
        # hint file's state into a refusal.
        self.path.write_text("[]", encoding="utf-8")
        self.assertEqual(dogen.read_progress(self.repo, "u1"), self.EMPTY)
        self.path.write_text('{"placed": "not a list"}', encoding="utf-8")
        self.assertEqual(dogen.read_progress(self.repo, "u1"), self.EMPTY)
        self.path.write_text('{"transition_attempts": -4}', encoding="utf-8")
        self.assertEqual(dogen.read_progress(self.repo, "u1"), self.EMPTY)
        self.path.write_text('{"transition_attempts": true}', encoding="utf-8")
        self.assertEqual(dogen.read_progress(self.repo, "u1"), self.EMPTY)


class TestStepFourFailureArm(unittest.TestCase):
    """WR-02 — both git calls of step 4 answer by the same rule.

    CR-01(b) gave the commit arm an attempt counter and left the ``git add``
    arm raising ``uncommitted_tail`` with ``hint="dogen resume <id>"``
    unconditionally, on the reasoning that only a commit hook can reject a
    batch. ``git add`` also fails deterministically — an index that will not
    lock, a pathspec a ``.gitignore`` change excluded after the guard ran, a
    read-only ``.git`` — and in every one of those the hint reproduced its own
    refusal, which is the closed loop CR-01(b) exists to break.

    Driven directly against the shared arm rather than through a repository:
    a second ``git add`` failure on ONE batch needs a fault injected between
    the ``--dry-run`` probe and the real add, so a hermetic repo would be
    testing the injection rather than the rule.
    """

    STEPS = ("git add", "git commit")

    def _refusal(self, attempts, step, stderr="fatal: whatever"):
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.refuse_transition(
                pathlib.Path("/nonexistent/repo"), "u1", attempts, step, stderr
            )
        return caught.exception

    def test_the_first_failure_of_either_call_offers_one_retry(self):
        for step in self.STEPS:
            with self.subTest(step=step):
                refusal = self._refusal(1, step)
                self.assertEqual(refusal.reason, "uncommitted_tail")
                self.assertEqual(refusal.hint, "dogen resume u1")
                self.assertIn(step, refusal.detail)

    def test_the_second_failure_of_either_call_is_the_honest_limit(self):
        for step in self.STEPS:
            with self.subTest(step=step):
                refusal = self._refusal(2, step)
                self.assertEqual(refusal.reason, "recovery_unsupported")
                # Both arms account for `--adopt`; only one offers it (WR-06).
                self.assertIn("--adopt", refusal.hint)
                self.assertEqual(refusal.extra.get("step"), step)

    def test_the_hint_is_never_only_the_command_that_just_refused(self):
        """WR-04 — the assertion that used to pin this could not fail.

        It read ``assertNotIn("dogen resume u1\\n", refusal.hint)``. The hint is
        built from implicitly-concatenated string literals with no newline
        anywhere in it, so the needle can never be present and the assertion was
        structurally incapable of failing — in a suite whose organising
        principle is the vacuous-pass guard. Its comment also claimed the
        opposite of what the hint does: the hint names ``dogen resume u1``
        twice, deliberately.

        The rule is about PLACEMENT, not absence. A second-attempt hint may not
        be merely the command that produced it, and every occurrence of that
        command has to carry the thing that must change first — otherwise it is
        the closed loop again, one sentence long.
        """
        sanctioned = (
            "emove what is refusing the transition and run "
            "`dogen resume u1` once more"
        )
        for step in self.STEPS:
            with self.subTest(step=step):
                hint = self._refusal(2, step).hint
                # Vacuous-pass guard: the needle IS present, so everything
                # below is a claim about how it is presented.
                self.assertIn("dogen resume u1", hint)
                self.assertNotEqual(hint.strip(), "dogen resume u1")
                self.assertNotIn("dogen resume u1;", hint)
                self.assertIn(
                    sanctioned,
                    hint,
                    "the plain resume is offered without naming what has to "
                    "change first, which is the command that just refused",
                )
                remainder = hint.replace(sanctioned, "")
                # WR-06: the conditional escape belongs to the arm where a hook
                # ran. On a `git add` failure the commit was never attempted,
                # nothing on disk is `unexpected`, and `--adopt` degrades to
                # the plain resume that just refused — so it must not be
                # offered as a command at all.
                if step == "git commit":
                    self.assertIn('`dogen resume u1 --adopt --note "<why>"`', hint)
                    self.assertIn("ONLY when", hint)
                    self.assertIn("adopt_unsupported", hint)
                    remainder = remainder.replace(
                        '`dogen resume u1 --adopt --note "<why>"`', ""
                    )
                else:
                    self.assertNotIn("--adopt --note", hint)
                    self.assertIn("`--adopt` is not an answer here", hint)
                # Nothing else may name the command. Strip the sanctioned
                # occurrences and no further one may survive.
                self.assertNotIn("dogen resume u1", remainder)

    def test_the_two_arms_do_not_share_one_detail(self):
        """WR-03 — ``detail`` is what the routed surfaces branch on.

        Both arms carried ``commit_rejected``, so a ``git add`` failure — where
        the commit was never attempted and no hook ran — was routed by name to
        "only the commit was refused; inspect the repository's commit hooks".
        Right reason, wrong diagnosis. ``extra.step`` carried the truth and
        nothing reads it.
        """
        self.assertEqual(self._refusal(2, "git commit").detail, "commit_rejected")
        self.assertEqual(self._refusal(2, "git add").detail, "stage_rejected")

    def test_each_arm_says_what_actually_happened(self):
        committed = self._refusal(2, "git commit").hint
        staged = self._refusal(2, "git add").hint
        for hint in (committed, staged):
            self.assertIn("The batch is on the record and the files are placed", hint)
            self.assertIn("is preserved and holds the recovery material", hint)
        self.assertIn("only the commit was refused", committed)
        self.assertIn("the repository's commit hooks", committed)
        # The add arm must claim neither of those: no commit ran, so no hook
        # ran either, and "only the commit was refused" is simply false.
        self.assertNotIn("only the commit was refused", staged)
        self.assertIn("could not stage them", staged)
        self.assertIn("the commit was never attempted", staged)
        # WR-06: and it names the causes that can actually produce it, in a
        # sentence that closes. The old shared template left the parenthetical
        # open — "…because the commit was never attempted, then remove what is
        # refusing the transition…" read as a comma splice — and then offered
        # a hook-conditional escape to an author no hook had run for.
        self.assertIn("an unstageable pathspec", staged)
        self.assertIn("an index that will not lock", staged)
        self.assertNotIn("REWROTE the placed bytes", staged)
        self.assertNotIn("A deleted file has no bytes to adopt", staged)
        # The commit arm keeps both, because there a hook is exactly the cause.
        self.assertIn("REWROTE the placed bytes", committed)

    def test_the_counter_is_not_described_as_a_count_of_refusals(self):
        """WR-03 — ``transition_attempts`` counts three different things.

        It is persisted before EITHER git call, so it covers an add failure, a
        commit refusal and a run killed between the two. "git refused this
        batch N times" asserted of every increment something true of only one:
        a transient add failure followed by a first genuine hook rejection read
        as two refusals.
        """
        for step in self.STEPS:
            with self.subTest(step=step):
                hint = self._refusal(2, step).hint
                self.assertNotIn("git refused this batch", hint)
                self.assertIn("failed to complete this batch 2 times", hint)
        # And the field the count is read from carries the same name.
        self.assertIn("transition_attempts", dogen.read_progress(
            pathlib.Path("/nonexistent/repo"), "u1"
        ))

    def test_the_refusal_names_which_git_call_failed(self):
        # Two arms, one reason: without the step in it, a reader of the record
        # cannot tell a rejecting pre-commit hook from an unstageable pathspec.
        for step in self.STEPS:
            with self.subTest(step=step):
                self.assertIn(step, self._refusal(2, step).hint)

    def test_gits_first_line_is_carried_and_an_empty_stderr_is_named(self):
        refusal = self._refusal(1, "git add", "fatal: no lock\nhint: ignore me")
        self.assertIn("fatal: no lock", refusal.detail)
        self.assertNotIn("hint: ignore me", refusal.detail)
        self.assertIn("no git output", self._refusal(1, "git add", "").detail)

    def test_both_arms_of_write_tail_go_through_the_shared_helper(self):
        # The structural half: the two arms drifted once already, and only a
        # check on the call sites keeps a future edit from re-forking them.
        source = DOGEN_PATH.read_text(encoding="utf-8")
        body = source[source.index("def write_tail(") :]
        body = body[: body.index("\ndef ", 1)]
        for step in self.STEPS:
            with self.subTest(step=step):
                self.assertIn(
                    'refuse_transition(repo, unit, attempts, "%s"' % step, body
                )
        self.assertNotIn(
            'raise Refusal(\n            "uncommitted_tail"', body,
            "write_tail raises uncommitted_tail directly again; step 4's two "
            "failure arms must answer through refuse_transition",
        )


class TestToolPackaging(unittest.TestCase):
    """U-10 — one executable, stdlib-only, LGPL-headed file."""

    def test_the_lgpl_header_is_present(self):
        source = DOGEN_PATH.read_text(encoding="utf-8")
        self.assertIn("GNU Lesser General Public License", source)
        self.assertIn("SPDX-License-Identifier: LGPL-3.0-only", source)

    def test_the_file_is_executable_with_a_python3_shebang(self):
        self.assertTrue(os.access(str(DOGEN_PATH), os.X_OK), "dogen must be executable")
        first = DOGEN_PATH.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, "#!/usr/bin/env python3")

    def test_it_imports_under_isolated_mode_with_no_third_party_module(self):
        code = (
            "import sys\n"
            "import importlib.machinery, importlib.util\n"
            "before = set(sys.modules)\n"
            "loader = importlib.machinery.SourceFileLoader('dogen', %r)\n"
            "spec = importlib.util.spec_from_loader('dogen', loader)\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "loader.exec_module(module)\n"
            "added = sorted({name.split('.')[0] for name in set(sys.modules) - before})\n"
            "sys.stdout.write(' '.join(added))\n" % str(DOGEN_PATH)
        )
        proc = subprocess.run(
            [sys.executable, "-I", "-c", code], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is None:
            self.skipTest("sys.stdlib_module_names needs Python 3.10 or newer")
        imported = [name for name in proc.stdout.split() if name]
        self.assertNotEqual(imported, [], "the import proved nothing if nothing loaded")
        third_party = [
            name for name in imported if name != "dogen" and name not in stdlib
        ]
        self.assertEqual(third_party, [], "dogen must import standard library only")

    def test_the_source_parses_under_a_newer_interpreter(self):
        """3.9 and 3.13 arrive with phase-18 CI; this is the cheap local smoke."""
        newer = shutil.which("python3.12")
        if newer is None:
            self.skipTest("no python3.12 on this machine")
        proc = subprocess.run(
            [newer, "-c", "import ast, sys; ast.parse(open(sys.argv[1]).read())",
             str(DOGEN_PATH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestThisSuiteIsWhollyDefined(unittest.TestCase):
    """U-10 — the suite's own vacuous-pass guard (CR-06).

    ``unittest.main()`` calls ``sys.exit()``. A ``__main__`` block anywhere but
    the end of the file therefore truncates the module when it is run as a
    script: everything below is never defined, the short run prints ``OK`` and
    exits 0, and it is indistinguishable from the full run without counting.
    That is what this file did for the whole of phase 17 — 325 of 404 tests,
    the entire U-11 / V1–V19 block, behind a green ``OK``.
    """

    def _module_tree(self):
        return ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))

    def test_the_runner_block_is_the_last_statement_in_the_module(self):
        tree = self._module_tree()
        mains = [
            index
            for index, node in enumerate(tree.body)
            if isinstance(node, ast.If)
            and ast.dump(node.test).find("'__main__'") >= 0
        ]
        self.assertEqual(
            len(mains), 1, "expected exactly one `if __name__` block, found %d" % len(mains)
        )
        self.assertEqual(
            mains[0],
            len(tree.body) - 1,
            "the `if __name__ == \"__main__\"` block is statement %d of %d; "
            "`unittest.main()` exits, so every class below it is undefined when "
            "this file is run as a script"
            % (mains[0] + 1, len(tree.body)),
        )

    def test_the_expected_minimum_is_a_floor_the_module_actually_meets(self):
        loaded = unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]
        ).countTestCases()
        self.assertGreaterEqual(loaded, EXPECTED_MIN_TESTS)
        # And the floor may not be lowered into uselessness: it is raised
        # deliberately, never dropped to make a truncated module pass.
        self.assertGreaterEqual(EXPECTED_MIN_TESTS, 400)


# --- U-11 (VERB-06) — contract 5.9's V1–V19 verification report --------------
#
# One class per check group, each method carrying the V id it pins. V1–V4 and
# V5–V13 are driven from synthetic event lists rather than from a repository:
# both are pure functions — of the ledger's exact bytes, and of the event list —
# so a temp repo would add setup without adding evidence. V14 needs real files
# and V15–V19 need real history, so those two groups drive a temp repo.


def by_id(checks):
    """``{V id: record}``, asserting that no id appears twice in one report."""
    seen = {}
    for row in checks:
        assert row["id"] not in seen, "duplicate check id %s" % row["id"]
        seen[row["id"]] = row
    return seen


def lines_of(events):
    """Canonical, chain-linked lines for hand-built events (never mutating them)."""
    return dogen.chain_lines([dict(event) for event in events])


def accept(seq, generation_seq, basis, resolves=None, withdraws=None):
    """An accept whose ``files`` ARE the basis — V6's own invariant, satisfied."""
    event = review(seq, "accept", generation_seq, resolves=resolves, withdraws=withdraws)
    event["files"] = [{"path": p, "sha256": h, "bytes": 1} for p, h in basis]
    return event


class TestVerifyIntegrityChecks(unittest.TestCase):
    """V1–V4 — the four checks that read the ledger's own bytes."""

    def report(self, events, committed=0, partial="", unit="u"):
        lines = lines_of(events)
        return by_id(dogen.verify_integrity(unit, lines, lines[:committed], partial))

    def raw(self, lines, committed=0, partial="", unit="u"):
        return by_id(dogen.verify_integrity(unit, lines, lines[:committed], partial))

    # V1 — header

    def test_v1_accepts_a_well_formed_header(self):
        rows = self.report(opening("u"))
        self.assertEqual(rows["V1"]["status"], "ok")
        self.assertEqual(rows["V1"]["level"], "fail")

    def test_v1_fails_when_the_first_event_is_not_the_header(self):
        rows = self.report([steering(0), ev("ledger", 1, v=1, unit="u", docs_root="docs")])
        self.assertEqual(rows["V1"]["status"], "fail")

    def test_v1_fails_on_an_unsupported_ledger_version(self):
        rows = self.report([ev("ledger", 0, v=2, unit="u", docs_root="docs")])
        self.assertEqual(rows["V1"]["status"], "fail")
        self.assertIn("2", rows["V1"]["detail"])

    def test_v1_fails_when_the_header_names_another_unit(self):
        rows = self.report(opening("other"), unit="u")
        self.assertEqual(rows["V1"]["status"], "fail")
        self.assertIn("other", rows["V1"]["detail"])

    def test_v1_is_vacuously_ok_on_a_zero_line_ledger(self):
        rows = self.raw([])
        self.assertEqual(rows["V1"]["status"], "ok")
        self.assertTrue(rows["V1"]["detail"])

    # V2 — lines parse, are canonical, and sit within the caps

    def test_v2_accepts_canonical_lines(self):
        rows = self.report(opening("u"))
        self.assertEqual(rows["V2"]["status"], "ok")

    def test_v2_fails_on_a_line_that_does_not_parse(self):
        lines = lines_of(opening("u")) + ["{not json"]
        self.assertEqual(self.raw(lines)["V2"]["status"], "fail")

    def test_v2_fails_on_a_line_that_is_not_canonical(self):
        lines = lines_of(opening("u"))
        lines[1] = json.dumps(json.loads(lines[1]), sort_keys=True, separators=(", ", ": "))
        self.assertEqual(self.raw(lines)["V2"]["status"], "fail")

    def test_v2_fails_on_a_line_beyond_the_byte_cap(self):
        oversize = ev("steering", 2, note="x" * (dogen.MAX_LINE_BYTES + 8), origin="manual")
        lines = lines_of(opening("u")) + [
            json.dumps(oversize, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        ]
        rows = self.raw(lines)
        self.assertEqual(rows["V2"]["status"], "fail")
        self.assertIn(str(dogen.MAX_LINE_BYTES), rows["V2"]["detail"])

    def test_v2_notes_a_truncated_final_line_without_failing_it(self):
        """A truncated tail is `uncommitted_tail`/resume, never `ledger_corrupt`."""
        rows = self.report(opening("u"), partial='{"kind":"steer')
        self.assertEqual(rows["V2"]["status"], "ok")
        self.assertIn("resume", rows["V2"]["detail"])

    # V3 — seq and chain

    def test_v3_accepts_a_linked_chain(self):
        rows = self.report(opening("u") + [steering(2)])
        self.assertEqual(rows["V3"]["status"], "ok")

    def test_v3_fails_on_a_seq_gap(self):
        lines = lines_of([ev("ledger", 0, v=1, unit="u", docs_root="docs"), steering(2)])
        self.assertEqual(self.raw(lines)["V3"]["status"], "fail")

    def test_v3_fails_on_a_repeated_seq(self):
        lines = lines_of(opening("u") + [steering(1, note="again")])
        self.assertEqual(self.raw(lines)["V3"]["status"], "fail")

    def test_v3_fails_on_a_broken_previous_hash_link(self):
        lines = lines_of(opening("u"))
        broken = json.loads(lines[1])
        broken["prev"] = "0" * 64
        lines[1] = dogen.canonical_line(broken)
        self.assertEqual(self.raw(lines)["V3"]["status"], "fail")

    def test_v3_consumes_verify_chains_findings_rather_than_re_walking(self):
        lines = lines_of(opening("u"))
        with mock.patch.object(
            dogen, "verify_chain", wraps=dogen.verify_chain
        ) as spy:
            dogen.verify_integrity("u", lines, [], "")
        self.assertTrue(spy.called, "V3 must consume verify_chain's findings")

    # V4 — committed prefix

    def test_v4_ok_when_the_committed_prefix_matches(self):
        rows = self.report(opening("u") + [steering(2)], committed=2)
        self.assertEqual(rows["V4"]["status"], "ok")

    def test_v4_fails_when_the_committed_prefix_was_rewritten(self):
        lines = lines_of(opening("u") + [steering(2)])
        committed = list(lines[:2])
        committed[1] = dogen.canonical_line(
            dict(json.loads(committed[1]), unit_hash="REWRITTEN")
        )
        self.assertEqual(by_id(dogen.verify_integrity("u", lines, committed, ""))["V4"]["status"], "fail")

    def test_v4_is_vacuously_ok_with_nothing_committed(self):
        rows = self.report(opening("u"))
        self.assertEqual(rows["V4"]["status"], "ok")
        self.assertTrue(rows["V4"]["detail"])

    def test_v1_to_v4_are_all_fail_level(self):
        for row in dogen.verify_integrity("u", lines_of(opening("u")), [], ""):
            self.assertEqual(row["level"], "fail", row["id"])


class TestVerifyDerivationChecks(unittest.TestCase):
    """V5–V13 — contract 5.4's derivation invariants, restated per event."""

    def report(self, events):
        return by_id(dogen.verify_derivation(events))

    def sealed(self):
        """A record every one of V5–V13 passes, used as each negative's base.

        The `fix` at seq 4 is below the accept's floor — the generation at seq 5
        answered it — so contract 5.4 leaves nothing pending at seq 6 and the
        accept disposes of nothing. That is the shape `cmd_review` can actually
        write: `--resolves` is validated against the CURRENT pending set.
        """
        return opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            review(4, "fix", 3),
            generation(5, [("a.rst", "h2")], signoff_seq=2),
            accept(6, 5, [("a.rst", "h2")]),
        ]

    def test_a_healthy_record_passes_every_check_from_v5_to_v13(self):
        rows = self.report(self.sealed())
        for number in range(5, 14):
            vid = "V%d" % number
            self.assertEqual(rows[vid]["status"], "ok", "%s: %s" % (vid, rows[vid]["detail"]))

    # V5 — signoff citation

    def test_v5_fails_when_a_generation_cites_a_superseded_signoff(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            signoff(3, ["a.rst"], plan_hash="P2"),
            generation(4, [("a.rst", "h1")], signoff_seq=2),
        ]
        self.assertEqual(self.report(events)["V5"]["status"], "fail")

    def test_v5_fails_when_a_generations_plan_hash_differs_from_its_signoff(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2, plan_hash="OTHER"),
        ]
        self.assertEqual(self.report(events)["V5"]["status"], "fail")

    def test_v5_fails_when_an_accepts_generation_predates_the_current_signoff(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            signoff(4, ["a.rst"], plan_hash="P2"),
            accept(5, 3, [("a.rst", "h1")]),
        ]
        self.assertEqual(self.report(events)["V5"]["status"], "fail")

    # V6 — review / reviewer-edit citation and accept files

    def test_v6_fails_when_a_review_does_not_cite_the_last_generation(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            review(4, "fix", 99),
        ]
        self.assertEqual(self.report(events)["V6"]["status"], "fail")

    def test_v6_fails_when_a_reviewer_edit_cites_a_generation_that_is_not_the_last(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            reviewer_edit(4, [("a.rst", "h2")], generation_seq=None),
        ]
        self.assertEqual(self.report(events)["V6"]["status"], "fail")

    def test_v6_accepts_a_null_generation_seq_when_no_generation_existed(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            reviewer_edit(3, [("a.rst", "h2")], generation_seq=None),
        ]
        self.assertEqual(self.report(events)["V6"]["status"], "ok")

    def test_v6_fails_when_an_accepts_files_are_not_the_basis(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            accept(4, 3, [("a.rst", "SOMETHING-ELSE")]),
        ]
        self.assertEqual(self.report(events)["V6"]["status"], "fail")

    # V7 — two generations with no intervening H

    def test_v7_fails_on_two_generations_with_no_intervening_steering(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            generation(4, [("a.rst", "h2")], signoff_seq=2),
        ]
        self.assertEqual(self.report(events)["V7"]["status"], "fail")

    def test_v7_accepts_an_unsteered_generation_carrying_its_reason(self):
        second = generation(4, [("a.rst", "h2")], signoff_seq=2)
        second["unsteered"] = True
        second["unsteered_reason"] = "restoring a deleted page"
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            second,
        ]
        self.assertEqual(self.report(events)["V7"]["status"], "ok")

    def test_v7_accepts_an_intervening_steering(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            steering(4),
            generation(5, [("a.rst", "h2")], signoff_seq=2),
        ]
        self.assertEqual(self.report(events)["V7"]["status"], "ok")

    # V8 — step hashes and evidence shape

    def walk(self, record):
        return opening("u") + [
            signoff(2, ["a.rst"], intent="how-to"),
            planned(3, [("s1", "run it", "agent", False)]),
            record,
        ]

    def good_record(self, **overrides):
        step_hash = hashlib.sha256(b"run it").hexdigest()
        payload = {
            "text_hash": step_hash,
            "mode": "agent",
            "output_sha256": DIGEST,
            "output_excerpt": "ok",
        }
        payload.update(overrides)
        return recorded(4, 3, "s1", "pass", **payload)

    def test_v8_accepts_a_matching_step_record(self):
        self.assertEqual(self.report(self.walk(self.good_record()))["V8"]["status"], "ok")

    def test_v8_fails_when_a_step_records_a_hash_the_plan_does_not(self):
        rows = self.report(self.walk(self.good_record(text_hash="0" * 64)))
        self.assertEqual(rows["V8"]["status"], "fail")

    def test_v8_fails_when_the_evidence_payload_is_missing_a_required_field(self):
        record = self.good_record()
        del record["output_sha256"]
        self.assertEqual(self.report(self.walk(record))["V8"]["status"], "fail")

    def test_v8_fails_when_a_skipped_step_carries_no_reason(self):
        record = self.good_record()
        record["verdict"] = "skipped"
        self.assertEqual(self.report(self.walk(record))["V8"]["status"], "fail")

    # V9 — actionable generations had all steps resolved at their seq

    def test_v9_fails_on_an_actionable_generation_with_an_unresolved_step(self):
        events = opening("u") + [
            signoff(2, ["a.rst"], intent="how-to"),
            planned(3, [("s1", "run it", "agent", False)]),
            generation(4, [("a.rst", "h1")], signoff_seq=2, steps_seq=3),
        ]
        self.assertEqual(self.report(events)["V9"]["status"], "fail")

    def test_v9_passes_when_every_step_was_resolved_first(self):
        events = self.walk(self.good_record()) + [
            generation(5, [("a.rst", "h1")], signoff_seq=2, steps_seq=3)
        ]
        self.assertEqual(self.report(events)["V9"]["status"], "ok")

    def test_v9_is_vacuous_on_a_non_actionable_unit(self):
        rows = self.report(self.sealed())
        self.assertEqual(rows["V9"]["status"], "ok")

    # V10 — accept dispositions

    def test_v10_fails_when_a_pending_request_has_no_disposition(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            steering(4),
            accept(5, 3, [("a.rst", "h1")]),
        ]
        self.assertEqual(self.report(events)["V10"]["status"], "fail")

    def test_v10_fails_when_resolves_names_a_seq_that_was_not_pending(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            accept(4, 3, [("a.rst", "h1")], resolves=[2]),
        ]
        self.assertEqual(self.report(events)["V10"]["status"], "fail")

    def test_v10_fails_when_resolves_and_withdraws_overlap(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            steering(4),
            accept(5, 3, [("a.rst", "h1")], resolves=[4],
                   withdraws=[{"seq": 4, "reason": "no longer wanted"}]),
        ]
        self.assertEqual(self.report(events)["V10"]["status"], "fail")

    def test_v10_fails_on_a_withdrawal_with_no_reason(self):
        events = opening("u") + [
            signoff(2, ["a.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
            steering(4),
            accept(5, 3, [("a.rst", "h1")], withdraws=[{"seq": 4, "reason": ""}]),
        ]
        self.assertEqual(self.report(events)["V10"]["status"], "fail")

    # V11 / V12

    def test_v11_fails_on_a_model_inconsistent_with_its_origin(self):
        gen = generation(3, [("a.rst", "h1")], signoff_seq=2)
        gen["model_origin"] = "unknown"
        events = opening("u") + [signoff(2, ["a.rst"]), gen]
        self.assertEqual(self.report(events)["V11"]["status"], "fail")

    def test_v12_fails_on_a_reuse_plan_with_no_reuse_note(self):
        events = opening("u") + [
            signoff(2, ["a.rst"], intent="how-to"),
            planned(3, [("s1", "run it", "agent", False)]),
            planned(4, [("s1", "run it", "agent", False)], replaces=3, reuse=True),
        ]
        self.assertEqual(self.report(events)["V12"]["status"], "fail")

    def test_v12_accepts_a_reuse_plan_that_states_its_reason(self):
        second = planned(4, [("s1", "run it", "agent", False)], replaces=3, reuse=True)
        second["reuse_note"] = "the walk is unchanged"
        events = opening("u") + [
            signoff(2, ["a.rst"], intent="how-to"),
            planned(3, [("s1", "run it", "agent", False)]),
            second,
        ]
        self.assertEqual(self.report(events)["V12"]["status"], "ok")

    # V13 — files against the signed targets

    def test_v13_fails_when_a_generations_files_are_not_the_signed_targets(self):
        events = opening("u") + [
            signoff(2, ["a.rst", "b.rst"]),
            generation(3, [("a.rst", "h1")], signoff_seq=2),
        ]
        self.assertEqual(self.report(events)["V13"]["status"], "fail")

    def test_v13_fails_when_a_reviewer_edit_drops_a_still_signed_basis_path(self):
        events = opening("u") + [
            signoff(2, ["a.rst", "b.rst"]),
            generation(3, [("a.rst", "h1"), ("b.rst", "h2")], signoff_seq=2),
            reviewer_edit(4, [("a.rst", "h3")], generation_seq=3),
        ]
        self.assertEqual(self.report(events)["V13"]["status"], "fail")

    def test_v13_lets_a_reviewer_edit_drop_a_path_that_is_no_longer_a_target(self):
        events = opening("u") + [
            signoff(2, ["a.rst", "b.rst"]),
            generation(3, [("a.rst", "h1"), ("b.rst", "h2")], signoff_seq=2),
            signoff(4, ["a.rst"], plan_hash="P2"),
            reviewer_edit(5, [("a.rst", "h3")], generation_seq=3),
        ]
        self.assertEqual(self.report(events)["V13"]["status"], "ok")

    # The vacuous record — probe 28's first half

    def test_a_declared_unit_reports_v5_to_v13_ok_with_a_detail_each(self):
        rows = self.report(opening("u"))
        for number in range(5, 14):
            vid = "V%d" % number
            self.assertEqual(rows[vid]["status"], "ok", vid)
            self.assertTrue(rows[vid]["detail"], "%s reported ok in silence" % vid)

    def test_an_unknown_kind_is_ignored_by_every_gate(self):
        """5.9: gates run over known kinds only; the one WARN is derive()'s."""
        events = self.sealed() + [ev("telemetry", 7, note="x"), ev("telemetry", 8)]
        rows = self.report(events)
        for number in range(5, 14):
            vid = "V%d" % number
            self.assertEqual(rows[vid]["status"], "ok", "%s: %s" % (vid, rows[vid]["detail"]))

    def test_the_reserved_superseded_by_field_is_not_evaluated(self):
        events = self.sealed()
        events[-1] = dict(events[-1], superseded_by=99)
        rows = self.report(events)
        for number in range(5, 14):
            self.assertEqual(rows["V%d" % number]["status"], "ok")

    def test_v5_to_v13_are_all_fail_level(self):
        for row in dogen.verify_derivation(self.sealed()):
            self.assertEqual(row["level"], "fail", row["id"])


class TestVerifyPageCurrency(TempRepoTestCase):
    """V14 — page currency, rendered by the same function ``show`` calls."""

    def build(self, disk=b"page\n", recorded_bytes=None, targets=("reference/p.rst",)):
        (self.repo / "docs" / "reference").mkdir(parents=True, exist_ok=True)
        page = self.repo / "docs" / "reference" / "p.rst"
        if disk is not None:
            page.write_bytes(disk)
        elif page.exists():
            page.unlink()
        sealed = recorded_bytes if recorded_bytes is not None else disk
        digest = hashlib.sha256(sealed or b"").hexdigest()
        events = opening("u") + [
            signoff(2, list(targets)),
            generation(3, [("reference/p.rst", digest)], signoff_seq=2),
        ]
        snapshot = dogen.read_fs(self.repo, "u", ["reference/p.rst"], list(targets))
        state = dogen.derive(events, snapshot)
        return by_id(dogen.verify_currency(self.repo, state, snapshot["paths"]))

    def test_v14_reports_a_path_whose_bytes_equal_the_digest_as_current(self):
        rows = self.build()
        self.assertEqual(rows["V14"]["status"], "ok")
        self.assertIn("current", rows["V14"]["detail"])

    def test_v14_reports_changed_bytes_as_drifted(self):
        rows = self.build(disk=b"edited\n", recorded_bytes=b"page\n")
        self.assertEqual(rows["V14"]["status"], "warn")
        self.assertIn("drifted", rows["V14"]["detail"])

    def test_v14_reports_an_absent_page_as_missing(self):
        rows = self.build(disk=None, recorded_bytes=b"page\n")
        self.assertEqual(rows["V14"]["status"], "warn")
        self.assertIn("missing", rows["V14"]["detail"])

    def test_v14_is_never_a_fail_level_check(self):
        for case in ({}, {"disk": b"edited\n", "recorded_bytes": b"page\n"},
                     {"disk": None, "recorded_bytes": b"page\n"}):
            rows = self.build(**case)
            self.assertEqual(rows["V14"]["level"], "status")
            self.assertNotEqual(rows["V14"]["status"], "fail")

    def test_v14_renders_through_the_same_drift_vocabulary_show_uses(self):
        with mock.patch.object(
            dogen, "describe_paths", wraps=dogen.describe_paths
        ) as spy:
            self.build(disk=b"edited\n", recorded_bytes=b"page\n")
        self.assertTrue(spy.called, "V14 must re-label describe_paths, not restate it")

    def test_v14_lists_an_orphan_without_calling_it_drift(self):
        (self.repo / "docs" / "reference").mkdir(parents=True, exist_ok=True)
        page = self.repo / "docs" / "reference" / "p.rst"
        page.write_bytes(b"page\n")
        digest = hashlib.sha256(b"page\n").hexdigest()
        events = opening("u") + [
            signoff(2, ["reference/p.rst"]),
            generation(3, [("reference/p.rst", digest)], signoff_seq=2),
            signoff(4, ["reference/q.rst"], plan_hash="P2"),
        ]
        snapshot = dogen.read_fs(self.repo, "u", ["reference/p.rst"], ["reference/q.rst"])
        state = dogen.derive(events, snapshot)
        rows = by_id(dogen.verify_currency(self.repo, state, snapshot["paths"]))
        self.assertIn("reference/p.rst", rows["V14"]["detail"])
        self.assertIn("no longer a target", rows["V14"]["detail"])

    def test_v14_is_vacuously_ok_with_no_basis(self):
        events = opening("u") + [signoff(2, ["reference/p.rst"])]
        state = dogen.derive(events, fs_of(None))
        rows = by_id(dogen.verify_currency(self.repo, state, {}))
        self.assertEqual(rows["V14"]["status"], "ok")
        self.assertTrue(rows["V14"]["detail"])


class VerifyRepoTestCase(TempRepoTestCase):
    """A temp repo carrying one hand-written, committed unit ledger."""

    UNIT = "u"

    def hygiene(self):
        """The two facts V17 asks git about, in a repository that has them."""
        (self.repo / ".gitignore").write_text(".dogen/staging/\n", encoding="utf-8")
        (self.repo / ".dogen").mkdir(exist_ok=True)
        (self.repo / ".dogen" / ".gitattributes").write_text(
            "*.jsonl -text\n", encoding="utf-8"
        )

    def write_unit(self, events, commit=True, trailers=False):
        """Write ``events`` as the unit's ledger; optionally commit every line.

        ``trailers`` writes the ``Dogen-Unit`` / ``Dogen-Seq`` pair a real
        transition commits with. Without it the committed lines have no trailer
        commit behind them, which is exactly V15's ``history_squashed`` case —
        so the flag is what separates "a plain commit" from "the commit dogen
        would have made".
        """
        ledger = self.repo / ".dogen" / "units" / self.UNIT / "ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        lines = lines_of(events)
        ledger.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
        if commit:
            self.git("add", "-A")
            args = ["commit", "-q", "-m", "dogen: declared %s" % self.UNIT]
            if trailers:
                args += [
                    "--trailer",
                    "Dogen-Unit: %s" % self.UNIT,
                    "--trailer",
                    "Dogen-Seq: 0-%d" % (len(lines) - 1),
                ]
            self.git(*args)
        return lines

    def verify(self):
        events, snapshot, state = dogen.unit_view(self.repo, self.UNIT)
        return dogen.run_verify(self.repo, self.UNIT, events, snapshot, state)


class TestVerifyReportShape(VerifyRepoTestCase):
    """Probe 28 (empty) and probe 29 (ordering) — the report's own shape."""

    def test_the_ids_are_v1_to_v19_in_ascending_order_with_no_gaps(self):
        """Probe 29: ascending V order, and the summary line after all of them."""
        self.write_unit(opening(self.UNIT))
        ids = [row["id"] for row in self.verify()]
        self.assertEqual(ids, ["V%d" % n for n in range(1, 20)])

    def test_every_id_from_v1_to_v19_appears_exactly_once(self):
        self.write_unit(opening(self.UNIT))
        rows = by_id(self.verify())
        for number in range(1, 20):
            self.assertIn("V%d" % number, rows)

    def test_every_record_carries_an_id_a_level_a_status_and_a_detail(self):
        self.write_unit(opening(self.UNIT))
        for row in self.verify():
            self.assertEqual(sorted(row), ["detail", "id", "level", "status"])
            self.assertIn(row["level"], ("fail", "status", "warn", "info"))
            self.assertIn(row["status"], ("ok", "warn", "fail"))
            self.assertTrue(row["detail"], "%s reported in silence" % row["id"])

    def test_a_header_and_a_declaration_alone_verify_ok(self):
        """Probe 28: most checks are vacuous, and vacuous is not a warning.

        The repository's own hygiene is fixed first so the verdict answers the
        question actually being asked — is a unit with no history ok? — rather
        than reporting a missing ignore pattern that has nothing to do with it.
        """
        self.hygiene()
        # `commit: null` is what a transition in a repository with no prior
        # commit records, so V16 has nothing to place and says so.
        events = [dict(event, commit=None) for event in opening(self.UNIT)]
        self.write_unit(events, trailers=True)
        checks = self.verify()
        self.assertEqual(
            dogen.verify_summary(checks)["verdict"],
            "ok",
            [row for row in checks if row["status"] != "ok"],
        )

    def test_only_a_fail_level_check_can_report_a_fail_status(self):
        self.write_unit(opening(self.UNIT))
        for row in self.verify():
            if row["status"] == "fail":
                self.assertEqual(row["level"], "fail", row["id"])

    def test_the_verdict_and_the_counts_come_from_the_statuses(self):
        checks = [
            dogen.check_record("V1", True, "ok"),
            dogen.check_record("V3", False, "broken"),
            dogen.check_record("V14", False, "drifted"),
        ]
        counts = dogen.verify_summary(checks)
        self.assertEqual(counts["verdict"], "fail")
        self.assertEqual(counts["fail"], 1)
        self.assertEqual(counts["warn"], 1)
        self.assertEqual(counts["failed"], ["V3"])

    def test_a_note_alone_makes_the_verdict_warn(self):
        counts = dogen.verify_summary(
            [dogen.check_record("V1", True, "ok")], ["ignored 1 event of unknown kind"]
        )
        self.assertEqual(counts["verdict"], "warn")
        self.assertEqual(counts["warn"], 1)

    def test_there_is_exactly_one_derivation_behind_the_report(self):
        source = DOGEN_PATH.read_text(encoding="utf-8")
        self.assertEqual(source.count("\ndef derive("), 1)


class TestVerifyCorroboration(VerifyRepoTestCase):
    """V15–V19 — git corroboration, which may warn and can never fail.

    Contract 5.9 fixes these five at WARN and INFO because the chain is
    tamper-EVIDENCE, not tamper-proofing: a maintenance edit or a squash merge
    reported as a failure trains the reader to ignore the one signal that means
    the record is actually broken (T-17-40).
    """

    def signed(self, targets=("reference/p.rst",), context=None, commit="0" * 40):
        events = opening(self.UNIT) + [signoff(2, list(targets))]
        events[-1]["context"] = dict(context or {})
        for event in events:
            event["commit"] = commit
        return events

    def corroborate(self, events, committed=0):
        snapshot = dogen.read_fs(self.repo, self.UNIT, [], [])
        state = dogen.derive(events, snapshot)
        return by_id(
            dogen.verify_corroboration(self.repo, self.UNIT, events, state, committed)
        )

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def freeze_plan(self, body=b"# Plan\n"):
        """Write a ``unit.md`` and return the digest a signoff would freeze."""
        unit_md = self.repo / ".dogen" / "units" / self.UNIT / "unit.md"
        unit_md.parent.mkdir(parents=True, exist_ok=True)
        unit_md.write_bytes(body)
        return hashlib.sha256(body).hexdigest()

    # V15 — trailer commits for every committed seq

    def test_v15_warns_when_committed_lines_have_no_trailer_commit(self):
        events = self.signed()
        self.write_unit(events)
        rows = self.corroborate(events, committed=3)
        self.assertEqual(rows["V15"]["status"], "warn")
        self.assertIn("history_squashed", rows["V15"]["detail"])

    def test_v15_is_vacuously_ok_with_nothing_committed(self):
        events = self.signed()
        self.write_unit(events, commit=False)
        rows = self.corroborate(events, committed=0)
        self.assertEqual(rows["V15"]["status"], "ok")
        self.assertTrue(rows["V15"]["detail"])

    # V16 — the recorded pre-transition HEAD in this history

    def test_v16_is_silent_when_the_trailers_are_gone_and_v15_named_it(self):
        """One rewrite, reported once, under its most specific name."""
        events = self.signed()
        self.write_unit(events)
        rows = self.corroborate(events, committed=3)
        self.assertEqual(rows["V15"]["status"], "warn")
        self.assertEqual(rows["V16"]["status"], "ok")

    def test_v16_is_ok_when_every_recorded_commit_is_an_ancestor(self):
        self.write_unit(self.signed(), commit=True)
        events = self.signed(commit=self.head())
        rows = self.corroborate(events, committed=0)
        self.assertEqual(rows["V16"]["status"], "ok")

    # V17 — the ignore patterns and the git attributes

    def test_v17_warns_and_names_what_is_missing(self):
        events = self.signed()
        self.write_unit(events)
        rows = self.corroborate(events, committed=3)
        self.assertEqual(rows["V17"]["status"], "warn")
        self.assertEqual(rows["V17"]["level"], "info")
        self.assertIn(".dogen/staging", rows["V17"]["detail"])
        self.assertIn("jsonl", rows["V17"]["detail"])

    def test_v17_is_ok_once_both_are_in_place(self):
        (self.repo / ".gitignore").write_text(".dogen/staging/\n", encoding="utf-8")
        (self.repo / ".dogen").mkdir(exist_ok=True)
        (self.repo / ".dogen" / ".gitattributes").write_text("*.jsonl -text\n", encoding="utf-8")
        events = self.signed()
        self.write_unit(events)
        rows = self.corroborate(events, committed=3)
        self.assertEqual(rows["V17"]["status"], "ok")

    # V18 — one target, more than one live unit

    def sibling(self, name, targets, retired=False):
        events = opening(name) + [signoff(2, list(targets))]
        if retired:
            events.append(ev("retired", 3, note="superseded"))
        ledger = self.repo / ".dogen" / "units" / name / "ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(
            "".join(line + "\n" for line in lines_of(events)), encoding="utf-8"
        )

    def test_v18_warns_and_names_both_units(self):
        events = self.signed()
        self.write_unit(events, commit=False)
        self.sibling("other", ["reference/p.rst"])
        rows = self.corroborate(events, committed=0)
        self.assertEqual(rows["V18"]["status"], "warn")
        self.assertIn("other", rows["V18"]["detail"])
        self.assertIn(self.UNIT, rows["V18"]["detail"])

    def test_v18_is_cleared_by_retiring_the_sibling(self):
        events = self.signed()
        self.write_unit(events, commit=False)
        self.sibling("other", ["reference/p.rst"], retired=True)
        self.assertEqual(self.corroborate(events, committed=0)["V18"]["status"], "ok")

    # V19 — the context digests and the plan

    def test_v19_warns_when_a_recorded_source_has_changed(self):
        source = self.repo / "source.md"
        events = self.signed(context={"source.md": "0" * 64})
        self.write_unit(events, commit=False)
        self.assertTrue(source.exists())
        rows = self.corroborate(events, committed=0)
        self.assertEqual(rows["V19"]["status"], "warn")
        self.assertIn("source.md", rows["V19"]["detail"])

    def test_v19_is_ok_when_the_digests_still_match(self):
        digest = hashlib.sha256((self.repo / "source.md").read_bytes()).hexdigest()
        events = self.signed(context={"source.md": digest})
        events[-1]["plan_hash"] = self.freeze_plan()
        self.write_unit(events, commit=False)
        self.assertEqual(self.corroborate(events, committed=0)["V19"]["status"], "ok")

    def test_v19_warns_plan_stale_by_name(self):
        unit_md = self.repo / ".dogen" / "units" / self.UNIT / "unit.md"
        unit_md.parent.mkdir(parents=True, exist_ok=True)
        unit_md.write_text("# edited by hand\n", encoding="utf-8")
        events = self.signed()
        self.write_unit(events, commit=False)
        snapshot = dogen.read_fs(self.repo, self.UNIT, [], [])
        state = dogen.derive(events, snapshot)
        rows = by_id(
            dogen.verify_corroboration(self.repo, self.UNIT, events, state, 0)
        )
        self.assertEqual(rows["V19"]["status"], "warn")
        self.assertIn("plan_stale", rows["V19"]["detail"])

    # The property the whole group exists to hold

    def test_no_check_from_v15_to_v19_can_report_a_fail(self):
        """Each of the five driven into its worst case.

        V15 and V16 are mutually exclusive by design — a history whose trailer
        commits are gone is reported ONCE, by V15 — so the sweep runs both
        configurations and asserts the property across them: never a ``fail``,
        always ``warn`` or ``info``, and each of the five does warn somewhere.
        """
        events = self.signed(context={"source.md": "0" * 64})
        self.write_unit(events)
        self.sibling("other", ["reference/p.rst"])
        (self.repo / ".dogen" / "units" / self.UNIT / "unit.md").write_text(
            "# edited by hand\n", encoding="utf-8"
        )
        warned = set()
        for committed in (3, 0):
            rows = self.corroborate(events, committed=committed)
            for number in range(15, 20):
                row = rows["V%d" % number]
                self.assertIn(row["level"], ("warn", "info"), row["id"])
                self.assertNotEqual(
                    row["status"], "fail", "%s: %s" % (row["id"], row["detail"])
                )
                if row["status"] == "warn":
                    warned.add(row["id"])
        self.assertEqual(warned, set("V%d" % n for n in range(15, 20)))

    def test_the_whole_report_carries_v1_through_v19_once_each(self):
        self.write_unit(opening(self.UNIT))
        rows = self.verify()
        self.assertEqual([row["id"] for row in rows], ["V%d" % n for n in range(1, 20)])


class TestEscapeHintHistory(unittest.TestCase):
    def test_attempt_history_never_suppresses_the_unblocked_remedy(self):
        for attempts in (2, 4, 100):
            with self.subTest(attempts=attempts), mock.patch.object(
                dogen, "read_progress", return_value={"transition_attempts": attempts}
            ):
                hint = dogen.escape_hint(None, "u1", "REMEDY")
                for marker in ("attempted %d times" % attempts,
                               "if something is still refusing",
                               "With nothing refusing it, REMEDY"):
                    with self.subTest(marker=marker):
                        self.assertIn(marker, hint)
                with self.subTest(prediction="no present obstruction inferred"):
                    self.assertNotIn("would re-place the same bytes and be refused again", hint)

    def test_the_escape_is_emitted_below_two_attempts_too(self):
        """WR-02(a) — the helper used to return ``otherwise`` verbatim.

        S-13 credits every calling site with this helper's text, so a first
        attempt on a batch a hook is still rejecting printed only the remedy —
        naming the one command that cannot work, with no warning and no way
        out. The counter is the only thing history can honestly claim; the
        escape is unconditional.
        """
        for attempts in (0, 1):
            with self.subTest(attempts=attempts), mock.patch.object(
                dogen, "read_progress", return_value={"transition_attempts": attempts}
            ):
                hint = dogen.escape_hint(None, "u1", "REMEDY")
                self.assertIn("remove what is refusing the transition", hint)
                self.assertIn("With nothing refusing it, REMEDY", hint)
                self.assertNotEqual(hint, "REMEDY")
                # And it does not invent a history it does not have.
                self.assertNotIn("attempted", hint)


# --- phase 18: the phase-16 review warnings deferred to this phase ----------
#
# WR-16 … WR-20 were deferred from phase 16's fourth review round with one
# instruction attached to each: close it in code AND leave behind a test that
# goes red if the defect returns. WR-18 and WR-19 are that second half alone —
# the code was already right and nothing asserted it, which is the "a green
# suite whose assertions cannot fail" shape this phase exists against.


class DogenCliTestCase(TempRepoTestCase):
    """A temp repo plus the real `dogen` executable, for the GATE-04 shape.

    The unit suite reaches `dogen`'s internals through `_load_dogen()`; a
    refusal's ONE-JSON-LINE-on-stderr promise is a property of the process, so
    the handful of assertions about it drive the executable instead.
    """

    def setUp(self):
        super().setUp()
        (self.repo / "docs" / "reference").mkdir(parents=True)
        (self.repo / "docs" / "index.md").write_text("# Docs\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "docs root")

    def dogen_cli(self, *args, **kwargs):
        return subprocess.run(
            [sys.executable, str(DOGEN_PATH)] + list(args),
            cwd=str(self.repo),
            env=self.env,
            capture_output=True,
            text=True,
            input=kwargs.get("stdin", "# Plan\n\nAn outline.\n"),
        )

    def declare(self, unit, target="reference/demo.rst", *extra):
        return self.dogen_cli(
            "unit", "new", unit,
            "--intent", "reference",
            "--audience", "TAs onboarding to the docs repo",
            "--title", "Demo",
            "--target", target,
            "--body-file", "-",
            *extra
        )

    def one_refusal(self, proc):
        """The single stderr JSON line, with the five keys GATE-04 requires."""
        lines = [line for line in proc.stderr.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, "GATE-04: exactly one line, got %r" % lines)
        self.assertNotIn("Traceback", proc.stderr)
        payload = json.loads(lines[0])
        for key in ("error", "unit", "detail", "hint", "next"):
            self.assertIn(key, payload)
        return payload


class TestWr16GitAddDetail(unittest.TestCase):
    """WR-16 — offenders past the third are counted, never silently dropped."""

    IGNORE_HEADER = "The following paths are ignored by one of your .gitignore files:"

    def test_wr16_a_fourth_offender_is_named_or_its_omission_is_counted(self):
        stderr = "%s\n%s\nhint: Use -f if you really want to add them.\n" % (
            self.IGNORE_HEADER,
            "\n".join("docs/reference/%s.rst" % letter for letter in "abcd"),
        )
        detail = dogen._git_add_detail(stderr)
        named = sum(
            1 for letter in "abcd" if "docs/reference/%s.rst" % letter in detail
        )
        self.assertTrue(
            named == 4 or ("and %d more" % (4 - named)) in detail,
            "WR-16: %d of 4 offenders named with no count: %r" % (named, detail),
        )

    def test_wr16_a_large_offender_set_states_how_many_it_omitted(self):
        stderr = "%s\n%s\n" % (
            self.IGNORE_HEADER,
            "\n".join("docs/reference/p%d.rst" % n for n in range(9)),
        )
        detail = dogen._git_add_detail(stderr)
        shown = sum(1 for n in range(9) if "docs/reference/p%d.rst" % n in detail)
        self.assertTrue(
            shown == 9 or ("and %d more" % (9 - shown)) in detail,
            "WR-16: %d of 9 offenders named with no count: %r" % (shown, detail),
        )

    def test_wr16_gits_own_diagnostics_are_never_presented_as_offenders(self):
        """The positional parse holds only when the block is alone on stderr."""
        stderr = (
            "%s\n"
            "docs/reference/b.rst\n"
            "hint: Use -f if you really want to add them.\n"
            "error: 'docs/reference/embedded/' does not have a commit checked out\n"
            "warning: adding embedded git repository\n"
            "fatal: adding files failed\n" % self.IGNORE_HEADER
        )
        detail = dogen._git_add_detail(stderr)
        self.assertIn("docs/reference/b.rst", detail)
        for prefix in ("hint:", "error:", "warning:", "fatal:"):
            self.assertNotIn(prefix, detail, "WR-16: %r is git's UI, not a path" % prefix)

    def test_wr16_a_single_line_stderr_is_unchanged(self):
        one = "fatal: pathspec 'docs/reference/l.rst' is beyond a symbolic link"
        self.assertEqual(dogen._git_add_detail(one), one)

    def test_wr16_empty_stderr_still_has_an_answer(self):
        self.assertEqual(dogen._git_add_detail(""), "git add failed")


class TestIn03TheProbeIsLocalePinned(unittest.TestCase):
    """Phase-16 IN-03 — the positional read of git's stderr is safe only pinned.

    `_git_add_detail` reads git's first line positionally and filters git's own
    diagnostic prefixes by name. Both are English facts, and what makes them
    true is that `guard_ignored_paths` runs the probe under `IPC_LOCALE`.
    Nothing asserted that coupling, so dropping `env=IPC_LOCALE` would have
    turned every ignore refusal into a mistranslated one under any other
    `LC_MESSAGES` with the whole suite still green.
    """

    def test_in03_the_locale_overlay_pins_messages_to_c(self):
        self.assertEqual(dogen.IPC_LOCALE.get("LC_ALL"), "C")
        self.assertEqual(dogen.IPC_LOCALE.get("LANGUAGE"), "")

    def test_in03_the_ignore_probe_is_run_under_the_pinned_locale(self):
        tree = ast.parse(DOGEN_PATH.read_text(encoding="utf-8"))
        node = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "guard_ignored_paths"
        )
        pinned = [
            call for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and getattr(call.func, "id", "") == "git"
            and any(
                keyword.arg == "env" and getattr(keyword.value, "id", "") == "IPC_LOCALE"
                for keyword in call.keywords
            )
        ]
        self.assertTrue(
            pinned,
            "IN-03: the probe must pin IPC_LOCALE — _git_add_detail reads its "
            "stderr positionally and by English prefix",
        )


class TestWr17SourcesAreCheckedWhereTheyAreDeclared(TempRepoTestCase):
    """WR-17 — a plan `signoff` can never sign is never written."""

    def test_wr17_a_missing_source_is_refused_by_the_declaring_guard(self):
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.guard_source_files(self.repo, ["docs/never-existed.md"], "u1")
        self.assertEqual(caught.exception.reason, "unit_invalid")
        self.assertIn(caught.exception.reason, dogen.REASONS)
        self.assertIn("never-existed.md", caught.exception.detail)

    def test_wr17_a_directory_source_is_refused_by_the_declaring_guard(self):
        (self.repo / "docs").mkdir()
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.guard_source_files(self.repo, ["docs"], "u1")
        self.assertEqual(caught.exception.reason, "unit_invalid")

    def test_wr17_a_readable_in_repo_source_passes(self):
        self.assertEqual(
            dogen.guard_source_files(self.repo, ["source.md"], "u1"), ["source.md"]
        )

    def test_wr17_both_declaring_verbs_ask_the_guard(self):
        """Stage b, before anything is written — not stage f's regret."""
        tree = ast.parse(DOGEN_PATH.read_text(encoding="utf-8"))
        for verb in ("cmd_unit_new", "cmd_unit_edit"):
            with self.subTest(verb=verb):
                node = next(
                    n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == verb
                )
                self.assertTrue(
                    [
                        call for call in ast.walk(node)
                        if isinstance(call, ast.Call)
                        and getattr(call.func, "id", "") == "guard_source_files"
                    ],
                    "WR-17: %s commits a plan signoff can never sign" % verb,
                )

    def test_wr17_signoff_still_asks_too(self):
        """unit.md is a plain file an author may hand-edit; both guards stay."""
        tree = ast.parse(DOGEN_PATH.read_text(encoding="utf-8"))
        node = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "sign_sources"
        )
        self.assertTrue(
            [
                call for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and getattr(call.func, "id", "") == "guard_source_files"
            ],
            "WR-17: declaration-time validation may not be the ONLY guard",
        )


class TestWr17DeclaringVerbWritesNothing(DogenCliTestCase):
    """WR-17, end to end: the refusal happens before the ledger exists."""

    def test_wr17_unit_new_appends_no_ledger_line_for_an_unsignable_source(self):
        proc = self.declare("u1", "reference/u1.rst", "--source", "docs/never.md")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        payload = self.one_refusal(proc)
        self.assertEqual(payload["error"], "unit_invalid")
        self.assertIn(payload["error"], dogen.REASONS)
        self.assertFalse((self.repo / ".dogen" / "units" / "u1").exists())

    def test_wr17_unit_edit_is_the_named_way_back(self):
        """`--source` REPLACES the list, so a declared source can be repointed."""
        self.assertEqual(
            self.declare("u2", "reference/u2.rst", "--source", "docs/index.md").returncode,
            0,
        )
        proc = self.dogen_cli("unit", "edit", "u2", "--source", "source.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(
            "source.md",
            (self.repo / ".dogen" / "units" / "u2" / "unit.md").read_text(
                encoding="utf-8"
            ),
        )


class TestWr18BusyNamesItsUnitAtTheRaiser(TempRepoTestCase):
    """WR-18 — the assertion binds to the raiser, not to a shared observable.

    `main` falls back to `_argv_unit(args)` when a refusal carries no unit, so
    an end-to-end assertion on the refusal's `unit` field is satisfied by the
    fallback ALONE: deleting `unit=unit` from `acquire_lock`'s `busy` raiser
    left the whole suite green. Asked here, of the raiser's own exception
    object, the fallback cannot answer for it.
    """

    def test_wr18_the_lock_raiser_populates_unit_itself(self):
        held = dogen.acquire_lock(self.repo, "held-unit")
        self.addCleanup(dogen.release_lock, held)
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.acquire_lock(self.repo, "lk-unit")
        self.assertEqual(caught.exception.reason, "busy")
        self.assertEqual(caught.exception.unit, "lk-unit")

    def test_wr18_the_busy_raiser_is_about_dogens_own_lock(self):
        """Negative keystone: `busy` is never git's index lock (`git_busy`)."""
        held = dogen.acquire_lock(self.repo, "held-unit")
        self.addCleanup(dogen.release_lock, held)
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.acquire_lock(self.repo, "other-unit")
        self.assertIn(".dogen/staging/lock", caught.exception.detail)
        self.assertNotIn("index.lock", caught.exception.detail)


class TestWr19ReadEventsLedgerCorruptArm(TempRepoTestCase):
    """WR-19 — the claim-policy half of WR-09, asserted at the raiser.

    `read_events`' two `ledger_corrupt` arms are reachable in production only
    through `find_claim` -> `unit_state(sibling)`, because for the CURRENT unit
    `classify_stage_a`'s `_read_text` always fires first. Deleting either arm
    used to leave the suite green.
    """

    def ledger(self, payload):
        path = self.repo / "ledger.jsonl"
        if isinstance(payload, bytes):
            path.write_bytes(payload)
        else:
            path.write_text(payload, encoding="utf-8")
        return str(path)

    def test_wr19_an_unparseable_line_raises_ledger_corrupt(self):
        path = self.ledger('{"kind":"ledger"}\nthis is not json\n')
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_events(path, "u1")
        self.assertEqual(caught.exception.reason, "ledger_corrupt")
        self.assertEqual(caught.exception.unit, "u1")
        self.assertEqual(caught.exception.next_token, "resume")
        self.assertIn("line 2", caught.exception.detail)

    def test_wr19_undecodable_bytes_raise_ledger_corrupt_at_read_events(self):
        path = self.ledger(b'{"kind":"ledger","note":"\xff\xfe"}\n')
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_events(path, "u1")
        self.assertEqual(caught.exception.reason, "ledger_corrupt")
        self.assertEqual(caught.exception.next_token, "resume")

    def test_wr19_the_arm_never_leaks_an_absolute_path(self):
        path = self.ledger("not json\n")
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.read_events(path, "u1")
        self.assertNotIn(str(self.repo), caught.exception.hint)


class TestWr19TheRefusalIsOneGate04Line(DogenCliTestCase):
    """WR-19, end to end: the five keys, one line, no traceback."""

    def test_wr19_a_corrupt_ledger_refuses_in_the_gate04_shape(self):
        self.assertEqual(self.declare("u1", "reference/u1.rst").returncode, 0)
        with open(
            self.repo / ".dogen" / "units" / "u1" / "ledger.jsonl", "a",
            encoding="utf-8",
        ) as handle:
            handle.write("this is not json\n")
        proc = self.dogen_cli("show", "u1")
        self.assertEqual(proc.returncode, 6, proc.stderr)
        payload = self.one_refusal(proc)
        self.assertEqual(payload["error"], "ledger_corrupt")
        self.assertEqual(payload["next"], "resume")


class TestWr20ADirectoryLedgerIsOneAnswer(TempRepoTestCase):
    """WR-20 — the two readers of the same file agree on the third case.

    `_read_text` called a directory ABSENT (derive state from nothing — the
    silent wrong answer its own docstring exists to prevent) while
    `read_events` let `IsADirectoryError` escape to `main`'s OSError backstop,
    so `dogen show` reported `ledger_diverged` — "the committed record was
    rewritten" — about a record that is a directory.
    """

    def reason_from(self, reader, path):
        try:
            reader(path, "u1")
        except dogen.Refusal as refusal:
            return refusal.reason
        except OSError as bad:
            return "unhandled %s" % type(bad).__name__
        return "no refusal at all"

    def test_wr20_read_events_names_a_directory_ledger(self):
        path = self.repo / "ledger.jsonl"
        path.mkdir()
        self.assertEqual(
            self.reason_from(dogen.read_events, str(path)), "ledger_corrupt"
        )

    def test_wr20_read_text_names_it_the_same_way(self):
        path = self.repo / "ledger.jsonl"
        path.mkdir()
        self.assertEqual(
            self.reason_from(dogen._read_text, str(path)), "ledger_corrupt"
        )

    def test_wr20_an_absent_ledger_is_still_absent_to_both(self):
        """Negative keystone: agreement must not be bought by refusing more."""
        path = str(self.repo / "nothing-here.jsonl")
        self.assertEqual(dogen.read_events(path, "u1"), [])
        self.assertEqual(dogen._read_text(path, "u1"), "")


class TestWr20TheDirectoryLedgerRefusalIsNamed(DogenCliTestCase):
    """WR-20, end to end: one named JSON line, and no Python traceback."""

    def test_wr20_a_directory_ledger_refuses_without_a_traceback(self):
        self.assertEqual(self.declare("u1", "reference/u1.rst").returncode, 0)
        ledger = self.repo / ".dogen" / "units" / "u1" / "ledger.jsonl"
        ledger.unlink()
        ledger.mkdir()
        proc = self.dogen_cli("show", "u1")
        payload = self.one_refusal(proc)
        self.assertEqual(payload["error"], "ledger_corrupt")
        self.assertEqual(proc.returncode, dogen.REASONS["ledger_corrupt"])


# --- phase 18: the small Info items phases 16 and 17 deferred ---------------


class TestIn01TheLockMustBeARealFile(TempRepoTestCase):
    """Phase-16 IN-01 — "not a symlink" is narrower than "is a real file".

    The refusal text and the docstring both say the lock "must be a real file",
    but only `islink` and `O_NOFOLLOW` were enforced, and `O_NOFOLLOW` rejects
    only ELOOP/EISDIR/ENOTDIR. A FIFO at `.dogen/staging/lock` was opened and
    locked successfully, so the repository's write mutex became an object
    `flock` does not guard the way the six steps assume.
    """

    def lock_path(self):
        path = self.repo / ".dogen" / "staging" / "lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def refusal_from_acquire(self):
        try:
            fd = dogen.acquire_lock(self.repo, "lk-unit")
        except dogen.Refusal as refusal:
            return refusal.reason
        except OSError as bad:
            return "unhandled %s" % type(bad).__name__
        dogen.release_lock(fd)
        return "acquired anyway"

    def test_in01_a_fifo_at_the_lock_path_is_refused(self):
        os.mkfifo(str(self.lock_path()))
        self.assertEqual(self.refusal_from_acquire(), "bad_write_path")

    def test_in01_a_directory_at_the_lock_path_is_still_refused(self):
        """WR-15's boundary: the errno arm keeps its own wording."""
        self.lock_path().mkdir()
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.acquire_lock(self.repo, "lk-unit")
        self.assertEqual(caught.exception.reason, "bad_write_path")
        self.assertIn("EISDIR", caught.exception.detail)

    def test_in01_a_symlink_at_the_lock_path_is_still_refused_by_name(self):
        path = self.lock_path()
        os.symlink("/tmp/somewhere-else", str(path))
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.acquire_lock(self.repo, "lk-unit")
        self.assertEqual(caught.exception.reason, "bad_write_path")
        self.assertIn("symlink", caught.exception.detail)

    def test_in01_a_regular_lock_file_still_locks(self):
        """Negative keystone: the widened check must not refuse the real case."""
        fd = dogen.acquire_lock(self.repo, "lk-unit")
        dogen.release_lock(fd)
        self.assertTrue(self.lock_path().is_file())


class TestIn02NoUnreferencedDefinitionSurvives(unittest.TestCase):
    """Phase-16 IN-02 — `Refusal.exit_code` and `validate_step_id` were dead.

    A definition nothing reaches is a claim nothing checks. `validate_step_id`
    acquired two callers with the phase-17 step verbs; `Refusal.exit_code`
    never did — `refuse()` is the one place the contract's exit code is chosen,
    and a second way to spell it is a second opinion waiting to drift.
    """

    def source(self):
        return DOGEN_PATH.read_text(encoding="utf-8")

    def test_in02_the_refusal_carries_no_unreferenced_exit_code_property(self):
        self.assertFalse(
            hasattr(dogen.Refusal("busy"), "exit_code"),
            "IN-02: refuse() chooses the exit code; a second speller drifts",
        )

    def test_in02_validate_step_id_is_reached_by_a_caller(self):
        tree = ast.parse(self.source())
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", "") == "validate_step_id"
        ]
        self.assertTrue(calls, "IN-02: validate_step_id must be reached or deleted")

    def test_in02_every_module_level_helper_is_reached_or_gone(self):
        """The rule generalised over the two names the row listed."""
        tree = ast.parse(self.source())
        called = {
            getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            for node in ast.walk(tree) if isinstance(node, ast.Call)
        }
        for name in ("validate_step_id", "exit_code"):
            defined = [
                node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name
            ]
            with self.subTest(name=name):
                self.assertTrue(
                    not defined or name in called,
                    "IN-02: %s is defined and never reached" % name,
                )


class TestIn05ReadPageBytesNamesItsUnit(TempRepoTestCase):
    """Phase-16 IN-05 — the `unit=""` default silently misattributed a refusal.

    `read_page_bytes` raises through `contained_page`, and a refusal that names
    `""` as its unit is a refusal a skill cannot route on. The default made
    forgetting the argument a silent mistake instead of a loud one.
    """

    def test_in05_read_page_bytes_requires_its_unit(self):
        with self.assertRaises(TypeError):
            dogen.read_page_bytes(self.repo, "ok.rst")

    def test_in05_the_signature_carries_no_unit_default(self):
        self.assertNotIn(
            'def read_page_bytes(repo, path, unit="")',
            DOGEN_PATH.read_text(encoding="utf-8"),
        )

    def test_in05_it_still_answers_with_the_unit_supplied(self):
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "ok.rst").write_text("page\n", encoding="utf-8")
        self.assertEqual(dogen.read_page_bytes(self.repo, "ok.rst", "u1"), b"page\n")


class TestIn06ABooleanIsNeverASeq(unittest.TestCase):
    """Phase-16 IN-06 — `isinstance(True, int)` is true, and that is a spoof.

    `verify_chain` checks seq contiguity and prev digests and nothing beneath
    them, so a hand-repaired, forged or future-tool-written record spells
    `resolves` exactly as it likes. With `bool` admitted, `"resolves": [true]`
    compared equal to seq 1 and closed a steering request the reviewer never
    resolved (T-18-11).
    """

    def test_in06_a_boolean_resolves_entry_closes_no_request(self):
        events = [
            make_event(kind="steering", seq=1),
            make_event(kind="review", seq=2, verdict="accept", resolves=[True]),
        ]
        self.assertEqual(
            dogen.pending_requests(events, 0),
            [1],
            "IN-06: True stood in for seq 1 and closed a live request",
        )

    def test_in06_a_boolean_withdraw_seq_closes_no_request(self):
        events = [
            make_event(kind="steering", seq=1),
            make_event(
                kind="review", seq=2, verdict="accept",
                withdraws=[{"seq": True, "reason": "no"}],
            ),
        ]
        self.assertEqual(dogen.pending_requests(events, 0), [1])

    def test_in06_a_boolean_accept_seq_disposes_of_nothing(self):
        events = [
            make_event(kind="steering", seq=0),
            make_event(kind="review", seq=True, verdict="accept", resolves=[0]),
        ]
        self.assertEqual(dogen.pending_requests(events, -1), [0])

    def test_in06_an_integer_seq_is_still_a_seq(self):
        """Negative keystone: the exclusion must not refuse a real seq."""
        events = [
            make_event(kind="steering", seq=1),
            make_event(kind="review", seq=2, verdict="accept", resolves=[1]),
        ]
        self.assertEqual(dogen.pending_requests(events, 0), [])

    def test_in06_the_cli_still_refuses_a_boolean_spelled_as_text(self):
        for value in ("true", "True", "false"):
            with self.subTest(value=value):
                with self.assertRaises(dogen.Refusal) as caught:
                    dogen.parse_resolves([value], "u1")
                self.assertEqual(caught.exception.reason, "bad_resolution")
        with self.assertRaises(dogen.Refusal) as caught:
            dogen.parse_withdraws([("true", "because")], "u1")
        self.assertEqual(caught.exception.reason, "bad_resolution")


class TestPhase17In01HookReportNeedsItsRepo(unittest.TestCase):
    """Phase-17 IN-01 — `repo=None` is a trap that fires after the commit.

    `digest_file(os.path.join(os.fspath(repo), path))` runs whenever a path is
    in `existing_drift`, and `os.fspath(None)` raises `TypeError`. This code
    runs AFTER the transition has landed, so a future caller that passes drift
    without a repo crashes a completed transition. Ten of the eleven call sites
    passed neither argument, which is what kept the trap invisible.
    """

    def test_phase17_in01_the_repository_argument_is_required(self):
        with self.assertRaises(TypeError):
            dogen.report_hook_changes({"changed": [], "extra": []})

    def test_phase17_in01_no_repo_default_survives(self):
        self.assertEqual(
            DOGEN_PATH.read_text(encoding="utf-8").count("repo=None"),
            0,
            "phase-17 IN-01: a hook report with no repository has no vantage point",
        )


class TestPhase17In02EveryInstalledHookIsExecutable(unittest.TestCase):
    """Phase-17 IN-02 — a hook without its executable bit is not installed.

    A fixture that writes `.git/hooks/pre-commit` and never chmods it passes
    only while some EARLIER fixture happened to leave the file executable. When
    that stops being true the test silently stops exercising a hook and its
    `assert_not_contains` assertions pass vacuously — the same class of vacuous
    green the whole suite-hygiene pass exists against.
    """

    SUITES = (
        "tests/lib.sh",
        "tests/test_dogen_lifecycle.sh",
        "tests/test_dogen_acceptance.sh",
    )
    WRITE = re.compile(r">>?\s*['\"]?(\.git/hooks/[A-Za-z0-9_-]+)")

    def test_phase17_in02_every_hook_write_is_followed_by_a_chmod(self):
        for name in self.SUITES:
            lines = (ROOT / name).read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, 1):
                match = self.WRITE.search(line)
                if not match:
                    continue
                hook = match.group(1)
                window = "\n".join(lines[number - 1 : number + 30])
                with self.subTest(file=name, line=number, hook=hook):
                    self.assertIn(
                        "chmod +x %s" % hook,
                        window,
                        "phase-17 IN-02: %s:%d writes %s and never chmods it"
                        % (name, number, hook),
                    )

    def test_phase17_in02_the_scan_is_not_vacuous(self):
        """A regex that stopped matching would make the gate above silent."""
        found = 0
        for name in self.SUITES:
            for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
                if self.WRITE.search(line):
                    found += 1
        self.assertGreaterEqual(found, 5, "the hook-write scan matched nothing")


class TestPhase17In04TheDriftNoticeIsBatchScoped(unittest.TestCase):
    """Phase-17 IN-04 — the notice's condition and its wording, one statement.

    The condition moved to `state["page_drift"]` — ANY drifted basis path or
    signed target of the unit — while the sentence still says "completing THIS
    BATCH leaves %s drifted" and recommends `edits` at the adoption's own seq.
    A drifted path outside the batch would produce a notice naming a file the
    batch never touched. Latent rather than reproduced (a generation batch
    spans every signed target today), which is exactly why it needs a test.
    """

    def test_in04_a_drifted_path_outside_the_batch_raises_no_notice(self):
        rows = [{"path": "docs/reference/a.rst", "class": "done"}]
        state = {"page_drift": True, "drifted_paths": ["reference/b.rst"]}
        self.assertEqual(dogen.batch_drift(rows, state), [])

    def test_in04_a_drifted_path_inside_the_batch_does(self):
        """`rows` spells a page repo-relatively, the snapshot docs-relatively.

        Comparing the two spellings raw matched nothing, which suppresses the
        notice exactly as thoroughly as the wrong condition raised it — the
        same defect from the other side.
        """
        rows = [{"path": "docs/reference/a.rst", "class": "done"}]
        state = {"page_drift": True, "drifted_paths": ["reference/a.rst"]}
        self.assertEqual(dogen.batch_drift(rows, state), ["docs/reference/a.rst"])

    def test_in04_an_exactly_spelled_drifted_path_matches_too(self):
        rows = [{"path": "reference/a.rst", "class": "done"}]
        state = {"page_drift": True, "drifted_paths": ["reference/a.rst"]}
        self.assertEqual(dogen.batch_drift(rows, state), ["reference/a.rst"])

    def test_in04_an_underivable_state_raises_no_notice(self):
        self.assertEqual(dogen.batch_drift([{"path": "x"}], None), [])

    def test_in04_the_resume_notice_asks_the_batch_scoped_question(self):
        tree = ast.parse(DOGEN_PATH.read_text(encoding="utf-8"))
        node = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "resume_pass_two"
        )
        self.assertTrue(
            [
                call for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and getattr(call.func, "id", "") == "batch_drift"
            ],
            "IN-04: the notice still asks a unit-scoped question",
        )


class TestPhase17In05HashInequalityIsNotContainment(unittest.TestCase):
    """Phase-17 IN-05 — a digest comparison is an equality, not a containment.

    `assert_not_contains "..." "$before_sha" "$fresh_sha"` passes two
    equal-length hex digests as haystack and needle. It happens to be
    equivalent to inequality for same-length strings, and it reads as a
    containment claim that will mislead the next editor — the same "an
    assertion that says something other than what it checks" class as WR-18.
    """

    SUITES = ("tests/lib.sh", "tests/test_dogen_lifecycle.sh",
              "tests/test_dogen_acceptance.sh")
    DIGEST = r'"\$\{?[A-Za-z_]*(?:sha|digest|hash)[A-Za-z_]*\}?"'
    PAIR = re.compile(
        r'assert_(?:not_)?contains\s+"[^"]*"\s+' + DIGEST + r'\s+' + DIGEST
    )

    def test_in05_no_digest_pair_is_compared_by_containment(self):
        for name in self.SUITES:
            for number, line in enumerate(
                (ROOT / name).read_text(encoding="utf-8").splitlines(), 1
            ):
                with self.subTest(file=name, line=number):
                    self.assertIsNone(
                        self.PAIR.search(line),
                        "IN-05: %s:%d compares two digests by containment"
                        % (name, number),
                    )

    def test_in05_the_scan_catches_the_shape_it_is_about(self):
        """Non-vacuity: the regex must still match the original defect."""
        self.assertIsNotNone(
            self.PAIR.search(
                'assert_not_contains "$mode: the new bytes really differ" '
                '"$before_sha" "$fresh_sha"'
            )
        )

    def test_in05_the_suites_offer_an_inequality_assertion(self):
        self.assertIn(
            "assert_not_eq() {", (ROOT / "tests" / "lib.sh").read_text(encoding="utf-8")
        )


# --- the runner, and the guard that proves it loaded the whole module --------
#
# CR-06: this block used to sit at line 4567 of a 5378-line file, two thirds of
# the way up. ``unittest.main()`` calls ``sys.exit()``, so everything below it —
# the entire U-11 / V1–V19 block, this phase's headline feature — was never
# defined when the file was run as a script, and the short run printed ``OK``
# and exited 0. It was indistinguishable from the full run without counting:
#
#   python3 tests/test_dogen_unit.py             → Ran 325 tests … OK
#   python3 -m unittest tests.test_dogen_unit    → Ran 404 tests … OK
#
# Position alone would fix today's truncation and not tomorrow's, so the count
# is asserted too — the same vacuous-pass discipline as ``run_test``'s "recorded
# no assertions", ``check_traces``'s exit 2 and ``EXPECTED_REFERENCE_COUNT``.

#: Raise this deliberately when tests are added; a DROP means the module stopped
#: being fully defined (an early ``sys.exit``, a syntax error swallowed by a
#: conditional import, a truncated file), not that tests were removed — removing
#: tests is an edit to this constant in the same commit.
EXPECTED_MIN_TESTS = 490



if __name__ == "__main__":
    _loaded = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    if _loaded.countTestCases() < EXPECTED_MIN_TESTS:
        raise SystemExit(
            "test_dogen_unit: loaded %d test(s), expected at least %d — the "
            "module is not fully defined, so an `OK` here would be vacuous"
            % (_loaded.countTestCases(), EXPECTED_MIN_TESTS)
        )
    unittest.main()
