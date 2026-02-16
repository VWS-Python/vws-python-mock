"""Tests for the VuMark generation web API."""

import json
from http import HTTPMethod, HTTPStatus
from pathlib import Path

import pytest
import requests
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from vws_auth_tools import authorization_header, rfc_1123_date

from mock_vws.database import VuforiaDatabase

_VWS_HOST = "https://vws.vuforia.com"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class _VuMarkGenerationSettings(BaseSettings):
    """Settings needed for VuMark instance generation tests."""

    target_id: str
    instance_id: str

    model_config = SettingsConfigDict(
        env_prefix="VUMARK_VUFORIA_",
        env_file=Path("vuforia_secrets.env"),
        extra="allow",
    )


def _get_vumark_generation_settings() -> _VuMarkGenerationSettings:
    """Return generation settings, skipping if they are not configured."""
    try:
        settings = _VuMarkGenerationSettings.model_validate(obj={})
    except ValidationError:
        pytest.skip(
            reason=(
                "VuMark generation settings are not configured. "
                "Set VUMARK_VUFORIA_TARGET_ID and "
                "VUMARK_VUFORIA_INSTANCE_ID."
            ),
        )

    if settings.target_id.startswith("<") or settings.instance_id.startswith(
        "<"
    ):
        pytest.skip(
            reason=(
                "VuMark generation settings are placeholders. "
                "Set VUMARK_VUFORIA_TARGET_ID and "
                "VUMARK_VUFORIA_INSTANCE_ID."
            ),
        )

    return settings


def test_generate_instance_success(
    vumark_vuforia_database: VuforiaDatabase,
) -> None:
    """A VuMark instance can be generated with valid template settings."""
    settings = _get_vumark_generation_settings()
    request_path = f"/targets/{settings.target_id}/instances"
    content_type = "application/json"
    content = json.dumps(obj={"instance_id": settings.instance_id}).encode(
        encoding="utf-8"
    )
    date = rfc_1123_date()
    authorization_string = authorization_header(
        access_key=vumark_vuforia_database.server_access_key,
        secret_key=vumark_vuforia_database.server_secret_key,
        method=HTTPMethod.POST,
        content=content,
        content_type=content_type,
        date=date,
        request_path=request_path,
    )

    response = requests.post(
        url=_VWS_HOST + request_path,
        headers={
            "Accept": "image/png",
            "Authorization": authorization_string,
            "Content-Length": str(object=len(content)),
            "Content-Type": content_type,
            "Date": date,
        },
        data=content,
        timeout=30,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.headers["Content-Type"].split(sep=";")[0] == "image/png"
    assert response.content.startswith(_PNG_SIGNATURE)
    assert len(response.content) > len(_PNG_SIGNATURE)
