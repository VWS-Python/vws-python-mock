"""Utilities for tests."""

import io
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin

import requests
from PIL import Image
from requests.structures import CaseInsensitiveDict
from vws.response import Response

from mock_vws._constants import ResultCodes


@dataclass(frozen=True)
class Endpoint:
    """Details of endpoints to be called in tests.

    Args:
        prepared_request: A request to make which would be successful.
        successful_headers_result_code: The expected result code if the
            example path is requested with the method.
        successful_headers_status_code: The expected status code if the
            example path is requested with the method.
        access_key: The access key used in the prepared request.
        secret_key: The secret key used in the prepared request.
        path_url: The path of the endpoint.
        base_url: The base URL of the endpoint.

    Attributes:
        prepared_request: A request to make which would be successful.
        successful_headers_result_code: The expected result code if the
            example path is requested with the method.
        successful_headers_status_code: The expected status code if the
            example path is requested with the method.
        access_key: The access key used in the prepared request.
        secret_key: The secret key used in the prepared request.
        path_url: The path of the endpoint.
        base_url: The base URL of the endpoint.
    """

    base_url: str
    path_url: str
    method: str
    headers: Mapping[str, str]
    data: bytes | str
    successful_headers_result_code: ResultCodes | None
    successful_headers_status_code: int
    access_key: str
    secret_key: str

    def send(self) -> Response:
        """Send the request."""
        request = requests.Request(
            method=self.method,
            url=urljoin(base=self.base_url, url=self.path_url),
            headers=self.headers,
            data=self.data,
        )
        prepared_request = request.prepare()
        prepared_request.headers = CaseInsensitiveDict(data=self.headers)
        session = requests.Session()
        requests_response = session.send(request=prepared_request)
        return Response(
            text=requests_response.text,
            url=requests_response.url,
            status_code=requests_response.status_code,
            headers=dict(requests_response.headers),
            request_body=requests_response.request.body,
            tell_position=requests_response.raw.tell(),
            content=requests_response.content,
        )

    @property
    def auth_header_content_type(self) -> str:
        """The content type to use for the `Authorization` header."""
        full_content_type = dict(self.headers).get("Content-Type", "")
        return full_content_type.split(sep=";")[0]


def make_image_file(
    file_format: str,
    color_space: Literal["RGB", "CMYK"],
    width: int,
    height: int,
) -> io.BytesIO:
    """Return an image file in the given format and color space.

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
    image = Image.new(mode=color_space, size=(width, height))
    for row_index in range(height):
        for column_index in range(width):
            red = secrets.choice(seq=range(255))
            green = secrets.choice(seq=range(255))
            blue = secrets.choice(seq=range(255))
            image.putpixel(
                xy=(column_index, row_index),
                value=(red, green, blue),
            )

    image.save(fp=image_buffer, format=file_format)
    image_buffer.seek(0)
    return image_buffer
