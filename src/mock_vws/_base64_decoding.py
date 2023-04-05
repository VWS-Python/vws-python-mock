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
    acceptable_characters = string.ascii_letters + string.digits + "+/="
    for character in encoded_data:
        if character not in acceptable_characters:
            raise binascii.Error

    mod_four_result_to_modified_encoded_data = {
        0: encoded_data,
        1: encoded_data[:-1],
        2: f"{encoded_data}==",
        3: f"{encoded_data}=",
    }
    modified_encoded_data = mod_four_result_to_modified_encoded_data[
        len(encoded_data) % 4
    ]
    return base64.b64decode(modified_encoded_data)
