"""Pipeline definition file model: schema, defaults, and validation.

The invented-neutral "product" source the eval fixtures ground against. It is
the ONLY source of truth for the fixture pages — anything a page asserts beyond
this file (and its tests) is an invention, even if plausible.
"""

from dataclasses import dataclass, field

VALID_MODES = ("batch", "stream")  # accepted execution modes
DEFAULT_MODE = "batch"
DEFAULT_RETRIES = 2  # applied when `retries` is omitted
MAX_RETRIES = 5
DEFAULT_TIMEOUT_S = 30  # seconds; 0 disables the timeout entirely
_RESERVED_STEP_NAMES = ("init", "teardown")


@dataclass
class StepSpec:
    """One step in a pipeline definition."""

    name: str
    run: str
    retries: int = DEFAULT_RETRIES
    timeout_s: int = DEFAULT_TIMEOUT_S
    # `watch` is parsed but not yet wired to any runtime behaviour.
    watch: bool = False


@dataclass
class PipelineSpec:
    """A parsed pipeline definition file."""

    name: str
    mode: str = DEFAULT_MODE
    steps: list[StepSpec] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


def validate_manifest(spec: PipelineSpec) -> list[str]:
    """Return every validation error for ``spec`` (empty when valid)."""
    errors: list[str] = []
    if spec.mode not in VALID_MODES:
        errors.append(f"mode must be one of {VALID_MODES}, got {spec.mode!r}")
    if not spec.steps:
        errors.append("a pipeline needs at least one step")
    for step in spec.steps:
        if step.name in _RESERVED_STEP_NAMES:
            errors.append(f"step name {step.name!r} is reserved")
        if step.retries < 0 or step.retries > MAX_RETRIES:
            errors.append(f"retries must be 0..{MAX_RETRIES}, got {step.retries}")
        if step.timeout_s < 0:
            errors.append(f"timeout_s must be >= 0, got {step.timeout_s}")
    return errors
