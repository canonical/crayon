"""tidewatch's settings: defaults, then tidewatch.toml, then TIDEWATCH_* variables."""

import os
from dataclasses import dataclass

#: Used when neither tidewatch.toml nor the environment sets a value.
DEFAULTS = {
    "poll_interval_seconds": 2.0,
    "debounce_ms": 250,
    "max_hooks_in_flight": 4,
    "hook_timeout_seconds": 300,
    "follow_symlinks": False,
    "log_format": "text",
    "state_dir": "~/.local/state/tidewatch",
}

#: Each setting can be overridden by the environment variable of this name.
ENV_OVERRIDES = {
    "poll_interval_seconds": "TIDEWATCH_POLL_INTERVAL",
    "debounce_ms": "TIDEWATCH_DEBOUNCE_MS",
    "max_hooks_in_flight": "TIDEWATCH_MAX_HOOKS",
    "hook_timeout_seconds": "TIDEWATCH_HOOK_TIMEOUT",
    "follow_symlinks": "TIDEWATCH_FOLLOW_SYMLINKS",
    "log_format": "TIDEWATCH_LOG_FORMAT",
    "state_dir": "TIDEWATCH_STATE_DIR",
}

LOG_FORMATS = ("text", "json")


@dataclass
class Config:
    poll_interval_seconds: float
    debounce_ms: int
    max_hooks_in_flight: int
    hook_timeout_seconds: int
    follow_symlinks: bool
    log_format: str
    state_dir: str


def _parse(key, raw):
    kind = type(DEFAULTS[key])
    if kind is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return kind(raw)


def problems(values):
    """Every invalid setting in ``values``, as one message each."""
    found = []
    if values["poll_interval_seconds"] <= 0:
        found.append("poll_interval_seconds must be more than 0")
    if values["debounce_ms"] < 0:
        found.append("debounce_ms must be 0 or more")
    if values["max_hooks_in_flight"] < 1:
        found.append("max_hooks_in_flight must be 1 or more")
    if values["log_format"] not in LOG_FORMATS:
        found.append("log_format must be one of: %s" % ", ".join(LOG_FORMATS))
    return found


def load(toml_values, environ=os.environ):
    """Merge defaults, then tidewatch.toml, then TIDEWATCH_* variables (last wins)."""
    merged = dict(DEFAULTS)
    merged.update(toml_values)
    for key, variable in ENV_OVERRIDES.items():
        if variable in environ:
            merged[key] = _parse(key, environ[variable])
    found = problems(merged)
    if found:
        raise ValueError("; ".join(found))
    merged["state_dir"] = os.path.expanduser(merged["state_dir"])
    return Config(**merged)
