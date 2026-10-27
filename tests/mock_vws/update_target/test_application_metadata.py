"""Tests for the application metadata parameter."""

import base64
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    FailError,
    MetadataTooLargeError,
)

from tests.mock_vws.update_target.helpers import (
    MAX_METADATA_BYTES,
    update_target,
)
from tests.mock_vws.utils.assertions import (
    assert_vws_failure,
)


@pytest.mark.parametrize(
    argnames="metadata",
    argvalues=[
        b"a",
        b"a" * MAX_METADATA_BYTES,
    ],
    ids=["Short", "Max length"],
)
def test_base64_encoded(
    *,
    target_id: str,
    metadata: bytes,
    vws_client: VWS,
) -> None:
    """A base64 encoded string is valid application metadata."""
    metadata_encoded = base64.b64encode(s=metadata).decode(encoding="ascii")
    vws_client.update_target(
        target_id=target_id,
        application_metadata=metadata_encoded,
    )


@pytest.mark.parametrize(argnames="invalid_metadata", argvalues=[1, None])
def test_invalid_type(
    *,
    vws_client: VWS,
    target_id: str,
    invalid_metadata: int | None,
) -> None:
    """Non-string values cannot be given as valid application metadata."""
    with pytest.raises(expected_exception=FailError) as exc:
        _ = update_target(
            vws_client=vws_client,
            data={"application_metadata": invalid_metadata},
            target_id=target_id,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )


def test_not_base64_encoded_processable(
    *,
    vws_client: VWS,
    target_id: str,
    not_base64_encoded_processable: str,
) -> None:
    """
    Some strings which are not valid base64 encoded strings are
    allowed as
    application metadata.
    """
    vws_client.update_target(
        target_id=target_id,
        application_metadata=not_base64_encoded_processable,
    )


def test_not_base64_encoded_not_processable(
    *,
    vws_client: VWS,
    target_id: str,
    not_base64_encoded_not_processable: str,
) -> None:
    """
    Some strings which are not valid base64 encoded strings are not
    allowed
    as application metadata.
    """
    with pytest.raises(expected_exception=FailError) as exc:
        vws_client.update_target(
            target_id=target_id,
            application_metadata=not_base64_encoded_not_processable,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="Fail",
    )


def test_metadata_too_large(
    *,
    vws_client: VWS,
    target_id: str,
    application_metadata_near_size_limit: str,
) -> None:
    """
    A base64 encoded string of greater than 1024 * 1024 bytes is too
    large
    for application metadata.
    """
    decoded_metadata = base64.b64decode(
        s=application_metadata_near_size_limit.encode(encoding="ascii"),
    )
    metadata_encoded = base64.b64encode(
        s=decoded_metadata + b"x",
    ).decode(encoding="ascii")

    with pytest.raises(expected_exception=MetadataTooLargeError) as exc:
        vws_client.update_target(
            target_id=target_id,
            application_metadata=metadata_encoded,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="MetadataTooLarge",
    )
