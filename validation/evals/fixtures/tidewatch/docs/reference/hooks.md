# Hooks

A hook is the shell command a watch runs. It inherits tidewatch's environment
plus `TIDEWATCH_EVENT` and `TIDEWATCH_PATH`. Its exit code is logged and never
stops tidewatch. A hook still running after the hook timeout is stopped and
logged with exit code 124.
