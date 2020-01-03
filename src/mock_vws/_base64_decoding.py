import base64
import binascii
import string

def decode_base64(encoded_data):
    acceptable_characters = string.ascii_letters + string.digits + '+/='
    for character in encoded_data:
        if character not in acceptable_characters:
            raise binascii.Error()

    if len(encoded_data) % 4 == 0:
        decoded = base64.b64decode(encoded_data)
    if len(encoded_data) % 4 == 1:
        decoded = base64.b64decode(encoded_data[:-1])
    if len(encoded_data) % 4 == 2:
        decoded = base64.b64decode(encoded_data + '==')
    if len(encoded_data) % 4 == 3:
        decoded = base64.b64decode(encoded_data + '=')

    return decoded
