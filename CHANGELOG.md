# Changelog

All notable changes to crayon are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/): `Added`, `Changed`, `Fixed`, `Removed`,
in that order under every release. Within a heading, entries run in the order the deliverables land
in the release series — contract and tool core, the four suites, skills over verbs, the retired v1
bash layer, CI and the install smoke, the docs, the session records — so two entries of equal
significance still have one order a reader can predict.

## [Unreleased]

dogen is now crayon. The command is `crayon` (the file `crayon.py`), the skills are
`crayon-onboard`, `crayon-fetch`, `crayon-plan`, `crayon-write` and `crayon-review`, the record
lives under `.crayon/`, the commit trailers are `Crayon-*`, the variables are `CRAYON_*`, and the
repository is `https://github.com/canonical/crayon`. crayon does not read a record dogen wrote
under `.dogen/`. [docs/upgrade.md](docs/upgrade.md) says how to move a machine and a repository
across. The contract number stays `1`.

### Added

- `crayon triage record` and `crayon triage export`, an opt-in record of documentation-triage
  advice. `crayon-plan` hands every triage advice to `triage record`, which keeps it only when the
  repository's owner has run `git config crayon.collect true`: one chained line in
  `.crayon/triage/log.jsonl` (the commit range, the changed paths, the advice and a note, never a
  diff) and one commit with no unit. With the setting off it writes nothing and says so.
  `triage export` sets each record beside the unit it led to and labels whether the change needed
  documentation: an accepted unit says yes; a retired one, or none within 30 days, says no.
  `validation/triage/measure.py` reports how often the advice was right, and
  `validation/triage/build_dataset.py` builds a fine-tuning dataset from 300 labelled records or
  more. Contract 1 holds, recorded in `docs/contract.md` §5.10.
- `crayon show --json` and `crayon summary --json` carry `handover`, always present, with
  `steps` (the current plan's deviated and skipped steps), `judged` (the requests the latest
  accept resolved with no generation or reviewer edit between the request and the accept) and
  `withdrawn` (the requests it withdrew, each with its reason). A skill can put what is still
  open to the author before the loop stops, without reading the ledger.
  Additive under contract 1, recorded in `docs/contract.md` §5.10.
- `crayon summary` and `summary --md` open with "Author decisions": the intent, the audience,
  every note the record says the author wrote under a plain label, and what is still open at
  handover. `summary --json` carries the same notes as `author_notes`, entries
  `{seq, origin, note, request}` in recording order. The list is what the record says, not a
  proof of who typed it.
  Additive under contract 1, recorded in `docs/contract.md` §5.10.
- `crayon verify --verbose` prints the full V1–V19 report with its counts, the report default
  `verify` printed before. `--json` wins over it and is unchanged, and the `ledger_corrupt`
  routing row tells a skill to show the `--verbose` report.
  Additive under contract 1, recorded in `docs/contract.md` §5.10.
- An accept's `--json` carries `files`, `resolves` and `withdraws`, copied from the recorded
  `review` event, so a skill can name the accepted pages and the disposed requests without a
  second read.
  Additive under contract 1, recorded in `docs/contract.md` §5.10.
- `validation/closeout-docpr-3008.md` — the slim-cycle disposition, landed
  evidence, release truth and known limitations in one record. It separates
  the current Jira stop condition from shipped product evidence and from the
  non-gating follow-up in canonical/crayon#39.
- `validation/evals/` — model evals. They answer one question: can an author rely on crayon,
  with the model they use, to keep them in control and keep the record true? The answer drives
  two decisions, written into every result: a skill change ships only if no case that passed
  three of three runs on the gate model now passes fewer, and `docs/evals.md` lists a model as
  supported only if it passes every critical case three of three times on the current skills.
  They measure skill-following, not the quality of a page, or speed or effort saved.
  Lane A checks skill selection (15 cases). Lane B checks the next action after real, recorded
  `crayon` output (94 cases): the model acts in a copy of the state inside a Workshop container,
  as an unprivileged user with an environment built from scratch, and the first call that would
  change the copy's files or git index, or that names a recording verb, ends the episode and is
  graded. Every case names the skill rule it protects and whether it is critical, carries a reply
  that must pass and one that must fail, and is graded by deterministic checks only. promptfoo
  runs and grades the cases; a held-out set of 25 lane B cases guards skill fixes, and every case
  a certified model fails gets a recorded disposition. The certified models are Claude Sonnet 5.5
  and Claude Haiku 5.5, the gate model, each pinned to one Zero Data Retention backend in
  `validation/evals/models.json`, whose caps are reserved before every paid call. Paid runs are
  started by hand, never in CI; the gate gains the kit's offline self-tests,
  `uv run --project validation/evals python -m unittest tests.test_evals`. Fifteen critical
  cases, one per critical rule, run on a second, larger project (tidewatch, 23 documentation
  pages), so support does not rest on one project's names. See `docs/evals.md`.
- `crayon show` lists the recorded step plan under the step tally — each step's id, mode,
  stateful marker, status and text — and `show --json` / `summary --json` carry the same rows
  as `steps.plan`. A session that did not propose a tutorial or how-to plan can now resume the
  walk from the read surface instead of the ledger; `crayon-write` says so, and gains a
  must-not against probing a step's command outside the capture recipe. Additive under
  contract 1, recorded in `docs/contract.md` §5.10.
- `crayon context stage`, `crayon context record` and `crayon context show` — the repository's
  context artefacts (`doc-style.md`, `glossary.md`, `structure.md`, `code-to-docs-map.md`,
  `doc-gaps.md`) now reach `.crayon/context/` through the tool. `stage` takes one artefact's text
  from a file or stdin, so a skill that holds no write tool can hand it over; `record` promotes
  the staged set, freezes `manifest.json` with tool-computed digests and the declared sources,
  and makes one commit with `Crayon-Phase: context-recorded` and no `Crayon-Unit`; `show` derives
  what is present, staged, unrecorded or drifted and routes `record`, `onboard` or `plan`. No
  event kind and no reason is added: the change is additive under contract 1, recorded in
  `docs/contract.md` §5.10 beside the `internal_error` revision. N-47 in the lifecycle suite,
  A-38 in the acceptance suite and a unit class cover it.
- `crayon-onboard` and `crayon-fetch` — two portable skills that produce the context artefacts,
  outside the per-unit loop. `crayon-onboard` walks the repository's own docs and cross-reads
  the product surface for `[CODE↔DOCS GAP]` findings; `crayon-fetch` takes sources the author
  declares — a local export, another checkout, a URL, a harness result — retrieves each
  through the declared method, records its origin, revision and preservation status, and
  reports an unreachable one as failed rather than substituting. Neither holds a write tool:
  each artefact is handed to `crayon context stage` and the set to `crayon context record`, so
  the single-writer rule is unchanged. The three stance references are authored in
  `crayon-onboard` and mirrored byte-identically into `crayon-fetch`; the family is five skills
  wherever it was three — `install.sh`, the install smoke, the skill-text suite, the docs.
- `docs/context.md` — the one home for the five context files: what each carries, who
  produces it, how the two verbs record it, and what `crayon-plan` does when they are missing.
- `crayon-plan` grounds itself through `crayon context show --json` and, when the three
  onboarding artefacts are missing, offers the author one three-way choice: supply the files,
  run `/crayon-onboard` first, or ground this one intake from an ephemeral in-memory read
  (`references/context-bootstrap.md`) that persists nothing. The skill never authors
  `.crayon/context/` itself.
- `install.sh` — an interactive installer at the repository root. It walks through the three
  decisions an install has (project or global skills, where the executable goes — a copy or a
  symlink into the checkout — and `.gitignore`), takes every default under `--yes`,
  and ends by verifying the result: the executable on `PATH`, the contract number against every
  installed skill's frontmatter, the skill directories, stale discovery roots, the git identity.
  `--verify-only` runs the last part alone. It is in the shellcheck scope. Skills are installed
  once under `.agents/skills/` and linked from `.claude/skills/`, the one discovery root some
  agents read instead; `--no-compat-links` skips the links. After an install it prints the
  commands that remove it, with the exact paths it used, and the `.gitignore` line to delete;
  `tests/install_smoke.sh` runs those printed lines and checks that nothing is left but the
  record.
- `docs/` is now a wiki in the lint-enforced shape: flat, one page per slug, addressed by slug
  in double square brackets from `AGENTS.md` and between pages, every page with an H1, a
  provenance comment and a `Related:` line, every page reachable from `AGENTS.md`.
  `scripts/wiki_lint.py` (ten checks, exit 0/1/2, `--json`) and `tests/test_wiki_lint.py` are
  gate commands; `AGENTS.md` is rewritten as the router the spec describes, with a topic index.
- `docs/install.md`, `docs/compatibility.md`, `docs/hooks.md`, `docs/shellcheck.md`,
  `docs/development.md`, `docs/architecture.md` and `docs/conventions.md` — one page each for
  what the README and `AGENTS.md` used to carry inline. The install
  guide carries the marked `INSTALL` region `tests/install_smoke.sh` executes; the compatibility
  page carries the `COMPAT` region `tests/check_docs.py` checks; the development page is the
  gate's second pinned home.
- `docs/internals.md` — under the hood in one page: the glossary, the verb table, the exit
  codes, how the record lives on a branch, and the repository layout. It carries the `VERBS`
  and `REASONS` regions. `docs/contents.md` — the reader's index of every document, in path
  links that work in a browser.
- `tests/check_docs.py` checks that the reader-facing documents (`README.md`,
  `docs/contents.md`, `install.md`, `context.md`, `upgrade.md`, `hooks.md`) name no
  `crayon <verb>` outside a `## Under the hood` section, with the verbs taken from
  `crayon --help`. It finds the `VERBS` and `REASONS` regions by their markers, as it already
  found `COMPAT`, and reports a region carried by two documents.

### Changed

- CI runs every Python command on 3.9, the oldest interpreter the tool supports, rather than on
  the runner image's own; the eval self-tests move from the unit matrix to their own `evals` job;
  and the `shellcheck` job checks that the image still ships the version `docs/shellcheck.md`
  names before it runs. Nine jobs.
- The gate checks what its tests assert, not only that they exist. `tests/check_traces.py` reads
  every Mechanisms row of `docs/contract.md`, each of which now names the suite its test lives in,
  and fails on a named test that asserts nothing. The unit suite counts the tests it defines and
  fails unless it loads exactly that many, replacing a fixed minimum of 509 when 638 were
  defined. A skipped test, in any suite, is reported by name and must be listed with its reason in
  `tests/skips.json`. A bash suite that finds no tests exits 2, and `tests/lib.sh` points
  `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` at nothing when it loads, so no suite reads the
  developer's git configuration. `scripts/skill_lint.py` fails on an `allowed-tools` name outside
  the seven tools the skills may use. The install smoke goes on through a review accept, `show`
  and `summary` through the installed command.
- The tool and the five skills move to 0.3.0 together: `crayon.py`'s `__version__`, `min_tool`
  in `docs/compatibility.md` and `docs/contract.md` §5.10, and every SKILL.md's
  `metadata.crayon_min_tool`. The `ledger_corrupt` routing row prescribes
  `crayon verify <id> --verbose`, which a 0.2.0 tool rejects, so a skill now stops on a tool
  older than 0.3.0 rather than route its author to a flag the tool lacks. Every copy of the
  version is read from `__version__` or checked against it.
  Contract 1 holds, recorded in `docs/contract.md` §5.10.
- The skills hand each judgment back to the author. After an accept, `crayon-review` asks at
  most three questions drawn from the unit's record — deviated or skipped steps, requests
  accepted without a page change, findings left open in that review, where a reader arrives
  from — none when nothing is open, and names no publishing step. The verdict is asked as one
  open question before the findings' lean is shown. Notes are recorded in the author's own
  words, single-quoted on the command line so a backtick or a `$` in them is recorded as typed
  rather than run or expanded, with nothing in them escaped or dropped; a bare accept records
  no note, and no judgment question marks an option as recommended. `crayon-plan` asks at least
  one open question even when a brief fills every field, and gives its view on audience or
  direction only when asked, ending that turn on the question the view informs. It skips the
  problem question when the brief states the problem, asks one of the two arrival questions and
  then the leave-out question, and records the replies in one `--notes`, a real line break
  between them, with nothing recorded for a "nothing". `crayon-onboard` ends on a question about
  the author's priorities and routes to `/crayon-plan` with their first pick, in their own
  words. The three author rules are authored once in `skills/README.md` and carried in the
  plan, write and review skills. Lane B gains the cases that pin these, the `question_count`
  kind and three named patterns.
- The skills talk to the author in plain words. What the author reads says "accepted", "the pages
  as accepted" and "request 7", with no `plan_hash`, digest or check count in prose; the record's
  tokens stay in `--json`, the ledger and every command line, and verbatim tool output sits in a
  code block. The rule is authored once in `skills/README.md` and carried in all five skills.
  It names every form of a record word, "sealed" included, and every place one can reach the
  author: an option's label or description, and a refusal or a `--json` value retold in a
  sentence. It names a commit by its id; the routing rows and references a model relays carry no
  record word.
  `crayon-review` puts each deviated or skipped step to the author as a question after the
  provenance summary, in both modes, and the closure does not ask it again in the same
  conversation unless the answer asked for a page change; a step left unanswered is not asked
  again either. It says when it is reviewing its own draft, and assesses a sixth dimension,
  focus, for what the page should not carry. A page change the author asks for in answer to a
  step question is not recorded until the verdict, and the skill says so; after a bare accept,
  the closure asks about it again, in the author's words. When the reviewer already authorised
  the accept, the steps are asked at the closure instead. The review's quick start puts the step
  questions before any finding and before the verdict question. The step questions end their
  message, and the not-recorded line says both of its halves. The closure counts a finding an
  accept did not name, finds a link by the page's bare stem as well as its path, numbers its
  questions in the order it took them, and is never a question-tool call. A pre-authorised
  accept asks no mode question; an "Accept." given to the verdict question on a must-fix tally
  still gets the lean and `Keep accept?`, and a lean asked for ends on the verdict question. A
  pending request is put as a question that ends the message. The self-review line is required
  when an earlier turn ran the draft, and another model on the record is no ground. The
  rubric's findings block always carries all six headings and a tally with its total first, a
  focus must-fix names what the notes left out, and the provenance summary quotes the tool's
  lines rather than re-composing them as bullets.
  `crayon-plan` asks every intake what the page can leave out and records the answer in the
  author's words, and `crayon-write` keeps it off the page. The author's leave-out notes narrow a
  promised inventory, and a later recorded request outranks them. Write and review state what
  they could not verify in the first person, only where the record grounds it, and the
  writer's gap line names the gap its report records. Lane B grades
  every case for record words in what the agent says (`plain_words`), and gains `@HEDGE`, a
  `prelude` for what ran earlier in the conversation, and the cases that pin these. `plain_words`
  reads the rule's own forms and both fence forms. `@HEDGE` catches a negated blanket disclaimer
  and a can-not-verify one, such as "I can't verify everything", and passes a grounded line or
  finding that names its thing. A prelude replays a skill invocation with its body. The kit
  checks that every oracle passes every deterministic assertion of every other case in its
  conversation, and that quoted tool output in a known-good reply sits in a fenced block.
- The tool's human lines are plain. On a sealed unit the handover line reads
  `Next: yours — crayon stops here`, and the accept line names the pages it accepted, with no
  count and no "sealed". The `signoff`, re-sign, `edits` and `resume` lines name the ledger
  and the pages rather than a plan hash, a basis or a seq range. Human `show` says
  `state: accepted`, names an overtaken accept by its commit, lists `request <n>` rows and
  reviewer edits by their notes, and labels the recorded side of `--diff` `recorded:`.
  `summary`'s provenance line reads `record: intact at <sha7>` or names in plain words what
  needs a look. Default `verify` answers `The record is intact.`, `The record is intact; these
  need a look:` or `The record is damaged:`, and its check lines name requests and record
  entries rather than seqs. When it finds damage, the `ledger_corrupt` refusal's `hint` names
  each failing check's V id beside that label, and `error`, `detail`, `next` and exit 6 are
  unchanged. `--json`, `verify --verbose` and the ledger keep every token.
- The 0.2.0 release record now matches the delivery that occurred rather than
  the abandoned release plan: the product tree reached `main` by force-push,
  without a reviewed release merge, `v0.2.0` tag or GitHub Release. The
  release-record check pins those facts and rejects the superseded
  future-tense merge/run/tag claims.
- `internal_error`'s `hint` names the whole route its routing row prescribes: run `crayon show`
  on the unit, then re-run the same command unchanged and report the detail. The old hint
  said only "re-run … and report", and models followed it past the `show`. `error`, `next`
  and exit 6 are unchanged.
- `unsteered`'s `hint` leads with the STOP: ask the author what should change, then
  `crayon steer <id> --note "<their words>"`; `--unsteered-reason` only for an authorised
  redraft with nothing to change. `crayon-write` says a bare "draft it again" is not a note,
  and that a step marked `stateful` takes the author's yes every time, on resume too. The STOP
  touches nothing on disk, and nothing runs toward a stateful step before its gate, not even
  a probe of the tools it needs.
- `unapplied_steering`'s `hint` leads with putting each pending seq to the reviewer, and
  writes the accept's note as optional, `[--note "…"]`, as the routing rows do. Every
  skill now acts on a refusal's routing row for its `error` before routing on `next`, and the
  `hint` is a reminder, never the whole route. The version stop rule gives a concrete case
  (`0.1.9` is older than `0.2.0`) instead of saying the numbers are never ordered.
  `crayon-fetch` records nothing when no declared source was accepted.
- The source file is `crayon.py`; the installed command is still `crayon`. `install.sh` copies or
  links it under that name, and every in-tree pin names `crayon.py`.
- The surface is harness-agnostic: no agent harness is named, detected or preferred in the
  README, the installer, the docs or `AGENTS.md`; skills are invoked as `/crayon-plan`,
  `/crayon-write` and `/crayon-review` everywhere.
- `README.md` is short and skills-first, in plain English: what crayon does, the requirements, a
  manual install in five numbered steps with the installer offered second, the five skills in
  order, a three-step note on using a separate branch, `What stays yours`, and one link to
  `docs/contents.md`. The intro says that crayon knows no Sphinx theme, extension or `conf.py`
  and never builds. `What stays yours` names the four decisions left to the author (audience,
  scope, accept and publish), states that the record shows what was decided and in what order
  but cannot prove who decided, since the author's coding agent runs the commands that approve
  and accept, names the reviewer of the pull request as the gate, and asks a reader who is not
  a technical author to have one review the page before merge. It names
  no `crayon` command. The glossary, the verb table, the exit codes, the branch procedure and the
  layout moved to `docs/internals.md`; the document list moved to `docs/contents.md`. The exit
  codes stay one compact table, a row per code with its reasons in the last cell;
  `tests/check_docs.py` reads that shape there and the per-reason shape in the contract,
  flattening both against the tool's `REASONS`.
- `docs/install.md` puts the manual install first, then the installer's choices, then
  uninstall. `docs/context.md`, `docs/upgrade.md` and `docs/hooks.md` tell the reader what to
  do with the skills and keep the tool's commands in a final `## Under the hood` section. The
  clone URL is `https://github.com/canonical/crayon`.
- `docs/upgrade.md` is a forward-looking procedure — upgrade the executable, re-copy the skills,
  check the two numbers, what a contract bump does to existing records — rather than a
  before-and-after of the previous release.
- `tests/install_smoke.sh` runs the documented `install.sh --yes` out of `docs/install.md` and
  then drives one unit through the installed tool itself; the walk is no longer reader-facing
  shell in the README.
- The shellcheck scope is `install.sh tests/*.sh validation/*.sh`, in CI, in `AGENTS.md` and in
  the unit suite's CI mirror.
- `docs/contract.md` §5.10 records three readings: the `--json` `message` of the accept,
  `signoff`, `unit edit --re-sign`, `edits` and `resume` keeps its contract-1 wording, with
  `plan_hash`, `file(s) sealed` and the seq range, and only the human line changed; the
  accept's note is optional, and `note_required` refuses only a fix or a redraft without one;
  and `verify` takes `--json` and `--verbose` together, `--json` winning. §6, its copy in
  `skills/README.md` and `docs/internals.md` write `verify <id> [--json] [--verbose]`.
  Contract 1 holds, recorded in `docs/contract.md` §5.10.

### Fixed

- `scripts/wiki_lint.py` reads only files git does not ignore, so the copies a model-eval run
  makes, and deletes, under `validation/evals/.cache/` are never linted or lost mid-read.
- Lane B's `@OFFERS_PUBLISH` pattern reads `next: publish` quoted whole in inline code as a
  mention of the routed token, as its own comment says, not as publishing offered. The bare
  token is still an offer. Case B-47.
- Lane B cases that failed replies saying what the skill asks now ask only their rule. B-56's history confirms the walk scope before the walk. B-64 reads a line saying no
  step is open as no step question. B-65 and B-75 take the record named before the fix or
  redraft verdict that puts the words on it. B-43 reads a lean set in bold, and B-46 asks where
  a reader arrives from second, one question per source first. Every oracle still passes and
  every foil still fails.
- Lane B's `@HEDGE` pattern passes a grounded line that locates what may be wrong ("the line
  on the page may be wrong", "the example in the draft might be wrong") or that cites a file
  or a line in the same clause as the hedge, before the hedge or after it ("Per config.py:12
  the page may be wrong.", "it may be wrong, config.py:12 sets 5"). A path with dots in it is
  read whole (`v1.2/config.py`), and the clause ends at a newline, `;`, a sentence stop or
  `but`. The dots of `e.g.` and `i.e.` are not a sentence stop, and `etc.` is one only before
  a capitalised word or the end ("The page may be wrong, e.g. config.py:12 sets 5."). It also
  passes a could-not-verify line that names its source ("I couldn't verify all of it against
  config.py: …"). A blanket hedge on a line that names a file in another clause
  ("I drafted reference/config.md from config.py, but some of it may be wrong.") is caught,
  and so is "Everything in the draft might be wrong.". It catches every "there may be errors"
  disclaimer, with an adverb, a quantifier or a clause after the noun ("There may still be
  errors", "There may be errors I missed"), unless it names a thing other than the page, and
  it catches "I can't verify every detail". The step-answer notice reads `won't`, `haven't`,
  `hasn't`, "recorded" after the verdict and "the record" before it, and rejects the opposite
  claim, that the answer is never recorded, not even with a fix verdict. Cases B-65, B-67,
  B-68, B-69, B-70 and B-75. Every oracle still passes and every foil still fails.
- Lane B case B-30 grades the turn its `why` names again: its history runs past the two fixed
  intake questions, so the turn under test is the proposal of the mechanical fields, and it
  passes only a reply that proposes `src/toyq/config.py`. A reply that asks the author which
  source files to use fails it offline, on a check that names the file. B-64 reads a step
  report that merely contains "no" ("No network in CI, so step first-job was skipped."), and
  still passes a line saying no step was skipped or deviated, or that no step walk ran, so
  nothing was deviated or skipped. Lane B's `@OFFERS_PUBLISH`
  pattern catches the token alone in inline code after a bare `Next:` and an offer to open a
  PR written in inline code, while `next: publish` quoted whole stays a mention. B-40 checks
  the provenance summary its `why` says comes first. Every oracle still passes and every foil
  still fails.
- The shipped skills no longer name the eval fixtures that grade them. The review skill's
  examples use a `<unit>` stand-in for the unit opening an ask, the steps `fetch-deps` and
  `seed-db`, the model `vendor/model-a` and the page `reference/webhooks.md`; the rubric's
  over-inclusion example names `delivery_timeout`; the write skill's gap example names
  `relay sync` and `server.py`, and its step-plan example `fetch-deps`. A gate test in
  `tests/test_skill_text.py` reads its tokens from the fixtures themselves (the `toyq`
  project, `states.sh` and the recorded states) and fails on any of them in skill text.
- `crayon-review`'s provenance reference says `page: current` compares the bytes crayon
  recorded with the bytes on disk, not the recorded digest.
- Human `crayon show` and `crayon summary` render a request note, a reviewer-edit note or a
  withdrawal reason that a record holds as a number, instead of exiting `internal_error`. A
  drift whose recording commit cannot be found reads "drifted since an earlier commit" rather
  than naming the commit before it. An accept that routes anywhere but the handover says
  "not handed over yet" before `Next:`. A withdrawal with no reason reads `withdrawn` and
  `request 4 withdrawn`, with no trailing colon. In `summary --md`, a note that opens with a
  heading or list marker (`#`, `-`, `+`, `*`, `1.`, `1)`) has it escaped, so it stays text in
  its list item. The plain `verify` line names several requests an accept resolves or
  withdraws as `requests 4, 5`. Human wording only; `--json` and the ledger are unchanged.
- Lane B's `question_count` counts a question tool's questions only when they are a list, so
  a JSON string is not counted by its characters, and a final code fence left open runs to the
  end of the reply, so the question marks after it are quoted output. The closure cases B-44,
  B-45, B-46 and B-47 fail a reply that asks through a question tool, since the closure asks in
  plain text. B-53 fails an intake turn that asks more than one question, as B-29 does. B-37,
  B-39, B-55 and B-48 accept a piped note only as `printf '%s'`, which adds nothing, so a
  recorded note never ends in a newline the author did not type. Every oracle still passes and
  every foil still fails.
- `validation/evals/fixtures/states.sh` stops on any setup step that fails, names the step,
  and still removes its temporary repository, so a broken fixture fails the recording instead
  of freezing a wrong state as lane B's baseline.
- `crayon-review` lets a request pending on an existing generation be settled at the verdict:
  the unit routes `draft`, yet the author may review that generation and resolve or withdraw
  the request at the accept, or have it redrafted. Its closure runs only when the accept's
  `next` is `publish`; any other `next`, such as `record_edits` after a hook changed a page,
  follows its own routing row. On a unit already accepted, the closure says that its questions
  are what the record still shows open, and a reply that they were settled ends it with nothing
  recorded. `crayon-plan`'s reference gives the true reason for `--origin plan`: `crayon summary`
  lists the request under "Author decisions" as from the plan, not as steering.
- Lane B's `bash_sequence` counts each command of a chain on its own, in the order it runs, as
  two calls in one turn do: an opening typed as `crayon version --json; crayon show <id> --json`
  opens on version, then the state read. A leading `cd` into the working directory, or an
  `echo`, `printf`, `true`, `:` or `pwd` after a command (as in `|| true` or `; pwd`),
  changes nothing; a read between the opening's commands (`; ls docs`) is a command of its
  own. Its feedback names what really ran, and a chain that reads the state first still
  fails. Cases B-01 and B-02.
- `crayon-write` says the signoff is `crayon-plan`'s act although the `sign_off` and `re_sign`
  routing rows name its verb: the writer runs and offers neither `crayon signoff` nor
  `crayon unit edit`, and routes back to `/crayon-plan`. Case B-23.
- Lane B cases whose replayed record contradicted itself replay one a careful model can trust.
  B-18's history reads the unit's plan and its source before it writes the page that plan asks
  for, and only then is the draft refused `busy`. B-57's replayed onboarding report counts the
  gaps its recorded `structure.md` holds and asks the question for that count. B-69 hands the
  writer a draft that leaves out what its intake notes leave out, from a new `reported_noted`
  state whose report keeps the one `log_level` gap. A test reads each against its state. Every
  oracle still passes and every foil still fails.

### Removed

- `scripts/planning_lint.py` and `tests/test_planning_lint.py`, the anonymization lint over
  planning documents the repository no longer keeps, and their two gate commands. The gate is
  fifteen commands.
- `validation/rubric.md`, a human scoring bar no run ever filled in, and `validation/score.py
  draft`, a report-only prose scorecard that fitted one project's pages. `score.py protocol` keeps
  the checks a real-use run's RUN file can answer (its keys and metrics, the transcript digest,
  compatibility and context origins) and no longer reads leg files or rubric tables.
- `docs/sessions/` and `validation/legs/` — the recorded session and leg records — and the unit
  tests over them. They carried run-specific paths and identities; the kit's tooling stays.
- Personal names in comments and prose are replaced by roles.
- The README's "What is and is not proven" section and the `CLAIMS` observable in
  `tests/check_docs.py`, with the release-record prose that cross-referenced them below.
- The README's credit section. The acceptance tests A-31 … A-35 keep the names they were ported
  under, and the *Fixed* entry below keeps the attribution.

## [0.2.0] - 2026-09-18

One stdlib-only `dogen` executable over a hash-chained JSONL ledger replaces the five
`scripts/dogen-*.sh` and the pipe-delimited `ledger.md`. Migration for anyone holding a record
written by the old scripts was archive-and-redeclare, the policy [docs/upgrade.md](docs/upgrade.md)
still states for any record under another contract number.

The record was finalized on 2026-09-18. The 0.2.0 product tree reached `main`
by force-push on 2026-10-01. No reviewed release pull request or merge
produced that state. No `v0.2.0` tag was created. No GitHub Release was
published.

Entries describe the delivered product tree as a whole. The delivery record
near the end of this section distinguishes that tree from the reviewed
pull-request, merge and tag process that had been planned but did not occur.

### Added

- `docs/contract.md` — the normative specification: artifacts and ownership, envelope and
  serialization, the event catalogue, derivation, routing, validation rules, verb order and
  refusals, the write protocol and resume, what `verify` reports, and compatibility. Reviewed and
  frozen at `contract-v1` (see *Where the frozen contract lives*).
- `dogen` — one executable, Python 3.9 syntax, standard library only: no package, no venv, no
  dependencies. The record is `.dogen/units/<id>/ledger.jsonl`, canonical JSON lines chained by
  sha256 over each previous line's exact bytes, with all state derived from the events rather than
  stored.
- Thirteen verbs, one per transition: `unit` (`new`, `edit`, `retire`), `signoff`, `steer`,
  `plan-steps`, `step`, `draft`, `edits`, `review`, `resume`, `show`, `summary`, `verify`,
  `version`. Every verb takes `--json`.
- `dogen verify` — nineteen checks, V1 through V19, over the whole record: chain and canonical-form
  integrity, the committed prefix, signoff/generation/review citation, evidence and step gates,
  page currency per basis path, and git corroboration as WARN or INFO rather than FAIL.
- The evidence-gated step walk — `plan-steps` records the step plan with tool-computed text
  hashes; `step` records one step's evidence under `.dogen/staging/<id>/scratch/`; an actionable
  draft is refused while any planned step is unresolved.
- `dogen resume` — two-pass recovery for a transition interrupted mid-write, classifying every
  manifest file before it decides, with `--dry-run`, `--overwrite` and `--adopt`.
- The four suites: `tests/test_dogen_acceptance.sh` (the ported black-box suite),
  `tests/test_dogen_lifecycle.sh`, `tests/test_dogen_unit.py` and `tests/test_skill_text.py`, over
  `tests/run_matrix.sh` and `tests/check_traces.py`.
- `validation/` — the validation kit, shipped as evidence apparatus rather than as product code:
  `validation/score.py` (the rubric scorer plus the four-oracle independent audit),
  `validation/fixtures.sh` (V-01…V-04, the four corruption fixtures and the oracle that catches
  each), `validation/runmeta.sh` (a leg's RUN metadata) and `validation/rubric.md` (the scoring
  bar). Session records and per-leg RUN files are not shipped. It reports as its own CI job and is
  a gate command.
- Three skills — `dogen-plan`, `dogen-write`, `dogen-review` — that drive the loop through the
  verbs and never re-implement a gated, side-effecting action.
- `.github/workflows/ci.yml`, `tests/install_smoke.sh` (the only test that reaches `dogen` through
  `PATH` rather than the in-tree file) and `tests/check_docs.py`, which checks the documented verb
  table, reason table, compatibility numbers and links against the tool's own observables.
- `tests/size_guard.py` — the line budget over `dogen`, reported and enforced. The CI job and
  the local guard load both thresholds **and** the comparison out of `tests/test_dogen_unit.py`, so
  there is one authoring site for the pair and the job and the guard are the same code rather than
  merely the same constants.
- [docs/upgrade.md](docs/upgrade.md) — the upgrade procedure.

### Changed

- The ledger moved from a pipe-delimited `ledger.md` to a hash-chained, canonical `ledger.jsonl`.
- Notes and reasons are now ordinary JSON text — a stated behaviour change from `slim@357c513`:
  `|` and newlines are ordinary characters, and a note round-trips byte-identical
  ([docs/contract.md](docs/contract.md) §5.2, §5.6).
- There is no `run_id`; `seq` is an event's identity, and `prev` chains the lines.
- A legacy pipe-delimited unit is refused with an archive hint (`legacy_unit`, exit 2) and is
  never migrated in place; a directory holding both files is a JSONL unit.
- Skills are discovered under `.agents/skills/` in the project, or `~/.agents/skills/` globally.
  Older roots (`.claude/skills/`, `.github/skills/`, `.opencode/skills/`) are found first by some
  agents and must be removed.
- The line budget is recalibrated a third time, to **10,000 lines annotate / 12,000 fail**,
  from the 8,000 / 9,500 pair the earlier builds of this release carried. `dogen` measured 9,472
  lines, so the review trigger had fired on every run for 263 commits and 28 lines of headroom
  remained below the failing threshold — a trigger that fires always reports nothing, and 28 lines
  would have turned the `size-guard` job red on the next substantive change. The new pair applies
  the same offsets the previous recalibration used. The budget is a review trigger, not a design
  goal: behaviour is never deleted to fit it, and the pair has one authoring site in
  `tests/test_dogen_unit.py` that the job and the local guard both load.

### Fixed

- Carries forward the three code-enforced gate holes a reviewer found and closed on the slim
  branch in the v1 review: a `sphinx_target` path traversal (the target was joined into
  `docs/${target}` with no validation), a ledger row injection (an unescaped `|` or newline in a
  `--note` injected fake pipe-delimited fields, including a spoofed `verdict: accept`), and
  `unresolved_steps` matching `status: unverified` as a substring. Each is carried into v2.0 as an
  acceptance test — **A-31** `record_draft_rejects_target_traversal`, **A-32**
  `record_draft_rejects_absolute_target`, **A-33** `record_review_accept_rejects_target_traversal`,
  **A-34** `record_review_note_rejects_pipe` (ported as an inversion: the pipe is now ordinary text
  and the assertion is that no field was forged), and **A-35**
  `unresolved_steps_no_substring_false_positive`.
- To be plain about why the tree was swapped: the swap is justified by what a pipe-delimited ledger
  *cannot* do — support multi-line and `|` notes, persist step text, derive state after
  accept-then-redraft, scope `git add` — **not** by those three holes. Their regression tests are
  carried by intent, and the fixes are credited here.
- **The CI workflow had drifted from the gate it claims to run, and nothing noticed.** The unit
  suite now carries a mirror test that reads `.github/workflows/ci.yml` itself and asserts both
  directions — no gate command without a job, and no job the gate does not declare — with the two
  exceptions held as commented data rather than as prose. The drift it found was real: the gate
  lists both invocation forms of the unit suite on purpose, because they once reported different
  counts, and CI ran only the module form. `python3 tests/test_dogen_unit.py` now runs as a job
  beside it, so the truncation class the second form exists to catch is finally visible to CI.
- **A merge to the default branch could have its gate run cancelled by the next merge.** The
  workflow's concurrency group now keys on the pull request number where there is one and on the
  run identifier otherwise, and cancels in-progress runs only for pull requests. A cancelled run
  reports as cancelled rather than as a failure, so the previous rule left no red behind.
- **Every `actions/checkout` step now sets `persist-credentials: false`.** All eight jobs check out
  the repository and seven of them execute branch-authored code — only `shellcheck` reads without
  executing anything — so leaving a credential in the runner's git config put a token within reach
  of code the job runs by design. The workflow states the rule it follows rather than a count:
  every `run:` step after a checkout executes code authored in the branch under test.
- **The release record was checked by nothing, which is how it came to omit what shipped.**
  `tests/check_docs.py` gained a sixth observable that reads `CHANGELOG.md`'s content rather than
  only its links: it locates the released section, refuses a changelog with no released heading at
  all rather than passing vacuously, and fails on any of four placeholder markers surviving inside
  it. The record itself is corrected with it — the released heading is dated, and `validation/`
  (a kit with its own CI job and its own gate command) and `tests/size_guard.py` are named under
  `### Added`, where neither had appeared.
- **A sha256 was stated as though a reader could check it.** The transcript-digest sentence above
  is restated: the digest is an author-side tamper-evidence commitment, and nothing in this release
  lets a third party verify it. The claim is now what it was always able to support.
- **The shipped tree carried the author's real home directory in 90 places** — 86 in the slash
  form and 4 in the harness-mangled form: in prose, in quoted Sphinx error text, in diagnostics
  blobs and in the RUN files' transcript paths — across five files. All 90 are redacted, in both
  encodings the paths appeared in, and a test over the tree that actually ships now fails if
  either encoding returns. The anonymization gate that existed
  before this covered only the planning tree, which does not ship.

### Removed

- The five `scripts/dogen-*.sh` — `dogen-common.sh`, `dogen-signoff.sh`, `dogen-record-draft.sh`,
  `dogen-record-review.sh`, `dogen-record-step.sh`.
- `tests/test_dogen_scripts.sh`, the suite that tested them.
- The pipe-delimited `ledger.md` as a record of truth. It is never read, converted or deleted; a
  unit directory holding both files is a JSONL unit.
- The `--force` flag, everywhere. Re-signing is `dogen unit edit <id> --re-sign`.

### Where the frozen contract lives

`docs/contract.md` was reviewed and frozen at the signed tag `contract-v1`, at commit `30fe9a5` on
a development branch. The tag remains on that branch's lineage and was not moved or duplicated
onto published `main`. It records the contract freeze where it happened; it is not evidence of a
`v0.2.0` release tag.

The claim is checkable rather than asserted:

```
git fetch origin --tags
git tag -v contract-v1
```

### Contract revision under `CONTRACT = 1`

The `internal_error` reason row (exit 6) was added to the contract's refusal table after
`contract-v1` was signed. It is raised only when dogen itself falls over below the verb.

The addition is **additive**: `contract` stays `1` and `min_tool` stays `0.2.0`, and so do the
`metadata.dogen_contract` and `metadata.dogen_min_tool` values in every `SKILL.md`. The reading is
that the contract's "enum change" means a rename, a removal, or a semantic change to an existing
member, and a new refusal reason that no caller can provoke by using the tool correctly is none of
those. The only callers that meet it are the ones previously told their own hash-chained record was
damaged — for a defect in dogen.

That reading reverses an earlier one, which classified the same row as a contract-2 change. Both
readings are recorded in `docs/contract.md`, and this revision goes to review with the pull request
that lands the row.

### Release-time evidence

GitHub Actions run `37534038841` at `edec520` is green. It is the 2026-10-06
push run for the current published `main` at this close-out snapshot, with all
ten jobs successful. It is later validation of the delivered tree, not
evidence of a tagged release or of a reviewed release merge.

CI is not a required status check on the default branch. The green run is
therefore evidence by inspection of a named run, not a condition the platform
held for the force-push or holds for every later change.

The release has no merge commit, release pull request, `v0.2.0` tag or GitHub
Release object to cite. The named commit and run above are the current
published-tree evidence that does exist.

### How the product tree was delivered

Two abandoned local builds remain historical evidence. `f83145a` was locally
green before the validation kit and its CI job were added. `9308949` was ten
signed commits and locally green before the later gap-closure changes. Neither
build was pushed, tagged or opened as a pull request, and both were superseded;
they do not identify the tree published on `main`.

The final product tree was assembled without the planning branch's process
artefacts and replaced `main` by force-push on 2026-10-01. This differed from
the original requirement's proposed pull request from `slim` into `main`.
That deviation is historical fact, not an equivalent reviewed merge. The
frozen `slim` and `contract-v1` references remain useful provenance where
available, while the published delivery is identified by the `main` history
and the later named CI run.
