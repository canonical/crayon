Pipeline definition file
========================

A pipeline definition file names the pipeline, selects its execution mode, and
lists the steps the runner executes in order.

Top-level fields
----------------

``name``
   The pipeline's identifier.

``mode``
   The execution mode: ``batch`` or ``stream``. The default is ``batch``.

``steps``
   The ordered list of steps. A pipeline needs at least one step. A step can
   reference the output of any previously completed step.

``labels``
   Optional key/value metadata attached to the pipeline.

Step fields
-----------

``name``
   The step's identifier. The names ``init`` and ``teardown`` are reserved and
   rejected.

``run``
   The command the step executes.

``retries``
   How many times a failing step is retried. The default is ``2``; the
   maximum is ``5``.

``timeout_s``
   How long the step may run, in seconds. The default is ``30``; ``0``
   disables the timeout.

Validation
----------

A definition that fails validation is rejected with the first matching error:

- ``mode must be one of ('batch', 'stream')`` — the mode is not a valid
  execution mode.
- ``a pipeline needs at least one step`` — the ``steps`` list is empty.
- ``step name '<name>' is reserved`` — a step uses ``init`` or ``teardown``.
- ``retries must be 0..5`` — a step's retry count is out of bounds.
- ``timeout_s must be >= 0`` — a step's timeout is negative.

.. code-block:: yaml

   name: demo
   mode: batch
   steps:
     - name: build
       run: make
