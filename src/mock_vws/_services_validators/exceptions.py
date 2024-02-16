"""
Exceptions to raise from validators.
"""

import email.utils
import textwrap
import uuid
from http import HTTPStatus
from pathlib import Path

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump


class ValidatorException(Exception):
    """
    A base class for exceptions thrown from mock Vuforia services endpoints.
    """

    status_code: HTTPStatus
    response_text: str
    headers: dict[str, str]


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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.UNKNOWN_TARGET.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.PROJECT_INACTIVE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.AUTHENTICATION_FAILURE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.FAIL.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.METADATA_TOO_LARGE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.TARGET_NAME_EXIST.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
        resources_dir = Path(__file__).parent.parent / "resources"
        filename = "oops_error_occurred_response.html"
        oops_resp_file = resources_dir / filename
        text = str(oops_resp_file.read_text())
        self.response_text = text
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "text/html; charset=UTF-8",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.BAD_IMAGE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.IMAGE_TOO_LARGE.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


class ContentLengthHeaderTooLarge(ValidatorException):
    """
    Exception raised when the given content length header is too large.
    """

    # We skip coverage here as running a test to cover this is very slow.
    def __init__(self) -> None:  # pragma: no cover
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.REQUEST_TIMEOUT
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.response_text = "stream timeout"
        self.headers = {
            "Content-Length": str(len(self.response_text)),
            "Date": date,
            "server": "envoy",
            "Content-Type": "text/plain",
            "Connection": "close",
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
        self.response_text = textwrap.dedent(
            """\
            <html>\r
            <head><title>400 Bad Request</title></head>\r
            <body>\r
            <center><h1>400 Bad Request</h1></center>\r
            </body>\r
            </html>\r
            """,
        )
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "close",
            "Content-Length": str(len(self.response_text)),
            "Date": date,
            "server": "awselb/2.0",
            "Content-Type": "text/html",
        }


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
        self.response_text = ""
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.TARGET_STATUS_NOT_SUCCESS.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
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
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.TARGET_STATUS_PROCESSING.value,
        }
        self.response_text = json_dump(body)
        date = email.utils.formatdate(None, localtime=False, usegmt=True)
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
