"""toyq's configuration: read from toyq.toml, overridden by TOYQ_* variables."""

from dataclasses import dataclass

#: Defaults, used when neither toyq.toml nor the environment sets a value.
DEFAULTS = {
    "db_path": "toyq.sqlite",
    "max_retries": 3,
    "retry_backoff_seconds": 5.0,
    "job_timeout_seconds": 600,
    "log_level": "info",
}

#: Each setting can be overridden by an environment variable of this name.
ENV_OVERRIDES = {
    "db_path": "TOYQ_DB_PATH",
    "max_retries": "TOYQ_MAX_RETRIES",
    "retry_backoff_seconds": "TOYQ_RETRY_BACKOFF",
    "job_timeout_seconds": "TOYQ_JOB_TIMEOUT",
    "log_level": "TOYQ_LOG_LEVEL",
}


@dataclass
class Config:
    db_path: str
    max_retries: int
    retry_backoff_seconds: float
    job_timeout_seconds: int
    log_level: str


def load(toml_values, environ):
    """Merge defaults, then toyq.toml, then TOYQ_* variables (last wins)."""
    merged = dict(DEFAULTS)
    merged.update(toml_values)
    for key, var in ENV_OVERRIDES.items():
        if var in environ:
            merged[key] = type(DEFAULTS[key])(environ[var])
    if merged["max_retries"] < 0:
        raise ValueError("max_retries must be 0 or more")
    return Config(**merged)
