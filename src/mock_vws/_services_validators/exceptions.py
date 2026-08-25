"""Exceptions to raise from validators."""

import textwrap
from collections.abc import Mapping
from http import HTTPStatus
from typing import Final

from beartype import beartype

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import http_date, result_code_response_text

# The headers which VWS gives with a JSON error response, apart from those
# which depend on the response itself.
_STANDARD_HEADERS: Final[Mapping[str, str]] = {
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "server": "envoy",
    "x-envoy-upstream-service-time": "5",
    "strict-transport-security": "max-age=31536000",
    "x-aws-region": "us-east-2, us-west-2",
    "x-content-type-options": "nosniff",
}


@beartype
class ValidatorError(Exception):
    """
    A base class for exceptions thrown from mock Vuforia services
    endpoints.
    """

    status_code: HTTPStatus
    response_text: str
    headers: Mapping[str, str]


@beartype
class UnknownTargetError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'UnknownTarget'.
    """

    def __init__(self) -> None:
        """Initialize an ``UnknownTarget`` response."""
        super().__init__()
        self.status_code = HTTPStatus.NOT_FOUND
        self.response_text = result_code_response_text(
            result_code=ResultCodes.UNKNOWN_TARGET,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class ProjectInactiveError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'ProjectInactive'.
    """

    def __init__(self) -> None:
        """Initialize a ``ProjectInactive`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.PROJECT_INACTIVE,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class RequestQuotaReachedError(ValidatorError):
    """Exception raised when a database's request quota is exhausted.

    This response is based on Vuforia's documented status code and its common
    VWS error response shape. It has not been verified against a real database
    with an exhausted quota.
    """

    def __init__(self) -> None:
        """Initialize a ``RequestQuotaReached`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.REQUEST_QUOTA_REACHED,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class TooManyRequestsError(ValidatorError):
    """Exception raised when a database exceeds its request rate limit."""

    def __init__(self) -> None:
        """Initialize a ``TooManyRequests`` response."""
        super().__init__()
        self.status_code = HTTPStatus.TOO_MANY_REQUESTS
        self.response_text = result_code_response_text(
            result_code=ResultCodes.TOO_MANY_REQUESTS,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class TargetQuotaReachedError(ValidatorError):
    """Exception raised when a database's target quota is exhausted."""

    def __init__(self) -> None:
        """Initialize a ``TargetQuotaReached`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.TARGET_QUOTA_REACHED,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class ProjectSuspendedError(ValidatorError):
    """Exception raised when a database has been suspended."""

    def __init__(self) -> None:
        """Initialize a ``ProjectSuspended`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.PROJECT_SUSPENDED,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class ProjectHasNoApiAccessError(ValidatorError):
    """Exception raised when a database cannot make API requests."""

    def __init__(self) -> None:
        """Initialize a ``ProjectHasNoApiAccess`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.PROJECT_HAS_NO_API_ACCESS,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class AuthenticationFailureError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'AuthenticationFailure'.
    """

    def __init__(self) -> None:
        """Initialize an ``AuthenticationFailure`` response."""
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        self.response_text = result_code_response_text(
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class FailError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'Fail'.
    """

    def __init__(self, *, status_code: HTTPStatus) -> None:
        """
        Args:
            status_code: The status code to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = status_code
        self.response_text = result_code_response_text(
            result_code=ResultCodes.FAIL,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class BadRequestError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'BadRequest'.
    """

    def __init__(self) -> None:
        """Initialize a ``BadRequest`` response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = result_code_response_text(
            result_code=ResultCodes.BAD_REQUEST,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class MetadataTooLargeError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'MetadataTooLarge'.
    """

    def __init__(self) -> None:
        """Initialize a ``MetadataTooLarge`` response."""
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        self.response_text = result_code_response_text(
            result_code=ResultCodes.METADATA_TOO_LARGE,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class TargetNameExistError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'TargetNameExist'.
    """

    def __init__(self) -> None:
        """Initialize a ``TargetNameExist`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.TARGET_NAME_EXIST,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class BadImageError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'BadImage'.
    """

    def __init__(self) -> None:
        """Initialize a ``BadImage`` response."""
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        self.response_text = result_code_response_text(
            result_code=ResultCodes.BAD_IMAGE,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class ImageTooLargeError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'ImageTooLarge'.
    """

    def __init__(self) -> None:
        """Initialize an ``ImageTooLarge`` response."""
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        self.response_text = result_code_response_text(
            result_code=ResultCodes.IMAGE_TOO_LARGE,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class RequestTimeTooSkewedError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'RequestTimeTooSkewed'.
    """

    def __init__(self) -> None:
        """Initialize a ``RequestTimeTooSkewed`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.REQUEST_TIME_TOO_SKEWED,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class ContentLengthHeaderTooLargeError(ValidatorError):
    """
    Exception raised when the given content length header is too
    large.
    """

    # We skip coverage here as running a test to cover this is very slow.
    def __init__(self) -> None:  # pragma: no cover
        """Initialize a stream timeout response."""
        super().__init__()
        self.status_code = HTTPStatus.REQUEST_TIMEOUT
        self.response_text = "stream timeout"
        self.headers = {
            "Content-Length": str(object=len(self.response_text)),
            "Date": http_date(),
            "server": "envoy",
            "Content-Type": "text/plain",
            "Connection": "close",
        }


@beartype
class ContentLengthHeaderNotIntError(ValidatorError):
    """
    Exception raised when the given content length header is not an
    integer.
    """

    def __init__(self) -> None:
        """Initialize a load balancer bad request response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = textwrap.dedent(
            text="""\
            <html>\r
            <head><title>400 Bad Request</title></head>\r
            <body>\r
            <center><h1>400 Bad Request</h1></center>\r
            </body>\r
            </html>\r
            """,
        )
        self.headers = {
            "Connection": "close",
            "Content-Length": str(object=len(self.response_text)),
            "Date": http_date(),
            "Server": "awselb/2.0",
            "Content-Type": "text/html",
        }


@beartype
class UnnecessaryRequestBodyError(ValidatorError):
    """Exception raised when a request body is given but not necessary."""

    def __init__(self) -> None:
        """Initialize an empty bad request response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = ""
        self.headers = {
            "server": "envoy",
            "Date": http_date(),
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class TargetStatusNotSuccessError(ValidatorError):
    """
    Exception raised when trying to update a target that does not have a
    success status.
    """

    def __init__(self) -> None:
        """Initialize a ``TargetStatusNotSuccess`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.TARGET_STATUS_NOT_SUCCESS,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class InvalidAcceptHeaderError(ValidatorError):
    """Exception raised when an unsupported Accept header is given."""

    def __init__(self) -> None:
        """Initialize an ``InvalidAcceptHeader`` response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = result_code_response_text(
            result_code=ResultCodes.INVALID_ACCEPT_HEADER,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class InvalidInstanceIdError(ValidatorError):
    """Exception raised when an invalid instance_id is given."""

    def __init__(self) -> None:
        """Initialize an ``InvalidInstanceId`` response."""
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        self.response_text = result_code_response_text(
            result_code=ResultCodes.INVALID_INSTANCE_ID,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class InvalidTargetTypeError(ValidatorError):
    """Exception raised when the target type is not valid for the
    operation.
    """

    def __init__(self) -> None:
        """Initialize an ``InvalidTargetType`` response."""
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        self.response_text = result_code_response_text(
            result_code=ResultCodes.INVALID_TARGET_TYPE,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class TargetStatusProcessingError(ValidatorError):
    """Exception raised when trying to delete a target which is processing."""

    def __init__(self) -> None:
        """Initialize a ``TargetStatusProcessing`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = result_code_response_text(
            result_code=ResultCodes.TARGET_STATUS_PROCESSING,
        )
        self.headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }
