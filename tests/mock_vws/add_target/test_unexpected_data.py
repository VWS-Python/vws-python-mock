"""
Tests for passing data which is not mandatory or allowed to the
endpoint.
"""

import base64
import io
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    FailError,
)

from mock_vws._constants import ResultCodes
from tests.mock_vws.add_target.helpers import (
    add_target_to_vws,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
)


def test_invalid_extra_data(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
) -> None:
    """
    A `BAD_REQUEST` response is returned when unexpected data is
    given.
    """
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )

    data = {
        "name": "example_name",
        "width": 1,
        "image": image_data_encoded,
        "extra_thing": 1,
    }

    with pytest.raises(expected_exception=FailError) as exc:
        _ = add_target_to_vws(
            vws_client=vws_client,
            data=data,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code=ResultCodes.FAIL,
    )
