---
schema_version: 1
unit_id: workshop-definition
intent: reference
audience: "Workshop users authoring their own workshop.yaml, and people debugging\
  \ or inheriting a workshop.yaml they didn't write \u2014 served equally"
title: Workshop definition
sources:
- path: internal/workshop/workshop_file.go
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: docs/reference/definition-files/schema.json
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
sphinx_target: reference/definition-files/workshop-definition.rst
steering_notes: "Exhaustive, self-contained field-by-field reference for workshop.yaml,\
  \ serving both people authoring their own definition and people debugging or inheriting\
  \ one they didn't write \u2014 enabling fast mechanical fixes as well as comprehension,\
  \ without requiring the reader to consult source code or explanation pages."
---
## Intent & scope

Single, self-contained reference for `workshop.yaml` (and its named/multi-workshop
variant under `.workshop/`). Serves two audiences equally: someone authoring their
own workshop definition, and someone debugging or inheriting a `workshop.yaml` they
didn't write who needs to check a field's syntax, type, and constraints fast enough
to make a mechanical fix. States facts neutrally — what's valid, not how to learn it.

## Outline / acceptance

- File location and naming: where `workshop.yaml` lives at the project root, and how
  a project stores multiple/named workshop definitions under `.workshop/`.
- Top-level fields table: `name`, `base`, `sdks`, `connections`, `actions` — required
  vs optional, type, constraints, and defaults.
- `name`: allowed character pattern, length limit, and the rule that it must match
  the definition file's basename under `.workshop/`.
- `base`: the enumerated supported Ubuntu base images and how it constrains which
  SDKs can be listed.
- `sdks` entries: how an entry addresses a Store SDK, an in-project SDK, a `try` SDK,
  or the implicit system SDK (including naming-prefix conventions), plus the
  optional channel field.
- Plug and slot addressing: the `<sdk>:<name>` syntax, and what omitting the SDK
  part defaults to.
- Plug definitions on an SDK entry: inline interface-specific attributes vs. binding
  to another plug (mutually exclusive), reusing the shared per-interface attribute
  tables (mount, tunnel, GPU, camera, desktop, SSH agent, custom device).
- Top-level `connections` block: explicit plug-to-slot pairing and how it combines
  with automatic connection at launch/refresh.
- Top-level `actions` block: naming rules and the shape of an action's script value.
- Embedded JSON Schema for machine validation, with a caveat that it may lag the
  field table above.
- At least one full worked example of a valid `workshop.yaml`, reusing an existing
  example file.
- Cross-links: workshop-definition explanation page, sibling SDK/SDKcraft reference
  pages, get-started tutorial.
