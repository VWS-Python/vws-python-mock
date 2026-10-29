"""Tools for using a fake implementation of Vuforia."""

from mock_vws._mock_common import MissingSchemeError
from mock_vws.decorators import MockVWS
from mock_vws.model_target import (
    ModelTargetFailureResponse,
    ModelTargetGenerationFailure,
    ModelTargetGenerationWarning,
    ModelTargetRequest,
)
from mock_vws.vumark import VuMarkGenerationFailure

__all__ = [
    "MissingSchemeError",
    "MockVWS",
    "ModelTargetFailureResponse",
    "ModelTargetGenerationFailure",
    "ModelTargetGenerationWarning",
    "ModelTargetRequest",
    "VuMarkGenerationFailure",
]
