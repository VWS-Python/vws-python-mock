"""Tests for the ``include_target_data`` parameter."""

import io
import json
from http import HTTPStatus

import pytest
from vws import VWS

from mock_vws.database import CloudDatabase
from tests.mock_vws.query.helpers import (
    add_and_wait_for_targets,
    query,
)
from tests.mock_vws.utils.assertions import (
    assert_query_success,
    assert_vwq_failure,
)


def test_default(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    vuforia_database: CloudDatabase,
) -> None:
    """The default ``include_target_data`` is 'top'."""
    add_and_wait_for_targets(
        image=high_quality_image,
        vws_client=vws_client,
        num_targets=2,
    )
    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "max_num_results": (None, 2, "text/plain"),
    }

    response = query(vuforia_database=vuforia_database, body=body)

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    result_1, result_2 = response_json["results"]
    assert "target_data" in result_1
    assert "target_data" not in result_2


@pytest.mark.parametrize(
    argnames="include_target_data",
    argvalues=["top", "TOP"],
)
def test_top(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    include_target_data: str,
    vws_client: VWS,
) -> None:
    """
    When ``include_target_data`` is set to "top" (case insensitive),
    only
    the first result includes target data.
    """
    add_and_wait_for_targets(
        image=high_quality_image,
        vws_client=vws_client,
        num_targets=2,
    )
    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "include_target_data": (None, include_target_data, "text/plain"),
        "max_num_results": (None, 2, "text/plain"),
    }

    response = query(vuforia_database=vuforia_database, body=body)

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    result_1, result_2 = response_json["results"]
    assert "target_data" in result_1
    assert "target_data" not in result_2


@pytest.mark.parametrize(
    argnames="include_target_data",
    argvalues=["none", "NONE"],
)
def test_none(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    include_target_data: str,
    vws_client: VWS,
) -> None:
    """
    When ``include_target_data`` is set to "none" (case
    insensitive), no
    results include target data.
    """
    add_and_wait_for_targets(
        image=high_quality_image,
        vws_client=vws_client,
        num_targets=2,
    )
    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "include_target_data": (None, include_target_data, "text/plain"),
        "max_num_results": (None, 2, "text/plain"),
    }

    response = query(vuforia_database=vuforia_database, body=body)

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    result_1, result_2 = response_json["results"]
    assert "target_data" not in result_1
    assert "target_data" not in result_2


@pytest.mark.parametrize(
    argnames="include_target_data",
    argvalues=["all", "ALL"],
)
def test_all(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    include_target_data: str,
    vws_client: VWS,
) -> None:
    """
    When ``include_target_data`` is set to "all" (case insensitive),
    all
    results include target data.
    """
    add_and_wait_for_targets(
        image=high_quality_image,
        vws_client=vws_client,
        num_targets=2,
    )
    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "include_target_data": (None, include_target_data, "text/plain"),
        "max_num_results": (None, 2, "text/plain"),
    }

    response = query(vuforia_database=vuforia_database, body=body)

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    result_1, result_2 = response_json["results"]
    assert "target_data" in result_1
    assert "target_data" in result_2


@pytest.mark.parametrize(
    argnames="include_target_data",
    argvalues=["a", True, 0],
)
def test_invalid_value(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    include_target_data: str | bool | int,
) -> None:
    """
    A ``BAD_REQUEST`` error is given when a string that is not one
    of
    'none', 'top' or 'all' (case insensitive).
    """
    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "include_target_data": (None, include_target_data, "text/plain"),
    }
    response = query(vuforia_database=vuforia_database, body=body)

    expected_text = (
        f"Invalid value '{str(object=include_target_data).lower()}' in "
        "form data part 'include_target_data'. "
        "Expecting one of the (unquoted) string values 'all', 'none' or "
        "'top'."
    )
    assert response.text == expected_text
    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        content_type="application/json",
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )
