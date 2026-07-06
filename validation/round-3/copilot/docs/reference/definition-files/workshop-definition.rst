.. _ref_workshop_definition:

.. meta::
   :description: Reference for the workshop.yaml definition file. Covers
                 filename and location, top-level fields, SDK entries,
                 connections, actions, the JSON Schema, and worked examples.

Workshop definition
===================

.. @artefact workshop definition

The :file:`workshop.yaml` file is the workshop definition:
|ws_markup| reads it when it launches, refreshes, or restores a workshop.
You author it by hand in the project directory,
or generate a starting point with :command:`workshop init`.


Filename and location
---------------------

|ws_markup| looks for the definition in the project directory.
Three forms are accepted:

- :file:`workshop.yaml` — single-workshop form at the project root.
- :file:`.workshop.yaml` — alternate single-workshop form at the project root.
- :file:`.workshop/<NAME>.yaml` — named form in the :file:`.workshop/`
  directory.
  :command:`workshop init <NAME>` creates this form.
  When this form is used,
  the value of :samp:`name` in the file must match the file's base name.

All three forms are equivalent in capability;
the choice is a project convention.


Top-level fields
----------------

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`name`
     - string
     - yes
     - Workshop name.
       See :ref:`ref_workshop_definition_name`.

   * - :samp:`base`
     - string
     - yes
     - Base operating-system image.
       See :ref:`ref_workshop_definition_base`.

   * - :samp:`sdks`
     - list
     - no
     - Ordered list of SDK entries to install.
       See :ref:`ref_workshop_definition_sdks`.

   * - :samp:`connections`
     - list
     - no
     - Explicit plug-to-slot connections.
       See :ref:`ref_workshop_definition_connections`.

   * - :samp:`actions`
     - object
     - no
     - Named shell scripts, available via :command:`workshop run`.
       See :ref:`ref_workshop_definition_actions`.

No other keys are accepted.


.. _ref_workshop_definition_name:

Name
----

The :samp:`name` field is a string identifying the workshop.

Constraints:

- Must start with a lowercase letter.
- May contain lowercase letters, digits, and single hyphens between characters.
- At most 40 characters.
- Matches the pattern :regexp:`^[a-z](?:-?[a-z0-9])*$`.

Valid examples: :samp:`dev`, :samp:`go-dev`, :samp:`digits-cuda`.


.. _ref_workshop_definition_base:

Base
----

The :samp:`base` field names the Ubuntu release used as the container image.

Accepted values: :samp:`ubuntu@20.04`, :samp:`ubuntu@22.04`,
:samp:`ubuntu@24.04`, or :samp:`ubuntu@26.04`.

SDKs that declare a base must match the workshop base.
SDKs that do not declare a base are accepted on any workshop.


.. _ref_workshop_definition_sdks:

SDK entries
-----------

The :samp:`sdks` field is a list of SDK entries.
|ws_markup| installs them in declaration order, on top of the base image.
The system SDK is installed first automatically and does not need to be listed.
Each SDK name must appear at most once in the list.

Each entry has the following fields:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`name`
     - string
     - yes
     - SDK to install.
       See :ref:`ref_workshop_definition_sdk_name`.

   * - :samp:`channel`
     - string
     - no
     - Store channel used to retrieve and refresh the SDK.
       See :ref:`ref_workshop_definition_sdk_channel`.

   * - :samp:`plugs`
     - object
     - no
     - Plug definitions and bindings for this SDK entry.
       See :ref:`ref_workshop_definition_sdk_plugs`.

   * - :samp:`slots`
     - object
     - no
     - Additional slot definitions for this SDK entry.
       See :ref:`ref_workshop_definition_sdk_slots`.

No other keys are accepted within an SDK entry.


.. _ref_workshop_definition_sdk_name:

SDK name
~~~~~~~~

The :samp:`name` field identifies the SDK to install.
An optional prefix controls the source:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 3 5

   * - Form
     - Source

   * - :samp:`<name>` (no prefix)
     - SDK Store

   * - :samp:`try-<name>`
     - Locally tried SDK (from :command:`sdkcraft try`)

   * - :samp:`project-<name>`
     - In-project SDK under :file:`.workshop/<name>/`

The underlying :samp:`<name>` must:

- contain at least one lowercase letter,
- consist of lowercase letters, digits, and single hyphens between characters,
- not be :samp:`agent` (reserved),
- be at most 40 characters (44 with :samp:`try-`; 48 with :samp:`project-`).

The names :samp:`system` and :samp:`sketch` identify implicit SDKs
that |ws_markup| installs regardless of whether they appear in the list.
You may list them explicitly to attach per-workshop plug or slot definitions.


.. _ref_workshop_definition_sdk_channel:

Channel
~~~~~~~

The :samp:`channel` field selects the Store channel from which |ws_markup|
retrieves and refreshes the SDK.
Omitting it defaults to :samp:`latest/stable`.

The field has no effect on :samp:`try-`, :samp:`project-`, :samp:`system`,
or :samp:`sketch` entries, but must be well-formed when present.

Format: :samp:`[<track>/]<risk>[/<branch>]` or :samp:`<track>` alone.

Components:

- **risk**: one of :samp:`stable`, :samp:`candidate`, :samp:`beta`, :samp:`edge`.
- **track**: alphanumeric with underscores, hyphens, and dots as separators;
  at most 28 characters; must not equal a risk name.
- **branch**: alphanumeric with hyphens and dots as separators;
  at most 128 characters; must not equal a risk name.

Valid examples: :samp:`stable`, :samp:`edge`, :samp:`1.26`,
:samp:`1.26/stable`, :samp:`latest/stable/hotfix-123`.


.. _ref_workshop_definition_sdk_plugs:

Plugs
~~~~~

The :samp:`plugs` key maps plug names to plug definitions or plug bindings.

Plug names must start with a lowercase letter and contain only lowercase letters,
digits, and single hyphens between characters.

Each value takes one of the following forms:

**Inline plug definition**
   A mapping with an :samp:`interface` key and interface-specific attributes:

   .. code-block:: yaml

      plugs:
        cuda:
          interface: mount
          workshop-target: /usr/local/cuda/lib64

**Interface shorthand**
   A string naming the interface,
   or :samp:`null` to use the plug name as the interface name:

   .. code-block:: yaml

      plugs:
        ssh-agent: null    # interface is ssh-agent
        data: my-iface     # interface is my-iface

**Plug binding**
   A mapping with a single :samp:`bind` key whose value is a plug reference
   in the form :samp:`<sdk>:<plug>`:

   .. code-block:: yaml

      plugs:
        data:
          bind: go:mod-cache

   Constraints on plug bindings:

   - A bound plug must not define any other attributes alongside :samp:`bind`.
   - A bound plug must not also appear in :samp:`connections`.
   - The target plug must not itself be bound.
   - Neither the binding plug nor the target may belong to the system SDK.
   - The target SDK must be listed in the workshop's :samp:`sdks` entries
     or be :samp:`sketch`.

For interface-specific attributes accepted in inline definitions,
see :ref:`ref_sdk_definition_interfaces`.


.. _ref_workshop_definition_sdk_slots:

Slots
~~~~~

The :samp:`slots` key maps slot names to slot definitions.
These supplement the SDK's own slot definitions.

Slot names must start with a lowercase letter and contain only lowercase letters,
digits, and single hyphens between characters.

Each value takes one of the following forms:

**Inline slot definition**
   A mapping with an :samp:`interface` key and interface-specific attributes:

   .. code-block:: yaml

      slots:
        images:
          interface: mount
          workshop-source: $SDK/images

**Interface shorthand**
   A string naming the interface,
   or :samp:`null` to use the slot name as the interface name.

For interface-specific attributes, see :ref:`ref_sdk_definition_interfaces`.


.. _ref_workshop_definition_connections:

Connections
-----------

The :samp:`connections` field is a list of explicit plug-to-slot pairs,
applied in addition to any automatic connections.

Each entry requires both keys:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`plug`
     - string
     - yes
     - Plug reference in the form :samp:`<sdk>:<plug>`.
       The :samp:`<sdk>` portion may be empty
       (for example, :samp:`:ssh-agent`) to refer to the system SDK.

   * - :samp:`slot`
     - string
     - yes
     - Slot reference in the form :samp:`<sdk>:<slot>`.
       The :samp:`<sdk>` portion may be empty to refer to the system SDK.

No other keys are accepted within a connection entry.

Constraints:

- Both endpoints must reference an SDK that is listed in :samp:`sdks`
  or is an implicit SDK (:samp:`system`, :samp:`sketch`).
- A plug that is bound (see :ref:`ref_workshop_definition_sdk_plugs`)
  may not also appear in :samp:`connections`.


.. _ref_workshop_definition_actions:

Actions
-------

The :samp:`actions` field is a map of named shell scripts.
Each action is available via :command:`workshop run`.

Action names must start with a lowercase letter and contain only lowercase
letters, digits, and single hyphens between characters
(the same pattern as :ref:`workshop names <ref_workshop_definition_name>`).

Each value is a YAML string containing the script body.
YAML literal blocks (:samp:`|`) are the conventional form for multi-line scripts.

The script runs inside the workshop as a bash login shell
with :samp:`errexit` and :samp:`pipefail` set.
Positional parameters :samp:`$@`, :samp:`$1`, :samp:`$2`, and so on
receive any arguments passed to the action.


JSON Schema
-----------

.. @artefact workshop schema

The following JSON Schema describes the complete accepted structure of
:file:`workshop.yaml`:

.. dropdown:: Workshop definition schema

   .. literalinclude:: schema.json
      :language: json


Examples
--------

A minimal workshop with a single Store SDK and a pinned track:

.. literalinclude:: ../../examples/workshop-golang.yaml
   :language: yaml
   :caption: workshop.yaml

A workshop with plug bindings across two SDK entries:

.. literalinclude:: ../../examples/workshop-go-dev.yaml
   :language: yaml
   :caption: workshop.yaml

A workshop with explicit connections and inline plug and slot definitions:

.. literalinclude:: ../../examples/workshop-digits-cuda.yaml
   :language: yaml
   :caption: workshop.yaml


See also
--------

Explanation:

- :ref:`exp_workshop_concepts`
- :ref:`exp_workshop_definition`

Reference:

- :ref:`ref_sdk_definition`
- :ref:`ref_sdkcraft_definition`
- :ref:`ref_workshop_init`
- :ref:`ref_workshop_run`
