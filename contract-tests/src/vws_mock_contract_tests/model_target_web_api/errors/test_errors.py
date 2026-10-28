"""Additional errors tests."""

from collections.abc import Set as AbstractSet
from http import HTTPStatus

import pytest

from vws_mock_contract_tests.model_target_web_api.errors.helpers import (
    fake_response,
)
from vws_mock_contract_tests.utils.assertions import (
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


@pytest.mark.parametrize(
    argnames="base_url",
    argvalues=["http://example.com", "https://vws.vuforia.com"],
)
def test_training_allowance_exceeded(*, base_url: str) -> None:
    """An unexpected allowance response fails without a backend policy."""
    response = fake_response(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        text=(
            '{"error":{"code":"TRAINING_ALLOWANCE_EXCEEDED",'
            '"message":"Signing quota reached","target":"7635391"}}'
        ),
        url=f"{base_url}/modeltargets/datasets",
    )
    with pytest.raises(expected_exception=AssertionError) as exc:
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )

    message = str(object=exc.value)
    assert message == (
        f"Expected 201 CREATED from {base_url}/modeltargets/datasets, "
        f"got 422.\n\nResponse body:\n{response.text}"
    )
