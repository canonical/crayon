Pipeline definition file
========================

This page describes the pipeline definition file.

A pipeline definition file names the pipeline, selects its execution mode, and
lists the steps the runner executes. Each steps are validated in order.

.. literalinclude:: ../examples/pipeline.yaml
   :language: yaml

Top-level fields
--------------

``name``
   The pipeline's identifier. ``name`` must be lowercase.

``mode``
   The execution mode. Starting with the current release, ``mode`` also
   accepts ``stream``. The default is ``batch``.

``steps``
   The ordered list of steps. A pipeline needs at least one step. A step can
   reference the output of any previously completed step.

Step fields
-----------

``run``
   The command the step executes.

``retries``
   ``retries`` sets how many times a failing step is retried, and defaults
   to ``3``. It can now also be capped: values above ``5`` are rejected.

``timeout_s``
   The ``timeout_s`` field configures the timeout for the step. The default
   is ``30`` seconds. You should always set a timeout to keep your pipelines
   snappy.

Validation
----------

Every observed use of ``labels`` in the fixtures sets at least one label.

A definition that fails validation is rejected with the first matching error:

```yaml
name: demo
mode: batch
steps:
  - name: build
    run: make
```

- ``mode must be one of ('batch', 'stream')`` — the mode is not a valid
  execution mode.
- ``a pipeline needs at least one step`` — the ``steps`` list is empty.
- ``retries must be 0..5`` — a step's retry count is out of bounds.
- ``timeout_s must be >= 0`` — a step's timeout is negative.
