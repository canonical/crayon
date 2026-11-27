# Ignore files you do not care about

Pass `--ignore` with a glob, once per pattern:

```console
$ tidewatch add docs --on-change "make html" --ignore "*/_build/*" --ignore "*.swp"
```

Patterns match the full path of the changed file.
