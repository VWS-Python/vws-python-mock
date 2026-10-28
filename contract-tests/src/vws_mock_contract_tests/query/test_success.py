"""Tests for successful calls to the query endpoint."""

import base64
import calendar
import copy
import io
import json
import time

from dirty_equals import IsInstance
from PIL import Image
from vws import VWS, CloudRecoService

from vws_mock_contract_tests.fixtures.credentials import (
    CloudDatabaseCredentials,
)
from vws_mock_contract_tests.query.helpers import (
    query,
)
from vws_mock_contract_tests.utils.assertions import (
    assert_query_success,
)


def test_no_results(
    *,
    high_quality_image: io.BytesIO,
    cloud_reco_client: CloudRecoService,
) -> None:
    """
    When there are no matching images in the database, an empty list
    of
    results is returned.
    """
    results = cloud_reco_client.query(image=high_quality_image)
    assert results == []


def test_match_exact(
    *,
    high_quality_image: io.BytesIO,
    vuforia_database: CloudDatabaseCredentials,
    vws_client: VWS,
    base_vwq_url: str,
) -> None:
    """
    If the exact high quality image that was added is queried for,
    target
    data is shown.
    """
    image_file = high_quality_image
    image_content = image_file.getvalue()
    metadata_encoded = base64.b64encode(s=b"example").decode(encoding="ascii")
    name = "example_name"

    target_id = vws_client.add_target(
        name=name,
        width=1,
        image=image_file,
        active_flag=True,
        application_metadata=metadata_encoded,
    )

    approximate_target_created = calendar.timegm(tuple=time.gmtime())

    vws_client.wait_for_target_processed(target_id=target_id)

    body = {"image": ("image.jpeg", image_content, "image/jpeg")}

    response = query(
        vuforia_database=vuforia_database, body=body, base_vwq_url=base_vwq_url
    )

    assert_query_success(response=response)
    response_json = json.loads(s=response.text)
    (result,) = response_json["results"]
    assert result == {
        "target_id": target_id,
        "target_data": {
            "application_metadata": metadata_encoded,
            "name": name,
            "target_timestamp": IsInstance(expected_type=int),
        },
    }
    target_timestamp_value: object = result["target_data"]["target_timestamp"]
    assert isinstance(target_timestamp_value, int)
    target_timestamp = target_timestamp_value
    time_difference = abs(approximate_target_created - target_timestamp)
    max_time_difference = 5
    assert time_difference < max_time_difference


def test_low_quality_image(
    *,
    image_file_success_state_low_rating: io.BytesIO,
    cloud_reco_client: CloudRecoService,
    vws_client: VWS,
) -> None:
    """
    If the exact low quality image that was added is queried for, no
    results are returned.
    """
    image_file = image_file_success_state_low_rating
    metadata_encoded = base64.b64encode(s=b"example").decode(encoding="ascii")
    name = "example_name"

    target_id = vws_client.add_target(
        name=name,
        width=1,
        image=image_file,
        active_flag=True,
        application_metadata=metadata_encoded,
    )

    vws_client.wait_for_target_processed(target_id=target_id)
    matching_targets = cloud_reco_client.query(image=image_file)
    assert not bool(matching_targets)


def test_match_similar(
    *,
    high_quality_image: io.BytesIO,
    different_high_quality_image: io.BytesIO,
    vws_client: VWS,
    cloud_reco_client: CloudRecoService,
) -> None:
    """
    If a similar image to one that was added is queried for, target
    data is
    shown.
    """
    metadata_encoded = base64.b64encode(s=b"example").decode(encoding="ascii")
    name_matching = "example_name_matching"
    name_not_matching = "example_name_not_matching"

    target_id_matching = vws_client.add_target(
        name=name_matching,
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=metadata_encoded,
    )

    target_id_not_matching = vws_client.add_target(
        name=name_not_matching,
        width=1,
        image=different_high_quality_image,
        active_flag=True,
        application_metadata=metadata_encoded,
    )

    vws_client.wait_for_target_processed(target_id=target_id_matching)
    vws_client.wait_for_target_processed(target_id=target_id_not_matching)

    similar_image_buffer = io.BytesIO()
    similar_image_data = copy.copy(x=high_quality_image)
    pil_similar_image = Image.open(fp=similar_image_data)
    # Re-save means similar but not identical.
    pil_similar_image.save(fp=similar_image_buffer, format="JPEG")

    (matching_target,) = cloud_reco_client.query(
        image=similar_image_buffer,
        max_num_results=5,
    )

    assert matching_target.target_id == target_id_matching


def test_not_base64_encoded_processable(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
    not_base64_encoded_processable: str,
    cloud_reco_client: CloudRecoService,
) -> None:
    """
    Vuforia accepts some metadata strings which are not valid
    base64.
    When a target with such a string is matched by a query, Vuforia
    returns
    an interesting result:

    * If the metadata string is a length one greater than a multiple of 4,
      the last character is ignored.
    * If the metadata is two greater than a multiple of 4, the result is
      padded, then decoded, then encoded.
    * If the metadata is three greater than a multiple of 4, the result is
      padded, then decoded, then encoded.
    """
    target_id = vws_client.add_target(
        name="example_name",
        width=1,
        image=high_quality_image,
        active_flag=True,
        application_metadata=not_base64_encoded_processable,
    )

    vws_client.wait_for_target_processed(target_id=target_id)

    query_results = cloud_reco_client.query(image=high_quality_image)

    (result,) = query_results
    assert result.target_data is not None
    query_metadata = result.target_data.application_metadata
    mod_4_to_expected_metadata_original = {
        1: not_base64_encoded_processable[:-1],
        2: not_base64_encoded_processable + "==",
        3: not_base64_encoded_processable + "=",
    }
    expected_metadata_original = mod_4_to_expected_metadata_original[
        len(not_base64_encoded_processable) % 4
    ]
    expected_metadata = base64.b64encode(
        s=base64.b64decode(s=expected_metadata_original),
    )
    assert query_metadata == expected_metadata.decode()
