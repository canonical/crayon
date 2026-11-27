# Your first watch

In this tutorial you rebuild a small site whenever one of its pages changes.

## Install tidewatch

```console
$ python3 -m pip install tidewatch
$ tidewatch version
1.4.2
```

## Make something to watch

```console
$ mkdir -p site/pages && echo "hello" > site/pages/index.txt
```

## Add a watch

```console
$ tidewatch add site/pages --on-change "cp -r site/pages site/out"
3f9c2a1b
```

The printed value is the watch's id. `tidewatch list` shows it again.

## Run it

```console
$ tidewatch run
```

Edit `site/pages/index.txt` in another terminal. Within a few seconds
`site/out/` holds the new copy. Press Ctrl+C to stop.

## Next steps

- {doc}`../how-to/filter-events` to skip files you do not care about.
- {doc}`../how-to/run-as-a-service` to keep tidewatch running after you log out.
