"""Tests for the ``request_usage`` field."""

import io
from http import HTTPStatus

import pytest
from vws import VWS, CloudRecoService
from vws.exceptions.vws_exceptions import FailError


def test_target_request(vws_client: VWS) -> None:
    """
    The ``request_usage`` count does not increase with each request
    to the
    target API.
    """
    report = vws_client.get_database_summary_report()
    original_request_usage = report.request_usage

    report = vws_client.get_database_summary_report()
    new_request_usage = report.request_usage
    assert new_request_usage == original_request_usage


def test_bad_target_request(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """
    The ``request_usage`` count does not increase with each request
    to the
    target API, even if it is a bad request.
    """
    report = vws_client.get_database_summary_report()
    original_request_usage = report.request_usage

    with pytest.raises(expected_exception=FailError) as exc:
        _ = vws_client.add_target(
            name="example",
            width=-1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )

    assert exc.value.response.status_code == HTTPStatus.BAD_REQUEST

    report = vws_client.get_database_summary_report()
    new_request_usage = report.request_usage
    assert new_request_usage == original_request_usage


def test_query_request(
    *,
    cloud_reco_client: CloudRecoService,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> None:
    """
    The ``request_usage`` count does not increase with each
    query.
    """
    report = vws_client.get_database_summary_report()
    original_request_usage = report.request_usage
    _ = cloud_reco_client.query(image=high_quality_image)
    report = vws_client.get_database_summary_report()
    new_request_usage = report.request_usage
    # The request usage goes up for the database summary request, not the
    # query.
    assert new_request_usage == original_request_usage
