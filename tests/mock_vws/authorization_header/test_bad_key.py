"""Tests for making requests with incorrect keys."""

import io
import json
import uuid
from http import HTTPStatus

import pytest
from vws import VWS, CloudRecoService
from vws.exceptions import cloud_reco_exceptions
from vws.exceptions.vws_exceptions import AuthenticationFailureError, FailError

from mock_vws._constants import ResultCodes
from mock_vws.database import CloudDatabase
from tests.mock_vws.utils.assertions import (
    assert_valid_transaction_id,
    assert_vwq_failure,
)


def test_bad_access_key_services(
    vuforia_database: CloudDatabase,
    base_vws_url: str,
) -> None:
    """
    If the server access key given does not match any database, a
    ``Fail``
    response is returned.
    """
    vws_client = VWS(
        server_access_key="example",
        server_secret_key=vuforia_database.server_secret_key,
        base_vws_url=base_vws_url,
    )

    with pytest.raises(expected_exception=FailError) as exc:
        _ = vws_client.get_target_record(target_id=uuid.uuid4().hex)

    assert exc.value.response.status_code == HTTPStatus.BAD_REQUEST


def test_bad_access_key_query(
    *,
    vuforia_database: CloudDatabase,
    high_quality_image: io.BytesIO,
    base_vwq_url: str,
) -> None:
    """
    If the client access key given is incorrect, an ``UNAUTHORIZED``
    response is returned.
    """
    cloud_reco_client = CloudRecoService(
        client_access_key="example",
        client_secret_key=vuforia_database.client_secret_key,
        base_vwq_url=base_vwq_url,
    )

    with pytest.raises(
        expected_exception=cloud_reco_exceptions.AuthenticationFailureError
    ) as exc:
        _ = cloud_reco_client.query(image=high_quality_image)

    response = exc.value.response

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.UNAUTHORIZED,
        content_type="application/json",
        cache_control=None,
        www_authenticate="VWS",
        connection="keep-alive",
    )

    assert json.loads(s=response.text).keys() == {
        "transaction_id",
        "result_code",
    }
    assert_valid_transaction_id(response=response)
    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert isinstance(response_json["result_code"], str)
    assert isinstance(response_json["transaction_id"], str)
    result_code: str = response_json["result_code"]
    transaction_id: str = response_json["transaction_id"]
    assert result_code == ResultCodes.AUTHENTICATION_FAILURE.value
    # The separators are inconsistent and we test this.
    expected_text = (
        '{"transaction_id":'
        f'"{transaction_id}",'
        f'"result_code":"{result_code}"'
        "}"
    )
    assert response.text == expected_text


def test_bad_secret_key_services(
    vuforia_database: CloudDatabase,
    base_vws_url: str,
) -> None:
    """
    If the server secret key given is incorrect, an
    ``AuthenticationFailureError`` response is returned.
    """
    vws_client = VWS(
        server_access_key=vuforia_database.server_access_key,
        server_secret_key="example",
        base_vws_url=base_vws_url,
    )

    with pytest.raises(expected_exception=AuthenticationFailureError):
        _ = vws_client.get_target_record(target_id=uuid.uuid4().hex)


def test_bad_secret_key_query(
    *,
    vuforia_database: CloudDatabase,
    high_quality_image: io.BytesIO,
    base_vwq_url: str,
) -> None:
    """
    If the client secret key given is incorrect, an ``UNAUTHORIZED``
    response is returned.
    """
    cloud_reco_client = CloudRecoService(
        client_access_key=vuforia_database.client_access_key,
        client_secret_key="example",
        base_vwq_url=base_vwq_url,
    )

    with pytest.raises(
        expected_exception=cloud_reco_exceptions.AuthenticationFailureError
    ) as exc:
        _ = cloud_reco_client.query(image=high_quality_image)

    response = exc.value.response

    assert_vwq_failure(
        response=response,
        status_code=HTTPStatus.UNAUTHORIZED,
        content_type="application/json",
        cache_control=None,
        www_authenticate="VWS",
        connection="keep-alive",
    )

    assert json.loads(s=response.text).keys() == {
        "transaction_id",
        "result_code",
    }
    assert_valid_transaction_id(response=response)
    response_json = json.loads(s=response.text)
    assert isinstance(response_json, dict)
    assert isinstance(response_json["result_code"], str)
    assert isinstance(response_json["transaction_id"], str)
    result_code: str = response_json["result_code"]
    transaction_id: str = response_json["transaction_id"]
    assert result_code == ResultCodes.AUTHENTICATION_FAILURE.value
    # The separators are inconsistent and we test this.
    expected_text = (
        '{"transaction_id":'
        f'"{transaction_id}",'
        f'"result_code":"{result_code}"'
        "}"
    )
    assert response.text == expected_text
