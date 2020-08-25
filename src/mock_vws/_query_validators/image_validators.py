"""
Input validators for the image field use in the mock query API.
"""

import cgi
import io
from typing import Dict

import requests
from PIL import Image

from mock_vws._query_validators.exceptions import BadImage, ImageNotGiven


def validate_image_field_given(
    request_headers: Dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate that the image field is given.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        ImageNotGiven: The image field is not given.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = cgi.parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    if 'image' in parsed.keys():
        return

    raise ImageNotGiven


def validate_image_file_size(
    request_headers: Dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the file size of the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        requests.exceptions.ConnectionError: The image file size is too large.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = cgi.parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [image] = parsed['image']

    # This is the documented maximum size of a PNG as per.
    # https://library.vuforia.com/articles/Solution/How-To-Perform-an-Image-Recognition-Query.
    # However, the tests show that this maximum size also applies to JPEG
    # files.
    max_bytes = 2 * 1024 * 1024
    if len(image) > max_bytes:
        raise requests.exceptions.ConnectionError


def validate_image_dimensions(
    request_headers: Dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the dimensions the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImage: The image is given and is not within the maximum width and
            height limits.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = cgi.parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [image] = parsed['image']
    assert isinstance(image, bytes)
    image_file = io.BytesIO(image)
    pil_image = Image.open(image_file)
    max_width = 30000
    max_height = 30000
    if pil_image.height <= max_height and pil_image.width <= max_width:
        return

    raise BadImage


def validate_image_format(
    request_headers: Dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate the format of the image given to the query endpoint.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImage: The image is given and is not either a PNG or a JPEG.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = cgi.parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [image] = parsed['image']

    assert isinstance(image, bytes)
    image_file = io.BytesIO(image)
    pil_image = Image.open(image_file)

    if pil_image.format in ('PNG', 'JPEG'):
        return

    raise BadImage


def validate_image_is_image(
    request_headers: Dict[str, str],
    request_body: bytes,
) -> None:
    """
    Validate that the given image data is actually an image file.

    Args:
        request_headers: The headers sent with the request.
        request_body: The body of the request.

    Raises:
        BadImage: Image data is given and it is not an image file.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = cgi.parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    [image] = parsed['image']

    assert isinstance(image, bytes)
    image_file = io.BytesIO(image)

    try:
        Image.open(image_file)
    except OSError as exc:
        raise BadImage from exc
