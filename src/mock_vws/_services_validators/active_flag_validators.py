"""
Validators for the active flag.
"""

import json

from requests import codes

from mock_vws._services_validators.exceptions import Fail


def validate_active_flag(request_text: str) -> None:
    """
    Validate the active flag data given to the endpoint.

    Args:
        request_text: The content of the request.

    Raises:
        Fail: There is active flag data given to the endpoint which is not
            either a Boolean or NULL.
    """

    if not request_text:
        return

    if 'active_flag' not in json.loads(request_text):
        return

    active_flag = json.loads(request_text).get('active_flag')

    if active_flag is None or isinstance(active_flag, bool):
        return

    raise Fail(status_code=codes.BAD_REQUEST)
