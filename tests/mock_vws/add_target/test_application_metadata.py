"""Tests for the application metadata parameter."""

import base64
import io
from http import HTTPStatus

import pytest
from vws import VWS
from vws.exceptions.vws_exceptions import (
    FailError,
    MetadataTooLargeError,
)

from tests.mock_vws.add_target.helpers import (
    MAX_METADATA_BYTES,
    add_target_to_vws,
    assert_success,
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
    image_file_failed_state: io.BytesIO,
    metadata: bytes,
    vws_client: VWS,
) -> None:
    """A base64 encoded string is valid application metadata."""
    metadata_encoded = base64.b64encode(s=metadata).decode(encoding="ascii")

    _ = vws_client.add_target(
        name="example",
        width=1,
        image=image_file_failed_state,
        application_metadata=metadata_encoded,
        active_flag=True,
    )


def test_null(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
) -> None:
    """NULL is valid application metadata."""
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )

    request_data = {
        "name": "example_name",
        "width": 1,
        "image": image_data_encoded,
        "application_metadata": None,
    }

    response = add_target_to_vws(
        vws_client=vws_client,
        data=request_data,
        content_type="application/json",
    )

    assert_success(response=response)


def test_invalid_type(
    *,
    vws_client: VWS,
    image_file_failed_state: io.BytesIO,
) -> None:
    """
    Values which are not a string or NULL are not valid application
    metadata.
    """
    image_data = image_file_failed_state.getvalue()
    image_data_encoded = base64.b64encode(s=image_data).decode(
        encoding="ascii"
    )

    data = {
        "name": "example_name",
        "width": 1,
        "image": image_data_encoded,
        "application_metadata": 1,
    }

    with pytest.raises(expected_exception=FailError) as exc:
        _ = add_target_to_vws(
            vws_client=vws_client,
            data=data,
            content_type="application/json",
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.BAD_REQUEST,
        result_code="Fail",
    )


def test_not_base64_encoded_processable(
    *,
    high_quality_image: io.BytesIO,
    not_base64_encoded_processable: str,
    vws_client: VWS,
) -> None:
    """
    Some strings which are not valid base64 encoded strings are
    allowed as
    application metadata.
    """
    _ = vws_client.add_target(
        name="example",
        width=1,
        image=high_quality_image,
        application_metadata=not_base64_encoded_processable,
        active_flag=True,
    )


def test_not_base64_encoded_not_processable(
    *,
    high_quality_image: io.BytesIO,
    not_base64_encoded_not_processable: str,
    vws_client: VWS,
) -> None:
    """
    Some strings which are not valid base64 encoded strings are not
    allowed
    as application metadata.
    """
    with pytest.raises(expected_exception=FailError) as exc:
        _ = vws_client.add_target(
            name="example",
            width=1,
            image=high_quality_image,
            application_metadata=not_base64_encoded_not_processable,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="Fail",
    )


def test_metadata_too_large(
    *,
    image_file_failed_state: io.BytesIO,
    vws_client: VWS,
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
        _ = vws_client.add_target(
            name="example",
            width=1,
            image=image_file_failed_state,
            application_metadata=metadata_encoded,
            active_flag=True,
        )

    assert_vws_failure(
        response=exc.value.response,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        result_code="MetadataTooLarge",
    )
