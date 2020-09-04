"""
Utilities for tests.
"""

import io
import json
import random
from typing import Any, Dict
from urllib.parse import urljoin

import requests
from PIL import Image
from requests import Response
from requests_mock import POST, PUT
from urllib3.filepost import encode_multipart_formdata
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws._constants import ResultCodes
from mock_vws.database import VuforiaDatabase


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
        content_type = headers.get('Content-Type', '')
        content_type = content_type.split(';')[0]
        assert isinstance(content_type, str)
        self.auth_header_content_type: str = content_type
        self.access_key = access_key
        self.secret_key = secret_key


class UnexpectedEmptyInternalServerError(Exception):  # pragma: no cover
    """
    Sometimes Vuforia gives an empty internal server error response.

    We want to retry tests in these cases so we raise this exception in order
    to do so.
    """


def update_target(
    vuforia_database: VuforiaDatabase,
    data: Dict[str, Any],
    target_id: str,
    content_type: str = 'application/json',
) -> Response:
    """
    Make a request to the endpoint to update a target.

    Args:
        vuforia_database: The credentials to use to connect to
            Vuforia.
        data: The data to send, in JSON format, to the endpoint.
        target_id: The ID of the target to update.
        content_type: The `Content-Type` header to use.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = '/targets/' + target_id

    content = bytes(json.dumps(data), encoding='utf-8')

    authorization_string = authorization_header(
        access_key=vuforia_database.server_access_key,
        secret_key=vuforia_database.server_secret_key,
        method=PUT,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    headers = {
        'Authorization': authorization_string,
        'Date': date,
        'Content-Type': content_type,
    }

    response = requests.request(
        method=PUT,
        url=urljoin('https://vws.vuforia.com/', request_path),
        headers=headers,
        data=content,
    )

    return response


def query(
    vuforia_database: VuforiaDatabase,
    body: Dict[str, Any],
) -> Response:
    """
    Make a request to the endpoint to make an image recognition query.

    Args:
        vuforia_database: The credentials to use to connect to
            Vuforia.
        body: The request body to send in ``multipart/formdata`` format.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = '/v1/query'
    content, content_type_header = encode_multipart_formdata(body)
    method = POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        # Note that this is not the actual Content-Type header value sent.
        content_type='multipart/form-data',
        date=date,
        request_path=request_path,
    )

    headers = {
        'Authorization': authorization_string,
        'Date': date,
        'Content-Type': content_type_header,
    }

    vwq_host = 'https://cloudreco.vuforia.com'
    response = requests.request(
        method=method,
        url=urljoin(base=vwq_host, url=request_path),
        headers=headers,
        data=content,
    )

    return response


def make_image_file(
    file_format: str,
    color_space: str,
    width: int,
    height: int,
) -> io.BytesIO:
    """
    Return an image file in the given format and color space.

    The image file is filled with randomly colored pixels.

    Args:
        file_format: See
            https://pillow.readthedocs.io/en/3.1.x/handbook/image-file-formats.html
        color_space: One of "L", "RGB", or "CMYK". "L" means greyscale.
        width: The width, in pixels of the image.
        height: The width, in pixels of the image.

    Returns:
        An image file in the given format and color space.
    """
    image_buffer = io.BytesIO()
    image = Image.new(color_space, (width, height))
    # If this assertion ever fails, see
    # https://github.com/VWS-Python/vws-test-fixtures for what to do.
    assert color_space != 'L'
    reds = random.choices(population=range(0, 255), k=width * height)
    greens = random.choices(population=range(0, 255), k=width * height)
    blues = random.choices(population=range(0, 255), k=width * height)
    pixels = list(zip(reds, greens, blues))
    image.putdata(pixels)
    image.save(image_buffer, file_format)
    image_buffer.seek(0)
    return image_buffer
