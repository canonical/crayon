.. _ref_workshop_definition:

.. meta::
   :description: Reference for the workshop.yaml definition file. Covers
                 filename conventions, top-level fields, SDK entries, plug
                 and slot addressing, connections, actions, the JSON Schema,
                 and worked examples.

Workshop definition
====================

.. @artefact workshop definition

The :file:`workshop.yaml` file is the workshop definition:
it declares a workshop's base image, the SDKs installed on it,
any explicit plug-to-slot connections, and named actions.
|ws_markup| reads it to launch and refresh a workshop.


Filename and location
-----------------------

.. @artefact workshop definition

A project with a single workshop stores its definition
at :file:`workshop.yaml` in the project root
(or the hidden variant :file:`.workshop.yaml`;
only one of the two may be present).

A project with multiple, named workshops stores each definition instead
under :file:`.workshop/<NAME>.yaml`.
Each file's :samp:`name` field must match its own file name
(without the :samp:`.yaml` extension).

A root-level :file:`workshop.yaml` and files under :file:`.workshop/`
cannot coexist in the same project;
|ws_markup| reports an error if both are present.

See :ref:`how_use_multiple_workshops` for the multi-workshop task guide.


Top-level fields
-------------------

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 6

   * - Key
     - Value
     - Description

   * - :samp:`name` (required)
     - string
     - Workshop name. Must start with a lowercase letter and may consist of
       lowercase letters, digits, and hyphens between them.
       Up to 40 characters.
       Must match the definition file's basename when stored under
       :file:`.workshop/`.

   * - :samp:`base` (required)
     - string
     - Base operating system image for the workshop.
       One of :samp:`ubuntu@20.04`, :samp:`ubuntu@22.04`, :samp:`ubuntu@24.04`,
       or :samp:`ubuntu@26.04`.
       An SDK that declares its own :samp:`base` must match this value;
       an SDK with no declared base is accepted on any workshop base.

   * - :samp:`sdks`
     - array
     - Ordered list of SDKs to install on top of the base.
       Each entry references an existing SDK — see
       :ref:`ref_workshop_definition_sdks`.
       The system SDK does not need to be listed: it is always present.

   * - :samp:`connections`
     - array
     - Explicit plug-to-slot pairings, applied on top of auto-connection.
       See :ref:`ref_workshop_definition_connections`.

   * - :samp:`actions`
     - object
     - Named shell scripts runnable with :command:`workshop run`.
       See :ref:`ref_workshop_definition_actions`.


.. _ref_workshop_definition_sdks:

SDK entries
--------------

Each entry in :samp:`sdks` is a mapping:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 6

   * - Key
     - Value
     - Description

   * - :samp:`name` (required)
     - string
     - Identifies which SDK to install and where it comes from.
       An unprefixed name (for example, :samp:`go`) resolves to an SDK from
       the Store.
       Prefix it with :samp:`try-` to use a locally tried SDK,
       or :samp:`project-` to use an in-project SDK.
       The underlying name (after any prefix is stripped) must contain at
       least one lowercase letter, may consist of lowercase letters,
       digits, and hyphens between them, cannot be :samp:`agent`, cannot
       chain prefixes, and is at most 40 characters in every case.
       The full field value as written — prefix included — is therefore at
       most 40 characters unprefixed, 44 with :samp:`try-`, or 48 with
       :samp:`project-`.
       Each SDK may only be listed once.

   * - :samp:`channel`
     - string
     - Store channel used to retrieve the SDK at launch and refresh, in the
       form :samp:`[<TRACK>/]<RISK>[/<BRANCH>]`, :samp:`<TRACK>`, or
       :samp:`<RISK>/<BRANCH>`.
       :samp:`<RISK>` is one of :samp:`stable`, :samp:`candidate`,
       :samp:`beta`, or :samp:`edge`.
       Defaults to :samp:`latest/stable`.
       Only meaningful for Store SDKs; ignored, but still validated, for
       :samp:`try-`, :samp:`project-`, and system SDKs.

   * - :samp:`plugs`
     - object
     - Plugs the SDK requests, keyed by plug name.
       Each value is either an inline, interface-specific definition or a
       binding to another plug — see :ref:`ref_workshop_definition_plugs`
       for addressing and binding, and :ref:`ref_workshop_definition_interfaces`
       for the interface-specific attributes.

   * - :samp:`slots`
     - object
     - Additional slots grafted onto the SDK, keyed by slot name.
       Only the :samp:`mount` and :samp:`tunnel` interfaces support slots on
       regular SDKs. See :ref:`ref_workshop_definition_interfaces`.


.. _ref_workshop_definition_plugs:

Plug and slot references
----------------------------

Plugs and slots are addressed throughout the file as :samp:`<sdk>:<name>`.
Omitting the :samp:`<sdk>` part (for example, :samp:`:ssh-agent`) refers to
the system SDK.

A plug can either declare its own inline attributes or bind to another plug
instead — the two are mutually exclusive:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 6

   * - Key
     - Value
     - Description

   * - :samp:`bind`
     - string
     - A :samp:`<sdk>:<plug>` reference to another plug in the same
       workshop.
       The target must use the same interface, must not itself be bound,
       and must not belong to the system SDK.
       A bound plug cannot declare any other attribute and cannot also
       appear in :samp:`connections`.


.. _ref_workshop_definition_interfaces:

Interfaces
-------------

An inline plug or slot definition is a mapping
that specifies the :samp:`interface` and any interface-specific attributes.

.. include:: _interfaces/camera.rst

.. include:: _interfaces/custom-device.rst

.. include:: _interfaces/desktop.rst

.. include:: _interfaces/gpu.rst

.. include:: _interfaces/mount.rst

.. include:: _interfaces/ssh-agent.rst

.. include:: _interfaces/tunnel.rst


.. _ref_workshop_definition_connections:

Connections
--------------

Each entry in :samp:`connections` explicitly pairs a plug with a slot:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 6

   * - Key
     - Value
     - Description

   * - :samp:`plug` (required)
     - string
     - A :samp:`<sdk>:<plug>` reference.

   * - :samp:`slot` (required)
     - string
     - A :samp:`<sdk>:<slot>` reference.

Both references must name an SDK present in the workshop,
or the implicit system or sketch SDK.
The plug and the slot must share the same interface.
A plug already bound to another plug (see
:ref:`ref_workshop_definition_plugs`) cannot also appear here.

Explicit connections apply on top of the interfaces' own auto-connection
behavior; see :ref:`exp_interface_connections` for the full model.


.. _ref_workshop_definition_actions:

Actions
----------

Each key in :samp:`actions` is the action's name;
each value is the shell script body executed by :command:`workshop run`.

- **Name:** must start with a lowercase letter and contain only lowercase
  letters, digits, and hyphens between them.
- **Value:** the script body, run under a bash login shell with
  :samp:`errexit` and :samp:`pipefail` set.
  Arguments given after the action name on the command line are forwarded
  to the script as positional parameters
  (:samp:`$@`, :samp:`$1`, :samp:`$2`, ...).

See :ref:`ref_workshop_run` to run an action and :ref:`ref_workshop_actions`
to list the actions a workshop defines.


JSON Schema
--------------

.. @artefact workshop schema

The following JSON Schema describes the structure above:

.. note::

   The field tables above are grounded directly in |ws_markup|'s validation
   code and are authoritative if the two ever diverge.

.. dropdown:: Workshop definition schema

   .. literalinclude:: schema.json
      :language: json


Examples
-----------

A workshop with plugs, slots, and an explicit connection:

.. literalinclude:: ../../examples/workshop-digits-cuda.yaml
   :language: yaml
   :caption: workshop.yaml

A workshop using an in-project SDK bound to another SDK's plug:

.. literalinclude:: ../../examples/workshop-go-dev.yaml
   :language: yaml
   :caption: workshop.yaml


See also
-----------

Explanation:

- :ref:`exp_in_project_sdk`
- :ref:`exp_interface_connections`
- :ref:`exp_workshop_definition`

How-to:

- :ref:`how_add_actions`
- :ref:`how_use_multiple_workshops`

Reference:

- :ref:`ref_sdk_definition`
- :ref:`ref_sdkcraft_definition`

Tutorial:

- :ref:`tut_get_started`
