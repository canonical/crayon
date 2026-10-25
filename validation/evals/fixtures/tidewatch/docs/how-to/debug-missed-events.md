# Find out why a change did not run a hook

1. Check the watch exists: `tidewatch list`.
2. Check the file is not ignored by one of the watch's `--ignore` patterns.
3. Changes closer together than the debounce window run the hook once.
4. A symbolic link to a directory is not followed unless symlinks are followed.
5. Run `tidewatch run --once` after making the change, and watch its output.
