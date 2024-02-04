"""
Utilities for tests.
"""

import io
import random
from typing import Literal

import requests
from mock_vws._constants import ResultCodes
from PIL import Image


class Endpoint:
    """
    Details of endpoints to be called in tests.
    """

    prepared_request: requests.PreparedRequest
    successful_headers_result_code: ResultCodes
    successful_headers_status_code: int
    auth_header_content_type: str
    access_key: str
    secret_key: str

    def __init__(
        self,
        prepared_request: requests.PreparedRequest,
        successful_headers_result_code: ResultCodes,
        successful_headers_status_code: int,
        access_key: str,
        secret_key: str,
    ) -> None:
        """
        Args:
            prepared_request: A request to make which would be successful.
            successful_headers_result_code: The expected result code if the
                example path is requested with the method.
            successful_headers_status_code: The expected status code if the
                example path is requested with the method.
            access_key: The access key used in the prepared request.
            secret_key: The secret key used in the prepared request.

        Attributes:
            prepared_request: A request to make which would be successful.
            successful_headers_result_code: The expected result code if the
                example path is requested with the method.
            successful_headers_status_code: The expected status code if the
                example path is requested with the method.
            auth_header_content_type: The content type to use for the
                `Authorization` header.
            access_key: The access key used in the prepared request.
            secret_key: The secret key used in the prepared request.
        """
        self.prepared_request = prepared_request
        self.successful_headers_status_code = successful_headers_status_code
        self.successful_headers_result_code = successful_headers_result_code
        headers = prepared_request.headers
        content_type = headers.get("Content-Type", "")
        content_type = content_type.split(";")[0]
        assert isinstance(content_type, str)
        self.auth_header_content_type: str = content_type
        self.access_key = access_key
        self.secret_key = secret_key


def make_image_file(
    file_format: str,
    color_space: Literal["RGB", "CMYK"],
    width: int,
    height: int,
) -> io.BytesIO:
    """
    Return an image file in the given format and color space.

    The image file is filled with randomly colored pixels.

    Args:
        file_format: See
            https://pillow.readthedocs.io/en/3.1.x/handbook/image-file-formats.html
        color_space: One of "RGB", or "CMYK".
        width: The width, in pixels of the image.
        height: The width, in pixels of the image.

    Returns:
        An image file in the given format and color space.
    """
    image_buffer = io.BytesIO()
    image = Image.new(color_space, (width, height))
    for row_index in range(height):
        for column_index in range(width):
            red = random.choice(seq=range(255))
            green = random.choice(seq=range(255))
            blue = random.choice(seq=range(255))
            image.putpixel(
                xy=(column_index, row_index),
                value=(red, green, blue),
            )

    image.save(image_buffer, file_format)
    image_buffer.seek(0)
    return image_buffer
