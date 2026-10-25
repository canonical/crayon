"""Structural text contracts for the crayon skill family (S-01, S-02, S-03).

Runner (D-12): ``python3 -m unittest tests/test_skill_text.py`` — never
``discover`` (the repo has no ``tests/__init__.py``, RESEARCH P-11) and never
pytest. The suite reads skill *text* only: it must NOT import ``crayon``, because
nothing here is a claim about the tool's behaviour.

These are TEXT contracts, not LLM evaluations (D-11). Every assertion is a
structural fact about bytes on disk — a frontmatter key, a table row, a file
comparison — so the suite is deterministic, offline, and as fast as a grep. What
the prose *means* is a human's judgment and is deliberately out of scope.

The frontmatter parser is not re-implemented here. ``scripts/skill_lint.py`` is
loaded by path through a ``SourceFileLoader`` shim and its ``split_front_matter``
is reused verbatim, so the lint and this suite can never disagree about what a
skill declares.

Organising principle: a positive
gate (the committed skills satisfy every declared contract), a negative keystone
(a drifted copy MUST be detected, never silently accepted) and a vacuous-pass
guard (an empty or mis-rooted scan cannot masquerade as valid).

Coverage:
  S-01  frontmatter — name, both compatibility numbers, a non-empty tool list;
        ``min_tool`` is ``crayon.py``'s ``__version__``, read as text through the
        lint, and every prose copy of it (each body's stop rule and its "older"
        example, the README's table row and prose, every
        ``metadata.crayon_min_tool: "…"`` under ``skills/`` and in contract
        5.10) names that version (D-07)
  S-02  single writer — only ``crayon-write`` holds a write-capable tool
  S-03  routing-copy equality (D-13) — the three mirrors equal the README block,
        and every reason and every ``next`` token has a row
  S-04  the common opening — ``crayon version --json`` then ``crayon show <id>
        --json`` as the first verb pair of every body, the routing sentence, the
        never-hand-edit sentence, and no ``--force`` anywhere
  S-05  ``crayon-plan`` through verbs — ``unit new --body-file -``, ``unit edit
        --re-sign``, ``unit retire``, no flag the tool does not expose ON THAT
        VERB (WR-06: the flat union let `crayon show <id> --re-sign` through),
        and the Socratic intake and triage fork carried over verbatim
  S-06  the D-15 evidence recipe — ``crayon step`` with ``--steps-seq``,
        ``--evidence-file`` and ``--output-file``, ``crayon plan-steps
        --steps-file``, and the question asked before ``--keep-evidence``
  S-07  the honesty guards — no shell digest utility, no pipeline exit-status
        array, no evidence key outside contract 5.6's set, and no claim that the
        committed excerpt is redacted, sanitised or free of secrets
  S-08  recovery presentation — the dry run before the real ``crayon resume``,
        exactly contract 5.8's two choices on ``resume_ambiguous``, the printed
        findings shown verbatim on ``recovery_unsupported``, no restore recipe
        of the skill's own, and dispositions on accept; and D-14's pre-pass and
        six-dimension findings list carried byte for byte (``SIX_DIMENSIONS``,
        with ``focus`` as item 4 since D-20)
  S-09  T34a/T34b, ``target_missing`` — the restore-or-amend question, the
        never-a-second-accept statement, an explicit restore instruction
        recorded through ``crayon steer`` without reconfirming, and no invented
        steering note
  S-10  the ``references/`` tree — no v1 artefact name, no ``--force``, and
        every flag a reference puts on a ``crayon`` verb is one the tool
        registers. Every other assertion here reads ``SKILL.md`` only, and the
        lint reads only its frontmatter, so the files the skills load at
        RUNTIME had no gate at all (CR-02)
        — and every field a reference attributes to `crayon summary --json` or
        `crayon show --json` is a key that payload actually carries (CR-04), and
        every backticked name written as a field of the unit is one of contract
        5.6's six frontmatter keys (WR-14)
  S-11  routed descriptions are grounded — for a pinned set of reasons, the
        words the tool's own ``Refusal`` puts in front of the operator appear
        both in that raiser and in the reason's routing row. S-10 sees a wrong
        token; S-11 sees a row that describes something else entirely, which is
        how ``evidence_mismatch`` shipped a remedy that could never clear it
  S-12  the step gate's two enumerations — ``walk-protocol.md``'s branch table
        and ``crayon-write``'s "Refusals to expect" both present themselves as
        complete, so both must name every reason a walk can meet (WR-07); and
        prose never outruns the command it sits beside — an origin attributed
        to a bare ``crayon steer`` that only ``--origin plan`` produces (WR-08)
  S-13  every routed escape terminates — an AST walk over ``crayon`` enumerates
        every refusal-constructing call, and no hint may route the operator to
        a command its own refusal has ruled out: ``--adopt`` is never named
        without its precondition, and no raise site of ``adopt_unsupported``,
        ``resume_ambiguous`` or ``recovery_unsupported`` names a resume command
        without either the shared ``escape_hint`` branch or the escape that
        always works. The same two properties over the routing rows. CR-01
        survived three fixes because each of its gates was pinned to the
        transcript that review had reproduced; this one is pinned to the walk
  S-15  the author-rules block (D-14) — the three rules authored once in
        ``skills/README.md`` (verbatim notes, no marked option on a judgment
        question, an explicit go) are carried byte for byte in the plan, write
        and review bodies, name no harness and no tool, and appear in no context
        skill
  S-16  the verdict is the author's (D-09) — the review skill shows the accept as
        the bare command line, says a bare accept records no note, and no longer
        carries an accept whose note the skill would have to supply; the routing
        rows that call an accept show its note as optional; the verdict is asked
        as one open question, the note is the author's words (a bare fix is
        asked what the next draft should change), and an answer that names no
        verdict or an accept with a condition is asked again (D-06, D-15); the
        lean is held until the author answers and a departing verdict gets one
        ``Keep <verdict>?``, and the rubric's layout ends on the verdict question
        with no recommended verdict and no publishing line (D-10, D-11); finding
        numbers cited in a note are restated with the author, the hook-adoption
        note is the author's words, and the skill's lists name these rules (D-07)
  S-17  the closure (CLOSE-01) — after an accept the author is asked, never
        offered a next step: the ``publish`` row names no publish, pull request
        or build; step 6 closes an accept on at most three questions drawn from
        the record (``handover.steps``, ``handover.judged``, this conversation's
        unanswered findings, where a reader arrives from), one per source first
        in a fixed order, none when nothing is open, the overflow on one plain
        line, a change request steered in the author's words, and never a
        publishing step (D-01 to D-04); and onboarding ends on one question
        about the author's priorities, records nothing from the answer, and
        routes to ``/crayon-plan`` with the author's first pick in their own
        words, or with none, never one of its own (CLOSE-02, D-05)
  S-18  the intake is the author's (JUDG-04, D-08, D-12, D-16) — every intake asks
        at least two open questions, the leave-out question always among them:
        one of two fixed questions (where the reader arrives from, what they do
        next) even when the brief fills every field, and the jump-ahead scripts
        keep one of them always open; a view on the
        audience or the direction is given only when the TA asks for it, as
        evidence, never as a marked option, and a vague answer gets a narrower
        probe; ``--notes`` carries only the TA's own words given in answer to an
        open question, no reference describes a synthesized note, and "looks
        good" or "yes, but" is not a go
  S-19  the writer's notes and step choices are the author's (D-06, D-13) — the
        ``--keep-evidence`` note is the author's answer, verbatim, with no
        placeholder inviting a composed reason, in the skill, its lists and the
        walk protocol; the permission gate, the ``--keep-evidence`` ask and a
        failed step or genuine fork are step choices put with no option marked,
        and resuming at the first unresolved step is a mechanical default
  S-20  what the author reads is in plain words (VOICE-03, D-01 to D-04, D-07) —
        a pending request is put to the reviewer one at a time as "request <n>",
        never by the record's own name for its number; the plain-words block,
        authored once in ``skills/README.md``, is carried byte for byte in all
        five bodies, names no tool and no verb, and sits where it binds: after
        the author-rules block in plan, write and review, after ``</opening>``
        in onboard and fetch; the routing rows name a pending request as
        "request <n>", name no other record number (a no-op gives the commit
        from its payload), and put output shown verbatim in a code block; the
        body and reference sites read the plan-stale qualifier plainly, give
        the commit for a no-op, put verbatim output in a code block, and the
        provenance reference presents the human lines, never the ``--json``
        counts and seqs; no routing row's what-to-do cell carries a record word
        the grader reads, outside code (22-14: WR-03); a commit is named by its
        id, never as a hash, and the relayed references say chained and Git
        commit id (22-14: WR-03), and ``page: current`` compares the bytes crayon
        recorded, never a recorded digest (24 D-13); the block quotes the tallies
        and names every form the check reads, and write step 5 echoes the
        response line the tool prints after its ``git: committed`` line (22-09)
  S-21  uncertainty is said in the first person, only where the record grounds it
        (VOICE-01, D-10) — write step 6 states each entry of the staged
        ``report.json``'s ``gaps`` as one first-person line, reads them from
        ``report.json`` and not from ``crayon summary``, and adds nothing when
        ``gaps`` is empty; review step 5 and the rubric's verification discipline
        put what a finding could not verify inside the finding, in the first
        person, and a verified finding carries no hedge; the rubric no longer
        admits only verified findings and still calls hedged prose in the page a
        violation; and no skill text asks for a section of doubts or a general
        caveat
  S-22  the reviewer says when it reviews its own draft, and only then (VOICE-02,
        D-08, D-09) — review step 5 names the two grounds, this conversation ran
        ``crayon draft`` or the ``model`` line of ``crayon summary`` names the
        reviewer's own model, established and never guessed; with neither there
        are no grounds and nothing is said; with grounds one first-person line
        sits directly before the findings, record mode has none, and it is never
        repeated at the verdict; the pinned pre-pass and dimension blocks are
        intact around it, and ``<must>``, ``<must_not>`` and
        ``<success_criteria>`` name the rule
  S-23  deviated and skipped steps reach the author during review (CLOSE-03,
        D-12 to D-14) — the review skill's ``<step_3a>`` sits between steps 3 and
        4, and in both modes, after the provenance summary and before any
        findings or the verdict, reads ``handover.steps`` from ``crayon show
        --json`` and puts every entry to the author as a question about the page,
        in one numbered list, in the order the tool lists them, with no cap;
        nothing is recorded from an answer, no steer and no note, and an answer
        that asks for a page change is told in one line that it is not recorded
        until the verdict, and that a fix or redraft verdict with those words
        records it (CR-01); when the reviewer already authorised the accept,
        step 3a is skipped and the closure asks the steps instead (WR-05, D-12
        amended); quick-start item 4, ``<must>``, ``<must_not>`` and
        ``<success_criteria>`` name it, quick-start item 4 puts the step
        questions before any finding and before the verdict question and moves
        them to the closure when the reviewer already authorised the accept
        (22-15: G-22-2, IN-03), and quick-start item 6 still closes on at
        most three questions; and the closure after an accept (D-15, amended for
        CR-01) counts no step this conversation already put to the author in
        step 3a unless its answer asked for a page change, and a step left
        unanswered is not asked again (22-15: WR-04), a step whose answer asked
        for one is open again and its question names the change in the author's
        words, and a later session counts every step again, with the source
        order and the cap unchanged
  S-24  scope is the author's (JUDG-05, D-16, D-17) — step 2 of ``crayon-plan``
        asks ``What can this page leave out?`` after the arrival-or-next
        question in every intake, even when the brief fills every field, and the
        jump-ahead entries keep it always open; step 6 records the answer in the
        TA's words, and a "nothing" answer records nothing; ``crayon-write`` step 2
        reads the intake notes (``crayon summary`` author decisions) and keeps
        what the author said to leave out off the page, as scope, and step 3's
        coverage check does not count it as missing; review's sixth dimension,
        ``focus``, sits between ``completeness`` and ``structure-fit`` in the
        rubric and its findings layout, mirrors completeness (what is present that
        the reader does not need), and makes material the author said to leave
        out a ``[must-fix]`` in the dimension and the priority table (D-18, D-19);
        no five-dimension wording remains in the review skill or the README, and
        the rubric counts five generalized dimensions (D-20); the leave-out notes
        narrow the plan's inventory and a later recorded request outranks them,
        stated once in write step 2 and once in the rubric, and plan's quick start
        and read-back name the leave-out answer (22-09: WR-02, IN-06); write's
        ``<must>`` and ``<success_criteria>`` owe every promised inventory less
        what the author's leave-out notes exclude, unless a later recorded
        request asks for it (22-15: IN-03)
  S-26  no skill names an eval fixture (D-18, D-19) — the token set is read from
        the fixture definitions (the tracked toyq tree and its config module's
        ``DEFAULTS`` and ``ENV_OVERRIDES``, ``states.sh``'s unit ids, targets,
        step ids and models, the recorded models in ``states.json``), never
        listed here; an ordinary word that is also a fixture id (``install``,
        ``init``, ``config``) counts only in a fixture shape, every other token
        as a whole token; and a planted token is caught
"""

from __future__ import annotations

import ast
import importlib.machinery
import importlib.util
import itertools
import json
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
README = SKILLS_ROOT / "README.md"
CONTRACT = ROOT / "docs" / "contract.md"
SKILL_LINT_PATH = ROOT / "scripts" / "skill_lint.py"
#: D-07: the compatibility row shape and contract 5.10's heading are read from
#: the docs checker, their one definition site.
CHECK_DOCS_PATH = ROOT / "tests" / "check_docs.py"
#: WR-03 (22-14): the grader whose record-word regex the S-20 row scan reuses.
EVALS_ROOT = ROOT / "validation" / "evals"
GRADE_PATH = EVALS_ROOT / "grade.py"

#: The five skills the family ships. Hardcoded on purpose: it is the quantity
#: the vacuous-pass guard below compares the discovered set against, so a
#: mis-rooted scan cannot make S-01 and S-02 pass over an empty set.
EXPECTED_SKILLS = (
    "crayon-fetch",
    "crayon-onboard",
    "crayon-plan",
    "crayon-review",
    "crayon-write",
)

#: The skills that act on the repository's context rather than on a unit. They
#: open on `crayon context show` where the unit skills open on `crayon show`, and
#: they hand every artefact to `crayon context stage` — none of them writes.
CONTEXT_SKILLS = ("crayon-fetch", "crayon-onboard")

#: The stance references are authored ONCE, in `crayon-onboard`, and mirrored
#: byte-identically into `crayon-fetch` — the routing table's own rule, applied
#: to the three files both skills load before authoring an artefact.
STANCE_REFERENCES = ("glossary-stance.md", "structure-stance.md", "style-stance.md")

#: contract.md 5.5's ordered routing table, rows 1-10 including 8b, then the
#: context routing rows C1-C3 in their own order.
NEXT_TOKENS = (
    "resume",
    "retired",
    "sign_off",
    "re_sign",
    "record_edits",
    "walk",
    "draft",
    "publish",
    "steer",
    "review",
    "record",
    "onboard",
    "plan",
)

#: contract.md 5.7's reason table has 48 rows (47 before D-14 added
#: ``internal_error``). The exact list is parsed from the contract below; this is
#: the floor the parse is checked against so a broken regex reports a vacuous
#: pass instead of a green one. Raise it with the table, never below it.
MIN_REASONS = 48

_SENTINEL_BEGIN = b"routing-table:begin"
_SENTINEL_END = b"routing-table:end"

#: D-14: the author-rules block's sentinels. Unlike the routing table, which is
#: mirrored into whole files, the block sits inside larger SKILL.md bodies, so
#: the sentinel lines travel with it and the copy is asserted as a substring.
_RULES_BEGIN = b"author-rules:begin"
_RULES_END = b"author-rules:end"

#: The skills that put judgment questions to the author and record the
#: author's notes, so the three rules must be in context at every question.
#: The context skills are out: their `context record --note` is the agent's
#: own summary of the scope it walked.
RULE_SKILLS = ("crayon-plan", "crayon-review", "crayon-write")

#: D-01: the plain-words block's sentinels. Like the author rules, the block
#: sits inside larger SKILL.md bodies, so the copy is asserted as a substring.
_PLAIN_BEGIN = b"plain-words:begin"
_PLAIN_END = b"plain-words:end"

#: D-01: unlike the author rules, the plain-words block binds all five skills,
#: because every one of them says something to the author.
PLAIN_SKILLS = tuple(sorted(CONTEXT_SKILLS + RULE_SKILLS))
_REASON_ROW_RE = re.compile(r"^\| `([a-z_]+)` \| [0-9] \|$")


def _load_skill_lint():
    """Import ``scripts/skill_lint.py`` by path (the plan 16-02 shim shape).

    Reusing its ``split_front_matter`` is the point: one parser means the lint
    and this suite cannot disagree about what a skill declares.
    """
    loader = importlib.machinery.SourceFileLoader(
        "skill_lint", str(SKILL_LINT_PATH)
    )
    spec = importlib.util.spec_from_loader("skill_lint", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


skill_lint = _load_skill_lint()


def _load_check_docs():
    """Import ``tests/check_docs.py`` by path, for its compatibility row shape.

    D-07: ``COMPAT_ROW_RE``, ``COMPAT_HEADING`` and ``heading_section`` are the
    docs checker's, so the README row and contract 5.10's section are found the
    way ``check_compat`` finds them. Loading the module runs no check and reads
    no tool: ``check_docs`` touches ``crayon.py`` only inside ``main``.
    """
    loader = importlib.machinery.SourceFileLoader(
        "check_docs_for_skill_text", str(CHECK_DOCS_PATH)
    )
    spec = importlib.util.spec_from_loader("check_docs_for_skill_text", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


check_docs = _load_check_docs()

#: D-07: the prose copies of ``min_tool``. Each SKILL.md body's stop rule names
#: it, and its example names a version older than it; the README's prose does
#: the same in its own shape; and a ``metadata.crayon_min_tool: "…"`` mention may
#: wrap after its colon, as contract 5.10's does.
_STOP_RULE_RE = re.compile(r"older than `min_tool` `([^`]+)`")
_OLDER_EXAMPLE_RE = re.compile(r"`([^`]+)` is older than `([^`]+)`")
_README_STOP_RE = re.compile(r"older than `min_tool ([^`]+)` \(`([^`]+)` is older\)")
_MIN_TOOL_MENTION_RE = re.compile(r'metadata\.crayon_min_tool:\s+"([^"]+)"')


def _load_grade():
    """Import ``validation/evals/grade.py`` by path, for its record-word regex.

    WR-03 (22-14): the S-20 row scan reads a row through the same
    ``LEDGER_WORDS_RE`` and ``_CODE_RE`` the always-on ``plain_words`` check
    runs, so the words have one definition site and no copy here can drift.
    ``grade`` imports its siblings ``agent`` and ``openrouter`` (stdlib only, no
    ``crayon``), so their directory goes on ``sys.path``. A ``grade`` another
    suite in the same process already imported is reused, never replaced, so a
    patch that suite applies by module name still reaches its own object.
    """
    if str(EVALS_ROOT) not in sys.path:
        sys.path.insert(0, str(EVALS_ROOT))
    loaded = sys.modules.get("grade")
    if loaded is not None and pathlib.Path(getattr(loaded, "__file__", "")).resolve() == GRADE_PATH:
        return loaded
    loader = importlib.machinery.SourceFileLoader("grade", str(GRADE_PATH))
    spec = importlib.util.spec_from_loader("grade", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["grade"] = module
    loader.exec_module(module)
    return module


grade = _load_grade()


def skill_dirs():
    """Every skill directory under ``skills/``, sorted by name."""
    return sorted(p.parent for p in SKILLS_ROOT.glob("*/SKILL.md"))


def frontmatter_of(skill_dir):
    """The frontmatter dict for one skill, through the lint's own parser."""
    text = skill_dir.joinpath("SKILL.md").read_text(encoding="utf-8")
    return skill_lint.split_front_matter(text)[0]


def tool_list(frontmatter):
    """``allowed-tools`` as a list of non-empty, stripped tool names."""
    raw = str(frontmatter.get("allowed-tools") or "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def routing_block_bytes():
    """The bytes between the two sentinels in ``skills/README.md``, exclusive.

    Returned as bytes, with the trailing newline of the final row, so it can be
    compared to a mirror file byte for byte rather than line by line.
    """
    lines = README.read_bytes().split(b"\n")
    begins = [i for i, line in enumerate(lines) if _SENTINEL_BEGIN in line]
    ends = [i for i, line in enumerate(lines) if _SENTINEL_END in line]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise AssertionError(
            "skills/README.md must carry exactly one %r line followed by exactly "
            "one %r line; found %d and %d"
            % (
                _SENTINEL_BEGIN.decode(),
                _SENTINEL_END.decode(),
                len(begins),
                len(ends),
            )
        )
    return b"\n".join(lines[begins[0] + 1 : ends[0]]) + b"\n"


def routing_signals():
    """The routing table's signals, split into (reason block, token block).

    The table is two blocks in one fixed order (Task 1): one row per reason in
    contract 5.7's order, then one row per ``next`` token in 5.5's order. The
    split is positional — the reason block is as long as the contract's reason
    table — so a row that drifted out of its block shows up as an order failure
    rather than being silently counted in the other block.
    """
    block = routing_block_bytes().decode("utf-8")
    rows = [ln for ln in block.splitlines() if ln.startswith("| `")]
    signals = [ln.split("`")[1] for ln in rows]
    cut = len(contract_reasons())
    return signals[:cut], signals[cut:]


def routing_row(signal, block="reasons"):
    """One routing row's full text, looked up inside its own block.

    Scoped to a block for the same reason ``routing_signals`` splits them:
    ``retired`` and ``resume`` name a reason AND a ``next`` token, and the two
    rows say different things.
    """
    text = routing_block_bytes().decode("utf-8")
    rows = [ln for ln in text.splitlines() if ln.startswith("| `")]
    cut = len(contract_reasons())
    chosen = rows[:cut] if block == "reasons" else rows[cut:]
    for row in chosen:
        if row.split("`")[1] == signal:
            return row
    raise AssertionError("no %s row for %r in the routing block" % (block, signal))


def sentinel_block_bytes(begin, end):
    """A README block from its ``begin`` line through its ``end`` line, as bytes.

    Sentinel lines included, and no trailing newline: the block is compared as
    a substring of a SKILL.md body, where the line after the end sentinel is
    the body's own.
    """
    lines = README.read_bytes().split(b"\n")
    begins = [i for i, line in enumerate(lines) if begin in line]
    ends = [i for i, line in enumerate(lines) if end in line]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise AssertionError(
            "skills/README.md must carry exactly one %r line followed by exactly "
            "one %r line; found %d and %d"
            % (begin.decode(), end.decode(), len(begins), len(ends))
        )
    return b"\n".join(lines[begins[0] : ends[0] + 1])


def author_rules_bytes():
    """The README's author-rules block, sentinel lines included, as bytes."""
    return sentinel_block_bytes(_RULES_BEGIN, _RULES_END)


def plain_words_bytes():
    """The README's plain-words block, sentinel lines included, as bytes."""
    return sentinel_block_bytes(_PLAIN_BEGIN, _PLAIN_END)


def row_cells(row):
    """A routing row's cells, split on the unescaped pipes, each stripped."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row)[1:-1]]


def record_word_outside_code(cell):
    """The first record word the grader reads in ``cell``, outside code, or None.

    Code spans and fenced blocks are removed first, through the grader's own
    ``_CODE_RE``: a command line quoted in code keeps its real flags (WR-03).
    """
    return grade.LEDGER_WORDS_RE.search(grade._CODE_RE.sub("", cell))


def carries_block_once(text, block):
    """``block`` occurs in ``text`` exactly once, as bytes."""
    return text.count(block) == 1


def contract_reasons():
    """Every reason in contract 5.7's reason table, in the table's own order."""
    reasons = []
    for line in CONTRACT.read_text(encoding="utf-8").splitlines():
        match = _REASON_ROW_RE.match(line)
        if match:
            reasons.append(match.group(1))
    return reasons


class TestSuiteIsNotVacuous(unittest.TestCase):
    """Vacuous-pass guard — an empty or mis-rooted scan must fail loudly."""

    def test_exactly_the_five_skill_directories_are_found(self):
        found = tuple(d.name for d in skill_dirs())
        self.assertEqual(
            len(found),
            len(EXPECTED_SKILLS),
            "expected %d skill directories under %s, found %d (%s) — a mis-rooted "
            "path would let S-01 and S-02 pass over an empty set"
            % (len(EXPECTED_SKILLS), SKILLS_ROOT, len(found), ", ".join(found)),
        )
        self.assertEqual(found, EXPECTED_SKILLS)

    def test_the_contract_reason_table_parses(self):
        reasons = contract_reasons()
        self.assertGreaterEqual(
            len(reasons),
            MIN_REASONS,
            "parsed only %d reasons from %s; S-03's per-reason row check would be "
            "vacuously satisfied" % (len(reasons), CONTRACT),
        )
        self.assertEqual(len(set(reasons)), len(reasons), "duplicate reason rows")


class TestS01Frontmatter(unittest.TestCase):
    """S-01 — every skill declares its name, both compatibility numbers and a tool list."""

    def test_s01_name_equals_the_directory_name(self):
        for skill_dir in skill_dirs():
            with self.subTest(skill=skill_dir.name):
                self.assertEqual(
                    frontmatter_of(skill_dir).get("name"), skill_dir.name
                )

    def test_s01_both_compatibility_numbers_are_the_literal_strings(self):
        # contract 5.10: compared as literal strings, never parsed as versions.
        # D-07: the expected min_tool is the lint's, and the lint's is the
        # tool's own __version__, so no version is typed here.
        expected = skill_lint._EXPECTED_METADATA["metadata.crayon_min_tool"]
        self.assertEqual(expected, skill_lint.tool_version(ROOT))
        for skill_dir in skill_dirs():
            with self.subTest(skill=skill_dir.name):
                frontmatter = frontmatter_of(skill_dir)
                self.assertEqual(frontmatter.get("metadata.crayon_contract"), "1")
                self.assertEqual(
                    frontmatter.get("metadata.crayon_min_tool"),
                    expected,
                    "%s/SKILL.md: metadata.crayon_min_tool is not crayon.py's "
                    "__version__ %r" % (skill_dir.name, expected),
                )

    def test_s01_every_version_site_names_the_tools_version(self):
        """D-07: every prose copy of ``min_tool`` names ``crayon.py``'s ``__version__``.

        ``check_compat`` reads only the COMPAT region and contract 5.10's table,
        and the lint only the frontmatter, so the copies a model actually reads
        had no check: each body's stop rule and its "older" example, the
        README's table row and prose, and every ``metadata.crayon_min_tool: "…"``
        mention. The example is the one other version literal allowed, and it
        must differ from the tool's. Compared as literal strings, never parsed.
        """
        version = skill_lint.tool_version(ROOT)
        stop_rules = 0
        for skill_dir in skill_dirs():
            where = "%s/SKILL.md" % skill_dir.name
            text = folded(body_of(skill_dir))
            named = _STOP_RULE_RE.findall(text)
            examples = _OLDER_EXAMPLE_RE.findall(text)
            with self.subTest(site=where + " stop rule"):
                self.assertTrue(named, "%s: no `older than `min_tool` `…`` stop rule" % where)
                for value in named:
                    self.assertEqual(
                        value, version,
                        "%s: the stop rule says older than `min_tool` `%s`, but "
                        "crayon.py's __version__ is %r" % (where, value, version),
                    )
            with self.subTest(site=where + " older example"):
                self.assertTrue(examples, "%s: no `X` is older than `Y` example" % where)
                for older, newer in examples:
                    self.assertEqual(
                        newer, version,
                        "%s: the example says `%s` is older than `%s`, but "
                        "crayon.py's __version__ is %r" % (where, older, newer, version),
                    )
                    self.assertNotEqual(
                        older, version,
                        "%s: the example's older version is the tool's own %r"
                        % (where, version),
                    )
            if named:
                stop_rules += 1

        readme = README.read_text(encoding="utf-8")
        rows = [
            match.group(2)
            for match in map(check_docs.COMPAT_ROW_RE.match, readme.splitlines())
            if match and match.group(1) == "min_tool"
        ]
        with self.subTest(site="skills/README.md compatibility row"):
            self.assertEqual(
                rows, [version],
                "skills/README.md: expected exactly one `min_tool` row reading "
                "%r, found %r" % (version, rows),
            )
        with self.subTest(site="skills/README.md stop prose"):
            prose = _README_STOP_RE.findall(folded(readme))
            self.assertTrue(prose, "skills/README.md: no `min_tool V` (`X` is older) prose")
            for value, older in prose:
                self.assertEqual(
                    value, version,
                    "skills/README.md: the prose says older than `min_tool %s`, "
                    "but crayon.py's __version__ is %r" % (value, version),
                )
                self.assertNotEqual(
                    older, version,
                    "skills/README.md: the example's older version is the tool's "
                    "own %r" % version,
                )

        sites = [
            (str(path.relative_to(ROOT)), path.read_text(encoding="utf-8"))
            for path in sorted(SKILLS_ROOT.rglob("*.md"))
        ]
        section = check_docs.heading_section(
            CONTRACT.read_text(encoding="utf-8"), check_docs.COMPAT_HEADING
        )
        self.assertIsNotNone(section, "docs/contract.md has no %r section"
                             % check_docs.COMPAT_HEADING)
        sites.append(("docs/contract.md 5.10", section))
        contract_mentions = 0
        for where, text in sites:
            for value in _MIN_TOOL_MENTION_RE.findall(text):
                if where.startswith("docs/contract.md"):
                    contract_mentions += 1
                with self.subTest(site=where + " metadata.crayon_min_tool mention"):
                    self.assertEqual(
                        value, version,
                        '%s: says metadata.crayon_min_tool: "%s", but crayon.py\'s '
                        "__version__ is %r" % (where, value, version),
                    )

        # Vacuous-pass guard: a drifted regex must not pass over nothing.
        self.assertGreaterEqual(
            stop_rules, len(EXPECTED_SKILLS),
            "found the stop rule in only %d SKILL.md bodies" % stop_rules,
        )
        self.assertEqual(len(rows), 1, "skills/README.md min_tool rows: %r" % rows)
        self.assertGreaterEqual(
            contract_mentions, 1,
            "no metadata.crayon_min_tool mention found in contract 5.10",
        )

    def test_s01_allowed_tools_parses_to_a_non_empty_list(self):
        for skill_dir in skill_dirs():
            with self.subTest(skill=skill_dir.name):
                self.assertTrue(tool_list(frontmatter_of(skill_dir)))


class TestS02SingleWriter(unittest.TestCase):
    """S-02 — exactly one skill may write files, and it is ``crayon-write``."""

    def _writers(self):
        writers = set()
        for skill_dir in skill_dirs():
            tools = tool_list(frontmatter_of(skill_dir))
            if any(t.lower() in skill_lint._WRITE_TOOLS for t in tools):
                writers.add(skill_dir.name)
        return writers

    def test_s02_crayon_write_is_the_only_skill_holding_a_write_capable_tool(self):
        self.assertEqual(self._writers(), {"crayon-write"})

    def test_s02_the_observed_writers_match_the_lint_allow_list(self):
        # The lint enforces the rule; this pins the lint's allow-list to the
        # fact on disk, so neither can drift without the other going red.
        self.assertEqual(self._writers(), set(skill_lint.WRITERS))


class TestProjectReadmeInstallCommands(unittest.TestCase):
    """WR-08 — the certified install block installs.

    The phase-17 tombstone reads "The skills install exactly as described
    below; only the scripts half is wrong", and the block it certifies created
    a GLOBAL directory and then copied into a PROJECT one that may not exist:
    `mkdir -p ~/.agents/skills && cp -r … .agents/skills/`. In a fresh docs
    repo — the state the heading "Project-scoped (recommended)" describes — the
    copy fails. Checked as a relation between the two halves of each line,
    because the defect was that they named different paths.

    Both manual install blocks are checked: the guide's, which carries the
    project and the global form, and the root README's, which carries the
    project form a stranger meets first.
    """

    #: Each document with its vacuous-pass floor: the guide carries one line
    #: per scope, the README the project line only.
    INSTALL_DOCS = ((ROOT / "docs" / "install.md", 2), (ROOT / "README.md", 1))

    def install_lines(self, path):
        """Every `mkdir … && cp -r …` line in one document's manual install."""
        text = path.read_text(encoding="utf-8")
        return [
            line.strip()
            for line in text.splitlines()
            if line.lstrip().startswith("mkdir -p ") and " && cp -r " in line
        ]

    def test_every_certified_install_line_creates_what_it_copies_into(self):
        for path, floor in self.INSTALL_DOCS:
            lines = self.install_lines(path)
            self.assertGreaterEqual(
                len(lines),
                floor,
                "found %d install lines in %s; the scan has stopped matching and "
                "every assertion below would be vacuous" % (len(lines), path),
            )
            for line in lines:
                with self.subTest(document=path.name, line=line):
                    made = line.split("mkdir -p ", 1)[1].split(" &&", 1)[0].strip()
                    into = line.rsplit(" ", 1)[1].rstrip("/")
                    self.assertEqual(
                        made.rstrip("/"),
                        into,
                        "the line creates %r and copies into %r; in a fresh repo "
                        "the copy fails" % (made, into),
                    )


class TestS03RoutingCopies(unittest.TestCase):
    """S-03 — D-13's mirrors are byte-identical and cover every signal."""

    def test_s03_each_mirror_is_byte_identical_to_the_readme_block(self):
        block = routing_block_bytes()
        for skill_dir in skill_dirs():
            mirror = skill_dir / "references" / "routing.md"
            with self.subTest(skill=skill_dir.name):
                self.assertTrue(
                    mirror.exists(),
                    "%s is missing; the portable install ships the table inside "
                    "each skill directory (D-13)" % mirror,
                )
                self.assertEqual(
                    mirror.read_bytes(),
                    block,
                    "%s has drifted from the routing block in %s; re-copy the "
                    "bytes between the sentinels rather than hand-editing the "
                    "mirror" % (mirror, README),
                )

    def test_s03_every_reason_and_every_next_token_has_a_row(self):
        reason_rows, token_rows = routing_signals()
        reasons = contract_reasons()
        # `retired` is both a reason and a `next` token, so it legitimately owns
        # one row in each block. The counts are therefore per block: within the
        # reason block no reason may appear twice, and within the token block no
        # token may appear twice.
        for reason in reasons:
            with self.subTest(signal=reason, block="reasons"):
                self.assertEqual(
                    reason_rows.count(reason),
                    1,
                    "reason %r must have exactly one routing row" % reason,
                )
        for token in NEXT_TOKENS:
            with self.subTest(signal=token, block="tokens"):
                self.assertEqual(
                    token_rows.count(token),
                    1,
                    "next token %r must have exactly one routing row" % token,
                )
        self.assertEqual(len(reason_rows), len(reasons))
        self.assertEqual(len(token_rows), len(NEXT_TOKENS))

    def test_s03_the_row_order_is_the_contract_order(self):
        reason_rows, token_rows = routing_signals()
        self.assertEqual(reason_rows, contract_reasons())
        self.assertEqual(token_rows, list(NEXT_TOKENS))

    def test_s03_commit_rejected_is_split_out_of_the_recovery_unsupported_row(self):
        """CR-01 — the write path's own ``recovery_unsupported`` DID write.

        ``commit_rejected`` is raised after step 2 appended the batch and step 3
        placed every file; only step 4 was refused. A row that says "nothing was
        written" across every detail sends the operator away from work that is on
        disk, and a row with no verb leaves the tool's own ``--adopt`` hint
        unrouted.
        """
        row = routing_row("recovery_unsupported")
        self.assertIn("commit_rejected", row)
        self.assertIn("--adopt", row)
        for detail in (
            "no_material",
            "material_invalid",
            "event_invalid",
            "tail_unknown",
        ):
            with self.subTest(detail=detail):
                self.assertIn(detail, row)

    def test_s03_the_adopt_escape_is_routed_with_its_precondition(self):
        """CR-01 (iteration 3) — ``--adopt`` is conditional, so the row must be.

        The first CR-01 fix put the bare command ``crayon resume <id> --adopt
        --note "…"`` in this row as *the* escape for ``commit_rejected``. The
        tool applies two preconditions to it: ``resume_adopt`` refuses
        ``adopt_unsupported`` unless the batch's last event is a generation or
        a reviewer edit, and degrades to a plain resume when nothing on disk is
        ``unexpected`` — in which case the same commit is refused again. A row
        that names the command unconditionally sends a skill into a refusal on
        every batch except the one shape where the hook rewrote placed bytes.
        """
        row = routing_row("recovery_unsupported")
        self.assertIn("ONLY", row)
        self.assertIn("adopt_unsupported", row)
        self.assertIn("plain resume", row)
        # The escape that always works has to be there too, or the row names a
        # precondition and no way forward when it does not hold. Matched on the
        # stem, because WR-03 widened "the commit" to "the transition" for the
        # `stage_rejected` arm, where no commit was ever attempted.
        self.assertIn("remove what is refusing the", row)

    def test_s03_the_adopt_unsupported_row_does_not_close_the_loop(self):
        """CR-01 (iteration 3) — the second hop of the two-hop livelock.

        ``adopt_unsupported``'s row routed to ``crayon resume <id> --overwrite``
        unconditionally. On a batch git has already refused, ``--overwrite``
        re-places the same bytes, meets the same hook and raises
        ``commit_rejected`` — whose row named ``--adopt``, which lands back
        here. The row must say where that loop stops.
        """
        row = routing_row("adopt_unsupported")
        for marker in ("historical count", "once nothing is refusing the transition"):
            with self.subTest(marker=marker):
                self.assertIn(marker, row)
        self.assertIn("remove what is refusing the", row)

    def test_s03_the_resume_row_does_not_route_commit_rejected_into_its_refusal(self):
        """CR-01 — ``commit_rejected`` carries ``next: resume``.

        Every SKILL.md body carries S-04's sentence, "act on the row for the
        emitted ``next``". Unqualified, that row's verb is ``crayon resume <id>``
        — precisely the command that produced the refusal, which is the livelock
        the tool-side fix was written to break, re-opened one layer up.
        """
        row = routing_row("resume", block="tokens")
        self.assertIn("commit_rejected", row)
        self.assertIn("--adopt", row)
        # WR-05: `stage_rejected` carries `next: resume` too (dogen:3256), and
        # the exception named only one of the two details. A body following
        # S-04 on a `stage_rejected` refusal found no applicable exception and
        # ran the command that had just refused.
        self.assertIn("stage_rejected", row)


# ---------------------------------------------------------------------------
# S-04 / S-05 — the SKILL.md body contracts (plan 17-03)
# ---------------------------------------------------------------------------

#: contract.md 6's verb table. A "verb invocation" in a body is an occurrence of
#: ``crayon <verb>``; the hyphenated skill names (``crayon-plan``) can never be
#: mistaken for one because the separator here is a space, not a hyphen.
VERBS = (
    "unit",
    "context",
    "signoff",
    "steer",
    "plan-steps",
    "step",
    "draft",
    "edits",
    "review",
    "resume",
    "show",
    "summary",
    "verify",
    "version",
)

#: Longest first, so ``crayon plan-steps`` is never read as ``crayon plan``.
_VERB_RE = re.compile(
    r"\bcrayon (%s)\b([^\n`]*)"
    % "|".join(re.escape(v) for v in sorted(VERBS, key=len, reverse=True))
)

#: Every ``--flag`` token, wherever it appears in a body.
_FLAG_RE = re.compile(r"--[a-z][a-z-]*")

#: ``add_argument("--flag"…)`` in the tool itself — the set of flags the tool
#: actually exposes. Parsed from source text rather than imported: this suite
#: must not import ``crayon`` (D-11).
_TOOL_FLAG_RE = re.compile(r'add_argument\(\s*"(--[a-z][a-z-]*)"')

#: D-13/D-14: every body routes on its own mirror of the one routing table, and
#: no body re-derives direction. The sentence is literal so a paraphrase — which
#: is where re-derivation creeps back in — goes red.
ROUTING_SENTENCE = (
    "Read `references/routing.md` and act on the row for the emitted `next`."
)

#: T-17-12: no skill may send an author into the ledger with an editor.
NEVER_HAND_EDIT = "The ledger is never hand-edited."

#: VERB-01 removed ``--force`` rather than renaming it; rev8 7 says the flag
#: never appears in a skill either.
FORCE_FLAG = "--force"

#: D-14's verbatim carry-over for ``crayon-plan``: the advise-only triage fork and
#: the Socratic intake, byte for byte as the dogfooded file had them. Stored as
#: literals on purpose — reading them back out of the file under test would make
#: the assertion vacuous.
TRIAGE_FORK = """**Triage fork (advise-only).** When the TA's ask is an assessment — "does this need
docs?" — do the same grounding, then deliver a **Triage Recommendation** and STOP:
what the change touches; which existing pages are affected; the unit you *would*
declare (id, target, sources, Diataxis type, route) if the TA says go; or "no
documentation change needed" and why. No intake, no ceremony, no signoff — only an
explicit "declare it" starts the Socratic intake."""

SOCRATIC_INTAKE = """Begin the Socratic intake with the reader's problem, then the audience — the two
judgment fields. Ask exactly one question per turn, building each on the previous
answer:

**"Looking at what you want to document, what problem does this page solve for its
reader?"**

Then, once the problem is clear, draw out who the page is for (the audience). Keep
questions open-ended, not leading; probe when an answer is vague; do not record
anything yet. Give your view of the audience only when the TA asks for it, stated as
evidence — what the siblings or the change show — and never as a marked option. A
vague answer gets a narrower probe, not a proposal."""

#: D-16: the two fixed questions an intake keeps open when the brief fills every
#: field. Literals, so a paraphrase of either goes red.
ARRIVAL_QUESTION = "What is the reader doing just before they land here?"
NEXT_QUESTION = "What do they do right after?"

#: JUDG-04, D-16: the sentence that opens step 2's minimum-intake paragraph —
#: the arrival-or-next question and the leave-out question make two.
TWO_OPEN_QUESTIONS = "Every intake asks at least two open questions."

#: D-16: the second fixed question, asked in every intake. A literal, so a
#: paraphrase goes red.
LEAVE_OUT_QUESTION = "What can this page leave out?"

#: D-16: where the leave-out question sits — after the arrival-or-next question.
LEAVE_OUT_ORDER = "after the arrival-or-next question"

#: D-17: a "nothing" answer to the leave-out question puts nothing in ``--notes``.
NOTHING_RECORDS_NOTHING = 'A "nothing" answer to the leave-out question records nothing'

#: D-12: a view on a judgment field is given on request, never volunteered.
VIEW_ON_REQUEST = "only when the TA asks for"

#: WR-06: the one terminal move once two narrowing probes leave the answer vague,
#: stated the same in every file the intake loads.
PROBES_RUN_OUT = (
    "After two narrowing probes, say plainly that the answer is still open, and ask "
    "whether they want your view on it"
)

#: D-08, D-17: what ``--notes`` carries, and nothing else.
NOTES_ARE_THEIRS = "the TA's own words given in answer to an open question"

#: WR-02 (22-09): the precedence between the author's leave-out notes and a
#: signed inventory, and between the notes and a later request. Stated once in
#: crayon-write step 2 and once in review-rubric.md, so the writer and the
#: reviewer settle B-74's own state the same way.
NOTES_NARROW_INVENTORY = "leave-out notes narrow the plan's inventory"
LATER_REQUEST_OUTRANKS = "A later recorded request outranks the intake notes"


def body_of(skill_dir):
    """One skill's body — everything after the frontmatter block."""
    text = skill_dir.joinpath("SKILL.md").read_text(encoding="utf-8")
    return skill_lint.split_front_matter(text)[1]


def verb_invocations(body):
    """``[(verb, whole invocation text)]`` in the order they appear in a body.

    A shell continuation (``\\`` then a newline) is joined first, so a call whose
    flags sit on later lines is still read as one invocation.
    """
    joined = re.sub(r"\\\n\s*", " ", body)
    return [(m.group(1), m.group(0)) for m in _VERB_RE.finditer(joined)]


def assert_verb_scoped_flags(case, text, what):
    """Every flag on a ``crayon <verb> …`` invocation is one THAT verb takes.

    WR-06: S-05 and S-10 both asserted membership of ``tool_flags()``, a flat
    union of every ``add_argument`` in the file, and then threw the verb away.
    ``crayon show <id> --re-sign``, ``crayon steer <id> --steps-seq 4`` and
    ``crayon edits <id> --hook`` all passed — and "documented-but-nonexistent
    verbs, wrong flag names" is the defect class the gate exists for.
    """
    per_verb = tool_verb_flags()
    for verb, invocation in verb_invocations(text):
        exposed = per_verb.get(verb)
        case.assertIsNotNone(
            exposed, "`crayon %s` is not a verb build_parser registers" % verb
        )
        for flag in sorted(set(_FLAG_RE.findall(invocation))):
            with case.subTest(what=what, verb=verb, flag=flag):
                case.assertIn(
                    flag,
                    exposed,
                    "%s writes `crayon %s %s`; `crayon %s` takes %s"
                    % (what, verb, flag, verb, ", ".join(sorted(exposed))),
                )


def assert_contains(case, haystack, needle, what):
    """``needle in haystack`` without dumping a whole SKILL.md into the report.

    ``assertIn`` prints the container on failure, which for a 250-line body
    buries the one fact that matters. The message names the file and the missing
    text instead.
    """
    case.assertTrue(
        needle in haystack, "%s does not contain %s" % (what, repr(needle))
    )


def assert_omits(case, haystack, needle, what):
    """The negative half of :func:`assert_contains`, equally quiet."""
    case.assertFalse(
        needle in haystack, "%s must not contain %s" % (what, repr(needle))
    )


def tool_flags():
    """Every ``--flag`` the tool registers, read from ``crayon``'s source text."""
    text = (ROOT / "crayon.py").read_text(encoding="utf-8")
    flags = set(_TOOL_FLAG_RE.findall(text))
    flags.add("--help")
    return flags


#: The vacuous-pass floor for :func:`tool_verb_flags`. A walk that stopped
#: matching ``build_parser``'s shape would return an empty map, and every
#: per-verb assertion would then pass over nothing.
MIN_VERBS_PARSED = 12

#: WR-06: bounds on the SHARED set, which is the walk's widening direction. It
#: is ``{--help, --json}`` today — ``--json`` from the ``common`` parent every
#: verb takes as ``parents=[common]``, ``--help`` from argparse itself. A flag
#: that landed here by accident is then accepted on EVERY verb at once, and the
#: verb-count floor above cannot see it because the verb count does not change.
MIN_SHARED_FLAGS = 2
MAX_SHARED_FLAGS = 3


def walk_verb_flags():
    """``({verb: {flags}}, [shared], [unbound])`` from ``build_parser`` (WR-06).

    :func:`tool_flags` greps every ``add_argument("--flag"…)`` in the file into
    ONE flat set, so a flag put on the WRONG verb passed: ``crayon show <id>
    --re-sign``, ``crayon steer <id> --steps-seq 4`` and ``crayon edits <id>
    --hook`` were all accepted by S-05 and S-10, and "wrong flag names" is the
    defect class those gates exist for.

    Walked with :mod:`ast` over ``crayon``'s SOURCE — parsing text, not importing
    it, so the D-11 rule the module docstring states still holds. Statements are
    read in source order because ``build_parser`` binds a subparser to a local
    name and then adds arguments to that name.

    ``unit``'s three sub-verbs fold into ``unit``: a body writes ``crayon unit
    new --body-file -``, which :data:`_VERB_RE` captures as the verb ``unit``.
    Flags on the shared ``common`` parent belong to every verb, as
    ``parents=[common]`` gives them. A mutually-exclusive group resolves to the
    parser it was opened on — ``--note`` and ``--note-file`` are registered that
    way on four different verbs, and reading the group as a parser of its own
    would put both flags on every verb instead.

    WR-06 (iteration 3): the walk FAILS CLOSED. ``owner`` is populated only by
    the four branches above, and an ``add_argument`` on a receiver none of them
    bound — a parser built by a helper, a subparser assigned through tuple
    unpacking, an ``add_parser`` whose verb is not a literal (``continue``d
    above, leaving ``owner[name]`` unset) — used to fall into the ``shared``
    set and be accepted on EVERY verb. A gate whose degradation mode is "accept
    more" is the shape WR-06 was filed against in the first place. Unbound
    receivers are collected instead, and
    :meth:`test_s10_the_per_verb_flag_map_is_not_vacuous` requires the list to
    be empty: an unrecognised parser shape is a walk that needs updating, not a
    flag that belongs everywhere.
    """
    tree = ast.parse((ROOT / "crayon.py").read_text(encoding="utf-8"))
    builder = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_parser"
    )
    owner = {}
    flags = {}
    shared = {"--help"}
    unbound = []

    def literal(node):
        return node.value if isinstance(node, ast.Constant) else None

    #: ``verbs``/``unit_verbs`` — a subparser factory, bound to the verb whose
    #: parser opened it (``None`` for the root's).
    subparsers = {}

    for statement in builder.body:
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
            call, func = statement.value, statement.value.func
            if not isinstance(statement.targets[0], ast.Name):
                continue
            name = statement.targets[0].id
            parent = (
                func.value.id
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                else ""
            )
            attribute = func.attr if isinstance(func, ast.Attribute) else ""
            if attribute == "add_parser":
                verb = literal(call.args[0]) if call.args else None
                if verb is None:
                    continue
                # `unit new` / `unit edit` / `unit retire` are written as
                # `crayon unit …`, so their flags are the `unit` verb's.
                owner[name] = subparsers.get(parent) or verb
                flags.setdefault(owner[name], set())
            elif attribute == "add_subparsers":
                subparsers[name] = owner.get(parent)
            elif attribute in ("add_mutually_exclusive_group", "add_argument_group"):
                # A group is not a parser: its flags belong to whatever opened it.
                owner[name] = owner.get(parent)
            elif isinstance(func, ast.Name) and func.id == "_Parser":
                owner[name] = None  # the root parser and the shared parent
        elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            func = statement.value.func
            if not (isinstance(func, ast.Attribute) and func.attr == "add_argument"):
                continue
            if not isinstance(func.value, ast.Name):
                continue
            flag = literal(statement.value.args[0]) if statement.value.args else None
            if not isinstance(flag, str) or not flag.startswith("--"):
                continue
            # WR-06: `not in owner` and `owner[...] is None` are DIFFERENT
            # facts, and `dict.get(name, None)` collapsed them. The first is
            # "this walk does not understand the receiver"; only the second is
            # "the root or the shared parent, so the flag is every verb's".
            if func.value.id not in owner:
                unbound.append((func.value.id, flag))
            elif owner[func.value.id] is None:
                shared.add(flag)
            else:
                flags.setdefault(owner[func.value.id], set()).add(flag)

    return (
        dict((verb, found | shared) for verb, found in flags.items()),
        sorted(shared),
        sorted(unbound),
    )


def tool_verb_flags():
    """:func:`walk_verb_flags`'s map alone, for the assertions that want it."""
    return walk_verb_flags()[0]


class TestS04TheCommonOpening(unittest.TestCase):
    """S-04 — every skill opens on the tool and routes on the mirrored table."""

    def test_s04_every_body_puts_each_flag_on_a_verb_that_takes_it(self):
        # WR-06, over all three bodies: S-05's version of this covers
        # `crayon-plan` only, and the defect is not skill-specific.
        for skill_dir in skill_dirs():
            assert_verb_scoped_flags(
                self, body_of(skill_dir), skill_dir.name
            )

    def test_s04_the_first_two_verb_invocations_are_version_then_show(self):
        # SKILL-05 - D-14, probe 33: nothing is proposed, written or recorded
        # before the tool has answered "which tool is this" and "where is this
        # unit" — or, for a context skill, "what context is there". Both
        # answers are read as JSON, so no skill parses prose.
        for skill_dir in skill_dirs():
            with self.subTest(skill=skill_dir.name):
                found = verb_invocations(body_of(skill_dir))
                self.assertGreaterEqual(
                    len(found),
                    2,
                    "%s names fewer than two verbs in its body" % skill_dir.name,
                )
                state_verb = "context" if skill_dir.name in CONTEXT_SKILLS else "show"
                self.assertEqual(
                    [verb for verb, _ in found[:2]],
                    ["version", state_verb],
                    "%s must open on `crayon version` then `crayon %s`; its first "
                    "two verb invocations are %r"
                    % (skill_dir.name, state_verb, [text for _, text in found[:2]]),
                )
                if state_verb == "context":
                    self.assertIn(
                        "show",
                        found[1][1],
                        "%s must open on `crayon context show`, not another "
                        "context verb: %r" % (skill_dir.name, found[1][1]),
                    )
                for verb, text in found[:2]:
                    self.assertIn(
                        "--json",
                        text,
                        "the opening `crayon %s` in %s must read the machine-"
                        "readable answer: %r" % (verb, skill_dir.name, text),
                    )

    def test_s04_every_body_routes_on_the_mirrored_routing_table(self):
        for skill_dir in skill_dirs():
            with self.subTest(skill=skill_dir.name):
                assert_contains(
                    self, body_of(skill_dir), ROUTING_SENTENCE, skill_dir.name
                )

    def test_s04_every_body_says_the_ledger_is_never_hand_edited(self):
        # T-17-12: an instruction to hand-edit the record is the one tampering
        # path a skill can open on its own.
        for skill_dir in skill_dirs():
            with self.subTest(skill=skill_dir.name):
                assert_contains(
                    self, body_of(skill_dir), NEVER_HAND_EDIT, skill_dir.name
                )

    def test_s04_no_body_names_a_force_flag(self):
        for skill_dir in skill_dirs():
            with self.subTest(skill=skill_dir.name):
                assert_omits(
                    self, body_of(skill_dir), FORCE_FLAG, skill_dir.name
                )


class TestS14ContextSkillsThroughVerbs(unittest.TestCase):
    """S-14 — the context skills hand every artefact to the tool and write nothing.

    The single-writer rule (S-02) says only `crayon-write` holds a write tool; the
    two context skills produce files nonetheless, so the path those files take
    is the assertion: `crayon context stage … --body-file -` for each artefact,
    `crayon context record` for the set, and no write tool named anywhere.
    """

    def test_s14_each_context_skill_stages_and_records_through_the_tool(self):
        for name in CONTEXT_SKILLS:
            body = body_of(SKILLS_ROOT / name)
            with self.subTest(skill=name):
                assert_contains(self, body, "crayon context stage", name)
                assert_contains(self, body, "--body-file -", name)
                assert_contains(self, body, "crayon context record", name)
                for tool in ("`Write`", "`Edit`", "`MultiEdit`"):
                    self.assertFalse(
                        tool in body, "%s must not name %s; it does not hold it" % (name, tool)
                    )

    def test_s14_every_flag_is_on_a_verb_that_takes_it(self):
        for name in CONTEXT_SKILLS:
            assert_verb_scoped_flags(self, body_of(SKILLS_ROOT / name), name)

    def test_s14_the_two_context_skills_hand_off_to_each_other(self):
        # onboard walks the repository; fetch takes declared external sources.
        # Each names the other for the case it does not serve, so an author is
        # never told "not this skill" without being told which one.
        assert_contains(self, body_of(SKILLS_ROOT / "crayon-onboard"), "/crayon-fetch", "crayon-onboard")
        assert_contains(self, body_of(SKILLS_ROOT / "crayon-fetch"), "/crayon-onboard", "crayon-fetch")

    def test_s14_the_stance_references_are_mirrored_byte_for_byte(self):
        for name in STANCE_REFERENCES:
            source = SKILLS_ROOT / "crayon-onboard" / "references" / name
            mirror = SKILLS_ROOT / "crayon-fetch" / "references" / name
            with self.subTest(reference=name):
                self.assertTrue(source.exists(), "%s is missing" % source)
                self.assertTrue(mirror.exists(), "%s is missing" % mirror)
                self.assertEqual(
                    mirror.read_bytes(),
                    source.read_bytes(),
                    "%s has drifted from %s; re-copy the bytes rather than "
                    "hand-editing the mirror" % (mirror, source),
                )

    def test_s14_the_context_skills_name_the_five_artefacts(self):
        names = ("doc-style.md", "glossary.md", "structure.md", "code-to-docs-map.md", "doc-gaps.md")
        fetch = body_of(SKILLS_ROOT / "crayon-fetch")
        for name in names:
            with self.subTest(artefact=name):
                assert_contains(self, fetch, name, "crayon-fetch")
        onboard = body_of(SKILLS_ROOT / "crayon-onboard")
        for name in names[:3]:
            with self.subTest(artefact=name):
                assert_contains(self, onboard, name, "crayon-onboard")


class TestS05PlanThroughVerbs(unittest.TestCase):
    """S-05 — ``crayon-plan`` declares through verbs and keeps its judgment."""

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-plan")

    def test_s05_unit_md_reaches_disk_only_through_unit_new_body_file(self):
        # D-14: the skill holds no write-capable tool, so the only path from a
        # composed plan to disk is the tool's own stdin flag, under its lock.
        assert_contains(self, self.body, "crayon unit new", "crayon-plan")
        assert_contains(self, self.body, "--body-file -", "crayon-plan")
        for tool in ("`Write`", "`Edit`", "`MultiEdit`"):
            self.assertFalse(
                tool in self.body,
                "crayon-plan must not name %s; it does not hold it" % tool,
            )

    def test_s05_the_context_is_read_through_the_tool_and_bootstrapped_once(self):
        # The plan skill grounds on `crayon context show`, not on a directory
        # listing, and when the context is missing it offers the three-way
        # choice — including the onboarding skill and the ephemeral reference —
        # rather than authoring `.crayon/context/` itself.
        assert_contains(self, self.body, "crayon context show --json", "crayon-plan")
        assert_contains(self, self.body, "/crayon-onboard", "crayon-plan")
        assert_contains(self, self.body, "/crayon-fetch", "crayon-plan")
        assert_contains(self, self.body, "references/context-bootstrap.md", "crayon-plan")
        for name in ("doc-style.md", "glossary.md", "structure.md", "code-to-docs-map.md", "doc-gaps.md"):
            with self.subTest(artefact=name):
                assert_contains(self, self.body, "`%s`" % name, "crayon-plan")
        bootstrap = (SKILLS_ROOT / "crayon-plan" / "references" / "context-bootstrap.md").read_text(encoding="utf-8")
        assert_contains(self, bootstrap, "Persist nothing", "context-bootstrap.md")
        assert_omits(self, bootstrap, "crayon context stage", "context-bootstrap.md")

    def test_s05_the_amendment_and_retire_verbs_are_named(self):
        assert_contains(self, self.body, "crayon unit edit", "crayon-plan")  # J3
        assert_contains(self, self.body, "--re-sign", "crayon-plan")
        assert_contains(self, self.body, "crayon unit retire", "crayon-plan")  # J7

    def test_s05_every_flag_the_body_names_is_a_flag_the_tool_exposes(self):
        exposed = tool_flags()
        for flag in sorted(set(_FLAG_RE.findall(self.body))):
            with self.subTest(flag=flag):
                self.assertIn(
                    flag,
                    exposed,
                    "crayon-plan names %s, which `crayon` does not register" % flag,
                )

    def test_s05_every_flag_is_on_a_verb_that_takes_it(self):
        # WR-06: the assertion above is against the tool's WHOLE flag set, so
        # `crayon show <id> --re-sign` passed it. The verb is already captured;
        # it was being discarded.
        assert_verb_scoped_flags(self, self.body, "crayon-plan")

    def test_s05_the_judgment_sections_are_carried_over_verbatim(self):
        # D-14: dogfood-validated judgment survives the rewrite byte for byte.
        assert_contains(self, self.body, "Socratic", "crayon-plan")
        assert_contains(self, self.body, TRIAGE_FORK, "crayon-plan")
        assert_contains(self, self.body, SOCRATIC_INTAKE, "crayon-plan")

# ---------------------------------------------------------------------------
# S-06 / S-07 — the ``crayon-write`` body and its walk protocol (plan 17-03)
# ---------------------------------------------------------------------------

WRITE_SKILL = SKILLS_ROOT / "crayon-write" / "SKILL.md"
WALK_PROTOCOL = SKILLS_ROOT / "crayon-write" / "references" / "walk-protocol.md"

#: contract.md 5.6, evidence-file row: ``JSON {verdict, exit_code, mode, command,
#: reason}``. Exactly this set — "digests never typed" is the same row.
EVIDENCE_KEYS = frozenset({"verdict", "exit_code", "mode", "command", "reason"})

#: contract.md 5.3, ``steps-planned``: the skill supplies these four per step and
#: the tool computes ``text_hash`` itself (D-01).
STEP_PLAN_KEYS = frozenset({"id", "text", "mode", "stateful"})

#: LEDG-06 / D-03 / D-15: a skill that computes a digest turns recorded
#: provenance into a claim the record cannot corroborate. None of these may
#: appear in the skill or in the protocol it loads.
DIGEST_UTILITIES = (
    "sha256sum",
    "sha1sum",
    "sha512sum",
    "shasum",
    "md5sum",
    "b2sum",
    "cksum",
    "openssl dgst",
)

#: The v1.2 recipe piped through ``tee``, so it needed the pipeline's exit-status
#: array to recover the command's own status. D-15 removes the pipe, so the plain
#: ``$?`` IS the command's status and the array has no place left.
EXIT_STATUS_ARRAYS = ("PIPESTATUS", "pipestatus")

#: D-02 rejected redaction for v2.0. The excerpt is committed as captured; the
#: only honest claim about it is the one below.
SANITISATION_CLAIMS = (
    "redact",
    "sanitis",
    "sanitiz",
    "scrub",
    "secrets removed",
    "secret-free",
    "free of secrets",
)
HONEST_EXCERPT_CLAIM = "control characters"

#: Digest keys the v1.2 evidence file carried. The tool refuses a typed digest.
TYPED_DIGEST_KEYS = ("output_sha256", "step_text_sha256")

#: Tutorial/how-to step modes, the two wire values the tool validates.
STEP_MODES = ("agent", "ta")

#: D-15: the author is asked before resolved evidence is carried forward, because
#: reuse is a claim about a prefix that has not been re-run.
KEEP_EVIDENCE_QUESTION = "Ask the author before passing `--keep-evidence`"

#: D-14's verbatim carry-over for the walk protocol: the just-in-time consent gate
#: with its destructive backstop, and the move-never-delete rule that keeps a
#: cleanup step away from the author's own captures. Literals on purpose — reading
#: them back out of the file under test would make the assertion vacuous.
JIT_CONSENT = """A step's destructive/stateful marker is proposed at plan review and vetoed/corrected
by the TA there. Permission for a marked step is asked **just-in-time**, right
before that step executes — informed by what prior steps actually did. An **unmarked**
command that smells destructive (`rm -rf`, `git reset --hard`, `docker … prune`, a
write outside the workspace) **re-prompts via the runtime backstop instead of
running**. Consent is confined to genuinely dangerous steps — never a confirm-parade.
The marker is conversational (no persisted field); the backstop is the safety net,
so safety never depends on persistence. A step the TA will not consent to can be
switched to TA-runs."""

MOVE_NEVER_DELETE = """The `evidence/` subdir is never
a cleanup target — move-never-delete; a cleanup step must not reach `evidence/`,
`docs/`, or `.git`."""

_FENCE_RE = re.compile(r"```[a-z]*\n(.*?)```", re.DOTALL)
_JSON_KEY_RE = re.compile(r'"([a-z_]+)"\s*:')


def fenced_blocks(text):
    """Every fenced code block's content, in order."""
    return _FENCE_RE.findall(text)


def blocks_containing(text, needle):
    """The fenced blocks that carry ``needle`` — e.g. an evidence JSON file."""
    return [block for block in fenced_blocks(text) if needle in block]


def json_keys(block):
    """``{"verdict": "pass"}`` → ``{"verdict"}``. Keys only, values ignored."""
    return set(_JSON_KEY_RE.findall(block))


class TestS06TheEvidenceRecipe(unittest.TestCase):
    """S-06 — ``crayon-write`` records the walk through the verbs that gate it."""

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-write")
        self.calls = {}
        for verb, text in verb_invocations(self.body):
            self.calls.setdefault(verb, []).append(text)

    def test_s06_the_step_verb_carries_the_three_evidence_flags(self):
        wanted = ("--steps-seq", "--evidence-file", "--output-file")
        calls = self.calls.get("step", [])
        self.assertTrue(calls, "crayon-write names no `crayon step` invocation")
        complete = [c for c in calls if all(flag in c for flag in wanted)]
        self.assertTrue(
            complete,
            "no `crayon step` invocation in crayon-write carries all of %s; found "
            "%r" % (", ".join(wanted), calls),
        )

    def test_s06_the_step_plan_is_recorded_through_plan_steps(self):
        calls = self.calls.get("plan-steps", [])
        self.assertTrue(calls, "crayon-write names no `crayon plan-steps` invocation")
        self.assertTrue(
            [c for c in calls if "--steps-file" in c],
            "no `crayon plan-steps` invocation carries --steps-file; found %r" % calls,
        )

    def test_s06_keep_evidence_is_asked_for_before_it_is_passed(self):
        assert_contains(self, self.body, "--keep-evidence", "crayon-write")
        assert_contains(self, self.body, KEEP_EVIDENCE_QUESTION, "crayon-write")

    def test_s06_the_skill_supplies_no_step_text_hash(self):
        # D-01: `text_hash` is the tool's to compute. A plan block that carries
        # one is a digest the record cannot corroborate.
        plans = blocks_containing(self.body, '"text"')
        self.assertTrue(plans, "crayon-write shows no step-plan JSON block")
        for block in plans:
            with self.subTest(block=block[:40]):
                self.assertLessEqual(json_keys(block), STEP_PLAN_KEYS)


class TestS07TheHonestyGuards(unittest.TestCase):
    """S-07 — the skill computes no digest and claims nothing about secrets."""

    def _files(self):
        return {
            path: path.read_text(encoding="utf-8")
            for path in (WRITE_SKILL, WALK_PROTOCOL)
        }

    def test_s07_neither_file_runs_a_shell_digest_utility(self):
        for path, text in self._files().items():
            for utility in DIGEST_UTILITIES:
                with self.subTest(path=path.name, utility=utility):
                    assert_omits(self, text, utility, path.name)

    def test_s07_neither_file_reads_a_pipeline_exit_status_array(self):
        for path, text in self._files().items():
            for name in EXIT_STATUS_ARRAYS:
                with self.subTest(path=path.name, name=name):
                    assert_omits(self, text, name, path.name)

    def test_s07_no_typed_digest_key_survives(self):
        for path, text in self._files().items():
            for key in TYPED_DIGEST_KEYS:
                with self.subTest(path=path.name, key=key):
                    assert_omits(self, text, key, path.name)

    def test_s07_every_evidence_file_key_is_a_contract_key(self):
        for path, text in self._files().items():
            blocks = blocks_containing(text, '"verdict"')
            with self.subTest(path=path.name):
                self.assertTrue(
                    blocks,
                    "%s documents no evidence file; the key check would pass "
                    "vacuously" % path.name,
                )
            for block in blocks:
                with self.subTest(path=path.name, block=block[:40]):
                    self.assertLessEqual(
                        json_keys(block),
                        EVIDENCE_KEYS,
                        "%s writes an evidence key outside contract 5.6's set"
                        % path.name,
                    )

    def test_s07_no_excerpt_is_called_redacted_or_sanitised(self):
        for path, text in self._files().items():
            lowered = text.lower()
            for claim in SANITISATION_CLAIMS:
                with self.subTest(path=path.name, claim=claim):
                    assert_omits(self, lowered, claim, path.name)

    def test_s07_the_honest_excerpt_claim_is_stated(self):
        assert_contains(
            self,
            WRITE_SKILL.read_text(encoding="utf-8"),
            HONEST_EXCERPT_CLAIM,
            WRITE_SKILL.name,
        )

    def test_s07_the_consent_and_cleanup_rules_are_carried_over_verbatim(self):
        # D-14: the walk's safety judgment is dogfood-validated, and
        # move-never-delete is the rule that stops a cleanup step from
        # destroying the very captures the record cites.
        text = WALK_PROTOCOL.read_text(encoding="utf-8")
        assert_contains(self, text, JIT_CONSENT, WALK_PROTOCOL.name)
        assert_contains(self, text, MOVE_NEVER_DELETE, WALK_PROTOCOL.name)

    def test_s07_both_step_mode_wire_values_are_written_out(self):
        text = WALK_PROTOCOL.read_text(encoding="utf-8")
        for mode in STEP_MODES:
            with self.subTest(mode=mode):
                assert_contains(self, text, "`%s`" % mode, WALK_PROTOCOL.name)

# ---------------------------------------------------------------------------
# S-08 / S-09 — the ``crayon-review`` body contracts (plan 17-03)
# ---------------------------------------------------------------------------

REVIEW_SKILL = SKILLS_ROOT / "crayon-review" / "SKILL.md"

#: contract.md 5.8: on `resume_ambiguous` the tool prints the per-file diff and
#: names exactly two choices. A third one would be the skill inventing recovery
#: the tool did not offer.
RESUME_FLAGS = frozenset({"--dry-run", "--overwrite", "--adopt", "--note"})
RESUME_CHOICES = ("--overwrite", "--adopt")

#: contract.md 5.8's honest limit: the tool writes nothing and prints what it
#: found. The skill adds nothing to that.
RECOVERY_UNSUPPORTED_SENTENCE = (
    "Show the tool's printed findings verbatim and stop."
)

#: A restore recipe of the skill's own would move or delete the author's bytes on
#: the strength of a guess. Nothing in the body may run one.
RESTORE_COMMANDS = ("git ", "mv ", "rm ", "cp ", "mkdir ", "truncate ")

#: T34b: the question `show` cannot answer, because the two answers have
#: different documentation outcomes.
RESTORE_OR_AMEND_QUESTION = (
    "Restore the page, or amend the plan so that path is no longer a target?"
)

#: T34a/T34b: `target_missing` is a precondition, not a transient failure.
NEVER_A_SECOND_ACCEPT = "Accept is never issued a second time."

#: T34a: an explicit instruction is recorded as given, not re-negotiated.
RESTORE_WITHOUT_RECONFIRMING = "record it with `crayon steer` without reconfirming it"

#: T34b: the author's direction is the only thing recorded.
INVENTS_NO_NOTE = "The skill invents no steering note."

#: D-09: the accept the author gave with no words beyond the verdict carries no
#: note; the skill never supplies one.
BARE_ACCEPT = "A bare accept records no note."

#: D-01, D-03: a pending request reaches the reviewer as "request <n>", the
#: number the author can say back; the record's own name for it stays on the
#: command line (`--resolves`, `--withdraw`).
PENDING_AS_REQUESTS = (
    'put each pending request to the reviewer one at a time, as "request <n>"'
)

#: D-09: the verdict is asked as one open question that also asks for anything the
#: author wants on the record; their words beyond the verdict are the note.
VERDICT_QUESTION = (
    "What's your verdict, and is there anything you want on the record with it?"
)

#: D-06: a fix or redraft given bare is asked for its note, never offered one.
NEXT_DRAFT_QUESTION = "What should the next draft change?"

#: D-11: a verdict that departs from the lean gets the lean once and this one
#: question, whose answer is final.
KEEP_VERDICT = "Keep <verdict>?"

#: D-10: the lean is shown after the author's verdict, never in front of it.
LEAN_HELD = "held until the author answers"

REVIEW_RUBRIC = SKILLS_ROOT / "crayon-review" / "references" / "review-rubric.md"

#: D-07: a finding's F-number is this conversation's; the next drafting session
#: never sees it, so a note that cites one is restated with the author.
NUMBERS_DO_NOT_TRAVEL = "the numbers will not reach the next drafting session"

#: Contract 5.8's hook sentence, met by the author's own words (D-06, P-02).
HOOK_NOTE = "a hook changed the bytes and that they kept them"

#: CLOSE-01 (D-02, D-03): after an accept the author is asked at most this many
#: questions, each drawn from the unit's record, and none when nothing is open.
AT_MOST_THREE = "at most three questions"

#: D-02: the fixed order the closure takes its questions in, one per source first.
CLOSURE_ORDER = "steps → judged requests → findings → where a reader arrives from"


def tagged_section(text, tag):
    """The text between ``<tag>`` and ``</tag>``, or ``None`` when absent."""
    match = re.search(r"<%s>(.*?)</%s>" % (tag, tag), text, re.DOTALL)
    return match.group(1) if match else None

#: Ways a skill could slip back into writing the author's note for them.
INVENTED_NOTE_TELLS = (
    "on the author's behalf",
    "compose a steering note for",
    "infer the note",
    "assume the author",
)


#: D-14's verbatim carry-over for ``crayon-review``: the deterministic pre-pass and
#: the findings rubric, byte for byte as the dogfooded file had them — six
#: dimensions since D-20 added ``focus`` as item 4. Literals on purpose — reading
#: them back out of the file under test would make the assertion vacuous.
PRE_PASS = """**Deterministic pre-pass (before any judgment):** run cheap read-only greps over
the drafted page(s):
- changelog-framing tells ("previously", "now supports", "starting with")
- banned researcher register ("observed", "the fixtures show", "the corpus")
- self-reference openers ("This page describes", "This document")

Each hit is either promoted into the findings as a prioritized finding marked
`(pre-pass)`, or dismissed with a one-line reason."""

SIX_DIMENSIONS = """Then assess the six dimensions, presenting findings grouped by dimension:

1. **writing-approach** (always on, assessed first) — stance contract violations,
   researcher register, implementation identifiers in prose.
2. **source-fidelity** — re-check the draft's concrete claims against the recorded
   sources. Open the files; don't judge only on internal coherence.
3. **completeness** — does the draft satisfy every `## Outline / acceptance` item?
   An objective-check failure is must-fix by definition.
4. **focus** — the mirror of completeness: what is on the page that the reader does
   not need. Material the reader's problem does not call for, anything the author's
   intake notes say to leave out (must-fix), and a complete page whose sections do not
   build toward the reader's problem, meet the reader where they arrive or hand them
   their next step.
5. **structure-fit** — format hygiene (MyST/rST), cross-page consistency for
   multi-file units, relative link paths resolve from the page's location.
6. **clarity** — sentence-level clarity, jargon, forward references.

Number findings `F-1`, `F-2`, … Each carries: page path, the verbatim offending
text, a concrete suggested action, and a priority tag (must-fix / should-fix / nit).
Ground source-fidelity and completeness by re-checking claims against the recorded
sources."""


def command_lines(text):
    """Every non-empty command line inside a fenced block, stripped."""
    lines = []
    for block in fenced_blocks(text):
        for line in block.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(stripped)
    return lines


class TestS08RecoveryPresentation(unittest.TestCase):
    """S-08 — ``crayon-review`` presents recovery the way the contract prints it."""

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-review")
        self.resumes = [
            text for verb, text in verb_invocations(self.body) if verb == "resume"
        ]

    def test_s08_the_dry_run_precedes_any_bare_resume(self):
        # probe 38: never two write verbs without reading the first one's
        # response. The dry run writes nothing and classifies everything.
        self.assertTrue(self.resumes, "crayon-review names no `crayon resume`")
        self.assertIn(
            "--dry-run",
            self.resumes[0],
            "the first `crayon resume` in crayon-review must be the dry run; it is "
            "%r" % self.resumes[0],
        )
        # Position in the ordered invocation list, not a substring offset: the
        # dry-run line BEGINS with the bare invocation's text, so `str.index`
        # would find the dry run when asked where the bare resume is.
        flagged = [
            i for i, text in enumerate(self.resumes) if "--dry-run" in text
        ]
        bare = [
            i
            for i, text in enumerate(self.resumes)
            if not any(flag in text for flag in RESUME_FLAGS)
        ]
        self.assertTrue(
            bare,
            "crayon-review never runs the real `crayon resume` after the dry run",
        )
        self.assertLess(
            flagged[0],
            bare[0],
            "the real resume must be instructed after the dry run, not before; "
            "the resume invocations are %r" % self.resumes,
        )

    def test_s08_resume_ambiguous_offers_exactly_the_two_contract_choices(self):
        used = set()
        for text in self.resumes:
            used.update(_FLAG_RE.findall(text))
        for choice in RESUME_CHOICES:
            with self.subTest(choice=choice):
                self.assertIn(choice, used)
        self.assertLessEqual(
            used,
            RESUME_FLAGS,
            "crayon-review offers a resume flag outside contract 5.8's two "
            "choices: %s" % sorted(used - RESUME_FLAGS),
        )

    def test_s08_recovery_unsupported_is_shown_verbatim_and_stops(self):
        assert_contains(
            self, self.body, RECOVERY_UNSUPPORTED_SENTENCE, "crayon-review"
        )

    def test_s08_commit_rejected_is_not_presented_as_having_written_nothing(self):
        """CR-01 — "it wrote nothing" is false for the one detail the WRITE
        path raises. On ``commit_rejected`` the batch is appended and the files
        are placed; a body that tells the author their work was not written,
        tells them to stop, and forbids anything that would commit the tail has
        forbidden the ``--adopt`` the tool's own hint offers.
        """
        assert_contains(self, self.body, "commit_rejected", "crayon-review")
        assert_contains(self, self.body, "--adopt", "crayon-review")

    def test_s08_the_adopt_escape_carries_its_precondition_in_the_body(self):
        """CR-01 (iteration 3) — step_10 offered ``--adopt`` unconditionally.

        The body is what the reviewer skill reads aloud. Naming the command
        without the two conditions the tool checks is how the escape became a
        second refusal. Both conditions, and the escape that needs neither, must
        be in the text.
        """
        assert_contains(self, self.body, "adopt_unsupported", "crayon-review")
        assert_contains(self, self.body, "conditional", "crayon-review")
        assert_contains(self, self.body, "unexpected", "crayon-review")
        # Whitespace-collapsed, because the claim is about the sentence and
        # not about where the paragraph happens to wrap today.
        self.assertIn(
            "remove what is refusing the",
            re.sub(r"\s+", " ", self.body),
            "crayon-review's step_10 no longer names the escape that works on "
            "every batch, leaving only the conditional one",
        )
        self.assertNotIn(
            "It wrote nothing",
            self.body,
            "crayon-review still makes the unscoped claim; it holds for stage "
            "a's details only",
        )

    def test_s08_the_body_carries_no_restore_recipe_of_its_own(self):
        for line in command_lines(self.body):
            for command in RESTORE_COMMANDS:
                with self.subTest(line=line[:50]):
                    self.assertFalse(
                        line.startswith(command),
                        "crayon-review runs %r; recovery is the tool's to print, "
                        "not the skill's to improvise" % line,
                    )

    def test_s08_accept_closes_pending_requests_by_recorded_disposition(self):
        # contract 5.6: the two sets are disjoint and every withdrawal carries a
        # non-empty reason, so nothing is closed by silence.
        assert_contains(self, self.body, "--resolves", "crayon-review")
        assert_contains(self, self.body, "--withdraw", "crayon-review")


class TestS08JudgmentCarryOver(unittest.TestCase):
    """S-08 — D-14's verbatim carry-over for ``crayon-review``."""

    def test_s08_the_findings_rubric_is_carried_over_verbatim(self):
        body = body_of(SKILLS_ROOT / "crayon-review")
        assert_contains(self, body, "six dimensions", "crayon-review")
        assert_contains(self, body, PRE_PASS, "crayon-review")
        assert_contains(self, body, SIX_DIMENSIONS, "crayon-review")


class TestS09TargetMissing(unittest.TestCase):
    """S-09 — T34a/T34b: the missing target is the author's call, not the skill's."""

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-review")

    def test_s09_the_restore_or_amend_question_is_asked_as_one_sentence(self):
        assert_contains(
            self, self.body, RESTORE_OR_AMEND_QUESTION, "crayon-review"
        )

    def test_s09_accept_is_never_retried_after_target_missing(self):
        assert_contains(self, self.body, "target_missing", "crayon-review")
        assert_contains(self, self.body, NEVER_A_SECOND_ACCEPT, "crayon-review")

    def test_s09_an_explicit_restore_instruction_is_recorded_without_asking_again(
        self,
    ):
        assert_contains(
            self, self.body, RESTORE_WITHOUT_RECONFIRMING, "crayon-review"
        )

    def test_s09_the_skill_records_only_the_direction_the_author_gave(self):
        assert_contains(self, self.body, INVENTS_NO_NOTE, "crayon-review")
        lowered = self.body.lower()
        for tell in INVENTED_NOTE_TELLS:
            with self.subTest(tell=tell):
                assert_omits(self, lowered, tell, "crayon-review")


class TestS15AuthorRules(unittest.TestCase):
    """S-15 — D-14: one author-rules block, carried byte for byte where it binds."""

    #: Typed on purpose: reading the rules back out of the README would make
    #: the non-vacuity check pass over whatever the block happens to say.
    LITERALS = (
        "**The author's words, verbatim.**",
        "**No marked option on a judgment question.**",
        "**An explicit go.**",
        "verbatim",
        "(Recommended)",
        "wins over",
        "harness",
        "explicit go",
        "yes, but",
        "--note",
        "--notes",
    )

    def setUp(self):
        self.block = author_rules_bytes()

    def test_s15_each_skill_carries_the_block_byte_for_byte(self):
        for name in RULE_SKILLS:
            text = (SKILLS_ROOT / name / "SKILL.md").read_bytes()
            with self.subTest(skill=name):
                self.assertTrue(
                    carries_block_once(text, self.block),
                    "%s/SKILL.md does not carry the author-rules block of %s "
                    "exactly once; re-copy the bytes from the begin sentinel "
                    "through the end sentinel rather than hand-editing the copy"
                    % (name, README),
                )
                self.assertEqual(
                    sum(1 for line in text.split(b"\n") if _RULES_BEGIN in line),
                    1,
                    "%s/SKILL.md carries more than one author-rules block" % name,
                )

    def test_s15_the_context_skills_do_not_carry_it(self):
        for name in CONTEXT_SKILLS:
            with self.subTest(skill=name):
                self.assertNotIn(
                    _RULES_BEGIN,
                    (SKILLS_ROOT / name / "SKILL.md").read_bytes(),
                    "%s records no author note, and states the no-marker rule "
                    "at its one judgment question; the author-rules block does "
                    "not belong there" % name,
                )

    def test_s15_the_block_is_not_vacuous(self):
        text = self.block.decode("utf-8")
        for literal in self.LITERALS:
            with self.subTest(literal=literal):
                assert_contains(self, text, literal, "the author-rules block")

    def test_s15_the_block_names_no_tool(self):
        text = self.block.decode("utf-8")
        assert_omits(self, text, "AskUserQuestion", "the author-rules block")
        tools = set()
        for skill_dir in skill_dirs():
            tools.update(tool_list(frontmatter_of(skill_dir)))
        self.assertTrue(tools, "no allowed-tools read: the scan would be vacuous")
        for tool in sorted(tools):
            with self.subTest(tool=tool):
                assert_omits(self, text, "`%s`" % tool, "the author-rules block")

    def test_s15_a_one_byte_drift_is_detected(self):
        # The negative keystone: a copy that differs by one byte must fail the
        # same check the positive gate runs.
        text = (SKILLS_ROOT / "crayon-plan" / "SKILL.md").read_bytes()
        self.assertTrue(carries_block_once(text, self.block))
        start = text.index(self.block) + len(self.block) // 2
        flipped = b"X" if text[start:start + 1] != b"X" else b"Y"
        drifted = text[:start] + flipped + text[start + 1:]
        self.assertFalse(carries_block_once(drifted, self.block))

    def test_s15_the_block_follows_the_opening(self):
        """21 IN-02: the README promises the block "directly after `</opening>`",
        so `</opening>` and one blank line immediately precede its begin
        sentinel: the author rules in plan, write and review, the plain-words
        rules in the two context skills."""
        for names, sentinel in ((RULE_SKILLS, b"<!-- author-rules:begin -->"),
                                (CONTEXT_SKILLS, b"<!-- plain-words:begin -->")):
            for name in names:
                text = (SKILLS_ROOT / name / "SKILL.md").read_bytes()
                with self.subTest(skill=name):
                    self.assertEqual(text.count(sentinel), 1,
                                     "%s carries no single %r" % (name, sentinel))
                    self.assertIn(b"</opening>\n\n" + sentinel, text,
                                  "%s: %r must follow `</opening>` and one blank line"
                                  % (name, sentinel))


class TestS16TheVerdict(unittest.TestCase):
    """S-16 — the verdict is the author's: a bare accept records no note (D-09)."""

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-review")

    def test_s16_a_bare_accept_records_no_note(self):
        self.assertIn(
            'crayon review "$UNIT_ID" --verdict accept',
            command_lines(self.body),
            "crayon-review shows no bare accept as a command line of its own",
        )
        assert_contains(self, self.body, BARE_ACCEPT, "crayon-review")
        assert_omits(
            self,
            self.body,
            '--verdict accept --note "<the reviewer\'s own words>"',
            "crayon-review",
        )

    def test_s16_the_verdict_is_asked_as_one_open_question(self):
        assert_contains(self, self.body, VERDICT_QUESTION, "crayon-review")

    def test_s16_the_note_is_the_authors_words(self):
        assert_contains(self, self.body, NEXT_DRAFT_QUESTION, "crayon-review")
        for stale in ("citing findings by number", "in the reviewer's own words, citing"):
            with self.subTest(stale=stale):
                assert_omits(self, self.body, stale, "crayon-review")

    def test_s16_a_non_answer_and_a_conditional_accept_are_asked_again(self):
        step = skill_step_body(self.body, 6)
        self.assertIsNotNone(step, "crayon-review has no step 6")
        assert_contains(self, step, "is not a verdict", "crayon-review step 6")
        assert_contains(self, step, "is not a go", "crayon-review step 6")

    def test_s16_the_lean_waits_for_the_verdict(self):
        assert_contains(self, self.body, KEEP_VERDICT, "crayon-review")
        assert_contains(self, self.body, LEAN_HELD, "crayon-review")
        assert_contains(
            self, self.body, "Record mode has no findings and no lean.", "crayon-review"
        )
        assert_omits(
            self,
            self.body,
            "The recommendation is a default, never a decision.",
            "crayon-review",
        )

    def test_s16_the_rubric_layout_ends_on_the_verdict_question(self):
        rubric = REVIEW_RUBRIC.read_text(encoding="utf-8")
        assert_contains(
            self, rubric.splitlines()[0], "workflow step 5", "the rubric's load line"
        )
        assert_contains(self, rubric, VERDICT_QUESTION, "review-rubric.md")
        assert_contains(self, rubric, LEAN_HELD, "review-rubric.md")
        for stale in ("Recommended verdict:", "publishing commit"):
            with self.subTest(stale=stale):
                assert_omits(self, rubric, stale, "review-rubric.md")

    def test_s16_cited_finding_numbers_are_restated_with_the_author(self):
        step = skill_step_body(self.body, 6)
        self.assertIsNotNone(step, "crayon-review has no step 6")
        assert_contains(self, step, NUMBERS_DO_NOT_TRAVEL, "crayon-review step 6")
        rubric = REVIEW_RUBRIC.read_text(encoding="utf-8")
        assert_omits(self, rubric, "the verdict note can say", "review-rubric.md")

    def test_s16_the_hook_note_is_the_authors_words(self):
        assert_contains(self, self.body, HOOK_NOTE, "crayon-review")
        # WR-08: the re-ask is bounded and has an exit.
        for literal in ("ask once more, naming only that one fact",
                        "never ask a third time"):
            with self.subTest(literal=literal):
                assert_contains(self, folded(self.body), literal, "crayon-review")
        for stale in (
            "say so in the note and name the hook",
            "Adopt the bytes with a note naming the hook",
        ):
            with self.subTest(stale=stale):
                assert_omits(self, self.body, stale, "crayon-review")

    def test_s16_the_lists_name_the_verdict_rules(self):
        for tag, literal in (
            ("must", VERDICT_QUESTION),
            ("must_not", KEEP_VERDICT),
            ("success_criteria", "recorded verbatim"),
        ):
            section = tagged_section(self.body, tag)
            with self.subTest(section=tag):
                self.assertIsNotNone(section, "crayon-review has no <%s>" % tag)
                assert_contains(self, section, literal, "crayon-review <%s>" % tag)

    def test_s16_the_routing_rows_leave_an_accepts_note_optional(self):
        for signal, block in (
            ("unapplied_steering", "reasons"),
            ("bad_resolution", "reasons"),
            ("review", "tokens"),
        ):
            verb = row_cells(routing_row(signal, block))[-1]
            with self.subTest(signal=signal):
                assert_contains(
                    self, verb, '--verdict accept [--note "…"]', "the %s row" % signal
                )
                assert_omits(
                    self, verb, '--verdict accept --note "…"', "the %s row" % signal
                )


#: CLOSE-02, D-05: onboarding ends on one question about the author's priorities.
PRIORITIES_QUESTION = "Which three gaps would your readers miss first?"

#: The route line once the author answers: their first pick, in their own words.
PICKED_ROUTE = "Next: /crayon-plan — start with"

#: WR-03: the priorities question follows the gap count, so it never asks for
#: three picks from fewer gaps, or for gaps the walk did not find.
FEW_GAPS_QUESTION = "Which of these would your readers miss first?"
NO_GAPS_QUESTION = "What would your readers miss most?"

#: WR-01: the priorities question is a judgment question the author rules do not
#: reach, so its step states the no-marker rule itself.
PRIORITIES_UNMARKED = "no gap is marked as recommended"

#: The route line onboarding used to end on, choosing the next move for the author.
GROUNDS_ROUTE = "the context now grounds unit declarations"


class TestS17TheClosure(unittest.TestCase):
    """S-17 — after an accept the author is asked, never offered a next step (CLOSE-01)."""

    #: Whole words, matched case-insensitively: none may describe what follows
    #: an accept, because what follows is the author's.
    NEXT_STEP_WORDS = ("publish", "PR", "pull request", "build")

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-review")

    def test_s17_an_accept_closes_on_what_the_record_holds_open(self):
        step = skill_step_body(self.body, 6)
        self.assertIsNotNone(step, "crayon-review has no step 6")
        for literal in (
            AT_MOST_THREE,
            CLOSURE_ORDER,
            "handover.steps",
            "handover.judged",
            "in this same conversation",
            "Nits never count.",
            "plain text, not options in a question tool",
            "Author decisions",
            'crayon summary "$UNIT_ID" --md',
            'crayon steer "$UNIT_ID" --note',
        ):
            with self.subTest(literal=literal):
                assert_contains(self, step, literal, "crayon-review step 6")
        # WR-04: a toctree entry or a role resolves relative to the page holding it.
        for literal in ("relative to the page that holds them",
                        "only when it resolves to the accepted page"):
            with self.subTest(literal=literal):
                assert_contains(self, folded(step), literal, "crayon-review step 6")

    def test_s17_no_publishing_step_follows_an_accept(self):
        assert_omits(self, self.body, "the publishing commit is yours", "crayon-review")

    def test_s17_an_already_accepted_unit_closes_without_the_findings_source(self):
        section = tagged_section(self.body, "edge_cases")
        self.assertIsNotNone(section, "crayon-review has no <edge_cases>")
        for literal in ("already accepted", "without the findings source"):
            with self.subTest(literal=literal):
                assert_contains(self, section, literal, "crayon-review <edge_cases>")

    def test_s17_the_quick_start_closes_an_accept(self):
        section = tagged_section(self.body, "quick_start")
        self.assertIsNotNone(section, "crayon-review has no <quick_start>")
        match = re.search(r"^6\. .*(?:\n   .*)*", section, re.MULTILINE)
        self.assertIsNotNone(match, "crayon-review <quick_start> has no item 6")
        item = " ".join(line.strip() for line in match.group(0).splitlines())
        assert_contains(self, item, AT_MOST_THREE, "crayon-review <quick_start> item 6")

    def test_s17_the_lists_name_the_closure(self):
        for tag, literal in (
            ("pipeline", AT_MOST_THREE),
            ("must", AT_MOST_THREE),
            ("must_not", "Never offer publishing, a pull request or a build"),
            ("success_criteria", "drawn from the record"),
        ):
            section = tagged_section(self.body, tag)
            with self.subTest(section=tag):
                self.assertIsNotNone(section, "crayon-review has no <%s>" % tag)
                assert_contains(self, section, literal, "crayon-review <%s>" % tag)

    def test_s17_onboarding_ends_on_the_authors_priorities(self):
        # WR-02: both context skills record the same artefacts and close the
        # same way, so neither picks the author's first unit.
        for name in CONTEXT_SKILLS:
            body = body_of(SKILLS_ROOT / name)
            step = skill_step_body(body, 6)
            with self.subTest(skill=name):
                self.assertIsNotNone(step, "%s has no step 6" % name)
                for literal in (PRIORITIES_QUESTION, PICKED_ROUTE, "never pick one for them",
                                "Nothing is recorded from the answer", PRIORITIES_UNMARKED,
                                FEW_GAPS_QUESTION, NO_GAPS_QUESTION,
                                "Only their first pick is used."):
                    assert_contains(self, folded(step), literal, "%s step 6" % name)
                self.assertEqual(
                    body.count(PRIORITIES_QUESTION), 1,
                    "%s must state %r exactly once" % (name, PRIORITIES_QUESTION),
                )
                assert_omits(self, folded(body), GROUNDS_ROUTE, name)
        onboard = body_of(SKILLS_ROOT / "crayon-onboard")
        record = skill_step_body(onboard, 5)
        self.assertIsNotNone(record, "crayon-onboard has no step 5")
        assert_contains(self, record, '--note "<one line: the scope walked and the gap count>"',
                        "crayon-onboard step 5")

    def test_s17_onboardings_lists_leave_the_priorities_to_the_author(self):
        for name in CONTEXT_SKILLS:
            body = body_of(SKILLS_ROOT / name)
            for tag, literal in (
                ("must", "priorities question"),
                ("must_not", "Never choose the author's priorities or first unit for them"),
                ("success_criteria", "priorities question"),
            ):
                section = tagged_section(body, tag)
                with self.subTest(skill=name, section=tag):
                    self.assertIsNotNone(section, "%s has no <%s>" % (name, tag))
                    assert_contains(self, folded(section), literal,
                                    "%s <%s>" % (name, tag))

    def test_s17_the_publish_row_offers_no_next_step(self):
        cells = row_cells(routing_row("publish", "tokens"))
        self.assertEqual(cells[0], "`publish`", "the `publish` token must not change")
        description = cells[1]
        assert_contains(self, description, "crayon stops here", "the publish row")
        for word in self.NEXT_STEP_WORDS:
            with self.subTest(word=word):
                self.assertIsNone(
                    re.search(r"(?i)\b%s\b" % re.escape(word), description),
                    "the publish row's description offers %r as a next step: %r"
                    % (word, description),
                )

    def test_review_step_1_lets_a_pending_request_be_settled_at_the_verdict(self):
        """21 IN-09: a request pending on a generation routes `draft`, yet that
        generation can be reviewed and the request settled at the accept."""
        step = skill_step_body(self.body, 1)
        self.assertIsNotNone(step, "crayon-review has no step 1")
        for literal in ("route the TA to crayon-write",
                        "unless the draft is owed only to a request pending on a generation",
                        "resolving or withdrawing it at the accept",
                        "`unapplied_steering`"):
            with self.subTest(literal=literal):
                assert_contains(self, folded(step), literal, "crayon-review step 1")

    def test_the_closure_runs_only_on_a_publish_route(self):
        """21 IN-10: an accept that routes anywhere but `publish` (a hook that
        rewrote a page routes `record_edits`) follows its row, not the closure;
        on an accepted unit the questions are what the record still shows open."""
        step = skill_step_body(self.body, 6)
        self.assertIsNotNone(step, "crayon-review has no step 6")
        assert_contains(self, folded(step),
                        "The closure runs only when the accept's emitted `next` is "
                        "`publish`; for any other `next`, follow its routing row.",
                        "crayon-review step 6")
        section = tagged_section(self.body, "edge_cases")
        self.assertIsNotNone(section, "crayon-review has no <edge_cases>")
        entry = labelled_entry(section, "The unit is already accepted")
        self.assertIsNotNone(entry, "crayon-review has no already-accepted edge case")
        for literal in ("the questions the record still shows open",
                        "ends the closure with nothing recorded"):
            with self.subTest(literal=literal):
                assert_contains(self, folded(entry), literal,
                                "crayon-review's already-accepted edge case")


PLAN_SKILL = SKILLS_ROOT / "crayon-plan"
SOCRATIC_REFERENCE = PLAN_SKILL / "references" / "socratic-technique.md"
REFERENCE_INTAKE = PLAN_SKILL / "references" / "reference-intake.md"
EXPLANATION_INTAKE = PLAN_SKILL / "references" / "explanation-intake.md"

#: D-12, D-13: wording that had the plan skill propose an audience or a direction
#: unasked. Each is checked with its whitespace folded, so a rewrap cannot hide it.
UNASKED_PROPOSALS = (
    (PLAN_SKILL / "SKILL.md", "evidence-grounded recommendation"),
    (PLAN_SKILL / "SKILL.md", "propose one only when the TA supplied none"),
    (SOCRATIC_REFERENCE, "Recommend when it helps, not before"),
    (SOCRATIC_REFERENCE, "Still vague → one recommendation"),
    (REFERENCE_INTAKE, "propose one only when the TA supplied"),
    (EXPLANATION_INTAKE, "offer **one** grounded"),
)


def folded(text):
    """``text`` with every run of whitespace folded to one space."""
    return " ".join(text.split())


def labelled_entry(text, label):
    """The entry that opens ``**<label>``, up to the next blank line or bullet.

    An edge case in a SKILL.md and a handling script in a reference both open on
    a bold label; the entry runs until a blank line or the next ``- **`` bullet,
    whichever comes first. ``None`` when no entry carries the label.
    """
    start = text.find("**%s" % label)
    if start < 0:
        return None
    rest = text[start:]
    ends = [i for i in (rest.find("\n\n"), rest.find("\n- **")) if i >= 0]
    return rest[: min(ends)] if ends else rest


class TestS18TheIntake(unittest.TestCase):
    """S-18 — the intake is the author's: two open questions always, a view only when asked, notes in their words (JUDG-04, D-08, D-12, D-16)."""

    def setUp(self):
        self.body = body_of(PLAN_SKILL)
        self.socratic = SOCRATIC_REFERENCE.read_text(encoding="utf-8")

    def test_the_origin_reason_is_true(self):
        """21 IN-07: no skill tells the review skill to read a request's origin;
        `--origin plan` matters because `crayon summary` lists the request under
        "Author decisions" as from the plan rather than as steering."""
        text = folded(self.socratic)
        assert_omits(self, text, "the review skill is told to read", "socratic-technique.md")
        assert_contains(self, text, "--origin plan", "socratic-technique.md")
        assert_contains(self, text, "Author decisions", "socratic-technique.md")

    def test_s18_every_intake_asks_one_of_two_fixed_questions(self):
        step = skill_step_body(self.body, 2)
        self.assertIsNotNone(step, "crayon-plan has no step 2")
        for literal in (TWO_OPEN_QUESTIONS, ARRIVAL_QUESTION, NEXT_QUESTION,
                        LEAVE_OUT_QUESTION):
            with self.subTest(literal=literal):
                assert_contains(self, step, literal, "crayon-plan step 2")
                self.assertEqual(
                    self.body.count(literal), 1,
                    "crayon-plan must state %r exactly once" % literal,
                )

    def test_s18_the_jump_ahead_entries_keep_one_question_always_open(self):
        edge = tagged_section(self.body, "edge_cases")
        self.assertIsNotNone(edge, "crayon-plan has no <edge_cases>")
        for what, text in (
            ("crayon-plan <edge_cases>", edge),
            ("socratic-technique.md", self.socratic),
        ):
            entry = labelled_entry(text, "Jump-ahead TA")
            with self.subTest(file=what):
                self.assertIsNotNone(entry, "%s has no Jump-ahead TA entry" % what)
                assert_contains(self, entry, "always open", "%s Jump-ahead TA" % what)

    def test_s18_the_lists_name_the_open_question(self):
        for tag in ("must", "success_criteria"):
            section = tagged_section(self.body, tag)
            with self.subTest(section=tag):
                self.assertIsNotNone(section, "crayon-plan has no <%s>" % tag)
                assert_contains(
                    self, " ".join(section.split()), "at least two open questions",
                    "crayon-plan <%s>" % tag,
                )

    def test_s18_no_audience_or_direction_is_proposed_unasked(self):
        for path, phrase in UNASKED_PROPOSALS:
            what = str(path.relative_to(ROOT))
            with self.subTest(file=what, phrase=phrase):
                assert_omits(self, folded(path.read_text(encoding="utf-8")), phrase, what)

    def test_s18_a_view_is_given_only_when_asked(self):
        for number in (2, 4):
            step = skill_step_body(self.body, number)
            with self.subTest(step=number):
                self.assertIsNotNone(step, "crayon-plan has no step %d" % number)
                assert_contains(self, folded(step), VIEW_ON_REQUEST,
                                "crayon-plan step %d" % number)
        self.assertGreaterEqual(
            folded(self.body).count(VIEW_ON_REQUEST), 2,
            "crayon-plan must say %r in step 2 and in step 4" % VIEW_ON_REQUEST,
        )
        assert_contains(self, self.socratic, "## Your view on judgment questions",
                        "socratic-technique.md")
        assert_contains(self, folded(self.socratic), "only when asked",
                        "socratic-technique.md")
        vague = labelled_entry(tagged_section(self.body, "edge_cases") or "", "Vague answer")
        self.assertIsNotNone(vague, "crayon-plan <edge_cases> has no Vague answer entry")
        assert_contains(self, folded(vague), "a narrower probe, not a proposal",
                        "crayon-plan <edge_cases> Vague answer")

    def test_s18_a_vague_answer_has_one_terminal_move(self):
        vague = labelled_entry(tagged_section(self.body, "edge_cases") or "", "Vague answer")
        self.assertIsNotNone(vague, "crayon-plan <edge_cases> has no Vague answer entry")
        for what, text in (
            ("crayon-plan <edge_cases> Vague answer", vague),
            ("socratic-technique.md", self.socratic),
            ("explanation-intake.md", EXPLANATION_INTAKE.read_text(encoding="utf-8")),
        ):
            with self.subTest(file=what):
                assert_contains(self, folded(text), PROBES_RUN_OUT, what)
                assert_omits(self, folded(text), "keep narrowing", what)
                assert_omits(self, folded(text), "third open probe", what)

    def test_s18_notes_are_the_tas_words_and_the_go_is_explicit(self):
        step = skill_step_body(self.body, 6)
        self.assertIsNotNone(step, "crayon-plan has no step 6")
        for literal in (NOTES_ARE_THEIRS, "is not a go"):
            with self.subTest(literal=literal):
                assert_contains(self, folded(step), literal, "crayon-plan step 6")

    def test_s18_no_reference_describes_a_synthesized_note(self):
        explanation = EXPLANATION_INTAKE.read_text(encoding="utf-8")
        for what, text, phrase in (
            ("socratic-technique.md", self.socratic, "synthesized steering note"),
            ("explanation-intake.md", explanation, "synthesized steering note"),
            ("explanation-intake.md", explanation, "One synthesized intent note"),
        ):
            with self.subTest(file=what, phrase=phrase):
                assert_omits(self, folded(text), phrase, what)
        assert_contains(self, folded(self.socratic), NOTES_ARE_THEIRS,
                        "socratic-technique.md")
        assert_contains(self, folded(explanation), NOTES_ARE_THEIRS,
                        "explanation-intake.md")


#: D-06, D-13, P-07: the writer's judgment step choices are named as the author's.
STEP_CHOICES = "step choices, and they are the author's judgment"

#: D-06: the reason for a re-plan is the author's answer to the `--keep-evidence`
#: question, verbatim, never a reason the skill composes.
VERBATIM_KEEP_NOTE = "Their answer, verbatim, is the note."

#: The placeholder that invited the skill to compose the re-plan reason itself.
COMPOSED_REASON = "<why the plan changed>"


def sentence_with(text, needle):
    """The sentence of ``text`` (whitespace folded) that carries ``needle``, or ``None``."""
    for sentence in re.split(r"(?<=[.!?])\s+", folded(text)):
        if needle in sentence:
            return sentence
    return None


class TestS19TheWriter(unittest.TestCase):
    """S-19 — the writer's notes are the author's words and its step choices are unmarked (D-06, D-13)."""

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-write")
        self.walk = WALK_PROTOCOL.read_text(encoding="utf-8")

    def test_s19_the_keep_evidence_note_is_the_authors_answer(self):
        assert_contains(self, self.body, KEEP_EVIDENCE_QUESTION, "crayon-write")
        assert_contains(self, folded(self.body), VERBATIM_KEEP_NOTE, "crayon-write")
        for what, text in (("crayon-write", self.body), ("walk-protocol.md", self.walk)):
            with self.subTest(file=what):
                assert_omits(self, text, COMPOSED_REASON, what)
        assert_contains(self, folded(self.walk), "the author's answer, verbatim",
                        "walk-protocol.md")

    def test_s19_the_step_choices_are_the_authors_and_unmarked(self):
        text = folded(self.body)
        self.assertEqual(
            text.count(STEP_CHOICES), 1,
            "crayon-write must state %r exactly once" % STEP_CHOICES,
        )
        paragraph = text[text.find(STEP_CHOICES):].split("**", 1)[0]
        for literal in ("permission gate", "--keep-evidence", "failed step",
                        "genuine fork", "no option marked", "mechanical"):
            with self.subTest(literal=literal):
                assert_contains(self, paragraph, literal,
                                "crayon-write's step-choices paragraph")

    def test_s19_resume_is_a_mechanical_default(self):
        sentence = sentence_with(self.walk, "resume as the **default**")
        self.assertIsNotNone(sentence, "walk-protocol.md no longer offers resume as the default")
        assert_contains(self, sentence, "mechanical", "walk-protocol.md's resume sentence")

    def test_s19_the_lists_carry_the_verbatim_note(self):
        for tag in ("must", "success_criteria"):
            section = tagged_section(self.body, tag)
            with self.subTest(section=tag):
                self.assertIsNotNone(section, "crayon-write has no <%s>" % tag)
                assert_contains(self, folded(section), "the author's answer, verbatim",
                                "crayon-write <%s>" % tag)


#: D-02, P-22-01: a no-op refusal (`identical_draft`, `already_*`) names the
#: commit its payload carries and no record number; the seq stays in `--json`.
NO_RECORD_NUMBER = "naming no record number"

#: D-02, D-03: a pending request is read out by the number the author can say
#: back; `--resolves` and `--withdraw <seq>` stay exact in the verb cell.
REQUEST_N = 'as "request <n>"'

#: D-03, D-07: the rows whose tool output is shown verbatim, so it goes in a
#: code block and the always-on plain-words check reads it as code.
VERBATIM_REASONS = (
    "bad_write_path",
    "legacy_unit",
    "ledger_corrupt",
    "ledger_diverged",
    "resume_ambiguous",
    "recovery_unsupported",
    "internal_error",
)

#: D-02, P-22-01: a no-op names the commit its refusal payload carries, at the
#: body and reference sites as in the routing rows.
GIVE_THE_COMMIT = "give the commit from the payload"

#: D-02: the plan-stale qualifier read out as what happened, not as its token.
PLAN_EDITED = "the plan was edited after it was signed"

#: D-02, RESEARCH Pitfall 7: the `--json` provenance and qualifier keep counts and
#: seqs for a command line; what the reviewer hears is the human line.
NEVER_READ_OUT = "never read out"

#: The vacuous-pass floor for the whole-tree scan: five SKILL.md bodies, the
#: README and 26 references.
MIN_SKILL_MARKDOWN = 30

PROVENANCE_REFERENCE = SKILLS_ROOT / "crayon-review" / "references" / "provenance-summary.md"

#: WR-03 (22-14): the fetch reference a model reads a source's revision from.
SOURCE_CONTRACT = SKILLS_ROOT / "crayon-fetch" / "references" / "source-contract.md"

#: The no-op rows, each of whose payloads carries `seq` and `commit`.
NO_OP_REASONS = (
    "identical_draft",
    "already_signed",
    "already_accepted",
    "already_recorded",
    "already_retired",
)


class TestS20PlainWords(unittest.TestCase):
    """S-20 — what the author reads is in plain words (VOICE-03, D-01 to D-04, D-07)."""

    #: Typed on purpose, as in S-15: read back from the README, the non-vacuity
    #: check would pass over whatever the block happens to say.
    LITERALS = (
        "**Accepted, the pages as accepted, request N.**",
        "**No hashes, digests or verify counts.**",
        "**The success line, verbatim.**",
        "**Refusals in plain words, commands exact.**",
        "the pages as accepted",
        "plan_hash",
        "--json",
        "code span",
        "fenced code block",
        # WR-06, IN-05, WR-04 (22-09): the tallies are quoted, the idiom is out,
        # and the block names every form grade.LEDGER_WORDS_RE reads.
        "not even as an English idiom",
        "walk tally and the findings tally",
        "seq 7",
        "sha256",
        "event 7",
        "ledger line 7",
        # WR-03 (22-14): a commit is named by its id, which the no-op rows ask
        # for, and the hashes the rule bans are a file's or the record's.
        "name a commit by its id, never as a hash",
        "a file or record hash",
    )

    #: Where the block binds: the line it follows in each skill.
    ANCHORS = dict(
        [(name, b"<!-- author-rules:end -->") for name in RULE_SKILLS]
        + [(name, b"</opening>") for name in CONTEXT_SKILLS]
    )

    def test_s20_each_skill_carries_the_block_byte_for_byte(self):
        block = plain_words_bytes()
        self.assertEqual(len(PLAIN_SKILLS), 5, "the block binds all five skills")
        for name in PLAIN_SKILLS:
            text = (SKILLS_ROOT / name / "SKILL.md").read_bytes()
            with self.subTest(skill=name):
                self.assertTrue(
                    carries_block_once(text, block),
                    "%s/SKILL.md does not carry the plain-words block of %s "
                    "exactly once; re-copy the bytes from the begin sentinel "
                    "through the end sentinel rather than hand-editing the copy"
                    % (name, README),
                )
                self.assertEqual(
                    sum(1 for line in text.split(b"\n") if _PLAIN_BEGIN in line),
                    1,
                    "%s/SKILL.md carries more than one plain-words block" % name,
                )

    def test_s20_the_block_sits_where_it_binds(self):
        for name in PLAIN_SKILLS:
            text = (SKILLS_ROOT / name / "SKILL.md").read_bytes()
            anchor = self.ANCHORS[name]
            with self.subTest(skill=name):
                self.assertEqual(text.count(anchor), 1, "%s has no single %r" % (name, anchor))
                self.assertTrue(_PLAIN_BEGIN in text, "%s has no plain-words block" % name)
                after = text.index(anchor) + len(anchor)
                begin = text.rfind(b"\n", 0, text.index(_PLAIN_BEGIN)) + 1
                self.assertGreaterEqual(begin, after, "%s: the block precedes %r" % (name, anchor))
                self.assertEqual(
                    text[after:begin].strip(),
                    b"",
                    "%s: the plain-words block must follow %r directly" % (name, anchor),
                )

    def test_s20_the_block_is_not_vacuous(self):
        text = plain_words_bytes().decode("utf-8")
        for literal in self.LITERALS:
            with self.subTest(literal=literal):
                assert_contains(self, text, literal, "the plain-words block")

    def test_s20_the_block_allows_a_commit_id(self):
        # WR-03 (22-14): "or any other hash" banned the commit id that every
        # no-op row asks the model to give, so the rule contradicted the rows.
        text = folded(plain_words_bytes().decode("utf-8"))
        assert_omits(self, text, "any other hash", "the plain-words block")

    def test_s20_the_relayed_references_name_no_hash(self):
        # WR-03 (22-14): a model explains the record and a source's revision from
        # these two references, and the always-on check fails "hash" in prose.
        provenance = folded(PROVENANCE_REFERENCE.read_text(encoding="utf-8"))
        assert_contains(self, provenance, "append-only and chained", "provenance-summary.md")
        assert_omits(self, provenance, "hash-chained", "provenance-summary.md")
        # 22 IN-04 (24 D-13): `page: current` compares bytes, in the plain words
        # the reviewer relays, never "the recorded digest".
        assert_contains(self, provenance, "the bytes crayon recorded", "provenance-summary.md")
        assert_omits(self, provenance, "recorded digest", "provenance-summary.md")
        source = folded(SOURCE_CONTRACT.read_text(encoding="utf-8"))
        assert_contains(self, source, "Git commit id", "source-contract.md")
        assert_omits(self, source, "commit hash", "source-contract.md")

    def test_s20_the_headline_forbids_no_tally(self):
        # WR-06: a bold headline that bans counts outright contradicts the walk
        # and findings tallies the skills require the model to quote.
        text = plain_words_bytes().decode("utf-8")
        self.assertIsNone(
            re.search(r"\*\*[^*\n]*or counts\.\*\*", text),
            "the plain-words block has a bold headline banning counts outright; "
            "it bans verify counts only, and the tallies are quoted",
        )

    def test_s20_the_block_names_no_tool_and_no_verb(self):
        text = plain_words_bytes().decode("utf-8")
        for absent in ("AskUserQuestion", "author-rules", "[[", "]("):
            with self.subTest(absent=absent):
                assert_omits(self, text, absent, "the plain-words block")
        self.assertIsNone(
            re.search(r"crayon [a-z]", text),
            "the plain-words block carries a `crayon <verb>`; the rule is about words",
        )
        tools = set()
        for skill_dir in skill_dirs():
            tools.update(tool_list(frontmatter_of(skill_dir)))
        self.assertTrue(tools, "no allowed-tools read: the scan would be vacuous")
        for tool in sorted(tools):
            with self.subTest(tool=tool):
                assert_omits(self, text, "`%s`" % tool, "the plain-words block")

    def test_s20_a_one_byte_drift_is_detected(self):
        # The negative keystone: a copy that differs by one byte must fail the
        # same check the positive gate runs.
        block = plain_words_bytes()
        text = (SKILLS_ROOT / "crayon-onboard" / "SKILL.md").read_bytes()
        self.assertTrue(carries_block_once(text, block))
        start = text.index(block) + len(block) // 2
        flipped = b"X" if text[start:start + 1] != b"X" else b"Y"
        drifted = text[:start] + flipped + text[start + 1:]
        self.assertFalse(carries_block_once(drifted, block))

    def test_s20_pending_requests_are_put_as_requests(self):
        step = skill_step_body(body_of(SKILLS_ROOT / "crayon-review"), 6)
        self.assertIsNotNone(step, "crayon-review has no step 6")
        assert_contains(self, folded(step), PENDING_AS_REQUESTS, "crayon-review step 6")
        assert_omits(self, folded(step), "put each seq to the reviewer", "crayon-review step 6")

    def test_s20_the_no_op_rows_name_no_record_number(self):
        for reason in NO_OP_REASONS:
            cell = row_cells(routing_row(reason))[1]
            with self.subTest(reason=reason):
                assert_contains(self, cell, NO_RECORD_NUMBER, "the %s row" % reason)
                assert_contains(self, cell, "commit", "the %s row" % reason)
                assert_omits(self, folded(cell).lower(), "existing seq", "the %s row" % reason)

    def test_s20_no_routing_row_says_a_record_word(self):
        # WR-03 (22-14): a model relays the "what the skill does" cell, and the
        # always-on check fails a reply carrying any word grade.LEDGER_WORDS_RE
        # reads. Every row, reasons and next tokens alike, read outside its code
        # spans, through the grader's own regex, so a later row cannot bring a
        # record word back. This supersedes the basis-only scan (IN-03, 22-09).
        text = routing_block_bytes().decode("utf-8")
        rows = [ln for ln in text.splitlines() if ln.startswith("| `")]
        self.assertGreaterEqual(
            len(rows), 50, "the routing scan read %d row(s); it would pass over nothing" % len(rows))
        for row in rows:
            signal = row.split("`")[1]
            match = record_word_outside_code(row_cells(row)[1])
            with self.subTest(signal=signal):
                self.assertIsNone(
                    match,
                    "the %s row tells the model %r, a record word the plain_words check "
                    "fails; say it plainly, or keep it inside a code span"
                    % (signal, match.group(0) if match else None),
                )

    def test_s20_the_row_scan_reads_prose_not_code(self):
        # The scan's own keystone: a record word in prose is flagged, the same
        # word inside a code span is quoted output, and plain words pass.
        match = record_word_outside_code("record the evidence the tool hashes")
        self.assertIsNotNone(match, "the row scan missed a record word in prose")
        self.assertEqual(match.group(0), "hashes")
        self.assertIsNone(record_word_outside_code("pass `--steps-seq N`"),
                          "the row scan read a flag inside a code span as prose")
        self.assertIsNone(record_word_outside_code("the pages as accepted"),
                          "the row scan flagged the plain words the rule asks for")

    def test_s20_the_adoption_rows_speak_plainly(self):
        # IN-03: the two rows the review named take its words exactly.
        for reason, literal in (("target_exists", "adopt the file as the page on record"),
                                ("target_missing", "an accepted page is absent")):
            with self.subTest(reason=reason):
                assert_contains(self, row_cells(routing_row(reason))[1], literal,
                                "the %s row" % reason)

    def test_s20_the_request_rows_speak_of_requests(self):
        for reason in ("unapplied_steering", "bad_resolution"):
            cells = row_cells(routing_row(reason))
            with self.subTest(reason=reason):
                assert_contains(self, cells[1], REQUEST_N, "the %s row" % reason)
                assert_omits(self, cells[1], "seqs", "the %s row" % reason)
                assert_contains(self, cells[-1], "--resolves", "the %s verb" % reason)
                assert_contains(self, cells[-1], "--withdraw <seq>", "the %s verb" % reason)

    def test_s20_verbatim_rows_say_code_block(self):
        self.assertEqual(len(VERBATIM_REASONS), 7)
        for reason in VERBATIM_REASONS:
            cell = row_cells(routing_row(reason))[1]
            with self.subTest(reason=reason):
                assert_contains(self, cell, "verbatim", "the %s row" % reason)
                assert_contains(self, cell, "code block", "the %s row" % reason)

    def test_s20_no_skill_file_asks_for_a_record_number(self):
        files = sorted(SKILLS_ROOT.rglob("*.md"))
        self.assertGreaterEqual(
            len(files), MIN_SKILL_MARKDOWN,
            "the skills/ scan read %d file(s); it would pass over nothing" % len(files),
        )
        for path in files:
            with self.subTest(path=str(path.relative_to(ROOT))):
                assert_omits(self, folded(path.read_text(encoding="utf-8")).lower(),
                             "existing seq", str(path.relative_to(ROOT)))

    def test_s20_a_no_op_gives_the_commit(self):
        review = body_of(SKILLS_ROOT / "crayon-review")
        plan = body_of(SKILLS_ROOT / "crayon-plan")
        write = body_of(SKILLS_ROOT / "crayon-write")
        sites = {
            "crayon-review <edge_cases> already_accepted": labelled_entry(
                tagged_section(review, "edge_cases") or "", "`already_accepted`"),
            "crayon-plan <edge_cases> already_signed": labelled_entry(
                tagged_section(plan, "edge_cases") or "", "`already_signed`"),
            "crayon-write step 5": skill_step_body(write, 5),
            "walk-protocol.md": WALK_PROTOCOL.read_text(encoding="utf-8"),
        }
        for what, text in sites.items():
            with self.subTest(site=what):
                self.assertIsNotNone(text, "%s is missing" % what)
                assert_contains(self, folded(text), GIVE_THE_COMMIT, what)

    def test_s20_write_echoes_the_response_line_after_the_git_line(self):
        # IN-02 (22-09): the tool prints its git line, then the response line;
        # the report echoes the response line, never a claim of a single line.
        write = body_of(SKILLS_ROOT / "crayon-write")
        step = skill_step_body(write, 5)
        self.assertIsNotNone(step, "crayon-write has no step 5")
        for literal in ("`git: committed", "Echo the response line verbatim"):
            with self.subTest(literal=literal):
                assert_contains(self, folded(step), literal, "crayon-write step 5")
        assert_omits(self, folded(write), "The response is one line", "crayon-write")
        report = skill_step_body(write, 6)
        self.assertIsNotNone(report, "crayon-write has no step 6")
        assert_contains(self, report, "- Recorded: <the response line, verbatim>",
                        "crayon-write step 6's template")

    def test_s20_the_plan_stale_qualifier_is_read_out_plainly(self):
        step = skill_step_body(body_of(SKILLS_ROOT / "crayon-review"), 3)
        self.assertIsNotNone(step, "crayon-review has no step 3")
        assert_contains(self, folded(step), PLAN_EDITED, "crayon-review step 3")
        assert_omits(self, step, "**`plan_stale`**", "crayon-review step 3")

    def test_s20_verbatim_output_goes_in_a_code_block(self):
        review = body_of(SKILLS_ROOT / "crayon-review")
        plan = body_of(SKILLS_ROOT / "crayon-plan")
        for what, step in (("crayon-review step 9", skill_step_body(review, 9)),
                           ("crayon-review step 10", skill_step_body(review, 10)),
                           ("crayon-plan step 8", skill_step_body(plan, 8))):
            with self.subTest(step=what):
                self.assertIsNotNone(step, "%s is missing" % what)
                assert_contains(self, folded(step), "in a code block", what)
        assert_contains(self, review, RECOVERY_UNSUPPORTED_SENTENCE, "crayon-review")

    def test_s20_the_provenance_reference_presents_the_human_lines(self):
        text = folded(PROVENANCE_REFERENCE.read_text(encoding="utf-8"))
        for literal in ("record: intact at", "accepted in",
                        "plan amended since the draft", '"request <n>"', NEVER_READ_OUT):
            with self.subTest(literal=literal):
                assert_contains(self, text, literal, "provenance-summary.md")


#: D-12, D-13: each deviated or skipped step is put to the author as a question
#: about the page, in the closure's own words.
STEP_QUESTION = "Does the page need to say so?"

#: D-14: an answer to a step question becomes nothing on the record; only the
#: verdict answer is a note.
STEP_ANSWER_RECORDS_NOTHING = "no steer and no note"

#: D-15 (amended, CR-01; WR-04): the closure after an accept does not ask a step
#: again that review already put to the author in this conversation, unless its
#: answer asked for a page change; a later session asks every step again.
STEPS_ASKED_ONCE = ("except a step this conversation already put to the author in step 3a, "
                    "unless its answer asked for a page change")

#: WR-04, D-15 amended: an unanswered step counts as asking for no page change,
#: so the closure does not ask it again; said in step 3a and in step 6 item 1.
STEP_LEFT_UNANSWERED = "a step left unanswered is not asked again"

#: CR-01: the clause D-15 used to carry, which skipped a step whatever its answer.
STEPS_SKIPPED_WHATEVER_THE_ANSWER = "answered or not"

#: CR-01, D-14 unchanged: a step answer that asks for a page change is told at
#: once that it is not on the record yet.
STEP_CHANGE_NOTICE = "say in one line that it is not recorded until the verdict"

#: CR-01: the notice names how the change reaches the record.
FIX_OR_REDRAFT_RECORDS = "a fix or redraft verdict with those words records it"

#: CR-01, D-15 amended: a step whose answer asked for a page change is open at
#: the closure, and its question names the change.
CHANGE_REQUEST_REOPENS = "A step whose answer asked for a page change"

#: WR-05, D-12 amended: a pre-authorised accept runs in the same turn, so no
#: step is put to the author in step 3a and the closure asks them all.
PREAUTHORISED_SKIPS_3A = "When the reviewer already authorised the accept, step 3a is skipped"

#: WR-05: the exception, as the lists carry it.
UNLESS_PREAUTHORISED = "unless the reviewer already authorised the accept"


#: D-10: an empty ``gaps`` list in the writer's report adds nothing to the report.
EMPTY_GAPS_ADD_NOTHING = "With an empty `gaps` list the report adds nothing"

#: D-10: the rubric's old opening, which admitted only verified findings.
ONLY_VERIFIED = "Only verified findings reach the report"

#: D-09: the one first-person line review mode puts directly before the
#: findings when this conversation or the record grounds a self-review.
SELF_REVIEW_LINE = ("I drafted this page, so this is a self-review; I'm likely to miss what I "
                    "got wrong the first time. Weigh these findings with that in mind.")


def step_3a_body(text):
    """The body of ``<step_3a …>``, or ``None`` when the skill has no such step."""
    match = re.search(r"<step_3a\b[^>]*>(.*?)</step_3a>", text, re.DOTALL)
    return match.group(1) if match else None


def quick_start_item(text, number):
    """Quick-start item ``number`` with its continuation lines folded, or ``None``."""
    section = tagged_section(text, "quick_start")
    if section is None:
        return None
    match = re.search(r"^%d\. .*(?:\n   .*)*" % number, section, re.MULTILINE)
    return folded(match.group(0)) if match else None


class TestS23StepQuestions(unittest.TestCase):
    """S-23 — deviated and skipped steps reach the author as questions during review (CLOSE-03, D-12 to D-15)."""

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-review")

    def test_s23_step_3a_sits_between_steps_3_and_4(self):
        end_3 = self.body.find("</step_3>")
        open_3a = self.body.find("<step_3a ")
        close_3a = self.body.find("</step_3a>")
        open_4 = self.body.find("<step_4 ")
        for what, at in (("</step_3>", end_3), ("<step_3a ", open_3a),
                         ("</step_3a>", close_3a), ("<step_4 ", open_4)):
            with self.subTest(tag=what):
                self.assertGreaterEqual(at, 0, "crayon-review has no %s" % what)
        self.assertTrue(end_3 < open_3a < close_3a < open_4,
                        "crayon-review's <step_3a> must sit between </step_3> and <step_4")

    def test_s23_both_modes_ask_every_step_after_the_summary(self):
        step = step_3a_body(self.body)
        self.assertIsNotNone(step, "crayon-review has no <step_3a>")
        step = folded(step)
        for literal in (
            "Both modes.",
            "handover.steps",
            'crayon show "$UNIT_ID" --json',
            "one numbered list",
            "no cap",
            "in the order `handover.steps` lists them",
            STEP_QUESTION,
            STEP_ANSWER_RECORDS_NOTHING,
            STEP_CHANGE_NOTICE,
            FIX_OR_REDRAFT_RECORDS,
            PREAUTHORISED_SKIPS_3A,
            "the closure asks the steps instead",
            STEP_LEFT_UNANSWERED,
        ):
            with self.subTest(literal=literal):
                assert_contains(self, step, literal, "crayon-review <step_3a>")

    def test_s23_the_lists_name_the_step_questions(self):
        item = quick_start_item(self.body, 4)
        self.assertIsNotNone(item, "crayon-review <quick_start> has no item 4")
        # G-22-2, IN-03 (22-15): the skim-first site states the order B-63
        # checks and the pre-authorised exception B-77 checks.
        for literal in ("deviated or skipped step",
                        "before any finding and before the verdict question",
                        "already authorised the accept",
                        "the closure asks them instead"):
            with self.subTest(item=4, literal=literal):
                assert_contains(self, item, literal, "crayon-review <quick_start> item 4")
        item = quick_start_item(self.body, 6)
        self.assertIsNotNone(item, "crayon-review <quick_start> has no item 6")
        assert_contains(self, item, AT_MOST_THREE, "crayon-review <quick_start> item 6")
        for tag, literal in (
            ("must", "deviated or skipped step"),
            ("must", "not recorded until the verdict"),
            ("must", UNLESS_PREAUTHORISED),
            ("must_not", "from an answer to a step question"),
            ("must_not", "not recorded until the verdict"),
            ("success_criteria", "deviated or skipped step"),
            ("success_criteria", "not recorded until the verdict"),
            ("success_criteria", UNLESS_PREAUTHORISED),
        ):
            section = tagged_section(self.body, tag)
            with self.subTest(section=tag):
                self.assertIsNotNone(section, "crayon-review has no <%s>" % tag)
                assert_contains(self, folded(section), literal, "crayon-review <%s>" % tag)

    def test_s23_the_closure_does_not_ask_a_step_twice(self):
        step = skill_step_body(self.body, 6)
        self.assertIsNotNone(step, "crayon-review has no step 6")
        for literal in (STEPS_ASKED_ONCE, STEP_LEFT_UNANSWERED,
                        "In a later session, every step counts again",
                        AT_MOST_THREE, CLOSURE_ORDER, "handover.steps", "handover.judged"):
            with self.subTest(literal=literal):
                assert_contains(self, folded(step), literal, "crayon-review step 6")

    def test_s23_a_change_request_comes_back_at_the_closure(self):
        # CR-01: a page change asked for at a step question is open at the
        # closure after an accept, so it is asked again, never dropped.
        step = skill_step_body(self.body, 6)
        self.assertIsNotNone(step, "crayon-review has no step 6")
        step = folded(step)
        assert_contains(self, step, CHANGE_REQUEST_REOPENS, "crayon-review step 6")
        assert_contains(self, step, "in their words", "crayon-review step 6")
        assert_omits(self, step, STEPS_SKIPPED_WHATEVER_THE_ANSWER, "crayon-review step 6")
        # S-17's closure is otherwise unchanged: the cap, the order, the sources.
        for literal in (AT_MOST_THREE, CLOSURE_ORDER, "handover.steps", "handover.judged",
                        "in this same conversation", "Nits never count.",
                        "plain text, not options in a question tool", "Author decisions",
                        'crayon summary "$UNIT_ID" --md', 'crayon steer "$UNIT_ID" --note'):
            with self.subTest(literal=literal):
                assert_contains(self, step, literal, "crayon-review step 6")


class TestS21Uncertainty(unittest.TestCase):
    """S-21 — uncertainty is said in the first person, only where the record grounds it (VOICE-01, D-10)."""

    def setUp(self):
        self.write = body_of(SKILLS_ROOT / "crayon-write")
        self.review = body_of(SKILLS_ROOT / "crayon-review")
        self.rubric = (SKILLS_ROOT / "crayon-review" / "references" /
                       "review-rubric.md").read_text(encoding="utf-8")

    def test_s21_the_writer_voices_each_gap_and_only_gaps(self):
        step = skill_step_body(self.write, 6)
        self.assertIsNotNone(step, "crayon-write has no step 6")
        step = folded(step)
        for literal in (
            "first person",
            "report.json",
            "gaps",
            "not from `crayon summary`",
            EMPTY_GAPS_ADD_NOTHING,
            "I didn't run `relay sync`; the page describes it from server.py.",
        ):
            with self.subTest(literal=literal):
                assert_contains(self, step, literal, "crayon-write step 6")

    def test_s21_a_reviewer_says_what_it_could_not_verify_inside_the_finding(self):
        step = skill_step_body(self.review, 5)
        self.assertIsNotNone(step, "crayon-review has no step 5")
        for where, text in (("crayon-review step 5", folded(step)),
                            ("review-rubric.md", folded(self.rubric))):
            for literal in ("I found no source for", "I inferred",
                            "A verified finding carries no hedge"):
                with self.subTest(where=where, literal=literal):
                    assert_contains(self, text, literal, where)
        self.assertFalse(ONLY_VERIFIED in folded(self.rubric),
                         "review-rubric.md still admits only verified findings")
        assert_contains(self, folded(self.rubric), "hedged prose is a violation",
                        "review-rubric.md")

    def test_s21_no_standing_section_of_doubts(self):
        for where, text in (("crayon-write", self.write), ("crayon-review", self.review),
                            ("review-rubric.md", self.rubric)):
            with self.subTest(where=where):
                self.assertFalse("what i'm not sure of" in folded(text).lower(),
                                 "%s asks for a section of doubts" % where)
        for where, text in (("crayon-write", self.write), ("crayon-review", self.review)):
            with self.subTest(where=where, literal="never a general caveat"):
                assert_contains(self, folded(text), "never a general caveat", where)


class TestS22SelfReview(unittest.TestCase):
    """S-22 — the reviewer says when it is reviewing its own draft, and only then (VOICE-02, D-08, D-09)."""

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-review")

    def test_s22_step_5_names_the_two_grounds_and_the_line(self):
        step = skill_step_body(self.body, 5)
        self.assertIsNotNone(step, "crayon-review has no step 5")
        step = folded(step)
        for literal in (
            SELF_REVIEW_LINE,
            "this conversation ran `crayon draft`",
            "the `model` line of `crayon summary`",
            "never guessed",
            "there are no grounds",
            "directly before the findings",
            "never repeated at the verdict",
            "Record mode has no findings and no such line",
        ):
            with self.subTest(literal=literal):
                assert_contains(self, step, literal, "crayon-review step 5")

    def test_s22_the_pinned_blocks_are_intact(self):
        assert_contains(self, self.body, PRE_PASS, "crayon-review")
        assert_contains(self, self.body, SIX_DIMENSIONS, "crayon-review")
        pre_pass = self.body.find(PRE_PASS) + len(PRE_PASS)
        self_review = self.body.find("**Self-review.**")
        dimensions = self.body.find(SIX_DIMENSIONS)
        self.assertGreaterEqual(self_review, 0, "crayon-review has no **Self-review.** paragraph")
        self.assertTrue(pre_pass <= self_review < dimensions,
                        "the self-review paragraph must sit between the pre-pass and the "
                        "dimension list")

    def test_s22_the_lists_name_the_rule(self):
        for tag, literal in (
            ("must", "self-review"),
            ("must_not", "without grounds"),
            ("success_criteria", "self-review"),
        ):
            section = tagged_section(self.body, tag)
            with self.subTest(section=tag):
                self.assertIsNotNone(section, "crayon-review has no <%s>" % tag)
                assert_contains(self, folded(section), literal, "crayon-review <%s>" % tag)


class TestS24LeaveOutAndFocus(unittest.TestCase):
    """S-24 — scope is the author's: intake asks what the page can leave out, the writer keeps it off the page, and review's focus dimension checks it (JUDG-05, D-16 to D-20)."""

    def setUp(self):
        self.plan = body_of(PLAN_SKILL)
        self.write = body_of(SKILLS_ROOT / "crayon-write")
        self.socratic = SOCRATIC_REFERENCE.read_text(encoding="utf-8")
        self.rubric = REVIEW_RUBRIC.read_text(encoding="utf-8")

    def test_s24_the_leave_out_question_follows_arrival_and_is_always_asked(self):
        step = skill_step_body(self.plan, 2)
        self.assertIsNotNone(step, "crayon-plan has no step 2")
        for literal in (LEAVE_OUT_ORDER, "even when the brief fills every field"):
            with self.subTest(literal=literal):
                assert_contains(self, folded(step), literal, "crayon-plan step 2")
        self.assertLess(step.find(ARRIVAL_QUESTION), step.find(LEAVE_OUT_QUESTION),
                        "crayon-plan step 2 must ask the leave-out question after the "
                        "arrival-or-next question")
        edge = tagged_section(self.plan, "edge_cases")
        self.assertIsNotNone(edge, "crayon-plan has no <edge_cases>")
        for what, text in (
            ("crayon-plan <edge_cases>", edge),
            ("socratic-technique.md", self.socratic),
        ):
            entry = labelled_entry(text, "Jump-ahead TA")
            with self.subTest(file=what):
                self.assertIsNotNone(entry, "%s has no Jump-ahead TA entry" % what)
                for literal in ("always open", "leave out"):
                    assert_contains(self, folded(entry), literal,
                                    "%s Jump-ahead TA" % what)

    def test_s24_the_leave_out_answer_is_recorded_verbatim(self):
        step = skill_step_body(self.plan, 6)
        self.assertIsNotNone(step, "crayon-plan has no step 6")
        for literal in (NOTES_ARE_THEIRS, NOTHING_RECORDS_NOTHING):
            with self.subTest(literal=literal):
                assert_contains(self, folded(step), literal, "crayon-plan step 6")

    def test_s24_the_writer_keeps_what_the_author_left_out_off_the_page(self):
        ground = skill_step_body(self.write, 2)
        self.assertIsNotNone(ground, "crayon-write has no step 2")
        for literal in ("intake notes", "author decisions", "leave out", "scope"):
            with self.subTest(step=2, literal=literal):
                assert_contains(self, folded(ground), literal, "crayon-write step 2")
        author = skill_step_body(self.write, 3)
        self.assertIsNotNone(author, "crayon-write has no step 3")
        assert_contains(self, folded(author), "said to leave out", "crayon-write step 3")

    def test_s24_the_notes_narrow_the_inventory_and_a_later_request_outranks_them(self):
        ground = skill_step_body(self.write, 2)
        self.assertIsNotNone(ground, "crayon-write has no step 2")
        for literal in (NOTES_NARROW_INVENTORY, LATER_REQUEST_OUTRANKS):
            for what, text in (("crayon-write step 2", folded(ground)),
                               ("crayon-write", folded(self.write)),
                               ("review-rubric.md", folded(self.rubric))):
                with self.subTest(literal=literal, site=what):
                    self.assertEqual(text.count(literal), 1,
                                     "%s must state %r exactly once" % (what, literal))
        author = skill_step_body(self.write, 3)
        self.assertIsNotNone(author, "crayon-write has no step 3")
        assert_omits(self, folded(author), "never added to the page", "crayon-write step 3")
        assert_contains(self, folded(author), "said to leave out", "crayon-write step 3")

    def test_s24_the_writers_lists_exclude_what_the_notes_leave_out(self):
        # IN-03 (22-15): the lists a model checks itself against agree with
        # step 2's precedence, without repeating its two sentences.
        for tag in ("must", "success_criteria"):
            section = tagged_section(self.write, tag)
            with self.subTest(section=tag):
                self.assertIsNotNone(section, "crayon-write has no <%s>" % tag)
                for literal in ("less what the author's leave-out notes exclude",
                                "unless a later recorded request asks for it"):
                    assert_contains(self, folded(section), literal, "crayon-write <%s>" % tag)

    def test_s24_the_quick_start_and_the_read_back_name_the_leave_out_answer(self):
        item = quick_start_item(self.plan, 5)
        self.assertIsNotNone(item, "crayon-plan has no quick-start item 5")
        assert_contains(self, item, "what the page can leave out", "crayon-plan quick-start item 5")
        step = skill_step_body(self.plan, 6)
        self.assertIsNotNone(step, "crayon-plan has no step 6")
        assert_contains(self, folded(step), "the notes as they will be recorded",
                        "crayon-plan step 6")
        for literal in (LEAVE_OUT_QUESTION, ARRIVAL_QUESTION):
            with self.subTest(literal=literal):
                self.assertEqual(self.plan.count(literal), 1,
                                 "crayon-plan must state %r exactly once" % literal)

    def test_s24_focus_mirrors_completeness(self):
        layout_at = self.rubric.find("## Findings layout")
        self.assertGreaterEqual(layout_at, 0, "review-rubric.md has no findings layout")
        for where, text in (
            ("the dimension sections", self.rubric[:layout_at]),
            ("the findings layout", self.rubric[layout_at:]),
        ):
            with self.subTest(part=where):
                marks = [re.search(r"(?m)^### %s$" % name, text)
                         for name in ("completeness", "focus", "structure-fit")]
                self.assertTrue(all(marks), "review-rubric.md %s lacks one of "
                                "### completeness, ### focus, ### structure-fit" % where)
                starts = [mark.start() for mark in marks]
                self.assertEqual(starts, sorted(starts),
                                 "review-rubric.md %s must put ### focus after "
                                 "### completeness and before ### structure-fit" % where)
        for literal in (
            "## The five review dimensions",
            "what is present that the reader does not need",
            "said to leave out",
        ):
            with self.subTest(literal=literal):
                assert_contains(self, folded(self.rubric), literal, "review-rubric.md")
        must_fix = [line for line in self.rubric.splitlines()
                    if line.startswith("| `[must-fix]` |")]
        self.assertEqual(len(must_fix), 1, "review-rubric.md has no single [must-fix] row")
        assert_contains(self, must_fix[0], "said to leave out",
                        "review-rubric.md's [must-fix] row")

    def test_s24_no_five_dimension_wording_remains(self):
        review = (SKILLS_ROOT / "crayon-review" / "SKILL.md").read_text(encoding="utf-8")
        for what, text in (("skills/crayon-review/SKILL.md", review),
                           ("skills/README.md", README.read_text(encoding="utf-8"))):
            for stale in ("five-dimension", "five dimensions"):
                with self.subTest(file=what, stale=stale):
                    assert_omits(self, folded(text), stale, what)
        for stale in ("four review dimensions", "the four dimensions", "four generalized"):
            with self.subTest(file="review-rubric.md", stale=stale):
                assert_omits(self, folded(self.rubric), stale, "review-rubric.md")
        description = [line for line in review.splitlines()
                       if line.startswith("description:")]
        self.assertEqual(len(description), 1, "crayon-review has no single description line")
        assert_contains(self, description[0], "six-dimension", "crayon-review's description")


# ---------------------------------------------------------------------------
# S-10 — the ``references/`` tree, which no gate could see (CR-02)
# ---------------------------------------------------------------------------
#
# Every invariant above is asserted over ``body_of(skill_dir)``, i.e. SKILL.md
# alone, and ``scripts/skill_lint.py`` only ever opens SKILL.md's frontmatter.
# The ``references/`` files are loaded at RUNTIME by the very steps those
# assertions cover, and nothing read them: that is how a whole reference file
# stayed v1 prose through two rewrites of the tool it describes. S-10 is the
# scan that closes the hole. It is deliberately a token scan and not a meaning
# check — what the prose means is still a human's judgment (D-11) — but a
# reference that names an artefact this tool has never written is a structural
# fact about bytes, and that is exactly what this suite asserts.

#: Artefacts, keys and scripts the v1.x iteration had and this tool does not.
#: Each is a name a reference could only carry by describing the old shape:
#: ``ledger.md`` (the record is ``ledger.jsonl``), ``report.md`` (``--report``
#: parses JSON), ``sphinx_target`` / ``steering_notes`` (``unit.md``'s
#: frontmatter subset is fixed and anything else is refused ``unit_invalid``),
#: ``run_id`` (contract §"Not built"), and the five deleted shell scripts.
LEGACY_TOKENS = (
    "ledger.md",
    "report.md",
    "sphinx_target",
    "steering_notes",
    "run_id",
    "dogen-signoff.sh",
    "dogen-record-",
    "dogen-common.sh",
    # CR-05: never a field of any event. The generation carries `origins[]` —
    # a list of plain strings, with no commit stamps on it — and it was the
    # *signoff's* `sources[]` that carry `{path, commit|null}`. `review-rubric.md`
    # grounded four `[must-fix]` rules on the invented name and on a property
    # the real field does not have.
    "context_origins",
)

#: The vacuous-pass guard for this section: the five skills ship this many
#: reference files between them (6 plan, 8 write, 3 review, 4 onboard, 5 fetch),
#: and a mis-rooted glob must not pass by scanning nothing.
EXPECTED_REFERENCE_COUNT = 26


def reference_files():
    """Every ``references/*.md`` under every skill, sorted, path-stable."""
    return sorted(SKILLS_ROOT.glob("*/references/*.md"))


#: ``the unit's `x` `` / ``unit.md``'s `` `x` `` — the two constructions that
#: read as "this is a field of the unit". WR-14: three stance files wrote
#: "Author in the unit's ``format`` (from the target extension in ``unit.md``)".
#: The parenthetical says where it comes from, but the backticked name reads as
#: a field, and a skill that tried to set it would be refused ``unit_invalid``.
_UNIT_FIELD_RE = re.compile(
    r"(?:the unit(?:\.md)?(?:'s|s') `([a-z_]+)`"
    r"|`unit\.md`'s `([a-z_]+)`)"
)


def unit_frontmatter_keys():
    """contract 5.6's fixed frontmatter subset, from ``_UNIT_KEY_ORDER``.

    Read from ``crayon``'s source text, like every other fact this suite pins
    about the tool.
    """
    text = (ROOT / "crayon.py").read_text(encoding="utf-8")
    match = re.search(r"^_UNIT_KEY_ORDER = \(([^)]*)\)", text, re.MULTILINE)
    if match is None:
        return set()
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


#: The two derived-state payloads a reference may tell a reviewer to read, and
#: the source anchor whose dict literal defines each one's keys. Read as TEXT
#: (the module never imports ``crayon``); both are plain ``{"key": …}`` literals.
PAYLOAD_ANCHORS = {
    "summary": ("def summary_data(", "    return {", "    }"),
    "show": ("def cmd_show(", "        payload = {", "        }"),
}

#: The floor each payload's key scrape is checked against, so an anchor that
#: stopped matching reports a vacuous pass instead of a green one.
MIN_PAYLOAD_KEYS = 8

#: ``## What `crayon summary <id>` gives you`` / ``## What `crayon show <id>`
#: adds`` — a heading that attributes the fields under it to one payload.
_PAYLOAD_HEADING_RE = re.compile(r"^#{2,4} .*`crayon (summary|show) ")
_BACKTICKED_RE = re.compile(r"`([a-z][a-z_]*)`")


def payload_keys(payload):
    """The keys of one derived-state payload, scraped from ``crayon``'s source."""
    start, open_line, close_line = PAYLOAD_ANCHORS[payload]
    lines = (ROOT / "crayon.py").read_text(encoding="utf-8").splitlines()
    try:
        head = next(i for i, ln in enumerate(lines) if ln.startswith(start))
        begin = next(i for i in range(head, len(lines)) if lines[i] == open_line)
        end = next(i for i in range(begin + 1, len(lines)) if lines[i] == close_line)
    except StopIteration:  # pragma: no cover - the vacuity guard reports it
        return set()
    keys = set()
    for line in lines[begin + 1 : end]:
        match = re.match(r'\s*"([a-z_]+)":', line)
        if match:
            keys.add(match.group(1))
    return keys


def attributed_fields(text):
    """``[(payload, field, line)]`` a reference attributes to a payload.

    A field is attributed when it sits in the FIRST cell of a table row, or at
    the head of a bullet, inside a section whose heading names ``crayon summary``
    or ``crayon show``. That is exactly the shape ``provenance-summary.md``'s
    field map uses, and it is the shape the reviewer reads as "these are the
    fields the verb gives you".
    """
    found = []
    payload = None
    for line in text.splitlines():
        if line.startswith("#"):
            heading = _PAYLOAD_HEADING_RE.match(line)
            payload = heading.group(1) if heading else None
            continue
        if payload is None:
            continue
        if line.startswith("| `"):
            cell = line.split("|")[1]
            found += [(payload, name, line) for name in _BACKTICKED_RE.findall(cell)]
        elif line.startswith("- `"):
            head = _BACKTICKED_RE.match(line[2:])
            if head:
                found.append((payload, head.group(1), line))
    return found


class TestS25FirstSweepRules(unittest.TestCase):
    """S-25 — the rules the first skill-following sweep found too weak to hold (23-03, D-16).

    Each literal is typed, as in S-15 and S-20, and names the case it answers. A
    mirrored block is read from its authoring site; S-15 and S-20 assert the copies.
    """

    #: The plain-words block (B-17, B-40, B-61).
    PLAIN = (
        "seal, seals and sealed",
        "an option's label or description",
        '`"state": "sealed"` is "accepted"',
        "never that a digest matches",
    )
    #: The author-rules block (B-59).
    AUTHOR = (
        "backticks and `$` included",
        "nothing in them is escaped, dropped or wrapped",
    )
    #: crayon-review, by step.
    REVIEW = (
        (2, "ask no mode question"),                                       # B-77
        ("3a", "They are the last thing in that message"),                 # B-62, B-63
        ("3a", "Nothing is recorded from that answer yet: a fix or redraft verdict with "
               "those words records it."),                                 # B-65
        ("3a", "spoke to other steps and not to it"),                      # B-76
        ("3a", "the other sources still count"),                           # B-66
        (5, "then the line is required"),                                  # B-67
        (5, "is no ground"),                                               # B-68
        (6, "is the verdict, not an accept authorised in advance"),        # B-42
        (6, "show the lean then, and end that message with the verdict question"),  # B-43
        (6, "Your message ends on that question"),                         # B-20
        (6, "An accept that did not name a finding is not an answer to it"),  # B-46
        (6, "Search for the bare stem as well as the path"),               # B-60
        (6, "Number the questions in the order they were taken"),          # B-45
        (6, "never a question-tool call"),                                 # B-11
    )
    #: review-rubric.md (B-41, B-74) and provenance-summary.md (B-31).
    RUBRIC = (
        "all six dimension headings, `### focus` included",
        "total first",
        "names what the notes left out",
    )
    PROVENANCE = "never a bulleted re-composition of them"
    #: crayon-plan, by step.
    PLAN = (
        (2, "do not ask the problem question"),                            # B-53
        (2, "Ask one of the two, never both"),                             # B-71
        (4, "end that turn with the question it informs"),                 # B-52
        (6, "give `--notes` once"),                                        # B-72
        (6, "a real line break"),                                          # B-72
        (6, "no label of yours"),                                          # B-54, B-73
        (6, 'no "Nothing."'),                                              # B-54, B-73
    )
    #: crayon-write, by step.
    WRITE = (
        ("1a", "Before that gate, run nothing toward the step"),           # B-08
        ("1u", "The STOP touches nothing on disk"),                        # B-19
        (6, "never a gap of your own in its place"),                       # B-69
    )

    def step(self, body, number, what):
        if isinstance(number, int):
            found = skill_step_body(body, number)
        else:
            match = re.search(r"<step_%s\b[^>]*>" % number, body)
            found = None
            if match:
                rest = body[match.end():]
                found = rest.split("</step_%s>" % number, 1)[0]
        self.assertIsNotNone(found, "%s has no step %s" % (what, number))
        return folded(found)

    def test_s25_the_plain_words_block_names_every_form_and_place(self):
        block = folded(plain_words_bytes().decode("utf-8"))
        for literal in self.PLAIN:
            with self.subTest(literal=literal):
                assert_contains(self, block, literal, "the plain-words block")

    def test_s25_the_author_rules_keep_the_words_as_typed(self):
        block = folded(author_rules_bytes().decode("utf-8"))
        for literal in self.AUTHOR:
            with self.subTest(literal=literal):
                assert_contains(self, block, literal, "the author-rules block")

    def test_s25_review_states_each_rule_where_it_binds(self):
        body = body_of(SKILLS_ROOT / "crayon-review")
        for number, literal in self.REVIEW:
            with self.subTest(step=number, literal=literal):
                assert_contains(self, self.step(body, number, "crayon-review"), literal,
                                "crayon-review step %s" % number)

    def test_s25_the_review_references_ask_for_the_tool_lines_and_every_heading(self):
        rubric = folded(REVIEW_RUBRIC.read_text(encoding="utf-8"))
        for literal in self.RUBRIC:
            with self.subTest(literal=literal):
                assert_contains(self, rubric, literal, "review-rubric.md")
        provenance = folded(PROVENANCE_REFERENCE.read_text(encoding="utf-8"))
        assert_contains(self, provenance, self.PROVENANCE, "provenance-summary.md")
        assert_omits(self, provenance, "Present the fields in plain language",
                     "provenance-summary.md")

    def test_s25_plan_states_each_rule_where_it_binds(self):
        body = body_of(PLAN_SKILL)
        for number, literal in self.PLAN:
            with self.subTest(step=number, literal=literal):
                assert_contains(self, self.step(body, number, "crayon-plan"), literal,
                                "crayon-plan step %s" % number)

    def test_s25_write_states_each_rule_where_it_binds(self):
        body = body_of(SKILLS_ROOT / "crayon-write")
        for number, literal in self.WRITE:
            with self.subTest(step=number, literal=literal):
                assert_contains(self, self.step(body, number, "crayon-write"), literal,
                                "crayon-write step %s" % number)


#: D-19: the eval fixtures whose values the shipped skills must not carry. Each
#: path below is a definition site the S-26 token set is READ from; none of the
#: tokens is copied into this module.
FIXTURES_ROOT = EVALS_ROOT / "fixtures"
#: The project lane B's states are recorded against. Its TRACKED tree is read
#: (``git ls-files``), so an untracked ``__pycache__`` on disk adds nothing.
FIXTURE_PROJECT = FIXTURES_ROOT / "toyq"
#: The recorder: its ``UNIT=``/``TARGET=`` lines, ``unit new`` ids, ``--target``
#: paths, step-plan ``"id"`` values and ``--model`` ids.
STATES_SH = FIXTURES_ROOT / "states.sh"
#: The recorded states: the non-empty ``model`` values the replayed outputs carry.
STATES_JSON = EVALS_ROOT / "cases" / "decision" / "states.json"

#: The fixture's config module defines its settings as these two dict literals:
#: every key of both, and every value of the second, is a fixture token.
_CONFIG_DICTS = ("DEFAULTS", "ENV_OVERRIDES")
_CONFIG_DICT_VALUES = ("ENV_OVERRIDES",)

#: ``states.sh`` shapes, each with whether its value is a docs target path (whose
#: extension-less form and stem are fixture tokens too).
_STATES_SH_PATTERNS = (
    (re.compile(r"^UNIT=([A-Za-z0-9][\w.-]*)", re.MULTILINE), False),
    (re.compile(r"^TARGET=([A-Za-z0-9][\w./-]*)", re.MULTILINE), True),
    (re.compile(r"\bunit new ([A-Za-z0-9][\w.-]*)"), False),
    (re.compile(r"--target ([A-Za-z0-9][\w./-]*)"), True),
    (re.compile(r'"id"\s*:\s*"([^"]+)"'), False),
    (re.compile(r"--model ([A-Za-z0-9][\w./-]*)"), False),
)

#: Where a recorded state names its model: the ``--json`` key, the human
#: ``model:`` line, and the ``--model`` flag of the recorded command.
_RECORDED_MODEL_PATTERNS = (
    re.compile(r'"model"\s*:\s*"([^"]+)"'),
    re.compile(r"^model: (\S+)", re.MULTILINE),
    re.compile(r"--model ([A-Za-z0-9][\w./-]*)"),
)

#: The fixture ids that are also ordinary English words. Each matches only in a
#: fixture shape (:func:`_ordinary_shapes`); every other derived token is
#: distinctive and matches as a whole token anywhere, so a new fixture id fails
#: closed until it is classified here. A classification, not the token set: S-26
#: requires every member to be derived from the fixtures, so it cannot go stale.
ORDINARY_WORDS = frozenset({"config", "init", "install"})

#: The vacuous-pass floor: a derivation that stopped reading a definition site
#: must not pass by matching nothing.
REQUIRED_FIXTURE_TOKENS = ("cfg", "install", "toyq", "db_path", "example/drafting-model-1")


def _target_forms(path):
    """A docs target path, its extension-less form and its stem."""
    stem_path = re.sub(r"\.(?:md|rst)$", "", path)
    return {path, stem_path, stem_path.rsplit("/", 1)[-1]}


def _fixture_project_tokens():
    """The project's name, its package and module names, and its config keys.

    Read from the tracked tree. The top-level scaffolding every Python project
    carries (``README.md``, ``pyproject.toml``, ``docs/index.md``, dunder
    modules) is not distinctive and is not a token.
    """
    rel = FIXTURE_PROJECT.relative_to(ROOT).as_posix()
    listed = subprocess.run(
        ["git", "ls-files", "--", rel], cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        universal_newlines=True, check=False,
    ).stdout.splitlines()
    tokens = set()
    for name in listed:
        parts = pathlib.PurePosixPath(name).relative_to(rel).parts
        if len(parts) != 3 or parts[0] != "src":
            continue
        tokens.update((FIXTURE_PROJECT.name, parts[1]))
        if parts[2].startswith("__"):
            continue
        tokens.add(parts[2])
        if not parts[2].endswith(".py"):
            continue
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in _CONFIG_DICTS):
                continue
            value = ast.literal_eval(node.value)
            tokens.update(str(key) for key in value)
            if node.targets[0].id in _CONFIG_DICT_VALUES:
                tokens.update(str(item) for item in value.values())
    return tokens


def _states_sh_tokens():
    """The unit ids, targets, step ids and model ids ``states.sh`` records."""
    text = STATES_SH.read_text(encoding="utf-8")
    tokens = set()
    for pattern, is_target in _STATES_SH_PATTERNS:
        for value in pattern.findall(text):
            tokens.update(_target_forms(value) if is_target else {value})
    return tokens


def _strings_in(value):
    """Every string inside a parsed JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            for text in _strings_in(item):
                yield text
    elif isinstance(value, list):
        for item in value:
            for text in _strings_in(item):
                yield text


def _recorded_model_tokens():
    """The non-empty ``model`` values in the recorded states."""
    data = json.loads(STATES_JSON.read_text(encoding="utf-8"))
    tokens = set()
    for text in _strings_in(data):
        for pattern in _RECORDED_MODEL_PATTERNS:
            tokens.update(value for value in pattern.findall(text) if value)
    return tokens


def fixture_token_sources():
    """``{definition site: tokens it yields}``, one entry per site D-19 names."""
    return {
        "the toyq tree": _fixture_project_tokens(),
        "states.sh": _states_sh_tokens(),
        "states.json": _recorded_model_tokens(),
    }


def fixture_tokens():
    """Every eval-fixture token, the union over :func:`fixture_token_sources`."""
    return set().union(*fixture_token_sources().values())


def _ordinary_shapes(word):
    """``(shape, regex)`` for the fixture shapes an ordinary word counts in."""
    w = re.escape(word)
    return (
        ("a docs file name", r"(?<![\w/.-])%s\.(?:md|rst)(?![\w-])" % w),
        ("a step id", r"\b[Ss]tep\s+%s(?![\w-])" % w),
        ("a JSON id", r'"id"\s*:\s*"%s"' % w),
        ("a quoted unit id opening an ask", '"%s\\s+[-–—]\\s' % w),
        ("a bare id in code", r"`%s`" % w),
    )


def fixture_hits(text, tokens):
    """``[(line, token, shape)]`` for every fixture token ``text`` carries."""
    hits = []
    for token in sorted(tokens):
        if token in ORDINARY_WORDS:
            shapes = _ordinary_shapes(token)
        else:
            shapes = (("a whole token", r"(?<![\w-])%s(?![\w-])" % re.escape(token)),)
        for shape, pattern in shapes:
            for match in re.finditer(pattern, text):
                hits.append((text.count("\n", 0, match.start()) + 1, token, shape))
    return sorted(hits)


class TestS26NoEvalFixtureInSkills(unittest.TestCase):
    """S-26 — no shipped skill names the eval fixtures that grade it (D-18, D-19).

    Skill text tuned to its own eval cases inflates the skill-following figure
    and gives real users examples that mean nothing to them. The tokens are read
    from the fixture definitions, never listed here: a new fixture value is
    guarded the moment it is defined.
    """

    def test_s26_the_token_set_is_read_from_the_fixtures(self):
        sources = fixture_token_sources()
        for site, found in sources.items():
            with self.subTest(site=site):
                self.assertTrue(found, "%s yields no fixture token" % site)
        self.assertIn("example/drafting-model-1", sources["states.json"],
                      "states.json's recorded model is not read")
        tokens = fixture_tokens()
        for token in REQUIRED_FIXTURE_TOKENS:
            with self.subTest(token=token):
                self.assertIn(token, tokens, "the derived token set lacks %r" % token)
        for word in sorted(ORDINARY_WORDS):
            with self.subTest(word=word):
                self.assertIn(word, tokens,
                              "ORDINARY_WORDS names %r, which no fixture defines" % word)

    def test_s26_no_skill_file_names_an_eval_fixture(self):
        tokens = fixture_tokens()
        files = sorted(SKILLS_ROOT.rglob("*.md"))
        self.assertGreaterEqual(
            len(files), len(EXPECTED_SKILLS) + EXPECTED_REFERENCE_COUNT + 1,
            "the skills scan found too few files to be meaningful")
        found = []
        for path in files:
            text = path.read_text(encoding="utf-8")
            for line, token, shape in fixture_hits(text, tokens):
                found.append("%s:%d: %s (%s)"
                             % (path.relative_to(ROOT).as_posix(), line, token, shape))
        self.assertEqual(found, [], "skill text names an eval fixture:\n  "
                         + "\n  ".join(found))

    def test_s26_a_planted_token_is_caught(self):
        tokens = fixture_tokens()
        plantings = (
            (PLAN_SKILL, "A model such as example/drafting-model-1 is no ground.",
             "example/drafting-model-1"),
            (SKILLS_ROOT / "crayon-write", 'Ask the author about "step init" first.', "init"),
        )
        for skill, sentence, token in plantings:
            with self.subTest(token=token):
                body = body_of(skill).rstrip("\n") + "\n" + sentence + "\n"
                line = body.count("\n")
                caught = [(at, name) for at, name, _ in fixture_hits(body, tokens)]
                self.assertIn((line, token), caught,
                              "a planted %r on line %d is not reported" % (token, line))


class TestS27ClosingRunRules(unittest.TestCase):
    """S-27 — the skill text the Phase 24 closing run found two ways to read (D-28).

    Each literal is typed, and names the case it answers.
    """

    #: B-23: crayon-write's routing row for ``re_sign`` names the signoff verb, and
    #: its step 1 routes the act back to crayon-plan. The step says which wins.
    WRITE_STEP_1 = (
        "though its routing row names the verb",
        "run no `crayon signoff` and no `crayon unit edit`, and offer neither",
        "route back to crayon-plan",
    )
    WRITE_MUST_NOT = "Never run or offer `crayon signoff` or `crayon unit edit`"

    def setUp(self):
        self.body = body_of(SKILLS_ROOT / "crayon-write")

    def test_s27_write_routes_the_signoff_to_plan_over_its_routing_row(self):
        step = skill_step_body(self.body, 1)
        self.assertIsNotNone(step, "crayon-write has no step 1")
        for literal in self.WRITE_STEP_1:
            with self.subTest(literal=literal):
                assert_contains(self, folded(step), literal, "crayon-write step 1")
        section = tagged_section(self.body, "must_not")
        self.assertIsNotNone(section, "crayon-write has no <must_not>")
        assert_contains(self, folded(section), self.WRITE_MUST_NOT, "crayon-write <must_not>")


class TestS10ReferenceFiles(unittest.TestCase):
    """S-10 — a reference file is shipped text and is held to the same rules."""

    def test_s10_the_scan_sees_every_reference_file(self):
        found = reference_files()
        self.assertEqual(
            len(found),
            EXPECTED_REFERENCE_COUNT,
            "the reference scan found %d file(s); update EXPECTED_REFERENCE_COUNT "
            "deliberately when the set changes: %r"
            % (len(found), [str(p.relative_to(ROOT)) for p in found]),
        )
        for path in found:
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertTrue(path.read_text(encoding="utf-8").strip())

    def test_s10_no_reference_file_names_a_v1_artefact(self):
        for path in reference_files():
            text = path.read_text(encoding="utf-8")
            for token in LEGACY_TOKENS:
                with self.subTest(file=str(path.relative_to(ROOT)), token=token):
                    assert_omits(self, text, token, str(path.relative_to(ROOT)))

    def test_s10_no_reference_file_names_a_force_flag(self):
        # S-04 asserts this over SKILL.md; VERB-01 removed the flag from the
        # tool, so a reference that still names it sends the reviewer at a
        # command that cannot parse.
        for path in reference_files():
            with self.subTest(file=str(path.relative_to(ROOT))):
                assert_omits(
                    self,
                    path.read_text(encoding="utf-8"),
                    FORCE_FLAG,
                    str(path.relative_to(ROOT)),
                )

    def test_s10_every_flag_a_reference_puts_on_a_crayon_verb_exists(self):
        # Scoped to `crayon <verb> …` invocations on purpose: a reference may
        # legitimately quote another program's flags (a walk records
        # `foo --version`), and only the flags handed to THIS tool are a claim
        # about THIS tool. WR-06: scoped to THAT VERB too — a flag on the wrong
        # verb is a command that cannot parse, and the flat union could not
        # see it.
        for path in reference_files():
            assert_verb_scoped_flags(
                self, path.read_text(encoding="utf-8"), str(path.relative_to(ROOT))
            )

    def test_s10_the_per_verb_flag_map_is_not_vacuous(self):
        per_verb, shared, unbound = walk_verb_flags()
        # WR-06 (iteration 3): the walk's degradation mode. An `add_argument`
        # on a receiver the walk failed to bind used to become a SHARED flag —
        # accepted on every verb — and none of the assertions below could see
        # it, because the verb count is unchanged and the three discrimination
        # pairs happen not to be affected. An unrecognised parser shape is a
        # walk that needs updating.
        self.assertEqual(
            unbound,
            [],
            "`build_parser` registers flag(s) on receiver(s) this walk did not "
            "bind: %r. Teach the walk the shape; do not let them widen every "
            "verb at once" % (unbound,),
        )
        # And the shared set is bounded in both directions: empty means the
        # `common` parent stopped being walked, and a growing one means flags
        # are leaking into "every verb".
        self.assertTrue(
            MIN_SHARED_FLAGS <= len(shared) <= MAX_SHARED_FLAGS,
            "%d shared flag(s) %r; expected between %d and %d — a shared flag "
            "is accepted on EVERY verb"
            % (len(shared), shared, MIN_SHARED_FLAGS, MAX_SHARED_FLAGS),
        )
        self.assertGreaterEqual(
            len(per_verb),
            MIN_VERBS_PARSED,
            "walked only %d verb(s) out of `build_parser`; every per-verb "
            "assertion would pass over an empty set: %r"
            % (len(per_verb), sorted(per_verb)),
        )
        self.assertEqual(
            set(per_verb),
            set(VERBS),
            "the walked verb set and contract 6's verb table disagree",
        )
        # And the map must actually DISCRIMINATE — a walk that put every flag
        # on every verb would satisfy the counts above and see nothing.
        self.assertNotIn("--re-sign", per_verb["show"])
        self.assertNotIn("--steps-seq", per_verb["steer"])
        self.assertIn("--re-sign", per_verb["unit"])
        self.assertIn("--steps-seq", per_verb["step"])


# ---------------------------------------------------------------------------
# S-11 — a routed DESCRIPTION is grounded in the refusal it describes (CR-02)
# ---------------------------------------------------------------------------

#: Words the tool's own ``Refusal`` for a reason puts in front of the operator,
#: which the routed row must therefore also carry.
#:
#: S-10 can see a wrong *token* and a wrong *flag*. It cannot see a row whose
#: description is simply about something else — which is how
#: ``evidence_mismatch`` shipped for two contract revisions telling the operator
#: to "re-run the step and record the output file the run actually produced",
#: a remedy that can never clear a gate on the evidence's ``mode`` (CR-02).
#:
#: Each entry is asserted on BOTH sides: the substring must appear in the
#: ``raise Refusal(...)`` block for that reason in ``crayon``'s source, and in
#: the reason's routing row. So the fixture cannot rot in either direction — a
#: raiser reworded without its row goes red, and a row reworded away from its
#: raiser goes red.
#:
#: WR-05: the word has to be one only THAT refusal's raiser can produce.
#: ``evidence_stale`` and ``step_unknown`` were both pinned to ``plan``/``seq``,
#: which is ordinary vocabulary — and ``seq`` is supplied unconditionally by the
#: verb column every ``step`` row carries (``--steps-seq N``), so only ``plan``
#: was load-bearing and "plan" appears in any description that mentions a step
#: plan at all. Swapping ``evidence_stale``'s description for
#: ``evidence_mismatch``'s satisfied both pins while describing a different
#: refusal entirely — which is precisely the failure S-11 exists to catch. The
#: replacements are phrases only the raiser says: "superseded by the plan at
#: seq M", "is not in the plan".
GROUNDED_REASONS = {
    "evidence_mismatch": ("mode",),
    "evidence_stale": ("superseded",),
    "step_unknown": ("is not in the plan",),
    "not_actionable": ("tutorial", "how-to"),
    # WR-09: both details, and the qualification rather than the bare flag.
    # `("commit_rejected", "--adopt")` grounded the row on the presence of a
    # string: a row that named `--adopt` unconditionally satisfied it, which is
    # the shape CR-02 was filed for, and `stage_rejected` — the other detail
    # this same refusal carries — was not pinned at all.
    "recovery_unsupported": ("commit_rejected", "stage_rejected", "ONLY when"),
    # WR-07: the reason `resume --adopt` raises, from TWO places, whose row was
    # rewritten three times without anything holding it to either raiser. The
    # two words are one per arm — "last event" is the eligibility arm's, "not
    # on disk" the absent-bytes arm's — so a row that dropped either half would
    # go red, and `refusal_blocks()` already returns both blocks.
    "adopt_unsupported": ("last event", "not on disk"),
}

#: The floor for the extractor below. A regex that stopped matching would make
#: every assertion in S-11 vacuous.
MIN_REFUSAL_BLOCKS = 40

_RAISE_RE = re.compile(r"^(\s*)raise Refusal\($")


def module_prose_constants(source=None):
    """S-11 needs the strings-only view of the shared module resolver."""
    if source is None:
        source = (ROOT / "crayon.py").read_text(encoding="utf-8")
    return _module_string_constants(ast.parse(source)).text


def refusal_blocks(source=None):
    """``{reason: [source text of each ``raise Refusal`` block]}`` from ``crayon``.

    Read as TEXT, never imported — the module docstring's rule. A block runs
    from the ``raise Refusal(`` line to the ``)`` at its own indentation, and
    the reason is its first quoted token, which is the call's first positional
    argument.
    """
    if source is None:
        source = (ROOT / "crayon.py").read_text(encoding="utf-8")
    lines = source.splitlines()
    constants = module_prose_constants(source)
    blocks = {}
    index = 0
    while index < len(lines):
        match = _RAISE_RE.match(lines[index])
        if not match:
            index += 1
            continue
        indent = len(match.group(1))
        cursor = index + 1
        body = []
        while cursor < len(lines):
            line = lines[cursor]
            if line.strip() == ")" and len(line) - len(line.lstrip()) == indent:
                break
            body.append(line)
            cursor += 1
        text = "\n".join(body)
        name = re.search(r'"([a-z_]+)"', text)
        if name:
            # WR-09: a named sentence reads as the sentence, not as its name.
            for constant, prose in constants.items():
                text = re.sub(
                    r"\b%s\b" % re.escape(constant),
                    lambda _match, prose=prose: prose, text,
                )
            blocks.setdefault(name.group(1), []).append(text)
        index = cursor + 1
    return blocks


class TestS11RoutedDescriptionsAreGrounded(unittest.TestCase):
    """S-11 — each pinned reason's row says what its refusal actually says."""

    @classmethod
    def setUpClass(cls):
        cls.blocks = refusal_blocks()

    def test_s11_the_refusal_extractor_is_not_vacuous(self):
        total = sum(len(v) for v in self.blocks.values())
        self.assertGreaterEqual(
            total,
            MIN_REFUSAL_BLOCKS,
            "extracted only %d `raise Refusal(` blocks from `crayon`; every "
            "S-11 assertion would be vacuously satisfied" % total,
        )

    def test_s11_every_pinned_reason_is_actually_raised(self):
        for reason in GROUNDED_REASONS:
            with self.subTest(reason=reason):
                self.assertIn(
                    reason,
                    self.blocks,
                    "S-11 pins %r, which `crayon` no longer raises — drop the "
                    "fixture entry or restore the raiser" % reason,
                )

    def test_s11_the_raiser_uses_the_words_the_fixture_pins(self):
        for reason, words in GROUNDED_REASONS.items():
            joined = "\n".join(self.blocks.get(reason, [])).lower()
            for word in words:
                with self.subTest(reason=reason, word=word):
                    self.assertIn(
                        word.lower(),
                        joined,
                        "`crayon`'s %s refusal no longer says %r; the routed row "
                        "below is pinned to it" % (reason, word),
                    )

    def test_s11_no_two_pinned_word_sets_are_nested(self):
        """WR-05 — a fixture that stops discriminating must go red.

        Two reasons pinned to the same words do not distinguish them: a row
        could be rewritten to describe either refusal and satisfy both pins.
        That was true of ``evidence_stale`` and ``step_unknown``, which shared
        ``("plan", "seq")`` exactly. Nesting is the general form of it — a
        subset satisfies every row its superset does — so the assertion is on
        the subset relation rather than on equality.
        """
        items = [(name, frozenset(w.lower() for w in words))
                 for name, words in GROUNDED_REASONS.items()]
        for left, left_words in items:
            for right, right_words in items:
                if left == right:
                    continue
                with self.subTest(left=left, right=right):
                    self.assertFalse(
                        left_words <= right_words,
                        "%s's pinned words %s are a subset of %s's %s, so a row "
                        "describing %s would satisfy %s's pin too — the fixture "
                        "no longer discriminates between them"
                        % (left, sorted(left_words), right, sorted(right_words),
                           right, left),
                    )

    def test_s11_the_routed_row_uses_the_words_its_refusal_uses(self):
        for reason, words in GROUNDED_REASONS.items():
            row = routing_row(reason).lower()
            for word in words:
                with self.subTest(reason=reason, word=word):
                    self.assertIn(
                        word.lower(),
                        row,
                        "the routing row for %s does not mention %r, which its "
                        "own refusal names; a row that describes something else "
                        "routes the skill to a remedy that cannot clear the gate"
                        % (reason, word),
                    )


class TestS10AttributedPayloadFields(unittest.TestCase):
    """S-10 — a field a reference attributes to a verb is one the verb carries.

    CR-04: the ``provenance-summary.md`` rewrite that closed the v1-prose hole
    shipped a field map that was wrong in four rows — a `requests.origin` value
    set the code never emits, a ``hook`` field neither payload surfaces, a
    ``paths`` status list missing both brownfield statuses and inventing
    ``orphan``, and two ``qualifier`` tokens that do not exist. None of those is
    a legacy token, a ``--force`` or an unregistered flag, so the rest of S-10
    reported green over all four. This is the structural half of that hole: the
    field NAMES are checkable against the payloads themselves.

    What is still a human's job: whether a row's prose describes the field
    correctly. S-11 pins that for the routed reason rows; here the claim is only
    that the name exists.
    """

    def test_s10_both_payload_key_scrapes_are_not_vacuous(self):
        for payload in PAYLOAD_ANCHORS:
            with self.subTest(payload=payload):
                keys = payload_keys(payload)
                self.assertGreaterEqual(
                    len(keys),
                    MIN_PAYLOAD_KEYS,
                    "scraped only %d key(s) for `crayon %s --json` from `crayon`; "
                    "its source anchor has moved and every assertion below "
                    "would pass vacuously" % (len(keys), payload),
                )

    def test_s10_the_attribution_scan_finds_the_known_field_map(self):
        # The one file that carries a field map today. A scan that stopped
        # matching its headings would make the gate vacuous without failing.
        text = (
            SKILLS_ROOT / "crayon-review" / "references" / "provenance-summary.md"
        ).read_text(encoding="utf-8")
        found = attributed_fields(text)
        payloads = {payload for payload, _, _ in found}
        self.assertEqual(
            payloads,
            {"summary", "show"},
            "provenance-summary.md must attribute fields to both derived-state "
            "payloads; the scan saw %r" % sorted(payloads),
        )
        self.assertGreaterEqual(len(found), 12, "found only %d fields" % len(found))

    def test_s10_the_unit_frontmatter_key_set_parses(self):
        keys = unit_frontmatter_keys()
        self.assertEqual(
            keys,
            {"title", "intent", "audience", "targets", "sources", "notes"},
            "`_UNIT_KEY_ORDER` did not parse out of `crayon` as contract 5.6's "
            "six keys; the assertion below would pass over an empty set",
        )

    def test_s10_a_backticked_unit_field_is_one_of_the_six(self):
        """WR-14 — ``the unit's `format` `` names a field that does not exist.

        Contract 5.6 fixes ``unit.md``'s frontmatter to exactly six keys and
        refuses anything else ``unit_invalid``, so a reference that writes
        ``the unit's `x` `` is either naming one of the six or sending the skill
        at a refusal. Same class as WR-08's ``steering_notes``; missed because
        ``format`` is not a legacy token, only a wrong one.
        """
        keys = unit_frontmatter_keys()
        for path in reference_files() + [
            skill_dir / "SKILL.md" for skill_dir in skill_dirs()
        ]:
            text = path.read_text(encoding="utf-8")
            for match in _UNIT_FIELD_RE.finditer(text):
                field = match.group(1) or match.group(2)
                with self.subTest(file=str(path.relative_to(ROOT)), field=field):
                    self.assertIn(
                        field,
                        keys,
                        "%s writes `%s` as a field of the unit; `unit.md`'s "
                        "frontmatter is exactly %s and any other key is refused "
                        "`unit_invalid`"
                        % (
                            path.relative_to(ROOT),
                            field,
                            ", ".join(sorted(keys)),
                        ),
                    )

    def test_s10_every_attributed_field_is_a_key_the_payload_carries(self):
        keys = {payload: payload_keys(payload) for payload in PAYLOAD_ANCHORS}
        for path in reference_files():
            text = path.read_text(encoding="utf-8")
            for payload, field, line in attributed_fields(text):
                with self.subTest(
                    file=str(path.relative_to(ROOT)), payload=payload, field=field
                ):
                    self.assertIn(
                        field,
                        keys[payload],
                        "%s tells the reviewer to read `%s` out of `crayon %s "
                        "--json`, which carries %s\n  %s"
                        % (
                            path.relative_to(ROOT),
                            field,
                            payload,
                            ", ".join(sorted(keys[payload])),
                            line.strip()[:120],
                        ),
                    )


# ---------------------------------------------------------------------------
# S-12 — an enumeration is complete, and prose never outruns the command
#        (WR-07, WR-08)
# ---------------------------------------------------------------------------

#: Every refusal a skill WALKING a unit has to branch on, and which both
#: ``walk-protocol.md``'s step-gate table and ``crayon-write``'s "Refusals to
#: expect" list present themselves as complete enumerations of.
#:
#: WR-07: WR-04 made `plan-steps` and `step` newly capable of refusing
#: `not_actionable`, and neither list was told. Both read as exhaustive — the
#: table opens "Branch on the `error` field of the refusal's JSON line" — so a
#: skill that met it had no branch at all.
WALK_GATE_REASONS = (
    "step_unknown",
    "not_actionable",
    "already_recorded",
    "evidence_incomplete",
    "evidence_mismatch",
    "evidence_stale",
)

WALK_GATE_FILES = (
    ("crayon-write", "SKILL.md"),
    ("crayon-write", "references/walk-protocol.md"),
)


class TestS12TheStepGateEnumerations(unittest.TestCase):
    """S-12 — both step-gate lists name every reason a walk can meet, and no
    reference attributes to a bare command an outcome only a flag produces."""

    def _text(self, skill, relative):
        return (SKILLS_ROOT / skill / relative).read_text(encoding="utf-8")

    def test_s12_both_enumerations_name_every_walk_gate_reason(self):
        for skill, relative in WALK_GATE_FILES:
            text = self._text(skill, relative)
            for reason in WALK_GATE_REASONS:
                with self.subTest(file="%s/%s" % (skill, relative), reason=reason):
                    self.assertIn(
                        reason,
                        text,
                        "%s/%s presents itself as the complete branch table for "
                        "the step gate and does not name %r"
                        % (skill, relative, reason),
                    )

    def test_s12_every_pinned_reason_is_one_the_contract_has(self):
        # The fixture may not drift into naming refusals the tool cannot raise:
        # that would document a branch no skill will ever take.
        reasons = set(contract_reasons())
        for reason in WALK_GATE_REASONS:
            with self.subTest(reason=reason):
                self.assertIn(reason, reasons)

    def test_s12_a_non_default_flag_value_is_never_claimed_by_prose_alone(self):
        """WR-08 — a value the tool only produces when a flag ASKS for it may
        not be attributed to the bare command.

        ``crayon steer``'s ``--origin`` defaults to ``manual``, so
        ``crayon steer <id> --note "…"`` (origin ``plan``) filed the note under
        the wrong origin — the field ``describe_requests`` reports and
        ``provenance-summary.md`` tells the reviewer to read.
        """
        for path in reference_files() + [
            skill_dir / "SKILL.md" for skill_dir in skill_dirs()
        ]:
            text = re.sub(r"\\\n\s*", " ", path.read_text(encoding="utf-8"))
            for match in re.finditer(r"`crayon steer [^`]*`[^\n]*", text):
                window = match.group(0)
                if "origin" not in window:
                    continue
                with self.subTest(file=str(path.relative_to(ROOT))):
                    self.assertIn(
                        "--origin",
                        window,
                        "%s attributes an origin to `crayon steer` without "
                        "passing --origin, which defaults to `manual`:\n  %s"
                        % (path.relative_to(ROOT), window.strip()[:140]),
                    )

    def test_s12_the_fixture_is_not_vacuous(self):
        self.assertGreaterEqual(len(WALK_GATE_REASONS), 6)
        for skill, relative in WALK_GATE_FILES:
            with self.subTest(file="%s/%s" % (skill, relative)):
                self.assertTrue((SKILLS_ROOT / skill / relative).is_file())

# ---------------------------------------------------------------------------
# S-13 — routed text is inspectable and carries its stated conditions
# ---------------------------------------------------------------------------
# This static walk checks structure and wording, not the truth of prose or
# termination. N-46 drives recovery routes against real git repositories;
# TestEscapeHintHistory checks that historical counts preserve the remedy.
# Unknown constructors' argument shapes and unknown hint expressions fail
# explicitly rather than vanishing behind empty extracted text.

ESCAPE_REASONS = ("adopt_unsupported", "resume_ambiguous", "recovery_unsupported")

#: Necessary markers for adoption offers; lifecycle tests check their meaning.
ADOPT_PRECONDITION_MARKERS = (
    "only when",
    "adopt_unsupported",
    "still on disk",
    # WR-03: the fourth condition the code applies. `resume_adopt` returns a
    # plain resume when the batch's last event is already an adoption, so an
    # offer that names only the other three sends the author to a command
    # that appends no event and drops the note they just wrote.
    "not itself an adoption",
)

#: The blocker-removal advice, matched on its stem — WR-03 widened
#: "the commit" to "the transition" for the ``stage_rejected`` arm.
TERMINATING_ESCAPE = "remove what is refusing the"

#: The helper every hint that re-offers a resume FLAG must be built through.
ESCAPE_BRANCH = "escape_hint"

#: The functions that construct a refusal. ``Refusal`` and ``refuse`` take the
#: reason first and hint fourth (either can also be a keyword); ``classify_stage_a``'s ``answer``
#: funnel takes ``(situation, reason, detail, hint)`` positionally.
_REFUSAL_CONSTRUCTORS = {
    "Refusal": (0, 3),
    "refuse": (0, 3),
    "answer": (1, 3),
}

#: The dicts a refusal already holds — JSON payloads read out of the ledger,
#: the pending manifest or argparse. A `.get` on one of these is a DATA read,
#: and its value is never prose the operator is routed by. Deliberately an
#: exhaustive list of the receivers that appear rather than "any `.get`": a new
#: receiver must be classified once, explicitly, instead of inheriting a
#: blanket exemption that hid a whole `adopt_unsupported` arm (WR-01).
PAYLOAD_DICTS = frozenset(
    {"entry", "plan", "current_plan", "planned_step", "plan_event"}
)

#: Floors for the walk. A regex or an AST shape that stopped matching would
#: make every assertion below vacuously true — the failure mode S-11's own
#: floor exists for, and the failure mode that let CR-01 through twice.
MIN_REFUSAL_SITES = 120
MIN_ESCAPE_SITES = 8


class _ModuleScope(object):
    """The module-level names the walk can resolve, and the ones it cannot.

    Reads as the ``{NAME: text}`` mapping it replaces — ``in``, ``[]`` and
    ``items()`` all see only the RESOLVED names — and additionally answers
    :meth:`opaque`, which is how a module-level name the walk cannot read
    fails closed instead of vanishing (WR-01).
    """

    def __init__(self, text, names, data=frozenset(), values=None):
        self.text = text
        self.names = names
        self.data = data
        self.values = values or {}

    def __contains__(self, name):
        return name in self.text

    def __getitem__(self, name):
        return self.text[name]

    def get(self, name, default=None):
        return self.text.get(name, default)

    def items(self):
        return self.text.items()

    def opaque(self, name):
        """True for a module-level name whose prose the walk cannot read.

        A name bound to a number, a bool, ``None`` or a collection of those is
        not prose and never becomes prose — ``MAX_STEPS`` interpolated into a
        detail is a count, not a sentence — so it is data, not a gap.
        """
        return (
            name in self.names
            and name not in self.text
            and name not in self.data
        )


def _collection_strings(value):
    """The string values of a module-level dict/tuple/list, or ``None``.

    ``None`` means "not resolvable as prose" — an empty collection, or one
    holding anything that is not a string literal. A collection the walk cannot
    read whole is one it must not read at all, because a partial read is what
    lets a single prose value hide (WR-01).
    """
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        elements = list(value.elts)
    elif isinstance(value, ast.Dict):
        if any(key is None for key in value.keys):  # `{**other}` — unresolvable
            return None
        elements = list(value.values)
    else:
        return None
    if not elements:
        return None
    texts = []
    for element in elements:
        if not isinstance(element, ast.Constant) or not isinstance(
            element.value, str
        ):
            return None
        texts.append(element.value)
    return texts


def _is_nontext_literal(value):
    """True for a module-level binding that cannot hold prose.

    A number, a bool, ``None``, or a collection of those. Anything a string
    could reach — a call's result, a name, a comprehension — is NOT this, and
    :meth:`_ModuleScope.opaque` reports it so a hint that reads it fails closed.
    """
    if isinstance(value, ast.Constant):
        return not isinstance(value.value, str)
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        elements = list(value.elts)
    elif isinstance(value, ast.Dict):
        if any(key is None for key in value.keys):
            return False
        elements = list(value.values)
    else:
        return False
    return bool(elements) and all(
        isinstance(element, ast.Constant) and not isinstance(element.value, str)
        for element in elements
    )


def _module_string_constants(tree):
    """The module-level prose of ``crayon``, as a :class:`_ModuleScope`.

    ``ADOPT_PRECONDITION`` is one of these, and the two hints that carry it
    reference it by name. Without this resolution the walk would read those
    hints as not stating the precondition they do state — and, worse, a future
    hint could hide ``--adopt`` behind a constant and pass. The constants are
    held to the same property in their own right below.

    WR-01: collections retain their AST values so literal-key lookups read
    only the selected value; computed prose lookups fail closed. Whole
    collections (for example, a join) resolve to the union of their values.
    ``_UNIT_FLAGS["sources"]`` and ``", ".join(EVIDENCE_KEYS)``
    are the two shapes that already appear, and the same resolution is what
    shuts the hole the `renderers` allowlist left open: prose routed through
    ``ADVICE.get("overwrite")`` used to be classified as "data formatting" and
    never read, so a fourth ``adopt_unsupported`` arm whose hint lived in a
    module dict named ``--adopt`` with no precondition and the suite stayed
    green. Every module-level assigned name is recorded either way, so one the
    walk CANNOT read is a gap rather than silence.
    """
    text, names, data, values = {}, set(), set(), {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        elif isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        else:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            resolved = value.value
        else:
            strings = _collection_strings(value) if value is not None else None
            resolved = "\n".join(strings) if strings is not None else None
        nontext = value is not None and _is_nontext_literal(value)
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            names.add(target.id)
            values[target.id] = value
            if resolved is not None:
                text[target.id] = resolved
            elif nontext:
                data.add(target.id)
    return _ModuleScope(text, frozenset(names), frozenset(data), values)


def _module_lookup(node, constants):
    """Return (is_module_lookup, selected_value); None means unresolved.

    Never credit a lookup with prose from another key. Computed prose lookups
    and unsupported collections are gaps, including inside formatting. A
    collection containing only option spellings is data, not qualifying prose.
    """
    if isinstance(node, ast.Subscript):
        receiver, key, default = node.value, node.slice, None
    elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
          and node.func.attr == "get" and 1 <= len(node.args) <= 2
          and not node.keywords):
        receiver, key = node.func.value, node.args[0]
        default = node.args[1] if len(node.args) == 2 else ast.Constant(None)
    else:
        return False, None
    if not isinstance(receiver, ast.Name) or receiver.id not in constants.names:
        return False, None
    value = constants.values.get(receiver.id)
    if not isinstance(key, ast.Constant):
        # Existing _UNIT_FLAGS.get(key, key) selects an option spelling, not
        # advice. Only bare flag tokens may use the union: none can supply a
        # precondition for a sibling offer. Any prose value fails closed.
        tokens = _collection_strings(value)
        flag_pattern = r"--[a-z][a-z-]*(?: / --[a-z][a-z-]*)*"
        fallback_is_key = (isinstance(default, ast.Name) and isinstance(key, ast.Name)
                           and default.id == key.id)
        fallback_is_empty = default is None or (
            isinstance(default, ast.Constant) and default.value is None
        )
        if (tokens and all(re.fullmatch(flag_pattern, token) for token in tokens)
                and (fallback_is_key or fallback_is_empty)):
            return True, ast.Constant("\n".join(tokens))
        return True, None
    if isinstance(value, ast.Dict):
        if any(not isinstance(k, ast.Constant) for k in value.keys):
            return True, None
        selected = next((v for k, v in reversed(list(zip(value.keys, value.values)))
                         if k.value == key.value), default)
    elif (isinstance(node, ast.Subscript) and isinstance(value, (ast.Tuple, ast.List))
          and isinstance(key.value, int) and -len(value.elts) <= key.value < len(value.elts)):
        selected = value.elts[key.value]
    else:
        return True, None
    return True, selected if isinstance(selected, ast.Constant) else None


#: One `%` conversion specifier, in the shape the language defines it:
#: ``%[(name)][flags][width][.precision][length]conversion``. WR-02: `%`-with-a
#: -tuple is the dominant hint shape in `crayon`, and until this regex existed
#: the collector had no way to tell a format string's operands apart — it
#: joined the template and every literal beneath it with a newline, so a flag
#: carried by an operand landed on its own line and the gate at
#: :meth:`test_s13_every_flag_a_hint_offers_is_registered_on_that_verb`, which
#: reads only up to the first newline, never saw it.
_PERCENT_SPEC = re.compile(
    r"%(?:\((?P<name>[^)]*)\))?"
    r"(?P<flags>[-+ #0]*)"
    r"(?P<width>\*|\d+)?"
    r"(?:\.(?P<precision>\*|\d+))?"
    r"[hlL]?"
    r"(?P<conv>[diouxXeEfFgGcrsa%])"
)


def _percent_operands(node):
    """``(positional, mapping)`` for a ``%`` expression's right-hand operand.

    ``mapping`` is a dict only when the operand is a literal dict whose keys
    are all constants — the only shape whose named specifiers can be resolved
    without running the program. Everything else is positional, which for a
    bare (non-tuple) operand means the single value Python itself would
    substitute.
    """
    right = node.right
    if isinstance(right, ast.Dict):
        if not all(isinstance(key, ast.Constant) for key in right.keys):
            return [], None
        return [], {key.value: value for key, value in zip(right.keys, right.values)}
    if isinstance(right, ast.Tuple):
        return list(right.elts), None
    return [right], None


def _percent_format(template, node, render):
    """``template`` with each specifier replaced by the operand it consumes.

    Returns ``None`` when the specifiers and the operands cannot be paired —
    a ``*`` width, a named specifier with no literal mapping, a count that
    does not match. WR-02/WR-03: pairing is the whole point. An operand that
    NO specifier consumes is never substituted at runtime, so it is not text
    the operator can read, and collecting it is how an unreferenced dict value
    came to qualify an adoption offer the operator was shown unqualified.
    """
    positional, mapping = _percent_operands(node)
    out, index, cursor = [], 0, 0
    for match in _PERCENT_SPEC.finditer(template):
        out.append(template[cursor:match.start()])
        cursor = match.end()
        if match.group("conv") == "%":
            out.append("%")
            continue
        if "*" in ((match.group("width") or "") + (match.group("precision") or "")):
            return None
        name = match.group("name")
        if name is not None:
            if mapping is None or name not in mapping:
                return None
            operand = mapping[name]
        else:
            if mapping is not None or index >= len(positional):
                return None
            operand = positional[index]
            index += 1
        out.append(render(operand) or "<value>")
    out.append(template[cursor:])
    if mapping is None and index != len(positional):
        return None
    return "".join(out)


def _literal_text(node, constants, choice=None):
    """Collect visible literal prose, including module string constants.

    This collector alone is not a completeness check. _hint_gaps rejects
    unresolved expressions before tests may rely on the collected text.

    ``choice`` maps an IfExp or BoolOp's identity to its selected branch. With no
    choice every branch is collected, which is the right answer for "does this
    text exist anywhere" and the wrong one for "is this true of what the
    operator reads" — see :func:`_literal_variants`.
    """
    parts = []
    choice = choice or {}

    def visit(child):
        lookup, selected = _module_lookup(child, constants)
        if lookup:
            if selected is not None:
                visit(selected)
            return
        if isinstance(child, ast.IfExp) and id(child) in choice:
            visit(child.body if choice[id(child)] else child.orelse)
            return
        if isinstance(child, ast.BoolOp) and id(child) in choice:
            visit(child.values[choice[id(child)]])
            return
        # Composition is not a command boundary. Keep literal newlines, but
        # never invent one between an f-string's verb, dynamic unit and flag,
        # or between the operands of string concatenation (WR-03).
        if isinstance(child, ast.JoinedStr):
            parts.append("".join(
                (_literal_text(value.value, constants, choice) or "<value>")
                if isinstance(value, ast.FormattedValue)
                else _literal_text(value, constants, choice)
                for value in child.values
            ))
            return
        if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add):
            parts.append(_literal_text(child.left, constants, choice)
                         + _literal_text(child.right, constants, choice))
            return
        # WR-02/WR-03: `%` is assembled in ORDER, like the two arms above, and
        # only the operands its specifiers actually consume are read. The
        # generic walk below joined the template and every literal underneath
        # it with a newline, which both split a command from the flag its own
        # operand carried and credited the site with prose no run ever emits.
        # When the pairing cannot be made the union below is still the honest
        # answer — but that shape does not occur for `%s`/`%(name)s` with a
        # literal tuple or dict, which is every hint in `crayon`.
        if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Mod):
            rendered = _percent_format(
                _literal_text(child.left, constants, choice),
                child,
                lambda operand: _literal_text(operand, constants, choice),
            )
            if rendered is not None:
                parts.append(rendered)
                return
        # A Subscript's KEY is not text the operator ever sees: `found["hint"]`
        # is a forwarder reading a dict, and counting `hint` as prose would make
        # the fail-closed assertion below fire on the three sites it exists to
        # let through.
        if isinstance(child, ast.Subscript):
            visit(child.value)
            return
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            parts.append(child.value)
            return
        if isinstance(child, ast.Name) and child.id in constants:
            parts.append(constants[child.id])
            return
        for grandchild in ast.iter_child_nodes(child):
            visit(grandchild)

    if node is None:
        return ""
    visit(node)
    return "\n".join(parts)


#: Guard on the branch enumeration below, counted over EVERY node
#: :func:`_literal_variants` enumerates — conditionals and short-circuits
#: both. Eight of them is 256 variants; a hint expression with more than that
#: has stopped being readable prose.
#:
#: WR-05 (iteration 9): the guard used to count `ast.IfExp` alone while
#: `branches` already held `ast.BoolOp` nodes too, with two consequences. The
#: comment no longer bounded the enumeration — `itertools.product` ran over
#: both kinds, and 8 IfExps + 11 BoolOps is 524,288 emissions for ONE site —
#: and, worse, above the ceiling the function fell back to a plain
#: `_literal_text`, so every BoolOp silently collapsed into the union that
#: iteration-8's WR-04 fix exists to prevent, disabled by a condition that has
#: nothing to do with BoolOps and reported by nothing. Over the ceiling is now
#: an analysis GAP: `test_s13_unreadable_reason_or_hint_fails_closed` refuses
#: the site rather than quietly crediting it with prose no branch emits. The
#: worst real hint in `crayon` carries 3.
_MAX_BRANCHED_HINT = 8


def _enumerable_branches(node):
    """Every node :func:`_literal_variants` resolves one way at a time."""
    if node is None:
        return []
    return [n for n in ast.walk(node) if isinstance(n, (ast.IfExp, ast.BoolOp))]


def _bool_choices(node, constants):
    """Operands a short-circuit expression could return, in evaluation order.

    Known literal truthiness removes unreachable operands. Unknown data can
    return its own value or continue; each possibility stays a separate
    emission, so a short-circuit's operands never qualify each other's prose.

    WR-03 (iteration 9): that claim is about THIS construct, and used to be
    written as though it were about the collector. A union still forms
    wherever :func:`_literal_text` reads more than one operand of an
    expression it cannot resolve — which is why `%` formatting is resolved by
    substitution (WR-02) rather than by collecting every literal beneath it.
    """
    choices = []
    for index, value in enumerate(node.values):
        if index == len(node.values) - 1:
            choices.append(index)
            break
        lookup, selected = _module_lookup(value, constants)
        if lookup:
            value = selected
        elif isinstance(value, ast.Name):
            value = constants.values.get(value.id)
        truth = bool(value.value) if isinstance(value, ast.Constant) else None
        stops = truth if isinstance(node.op, ast.Or) else (not truth if truth is not None else None)
        if stops is not False:
            choices.append(index)
        if stops is True:
            break
    return choices


def _literal_variants(node, constants):
    """Every text this expression can actually EMIT, one per branch taken.

    WR-02(a). :func:`_literal_text` collects the union of an expression's
    literals, so a site was credited with wording that only one branch emits.
    ``escape_hint`` returned ``otherwise`` verbatim below two attempts, and the
    blocker-removal sentence ``test_s13_resume_hints_name_blocker_removal``
    accepted as proof was absent from the string actually printed — at the
    commonest attempt count there is.

    Enumerated by resolving each ``IfExp`` both ways and each ``BoolOp`` to
    the operands its truthiness permits, including inside formatting. Nothing
    rewrites the tree, and a nested conditional collapses into the same set.
    """
    if node is None:
        return [""]
    branches = _enumerable_branches(node)
    if len(branches) > _MAX_BRANCHED_HINT:
        # The union, and `refusal_sites` raises a gap for it — never a silent
        # fallback that looks like a resolved emission (WR-05).
        return [_literal_text(node, constants)]
    variants = set()
    options = [(False, True) if isinstance(n, ast.IfExp) else _bool_choices(n, constants)
               for n in branches]
    for values in itertools.product(*options):
        choice = {id(branch): value for branch, value in zip(branches, values)}
        variants.add(_literal_text(node, constants, choice))
    return sorted(variants)


def _calls_in(node):
    """The names of the functions this expression calls, at any depth."""
    if node is None:
        return frozenset()
    return frozenset(
        child.func.id
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
    )


def _hint_gaps(node, constants, helper=None, bindings=None):
    """Reject prose expressions the text walk cannot inspect.

    Formatting data may use these existing renderers/accessors. A new prose
    helper is not a renderer: it must gain an explicit analysis rule. In
    particular, wrapping it in escape_hint or adding a literal cannot hide it.
    """
    bindings = bindings or {}
    renderers = {"len", "str", "ledger_label", "ledger_path", "pending_dir",
                 "os.path.relpath", "os.path.dirname", "os.fspath", "_first_line",
                 "self.prog.split"}

    def readable(node):
        """A name whose prose the walk resolves — a module string or collection."""
        return isinstance(node, ast.Name) and node.id in constants

    def data_gaps(value):
        gaps = []
        for child in ast.walk(value):
            lookup, selected = _module_lookup(child, constants)
            if lookup and selected is None:
                gaps.append("unreadable module lookup: " + ast.unparse(child))
            if isinstance(child, ast.Name):
                if child.id in bindings:
                    gaps.extend(_hint_gaps(bindings[child.id], constants))
                elif constants.opaque(child.id):
                    # WR-01: a module-level name the walk cannot read whole.
                    # `", ".join(ADVICE_LINES)` used to be waved through as
                    # "data formatting" with ADVICE_LINES never read at all.
                    gaps.append("unreadable module reference: " + child.id)
            if not isinstance(child, ast.Call):
                continue
            name = ast.unparse(child.func)
            accessor = False
            if isinstance(child.func, ast.Attribute):
                receiver = child.func.value
                if child.func.attr == "get":
                    # `.get` is a data read ONLY on a payload dict a refusal
                    # already holds, or on a module collection `_literal_text`
                    # resolves. On anything else — a module dict of prose, an
                    # object, a call's result — the value is never read, which
                    # is how a hint that names `--adopt` with no precondition
                    # stayed invisible to every assertion below (WR-01).
                    accessor = readable(receiver) or (
                        isinstance(receiver, ast.Name)
                        and receiver.id in PAYLOAD_DICTS
                    )
                elif child.func.attr == "join":
                    # A literal separator only, and the joined expression is
                    # walked by this same loop — so a module name inside it is
                    # either resolved by `_literal_text` or a gap above.
                    accessor = isinstance(receiver, ast.Constant)
            if name not in renderers and not accessor:
                gaps.append("unreadable formatting call: " + name)
        return gaps

    if node is None:
        return []
    lookup, selected = _module_lookup(node, constants)
    if lookup:
        return ([] if selected is not None else
                ["unreadable module lookup: " + ast.unparse(node)])
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return []
    if isinstance(node, ast.Name):
        if node.id in bindings:
            return _hint_gaps(bindings[node.id], constants)
        if node.id in constants:
            return []
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Mod):
            return _hint_gaps(node.left, constants, helper, bindings) + data_gaps(node.right)
        if isinstance(node.op, ast.Add):
            return (_hint_gaps(node.left, constants, helper, bindings) +
                    _hint_gaps(node.right, constants, helper, bindings))
    if isinstance(node, ast.IfExp):
        return (_hint_gaps(node.body, constants, helper, bindings) +
                _hint_gaps(node.orelse, constants, helper, bindings))
    if isinstance(node, ast.BoolOp):
        return [gap for value in node.values for gap in
                _hint_gaps(value, constants, helper, bindings)]
    if isinstance(node, ast.JoinedStr):
        return [gap for value in node.values for gap in (
            data_gaps(value.value) if isinstance(value, ast.FormattedValue)
            else _hint_gaps(value, constants, helper, bindings)
        )]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == ESCAPE_BRANCH and helper is not None):
        otherwise = node.args[2] if len(node.args) > 2 else None
        for keyword in node.keywords:
            if keyword.arg == "otherwise":
                otherwise = keyword.value
        if otherwise is None or any(k.arg is None for k in node.keywords):
            return ["unreadable escape_hint arguments"]
        # Inspect the wrapper's returns too, not just its name. No recursive
        # wrapper exemption: a new call in its output fails closed.
        returns = [n.value for n in ast.walk(helper) if isinstance(n, ast.Return)]
        if not returns:
            return ["escape_hint has no readable return"]
        return [gap for value in returns for gap in
                _hint_gaps(value, constants, bindings={"otherwise": otherwise})]
    return ["unreadable hint expression: " + ast.unparse(node)]


#: A skill body's `<step_N …>` element, with or without attributes.
_STEP_OPEN = "<step_%d"


def skill_step_body(text, number):
    """The body of ``<step_N>``, or ``None`` when the skill has no such step.

    Phase-17 IN-03: the two call sites spelled this ``text.split("<step_9 ",
    1)[1]``, which raises ``IndexError`` — a test *error*, not a readable
    failure — the moment step 9 is written ``<step_9>`` with no attributes.
    A gate that ERRORS instead of failing tells the next reader nothing about
    what the skill was supposed to say.
    """
    match = re.search(r"<step_%d\b[^>]*>" % number, text)
    if match is None:
        return None
    rest = text[match.end() :]
    closing = "</step_%d>" % number
    return rest.split(closing, 1)[0] if closing in rest else rest


#: The keep path a batch that has ALREADY adopted must never be offered.
_BARE_RESUME = "`crayon resume <id>`"


def bare_resume_offers(text):
    """Sentences about an already-adopted batch that offer a BARE resume.

    Phase-17 IN-03: the negative this replaces pinned two literal phrases —
    ``offer the plain resume``, ``takes the plain resume`` — and any paraphrase
    of the same wrong advice walked past both. The property is about the
    ADVICE: contract 5.8 says a batch already carrying an adoption is completed
    by ``--adopt`` or ``--overwrite``, so no sentence about that case may name
    a bare ``crayon resume <id>`` as the keep path. The flagged forms are
    backticked whole, so ```crayon resume <id> --adopt``` never matches the
    bare spelling.
    """
    hits = []
    for sentence in re.split(r"(?<=[.;])\s+", " ".join(text.split())):
        low = sentence.lower()
        if "already" not in low or "adopt" not in low:
            continue
        if _BARE_RESUME in sentence:
            hits.append(sentence)
    return hits


# --- the hint-analysis gate, and where its review ends (D-16) ----------------
#
# What follows is an AST walk over Python string formatting: it resolves the
# text each `Refusal(...)`/`refuse(...)` site can actually EMIT and checks the
# operator-facing wording against the routing rows. Every deep review from
# iteration 8 onward found a new formatting shape that evaded it — f-string,
# `+` concatenation, `%`-tuple, `%`-dict, the branch ceiling — each fix closed
# that shape, and the next review found another.
#
# THE STOP-RULE. The space of Python formatting shapes that can evade an
# analyzer of this kind is unbounded by construction, so this class cannot
# converge through review/fix cycles: every round closes a shape and leaves the
# space the same size. Iteration 9 closed the shapes reported so far (commits
# b106d16, 6236063, 9d05347). From here, a newly IMAGINED evasion shape is
# out of scope and is not fixed. The one condition that reopens this
# gate for an analyzer rewrite is a real emitted hint
# slipping through in practice: an operator-facing string that actually
# reached a user while this walk called the site clean.
#
# So: do not send this gate another round of shape-by-shape hardening. Send it
# a hint that got out.


def refusal_sites(source=None):
    """Return sites, module strings, and explicit analysis gaps.

    Both positional and keyword arguments are bound. Only the three existing
    reason/hint forwarders are exempt from prose analysis, by their complete
    expression pair and enclosing function. Unknown shapes never disappear.
    """
    if source is None:
        source = (ROOT / "crayon.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    constants = _module_string_constants(tree)
    parents = {child: parent for parent in ast.walk(tree)
               for child in ast.iter_child_nodes(parent)}
    helper = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == ESCAPE_BRANCH), None)
    forwarders = {
        ("answer", "reason", "hint"),
        ("cmd_resume", "reason", "found['hint']"),
        ("main", "refusal.reason", "refusal.hint"),
    }
    sites, gaps = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        spec = _REFUSAL_CONSTRUCTORS.get(node.func.id)
        if spec is None:
            continue
        reason_index, hint_index = spec
        reason_node = node.args[reason_index] if len(node.args) > reason_index else None
        hint_node = node.args[hint_index] if hint_index is not None and len(node.args) > hint_index else None
        for keyword in node.keywords:
            if keyword.arg == "reason":
                reason_node = keyword.value
            elif keyword.arg == "hint":
                hint_node = keyword.value
        # answer(situation) without a reason or any refusal fields is a clean
        # classification. All other missing/computed reasons must be audited.
        if (node.func.id == "answer" and len(node.args) == 1
                and not node.keywords):
            continue
        reason = reason_node.value if isinstance(reason_node, ast.Constant) and isinstance(reason_node.value, str) else None
        parent = parents.get(node)
        while parent is not None and not isinstance(parent, ast.FunctionDef):
            parent = parents.get(parent)
        owner = parent.name if parent is not None else "<module>"
        forwarding = (owner, ast.unparse(reason_node) if reason_node else "",
                      ast.unparse(hint_node) if hint_node else "") in forwarders
        if reason is None and not forwarding:
            gaps.append((node.lineno, "unresolved reason or unrecognised forwarder"))
        if not forwarding:
            gaps.extend((node.lineno, gap) for gap in _hint_gaps(hint_node, constants, helper))
            # WR-05: past the ceiling `_literal_variants` cannot separate the
            # branches, so what it returns is the union — the one answer this
            # walk must never present as an emission. Say so instead.
            enumerable = len(_enumerable_branches(hint_node))
            if enumerable > _MAX_BRANCHED_HINT:
                gaps.append((
                    node.lineno,
                    "branched hint past the enumeration ceiling: %d conditional"
                    "/short-circuit nodes, ceiling %d"
                    % (enumerable, _MAX_BRANCHED_HINT),
                ))
        if any(k.arg is None for k in node.keywords) or any(isinstance(n, ast.Starred) for n in node.args):
            gaps.append((node.lineno, "unresolved expanded arguments"))
        hint = _literal_text(hint_node, constants)
        emissions = _literal_variants(hint_node, constants)
        if ESCAPE_BRANCH in _calls_in(hint_node) and helper is not None:
            returns = [n.value for n in ast.walk(helper) if isinstance(n, ast.Return)]
            hint += "\n" + "\n".join(_literal_text(n, constants) for n in returns)
            # WR-02(a): the CROSS PRODUCT, not the union. A site that calls the
            # wrapper emits one of its own branches joined to one of the
            # wrapper's, and the property has to hold of every such pair.
            wrapped = [
                text for n in returns for text in _literal_variants(n, constants)
            ]
            emissions = [own + "\n" + text for own in emissions for text in wrapped]
        sites.append(
            (node.lineno, node.func.id, reason, hint, _calls_in(hint_node), emissions)
        )
    return sites, constants, gaps


class TestS13RoutedTextIsInspectable(unittest.TestCase):
    """S-13 audits refusal expressions and necessary wording conditions."""

    @classmethod
    def setUpClass(cls):
        cls.sites, cls.constants, cls.gaps = refusal_sites()

    def test_s13_unreadable_reason_or_hint_fails_closed(self):
        self.assertEqual(self.gaps, [], "S-13 cannot inspect these refusal expressions")

    def test_s13_the_site_walk_is_not_vacuous(self):
        self.assertGreaterEqual(
            len(self.sites),
            MIN_REFUSAL_SITES,
            "the AST walk found only %d refusal sites in `crayon`; every S-13 "
            "assertion would be vacuously satisfied" % len(self.sites),
        )
        escapes = [s for s in self.sites if s[2] in ESCAPE_REASONS]
        self.assertGreaterEqual(
            len(escapes),
            MIN_ESCAPE_SITES,
            "the walk found only %d sites for %s; the reasons that route back "
            "into `crayon resume` are the whole point of S-13"
            % (len(escapes), ", ".join(ESCAPE_REASONS)),
        )
        for reason in ESCAPE_REASONS:
            with self.subTest(reason=reason):
                self.assertTrue(
                    any(site[2] == reason for site in self.sites),
                    "`crayon` no longer raises %r anywhere the walk can see; "
                    "either the reason went away or the walk did" % reason,
                )

    def test_s13_the_walk_sees_every_reason_the_regex_extractor_sees(self):
        """Two independent extractors, held to each other.

        S-11 reads ``raise Refusal(`` blocks with a regex; S-13 reads the AST.
        A reason only one of them can see is a hole in the other, and a hole is
        exactly how this defect survived three fixes.
        """
        ast_reasons = {site[2] for site in self.sites if site[2]}
        # Scoped to contract 5.7's reason table on the regex side: that
        # extractor takes the first quoted token in the block, which on a
        # forwarder is the dict key it reads (`found["detail"]`) rather than a
        # reason. The claim is about reasons, so it is made about reasons.
        regex_reasons = set(refusal_blocks()) & set(contract_reasons())
        missing = sorted(regex_reasons - ast_reasons)
        self.assertEqual(
            missing,
            [],
            "S-11's regex extractor sees reasons the S-13 AST walk does not: "
            "%s — the walk's constructor list is incomplete" % missing,
        )

    def test_s13_a_site_with_a_computed_reason_writes_no_hint_of_its_own(self):
        """Fail closed: a forwarder may forward, it may not compose.

        Three sites re-raise a reason they were handed — ``answer``'s funnel,
        ``resume``'s stage-a forward and ``main``'s printer. Their hints are
        arguments, so the text they carry is checked at the site that WROTE it.
        A new site with a computed reason AND text of its own would be invisible
        to every assertion below, so it is a failure here rather than a silent
        gap.
        """
        for line, func, reason, hint, _calls, _emitted in self.sites:
            if reason is not None:
                continue
            with self.subTest(line=line, constructor=func):
                self.assertEqual(
                    hint,
                    "",
                    "crayon:%d builds a hint under a reason S-13 cannot resolve, "
                    "so no assertion below can hold it to the escape property. "
                    "Raise the reason as a literal, or hand the hint in." % line,
                )

    def test_s13_no_hint_offers_a_note_on_an_accept(self):
        """WR-09: an accept's note is optional, so no hint writes one in unbracketed."""
        checked = 0
        for line, _func, _reason, _hint, _calls, emitted in self.sites:
            for hint in emitted:
                if "--verdict accept" not in hint:
                    continue
                checked += 1
                with self.subTest(line=line):
                    self.assertNotRegex(hint, r"--verdict accept --note")
        self.assertGreater(checked, 0, "no hint names an accept: the check is vacuous")

    def test_s13_every_flag_a_hint_offers_is_registered_on_that_verb(self):
        per_verb, shared, _unbound = walk_verb_flags()
        checked = 0
        for line, _func, _reason, _hint, _calls, emitted in self.sites:
            for hint in emitted:
                # Stop at the next command, so its flags belong to its verb.
                commands = list(re.finditer(r"crayon ([a-z][a-z-]*)\b", hint))
                for index, command in enumerate(commands):
                    end = commands[index + 1].start() if index + 1 < len(commands) else len(hint)
                    rest = hint[command.end():end].split("\n", 1)[0]
                    verb = command.group(1)
                    for flag in re.findall(r"--[a-z][a-z-]+", rest):
                        checked += 1
                        with self.subTest(line=line, verb=verb, flag=flag):
                            self.assertIn(flag, per_verb.get(verb, set()) | set(shared))
        self.assertGreater(checked, 10, "the hint flag check must not be vacuous")

    def test_s13_a_constant_cannot_smuggle_an_unqualified_adopt(self):
        """The resolver's own back door, closed.

        ``_literal_text`` resolves module-level string constants so a hint that
        carries its precondition by reference passes. The same resolution would
        let a constant carry `--adopt` WITHOUT one, so the constants are held to
        the property directly.
        """
        for name, text in sorted(self.constants.items()):
            if "--adopt" not in text:
                continue
            lowered = text.lower()
            for marker in ADOPT_PRECONDITION_MARKERS:
                with self.subTest(constant=name, marker=marker):
                    self.assertIn(marker, lowered)

    def test_s13_resume_hints_name_blocker_removal(self):
        """A structural requirement; N-46 tests whether the routes work.

        WR-02(a): asserted over each EMISSION, not over their union. The walk
        used to append ``escape_hint``'s literal returns to every site that
        called it, unconditionally — while the helper returned ``otherwise``
        verbatim below two attempts, so the sentence this test accepted as
        proof was missing from the string the operator read on a first-attempt
        refusal. Membership of ``calls`` is no longer proof of anything: the
        wrapper's own text has to carry the escape down every branch.
        """
        for line, _func, reason, _hint, _calls, emitted in self.sites:
            if reason not in ESCAPE_REASONS:
                continue
            for text in emitted:
                if "crayon resume " not in text:
                    continue  # offers no command: nothing to loop through
                with self.subTest(line=line, reason=reason, emitted=text[:60]):
                    self.assertIn(
                        TERMINATING_ESCAPE,
                        text.lower(),
                        "crayon:%d raises %s and one of the strings it can "
                        "actually emit names `crayon resume` without naming the "
                        "escape that always works (%r). On a batch git has "
                        "already refused, every resume re-places the same "
                        "bytes and meets the same refusal — which is the loop "
                        "CR-01 has been filed for four times."
                        % (line, reason, TERMINATING_ESCAPE),
                    )

    #: Mentions are exempt only when they explicitly disclaim this escape.
    _ADOPT_DISCLAIMER = "`--adopt` is not an answer here"

    def test_s13_every_emission_that_offers_adopt_states_its_precondition(self):
        """CR-02 / WR-02(a) — per emission, not per union.

        A string the operator can actually read that offers the command must carry the
        conditions the tool applies, even when a SIBLING branch of the same
        expression carries them.
        """
        offers = 0
        for line, _func, _reason, _hint, _calls, emitted in self.sites:
            for text in emitted:
                if "--adopt" not in text or self._ADOPT_DISCLAIMER in text:
                    continue
                offers += 1
                lowered = text.lower()
                for marker in ADOPT_PRECONDITION_MARKERS:
                    with self.subTest(line=line, marker=marker):
                        self.assertIn(
                            marker,
                            lowered,
                            "crayon:%d can emit a string that offers `--adopt` "
                            "without saying %r" % (line, marker),
                        )
        self.assertTrue(offers, "no emitted string in `crayon` offers `--adopt`")

    def test_s13_the_shared_escape_branch_is_intact(self):
        """The wrapper's shape, not two substrings of its source.

        WR-02(b): this used to assert only that the source segment CONTAINED
        ``transition_attempts`` and the escape phrase. A body comparing the
        counter to ``10**9``, or one that dropped ``otherwise`` from a return,
        satisfied both and turned the helper into a no-op — while every site
        that calls it is credited with its text. The three things that matter
        are asserted as structure: the counter is compared to ONE, the
        caller's remedy survives every return, and the escape is in every
        string the helper can emit.
        """
        source = (ROOT / "crayon.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        found = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == ESCAPE_BRANCH
        ]
        self.assertEqual(
            len(found),
            1,
            "`crayon` must define exactly one %s(); found %d"
            % (ESCAPE_BRANCH, len(found)),
        )
        helper = found[0]
        body = ast.get_source_segment(source, helper)
        self.assertIn("transition_attempts", body)

        comparisons = [n for n in ast.walk(helper) if isinstance(n, ast.Compare)]
        self.assertTrue(
            any(
                isinstance(operand, ast.Constant) and operand.value == 1
                for comparison in comparisons
                for operand in comparison.comparators
            ),
            "%s() no longer compares the attempt counter to the literal 1. A "
            "threshold of 10**9 leaves the source substrings in place and the "
            "history clause unreachable." % ESCAPE_BRANCH,
        )

        returns = [n.value for n in ast.walk(helper) if isinstance(n, ast.Return)]
        self.assertTrue(returns, "%s() has no readable return" % ESCAPE_BRANCH)
        for value in returns:
            names = {
                n.id for n in ast.walk(value) if isinstance(n, ast.Name)
            }
            with self.subTest(line=value.lineno):
                self.assertIn(
                    "otherwise",
                    names,
                    "a return of %s() drops the caller's own remedy; removing "
                    "a hook does not reset history, so the remedy has to "
                    "survive every count" % ESCAPE_BRANCH,
                )
            for text in _literal_variants(value, self.constants):
                with self.subTest(line=value.lineno, emitted=text[:60]):
                    self.assertIn(
                        TERMINATING_ESCAPE,
                        text.lower(),
                        "%s() can return a string that does not name the "
                        "escape that always works; every calling site is "
                        "credited with that sentence" % ESCAPE_BRANCH,
                    )

    def test_s13_every_row_that_names_adopt_states_its_precondition(self):
        """The surface half — S-04 tells every body to act on the ROW.

        ``crayon-review/SKILL.md`` step_9 stated the precondition in prose, which
        is why CR-02's blast radius was one skill. The row is what every body is
        told to act on, and the ``resume_ambiguous`` row offered `--adopt`
        unconditionally. Asserted over every row rather than over a named one.
        """
        reason_rows, token_rows = routing_signals()
        rows = [("reasons", s) for s in reason_rows] + [
            ("tokens", s) for s in token_rows
        ]
        named = 0
        for block, signal in rows:
            row = routing_row(signal, block=block)
            if "--adopt" not in row:
                continue
            named += 1
            for marker in ADOPT_PRECONDITION_MARKERS:
                with self.subTest(block=block, signal=signal, marker=marker):
                    self.assertIn(
                        marker, row.lower(),
                        "the %s row for %s omits adoption condition %r"
                        % (block, signal, marker),
                    )
        self.assertGreaterEqual(
            named, 3, "only %d routing rows name `--adopt`" % named
        )

    def test_s13_review_recovery_steps_require_current_bytes(self):
        text = (SKILLS_ROOT / "crayon-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for step in (9, 10):
            body = skill_step_body(text, step)
            if body is None:
                self.fail("crayon-review/SKILL.md has no <step_%d> element" % step)
            for marker in ADOPT_PRECONDITION_MARKERS:
                with self.subTest(step=step, marker=marker):
                    self.assertIn(marker, body.lower())
            with self.subTest(step=step, count=True):
                self.assertNotIn("all three conditions", body)

    def test_s13_already_adopted_completion_names_the_flagged_command(self):
        row = routing_row("resume_ambiguous")
        skill = (SKILLS_ROOT / "crayon-review" / "SKILL.md").read_text(encoding="utf-8")
        step = skill_step_body(skill, 9)
        if step is None:
            self.fail("crayon-review/SKILL.md has no <step_9> element")
        for text in (row, step):
            text = " ".join(text.split())
            with self.subTest(text=text[:50]):
                self.assertIn('`crayon resume <id> --adopt`', text)
                self.assertIn('`crayon resume <id> --overwrite`', text)
                self.assertIn('only with no `unexpected` files', text)
                # IN-03 (phase 17): the negative is about the ADVICE, not about
                # the two phrasings of it this used to pin.
                self.assertEqual(
                    bare_resume_offers(text),
                    [],
                    "a bare `crayon resume <id>` is offered for a batch that "
                    "already carries an adoption",
                )
        # The actionable column must include the no-note completion command.
        self.assertIn('`crayon resume <id> --adopt`', row.rsplit('|', 2)[1])
        # WR-01 (iteration 9): the tool's own constant is the third mirror of
        # this row, not a private comment. `ADOPT_PRECONDITION` is interpolated
        # verbatim into the `resume_ambiguous`, `recovery_unsupported` and
        # `--note`-without-`--adopt` hints — the strings the routing rows tell
        # the skills to relay word for word — so it said "a batch already
        # carrying one adoption ... is a plain resume" while the row said a
        # bare resume is unavailable there. Pinned on the clause rather than on
        # the whole constant, because the UNCHANGED-bytes case IS a plain
        # resume and that sentence must survive.
        precondition = " ".join(self.constants["ADOPT_PRECONDITION"].split())
        self.assertIn("already carrying one adoption", precondition)
        adopted_clause = precondition.split("already carrying one adoption", 1)[1]
        self.assertNotIn(
            "plain resume",
            adopted_clause,
            "ADOPT_PRECONDITION still calls the already-adopted case a plain "
            "resume; a bare `crayon resume <id>` exits 6 resume_ambiguous there",
        )
        for phrase in (
            "repeated `--adopt`",
            "appends no event",
            "records no note",
            "restores the saved adoption bytes",
            "refuses `resume_ambiguous`",
            "while any file is still `unexpected`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, adopted_clause)

    def test_s13_contract_post_commit_notices_are_not_promised_on_a_refusal(self):
        """5.8 must not claim stderr prose or drift notices on the refusal arm.

        Iteration 10 (WR-02): the text said post-commit notices arrive as
        stderr prose "either way", but a refusal is one JSON line on stderr and
        the drift / derivation notices exist only after a landed commit
        (``tests/test_crayon_lifecycle.sh`` pins both). Pin the corrected claim.
        """
        text = " ".join(CONTRACT.read_text(encoding="utf-8").split())
        self.assertNotIn("as stderr prose either way", text)
        self.assertIn("stderr prose after a success", text)
        self.assertIn("travel with the success outcome alone", text)

    def test_s13_every_row_that_names_overwrite_names_the_escape(self):
        """Overwrite advice must account for a blocker that may remain."""
        reason_rows, token_rows = routing_signals()
        rows = [("reasons", s) for s in reason_rows] + [
            ("tokens", s) for s in token_rows
        ]
        named = 0
        for block, signal in rows:
            row = routing_row(signal, block=block)
            if "--overwrite" not in row:
                continue
            named += 1
            with self.subTest(block=block, signal=signal):
                self.assertIn(
                    TERMINATING_ESCAPE,
                    row.lower(),
                    "the %s row for %s offers `--overwrite` and never names "
                    "the escape that works when git has already refused the "
                    "batch" % (block, signal),
                )
        self.assertGreaterEqual(
            named, 2, "only %d routing rows name `--overwrite`" % named
        )


class TestS13WalkControls(unittest.TestCase):
    def test_keyword_reasons_are_inspected_for_every_constructor(self):
        for call in ('Refusal(reason="adopt_unsupported", hint="unsafe")',
                     'refuse(reason="adopt_unsupported", hint="unsafe")',
                     'answer(situation="broken", reason="adopt_unsupported", hint="unsafe")'):
            with self.subTest(call=call):
                sites, _, _ = refusal_sites(call)
                self.assertEqual([s[2] for s in sites], ["adopt_unsupported"])

    def test_computed_hints_cannot_hide_at_any_depth(self):
        source = (ROOT / "crayon.py").read_text(encoding="utf-8")
        helper = source.split("def escape_hint(", 1)[1].split(
            "def refuse_transition(", 1
        )[0]
        for hint in ("advice(unit)", "advice", '"inspect " + advice(unit)',
                     '"%s" % advice(unit)', 'f"inspect {advice(unit)}"',
                     "escape_hint(repo, unit, advice(unit))",
                     "escape_hint(repo, unit, otherwise=advice(unit))",
                     "escape_hint(repo, unit, advice)", "obj.advice(unit)"):
            with self.subTest(hint=hint):
                source = "def escape_hint(" + helper + '\nRefusal("adopt_unsupported", hint=' + hint + ')'
                _, _, gaps = refusal_sites(source)
                self.assertTrue(gaps, "unreadable hint silently accepted: " + hint)

    def test_positional_hints_are_inspected_for_every_constructor(self):
        for call in ('Refusal("adopt_unsupported", unit, detail, advice(unit))',
                     'refuse("adopt_unsupported", unit, detail, advice(unit))',
                     'answer("broken", "adopt_unsupported", detail, advice(unit))'):
            with self.subTest(call=call):
                _, _, gaps = refusal_sites(call)
                self.assertTrue(gaps, "positional hint silently accepted: " + call)

    def test_the_escape_wrapper_cannot_hide_a_new_prose_helper(self):
        source = ("def escape_hint(repo, unit, otherwise):\n"
                  "    return advice(unit)\n"
                  'Refusal("adopt_unsupported", hint=escape_hint(repo, unit, "inspect"))')
        _, _, gaps = refusal_sites(source)
        self.assertTrue(gaps, "the wrapper's name is not proof of inspectability")

    #: WR-01's mutation, verbatim: a fourth `adopt_unsupported` arm whose prose
    #: lives in a module-level dict. Before the fix the `renderers` allowlist
    #: classified `ADVICE.get(...)` as data formatting, the value was never
    #: read, and this arm named `--adopt` with no precondition and
    #: `--overwrite` with no blocker-removal advice while the suite stayed
    #: green at 83 tests OK.
    LOOKUP_MUTATION = (
        'ADVICE = {"overwrite": "crayon resume %s --overwrite places the '
        "intended bytes; crayon resume %s --adopt --note '<why>' keeps them\"}\n"
        'Refusal("adopt_unsupported", unit=unit, detail="too many adopted '
        'files", hint="%s" % (ADVICE.get("overwrite") % (unit, unit)), '
        'next_token="resume")\n'
    )

    def test_prose_behind_a_module_dict_lookup_is_read_not_waved_through(self):
        sites, _constants, gaps = refusal_sites(self.LOOKUP_MUTATION)
        self.assertEqual(gaps, [], "the lookup is resolvable, so it is no gap")
        self.assertEqual(len(sites), 1)
        hint = sites[0][3]
        self.assertIn("--adopt", hint, "the dict's prose was never read")
        # And, read, it is held to the property CR-02 filed: this arm states no
        # precondition, so the S-13 assertion over `--adopt` hints must fire.
        missing = [m for m in ADOPT_PRECONDITION_MARKERS if m not in hint.lower()]
        self.assertTrue(
            missing,
            "the mutation is supposed to be an UNQUALIFIED offer; if it now "
            "states the precondition it has stopped being a negative control",
        )

    def test_a_sibling_lookup_value_cannot_qualify_an_offer(self):
        offer = "crayon resume %s --adopt --note '<why>' keeps them"
        qualified = " ".join(ADOPT_PRECONDITION_MARKERS)
        for expression in ('ADVICE.get("overwrite")', 'ADVICE["overwrite"]'):
            with self.subTest(expression=expression):
                source = ('ADVICE = %r\nRefusal("adopt_unsupported", hint="%%s" %% (%s %% unit))'
                          % ({"overwrite": offer, "manual": qualified}, expression))
                sites, _, gaps = refusal_sites(source)
                self.assertEqual(gaps, [])
                # WR-02: the operands are SUBSTITUTED now, so the emission is
                # the line the operator reads rather than the template and its
                # operands stacked on separate lines.
                self.assertEqual(
                    sites[0][5], [offer.replace("%s", "<value>")]
                )
                self.assert_rejects_unqualified_emission(sites)

    def test_computed_lookup_keys_fail_closed(self):
        for expression in ('ADVICE.get(key)', 'ADVICE[key]'):
            with self.subTest(expression=expression):
                _, _, gaps = refusal_sites(
                    'ADVICE = {"offer": "unsafe", "manual": "qualified"}\n'
                    'Refusal("adopt_unsupported", hint="%%s" %% %s)' % expression
                )
                self.assertTrue(gaps)

    def test_short_circuit_fallback_cannot_qualify_an_offer(self):
        advice = {
            "offer": "crayon resume %s --adopt --note x keeps them",
            "manual": " ".join(ADOPT_PRECONDITION_MARKERS) + " " + TERMINATING_ESCAPE,
        }
        for expression in (
            'ADVICE["offer"] or ADVICE["manual"]',
            '(ADVICE["offer"] or ADVICE["manual"]) % unit',
            '"%s" % ((ADVICE["offer"] or ADVICE["manual"]) % unit)',
            'f"{(ADVICE[\'offer\'] or ADVICE[\'manual\']) % unit}"',
        ):
            with self.subTest(expression=expression):
                sites, _, gaps = refusal_sites(
                    'ADVICE = %r\nRefusal("adopt_unsupported", hint=%s)' % (advice, expression)
                )
                self.assertEqual(gaps, [])
                self.assert_rejects_unqualified_emission(sites)
                self.assertTrue(all(advice["manual"] not in text for text in sites[0][5]))
        # Removing the never-emitted fallback keeps the hint unsafe; now it
        # is inspectable and must be rejected by the per-emission gate.
        sites, _, gaps = refusal_sites(
            'ADVICE = %r\nRefusal("adopt_unsupported", hint="%%s" %% (ADVICE["offer"] %% unit))'
            % advice
        )
        self.assertEqual(gaps, [])
        self.assert_rejects_unqualified_emission(sites)

    def test_an_unreferenced_format_operand_cannot_qualify_an_offer(self):
        """WR-03: a mapping value no specifier names is never emitted.

        ``%(name)s`` with an extra key is valid Python: it substitutes the
        keys the format string references and ignores the rest. The collector
        used to read every literal beneath the `%` expression, so an operand
        no run ever substitutes qualified an offer the operator was shown
        UNQUALIFIED — iteration-8 WR-04's defect in the shape that fix did not
        touch. The three mappings below must all emit the same text and all be
        rejected: a suite that fails only for the one without a decoy is
        asserting over the decoy, not over what the operator reads.
        """
        dead = " ".join(ADOPT_PRECONDITION_MARKERS) + " " + TERMINATING_ESCAPE
        template = '"crayon resume %(u)s --adopt --note x keeps them"'
        for mapping in (
            '{"u": unit, "dead": ' + repr(dead) + "}",
            '{"dead": ' + repr(dead) + ', "u": unit}',
            '{"u": unit}',
        ):
            with self.subTest(mapping=mapping[:24]):
                sites, _constants, gaps = refusal_sites(
                    'Refusal("adopt_unsupported", hint='
                    + template + " % " + mapping + ")"
                )
                self.assertEqual(gaps, [])
                self.assertEqual(
                    sites[0][5],
                    ["crayon resume <value> --adopt --note x keeps them"],
                )
                self.assertTrue(all(dead not in text for text in sites[0][5]))
                self.assert_rejects_unqualified_emission(sites)

    def test_short_circuit_variants_follow_truthiness(self):
        for expression, expected in (
            ('TEXT["empty"] or TEXT["a"] or TEXT["b"]', ["A"]),
            ('TEXT["a"] and TEXT["b"]', ["B"]),
            ('TEXT["empty"] and TEXT["b"]', [""]),
            # WR-02: one variant per operand the `or` can return, each
            # substituted into the template — `<value>` where the operand is
            # data the walk cannot read.
            ('"%s" % (dynamic or TEXT["a"])', ["<value>", "A"]),
        ):
            with self.subTest(expression=expression):
                sites, _, gaps = refusal_sites(
                    'TEXT = {"empty": "", "a": "A", "b": "B"}\n'
                    'Refusal("bad_target", hint=' + expression + ')'
                )
                self.assertEqual(gaps, [])
                self.assertEqual(sites[0][5], expected)

    def test_a_hint_past_the_enumeration_ceiling_is_a_gap_not_a_union(self):
        """WR-05: the ceiling counts every enumerated node and overflow says so.

        The guard used to count `IfExp` alone, so adding conditionals — which
        have nothing to do with a short-circuit — silently switched every
        `BoolOp` back to the union iteration-8's WR-04 fix removed, with
        nothing reporting it. Both halves are pinned here: at the ceiling the
        separation still holds, and one node past it the site is a GAP rather
        than a union wearing an emission's clothes.
        """
        offer = "crayon resume %s --adopt --note x keeps them"
        manual = " ".join(ADOPT_PRECONDITION_MARKERS) + " " + TERMINATING_ESCAPE

        def source(conditionals):
            return (
                "ADVICE = %r\n" % {"offer": offer, "manual": manual}
                + 'Refusal("adopt_unsupported", hint=('
                + " + ".join(['("" if unit else "")'] * conditionals)
                + ' + ((ADVICE["offer"] or ADVICE["manual"]) % unit)))'
            )

        # The one BoolOp plus _MAX_BRANCHED_HINT - 1 conditionals sits exactly
        # ON the ceiling: still enumerated, so the never-emitted fallback
        # cannot qualify the offer.
        sites, _constants, gaps = refusal_sites(source(_MAX_BRANCHED_HINT - 1))
        self.assertEqual(gaps, [])
        self.assertTrue(all(manual not in text for text in sites[0][5]))
        self.assert_rejects_unqualified_emission(sites)

        # One node more and the enumeration gives up. What it returns is the
        # union — which is why it has to be reported rather than believed.
        sites, _constants, gaps = refusal_sites(source(_MAX_BRANCHED_HINT))
        self.assertTrue(
            any("enumeration ceiling" in gap for _line, gap in gaps),
            "a hint past the ceiling must fail closed as an analysis gap: the "
            "ceiling counts conditionals AND short-circuits, and what the walk "
            "returns above it is the union",
        )
        self.assertEqual(len(sites[0][5]), 1)
        self.assertIn(
            manual,
            sites[0][5][0],
            "the overflow fallback IS the union; if it ever stops being one "
            "this control has stopped testing the thing it was written for",
        )

    def test_computed_flag_lookups_cannot_hide_prose_in_a_default(self):
        _, _, gaps = refusal_sites(
            'FLAGS = {"title": "--title"}\n'
            'Refusal("adopt_unsupported", hint="%s" % '
            'FLAGS.get(key, "crayon resume u --adopt"))'
        )
        self.assertTrue(gaps)

    def test_hint_flags_are_checked_on_the_named_verb(self):
        for hint in ("crayon resume u --discard", "crayon show u --re-sign"):
            with self.subTest(hint=hint):
                sites, _, gaps = refusal_sites('Refusal("example", hint=%r)' % hint)
                self.assertEqual(gaps, [])
                gate = TestS13RoutedTextIsInspectable(
                    "test_s13_every_flag_a_hint_offers_is_registered_on_that_verb"
                )
                gate.sites = sites * 11  # satisfy the scan floor independently
                result = unittest.TestResult()
                gate.run(result)
                self.assertTrue(result.failures)
                self.assertEqual(result.errors, [])
                self.assertIn(hint.split()[-1], result.failures[0][1])

    def test_composed_hint_flags_reach_the_actual_gate(self):
        for expression in (
            'f"crayon resume {unit} --discard"',
            '"crayon resume %s" % unit + " --discard"',
            'f"crayon show {unit} --re-sign"',
            # WR-02: `%` with a tuple, and `%(name)s` with a mapping. These
            # are the shapes `crayon` itself uses everywhere — the two above
            # are the rare ones — and until the collector substituted them the
            # flag landed on a line of its own, past the `split("\n", 1)[0]`
            # the gate below reads. Both forms went green with `--discard`
            # offered on `resume`.
            '"crayon resume %s %s" % (unit, "--discard")',
            '"crayon resume %(u)s %(f)s" % {"u": unit, "f": "--discard"}',
            '"crayon show %s %s" % (unit, "--re-sign")',
        ):
            with self.subTest(expression=expression):
                sites, _, gaps = refusal_sites(
                    'Refusal("bad_target", hint=' + expression + ')'
                )
                self.assertEqual(gaps, [])
                self.assertNotIn("\n", sites[0][5][0])
                gate = TestS13RoutedTextIsInspectable(
                    "test_s13_every_flag_a_hint_offers_is_registered_on_that_verb"
                )
                gate.sites = sites * 11
                result = unittest.TestResult()
                gate.run(result)
                self.assertTrue(result.failures, "composed invalid flag passed the real gate")
                self.assertEqual(result.errors, [])

    def test_composed_valid_flags_and_real_newlines_are_preserved(self):
        for expression, expected in (
            ('f"crayon resume {unit} --overwrite"', 'crayon resume <value> --overwrite'),
            ('"crayon resume %s" % unit + " --overwrite"',
             'crayon resume <value> --overwrite'),
            # The positive halves of the two WR-02 shapes: a REGISTERED flag
            # carried by an operand must survive substitution intact, on one
            # line, so the gate above is not merely rejecting everything.
            ('"crayon resume %s %s" % (unit, "--overwrite")',
             'crayon resume <value> --overwrite'),
            ('"crayon resume %(u)s %(f)s" % {"u": unit, "f": "--overwrite"}',
             'crayon resume <value> --overwrite'),
            # A literal `%%` is one per cent sign and consumes no operand.
            ('"crayon resume %s --overwrite 100%%" % unit',
             'crayon resume <value> --overwrite 100%'),
            ('f"crayon show {unit}\\n--discard"', 'crayon show <value>\n--discard'),
        ):
            with self.subTest(expression=expression):
                sites, _, gaps = refusal_sites('Refusal("bad_target", hint=' + expression + ')')
                self.assertEqual(gaps, [])
                self.assertEqual(sites[0][5], [expected])

    def assert_rejects_unqualified_emission(self, sites):
        gate = TestS13RoutedTextIsInspectable(
            "test_s13_every_emission_that_offers_adopt_states_its_precondition"
        )
        gate.sites = sites
        result = unittest.TestResult()
        gate.run(result)
        self.assertTrue(result.failures, "the actual per-emission gate accepted unsafe prose")
        self.assertEqual(result.errors, [])

    def test_a_sibling_branch_cannot_qualify_a_reworded_offer(self):
        source = ('Refusal("adopt_unsupported", hint=%r if committing else %r)' % (
            "`--adopt` keeps the bytes; run `crayon resume %s` with it. "
            "remove what is refusing the transition",
            "crayon resume %s --adopt " + " ".join(ADOPT_PRECONDITION_MARKERS),
        ))
        sites, _, gaps = refusal_sites(source)
        self.assertEqual(gaps, [])
        self.assert_rejects_unqualified_emission(sites)

    def test_s11_prose_substitution_preserves_literal_backslashes(self):
        for prose in (r"use \1 here", r"a \g<0> b", r"C:\temp"):
            with self.subTest(prose=prose):
                source = ('PATH_HINT = %r\ndef example():\n'
                          '    raise Refusal(\n        "example",\n'
                          '        hint=PATH_HINT,\n    )\n') % prose
                self.assertIn(prose, refusal_blocks(source)["example"][0])
                self.assertEqual(module_prose_constants(source)["PATH_HINT"], prose)

    def test_prose_behind_a_module_list_join_is_read_not_waved_through(self):
        source = (
            'ADVICE_LINES = ["crayon resume <id> --adopt keeps the later edits"]\n'
            'Refusal("adopt_unsupported", hint="%s" % ", ".join(ADVICE_LINES))\n'
        )
        sites, _constants, gaps = refusal_sites(source)
        self.assertEqual(gaps, [])
        self.assertIn("--adopt", sites[0][3])

    def test_a_module_name_the_walk_cannot_read_fails_closed(self):
        source = (
            "ADVICE = build_advice()\n"
            'Refusal("adopt_unsupported", hint="%s" % ADVICE.get("overwrite"))\n'
        )
        _, _, gaps = refusal_sites(source)
        self.assertTrue(gaps, "an unresolvable module dict was silently accepted")

    def test_get_on_an_unclassified_receiver_fails_closed(self):
        for receiver in ("advice", "self.advice", "load_advice()"):
            with self.subTest(receiver=receiver):
                source = (
                    'Refusal("adopt_unsupported", hint="%%s" %% %s.get("k"))\n'
                    % receiver
                )
                _, _, gaps = refusal_sites(source)
                self.assertTrue(gaps, "unclassified `.get` accepted: " + receiver)

    def test_a_payload_read_is_still_data_and_still_passes(self):
        source = 'Refusal("bad_step", hint="step %s is unplanned" % plan.get("id"))\n'
        _, _, gaps = refusal_sites(source)
        self.assertEqual(gaps, [], "a payload `.get` is a data read, not prose")

    def test_unresolved_reasons_and_expanded_arguments_fail_closed(self):
        for call in ('Refusal(reason=reason, hint=advice(unit))',
                     'Refusal(**fields)', 'refuse(*fields)',
                     'answer(situation="broken", hint=advice(unit))'):
            with self.subTest(call=call):
                _, _, gaps = refusal_sites(call)
                self.assertTrue(gaps, "unresolved call silently accepted: " + call)


class TestPhase17In03StepLookupAndNegatives(unittest.TestCase):
    """Phase-17 IN-03 — the step-9 gate fails readably, and its negatives are
    about the ADVICE rather than about one phrasing of it.

    `skill.split('<step_9 ', 1)[1]` raised `IndexError` — a test *error*, not a
    readable failure — the moment step 9 was written `<step_9>`. And the two
    negatives pinned literal strings ('offer the plain resume', 'takes the
    plain resume') that any paraphrase of the same wrong advice walks past.
    """

    SKILL = "crayon-review"

    def test_in03_a_step_written_without_attributes_is_still_found(self):
        source = "<step_9>keep this</step_9>"
        self.assertEqual(skill_step_body(source, 9), "keep this")

    def test_in03_a_step_written_with_attributes_is_still_found(self):
        source = '<step_9 name="recover">keep this</step_9>'
        self.assertEqual(skill_step_body(source, 9), "keep this")

    def test_in03_a_missing_step_is_none_rather_than_an_index_error(self):
        self.assertIsNone(skill_step_body("<step_8>x</step_8>", 9))

    def test_in03_the_live_skill_still_has_its_two_recovery_steps(self):
        text = (SKILLS_ROOT / self.SKILL / "SKILL.md").read_text(encoding="utf-8")
        for step in (9, 10):
            with self.subTest(step=step):
                body = skill_step_body(text, step)
                if body is None:
                    self.fail(
                        "%s/SKILL.md has no <step_%d> element" % (self.SKILL, step)
                    )

    def test_in03_a_paraphrased_bare_resume_offer_is_still_caught(self):
        """The negative the two exact phrases could not see."""
        for wording in (
            "Where the batch already carries an adoption, offer the plain "
            "resume: `crayon resume <id>`.",
            "A batch that already adopted once simply takes `crayon resume <id>`.",
            "If adoption already happened, `crayon resume <id>` is what keeps "
            "the bytes.",
        ):
            with self.subTest(wording=wording[:40]):
                self.assertTrue(
                    bare_resume_offers(wording),
                    "a bare resume offered for an already-adopted batch was "
                    "not caught: %r" % wording,
                )

    def test_in03_the_flagged_commands_are_not_false_positives(self):
        """Negative keystone: the two real answers must not trip the scan."""
        good = (
            "A batch that already carries an adoption takes "
            "`crayon resume <id> --adopt` or `crayon resume <id> --overwrite`, "
            "only with no `unexpected` files."
        )
        self.assertEqual(bare_resume_offers(good), [])

    def test_in03_the_live_step_and_row_offer_no_bare_resume(self):
        skill = (SKILLS_ROOT / self.SKILL / "SKILL.md").read_text(encoding="utf-8")
        for text in (routing_row("resume_ambiguous"), skill_step_body(skill, 9)):
            with self.subTest(text=(text or "")[:50]):
                self.assertEqual(bare_resume_offers(text or ""), [])


class TestD176TheAnalyzerStopRuleIsStated(unittest.TestCase):
    """D-16 — the evasion class is closed by a RULE, not by another fix round.

    The hint-analysis gate is an AST walk over Python string formatting. The
    space of formatting shapes that can evade it is unbounded by construction,
    so it cannot converge through review/fix cycles. The rule has to be where a
    reviewer meets it: in this file, beside the gate.
    """

    SENTENCE = "unbounded by construction"
    GATE = "def refusal_sites("

    def source(self):
        return pathlib.Path(__file__).read_text(encoding="utf-8")

    def test_the_stop_rule_is_stated_beside_the_gate(self):
        """Not merely present in the file — a reviewer has to MEET it there."""
        text = self.source()
        self.assertIn(self.SENTENCE, text)
        self.assertLess(
            text.index(self.SENTENCE),
            text.index(self.GATE),
            "the stop-rule must be stated above the gate it stops, not below "
            "it where only a reader of this class will find it",
        )

    def test_the_stop_rule_names_its_one_reopening_condition(self):
        """A rule that says only 'we stopped' moves the problem."""
        text = self.source()
        start = text.index(self.SENTENCE)
        window = text[max(0, start - 1600) : start + 1600]
        for marker in ("out of scope", "slipping through in practice"):
            with self.subTest(marker=marker):
                self.assertIn(marker, window)


if __name__ == "__main__":
    unittest.main()
