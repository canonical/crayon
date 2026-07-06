---
schema_version: 1
unit_id: workshop-definition
intent: reference
audience: Workshop users editing their own workshop.yaml and SDK publishers wiring
  up workshop definitions
title: Workshop definition
sources:
- path: internal/workshop/workshop_file.go
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: internal/sdk/validate.go
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: docs/reference/definition-files/schema.json
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: docs/examples/workshop-digits-cuda.yaml
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: docs/examples/workshop-go-dev.yaml
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: docs/examples/workshop-golang.yaml
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: docs/examples/workshop-try-go.yaml
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
sphinx_target: docs/reference/definition-files/workshop-definition.rst
steering_notes: Exhaustive, self-contained reference for workshop.yaml so a reader
  with the file open can author from scratch or diagnose and mechanically fix a broken
  one without leaving the page. Serves both workshop users and SDK publishers equally.
---
## Intent & scope

An exhaustive, self-contained reference for the `workshop.yaml` definition file. The reader has the file open and needs to know exactly what every field accepts, what the constraints are, and what the file means as a whole — enough to author one from scratch or diagnose and fix a broken one without leaving the page. Serves both workshop users editing their own file and SDK publishers wiring up workshop definitions.

## Outline / acceptance

1. **Title and lead** — label `ref_workshop_definition`, meta description, one-paragraph summary of what `workshop.yaml` is and who reads it.

2. **Filename and location** — `workshop.yaml` or `.workshop.yaml` at the project root; where Workshop looks for it; how it relates to the `.workshop/` directory.

3. **Top-level fields** — list-table with columns Key / Value / Description, covering every field:
   - `name` (required) — workshop identifier; must start with a lowercase letter, contain only lowercase letters, digits, and hyphens joining them; max 40 characters.
   - `base` (required) — base OS image; one of `ubuntu@20.04`, `ubuntu@22.04`, `ubuntu@24.04`, `ubuntu@26.04`.
   - `sdks` (optional) — ordered list of SDK entries; each SDK name must be unique within the file. See nested structure below.
   - `connections` (optional) — list of explicit plug-to-slot connections. See nested structure below.
   - `actions` (optional) — named action scripts. See nested structure below.

4. **Nested: SDK entry** — fields of each item under `sdks`:
   - `name` (required) — SDK identifier; same naming rules as SDK definition names; reserved prefixes `try-` and `project-` are added by Workshop, not authored.
   - `channel` (optional) — SDK channel to track (e.g. `latest/stable`).
   - `plugs` (optional) — map of plug name to either an inline plug definition (interface + attributes) or a `bind` reference (`<sdk>:<plug>`). A bound plug inherits its attributes from the referenced plug and must not define its own. Cannot bind system SDK plugs; cannot bind to itself; cannot chain bindings (A binds to B which binds to C).
   - `slots` (optional) — map of slot name to inline slot definition (interface + attributes). Only `mount` and `tunnel` interfaces support slots.

5. **Nested: Plug/slot reference format** — the `<sdk>:<name>` string syntax used in `bind` values and in connections; system SDK plugs omit the SDK name before the colon; how Workshop resolves the reference.

6. **Nested: Connection entry** — fields of each item under `connections`:
   - `plug` (required) — a plug reference (`<sdk>:<plug>`); the plug must not be bound.
   - `slot` (required) — a slot reference (`<sdk>:<slot>`).
   - Both the plug's SDK and the slot's SDK must exist in the `sdks` list (or be an implicit SDK like `system` or `sketch`).

7. **Nested: Action entry** — each key under `actions` is an action name (same naming rules as workshop name: starts with a letter, lowercase letters, digits, hyphens joining them); the value is a shell script string. One-liner and literal-block YAML forms both accepted; trailing newlines are normalised.

8. **Interfaces** — plug and slot attribute reference, via the same `.. include::` pattern used by the sibling SDK and SDKcraft pages (camera, custom-device, desktop, GPU, mount, SSH agent, tunnel).

9. **JSON Schema** — collapsible dropdown including `schema.json`, with a note about numeric bounds and authoritative rules.

10. **Examples** — at least two worked examples drawn from the existing example YAMLs: a minimal single-SDK workshop and a multi-SDK workshop with connections, plugs/slots, and actions.

11. **See also** — cross-links to sibling definition pages, relevant explanation pages (workshop concepts, plugs and slots, interfaces), and the tutorial.
