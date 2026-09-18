# Upgrading from slim (`357c513`) to v0.2.0

This page is for someone who already holds a record written by the five `scripts/dogen-*.sh` at
`slim@357c513`. Read it **before** you run `dogen` against that record. Every change below is
stated as a *before → after* pair, so you can tell in one pass whether it affects you.

The normative statement of each rule is `docs/contract.md`; this page only says what moved.
A section with nothing to report says so — `no change` is written, never omitted, the same rule
[`docs/sessions/TEMPLATE.md`](sessions/TEMPLATE.md) states for an unmeasured metric.

## 1 The record: notes and reasons are ordinary JSON text

**Before.** `ledger.md` was a pipe-delimited markdown table. A `|` or a newline in a note was a
field separator, so a note carrying `| verdict: accept | sealed: …` could write a verdict the
reviewer never gave — the row-injection hole closed on the slim branch by refusing the character
outright. Notes therefore could not contain `|`, and multi-line notes were impossible.

**After.** `.dogen/units/<id>/ledger.jsonl` is canonical JSON lines: exactly one
`json.dumps(sort_keys=True, separators=(",",":"))` object per line, one trailing newline per line,
no blank lines anywhere, and `seq` contiguous from zero. `|` and newlines are ordinary characters
in a note or a reason, and a note containing both round-trips **byte-identical**. The forgery is
structurally impossible rather than merely refused: a `|` cannot become a key.

**What is still refused.** A note or reason must be UTF-8 and non-empty, at most 64 KiB. A
carriage return (`\r`) is refused; C0 control characters other than `\n` and `\t` are stripped.
See `docs/contract.md` [§5.6](contract.md#56-validation-rules) and
[§5.2](contract.md#52-envelope-and-serialization).

**What this means for you.** If you scripted around the old restriction — escaping `|`, collapsing
newlines, or splitting a note across rows — stop. Pass the text as it is.

## 2 There is no `run_id`. `seq` is the identity

**Before.** `dogen-record-draft.sh` minted a `run_id` per generation — a nanosecond timestamp plus
a random suffix — and wrote it as a field of the generation row. It was the only per-transition
handle a caller could key on.

**After.** There is no `run_id`, in any event, anywhere. The identity of an event is its **`seq`**:
an integer, contiguous from zero within the unit's ledger, and the thing every other event cites
(`signoff_seq`, `generation_seq`, `steps_seq`, `basis_seq`). `prev` is the sha256 of the previous
line's exact bytes, so the sequence is also a chain: `seq` is stable *and* tamper-evident, which a
random suffix never was.

**What this means for you.** Key on `seq`. If you stored a `run_id` to point at a generation, the
equivalent is the generation event's `seq`; `dogen show <id>` and `dogen show <id> --json` report
the derived state with the seqs it was derived from.

## 3 Legacy units are archived, never migrated in place

**Before.** A unit directory held `ledger.md`, and the scripts read and appended to it.

**After.** A unit directory that holds only the pipe-delimited `ledger.md` and no `ledger.jsonl`
is refused: **exit 2, reason `legacy_unit`**, on every verb, with this hint:

```
archive the unit directory (move <dir> aside) and declare the unit again —
dogen never migrates a ledger in place
```

There is no migration command and no `--migrate` flag. The legacy file is not read, not converted
and not deleted.

**Coexistence.** A directory holding **both** files is a JSONL unit, silently: `ledger.jsonl` is
the record of truth and `ledger.md` is ignored — not read, not written, not removed. That is the
normal state for a repository whose history crossed the swap, not a defect.

**What this means for you.** Move the old unit directory aside and declare the unit again with
`dogen unit new`. The old file stays readable as history; it is simply not a dogen record any more.
See `docs/contract.md` [§5.10](contract.md#510-compatibility).

## 4 Five scripts become one executable, one verb per transition

**Before.** Five bash files on `PATH`. **After.** One stdlib-only `dogen` executable, thirteen
verbs, one verb per transition.

| `slim@357c513` | v0.2.0 |
|---|---|
| `dogen-signoff.sh <id>` | `dogen signoff <id>` |
| `dogen-signoff.sh <id> --force` | `dogen unit edit <id> --re-sign` (see §5) |
| `dogen-record-draft.sh <id> <file> [--model M]` | `dogen draft <id> <source> [--model M]` |
| `dogen-record-review.sh <id> --verdict accept\|fix\|redraft [--note N]` | `dogen review <id> --verdict accept\|fix\|redraft [--note N]` |
| `dogen-record-step.sh <id> <step> --evidence-file F` | `dogen step <id> <step-id> --steps-seq N --evidence-file F` |
| `dogen-common.sh` (sourced helpers: hashing, ledger ops, path validation, commit) | no replacement verb — folded into the single executable |

`tests/test_dogen_scripts.sh` went with them; the black-box suite is now
`tests/test_dogen_acceptance.sh`.

Verbs with no v1 equivalent, because v1 had no place to record the fact: `dogen unit new`,
`dogen unit edit`, `dogen unit retire`, `dogen steer`, `dogen plan-steps`, `dogen edits`,
`dogen resume`, `dogen show`, `dogen summary`, `dogen verify`, `dogen version`. The full verb
table is in `docs/contract.md` [§6](contract.md#6-verb-table).

## 5 There is no `--force`

**Before.** `dogen-signoff.sh <id> --force` re-signed a unit over an existing signoff.

**After.** No verb takes `--force`, and no flag re-signs by overriding a refusal. Amending the
plan and recording the new human signoff is one command and one commit:

```
dogen unit edit <id> --title "…" --body-file plan.md --re-sign
```

`--re-sign` records the amendment and the signoff together, so the record shows what was re-signed
and why, rather than that a gate was overridden.

## 6 Skills are discovered under `.agents/skills/`

**Before.** Skills were installed under runtime-specific roots — `.claude/skills/`,
`.github/skills/`, `.opencode/skills/` — and some installs left a record at
`.dogen/skills-install.yaml`.

**After.** The three skills (`dogen-plan`, `dogen-write`, `dogen-review`) are discovered under
`.agents/skills/` in the project, or `~/.agents/skills/` globally.

**The trap.** Agent runtimes auto-discover the **first** root they find, silently. A stale
v1.0-era skill root wins over a correct `.agents/skills/` install, and nothing tells you — the
session simply runs the old prose against the new tool. Before you upgrade, remove
`.claude/skills/`, `.github/skills/` and `.opencode/skills/` from the repository, together with any
stale `.dogen/skills-install.yaml`, and install into `.agents/skills/`.

## 7 What does not change

- **Install shape** — no change in kind: a file on `PATH`, no package, no venv, no dependencies.
  The steps are in [`README.md`](../README.md).
- **Docs root** — no change: pages are still written under `docs/`, and a target is still a
  docs-relative path.
- **The human-in-the-loop gate** — no change in kind: `signoff` still freezes the sha256 of
  `unit.md`, and a draft with no current signoff, or against a stale plan hash, is still refused.
- **Write ordering** — no change in kind: the ledger is written and fsynced before the page.
- **`unit.md`** — no change in shape: frontmatter (`title`, `intent`, `audience`, `targets`, with
  optional `sources` and `notes`) over a free-Markdown body.
- **Your git history** — no change: nothing rewrites, moves or deletes a commit you already have.

## 8 Compatibility

- `contract` is `1`.
- `min_tool` is `0.2.0`.

Both are compared as **literal strings**, never parsed or rounded as versions — a version parser
would read `0.2.0` and `0.2` as the same thing, and they are not. `dogen version --json` reports
the same pair as `{"tool", "contract"}`. A skill stops only on a contract mismatch, or on a tool
older than `min_tool`.

Their home is `docs/contract.md` [§5.10](contract.md#510-compatibility). If this page and that
section ever disagree, the contract is right and this page is a bug.
