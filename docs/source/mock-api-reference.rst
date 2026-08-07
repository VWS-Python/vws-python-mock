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

.. autoclass:: mock_vws.VuMarkGenerationFailure
   :members:
   :undoc-members:

.. autoclass:: mock_vws.ModelTargetGenerationFailure
   :members:
   :undoc-members:

.. autoclass:: mock_vws.ModelTargetGenerationWarning(*, message='Warning after creating dataset', details=...)
   :members:
   :undoc-members:

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
