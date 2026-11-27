# Run tidewatch as a service

Create `~/.config/systemd/user/tidewatch.service`:

```ini
[Unit]
Description=tidewatch

[Service]
ExecStart=%h/.local/bin/tidewatch run
Restart=on-failure

[Install]
WantedBy=default.target
```

Then enable it:

```console
$ systemctl --user enable --now tidewatch
```
