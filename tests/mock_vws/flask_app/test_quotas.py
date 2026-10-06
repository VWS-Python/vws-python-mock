"""Tests for quotas through the Flask app."""

import io

import pytest
import requests
from vws import VWS
from vws.exceptions.vws_exceptions import (
    RequestQuotaReachedError,
    TargetQuotaReachedError,
    TooManyRequestsError,
)

from mock_vws.database import CloudDatabase
from mock_vws.request_rate_limits import RequestRateLimit, RequestRateLimits


def test_request_quota_reached(target_manager_url: str) -> None:
    """The Flask mock preserves and enforces a zero request quota."""
    database = CloudDatabase(request_quota=0)
    databases_url = target_manager_url + "/cloud_databases"
    response = requests.post(
        url=databases_url,
        json=database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with pytest.raises(expected_exception=RequestQuotaReachedError):
        _ = client.list_targets()


def test_target_quota_reached(
    *, image_file_failed_state: io.BytesIO, target_manager_url: str
) -> None:
    """The Flask mock preserves and enforces a zero target quota."""
    database = CloudDatabase(target_quota=0)
    databases_url = target_manager_url + "/cloud_databases"
    response = requests.post(
        url=databases_url,
        json=database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with pytest.raises(expected_exception=TargetQuotaReachedError):
        _ = client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            application_metadata=None,
            active_flag=True,
        )


def test_too_many_requests(target_manager_url: str) -> None:
    """The Flask mock preserves and enforces a zero request rate limit."""
    database = CloudDatabase(requests_per_second_limit=0)
    databases_url = target_manager_url + "/cloud_databases"
    response = requests.post(
        url=databases_url,
        json=database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with pytest.raises(expected_exception=TooManyRequestsError):
        _ = client.list_targets()


def test_per_endpoint_limits(target_manager_url: str) -> None:
    """The Flask mock preserves and enforces per-endpoint limits."""
    database = CloudDatabase(
        request_rate_limits=RequestRateLimits(
            list_targets=RequestRateLimit(
                max_requests=1,
                window_seconds=60.0,
            ),
        ),
    )
    databases_url = target_manager_url + "/cloud_databases"
    response = requests.post(
        url=databases_url,
        json=database.to_dict(),
        timeout=30,
    )
    response.raise_for_status()
    client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    _targets = client.list_targets()
    with pytest.raises(expected_exception=TooManyRequestsError):
        _targets = client.list_targets()

    # Other endpoints are not limited.
    _summary = client.get_database_summary_report()
