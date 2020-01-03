import base64

def decode_base64(encoded_data):
    for character in encoded_data:
        # Raise a binascii.Error if any character is not in the base64
        # alphabet.
        base64.b64decode(character * 4, validate=True)

    if len(encoded_data) % 4 == 0:
        decoded = base64.b64decode(encoded_data)
    if len(encoded_data) % 4 == 1:
        decoded = base64.b64decode(encoded_data[:-1])
    if len(encoded_data) % 4 == 2:
        decoded = base64.b64decode(encoded_data + '==')
    if len(encoded_data) % 4 == 3:
        decoded = base64.b64decode(encoded_data + '=')

    return decoded
