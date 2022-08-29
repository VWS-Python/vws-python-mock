"""
Exceptions to raise from validators.
"""

import email.utils
import textwrap
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Dict

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump


class ValidatorException(Exception):
    """
    A base class for exceptions thrown from mock Vuforia cloud recognition
    client endpoints.
    """

    status_code: HTTPStatus
    response_text: str
    headers: Dict[str, str]


class DateHeaderNotGiven(ValidatorException):
    """
    Exception raised when a date header is not given.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = 'Date header required.'
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'text/plain;charset=iso-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class DateFormatNotValid(ValidatorException):
    """
    Exception raised when the date format is not valid.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        self.response_text = 'Malformed date header.'
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'text/plain;charset=iso-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
            'Content-Length': str(len(self.response_text)),
        }


class RequestTimeTooSkewed(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'RequestTimeTooSkewed'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class BadImage(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'BadImage'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        transaction_id = uuid.uuid4().hex
        result_code = ResultCodes.BAD_IMAGE.value

        # The response has an unusual format of separators, so we construct it
        # manually.
        self.response_text = (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class AuthenticationFailure(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'AuthenticationFailure'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        transaction_id = uuid.uuid4().hex
        result_code = ResultCodes.AUTHENTICATION_FAILURE.value

        # The response has an unusual format of separators, so we construct it
        # manually.
        self.response_text = (
            '{"transaction_id":'
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
            'Content-Length': str(len(self.response_text)),
        }


class AuthenticationFailureGoodFormatting(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'AuthenticationFailure' with a standard JSON formatting.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED

        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.AUTHENTICATION_FAILURE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
            'Content-Length': str(len(self.response_text)),
        }


class ImageNotGiven(ValidatorException):
    """
    Exception raised when an image is not given.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = 'No image.'

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class AuthHeaderMissing(ValidatorException):
    """
    Exception raised when an auth header is not given.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        self.response_text = 'Authorization header missing.'

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'text/plain;charset=iso-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
            'Content-Length': str(len(self.response_text)),
        }


class MalformedAuthHeader(ValidatorException):
    """
    Exception raised when an auth header is not given.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        self.response_text = 'Malformed authorization header.'

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'text/plain;charset=iso-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
            'Content-Length': str(len(self.response_text)),
        }


class UnknownParameters(ValidatorException):
    """
    Exception raised when unknown parameters are given.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = 'Unknown parameters in the request.'

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class InactiveProject(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'InactiveProject'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        transaction_id = uuid.uuid4().hex
        result_code = ResultCodes.INACTIVE_PROJECT.value
        # The response has an unusual format of separators, so we construct it
        # manually.
        self.response_text = (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class InvalidMaxNumResults(ValidatorException):
    """
    Exception raised when an invalid value is given as the
    "max_num_results" field.
    """

    def __init__(self, given_value: str) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        invalid_value_message = (
            f"Invalid value '{given_value}' in form data part 'max_result'. "
            'Expecting integer value in range from 1 to 50 (inclusive).'
        )
        self.response_text = invalid_value_message

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class MaxNumResultsOutOfRange(ValidatorException):
    """
    Exception raised when an integer value is given as the "max_num_results"
    field which is out of range.
    """

    def __init__(self, given_value: str) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        integer_out_of_range_message = (
            f'Integer out of range ({given_value}) in form data part '
            "'max_result'. Accepted range is from 1 to 50 (inclusive)."
        )
        self.response_text = integer_out_of_range_message

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class InvalidIncludeTargetData(ValidatorException):
    """
    Exception raised when an invalid value is given as the
    "include_target_data" field.
    """

    def __init__(self, given_value: str) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        unexpected_target_data_message = (
            f"Invalid value '{given_value}' in form data part "
            "'include_target_data'. "
            "Expecting one of the (unquoted) string values 'all', 'none' or "
            "'top'."
        )
        self.response_text = unexpected_target_data_message

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class UnsupportedMediaType(ValidatorException):
    """
    Exception raised when no boundary is found for multipart data.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        self.response_text = ''

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class InvalidAcceptHeader(ValidatorException):
    """
    Exception raised when there is an invalid accept header given.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.NOT_ACCEPTABLE
        self.response_text = ''

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class NoBoundaryFound(ValidatorException):
    """
    Exception raised when an invalid media type is given.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = (
            'java.io.IOException: RESTEASY007550: '
            'Unable to get boundary for multipart'
        )

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'text/html;charset=utf-8',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class QueryOutOfBounds(ValidatorException):
    """
    Exception raised when VWS returns an HTML page which says that there is a
    particular out of bounds error.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        resources_dir = Path(__file__).parent / 'resources'
        filename = 'query_out_of_bounds_response.html'
        oops_resp_file = resources_dir / filename
        text = str(oops_resp_file.read_text())
        self.response_text = text

        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'text/html;charset=iso-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Cache-Control': 'must-revalidate,no-cache,no-store',
            'Content-Length': str(len(self.response_text)),
        }


class ContentLengthHeaderTooLarge(ValidatorException):
    """
    Exception raised when the given content length header is too large.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.GATEWAY_TIMEOUT
        self.response_text = ''
        self.headers = {
            'Connection': 'keep-alive',
            'Content-Length': str(len(self.response_text)),
        }


class ContentLengthHeaderNotInt(ValidatorException):
    """
    Exception raised when the given content length header is not an integer.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = ''
        self.headers = {
            'Connection': 'Close',
            'Content-Length': str(len(self.response_text)),
        }


class RequestEntityTooLarge(ValidatorException):
    """
    Exception raised when the given image file size is too large.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        self.response_text = textwrap.dedent(
            """\
            <html>\r
            <head><title>413 Request Entity Too Large</title></head>\r
            <body>\r
            <center><h1>413 Request Entity Too Large</h1></center>\r
            <hr><center>nginx</center>\r
            </body>\r
            </html>\r
            """,
        )
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Connection': 'Close',
            'Date': date,
            'Server': 'nginx',
            'Content-Type': 'text/html',
            'Content-Length': str(len(self.response_text)),
        }


class DeletedTargetMatched(ValidatorException):
    """
    Exception raised when target which was recently deleted is matched.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        # We return an example 500 response.
        # Each response given by Vuforia is different.
        #
        # Sometimes Vuforia will ignore matching targets with the
        # processing status, but we choose to:
        # * Do the most unexpected thing.
        # * Be consistent with every response.
        resources_dir = Path(__file__).parent.parent / 'resources'
        filename = 'deleted_target_matched_response.html'
        deleted_target_matched_resp_file = resources_dir / filename
        self.response_text = Path(deleted_target_matched_resp_file).read_text(
            encoding='utf-8',
        )
        self.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'text/html;charset=iso-8859-1',
            'Server': 'nginx',
            'Cache-Control': 'must-revalidate,no-cache,no-store',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }


class NoContentType(ValidatorException):
    """
    Exception raised when a content type is either not given or is empty.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        jetty_content_type_error = textwrap.dedent(
            """\
            <html>
            <head>
            <meta http-equiv="Content-Type" content="text/html;charset=utf-8"/>
            <title>Error 400 Bad Request</title>
            </head>
            <body><h2>HTTP ERROR 400 Bad Request</h2>
            <table>
            <tr><th>URI:</th><td>/v1/query</td></tr>
            <tr><th>STATUS:</th><td>400</td></tr>
            <tr><th>MESSAGE:</th><td>Bad Request</td></tr>
            <tr><th>SERVLET:</th><td>Resteasy</td></tr>
            </table>
            <hr><a href="https://eclipse.org/jetty">Powered by Jetty:// 9.4.43.v20210629</a><hr/>

            </body>
            </html>
            """,  # noqa: E501
        )
        self.response_text = jetty_content_type_error
        self.headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'text/html;charset=iso-8859-1',
            'Server': 'nginx',
            'Cache-Control': 'must-revalidate,no-cache,no-store',
            'Date': date,
            'Content-Length': str(len(self.response_text)),
        }
