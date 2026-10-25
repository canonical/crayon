# Run a command when a file changes

The command given to `--on-change` is a hook. It runs through the shell, so
pipes and `&&` work:

```console
$ tidewatch add src --on-change "python3 -m pytest -q && echo ok"
```

Each hook run sees two variables:

- `TIDEWATCH_EVENT`: `created`, `modified` or `deleted`;
- `TIDEWATCH_PATH`: the file that changed.

A hook that runs longer than the hook timeout is stopped. See
{doc}`../reference/hooks`.
