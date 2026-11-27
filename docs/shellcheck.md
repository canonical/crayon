# Shellcheck policy

<!-- provenance: moved from README.md (Shellcheck policy) -->

`install.sh`, the bash suites and the validation kit are kept clean at `shellcheck -S warning`:

```bash
shellcheck -S warning install.sh tests/*.sh validation/*.sh
```

That exact command, with that exact file scope, is what CI's `shellcheck` job runs, so the two
cannot drift in scope even where they drift in version.

CI runs the shellcheck **preinstalled on the runner image, version 0.9.0**, rather than
downloading a newer one — a pinned download or a third-party action would add supply-chain
surface to a gate whose whole job is to be boring. The `shellcheck` job checks the version before
it runs, so an image update that changes it fails by name rather than changing the gate
silently. A developer machine is likely to have a newer
shellcheck, so a finding can in principle appear on one side and not the other.

The rule when that happens: **reproduce the CI-only finding against the pinned 0.9.0 before
changing any code.** A fix written against a newer analyzer's model of the same script is a
guess, and a guess committed to silence a gate is how a gate stops meaning anything. The mirror
image holds too: reproduce a local-only finding against 0.9.0 before changing code for it.

Related: [[development]], [[conventions]].
