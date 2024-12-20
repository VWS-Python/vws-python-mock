"""
Constants used to make the VWS mock.
"""

from enum import Enum, unique

from beartype import beartype


@beartype
@unique
class ResultCodes(Enum):
    """Constants representing various VWS result codes.

    See
    https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#result-codes.

    Some codes here are not documented in the above link.
    """

    SUCCESS = "Success"
    TARGET_CREATED = "TargetCreated"
    AUTHENTICATION_FAILURE = "AuthenticationFailure"
    REQUEST_TIME_TOO_SKEWED = "RequestTimeTooSkewed"
    TARGET_NAME_EXIST = "TargetNameExist"
    UNKNOWN_TARGET = "UnknownTarget"
    BAD_IMAGE = "BadImage"
    IMAGE_TOO_LARGE = "ImageTooLarge"
    METADATA_TOO_LARGE = "MetadataTooLarge"
    # The documentation says "Start date is after the end date" but, at the
    # time of writing, I do not know how to trigger that, therefore this is not
    # tested.
    DATE_RANGE_ERROR = "DateRangeError"
    FAIL = "Fail"
    TARGET_STATUS_PROCESSING = "TargetStatusProcessing"
    # While we sometimes hit this, we don't want to keep a database that is
    # constantly in this state.
    REQUEST_QUOTA_REACHED = "RequestQuotaReached"
    TARGET_STATUS_NOT_SUCCESS = "TargetStatusNotSuccess"
    PROJECT_INACTIVE = "ProjectInactive"
    INACTIVE_PROJECT = "InactiveProject"
    TOO_MANY_REQUESTS = "TooManyRequests"


@beartype
@unique
class TargetStatuses(Enum):
    """Constants representing VWS target statuses.

    See the 'status' field in
    https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#target-record
    """

    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
