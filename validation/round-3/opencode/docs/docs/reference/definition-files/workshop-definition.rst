.. _ref_workshop_definition:

.. meta::
   :description: Reference for the workshop.yaml definition file. Covers
                 filename conventions, top-level fields, SDK entries, plug
                 bindings, connections, actions, interface attributes, the
                 JSON Schema, and worked examples.

Workshop definition
===================

.. @artefact workshop definition

The :file:`workshop.yaml` file is the workshop definition:
|ws_markup| reads it to launch a workshop.
Workshop users author this file to declare which base image,
SDKs, interface connections, and actions make up their workshop.


Filename and location
---------------------

.. @artefact workshop definition

- The definition file is :file:`workshop.yaml` or :file:`.workshop.yaml`
  at the project root.
  |ws_markup| looks for both names and uses the first one it finds.
- The :file:`.workshop/` directory next to the definition file
  holds per-workshop data, in-project SDKs, and the workshop lock file.
  |ws_markup| creates it automatically; do not edit its contents by hand.


Top-level fields
----------------

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 6

   * - Key
     - Value
     - Description

   * - :samp:`name` (required)
     - string
     - Workshop identifier.
       Must start with a lowercase letter,
       and may contain only lowercase letters, digits,
       and hyphens joining them.
       Up to 40 characters.

   * - :samp:`base` (required)
     - string
     - Base operating system image for the workshop.
       One of :samp:`ubuntu@20.04`, :samp:`ubuntu@22.04`,
       :samp:`ubuntu@24.04`, or :samp:`ubuntu@26.04`.

   * - :samp:`sdks`
     - array
     - Ordered list of SDKs to install on top of the base.
       Each SDK name must be unique within the file.
       The system SDK is installed first implicitly
       and need not be listed.
       See :ref:`ref_workshop_definition_sdks`.

   * - :samp:`connections`
     - array
     - Explicit plug-to-slot connections,
       applied on top of auto-connection.
       See :ref:`ref_workshop_definition_connections`.

   * - :samp:`actions`
     - object
     - Named shell scripts available via
       :command:`workshop run`.
       See :ref:`ref_workshop_definition_actions`.


Nested structures
-----------------

.. _ref_workshop_definition_sdks:

SDK entry
~~~~~~~~~

Each item under :samp:`sdks` is an object with these fields:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 6

   * - Key
     - Value
     - Description

   * - :samp:`name` (required)
     - string
     - SDK identifier.
       The name determines how |ws_markup| resolves the SDK:

       - An unprefixed name resolves to an SDK from the Store.
         Must contain at least one lowercase letter
         and may consist of lowercase letters, digits,
         and hyphens between them.
         Up to 40 characters.
         Cannot be :samp:`agent`.

       - Prefix :samp:`try-` refers to a locally tried SDK
         (set up with :command:`sdkcraft try`).
         The name after the prefix follows the same rules;
         total length up to 44 characters.

       - Prefix :samp:`project-` refers to an in-project SDK
         defined under :file:`.workshop/<NAME>/sdk.yaml`.
         The name after the prefix follows the same rules;
         total length up to 48 characters.

       The prefixes are added by |ws_markup| automatically
       when it writes the workshop state;
       author them in the definition file only when you want
       to refer to a tried or in-project SDK explicitly.

       The name :samp:`system` refers to the built-in system SDK.
       It is installed implicitly even when omitted from the list;
       list it explicitly only when you need to set a channel
       or declare plugs on it.
       The name :samp:`sketch` refers to a sketch SDK
       (created with :command:`workshop sketch-sdk`).

   * - :samp:`channel`
     - string
     - Store channel used to retrieve the SDK at launch and refresh.
       Format: :samp:`[<TRACK>/]<RISK>[/<BRANCH>]`
       or :samp:`<TRACK>` alone or :samp:`<RISK>/<BRANCH>`.

       - **Risk** (required when present): one of
         :samp:`stable`, :samp:`candidate`, :samp:`beta`, or :samp:`edge`.
       - **Track**: up to 28 characters;
         must not equal a risk name.
         Defaults to :samp:`latest`.
       - **Branch**: up to 128 characters;
         must not equal a risk name.

       Default is :samp:`latest/stable`.
       Only applies to Store SDKs;
       for tried, in-project, and system SDKs
       the value has no effect but must still be well formed.

   * - :samp:`plugs`
     - object
     - Plug bindings and additional plug definitions for the SDK.
       Each key is a plug name
       (starts with a lowercase letter;
       lowercase letters, digits, hyphens joining them).
       Each value is either an inline plug definition
       or a binding to another plug.
       See :ref:`ref_workshop_definition_plugs`.

   * - :samp:`slots`
     - object
     - Additional slot definitions grafted onto the SDK by the workshop.
       Each key is a slot name
       (same naming rules as plug names).
       Each value is an inline slot definition.
       Only the :samp:`mount` and :samp:`tunnel` interfaces
       support slots on regular SDKs.
       See :ref:`ref_workshop_definition_interfaces`.


.. _ref_workshop_definition_plugs:

Plug definitions and bindings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A plug value under :samp:`sdks.*.plugs` can be one of:

- **Inline plug definition** — a mapping that specifies
  :samp:`interface` and any interface-specific attributes.
  The plug is owned by the SDK that declares it.

- **Binding** — a mapping with a single :samp:`bind` key
  whose value is a plug reference
  (see :ref:`ref_workshop_definition_references`).
  A bound plug inherits the interface and attributes
  of the plug it binds to;
  it must not define its own attributes.

  Constraints on bindings:

  - A bound plug cannot also appear in
    :samp:`connections` — bound plugs are wired internally.
  - Cannot bind a system SDK plug.
  - Cannot bind a plug to itself.
  - Cannot chain bindings
    (plug A binds to plug B which itself binds to plug C).

.. _ref_workshop_definition_references:

Plug and slot references
~~~~~~~~~~~~~~~~~~~~~~~~

Plug and slot references appear in :samp:`bind` values
and in :samp:`connections` entries.
The format is:

   :samp:`<SDK>:<NAME>`

- :samp:`<SDK>` is the SDK name as declared in the :samp:`sdks` list
  (or the implicit :samp:`system` SDK).
- :samp:`<NAME>` is the plug or slot name within that SDK.
- For the system SDK, the :samp:`<SDK>` portion may be omitted:
  :samp:`:ssh-agent` is equivalent to :samp:`system:ssh-agent`.


.. _ref_workshop_definition_connections:

Connection entry
~~~~~~~~~~~~~~~~

Each item under :samp:`connections` is an object:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 6

   * - Key
     - Value
     - Description

   * - :samp:`plug` (required)
     - string
     - Plug reference in the form :samp:`<SDK>:<PLUG>`.
       The :samp:`<SDK>` portion may be empty
       to refer to the system SDK
       (for example, :samp:`:ssh-agent`).
       The plug must not be bound.

   * - :samp:`slot` (required)
     - string
     - Slot reference in the form :samp:`<SDK>:<SLOT>`.
       The :samp:`<SDK>` portion may be empty
       to refer to the system SDK.

Both the plug's SDK and the slot's SDK
must be present in the :samp:`sdks` list
or be an implicit SDK (:samp:`system` or :samp:`sketch`).
The plug and the slot must share the same interface.


.. _ref_workshop_definition_actions:

Action entry
~~~~~~~~~~~~

Each key under :samp:`actions` is an action name;
the value is a shell script string.

- Action names follow the same rules as workshop names:
  start with a lowercase letter;
  contain only lowercase letters, digits,
  and hyphens joining them.
- The script runs inside the workshop
  as a login shell with :envvar:`errexit` and :envvar:`pipefail` set.
- Positional parameters (``$@``, ``$1``, ``$2``, …)
  receive any arguments passed after the action name
  via :command:`workshop run`.
- One-liner and YAML literal-block (``|``) forms are both accepted.
  Trailing newlines are normalised.

.. code-block:: yaml
   :caption: workshop.yaml — actions

   actions:
     lint: |
       go vet
       golangci-lint run
     tests: go test "$@"


.. _ref_workshop_definition_interfaces:

Interfaces
----------

Plug and slot values in :file:`workshop.yaml`
use the same shape as in :file:`sdk.yaml`.
A plug or slot value is an inline definition:
a mapping that specifies the :samp:`interface`
and any interface-specific attributes.

.. include:: _interfaces/camera.rst

.. include:: _interfaces/custom-device.rst

.. include:: _interfaces/desktop.rst

.. include:: _interfaces/gpu.rst

.. include:: _interfaces/mount.rst

.. include:: _interfaces/ssh-agent.rst

.. include:: _interfaces/tunnel.rst


JSON Schema
-----------

.. @artefact workshop schema

The following JSON Schema describes the structure above:

.. dropdown:: Workshop definition schema

   .. literalinclude:: schema.json
      :language: json


Examples
--------

Minimal workshop with a single SDK from the Store:

.. literalinclude:: ../../examples/workshop-try-go.yaml
   :language: yaml
   :caption: workshop.yaml

Workshop with multiple SDKs, plug bindings, connections, and actions:

.. literalinclude:: ../../examples/workshop-digits-cuda.yaml
   :language: yaml
   :caption: workshop.yaml

Workshop with a bound plug sharing another SDK's cache:

.. literalinclude:: ../../examples/workshop-go-dev.yaml
   :language: yaml
   :caption: workshop.yaml

Workshop with actions:

.. literalinclude:: ../../examples/workshop-golang.yaml
   :language: yaml
   :caption: workshop.yaml


See also
--------

Explanation:

- :ref:`exp_workshop_definition`
- :ref:`exp_workshop_concepts`
- :ref:`exp_plugs_slots`
- :ref:`exp_interface_concepts`
- :ref:`exp_plug_bindings`

How-to:

- :ref:`how_add_mounts`
- :ref:`how_forward_ports`
- :ref:`how_resolve_plug_conflicts`

Reference:

- :ref:`ref_sdk_definition`
- :ref:`ref_sdkcraft_definition`
- :ref:`ref_workshop_internals`

Tutorial:

- :ref:`tut_get_started`
- :ref:`tut_work_with_interfaces`
