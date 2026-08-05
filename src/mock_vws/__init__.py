"""Tools for using a fake implementation of Vuforia."""

from mock_vws._mock_common import MissingSchemeError
from mock_vws._requests_mock_server.decorators import MockVWS
from mock_vws.cloud_query import CloudQueryFailureResponse
from mock_vws.model_target import (
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
)
from mock_vws.vumark import VuMarkGenerationFailure

__all__ = [
    "CloudQueryFailureResponse",
    "MissingSchemeError",
    "MockVWS",
    "ModelTargetGenerationFailure",
    "ModelTargetGenerationWarning",
    "VuMarkGenerationFailure",
]
