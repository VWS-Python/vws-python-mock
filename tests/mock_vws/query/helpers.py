"""Shared helpers for query tests."""

import io
import re
import textwrap
import uuid
from collections.abc import Mapping
from http import HTTPMethod
from urllib.parse import urljoin

import requests
from pydantic import TypeAdapter
from urllib3.fields import RequestField
from urllib3.filepost import encode_multipart_formdata
from vws import VWS
from vws.response import Response
from vws_auth_tools import authorization_header, rfc_1123_date

from tests.mock_vws.fixtures.credentials import CloudDatabaseCredentials
from tests.mock_vws.utils.too_many_requests import handle_server_errors

JETTY_CONTENT_TYPE_ERROR = textwrap.dedent(
    text="""\
    <html>
    <head>
    <meta http-equiv="Content-Type" content="text/html;charset=ISO-8859-1"/>
    <title>Error 400 Bad Request</title>
    </head>
    <body>
    <h2>HTTP ERROR 400 Bad Request</h2>
    <table>
    <tr><th>URI:</th><td>http://cloudreco.vuforia.com/v1/query</td></tr>
    <tr><th>STATUS:</th><td>400</td></tr>
    <tr><th>MESSAGE:</th><td>Bad Request</td></tr>
    </table>
    <hr/><a href="https://jetty.org/">Powered by Jetty:// 12.0.20</a><hr/>

    </body>
    </html>
    """,
)

JETTY_VERSION_RE = re.compile(pattern=r"Powered by Jetty:// [\d.]+")

NGINX_REQUEST_ENTITY_TOO_LARGE_ERROR = textwrap.dedent(
    text="""\
    <html>\r
    <head><title>413 Request Entity Too Large</title></head>\r
    <body>\r
    <center><h1>413 Request Entity Too Large</h1></center>\r
    <hr><center>nginx</center>\r
    </body>\r
    </html>\r
    """,
)


def query_raw(
    *,
    vuforia_database: CloudDatabaseCredentials,
    content: bytes,
    content_type_header: str,
    base_vwq_url: str,
) -> Response:
    """Make a request to the endpoint to make an image recognition query,
    with a body which is sent exactly as given.

    Args:
        vuforia_database: The credentials to use to connect to
            Vuforia.
        content: The request body to send.
        base_vwq_url: The base URL of the query API for the backend.
        content_type_header: The ``Content-Type`` header to send.

    Returns:
        The response returned by the API.
    """
    date = rfc_1123_date()
    request_path = "/v1/query"
    method = HTTPMethod.POST

    access_key = vuforia_database.client_access_key
    secret_key = vuforia_database.client_secret_key
    authorization_string = authorization_header(
        access_key=access_key,
        secret_key=secret_key,
        method=method,
        content=content,
        # Note that this is not the actual Content-Type header value sent.
        content_type="multipart/form-data",
        date=date,
        request_path=request_path,
    )

    headers = {
        "Authorization": authorization_string,
        "Date": date,
        "Content-Type": content_type_header,
    }

    requests_response = requests.request(
        method=method,
        url=urljoin(base=base_vwq_url, url=request_path),
        headers=headers,
        data=content,
        timeout=30,
    )

    vws_response = Response(
        text=requests_response.text,
        url=requests_response.url,
        status_code=requests_response.status_code,
        headers=dict(requests_response.headers),
        request_body=requests_response.request.body,
        tell_position=requests_response.raw.tell(),
        content=requests_response.content,
    )
    handle_server_errors(response=vws_response)
    return vws_response


def query(
    *,
    vuforia_database: CloudDatabaseCredentials,
    body: Mapping[
        str,
        tuple[str | None, object, str],
    ],
    base_vwq_url: str,
) -> Response:
    """Make a request to the endpoint to make an image recognition query.

    Args:
        vuforia_database: The credentials to use to connect to
            Vuforia.
        body: The request body to send in ``multipart/formdata`` format.
        base_vwq_url: The base URL of the query API for the backend.

    Returns:
        The response returned by the API.
    """
    value_adapter: TypeAdapter[str | bytes | int | bool] = TypeAdapter(
        type=str | bytes | int | bool
    )
    fields: list[RequestField] = []
    for name, (filename, value, content_type) in body.items():
        validated_value = value_adapter.validate_python(value, strict=True)
        encoded_value = (
            str(object=validated_value)
            if isinstance(validated_value, int)
            else validated_value
        )
        field = RequestField(
            name=name,
            data=encoded_value,
            filename=filename,
        )
        field.make_multipart(
            content_disposition="form-data",
            content_type=content_type,
        )
        fields.append(field)

    content, content_type_header = encode_multipart_formdata(fields=fields)
    return query_raw(
        vuforia_database=vuforia_database,
        content=content,
        content_type_header=content_type_header,
        base_vwq_url=base_vwq_url,
    )


def add_and_wait_for_targets(
    *,
    image: io.BytesIO,
    vws_client: VWS,
    num_targets: int,
) -> None:
    """Add targets with the given image."""
    target_ids: set[str] = set()
    for _ in range(num_targets):
        target_id = vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=image,
            active_flag=True,
            application_metadata=None,
        )
        target_ids.add(target_id)

    for created_target_id in target_ids:
        vws_client.wait_for_target_processed(target_id=created_target_id)
