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
