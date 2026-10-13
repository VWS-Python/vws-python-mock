"""Additional errors tests."""

from collections.abc import Set as AbstractSet
from http import HTTPStatus

import pytest

from tests.mock_vws.model_target_web_api.errors.helpers import (
    fake_response,
)
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
)


@pytest.mark.parametrize(
    argnames="status_codes",
    argvalues=[
        pytest.param(HTTPStatus.OK, id="single"),
        pytest.param(
            {HTTPStatus.OK, HTTPStatus.NO_CONTENT},
            id="set",
        ),
    ],
)
def test_expected_status(
    *,
    base_vws_url: str,
    status_codes: HTTPStatus | AbstractSet[HTTPStatus],
) -> None:
    """An expected status code does not raise."""
    response = fake_response(
        status_code=HTTPStatus.OK,
        text="{}",
        url=f"{base_vws_url}/modeltargets/advancedDatasets",
    )
    assert_model_target_status(
        response=response,
        status_codes=status_codes,
    )


def test_unexpected_status_shows_the_body(*, base_vws_url: str) -> None:
    """An unexpected status code reports the URL and the body."""
    text = '{"error":{"code":"VALIDATION_ERROR"}}'
    response = fake_response(
        status_code=HTTPStatus.BAD_REQUEST,
        text=text,
        url=f"{base_vws_url}/modeltargets/advancedDatasets",
    )
    with pytest.raises(expected_exception=AssertionError) as exc:
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )

    message = str(object=exc.value)
    assert message == (
        "Expected 201 CREATED from "
        f"{base_vws_url}/modeltargets/advancedDatasets, got 400.\n"
        f"\nResponse body:\n{text}"
    )


def test_multiple_expected_statuses(*, base_vws_url: str) -> None:
    """Every expected status code is named in the message."""
    response = fake_response(
        status_code=HTTPStatus.BAD_REQUEST,
        text="{}",
        url=f"{base_vws_url}/modeltargets/advancedDatasets",
    )
    with pytest.raises(expected_exception=AssertionError) as exc:
        assert_model_target_status(
            response=response,
            status_codes={HTTPStatus.OK, HTTPStatus.NO_CONTENT},
        )

    assert "Expected 200 OK or 204 NO_CONTENT from " in str(object=exc.value)


def test_training_allowance_exceeded() -> None:
    """An exhausted account allowance is an expected failure, called
    out as such in the first line so that a truncated CI summary
    still shows it.
    """
    response = fake_response(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        text=(
            '{"error":{"code":"TRAINING_ALLOWANCE_EXCEEDED",'
            '"message":"Signing quota reached","target":"7635391"}}'
        ),
        url="http://example.com/modeltargets/datasets",
    )
    with pytest.raises(expected_exception=pytest.xfail.Exception) as exc:
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )

    message = str(object=exc.value)
    first_line = message.splitlines()[0]
    assert first_line == (
        "The Vuforia account is out of Model Target training allowance - "
        "this is not a failure of the code under test."
    )
    assert "MODEL_TARGET_VUFORIA_CLIENT_ID" in message
    assert "has to be raised, or reset, on the Vuforia account" in message
    assert "expected failure" in message
