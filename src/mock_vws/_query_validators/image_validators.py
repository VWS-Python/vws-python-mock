"""
Input validators for the image field use in the mock query API.
"""

import cgi
import io
import uuid
from typing import Any, Callable, Dict, List, Tuple
from mock_vws.database import VuforiaDatabase

import requests
import wrapt
from PIL import Image
from requests import codes
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mock_vws._constants import ResultCodes
from .._mock_common import parse_multipart
from mock_vws._query_validators.exceptions import DateHeaderNotGiven, DateFormatNotValid, RequestTimeTooSkewed, BadImage, ImageNotGiven


@wrapt.decorator
def validate_image_field_given(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate that the image field is given.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        A ``BAD_REQUEST`` response if the image field is not given.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = parse_multipart(
        fp=body_file,
        pdict={
            'boundary': pdict['boundary'].encode(),
        },
    )

    if 'image' in parsed.keys():
        return

    raise ImageNotGiven


@wrapt.decorator
def validate_image_file_size(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the file size of the image given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.

    Raises:
        requests.exceptions.ConnectionError: The image file size is too large.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = parse_multipart(
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
    return


@wrapt.decorator
def validate_image_dimensions(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the dimensions the image given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.

    Raises:
        The result of calling the endpoint.
        An ``UNPROCESSABLE_ENTITY`` response if the image is given and is not
        within the maximum width and height limits.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = parse_multipart(
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

@wrapt.decorator
def validate_image_format(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate the format of the image given to the query endpoint.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if the image is given and is not
        either a PNG or a JPEG.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = parse_multipart(
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


@wrapt.decorator
def validate_image_is_image(
    request_path: str,
    request_headers: Dict[str, str],
    request_body: bytes,
    request_method: str,
    databases: List[VuforiaDatabase],
) -> None:
    """
    Validate that the given image data is actually an image file.

    Args:
        wrapped: An endpoint function for `requests_mock`.
        instance: The class that the endpoint function is in.
        args: The arguments given to the endpoint function.
        kwargs: The keyword arguments given to the endpoint function.

    Returns:
        The result of calling the endpoint.
        An `UNPROCESSABLE_ENTITY` response if image data is given and it is not
        an image file.
    """
    body_file = io.BytesIO(request_body)

    _, pdict = cgi.parse_header(request_headers['Content-Type'])
    parsed = parse_multipart(
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
    except OSError:
        raise BadImage
