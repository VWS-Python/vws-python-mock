# TODO put status code in each of these
# TODO put response text in each of these

class UnknownTarget(Exception):
    pass

class ProjectInactive(Exception):
    pass

class AuthenticationFailure(Exception):
    pass

class Fail(Exception):

    def __init__(self, status_code: int) -> None:
        super().__init__()
        self.status_code = status_code

class MetadataTooLarge(Exception):
    pass

class TargetNameExist(Exception):
    pass

class OopsErrorOccurredResponse(Exception):
    pass

class BadImage(Exception):
    pass

class ImageTooLarge(Exception):
    pass

class RequestTimeTooSkewed(Exception):
    pass

class ContentLengthHeaderTooLarge(Exception):
    pass

class ContentLengthHeaderNotInt(Exception):
    pass

class UnnecessaryRequestBody(Exception):
    pass
