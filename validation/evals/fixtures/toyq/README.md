# toyq

A small local job queue. `toyq` stores jobs in a SQLite file and runs them one at a
time with a configurable retry policy.

## Install

```bash
pip install toyq
toyq init
```

## Use

```bash
toyq add "make report"
toyq run
toyq status
```

Configuration lives in `toyq.toml` in the working directory; see the configuration
reference in the docs.
