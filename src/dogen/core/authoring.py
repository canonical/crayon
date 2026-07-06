"""Provider-agnostic authoring policy for drafted documentation pages.

This is pure domain policy — it carries **zero vendor imports** so the provider
seam (SEAM-01) stays real, and it is seam-legal for the Copilot adapter to import
(``import-linter`` forbids the reverse edge only).

The single distinction encoded here: **rooting a draft IN the code you read is
not the same as surfacing that code IN the narrative.** dogen-write leaked source
because both authoring loci told the drafter to *ground in* the sources but said
nothing about what may *surface* in the output. :data:`REFERENCE_CODE_RUBRIC` is
the canonical text that closes that gap; both the driver strings (interpolated in
:mod:`dogen.adapters.copilot.provider`) and the passenger prose (mirrored in
``skills/dogen-write/references/provider-branch.md``) draw from it, bound by a
drift-guard test to :data:`RUBRIC_HEURISTIC` so the copies cannot silently
diverge.
"""

# The single per-block decision sentence. It is the stable canonical anchor: it
# appears verbatim inside REFERENCE_CODE_RUBRIC (below), and both the driver test
# and the passenger drift-guard test bind to THIS symbol, so a one-sided edit of
# either authoring locus fails loudly.
RUBRIC_HEURISTIC: str = (
    "Per block, ask: would the reader themselves type, author, or invoke this "
    "exact text? If so, a minimal version may be shown; if instead it is how the "
    "machinery is implemented internally, reference it by qualified name and "
    "never show it."
)

# The full code-in-narrative rubric — default, closed exception list, never-show
# list, and the per-block heuristic (interpolated verbatim so the two constants
# are one source of truth). Condensed from the quick-research "The Rubric"
# section; it invents no new policy.
REFERENCE_CODE_RUBRIC: str = (
    "Code-in-narrative rubric. Default: document behaviour — fields, types, "
    "defaults, bounds, constraints — in prose and tables, and refer to code "
    "entities by qualified name (package.Type, package.Function); do not "
    "reproduce their source. The narrative is rooted in the code you read; it "
    "does not surface that code. Exception — a code block may appear only when "
    "the reader themselves authors or invokes it: a minimal input or config, a "
    "public signature or CLI/API call, or a short snippet that cannot be stated "
    "in prose. Never show implementation bodies, private internals, or verbatim "
    f"struct or function source. {RUBRIC_HEURISTIC}"
)

# The stance contract's stable anchor sentence (v1). Like RUBRIC_HEURISTIC, it
# appears verbatim inside STANCE_CONTRACT (below) and the drift-guard test binds
# the passenger prose mirror to THIS symbol, so a one-sided edit fails loudly.
STANCE_ANCHOR: str = (
    "Write as the product's reference, never as a researcher describing their evidence."
)

# The stance contract (v1) — the RC-4 fix for researcher register leaking into
# drafted prose ("every observed use is `interface: camera` alone"). It pairs
# with the v1 source policy: sources are starting points, so a fact that cannot
# be verified where it is defined is either chased to its origin or recorded as
# a provenance gap — it never becomes hedged corpus-narration in the page.
STANCE_CONTRACT: str = (
    f"Stance contract. {STANCE_ANCHOR} State what the product accepts, does, "
    "and enforces — not what you observed while reading. Banned register: "
    "'observed', 'the fixtures show', 'every observed use', 'the corpus', "
    "'at this level'. When a fact cannot be verified from what you have read, "
    "navigate to its origin and verify it there; if it still cannot be "
    "verified, leave it out of the prose and record it as a gap in the "
    "generation's context report — confidence gaps are provenance, not "
    "content. The same discipline covers runtime mechanics: how the machinery "
    "executes internally (temporary files, interpreter invocations, internal "
    "process flow) is implementation, not interface — describe the behaviour "
    "the reader can rely on, never the mechanism, even in declarative voice."
)
