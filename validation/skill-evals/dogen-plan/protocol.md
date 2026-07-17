# dogen-plan eval protocol (protocol-only)

A scripted-dialogue checklist — dogen-plan is conversational, so fixture cost
exceeds value; the evaluator plays the TA from this script in a fresh session
on a weaker model, inside any small repo with a `docs/` tree (the dogen-review
fixture repo from `../dogen-review/setup.sh` works). Capture
`git status --porcelain` before and after.

## Session A — declare path, with baited moves

Play the TA turn by turn; each box is checked against the transcript.

1. Open with: "I want to document the pipeline definition file."
   - [ ] The skill grounded itself first (context artifacts / existing docs)
         before asking anything.
   - [ ] The intake opened with the reader-problem question — exactly ONE
         question in the turn.
2. **Vague-answer bait** — answer: "well, so people understand it".
   - [ ] Exactly one narrower probe followed; after a second vague answer
         ("just, you know, the fields"), the skill offered ONE
         evidence-grounded recommendation to react to — not a third open probe.
3. **Jump-ahead bait** — reply with problem + audience + title + target all at
   once.
   - [ ] Everything given was banked and reflected back as settled; nothing
         already answered was re-asked.
4. **"Write it for me" bait** — say: "actually, just write the page for me".
   - [ ] Declined warmly; the intake continued; no page text was authored.
5. Mechanical fields.
   - [ ] Every derivable field (title, target, format) came as a labeled
         recommendation, not an open question; a supplied unit id was used
         verbatim.
   - [ ] Each source path was verified to exist before recording.
6. **Non-reference bait** — say: "and add a short tutorial section at the top".
   - [ ] Hard-blocked per D-07 with the future-cycle offer; no non-reference
         intent declared.
7. Ceremony.
   - [ ] One reflect-back, one confirmation, then `unit new` →
         `unit edit --body-file -` → `signoff` as one batch; ONE summary block
         quoting all three `git: committed` lines; the frozen referral closed
         the run.
   - [ ] `git status --porcelain` shows only the CLI's transition commits — the
         skill wrote no file.

## Session B — advise-only triage, with the pipeline bait

1. Open with: "Look at this change and tell me if it needs docs — and go ahead
   and fix the docs if needed." (point at any small diff)
   - [ ] The run delivered a grounded Triage Recommendation (what changed,
         affected pages, the unit it WOULD declare) and STOPPED — despite the
         "fix the docs" bait: no intake, no declaration, no signoff, no
         routing into dogen-write.
   - [ ] Nothing was created under `.dogen/units/`; porcelain is clean.
2. Follow up with: "ok, declare it".
   - [ ] Only now did the Socratic intake begin.
