"""
Exceptions to raise from validators.
"""

import email.utils
import uuid
from http import HTTPStatus
from pathlib import Path

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump


class DateHeaderNotGiven(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'text/plain; charset=ISO-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class DateFormatNotValid(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'text/plain; charset=ISO-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
        }


class RequestTimeTooSkewed(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class BadImage(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class AuthenticationFailure(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
        }


class AuthenticationFailureGoodFormatting(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
        }


class ImageNotGiven(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class AuthHeaderMissing(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'text/plain; charset=ISO-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
        }


class MalformedAuthHeader(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'text/plain; charset=ISO-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'WWW-Authenticate': 'VWS',
        }


class UnknownParameters(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class InactiveProject(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class InvalidMaxNumResults(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class MaxNumResultsOutOfRange(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }

class InvalidIncludeTargetData(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class UnsupportedMediaType(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class InvalidAcceptHeader(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class BoundaryNotInBody(Exception):
    """
    Exception raised when the form boundary is not in the request body.
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
            'java.lang.RuntimeException: RESTEASY007500: '
            'Could find no Content-Disposition header within part'
        )

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'text/html;charset=UTF-8',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class NoBoundaryFound(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'text/html;charset=UTF-8',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class QueryOutOfBounds(Exception):
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

    @property
    def headers(self):
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        return {
            'Content-Type': 'text/html; charset=ISO-8859-1',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
            'Cache-Control': 'must-revalidate,no-cache,no-store',
        }


class ContentLengthHeaderTooLarge(Exception):
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

    @property
    def headers(self):
        return {
            'Connection': 'keep-alive',
        }


class ContentLengthHeaderNotInt(Exception):
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

    @property
    def headers(self):
        return {
            'Connection': 'Close',
        }
