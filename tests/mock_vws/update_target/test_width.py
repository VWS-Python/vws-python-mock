"""Tests for the target width field."""

from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    FailError,
)

from tests.mock_vws.update_target.helpers import (
    update_target,
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
    width: int | str | None,
    target_id: str,
) -> None:
    """The width must be a number greater than zero."""
    target_details = vws_client.get_target_record(target_id=target_id)
    original_width = target_details.target_record.width

    with pytest.raises(expected_exception=FailError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"width": width},
            target_id=target_id,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )

    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.target_record.width == original_width


def test_width_valid(*, vws_client: VWS, target_id: str) -> None:
    """Positive numbers are valid widths."""
    width = 0.01
    vws_client.update_target(target_id=target_id, width=width)
    target_details = vws_client.get_target_record(target_id=target_id)
    assert target_details.target_record.width == width
