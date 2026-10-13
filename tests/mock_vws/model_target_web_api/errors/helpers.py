"""Shared helpers for errors tests."""

from http import HTTPStatus

from beartype import beartype
from vws.response import Response

from tests.mock_vws.model_target_web_api.sample_data import (
    MODEL,
)

MODEL_WITHOUT_CAD_DATA: dict[str, object] = {
    key: value for key, value in MODEL.items() if key != "cadDataUrl"
}

EMPTY_MODEL: dict[str, object] = {}

EMPTY_VIEW: dict[str, object] = {}

EMPTY_GUIDE_VIEW_POSITION: list[object] = []

EMPTY_GUIDE_VIEW_POSITION_OBJECT: dict[str, object] = {}


@beartype
def fake_response(
    *,
    status_code: HTTPStatus,
    text: str,
    url: str,
) -> Response:
    """Return a response for testing the status assertion helper."""
    return Response(
        text=text,
        url=url,
        status_code=status_code,
        headers={},
        request_body=None,
        tell_position=len(text),
        content=text.encode(encoding="utf-8"),
    )
