"""Tests for images through the Flask app."""

import io
import uuid

import pytest
import requests
from PIL import Image
from vws import VWS, CloudRecoService

from mock_vws.database import CloudDatabase


def test_query_image_matchers_exact_match(
    *,
    high_quality_image: io.BytesIO,
    monkeypatch: pytest.MonkeyPatch,
    target_manager_url: str,
) -> None:
    """The exact matcher matches only exactly the same images."""
    monkeypatch.setenv(name="QUERY_IMAGE_MATCHER", value="exact")

    database = CloudDatabase()

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    cloud_reco_client = CloudRecoService(
        client_access_key=database.client_access_key,
        client_secret_key=database.client_secret_key,
    )

    pil_image = Image.open(fp=high_quality_image)
    re_exported_image = io.BytesIO()
    pil_image.save(fp=re_exported_image, format="PNG")

    databases_url = target_manager_url + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

    target_id = vws_client.add_target(
        name="example",
        width=1,
        image=high_quality_image,
        application_metadata=None,
        active_flag=True,
    )
    vws_client.wait_for_target_processed(target_id=target_id)
    same_image_result = cloud_reco_client.query(
        image=high_quality_image,
    )
    assert len(same_image_result) == 1
    different_image_result = cloud_reco_client.query(
        image=re_exported_image,
    )
    assert not bool(different_image_result)


def test_query_image_matchers_structural_similarity_matcher(
    *,
    high_quality_image: io.BytesIO,
    different_high_quality_image: io.BytesIO,
    monkeypatch: pytest.MonkeyPatch,
    target_manager_url: str,
) -> None:
    """The structural similarity matcher matches similar images."""
    monkeypatch.setenv(
        name="QUERY_IMAGE_MATCHER",
        value="structural_similarity",
    )
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    cloud_reco_client = CloudRecoService(
        client_access_key=database.client_access_key,
        client_secret_key=database.client_secret_key,
    )

    pil_image = Image.open(fp=high_quality_image)
    re_exported_image = io.BytesIO()
    pil_image.save(fp=re_exported_image, format="PNG")
    databases_url = target_manager_url + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

    assert re_exported_image.getvalue() != high_quality_image.getvalue()

    target_id = vws_client.add_target(
        name="example",
        width=1,
        image=high_quality_image,
        application_metadata=None,
        active_flag=True,
    )
    vws_client.wait_for_target_processed(target_id=target_id)
    same_image_result = cloud_reco_client.query(
        image=high_quality_image,
    )
    assert len(same_image_result) == 1
    similar_image_result = cloud_reco_client.query(
        image=re_exported_image,
    )
    assert len(similar_image_result) == 1

    different_image_result = cloud_reco_client.query(
        image=different_high_quality_image,
    )
    assert not bool(different_image_result)


def test_duplicates_image_matchers_exact_match(
    *,
    high_quality_image: io.BytesIO,
    monkeypatch: pytest.MonkeyPatch,
    target_manager_url: str,
) -> None:
    """The exact matcher matches only exactly the same images."""
    monkeypatch.setenv(name="DUPLICATES_IMAGE_MATCHER", value="exact")
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    pil_image = Image.open(fp=high_quality_image)
    re_exported_image = io.BytesIO()
    pil_image.save(fp=re_exported_image, format="PNG")

    databases_url = target_manager_url + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

    target_id = vws_client.add_target(
        name="example_0",
        width=1,
        image=high_quality_image,
        application_metadata=None,
        active_flag=True,
    )
    duplicate_target_id = vws_client.add_target(
        name="example_1",
        width=1,
        image=high_quality_image,
        application_metadata=None,
        active_flag=True,
    )
    not_duplicate_target_id = vws_client.add_target(
        name="example_2",
        width=1,
        image=re_exported_image,
        application_metadata=None,
        active_flag=True,
    )
    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.wait_for_target_processed(target_id=duplicate_target_id)
    vws_client.wait_for_target_processed(
        target_id=not_duplicate_target_id,
    )
    duplicates = vws_client.get_duplicate_targets(target_id=target_id)
    assert duplicates == [duplicate_target_id]


def test_duplicates_image_matchers_structural_similarity_matcher(
    *,
    high_quality_image: io.BytesIO,
    monkeypatch: pytest.MonkeyPatch,
    target_manager_url: str,
) -> None:
    """The structural similarity matcher matches similar images."""
    monkeypatch.setenv(
        name="DUPLICATES_IMAGE_MATCHER",
        value="structural_similarity",
    )
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    pil_image = Image.open(fp=high_quality_image)
    re_exported_image = io.BytesIO()
    pil_image.save(fp=re_exported_image, format="PNG")

    databases_url = target_manager_url + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

    target_id = vws_client.add_target(
        name="example",
        width=1,
        image=high_quality_image,
        application_metadata=None,
        active_flag=True,
    )
    duplicate_target_id = vws_client.add_target(
        name="example_1",
        width=1,
        image=re_exported_image,
        application_metadata=None,
        active_flag=True,
    )
    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.wait_for_target_processed(target_id=duplicate_target_id)
    duplicates = vws_client.get_duplicate_targets(target_id=target_id)
    assert duplicates == [duplicate_target_id]


def test_default(
    *,
    image_file_success_state_low_rating: io.BytesIO,
    high_quality_image: io.BytesIO,
    target_manager_url: str,
) -> None:
    """By default, the BRISQUE target rater is used."""
    database = CloudDatabase()
    databases_url = target_manager_url + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    low_rating_image_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_success_state_low_rating,
        application_metadata=None,
        active_flag=True,
    )

    high_quality_image_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        application_metadata=None,
        active_flag=True,
    )

    for target_id in (
        low_rating_image_target_id,
        high_quality_image_target_id,
    ):
        vws_client.wait_for_target_processed(target_id=target_id)

    low_rated_image_rating = vws_client.get_target_record(
        target_id=low_rating_image_target_id,
    ).target_record.tracking_rating

    high_quality_image_rating = vws_client.get_target_record(
        target_id=high_quality_image_target_id,
    ).target_record.tracking_rating

    assert low_rated_image_rating <= 0
    assert high_quality_image_rating > 1


def test_brisque(
    *,
    monkeypatch: pytest.MonkeyPatch,
    image_file_success_state_low_rating: io.BytesIO,
    high_quality_image: io.BytesIO,
    target_manager_url: str,
) -> None:
    """It is possible to use the BRISQUE target rater."""
    monkeypatch.setenv(name="TARGET_RATER", value="brisque")

    database = CloudDatabase()
    databases_url = target_manager_url + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    low_rating_image_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image_file_success_state_low_rating,
        application_metadata=None,
        active_flag=True,
    )

    high_quality_image_target_id = vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=high_quality_image,
        application_metadata=None,
        active_flag=True,
    )

    for target_id in (
        low_rating_image_target_id,
        high_quality_image_target_id,
    ):
        vws_client.wait_for_target_processed(target_id=target_id)

    low_rated_image_rating = vws_client.get_target_record(
        target_id=low_rating_image_target_id,
    ).target_record.tracking_rating

    high_quality_image_rating = vws_client.get_target_record(
        target_id=high_quality_image_target_id,
    ).target_record.tracking_rating

    assert low_rated_image_rating <= 0
    assert high_quality_image_rating > 1


def test_perfect(
    *,
    monkeypatch: pytest.MonkeyPatch,
    high_quality_image: io.BytesIO,
    target_manager_url: str,
) -> None:
    """It is possible to use the perfect target rater."""
    monkeypatch.setenv(name="TARGET_RATER", value="perfect")
    database = CloudDatabase()
    databases_url = target_manager_url + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    target_ids = [
        vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            application_metadata=None,
            active_flag=True,
        )
        for _ in range(50)
    ]

    for target_id in target_ids:
        vws_client.wait_for_target_processed(target_id=target_id)

    ratings_set = {
        vws_client.get_target_record(
            target_id=target_id
        ).target_record.tracking_rating
        for target_id in target_ids
    }

    assert ratings_set == {5}


def test_random(
    *,
    monkeypatch: pytest.MonkeyPatch,
    high_quality_image: io.BytesIO,
    target_manager_url: str,
) -> None:
    """It is possible to use the random target rater."""
    monkeypatch.setenv(name="TARGET_RATER", value="random")

    database = CloudDatabase()
    databases_url = target_manager_url + "/cloud_databases"
    _ = requests.post(url=databases_url, json=database.to_dict(), timeout=30)

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    target_ids = [
        vws_client.add_target(
            name=uuid.uuid4().hex,
            width=1,
            image=high_quality_image,
            application_metadata=None,
            active_flag=True,
        )
        for _ in range(50)
    ]

    for target_id in target_ids:
        vws_client.wait_for_target_processed(target_id=target_id)

    ratings = [
        vws_client.get_target_record(
            target_id=target_id
        ).target_record.tracking_rating
        for target_id in target_ids
    ]

    sorted_ratings = sorted(ratings)
    lowest_rating = sorted_ratings[0]
    highest_rating = sorted_ratings[-1]
    minimum_rating = 0
    maximum_rating = 5
    assert lowest_rating >= minimum_rating
    assert highest_rating <= maximum_rating
    assert lowest_rating != highest_rating
