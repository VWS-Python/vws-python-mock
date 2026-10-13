"""Tests for passing data which is not allowed to the endpoint."""

from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    FailError,
)

from mock_vws._constants import ResultCodes
from tests.mock_vws.update_target.helpers import (
    update_target,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
)


def test_invalid_extra_data(
    *,
    vws_client: VWS,
    target_id: str,
) -> None:
    """
    A `BAD_REQUEST` response is returned when unexpected data is
    given.
    """
    with pytest.raises(expected_exception=FailError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"extra_thing": 1},
            target_id=target_id,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code=ResultCodes.FAIL,
    )
