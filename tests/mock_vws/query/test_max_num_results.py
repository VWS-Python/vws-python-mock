"""Tests for the ``max_num_results`` parameter."""

import io
import json
import uuid
from http import HTTPStatus

import pytest
from pydantic import TypeAdapter
from vws import VWS, CloudRecoService
from vws.exceptions.cloud_reco_exceptions import (
    MaxNumResultsOutOfRangeError,
)

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
    vuforia_database: CloudDatabase,
    vws_client: VWS,
    base_vwq_url: str,
) -> None:
    """The default ``max_num_results`` is 1."""
    image_content = high_quality_image.getvalue()

    target_id_1 = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    target_id_2 = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=target_id_1)
    vws_client.wait_for_target_processed(target_id=target_id_2)

    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
    }

    response = query(
        vuforia_database=vuforia_database, body=body, base_vwq_url=base_vwq_url
    )

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    results_value: object = response_json["results"]
    results = TypeAdapter(type=list[object]).validate_python(
        results_value,
    )
    assert len(results) == 1


@pytest.mark.parametrize(argnames="num_results", argvalues=[1, b"1", 50])
def test_valid_accepted(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    num_results: int | bytes,
    base_vwq_url: str,
) -> None:
    """Numbers between 1 and 50 are valid inputs.

    We assert that the response is a success, but not that the
    maximum number of results is enforced.

    This is because uploading 50 images would be very slow.

    The documentation at
    https://developer.vuforia.com/library/web-api/vuforia-query-web-api
    states that this must be between 1 and 10, but in practice, 50 is the
    maximum.
    """
    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "max_num_results": (None, num_results, "text/plain"),
    }

    response = query(
        vuforia_database=vuforia_database, body=body, base_vwq_url=base_vwq_url
    )

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    assert response_json["results"] == []


def test_valid_works(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
) -> None:
    """A maximum of ``max_num_results`` results are returned."""
    add_and_wait_for_targets(
        image=high_quality_image,
        vws_client=vws_client,
        num_targets=3,
    )

    max_num_results = 2

    result = cloud_reco_client.query(
        image=high_quality_image,
        max_num_results=max_num_results,
    )
    assert len(result) == max_num_results


@pytest.mark.parametrize(argnames="num_results", argvalues=[-1, 0, 51])
def test_out_of_range(
    *,
    high_quality_image: io.BytesIO,
    num_results: int,
    cloud_reco_client: CloudRecoService,
) -> None:
    """An error is returned if ``max_num_results`` is given as an
    integer
    out of the range (1, 50).

    The documentation at
    https://developer.vuforia.com/library/web-api/vuforia-query-web-api.
    states that this must be between 1 and 10, but in practice, 50 is the
    maximum.
    """
    with pytest.raises(
        expected_exception=MaxNumResultsOutOfRangeError,
    ) as exc_info:
        _ = cloud_reco_client.query(
            image=high_quality_image,
            max_num_results=num_results,
        )

    expected_text = (
        f"Integer out of range ({num_results}) in form data part "
        "'max_result'. Accepted range is from 1 to 50 (inclusive)."
    )
    assert exc_info.value.response.text == expected_text
    assert_vwq_failure(
        response=exc_info.value.response,
        content_type="application/json",
        status_code=HTTPStatus.BAD_REQUEST,
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )


@pytest.mark.parametrize(
    argnames="num_results",
    argvalues=[b"0.1", b"1.1", b"a", b"2147483648"],
)
def test_invalid_type(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabase,
    num_results: bytes,
    base_vwq_url: str,
) -> None:
    """An error is returned if ``max_num_results`` is given as
    something
    other than an integer.

    Integers greater than 2147483647 are not considered integers
    because they are bigger than Java's maximum integer.
    """
    image_content = high_quality_image.getvalue()
    body = {
        "image": ("image.jpeg", image_content, "image/jpeg"),
        "max_num_results": (None, num_results, "text/plain"),
    }
    response = query(
        vuforia_database=vuforia_database, body=body, base_vwq_url=base_vwq_url
    )

    expected_text = (
        f"Invalid value '{num_results.decode()}' in form data part "
        "'max_result'. "
        "Expecting integer value in range from 1 to 50 (inclusive)."
    )
    assert response.text == expected_text
    assert_vwq_failure(
        response=response,
        content_type="application/json",
        status_code=HTTPStatus.BAD_REQUEST,
        cache_control=None,
        www_authenticate=None,
        connection="keep-alive",
    )
