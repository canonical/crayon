# Watch a directory

```console
$ tidewatch add <path> --on-change "<command>"
```

`<path>` may be relative; it is stored as given and resolved from the directory
`tidewatch run` starts in. Add as many watches as you need; `tidewatch list`
shows them all and `tidewatch remove <id>` stops one.
