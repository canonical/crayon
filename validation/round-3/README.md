# Round-3 validation — captured results

This folder is a static, flattened capture of dogen's third end-to-end validation round,
run across three agent harnesses against the same documentation unit (a single
reference page, `reference/definition-files/workshop-definition.rst`, in a Sphinx docs
repo). The full analysis — Sphinx builds, output-vs-gold comparison, and provenance
review — is in [`../round-3-report.md`](../round-3-report.md); the scorer and rubric are
[`../score.py`](../score.py) and [`../rubric.md`](../rubric.md).

Each leg below preserves exactly what that harness produced: the drafted page at the path
it was actually sealed to, the `.dogen/units/workshop-definition/` provenance sidecars
(`unit.md`, `provenance.yaml`, `progress.yaml`), and the harness session log
(`SESSION-<leg>.md`).

| Leg | Model (recorded) | Draft passes | Sealed path | Sphinx build |
|-----|------------------|--------------|-------------|--------------|
| **claude**   | `claude-sonnet-5`   | 2 (fix → accept) | `docs/reference/definition-files/…` ✓ | clean |
| **copilot**  | `claude-sonnet-4.6` | 2 (fix → accept) | `docs/reference/definition-files/…` ✓ | clean |
| **opencode** | `''` — GLM-5.1, recorded empty (the `model_unrecorded` defect) | 3 (fix ×3 → accept) | `docs/docs/reference/definition-files/…` ✗ (doubled) | **fails as-committed** |

**The opencode leg's doubled `docs/docs/…` path is preserved on purpose.** It is the
round's headline defect: the leg declared `--target docs/reference/…`, the CLI joined a
second `docs/`, and the page sealed to a slot the toctree never references — the build
fails as-committed (0 warnings once the file is moved to the canonical slot; the content
is sound, the placement is the fault). This drove the v1.3 fixes (docs/-prefix
normalization at declare/edit, and the `model_unrecorded` honesty flag).

## Provenance of this capture

Flattened from the smoke validation repo (not preserved here) via read-only `git show`
against its round-3 refs:

- `claude/`   ← branch `validation/claude-3`
- `copilot/`  ← branch `validation/copilot-3`
- `opencode/` ← branch `validation/opencode-3`

Session logs were renamed to a uniform `SESSION-<leg>.md` (the harnesses named them
inconsistently: `validation/SESSION-claude.md`, `copilot-session-<uuid>.md`, and
`session-ses_0d1b.md` respectively). Only unit 1 (the single-page reference) was driven on
every leg; the multi-file unit-2 flow was not exercised this round.
