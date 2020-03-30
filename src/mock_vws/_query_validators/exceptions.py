"""
Exceptions to raise from validators.
"""

import uuid

from requests import codes

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
        self.status_code = codes.BAD_REQUEST
        self.response_text = 'Date header required'


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
        self.status_code = codes.UNAUTHORIZED
        self.response_text = 'Malformed date header.'


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
        self.status_code = codes.FORBIDDEN
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
        }
        self.response_text = json_dump(body)


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
        self.status_code = codes.UNPROCESSABLE_ENTITY
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
        self.status_code = codes.UNAUTHORIZED
        transaction_id = uuid.uuid4().hex
        result_code = ResultCodes.AUTHENTICATION_FAILURE.value

        # The response has an unusual format of separators, so we construct it
        # manually.
        self.response_text = (
            '{"transaction_id": '
            f'"{transaction_id}",'
            f'"result_code":"{result_code}"'
            '}'
        )

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
        self.status_code = codes.BAD_REQUEST
        self.response_text = 'No image.'


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
        self.status_code = codes.BAD_REQUEST
        self.response_text = 'Authorization header missing.'


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
        self.status_code = codes.BAD_REQUEST
        self.response_text = 'Malformed authorization header.'


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
        self.status_code = codes.BAD_REQUEST
        self.response_text = 'Unknown parameters in the request.'


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
        self.status_code = codes.FORBIDDEN
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
        self.status_code = codes.BAD_REQUEST
        unexpected_target_data_message = (
            f"Invalid value '{given_value}' in form data part "
            "'include_target_data'. "
            "Expecting one of the (unquoted) string values 'all', 'none' or 'top'."
        )
        self.response_text = unexpected_target_data_message

