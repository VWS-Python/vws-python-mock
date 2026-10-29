"""Tests for `VWS` through the `httpx2` mock."""

from http import HTTPStatus

import httpx2
import pytest

from mock_vws import MockVWS


def test_nested_mocks() -> None:
    """A mock inside another mock leaves the outer one working.

    The innermost mock is the only one which answers while it is
    running, which is what the ``requests`` backend does too, and the
    outer mock answers again once the inner one has stopped.
    """
    outer_url = "https://vws.vuforia.com/targets/template/instances"
    inner_url = "https://vuforia.vws.example.com/targets/template/instances"

    with MockVWS():
        with MockVWS(base_vws_url="https://vuforia.vws.example.com"):
            inner_response = httpx2.post(url=inner_url, timeout=30)
            with pytest.raises(expected_exception=httpx2.ConnectError):
                _ = httpx2.post(url=outer_url, timeout=30)
        outer_response = httpx2.post(url=outer_url, timeout=30)

        with pytest.raises(expected_exception=httpx2.ConnectError):
            _ = httpx2.post(url=inner_url, timeout=30)

    assert inner_response.status_code == HTTPStatus.UNAUTHORIZED
    assert outer_response.status_code == HTTPStatus.UNAUTHORIZED
