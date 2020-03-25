import uuid

from requests import codes

from mock_vws._constants import ResultCodes
from mock_vws._mock_common import json_dump


class UnknownTarget(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.NOT_FOUND
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.UNKNOWN_TARGET.value,
        }
        self.response_text = json_dump(body)


class ProjectInactive(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.FORBIDDEN
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.PROJECT_INACTIVE.value,
        }
        self.response_text = json_dump(body)


class AuthenticationFailure(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.UNAUTHORIZED
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.AUTHENTICATION_FAILURE.value,
        }
        self.response_text = json_dump(body)


class Fail(Exception):

    def __init__(self, status_code: int) -> None:
        super().__init__()
        self.status_code = status_code
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.FAIL.value,
        }
        self.response_text = json_dump(body)


class MetadataTooLarge(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.UNPROCESSABLE_ENTITY
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.METADATA_TOO_LARGE.value,
        }
        self.response_text = json_dump(body)


class TargetNameExist(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.FORBIDDEN
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.TARGET_NAME_EXIST.value,
        }
        self.response_text = json_dump(body)


class OopsErrorOccurredResponse(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.INTERNAL_SERVER_ERROR


class BadImage(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.UNPROCESSABLE_ENTITY
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.BAD_IMAGE.value,
        }
        self.response_text = json_dump(body)


class ImageTooLarge(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.UNPROCESSABLE_ENTITY
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.IMAGE_TOO_LARGE.value,
        }
        self.response_text = json_dump(body)


class RequestTimeTooSkewed(Exception):

    def __init__(self):
        super().__init__()
        self.status_code = codes.FORBIDDEN
        body = {
            'transaction_id': uuid.uuid4().hex,
            'result_code': ResultCodes.REQUEST_TIME_TOO_SKEWED.value,
        }
        self.response_text = json_dump(body)


class ContentLengthHeaderTooLarge(Exception):
    pass


class ContentLengthHeaderNotInt(Exception):
    pass


class UnnecessaryRequestBody(Exception):
    pass
