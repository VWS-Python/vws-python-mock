"""Shared helpers for VuMark generation API tests."""

import json
from http import HTTPMethod

import requests
from beartype import beartype
from vws import VuMarkService
from vws_auth_tools import authorization_header, rfc_1123_date

type JsonValue = (
    str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

PDF_SIGNATURE = b"%PDF"

SVG_START = b"<"


@beartype
def make_vumark_service(
    *,
    base_vws_url: str,
    server_access_key: str,
    server_secret_key: str,
) -> VuMarkService:
    """Return a VuMark service client."""
    return VuMarkService(
        base_vws_url=base_vws_url,
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
    )


@beartype
def make_vumark_request(
    *,
    base_vws_url: str,
    server_access_key: str,
    server_secret_key: str,
    target_id: str,
    instance_id: JsonValue,
    accept: str,
) -> requests.Response:
    """Send a VuMark instance generation request and return the
    response.
    """
    request_path = f"/targets/{target_id}/instances"
    content_type = "application/json"
    content = json.dumps(obj={"instance_id": instance_id}).encode(
        encoding="utf-8"
    )
    date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=server_access_key,
        secret_key=server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    return requests.post(
        url=base_vws_url + request_path,
        headers={
            "Accept": accept,
            "Authorization": authorization_string,
            "Content-Length": str(object=len(content)),
            "Content-Type": content_type,
            "Date": date,
        },
        data=content,
        timeout=30,
    )
