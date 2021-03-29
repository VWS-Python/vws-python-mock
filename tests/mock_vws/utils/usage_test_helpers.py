"""
Helpers for testing the usage of the mocks.
"""
import io
from datetime import datetime

from vws import VWS, CloudRecoService
from vws.exceptions.custom_exceptions import (
    ActiveMatchingTargetsDeleteProcessing,
)
from vws.reports import TargetStatuses

from mock_vws.database import VuforiaDatabase


def _add_and_delete_target(
    image: io.BytesIO,
    vuforia_database: VuforiaDatabase,
) -> None:
    """
    Add and delete a target with the given image.
    """
    vws_client = VWS(
        server_access_key=vuforia_database.server_access_key,
        server_secret_key=vuforia_database.server_secret_key,
    )

    target_id = vws_client.add_target(
        name='example_name',
        width=1,
        image=image,
        active_flag=True,
        application_metadata=None,
    )
    vws_client.wait_for_target_processed(target_id=target_id)
    vws_client.delete_target(target_id=target_id)


def processing_time_seconds(
    vuforia_database: VuforiaDatabase,
    image: io.BytesIO,
) -> float:
    """
    Return the time taken to process a target in the database.
    """
    vws_client = VWS(
        server_access_key=vuforia_database.server_access_key,
        server_secret_key=vuforia_database.server_secret_key,
    )
    target_id = vws_client.add_target(
        name='example',
        width=1,
        image=image,
        active_flag=True,
        application_metadata=None,
    )
    start_time = datetime.now()

    while (
        vws_client.get_target_record(target_id=target_id).status
        == TargetStatuses.PROCESSING
    ):
        pass

    return (datetime.now() - start_time).total_seconds()


def _wait_for_deletion_recognized(
    image: io.BytesIO,
    vuforia_database: VuforiaDatabase,
) -> None:
    """
    Wait until the query endpoint "recognizes" the deletion of all targets with
    an image matching the given image.

    That is, wait until querying the given image does not return a result with
    targets.
    """
    cloud_reco_client = CloudRecoService(
        client_access_key=vuforia_database.client_access_key,
        client_secret_key=vuforia_database.client_secret_key,
    )

    while True:
        try:
            results = cloud_reco_client.query(image=image)
        except ActiveMatchingTargetsDeleteProcessing:
            return

        if not results:
            return


def _wait_for_deletion_processed(
    image: io.BytesIO,
    vuforia_database: VuforiaDatabase,
) -> None:
    """
    Wait until the query endpoint "recognizes" the deletion of all targets with
    an image matching the given image.

    That is, wait until querying the given image returns a result with no
    targets.
    """
    _wait_for_deletion_recognized(
        image=image,
        vuforia_database=vuforia_database,
    )

    cloud_reco_client = CloudRecoService(
        client_access_key=vuforia_database.client_access_key,
        client_secret_key=vuforia_database.client_secret_key,
    )

    while True:
        try:
            cloud_reco_client.query(image=image)
        except ActiveMatchingTargetsDeleteProcessing:
            continue
        return


def recognize_deletion_seconds(
    high_quality_image: io.BytesIO,
    vuforia_database: VuforiaDatabase,
) -> float:
    """
    The number of seconds it takes for the query endpoint to recognize a
    deletion.
    """
    _add_and_delete_target(
        image=high_quality_image,
        vuforia_database=vuforia_database,
    )

    time_after_deletion = datetime.now()

    _wait_for_deletion_recognized(
        image=high_quality_image,
        vuforia_database=vuforia_database,
    )

    time_difference = datetime.now() - time_after_deletion
    return time_difference.total_seconds()


def process_deletion_seconds(
    high_quality_image: io.BytesIO,
    vuforia_database: VuforiaDatabase,
) -> float:
    """
    The number of seconds it takes for the query endpoint to process a
    deletion.
    """
    _add_and_delete_target(
        image=high_quality_image,
        vuforia_database=vuforia_database,
    )

    _wait_for_deletion_recognized(
        image=high_quality_image,
        vuforia_database=vuforia_database,
    )

    time_after_deletion_recognized = datetime.now()

    _wait_for_deletion_processed(
        image=high_quality_image,
        vuforia_database=vuforia_database,
    )

    time_difference = datetime.now() - time_after_deletion_recognized
    return time_difference.total_seconds()
