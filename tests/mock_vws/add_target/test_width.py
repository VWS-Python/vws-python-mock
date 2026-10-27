"""Tests for the target width field."""

import base64
import io
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    FailError,
)

from tests.mock_vws.add_target.helpers import (
    add_target_to_vws,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
)


@pytest.mark.parametrize(
    argnames="width",
    argvalues=[-1, "10", None, 0],
    ids=["Negative", "Wrong Type", "None", "Zero"],
)
def test_width_invalid(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
    width: int | str | None,
) -> None:
    """The width must be a number greater than zero."""
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )

    data = {
        "name": "example_name",
        "width": width,
        "image": image_data_encoded,
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
        result_code="Fail",
    )


def test_width_valid(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
) -> None:
    """Positive numbers are valid widths."""
    _ = vws_client.add_target(
        name="example",
        width=0.01,
        image=image_file_failed_state,
        application_metadata=None,
        active_flag=True,
    )
