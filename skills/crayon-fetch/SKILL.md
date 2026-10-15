---
name: crayon-fetch
description: Produces crayon context artefacts (doc-style.md, glossary.md, structure.md, code-to-docs-map.md or doc-gaps.md) from sources the author explicitly declares — a local export, a repository path, a URL, or a result the harness already holds — recording each source's origin, retrieval method, revision when known and preservation status, and failing visibly when a requested integration or source is unavailable. Hands each artefact's text to the tool with crayon context stage, declaring its sources, and records the set with crayon context record. Use occasionally, when the material that should steer the docs lives outside the repository (a house style guide, an exported docs set, a glossary held elsewhere), or when crayon-onboard meets a non-standard source.
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
metadata:
  crayon_contract: 1
  crayon_min_tool: "0.2.0"
---
<objective>
Produce one or more of the repository's context artefacts from sources the author
declares, so later documentation work starts from evidence rather than assumptions
even when that evidence lives outside the repository. Where `crayon-onboard` walks the
repository it is run in, this skill takes declared sources — an exported directory,
another checkout, a page at a URL, a document the harness already holds — records
where each one came from, and turns them into the same artefacts under the same
names, so `crayon-plan` and `crayon-write` read them without knowing the difference.

This skill writes no file itself. It holds no write-capable tool: every artefact
reaches disk through the tool's `context stage` verb, with its sources declared on the
same command, and the record through its `context record` verb.
</objective>

<opening>
The first two commands of every session — before any source is declared, retrieved
or read:

```bash
crayon version --json                # {"tool": "<version>", "contract": 1}
crayon context show --json           # what is present, staged, drifted; the routed `next`
```

Stop on exactly two answers from the first call: a `contract` that is not `1`, or a
`tool` older than `min_tool` `0.2.0`. Both numbers are compared as literal strings —
never parsed or rounded as versions. `0.1.9` is older than `0.2.0`: stop, say which
number stopped you, and run nothing else. Any other answer means the pairing is
supported; continue.

The second call is the only source of direction.
**Read `references/routing.md` and act on the row for the emitted `next`.**
`record` means artefacts are already staged and not yet recorded — record them
before fetching anything; `onboard` or `plan` say what the repository holds today,
and either way this skill's work is to add or refresh the artefacts the author's
declared sources support.
A refusal is one JSON line with `error`, `hint` and `next`: act on the routing row
for its `error` first — that row says what to do now — and route on `next` only
after it. The `hint` is a reminder, never the whole route.

**The ledger is never hand-edited.** This skill touches no unit and no ledger at all;
the record it makes is `.crayon/context/manifest.json`, which the tool writes and
nothing else ever edits.
</opening>

<!-- plain-words:begin -->
<plain_words>
What the author reads from this skill is in plain words. The record's own words stay in
`--json`, in the ledger and on every command line, and never reach your prose.

- **Accepted, the pages as accepted, request N.** Say "accepted" where the record says
  sealed, "the pages as accepted" where it says basis, and "request 7" where it says
  seq 7 for a request. Give no other record entry a number, neither "event 7" nor
  "ledger line 7": say what is already recorded and name its commit. These record
  words stay out of your own prose altogether, not even as an English idiom: say
  "on what grounds", not "on what basis".
- **No hashes, digests or verify counts.** A `plan_hash` or a file or record hash,
  a sha256, a digest, and a verify or check count never appear in what you say;
  name a commit by its id, never as a hash. Quote the tallies:
  the walk tally and the findings tally are the tool's and the rubric's own lines.
- **The success line, verbatim.** Echo each verb's success response line exactly as the
  tool printed it; it is already plain. These rules cover what you say around it.
- **Refusals in plain words, commands exact.** Tell the author in plain words what a
  refusal means, for example "request 4 is still open". A command you run or show keeps
  its real flags and values, in a code span. Tool output you show verbatim goes in a
  fenced code block, never inside a sentence. That covers what a step or a routing row
  says to show, and any other line you quote beyond the success line, such as a
  diagnostic a verb prints.
</plain_words>
<!-- plain-words:end -->

<hard_gate>
Do NOT retrieve or inspect anything before every source is declared under the
contract in `references/source-contract.md`, and do NOT write `.crayon/context/*`
yourself. The only path an artefact has to disk is `crayon context stage <name>
--body-file - --source <locator>…` followed by `crayon context record …`. A source
that cannot be reached is recorded as failed in the handoff and is never replaced by
one the author did not declare.
</hard_gate>

<quick_start>
1. Run the two-verb opening above and act on the routing row for `next`.
2. Declare every source with the author: its type (`local-export`,
   `repository-path`, `url`, `harness-tool-result`), its locator, the requested
   retrieval method, whether to preserve content locally, and any allowed fallback.
3. Retrieve or inspect each source through the declared method only; record origin,
   retrieval time, revision when known, and preservation status.
4. Fail visibly: an unavailable source or integration becomes a failure record in
   the handoff, not a substitute.
5. Author the artefacts the sources support — any subset of the five names — loading
   the matching stance reference for each, and hand each one to the tool with
   `crayon context stage <name> --body-file - --source …`.
6. Record the set with `crayon context record --note "…"`, the note summarising the
   accepted and failed sources. When no declared source was accepted, nothing is
   staged and there is nothing to record — the tool refuses a record with nothing
   staged. Skip this step, report the failed sources, and ask the author how to
   proceed.
7. Report accepted sources, failed sources, revisions, preservation, output paths and
   limitations, end on the priorities question, and once the author answers, route to
   `/crayon-plan` with their first pick.
</quick_start>

<pipeline>
crayon-onboard (repo-level, occasional) ─┐
crayon-fetch (declared sources, occasional) ─┴─> .crayon/context/ ─> crayon-plan -> crayon-write -> crayon-review

This skill is not per-unit and not a one-time act: run it when the material that
should steer the docs lives outside the repository, and again when that material
moves. It produces the same artefacts `crayon-onboard` produces, under the same names,
and `crayon context record` keeps every artefact it does not touch — so a house style
guide fetched from a URL can replace `doc-style.md` while the walked `glossary.md` and
`structure.md` stand.
</pipeline>

<workflow>
<step_1 name="Declare every source">
Load `references/source-contract.md` now. Normalize each input into a source record
before anything is retrieved:

- `local-export` — content already exported to a local file or directory; locator is
  a path.
- `repository-path` — a local checkout or source tree; locator is a path.
- `url` — a remote page or API resource; locator is the URL.
- `harness-tool-result` — content the harness already returned (an attached file, a
  tool result in the conversation); locator is the tool name and result identifier
  or transcript reference.

Each declaration also carries the requested retrieval method or integration, whether
local preservation is requested, and the allowed fallbacks, if any. Never accept an
undeclared or implied source class, and never silently replace a requested source or
integration with a different one. If a declaration is incomplete but the missing
value is obvious from the request, infer it and say so; otherwise ask one focused
question with `AskUserQuestion`.

Also settle **which artefacts** the sources are meant to produce. A style guide feeds
`doc-style.md`; a terminology document feeds `glossary.md`; an exported docs set can
feed all three onboarding artefacts; the output of a code-to-docs mapper feeds
`code-to-docs-map.md` and `doc-gaps.md`. Only these five names exist; the tool
refuses any other.
</step_1>

<step_2 name="Retrieve or inspect through the declared method">
- A local export must exist and be readable; inspect filesystem metadata and record
  the export or modification timestamp as its revision.
- A repository path must exist and be readable. If it is a git repository, record
  `HEAD` and whether the tree is dirty; otherwise record the revision as `unknown`.
- A URL is retrieved through the requested integration when one is named — the
  harness's own web tool, or `curl` through `Bash` when that is what the author asked
  for. Record the final URL, the status or response metadata when available, and the
  retrieval time.
- A harness-native tool result must already be present in the harness context.
  Record the tool name and the result identifier; do not re-run the tool unless the
  author asks for fresh input.

Preservation means keeping the source content, a sanitized excerpt or a bounded
inventory locally for later verification; it is never assumed, and whether it
happened is always recorded. Never preserve credentials, tokens, private keys or
sensitive private content; if you meet them, record that redaction occurred and keep
only sanitized metadata.
</step_2>

<step_3 name="Fail visibly">
When a requested integration, path, URL or harness result is unavailable, mark the
source `failed` with the retrieval method that failed, the observed error, the
attempt time, and the next action required. Stop processing that source unless an
allowed fallback was declared; when one was, record both attempts. A failed source
is never marked accepted and never replaced by a substitute the author did not
declare. The failure record lives in the handoff and in the `--note` of the record;
the tool records only what landed.
</step_3>

<step_4 name="Author the artefacts and hand them to the tool">
Use only accepted or explicitly partial sources as the evidence base. Keep excerpts
bounded and preserve paths or identifiers for verification. Distinguish observed
evidence from inference, and never claim a gap or a coverage is exhaustive when the
sources were partial, sampled or failed.

Load the matching stance reference immediately before authoring each artefact:

- `doc-style.md` — `references/style-stance.md`.
- `glossary.md` — `references/glossary-stance.md`.
- `structure.md` — `references/structure-stance.md`.

Then hand each artefact to the tool on stdin, declaring the sources it rests on. A
`--source` is the locator from the source record — a path, a URL, a tool-result id —
recorded verbatim in the manifest; the tool digests nothing behind it, because it
cannot see behind a URL:

```bash
printf '%s\n' "$DOC_STYLE" | crayon context stage doc-style.md --body-file - \
  --source "https://docs.example.com/style-guide" --source "/tmp/style-export/"
```

Each verb answers with one line — what was staged, where, and `Next: record`. Echo
those lines as the tool printed them; never recompose or reword them.
</step_4>

<step_5 name="Record the set">
```bash
crayon context record --model "$MODEL" --model-origin "$MODEL_ORIGIN" \
  --note "<accepted: …; failed: …; revisions: …>"
```

The note is the one place a failed source reaches the record: it becomes the commit
body, collapsed to one line. Omit `--model` and `--model-origin` when you cannot say
who produced the text; the tool records the honest default. The verb promotes the
staged artefacts, freezes `manifest.json`, and makes one commit with `Crayon-Phase:
context-recorded` and no `Crayon-Unit`. Quote the `git: committed <sha>` line it
prints. On `noop_unchanged` (exit 3) nothing changed since the last record: say so
and act on the payload's `next`.
</step_5>

<step_6 name="Report and route">
Present a single summary block, as plain text rather than a code block, ending on
one question about the author's priorities:

```
## crayon-fetch

- Accepted: <source id — type — revision — preserved: yes/no>, …
- Failed: <source id — method — error — next action>, … (or none)
- Artefacts: .crayon/context/<name>, …
- Recorded: <the tool's response line, verbatim>
- Limitations: <what the accepted sources do not cover>

Which three gaps would your readers miss first?
```

That question is for three gaps or more across the artefacts. With one or two, ask
`Which of these would your readers miss first?`; with none, ask
`What would your readers miss most?`. Only their first pick is used.

Ask nothing else in the report, and give it no route line yet: which gaps matter
most is the author's judgment, not something the fetched sources can settle. So the
question is plain text, not options in a question tool, and no gap is marked as
recommended, suggested or a default, whatever a harness's own convention: the order
of the gaps implies nothing. Nothing is recorded from the answer; `crayon context
record` has already run. Once the author answers, the route line names their first
pick in their own words:

```
Next: /crayon-plan — start with <their first pick>
```

Their first pick is the first item in their reply, in the words they used for it,
whatever the sources called that gap. If they name none, the route line is
`Next: /crayon-plan`, with no pick: never pick one for them.

Do not push or build — the tool's commit seam already recorded the transition.
</step_6>
</workflow>

<edge_cases>
**The source is this repository:** route the author to `/crayon-onboard`, whose walk
is the right tool for the repository crayon is run in; this skill is for material
that lives elsewhere.

**A source the author names but cannot locate:** ask one question; never guess a
path or a URL, and never search the network for "the likely one".

**Multiple sources for one artefact:** the artefact's `--source` list names every
one that contributed; the handoff says which was primary.

**A URL that returns something other than documentation** (a login page, an error,
a redirect elsewhere): record it as failed or partial with the observed response,
never as accepted.

**Sensitive content in a source:** record that redaction occurred, keep only
sanitized metadata or excerpts, and say so in the handoff and the note.

**`drifted` in `context show`:** someone edited a recorded artefact by hand. Nothing
is refused; say so, and let the author choose between keeping the edit and refreshing
from the declared sources.

**`busy` (exit 5) or `git_busy` (exit 5):** another run holds the lock, or a git
process is mid-write. Nothing was written. Wait, then re-run the same command
unchanged.

**A refusal you do not recognise:** it is still one JSON line with `error`, `detail`,
`hint` and `next`. Branch on `error`, not on the exit code (several reasons share
one), and act on the routing row for `next`.
</edge_cases>

<constraints>
<must>
- Open every session with `crayon version --json` then `crayon context show --json`,
  and act on the routing row for `next`.
- Declare every source — type, locator, method, preservation, fallbacks — before
  retrieving or inspecting anything.
- Retrieve through the declared method only, and record origin, retrieval time,
  revision or `unknown`, and preservation status for every source.
- Record an unavailable source as failed, in the handoff and in the record's note.
- Hand each artefact to the tool with `crayon context stage <name> --body-file -
  --source …`, and record the set with `crayon context record`, in that order.
- Distinguish observed evidence from inference in every artefact.
- Echo each verb's own response line verbatim.
- End the report on the priorities question, and route to `/crayon-plan` only after
  the author answers, naming their first pick in their own words, or none.
</must>
<must_not>
- Never accept an undeclared or implied source class, and never substitute a source
  or integration the author did not declare.
- Never write `.crayon/context/*` or `manifest.json` yourself — this skill holds no
  write-capable tool and needs none.
- Never stage a name outside the tool's fixed set; the tool refuses it anyway.
- Never preserve credentials, tokens, private keys or sensitive private content.
- Never claim exhaustive coverage over partial, sampled or failed sources.
- Never rewrite source documentation, declare, draft, review, push or build.
- Never re-derive state or invent a next step; the tool emits `next`.
- Never run `crayon context record` with nothing staged.
- Never choose the author's priorities or first unit for them.
</must_not>
</constraints>

<success_criteria>
- [ ] The session opened on `crayon version --json` and `crayon context show --json`.
- [ ] Every source was declared before retrieval, and every record carries origin,
      time, revision or `unknown`, and preservation status.
- [ ] Unavailable sources were reported as failed, never substituted.
- [ ] Each artefact reached the tool through `crayon context stage … --source …`.
- [ ] `crayon context record` exited 0, or 3 on an unchanged set, and its line was quoted.
- [ ] The handoff named accepted and failed sources, revisions, outputs and limitations,
      and ended on the priorities question.
- [ ] The route line to `/crayon-plan` named the author's first pick in their own
      words, or none when they named none.
</success_criteria>
