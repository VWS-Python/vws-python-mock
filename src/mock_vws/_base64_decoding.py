"""
Helpers for handling Base64 like Vuforia does.
"""

import base64
import binascii
import string


def decode_base64(encoded_data: str) -> bytes:
    """
    Decode base64 somewhat like Vuforia does.

    Raises:
        binascii.Error: Vuforia would consider this encoded data as an
        "UNPROCESSABLE_ENTITY".

    Returns:
        The given data, decoded as base64.
    """
    acceptable_characters = string.ascii_letters + string.digits + '+/='
    for character in encoded_data:
        if character not in acceptable_characters:
            raise binascii.Error()

    if len(encoded_data) % 4 == 0:
        decoded = base64.b64decode(encoded_data)
    elif len(encoded_data) % 4 == 1:
        decoded = base64.b64decode(encoded_data[:-1])
    elif len(encoded_data) % 4 == 2:
        decoded = base64.b64decode(encoded_data + '==')
    else:
        assert len(encoded_data) % 4 == 3
        decoded = base64.b64decode(encoded_data + '=')

    return decoded
