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

    def __init__(
        self,
        *,
        status_code: HTTPStatus,
        response_text: str,
        headers: Mapping[str, str],
    ) -> None:
        """Initialize the HTTP response represented by this error.

        Args:
            status_code: The response's HTTP status.
            response_text: The response body.
            headers: The response headers.
        """
        super().__init__()
        self.status_code = status_code
        self.response_text = response_text
        self.headers = headers


@beartype
class UnknownTargetError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'UnknownTarget'.
    """

    def __init__(self) -> None:
        """Initialize an ``UnknownTarget`` response."""
        status_code = HTTPStatus.NOT_FOUND
        response_text = result_code_response_text(
            result_code=ResultCodes.UNKNOWN_TARGET,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class ProjectInactiveError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'ProjectInactive'.
    """

    def __init__(self) -> None:
        """Initialize a ``ProjectInactive`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.PROJECT_INACTIVE,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class RequestQuotaReachedError(ValidatorError):
    """Exception raised when a database's request quota is exhausted.

    This response is based on Vuforia's documented status code and its common
    VWS error response shape. It has not been verified against a real database
    with an exhausted quota.
    """

    def __init__(self) -> None:
        """Initialize a ``RequestQuotaReached`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.REQUEST_QUOTA_REACHED,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class TooManyRequestsError(ValidatorError):
    """Exception raised when a database exceeds its request rate limit.

    Real Vuforia's Envoy layer applies the rate limits, before the request
    reaches the application, and its response has no body and no
    ``Content-Type`` header. This was observed on 2026-09-08.
    """

    def __init__(self) -> None:
        """Initialize a ``429 Too Many Requests`` response."""
        status_code = HTTPStatus.TOO_MANY_REQUESTS
        response_text = ""
        headers = {
            "Connection": "keep-alive",
            "Content-Length": "0",
            "Date": http_date(),
            "server": "envoy",
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
            "x-envoy-ratelimited": "true",
            "x-envoy-upstream-service-time": "5",
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class TargetQuotaReachedError(ValidatorError):
    """Exception raised when a database's target quota is exhausted."""

    def __init__(self) -> None:
        """Initialize a ``TargetQuotaReached`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.TARGET_QUOTA_REACHED,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class ProjectSuspendedError(ValidatorError):
    """Exception raised when a database has been suspended."""

    def __init__(self) -> None:
        """Initialize a ``ProjectSuspended`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.PROJECT_SUSPENDED,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class ProjectHasNoApiAccessError(ValidatorError):
    """Exception raised when a database cannot make API requests."""

    def __init__(self) -> None:
        """Initialize a ``ProjectHasNoApiAccess`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.PROJECT_HAS_NO_API_ACCESS,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class AuthenticationFailureError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'AuthenticationFailure'.
    """

    def __init__(self) -> None:
        """Initialize an ``AuthenticationFailure`` response."""
        status_code = HTTPStatus.UNAUTHORIZED
        response_text = result_code_response_text(
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


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
        response_text = result_code_response_text(
            result_code=ResultCodes.FAIL,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class BadRequestError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'BadRequest'.
    """

    def __init__(self) -> None:
        """Initialize a ``BadRequest`` response."""
        status_code = HTTPStatus.BAD_REQUEST
        response_text = result_code_response_text(
            result_code=ResultCodes.BAD_REQUEST,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class MetadataTooLargeError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'MetadataTooLarge'.
    """

    def __init__(self) -> None:
        """Initialize a ``MetadataTooLarge`` response."""
        status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        response_text = result_code_response_text(
            result_code=ResultCodes.METADATA_TOO_LARGE,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class TargetNameExistError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'TargetNameExist'.
    """

    def __init__(self) -> None:
        """Initialize a ``TargetNameExist`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.TARGET_NAME_EXIST,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class BadImageError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'BadImage'.
    """

    def __init__(self) -> None:
        """Initialize a ``BadImage`` response."""
        status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        response_text = result_code_response_text(
            result_code=ResultCodes.BAD_IMAGE,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class ImageTooLargeError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'ImageTooLarge'.
    """

    def __init__(self) -> None:
        """Initialize an ``ImageTooLarge`` response."""
        status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        response_text = result_code_response_text(
            result_code=ResultCodes.IMAGE_TOO_LARGE,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class RequestTimeTooSkewedError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'RequestTimeTooSkewed'.
    """

    def __init__(self) -> None:
        """Initialize a ``RequestTimeTooSkewed`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.REQUEST_TIME_TOO_SKEWED,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class ContentLengthHeaderTooLargeError(ValidatorError):
    """
    Exception raised when the given content length header is too
    large.
    """

    def __init__(self) -> None:
        """Initialize a stream timeout response."""
        status_code = HTTPStatus.REQUEST_TIMEOUT
        response_text = "stream timeout"
        headers = {
            "Content-Length": str(object=len(response_text)),
            "Date": http_date(),
            "server": "envoy",
            "Content-Type": "text/plain",
            "Connection": "close",
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class RequestHeaderOrCookieTooLargeError(ValidatorError):
    """Exception raised when a request header line is too long for NGINX.

    NGINX rejects the request before it reaches the Vuforia application,
    so this takes precedence over every other validation, including
    authorization.
    """

    def __init__(self) -> None:
        """Initialize an NGINX request header too large response."""
        status_code = HTTPStatus.BAD_REQUEST
        response_text = "".join(
            f"{line}\r\n"
            for line in (
                "<html>",
                (
                    "<head><title>400 Request Header Or Cookie Too Large"
                    "</title></head>"
                ),
                "<body>",
                "<center><h1>400 Bad Request</h1></center>",
                "<center>Request Header Or Cookie Too Large</center>",
                "<hr><center>nginx</center>",
                "</body>",
                "</html>",
            )
        )
        headers = {
            **_STANDARD_HEADERS,
            "Content-Type": "text/html",
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class ContentLengthHeaderNotIntError(ValidatorError):
    """
    Exception raised when the given content length header is not an
    integer.
    """

    def __init__(self) -> None:
        """Initialize a load balancer bad request response."""
        status_code = HTTPStatus.BAD_REQUEST
        response_text = textwrap.dedent(
            text="""\
            <html>\r
            <head><title>400 Bad Request</title></head>\r
            <body>\r
            <center><h1>400 Bad Request</h1></center>\r
            </body>\r
            </html>\r
            """,
        )
        headers = {
            "Connection": "close",
            "Content-Length": str(object=len(response_text)),
            "Date": http_date(),
            "Server": "awselb/2.0",
            "Content-Type": "text/html",
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class UnnecessaryRequestBodyError(ValidatorError):
    """Exception raised when a request body is given but not necessary."""

    def __init__(self) -> None:
        """Initialize an empty bad request response."""
        status_code = HTTPStatus.BAD_REQUEST
        response_text = ""
        headers = {
            "server": "envoy",
            "Date": http_date(),
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class TargetStatusNotSuccessError(ValidatorError):
    """
    Exception raised when trying to update a target that does not have a
    success status.
    """

    def __init__(self) -> None:
        """Initialize a ``TargetStatusNotSuccess`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.TARGET_STATUS_NOT_SUCCESS,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class InvalidAcceptHeaderError(ValidatorError):
    """Exception raised when an unsupported Accept header is given."""

    def __init__(self) -> None:
        """Initialize an ``InvalidAcceptHeader`` response."""
        status_code = HTTPStatus.BAD_REQUEST
        response_text = result_code_response_text(
            result_code=ResultCodes.INVALID_ACCEPT_HEADER,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class InvalidInstanceIdError(ValidatorError):
    """Exception raised when an invalid instance_id is given."""

    def __init__(self) -> None:
        """Initialize an ``InvalidInstanceId`` response."""
        status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        response_text = result_code_response_text(
            result_code=ResultCodes.INVALID_INSTANCE_ID,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class InvalidTargetTypeError(ValidatorError):
    """Exception raised when the target type is not valid for the
    operation.
    """

    def __init__(self) -> None:
        """Initialize an ``InvalidTargetType`` response."""
        status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        response_text = result_code_response_text(
            result_code=ResultCodes.INVALID_TARGET_TYPE,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )


@beartype
class TargetStatusProcessingError(ValidatorError):
    """Exception raised when trying to delete a target which is processing."""

    def __init__(self) -> None:
        """Initialize a ``TargetStatusProcessing`` response."""
        status_code = HTTPStatus.FORBIDDEN
        response_text = result_code_response_text(
            result_code=ResultCodes.TARGET_STATUS_PROCESSING,
        )
        headers = {
            **_STANDARD_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(response_text)),
        }
        super().__init__(
            status_code=status_code,
            response_text=response_text,
            headers=headers,
        )
