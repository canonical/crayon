# Limit how many hooks run at once

When many watches change together, tidewatch starts their hooks in parallel,
up to a limit. Lower it on a small machine:

```console
$ export TIDEWATCH_MAX_HOOKS=2
$ tidewatch run
```
