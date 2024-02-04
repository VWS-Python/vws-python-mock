.. _mock-api-reference:

API Reference
=============

.. autoclass:: mock_vws.MockVWS
   :members:
   :undoc-members:

.. Many parts of the VuforiaDatabase API are used for the Flask target
.. database app, but Python users are not expected to use them.
.. Therefore, they are not documented.

.. autoclass:: mock_vws.database.VuforiaDatabase
   :members:
   :undoc-members:
   :exclude-members: to_dict, get_target, from_dict, not_deleted_targets, active_targets, inactive_targets, failed_targets, processing_targets

.. autoenum:: mock_vws.states.States
   :members:
   :undoc-members:

.. autoclass:: mock_vws.target.Target

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
