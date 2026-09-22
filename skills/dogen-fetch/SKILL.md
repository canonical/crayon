---
name: dogen-fetch
description: Produces dogen context artefacts (doc-style.md, glossary.md, structure.md, code-to-docs-map.md or doc-gaps.md) from sources the author explicitly declares — a local export, a repository path, a URL, or a result the harness already holds — recording each source's origin, retrieval method, revision when known and preservation status, and failing visibly when a requested integration or source is unavailable. Hands each artefact's text to the tool with dogen context stage, declaring its sources, and records the set with dogen context record. Use occasionally, when the material that should steer the docs lives outside the repository (a house style guide, an exported docs set, a glossary held elsewhere), or when dogen-onboard meets a non-standard source.
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
metadata:
  dogen_contract: 1
  dogen_min_tool: "0.2.0"
---
<objective>
Produce one or more of the repository's context artefacts from sources the author
declares, so later documentation work starts from evidence rather than assumptions
even when that evidence lives outside the repository. Where `dogen-onboard` walks the
repository it is run in, this skill takes declared sources — an exported directory,
another checkout, a page at a URL, a document the harness already holds — records
where each one came from, and turns them into the same artefacts under the same
names, so `dogen-plan` and `dogen-write` read them without knowing the difference.

This skill writes no file itself. It holds no write-capable tool: every artefact
reaches disk through the tool's `context stage` verb, with its sources declared on the
same command, and the record through its `context record` verb.
</objective>

<opening>
The first two commands of every session — before any source is declared, retrieved
or read:

```bash
dogen version --json                 # {"tool": "<version>", "contract": 1}
dogen context show --json            # what is present, staged, drifted; the routed `next`
```

Stop on exactly two answers from the first call: a `contract` that is not `1`, or a
`tool` older than `min_tool` `0.2.0`. Both numbers are compared as literal strings —
never parsed, ordered or rounded as versions. Any other answer means the pairing is
supported; continue.

The second call is the only source of direction.
**Read `references/routing.md` and act on the row for the emitted `next`.**
`record` means artefacts are already staged and not yet recorded — record them
before fetching anything; `onboard` or `plan` say what the repository holds today,
and either way this skill's work is to add or refresh the artefacts the author's
declared sources support. A refusal carries its own `next` in the JSON line — route
on that the same way.

**The ledger is never hand-edited.** This skill touches no unit and no ledger at all;
the record it makes is `.dogen/context/manifest.json`, which the tool writes and
nothing else ever edits.
</opening>

<hard_gate>
Do NOT retrieve or inspect anything before every source is declared under the
contract in `references/source-contract.md`, and do NOT write `.dogen/context/*`
yourself. The only path an artefact has to disk is `dogen context stage <name>
--body-file - --source <locator>…` followed by `dogen context record …`. A source
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
   `dogen context stage <name> --body-file - --source …`.
6. Record the set with `dogen context record --note "…"`, the note summarising the
   accepted and failed sources.
7. Report accepted sources, failed sources, revisions, preservation, output paths and
   limitations, and route the author on `next`.
</quick_start>

<pipeline>
dogen-onboard (repo-level, occasional) ─┐
dogen-fetch (declared sources, occasional) ─┴─> .dogen/context/ ─> dogen-plan -> dogen-write -> dogen-review

This skill is not per-unit and not a one-time act: run it when the material that
should steer the docs lives outside the repository, and again when that material
moves. It produces the same artefacts `dogen-onboard` produces, under the same names,
and `dogen context record` keeps every artefact it does not touch — so a house style
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
printf '%s\n' "$DOC_STYLE" | dogen context stage doc-style.md --body-file - \
  --source "https://docs.example.com/style-guide" --source "/tmp/style-export/"
```

Each verb answers with one line — what was staged, where, and `Next: record`. Echo
those lines as the tool printed them; never recompose or reword them.
</step_4>

<step_5 name="Record the set">
```bash
dogen context record --model "$MODEL" --model-origin "$MODEL_ORIGIN" \
  --note "<accepted: …; failed: …; revisions: …>"
```

The note is the one place a failed source reaches the record: it becomes the commit
body, collapsed to one line. Omit `--model` and `--model-origin` when you cannot say
who produced the text; the tool records the honest default. The verb promotes the
staged artefacts, freezes `manifest.json`, and makes one commit with `Dogen-Phase:
context-recorded` and no `Dogen-Unit`. Quote the `git: committed <sha>` line it
prints. On `noop_unchanged` (exit 3) nothing changed since the last record: say so
and act on the payload's `next`.
</step_5>

<step_6 name="Report and route">
Present a single summary block:

```
## dogen-fetch

- Accepted: <source id — type — revision — preserved: yes/no>, …
- Failed: <source id — method — error — next action>, … (or none)
- Artefacts: .dogen/context/<name>, …
- Recorded: <the tool's response line, verbatim>
- Limitations: <what the accepted sources do not cover>

Next: /dogen-plan — the context now grounds unit declarations.
```

Do not push or build — the tool's commit seam already recorded the transition.
</step_6>
</workflow>

<edge_cases>
**The source is this repository:** route the author to `/dogen-onboard`, whose walk
is the right tool for the repository dogen is run in; this skill is for material
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
- Open every session with `dogen version --json` then `dogen context show --json`,
  and act on the routing row for `next`.
- Declare every source — type, locator, method, preservation, fallbacks — before
  retrieving or inspecting anything.
- Retrieve through the declared method only, and record origin, retrieval time,
  revision or `unknown`, and preservation status for every source.
- Record an unavailable source as failed, in the handoff and in the record's note.
- Hand each artefact to the tool with `dogen context stage <name> --body-file -
  --source …`, and record the set with `dogen context record`, in that order.
- Distinguish observed evidence from inference in every artefact.
- Echo each verb's own response line verbatim.
</must>
<must_not>
- Never accept an undeclared or implied source class, and never substitute a source
  or integration the author did not declare.
- Never write `.dogen/context/*` or `manifest.json` yourself — this skill holds no
  write-capable tool and needs none.
- Never stage a name outside the tool's fixed set; the tool refuses it anyway.
- Never preserve credentials, tokens, private keys or sensitive private content.
- Never claim exhaustive coverage over partial, sampled or failed sources.
- Never rewrite source documentation, declare, draft, review, push or build.
- Never re-derive state or invent a next step; the tool emits `next`.
</must_not>
</constraints>

<success_criteria>
- [ ] The session opened on `dogen version --json` and `dogen context show --json`.
- [ ] Every source was declared before retrieval, and every record carries origin,
      time, revision or `unknown`, and preservation status.
- [ ] Unavailable sources were reported as failed, never substituted.
- [ ] Each artefact reached the tool through `dogen context stage … --source …`.
- [ ] `dogen context record` exited 0, or 3 on an unchanged set, and its line was quoted.
- [ ] The handoff named accepted and failed sources, revisions, outputs and limitations.
</success_criteria>
