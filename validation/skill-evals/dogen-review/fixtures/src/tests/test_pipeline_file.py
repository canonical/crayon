"""Behavioural tests for the pipeline definition schema.

The second in-repo signal for the fixture's corroboration checks: a field or
behaviour exercised here is user-reachable; a symbol that appears only in
``pipeline_file.py`` (like ``watch``) has no second signal and must not be
documented as supported.
"""

from internal.pipeline.pipeline_file import (
    DEFAULT_MODE,
    DEFAULT_RETRIES,
    MAX_RETRIES,
    PipelineSpec,
    StepSpec,
    validate_manifest,
)


def _spec(**step_kwargs):
    return PipelineSpec(name="demo", steps=[StepSpec(name="build", run="make", **step_kwargs)])


def test_default_mode_is_batch():
    assert DEFAULT_MODE == "batch"
    assert PipelineSpec(name="demo").mode == "batch"


def test_stream_mode_is_accepted():
    spec = _spec()
    spec.mode = "stream"
    assert validate_manifest(spec) == []


def test_retries_defaults_to_two():
    assert StepSpec(name="build", run="make").retries == DEFAULT_RETRIES == 2


def test_retries_above_max_rejected():
    errors = validate_manifest(_spec(retries=MAX_RETRIES + 1))
    assert any("retries must be 0..5" in e for e in errors)


def test_reserved_step_names_rejected():
    errors = validate_manifest(
        PipelineSpec(name="demo", steps=[StepSpec(name="init", run="make")])
    )
    assert any("is reserved" in e for e in errors)


def test_zero_timeout_is_valid():
    assert validate_manifest(_spec(timeout_s=0)) == []


def test_negative_timeout_rejected():
    errors = validate_manifest(_spec(timeout_s=-1))
    assert any("timeout_s must be >= 0" in e for e in errors)


def test_empty_steps_rejected():
    errors = validate_manifest(PipelineSpec(name="demo"))
    assert any("at least one step" in e for e in errors)
