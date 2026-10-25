# Security

Hooks run through the shell, as the user running tidewatch, with that user's
environment. Anyone who can add a watch can run commands as that user, so keep
the state directory private.
