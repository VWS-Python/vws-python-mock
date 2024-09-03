"""
Constants used to make the VWS mock.
"""

from enum import Enum

from beartype import beartype


@beartype
class ResultCodes(Enum):
    """
    Constants representing various VWS result codes.

    See
    https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#result-codes.

    Some codes here are not documented in the above link.
    """

    SUCCESS = "Success"
    TARGET_CREATED = "TargetCreated"
    AUTHENTICATION_FAILURE = "AuthenticationFailureError"
    REQUEST_TIME_TOO_SKEWED = "RequestTimeTooSkewed"
    TARGET_NAME_EXIST = "TargetNameExistError"
    UNKNOWN_TARGET = "UnknownTargetError"
    BAD_IMAGE = "BadImageError"
    IMAGE_TOO_LARGE = "ImageTooLargeError"
    METADATA_TOO_LARGE = "MetadataTooLargeError"
    # The documentation says "Start date is after the end date" but, at the
    # time of writing, I do not know how to trigger that, therefore this is not
    # tested.
    DATE_RANGE_ERROR = "DateRangeError"
    FAIL = "Fail"
    TARGET_STATUS_PROCESSING = "TargetStatusProcessingError"
    REQUEST_QUOTA_REACHED = "RequestQuotaReached"
    TARGET_STATUS_NOT_SUCCESS = "TargetStatusNotSuccessError"
    PROJECT_INACTIVE = "ProjectInactiveError"
    INACTIVE_PROJECT = "InactiveProjectError"
    TOO_MANY_REQUESTS = "TooManyRequestsError"


@beartype
class TargetStatuses(Enum):
    """
    Constants representing VWS target statuses.

    See the 'status' field in
    https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#target-record
    """

    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
