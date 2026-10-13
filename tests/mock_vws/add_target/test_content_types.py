"""Tests for the `Content-Type` header."""

import base64
import io
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    AuthenticationFailureError,
)

from mock_vws._constants import ResultCodes
from tests.mock_vws.add_target.helpers import (
    add_target_to_vws,
    assert_success,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
)


@pytest.mark.parametrize(
    argnames="content_type",
    argvalues=[
        # This is the documented required content type:
        "application/json",
        # Other content types also work.
        "other/content_type",
    ],
    ids=[
        "Documented Content-Type",
        "Undocumented Content-Type",
    ],
)
def test_content_types(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
    content_type: str,
) -> None:
    """Any non-empty ``Content-Type`` header is allowed."""
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )

    data = {
        "name": "example",
        "width": 1,
        "image": image_data_encoded,
    }

    response = add_target_to_vws(
        vws_client=vws_client,
        data=data,
        content_type=content_type,
    )

    assert_success(response=response)


def test_empty_content_type(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
) -> None:
    """
    An ``UNAUTHORIZED`` response is given if an empty ``Content-
    Type``
    header is given.
    """
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )

    data = {
        "name": "example",
        "width": 1,
        "image": image_data_encoded,
    }

    with pytest.raises(
        expected_exception=AuthenticationFailureError,
    ) as exc:
        _ = add_target_to_vws(
            vws_client=vws_client,
            data=data,
            content_type="",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNAUTHORIZED,
        result_code=ResultCodes.AUTHENTICATION_FAILURE,
    )
