"""
Exceptions to raise from validators.
"""

import email.utils
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Dict

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump


class ValidatorException(Exception):
    """
    A base class for exceptions thrown from mock Vuforia services endpoints.
    """

    status_code: HTTPStatus
    response_text: str
    headers: Dict[str, str]


class UnknownTarget(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'UnknownTarget'.
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
        self.status_code = HTTPStatus.NOT_FOUND
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.UNKNOWN_TARGET.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class ProjectInactive(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'ProjectInactive'.
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
            'result_code': ResultCodes.PROJECT_INACTIVE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
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
        }


class Fail(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code 'Fail'.
    """

    def __init__(self, status_code: HTTPStatus) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = status_code
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class MetadataTooLarge(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'MetadataTooLarge'.
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
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.METADATA_TOO_LARGE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class TargetNameExist(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'TargetNameExist'.
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
            'result_code': ResultCodes.TARGET_NAME_EXIST.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class OopsErrorOccurredResponse(ValidatorException):
    """
    Exception raised when VWS returns an HTML page which says "Oops, an error
    occurred".

    This has been seen to happen when the given name includes a bad character.
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
        resources_dir = Path(__file__).parent.parent / 'resources'
        filename = 'oops_error_occurred_response.html'
        oops_resp_file = resources_dir / filename
        text = str(oops_resp_file.read_text())
        self.response_text = text
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'text/html; charset=UTF-8',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
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
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.BAD_IMAGE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class ImageTooLarge(ValidatorException):
    """
    Exception raised when Vuforia returns a response with a result code
    'ImageTooLarge'.
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
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.IMAGE_TOO_LARGE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
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
        self.headers = {'Connection': 'keep-alive'}


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
        self.headers = {'Connection': 'Close'}


class UnnecessaryRequestBody(ValidatorException):
    """
    Exception raised when a request body is given but not necessary.
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
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class TargetStatusNotSuccess(ValidatorException):
    """
    Exception raised when trying to update a target that does not have a
    success status.
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
            'result_code': ResultCodes.TARGET_STATUS_NOT_SUCCESS.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }


class TargetStatusProcessing(ValidatorException):
    """
    Exception raised when trying to delete a target which is processing.
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
            'result_code': ResultCodes.TARGET_STATUS_PROCESSING.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Server': 'nginx',
            'Date': date,
        }
