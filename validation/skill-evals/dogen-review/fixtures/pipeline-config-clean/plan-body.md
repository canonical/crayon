## Intent & scope

The reference page for the pipeline definition file: every top-level field and
every step field, with types, defaults, bounds, and validation behaviour,
stated in the reader's terms.

## Outline / acceptance

- Top-level fields: name, mode (accepted values and the default), steps, labels.
- Step fields: name (including the reserved names), run, retries (default and
  maximum), timeout_s (default; 0 disables the timeout).
- Validation: every rule the validator enforces, stated as a reader-facing
  constraint with the error text a rejected definition shows.
