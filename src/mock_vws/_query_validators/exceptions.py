"""Exceptions to raise from validators."""

import textwrap
import uuid
from collections.abc import Mapping
from http import HTTPStatus
from typing import Final

from beartype import beartype

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import http_date, result_code_response_text

# The headers which the cloud recognition API gives with an error response,
# apart from those which depend on the response itself.
_BASE_HEADERS: Final[Mapping[str, str]] = {
    "Connection": "keep-alive",
    "Server": "nginx",
}

# The base headers, with the content types which most error responses use.
_JSON_HEADERS: Final[Mapping[str, str]] = {
    **_BASE_HEADERS,
    "Content-Type": "application/json",
}
_TEXT_HEADERS: Final[Mapping[str, str]] = {
    **_BASE_HEADERS,
    "Content-Type": "text/plain;charset=iso-8859-1",
}


@beartype
def _unusual_separators_response_text(
    *,
    result_code: ResultCodes,
    space_after_transaction_id_key: bool,
) -> str:
    """Give a response body with the separators which some cloud reco
    responses use, rather than the separators used elsewhere.

    Args:
        result_code: The result code to give in the response body.
        space_after_transaction_id_key: Whether to put a space after the
            ``transaction_id`` key.

    Returns:
        The body of a cloud recognition error response, with a new transaction
        ID.
    """
    space = " " if space_after_transaction_id_key else ""
    transaction_id = uuid.uuid4().hex
    return (
        f'{{"transaction_id":{space}"{transaction_id}",'
        f'"result_code":"{result_code.value}"}}'
    )


@beartype
class ValidatorError(Exception):
    """
    A base class for exceptions thrown from mock Vuforia cloud
    recognition
    client endpoints.
    """

    status_code: HTTPStatus
    response_text: str
    headers: Mapping[str, str]


@beartype
class DateHeaderNotGivenError(ValidatorError):
    """Exception raised when a date header is not given."""

    def __init__(self) -> None:
        """Initialize a missing date header response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = "Date header required."
        self.headers = {
            **_TEXT_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class DateFormatNotValidError(ValidatorError):
    """Exception raised when the date format is not valid."""

    def __init__(self) -> None:
        """Initialize a malformed date header response."""
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        self.response_text = "Malformed date header."
        self.headers = {
            **_TEXT_HEADERS,
            "Date": http_date(),
            "WWW-Authenticate": "KWS",
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
            **_JSON_HEADERS,
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
        self.response_text = _unusual_separators_response_text(
            result_code=ResultCodes.BAD_IMAGE,
            space_after_transaction_id_key=True,
        )
        self.headers = {
            **_JSON_HEADERS,
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
        self.response_text = _unusual_separators_response_text(
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
            space_after_transaction_id_key=False,
        )
        self.headers = {
            **_JSON_HEADERS,
            "Date": http_date(),
            "WWW-Authenticate": "VWS",
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class AuthenticationFailureGoodFormattingError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'AuthenticationFailure' with a standard JSON formatting.
    """

    def __init__(self) -> None:
        """Initialize a well formatted ``AuthenticationFailure`` body."""
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        self.response_text = result_code_response_text(
            result_code=ResultCodes.AUTHENTICATION_FAILURE,
        )
        self.headers = {
            **_JSON_HEADERS,
            "Date": http_date(),
            "WWW-Authenticate": "VWS",
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class ImageNotGivenError(ValidatorError):
    """Exception raised when an image is not given."""

    def __init__(self) -> None:
        """Initialize a missing image response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = "No image."
        self.headers = {
            **_JSON_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class NoContentDispositionError(ValidatorError):
    """Exception raised when a part of a multipart body has no
    ``Content-Disposition`` header.
    """

    def __init__(self) -> None:
        """Initialize a missing ``Content-Disposition`` header
        response.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = (
            "Could find no Content-Disposition header within part"
        )
        self.headers = {
            **_BASE_HEADERS,
            "Content-Type": "text/plain;charset=utf-8",
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class AuthHeaderMissingError(ValidatorError):
    """Exception raised when an auth header is not given."""

    def __init__(self) -> None:
        """Initialize a missing authorization header response."""
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        self.response_text = "Authorization header missing."
        self.headers = {
            **_TEXT_HEADERS,
            "Date": http_date(),
            "WWW-Authenticate": "KWS",
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class MalformedAuthHeaderError(ValidatorError):
    """Exception raised when an auth header is not given."""

    def __init__(self) -> None:
        """Initialize a malformed authorization header response."""
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        self.response_text = "Malformed authorization header."
        self.headers = {
            **_TEXT_HEADERS,
            "Date": http_date(),
            "WWW-Authenticate": "KWS",
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class UnknownParametersError(ValidatorError):
    """Exception raised when unknown parameters are given."""

    def __init__(self) -> None:
        """Initialize an unknown parameters response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = "Unknown parameters in the request."
        self.headers = {
            **_JSON_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class InactiveProjectError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'InactiveProject'.
    """

    def __init__(self) -> None:
        """Initialize an ``InactiveProject`` response."""
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        self.response_text = _unusual_separators_response_text(
            result_code=ResultCodes.INACTIVE_PROJECT,
            space_after_transaction_id_key=True,
        )
        self.headers = {
            **_JSON_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class InvalidMaxNumResultsError(ValidatorError):
    """Exception raised when an invalid value is given as the
    "max_num_results"
    field.
    """

    def __init__(self, given_value: str) -> None:
        """
        Args:
            given_value: The given value of the "max_num_results" field.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = (
            f"Invalid value '{given_value}' in form data part 'max_result'. "
            "Expecting integer value in range from 1 to 50 (inclusive)."
        )
        self.headers = {
            **_JSON_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class MaxNumResultsOutOfRangeError(ValidatorError):
    """Exception raised when an integer value is given as the
    "max_num_results"
    field which is out of range.
    """

    def __init__(self, given_value: str) -> None:
        """
        Args:
            given_value: The given value of the "max_num_results" field.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = (
            f"Integer out of range ({given_value}) in form data part "
            "'max_result'. Accepted range is from 1 to 50 (inclusive)."
        )
        self.headers = {
            **_JSON_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class InvalidIncludeTargetDataError(ValidatorError):
    """Exception raised when an invalid value is given as the
    "include_target_data" field.
    """

    def __init__(self, given_value: str) -> None:
        """
        Args:
            given_value: The given "include_target_data" value.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = (
            f"Invalid value '{given_value.lower()}' in form data part "
            "'include_target_data'. "
            "Expecting one of the (unquoted) string values 'all', 'none' or "
            "'top'."
        )
        self.headers = {
            **_JSON_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class UnsupportedMediaTypeError(ValidatorError):
    """Exception raised when no boundary is found for multipart data."""

    def __init__(self) -> None:
        """Initialize an unsupported media type response."""
        super().__init__()
        self.status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        self.response_text = ""
        self.headers = {
            **_BASE_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class InvalidAcceptHeaderError(ValidatorError):
    """Exception raised when there is an invalid accept header given."""

    def __init__(self) -> None:
        """Initialize an invalid accept header response."""
        super().__init__()
        self.status_code = HTTPStatus.NOT_ACCEPTABLE
        self.response_text = ""
        self.headers = {
            **_BASE_HEADERS,
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class NoBoundaryFoundError(ValidatorError):
    """Exception raised when an invalid media type is given."""

    def __init__(self) -> None:
        """Initialize a missing multipart boundary response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = "Unable to get boundary for multipart"
        self.headers = {
            **_BASE_HEADERS,
            "Content-Type": "text/plain;charset=utf-8",
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
        """Initialize a gateway timeout response."""
        super().__init__()
        self.status_code = HTTPStatus.GATEWAY_TIMEOUT
        self.response_text = ""
        self.headers = {
            "Connection": "keep-alive",
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class ContentLengthHeaderNotIntError(ValidatorError):
    """
    Exception raised when the given content length header is not an
    integer.
    """

    def __init__(self) -> None:
        """Initialize an empty bad request response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = ""
        self.headers = {
            "Connection": "Close",
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class RequestEntityTooLargeError(ValidatorError):
    """Exception raised when the given image file size is too large."""

    # Ignore coverage on this as there is a bug in urllib3 which means that we
    # do not trigger this exception.
    # See https://github.com/urllib3/urllib3/issues/2733.
    def __init__(self) -> None:  # pragma: no cover
        """Initialize a request entity too large response."""
        super().__init__()
        self.status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        self.response_text = textwrap.dedent(
            text="""\
            <html>\r
            <head><title>413 Request Entity Too Large</title></head>\r
            <body>\r
            <center><h1>413 Request Entity Too Large</h1></center>\r
            <hr><center>nginx</center>\r
            </body>\r
            </html>\r
            """,
        )
        self.headers = {
            "Connection": "Close",
            "Date": http_date(),
            "Server": "nginx",
            "Content-Type": "text/html",
            "Content-Length": str(object=len(self.response_text)),
        }


@beartype
class NoContentTypeError(ValidatorError):
    """
    Exception raised when a content type is either not given or is
    empty.
    """

    def __init__(self) -> None:
        """Initialize a missing content type response."""
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        jetty_content_type_error = textwrap.dedent(
            text="""\
            <html>
            <head>
            <meta http-equiv="Content-Type" content="text/html;charset=ISO-8859-1"/>
            <title>Error 400 Bad Request</title>
            </head>
            <body>
            <h2>HTTP ERROR 400 Bad Request</h2>
            <table>
            <tr><th>URI:</th><td>http://cloudreco.vuforia.com/v1/query</td></tr>
            <tr><th>STATUS:</th><td>400</td></tr>
            <tr><th>MESSAGE:</th><td>Bad Request</td></tr>
            </table>
            <hr/><a href="https://jetty.org/">Powered by Jetty:// 12.0.20</a><hr/>

            </body>
            </html>
            """,  # noqa: E501
        )
        self.response_text = jetty_content_type_error
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "text/html;charset=iso-8859-1",
            "Server": "nginx",
            "Cache-Control": "must-revalidate,no-cache,no-store",
            "Date": http_date(),
            "Content-Length": str(object=len(self.response_text)),
        }
