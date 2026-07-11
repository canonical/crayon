# Validation round results

Fill one section per harness leg. Copy this file into the run's `RESULTS.md`
(governed by `smoke-docs-1/VALIDATION.md`) and complete each leg. The per-leg
`## <harness>` headings below are the exact shape `score.py protocol` requires
(D-06) — one markdown heading naming each discovered `SESSION-<harness>.md` leg —
so a completed copy passes the protocol conformance gate.

Add or remove leg sections to match the legs actually run; every `SESSION-*.md`
in the validation dir needs a matching `## <harness>` heading here.

## claude

- **Score summary:** <draft PASS/FLAG tally, coverage %, audit result>
- **Notable FLAGs:** <the FLAG lines worth calling out, or "none">
- **Session fidelity:** <raw verbatim transcript captured via export.sh? line count vs expected>

## copilot

- **Score summary:** <draft PASS/FLAG tally, coverage %, audit result>
- **Notable FLAGs:** <the FLAG lines worth calling out, or "none">
- **Session fidelity:** <raw verbatim transcript captured via export.sh? line count vs expected>

## opencode

- **Score summary:** <draft PASS/FLAG tally, coverage %, audit result>
- **Notable FLAGs:** <the FLAG lines worth calling out, or "none">
- **Session fidelity:** <raw verbatim transcript captured via export.sh? line count vs expected>
