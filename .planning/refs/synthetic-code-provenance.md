# Synthetic-code provenance

A reusable, harness-agnostic record for code produced with machine assistance. Per Canonical's *Handbook for engineering practice in documentation*: synthetic code must declare where it came from so it stays auditable and reproducible.

This is a **development-process** artefact — it records how *dogen's own code* was produced. It is deliberately shaped like `dogen`'s product `provenance.yaml` (Phase 2), but the two are separate: do not conflate the record of building the tool with the record the tool emits about drafted docs.

## When to use it

- Any PR that includes machine-generated or machine-assisted code or scripts.
- Any **reusable agent operation** (a task an agent runs more than once — a CI job, an on-demand workflow). These additionally need the cross-vendor / fresh-context test record in §"Reusable operations" below.

## The prompt

Append this to the generating prompt, or run it as a final step, and paste the output into the PR description (or a `SYNTHETIC.md` for a reusable operation):

> Report the provenance of the code you just produced as a fenced `yaml` block with exactly these fields: `timestamp` (ISO-8601, UTC), `harness` (tool name + version), `model`, `mode` (and reasoning effort if any), `anatomy` (the skills, instructions, user decisions, prompts, and examples this solution depended on), and `token_cost` (input/output for this operation; note if cached). State unknown fields as `unknown` — do not guess.

## Output template

```yaml
timestamp: 2026-06-19T14:32:00Z
harness: <tool + version>           # e.g. claude-code 2.x, copilot-cli 0.0.x
model: <model id>                   # e.g. claude-opus-4-8
mode: <mode / reasoning effort>     # e.g. default, high
anatomy:
  skills: []                        # skills/SKILL.md in play
  instructions: []                  # AGENTS.md, coding-guide.md, CLAUDE.md, ...
  user_decisions: []                # choices the human made that shaped the output
  prompts: []                       # the operative prompt(s), or a pointer to them
  examples: []                      # examples/fixtures provided
token_cost:
  input: <n>
  output: <n>
  cached: <true|false>
```

## Reusable operations — additional record

For an operation meant to run more than once, also document (per the Handbook):

```yaml
example_output: <pointer to a correct, complete example>
harnesses_tested: []                # every harness it was verified on
models_tested: []                   # include competing vendors
result_variation: <none | describe> # differences observed across models
input_data: []                      # disparate sources it was tested against (reST/MD, repos, extensions)
token_cost_cached: <n>
token_cost_uncached: <n>
test_date: 2026-06-19
```

Store reusable operations in a freely-editable workspace, test them with a **fresh context and no caching**, and give any agent tool an explicit **shell-command allowlist** — never arbitrary shell.
