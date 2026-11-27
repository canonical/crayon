# tidewatch

tidewatch watches directories and runs a command when something in them changes.
It polls, so it works the same on local disks, network mounts and containers.

```console
$ python3 -m pip install .
$ tidewatch add docs --on-change "make html"
$ tidewatch run
```

The documentation lives under `docs/` and builds with Sphinx:
`python3 -m sphinx docs docs/_build/html`.
