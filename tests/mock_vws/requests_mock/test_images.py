"""Tests for images through the `requests-mock` backend."""

import io

import pytest
from beartype import beartype
from PIL import Image
from vws import VWS, CloudRecoService

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase
from mock_vws.image_matchers import ExactMatcher, StructuralSimilarityMatcher


@beartype
def _not_exact_matcher(
    first_image_content: bytes,
    second_image_content: bytes,
) -> float | None:
    """A matcher which matches images which are not the same."""
    if first_image_content != second_image_content:
        return 1.0
    return None


@beartype
def _image_length_matcher(
    first_image_content: bytes,
    second_image_content: bytes,
) -> float | None:
    """A matcher which matches every image.

    Images whose contents are closer in length get a higher score.
    """
    return float(-abs(len(first_image_content) - len(second_image_content)))


@beartype
def _bool_matcher(
    first_image_content: bytes,
    second_image_content: bytes,
) -> bool:
    """A matcher of the kind which was supported before matchers gave
    scores.
    """
    return first_image_content == second_image_content


def test_query_exact_match(
    high_quality_image: io.BytesIO,
) -> None:
    """The exact matcher matches only exactly the same images."""
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

    with MockVWS(query_match_checker=ExactMatcher()) as mock:
        mock.add_cloud_database(cloud_database=database)
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


def test_query_custom_matcher(
    high_quality_image: io.BytesIO,
) -> None:
    """It is possible to use a custom matcher."""
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

    with MockVWS(query_match_checker=_not_exact_matcher) as mock:
        mock.add_cloud_database(cloud_database=database)
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
        assert not bool(same_image_result)
        different_image_result = cloud_reco_client.query(
            image=re_exported_image,
        )
        assert len(different_image_result) == 1


def test_query_structural_similarity_matcher(
    *,
    high_quality_image: io.BytesIO,
    different_high_quality_image: io.BytesIO,
) -> None:
    """The structural similarity matcher matches similar images."""
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

    with MockVWS(
        query_match_checker=StructuralSimilarityMatcher(),
    ) as mock:
        mock.add_cloud_database(cloud_database=database)
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


def test_query_results_are_ordered_by_match_score(
    *,
    high_quality_image: io.BytesIO,
    different_high_quality_image: io.BytesIO,
) -> None:
    """Query results are ordered by match score, best match first."""
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    cloud_reco_client = CloudRecoService(
        client_access_key=database.client_access_key,
        client_secret_key=database.client_secret_key,
    )

    with MockVWS(query_match_checker=_image_length_matcher) as mock:
        mock.add_cloud_database(cloud_database=database)
        first_target_id = vws_client.add_target(
            name="example_0",
            width=1,
            image=high_quality_image,
            application_metadata=None,
            active_flag=True,
        )
        second_target_id = vws_client.add_target(
            name="example_1",
            width=1,
            image=different_high_quality_image,
            application_metadata=None,
            active_flag=True,
        )
        vws_client.wait_for_target_processed(target_id=first_target_id)
        vws_client.wait_for_target_processed(target_id=second_target_id)

        # The second target's image is an exact length match for the
        # query image, so it comes first despite being uploaded last.
        results = cloud_reco_client.query(
            image=different_high_quality_image,
            max_num_results=2,
        )
        result_target_ids = [result.target_id for result in results]
        assert result_target_ids == [second_target_id, first_target_id]

        results = cloud_reco_client.query(
            image=high_quality_image,
            max_num_results=2,
        )
        result_target_ids = [result.target_id for result in results]
        assert result_target_ids == [first_target_id, second_target_id]


def test_bool_matcher(high_quality_image: io.BytesIO) -> None:
    """A matcher which returns a ``bool`` gives a useful error.

    Matchers used to answer yes or no; they now give a score.
    """
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )
    cloud_reco_client = CloudRecoService(
        client_access_key=database.client_access_key,
        client_secret_key=database.client_secret_key,
    )

    with MockVWS(query_match_checker=_bool_matcher) as mock:
        mock.add_cloud_database(cloud_database=database)
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=high_quality_image,
            application_metadata=None,
            active_flag=True,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        expected_message = (
            "Image matchers must return a score or None, but .* returned True."
        )
        with pytest.raises(
            expected_exception=TypeError,
            match=expected_message,
        ):
            _ = cloud_reco_client.query(image=high_quality_image)


def test_duplicates_exact_match(
    high_quality_image: io.BytesIO,
) -> None:
    """The exact matcher matches only exactly the same images."""
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    pil_image = Image.open(fp=high_quality_image)
    re_exported_image = io.BytesIO()
    pil_image.save(fp=re_exported_image, format="PNG")

    with MockVWS(duplicate_match_checker=ExactMatcher()) as mock:
        mock.add_cloud_database(cloud_database=database)
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


def test_duplicates_custom_matcher(
    high_quality_image: io.BytesIO,
) -> None:
    """It is possible to use a custom matcher."""
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    pil_image = Image.open(fp=high_quality_image)
    re_exported_image = io.BytesIO()
    pil_image.save(fp=re_exported_image, format="PNG")

    with MockVWS(duplicate_match_checker=_not_exact_matcher) as mock:
        mock.add_cloud_database(cloud_database=database)
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
        assert duplicates == [not_duplicate_target_id]


def test_duplicates_structural_similarity_matcher(
    high_quality_image: io.BytesIO,
) -> None:
    """The structural similarity matcher matches similar images."""
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    pil_image = Image.open(fp=high_quality_image)
    re_exported_image = io.BytesIO()
    pil_image.save(fp=re_exported_image, format="PNG")

    with MockVWS(
        duplicate_match_checker=StructuralSimilarityMatcher(),
    ) as mock:
        mock.add_cloud_database(cloud_database=database)
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


def test_duplicates_results_are_ordered_by_match_score(
    *,
    high_quality_image: io.BytesIO,
    different_high_quality_image: io.BytesIO,
) -> None:
    """Duplicates are ordered by match score, best match first."""
    database = CloudDatabase()
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS(duplicate_match_checker=_image_length_matcher) as mock:
        mock.add_cloud_database(cloud_database=database)
        target_id = vws_client.add_target(
            name="example_0",
            width=1,
            image=high_quality_image,
            application_metadata=None,
            active_flag=True,
        )
        different_image_target_id = vws_client.add_target(
            name="example_1",
            width=1,
            image=different_high_quality_image,
            application_metadata=None,
            active_flag=True,
        )
        same_image_target_id = vws_client.add_target(
            name="example_2",
            width=1,
            image=high_quality_image,
            application_metadata=None,
            active_flag=True,
        )
        for created_target_id in (
            target_id,
            different_image_target_id,
            same_image_target_id,
        ):
            vws_client.wait_for_target_processed(
                target_id=created_target_id,
            )

        # The last uploaded target's image is an exact length match, so
        # it comes first.
        duplicates = vws_client.get_duplicate_targets(target_id=target_id)
        assert duplicates == [
            same_image_target_id,
            different_image_target_id,
        ]
