.. _mock-api-reference:

API Reference
=============

.. autoclass:: mock_vws.MockVWS
   :members:
   :undoc-members:

.. autoclass:: mock_vws.MissingSchemeError
   :members:
   :undoc-members:

.. autoclass:: mock_vws.CloudQueryFailureResponse(*, status_code, headers={}, body=b'')
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

.. Many parts of the CloudDatabase API are used for the Flask target
.. database app, but Python users are not expected to use them.
.. Therefore, they are not documented.

.. autoclass:: mock_vws.database.CloudDatabase
   :members:
   :undoc-members:
   :exclude-members: to_dict, get_target, from_dict, not_deleted_targets, active_targets, inactive_targets, failed_targets, processing_targets

.. autoclass:: mock_vws.database.VuMarkDatabase
   :members:
   :undoc-members:
   :exclude-members: to_dict, from_dict, not_deleted_targets

.. autoclass:: mock_vws.request_rate_limits.RequestRateLimit
   :members:
   :undoc-members:
   :exclude-members: to_dict, from_dict

.. autoclass:: mock_vws.request_rate_limits.RequestRateLimits
   :members:
   :undoc-members:
   :exclude-members: to_dict, from_dict, for_endpoint

.. autoclass:: mock_vws.request_rate_limits.RateLimitedEndpoint
   :members:
   :undoc-members:

.. autodata:: mock_vws.request_rate_limits.DOCUMENTED_REQUEST_RATE_LIMITS

.. autoclass:: mock_vws.states.States
   :members:
   :undoc-members:

.. autoclass:: mock_vws.database_type.DatabaseType
   :members:
   :undoc-members:

.. autoclass:: mock_vws.target.ImageTarget

.. autoclass:: mock_vws.target.VuMarkTarget

Image matchers
--------------

.. autoprotocol:: mock_vws.image_matchers.ImageMatcher

.. autoclass:: mock_vws.image_matchers.ExactMatcher

.. autoclass:: mock_vws.image_matchers.StructuralSimilarityMatcher

Target raters
-------------

.. autoprotocol:: mock_vws.target_raters.TargetTrackingRater

.. autoclass:: mock_vws.target_raters.RandomTargetTrackingRater

.. autoclass:: mock_vws.target_raters.HardcodedTargetTrackingRater

.. autoclass:: mock_vws.target_raters.BrisqueTargetTrackingRater

Server integration
------------------

``mock_vws.server_api`` is the supported interface for the core operations used by VWS and VWQ HTTP servers.
The bundled Flask applications use these same imports.
Adapters provide request data and database state, call core operations, and translate their results into HTTP responses.
Validation order, matching and response construction remain owned by core.

The interface exports the following operations and supporting types:

* Request handling: ``RequestData``, ``json_dump``, ``sorted_targets``, ``matching_targets`` and ``get_database_matching_server_keys``.
* Services validation: ``run_services_validators``, ``RequestRateLimiter``, ``ServicesValidatorError``, ``FailError``, ``InvalidAcceptHeaderError``, ``InvalidTargetTypeError``, ``TargetStatusNotSuccessError`` and ``TargetStatusProcessingError``.
* Query handling: ``run_query_validators``, ``ValidatedQuery``, ``get_query_match_response_text`` and ``QueryValidatorError``.
* Model Target datasets: ``create_model_target_dataset``, ``delete_model_target_dataset``, ``download_model_target_dataset`` and ``get_model_target_dataset_status``.
* OAuth2: ``create_oauth2_client_credential``, ``delete_oauth2_client_credential``, ``list_oauth2_client_credentials``, ``oauth2_token`` and ``update_oauth2_client_credential_scopes``.
* Recognition reports: ``create_reco_counts_report`` and ``download_reco_counts_report``.
* Response constants: ``ResultCodes``, ``TargetStatuses``, ``VUMARK_PDF``, ``VUMARK_PNG`` and ``VUMARK_SVG``.

For example, a query adapter passes the result of ``run_query_validators`` to ``get_query_match_response_text``.
If validation raises ``QueryValidatorError``, its ``status_code``, ``headers`` and ``response_text`` describe the HTTP response to send.
``ServicesValidatorError`` provides the same response attributes for VWS.
Use the distinct error types to keep each API's error handling scoped to its own validators.

Servers also use the public modules ``mock_vws.database``, ``mock_vws.database_type``, ``mock_vws.image_matchers``, ``mock_vws.model_target``, ``mock_vws.reco_counts``, ``mock_vws.request_rate_limits``, ``mock_vws.states``, ``mock_vws.target``, ``mock_vws.target_manager`` and ``mock_vws.target_raters``.
Database and target ``to_dict`` and ``from_dict`` methods support the target-manager transport.
These public imports and their typed signatures form the server interface.
Underscore-prefixed modules remain implementation details.

Server consumers should pin a compatible core revision or release.
The :doc:`versioning-and-api-stability` policy applies to this interface, including documenting incompatible changes in the changelog.

Core operations do not require Flask.
The package still installs Flask while the bundled server lives here.
``Werkzeug`` remains a core dependency because query validation uses its multipart parser.
