"""Exceptions to raise from validators."""

import email.utils
import textwrap
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING

from beartype import beartype

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump

if TYPE_CHECKING:
    from collections.abc import Mapping


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
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.NOT_FOUND
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.UNKNOWN_TARGET.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class ProjectInactiveError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'ProjectInactive'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.PROJECT_INACTIVE.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class AuthenticationFailureError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'AuthenticationFailure'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNAUTHORIZED
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.AUTHENTICATION_FAILURE.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class FailError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'Fail'.
    """

    def __init__(self, *, status_code: HTTPStatus) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = status_code
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.FAIL.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class MetadataTooLargeError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'MetadataTooLarge'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.METADATA_TOO_LARGE.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class TargetNameExistError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'TargetNameExist'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.TARGET_NAME_EXIST.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class BadImageError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'BadImage'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.BAD_IMAGE.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class ImageTooLargeError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'ImageTooLarge'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.IMAGE_TOO_LARGE.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class RequestTimeTooSkewedError(ValidatorError):
    """Exception raised when Vuforia returns a response with a result code
    'RequestTimeTooSkewed'.
    """

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class ContentLengthHeaderTooLargeError(ValidatorError):
    """
    Exception raised when the given content length header is too
    large.
    """

    # We skip coverage here as running a test to cover this is very slow.
    def __init__(self) -> None:  # pragma: no cover
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.REQUEST_TIMEOUT
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.response_text = "stream timeout"
        self.headers = {
            "Content-Length": str(object=len(self.response_text)),
            "Date": date,
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
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
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
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "close",
            "Content-Length": str(object=len(self.response_text)),
            "Date": date,
            "Server": "awselb/2.0",
            "Content-Type": "text/html",
        }


@beartype
class UnnecessaryRequestBodyError(ValidatorError):
    """Exception raised when a request body is given but not necessary."""

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.BAD_REQUEST
        self.response_text = ""
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "server": "envoy",
            "Date": date,
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
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.TARGET_STATUS_NOT_SUCCESS.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }


@beartype
class TargetStatusProcessingError(ValidatorError):
    """Exception raised when trying to delete a target which is processing."""

    def __init__(self) -> None:
        """
        Attributes:
            status_code: The status code to use in a response if this is
                raised.
            response_text: The response text to use in a response if this
        is
                raised.
        """
        super().__init__()
        self.status_code = HTTPStatus.FORBIDDEN
        body = {
            "transaction_id": uuid.uuid4().hex,
            "result_code": ResultCodes.TARGET_STATUS_PROCESSING.value,
        }
        self.response_text = json_dump(body=body)
        date = email.utils.formatdate(
            timeval=None,
            localtime=False,
            usegmt=True,
        )
        self.headers = {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "server": "envoy",
            "Date": date,
            "x-envoy-upstream-service-time": "5",
            "Content-Length": str(object=len(self.response_text)),
            "strict-transport-security": "max-age=31536000",
            "x-aws-region": "us-east-2, us-west-2",
            "x-content-type-options": "nosniff",
        }
