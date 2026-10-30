"""Constants used to make the VWS mock."""

from enum import Enum, unique

from beartype import beartype

VUMARK_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
    b"\x01\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac"
    b"\xfc\xff\x1f\x00\x03\x03\x02\x00\xee\xd9\x97\xa9\x00\x00\x00\x00IEND"
    b"\xaeB`\x82"
)

VUMARK_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>'
)

VUMARK_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
    b"3 0 obj<</Type /Page /MediaBox [0 0 100 100]>>endobj\n"
    b"xref\n0 4\n"
    b"0000000000 65535 f \n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n9\n%%EOF"
)


@beartype
@unique
class ResultCodes(Enum):
    """Constants representing various VWS result codes.

    See
    https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#result-codes.

    Some codes here are not documented in the above link.
    """

    SUCCESS = "Success"
    AUTHENTICATION_FAILURE = "AuthenticationFailure"
    REQUEST_TIME_TOO_SKEWED = "RequestTimeTooSkewed"
    UNKNOWN_TARGET = "UnknownTarget"
    FAIL = "Fail"
    # Processing VuMark templates are tested against the mock.
    TARGET_STATUS_NOT_SUCCESS = "TargetStatusNotSuccess"
    PROJECT_SUSPENDED = "ProjectSuspended"
    # We have never seen a real response for a database in this state, so this
    # casing comes from Vuforia's result codes table rather than from an
    # observed response.
    PROJECT_HAS_NO_API_ACCESS = "ProjectHasNoApiAccess"
    INVALID_ACCEPT_HEADER = "InvalidAcceptHeader"
    INVALID_INSTANCE_ID = "InvalidInstanceId"
    BAD_REQUEST = "BadRequest"


@beartype
@unique
class TargetStatuses(Enum):
    """Constants representing VWS target statuses.

    See the 'status' field in
    https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#target-record
    """

    PROCESSING = "processing"
    SUCCESS = "success"
