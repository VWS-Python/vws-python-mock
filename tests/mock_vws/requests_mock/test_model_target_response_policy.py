"""Tests for backend handling of unexpected Model Target responses."""

from collections.abc import Generator
from http import HTTPStatus

import pytest
import requests
from vws.response import Response

from vws_mock_contract_tests.model_target_web_api.errors.helpers import (
    fake_response,
)
from vws_mock_contract_tests.utils.assertions import assert_model_target_status
from vws_mock_contract_tests.utils.model_target_response_policy import (
    handling_unexpected_model_target_responses,
)
from vws_mock_test_backends.vuforia_backends import VuforiaBackend

_ALLOWANCE_BODY = '{"error":{"code":"TRAINING_ALLOWANCE_EXCEEDED"}}'


@pytest.fixture(name="_model_target_backend")
def fixture_model_target_backend() -> VuforiaBackend:
    """Select the real policy without credentials or service requests."""
    return VuforiaBackend.REAL


@pytest.fixture(
    name="base_vws_url",
    params=["https://vws.vuforia.com", "http://consumer.example"],
)
def fixture_base_vws_url(*, request: pytest.FixtureRequest) -> str:
    """Supply a URL for the adapter and its synthetic responses."""
    url = request.param
    assert isinstance(url, str)
    return url


@pytest.fixture(autouse=True)
def fixture_check_response_policy_cleanup() -> Generator[None]:
    """Check the default before setup and after backend fixtures finish.

    Yields:
        ``None``, while the test and its backend fixtures run.
    """
    response = fake_response(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        text=_ALLOWANCE_BODY,
        url="https://vws.vuforia.com/modeltargets/datasets",
    )
    with pytest.raises(expected_exception=AssertionError):
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )
    yield
    with pytest.raises(expected_exception=AssertionError):
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
def test_real_adapter_handles_allowance(*, base_vws_url: str) -> None:
    """The real adapter handles allowance rejections at its supplied
    URL.
    """
    response = fake_response(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        text=_ALLOWANCE_BODY,
        url=f"{base_vws_url}/modeltargets/datasets",
    )
    with pytest.raises(
        expected_exception=pytest.skip.Exception,
        match="out of Model Target training allowance",
    ):
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
def test_expected_allowance_status(*, base_vws_url: str) -> None:
    """An expected allowance response remains an ordinary assertion."""
    response = fake_response(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        text=_ALLOWANCE_BODY,
        url=f"{base_vws_url}/modeltargets/datasets",
    )
    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.UNPROCESSABLE_ENTITY,
    )


@pytest.mark.usefixtures("verify_model_target_mock_vuforia")
def test_other_unexpected_status(*, base_vws_url: str) -> None:
    """The real adapter does not hide unrelated response failures."""
    response = fake_response(
        status_code=HTTPStatus.BAD_REQUEST,
        text='{"error":{"code":"VALIDATION_ERROR"}}',
        url=f"{base_vws_url}/modeltargets/datasets",
    )
    with pytest.raises(
        expected_exception=AssertionError,
        match="VALIDATION_ERROR",
    ):
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )


def test_nested_response_handlers() -> None:
    """Nested handlers restore the outer handler and finally the
    default.
    """
    calls: list[str] = []
    response = fake_response(
        status_code=HTTPStatus.BAD_REQUEST,
        text="{}",
        url="http://consumer.example/modeltargets/datasets",
    )

    def outer_handler(*, response: Response | requests.Response) -> None:
        """Record a response handled by the outer context."""
        assert response.status_code == HTTPStatus.BAD_REQUEST
        calls.append("outer")

    def inner_handler(*, response: Response | requests.Response) -> None:
        """Record a response handled by the inner context."""
        assert response.status_code == HTTPStatus.BAD_REQUEST
        calls.append("inner")

    with handling_unexpected_model_target_responses(handler=outer_handler):
        with pytest.raises(expected_exception=AssertionError):
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.CREATED,
            )
        with (
            handling_unexpected_model_target_responses(handler=inner_handler),
            pytest.raises(expected_exception=AssertionError),
        ):
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.CREATED,
            )
        with pytest.raises(expected_exception=AssertionError):
            assert_model_target_status(
                response=response,
                status_codes=HTTPStatus.CREATED,
            )

    with pytest.raises(expected_exception=AssertionError):
        assert_model_target_status(
            response=response,
            status_codes=HTTPStatus.CREATED,
        )
    assert calls == ["outer", "inner", "outer"]
