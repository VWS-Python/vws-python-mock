.. _mock-api-reference:

API Reference
=============

.. autoclass:: mock_vws.MockVWS
   :members:
   :undoc-members:

.. autoclass:: mock_vws.MissingSchemeError
   :members:
   :undoc-members:

.. autoclass:: mock_vws.ModelTargetFailureResponse(*, status_code, headers={}, body=b'', requests=...)
   :members:
   :undoc-members:

.. autoclass:: mock_vws.ModelTargetRequest
   :members:
   :undoc-members:

.. autoclass:: mock_vws.VuMarkGenerationFailure
   :members:
   :undoc-members:

.. autoclass:: mock_vws.ModelTargetGenerationFailure
   :members:
   :undoc-members:

.. autoclass:: mock_vws.ModelTargetGenerationWarning(*, message='Warning after creating dataset', details=...)
   :members:
   :undoc-members:

.. py:data:: mock_vws.model_target.JSONValue

   A recursive JSON value type.

.. autoclass:: mock_vws.database.VuMarkDatabase
   :members:
   :undoc-members:
   :exclude-members: to_dict, from_dict, not_deleted_targets

.. autoclass:: mock_vws.states.States
   :members:
   :undoc-members:

.. autoclass:: mock_vws.target.VuMarkTarget

Server integration
------------------

``mock_vws.server_api`` exposes supported validation, response, Model Target, and OAuth2 operations for HTTP adapters.
The bundled Flask server uses the same interface.
Core operations do not require Flask.
Servers use ``mock_vws.database``, ``mock_vws.model_target``, ``mock_vws.states``, ``mock_vws.target`` and ``mock_vws.target_manager`` for state and serialization.
Pin compatible core, server and contract-suite revisions when installing from Git.
