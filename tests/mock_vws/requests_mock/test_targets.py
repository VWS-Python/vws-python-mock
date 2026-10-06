"""Tests for targets through the `requests-mock` backend."""

import dataclasses
import datetime
import io
import json
import uuid
from zoneinfo import ZoneInfo

import pytest
from vws import VWS
from vws.reports import TargetStatuses

from mock_vws import MockVWS
from mock_vws.database import CloudDatabase
from mock_vws.target import ImageTarget, VuMarkTarget
from mock_vws.target_raters import HardcodedTargetTrackingRater


def test_to_dict(high_quality_image: io.BytesIO) -> None:
    """
    It is possible to dump a target to a dictionary and load it
    back.
    """
    database = CloudDatabase()

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        _ = vws_client.add_target(
            name="example",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )

    assert len(database.targets) == 1
    target = next(iter(database.targets))
    assert isinstance(target, ImageTarget)
    target_dict = target.to_dict()

    # The dictionary is JSON dump-able
    assert bool(json.dumps(obj=target_dict))

    new_target = ImageTarget.from_dict(target_dict=target_dict)
    assert new_target == target


def test_to_dict_deleted(high_quality_image: io.BytesIO) -> None:
    """
    It is possible to dump a deleted target to a dictionary and load
    it
    back.
    """
    database = CloudDatabase()

    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        target_id = vws_client.add_target(
            name="example",
            width=1,
            image=high_quality_image,
            active_flag=True,
            application_metadata=None,
        )
        vws_client.wait_for_target_processed(target_id=target_id)
        vws_client.delete_target(target_id=target_id)

    assert len(database.targets) == 1
    target = next(iter(database.targets))
    assert isinstance(target, ImageTarget)
    target_dict = target.to_dict()

    # The dictionary is JSON dump-able
    assert bool(json.dumps(obj=target_dict))

    new_target = ImageTarget.from_dict(target_dict=target_dict)
    assert new_target.delete_date == target.delete_date


def test_round_trip_non_default_fields(
    high_quality_image: io.BytesIO,
) -> None:
    """Every field of a target survives a dictionary round trip.

    The target tracking rater is deliberately not preserved:
    ``to_dict`` writes the computed tracking rating and ``from_dict``
    rebuilds the target with a hardcoded rater which gives that
    rating.
    """
    gmt = ZoneInfo(key="GMT")
    target = ImageTarget(
        active_flag=False,
        application_metadata="example-metadata",
        current_month_recos=1,
        delete_date=datetime.datetime(year=2020, month=1, day=4, tzinfo=gmt),
        image_value=high_quality_image.getvalue(),
        last_modified_date=datetime.datetime(
            year=2020, month=1, day=3, tzinfo=gmt
        ),
        name="example",
        previous_month_recos=2,
        processing_time_seconds=0.5,
        reco_rating="example-reco-rating",
        target_id="example-target-id",
        target_tracking_rater=HardcodedTargetTrackingRater(rating=4),
        total_recos=3,
        upload_date=datetime.datetime(year=2020, month=1, day=2, tzinfo=gmt),
        width=1.5,
    )
    # Adding a field to ``ImageTarget`` must mean adding it to this
    # test, and therefore to the round trip.
    expected_field_names = {
        "active_flag",
        "application_metadata",
        "current_month_recos",
        "delete_date",
        "image_value",
        "last_modified_date",
        "name",
        "previous_month_recos",
        "processing_time_seconds",
        "reco_rating",
        "target_id",
        "target_tracking_rater",
        "total_recos",
        "upload_date",
        "width",
    }
    field_names = {
        field.name
        for field in dataclasses.fields(class_or_instance=ImageTarget)
    }
    assert field_names == expected_field_names

    target_dict = target.to_dict()
    # The dictionary is JSON dump-able
    assert bool(json.dumps(obj=target_dict))

    new_target = ImageTarget.from_dict(target_dict=target_dict)
    assert new_target == target
    assert new_target.tracking_rating == target.tracking_rating


def test_vumark_target_to_dict() -> None:
    """It is possible to dump a VuMark target to a dictionary and
    load it back.
    """
    vumark_target = VuMarkTarget(
        name="example-vumark",
        processing_time_seconds=5.0,
    )
    target_dict = vumark_target.to_dict()

    assert bool(json.dumps(obj=target_dict))

    new_target = VuMarkTarget.from_dict(target_dict=target_dict)
    assert new_target == vumark_target


class TestSetTargetRecognitionCounts:
    """Tests for setting the recognition counts of a target."""

    CURRENT_MONTH_RECOS = 3
    PREVIOUS_MONTH_RECOS = 5
    TOTAL_RECOS = 8

    def test_set_one_count(self, high_quality_image: io.BytesIO) -> None:
        """Counts which are not given are left as they are."""
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            mock.set_target_recognition_counts(
                target_id=target_id,
                total_recos=self.TOTAL_RECOS,
            )
            mock.set_target_recognition_counts(
                target_id=target_id,
                current_month_recos=self.CURRENT_MONTH_RECOS,
            )

            report = vws_client.get_target_summary_report(target_id=target_id)

        assert report.total_recos == self.TOTAL_RECOS
        assert report.current_month_recos == self.CURRENT_MONTH_RECOS
        assert report.previous_month_recos == 0

    def test_recognition_counts_do_not_change_the_target(
        self,
        high_quality_image: io.BytesIO,
    ) -> None:
        """Setting recognition counts does not change the target itself.

        A target which is being recognized is not being modified, so its
        last modified date does not change, and it does not go back to
        being processed.
        """
        database = CloudDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            target_id = vws_client.add_target(
                name="example",
                width=1,
                image=high_quality_image,
                active_flag=True,
                application_metadata=None,
            )
            vws_client.wait_for_target_processed(target_id=target_id)
            (target,) = database.targets
            last_modified_date = target.last_modified_date

            mock.set_target_recognition_counts(
                target_id=target_id,
                current_month_recos=self.CURRENT_MONTH_RECOS,
                previous_month_recos=self.PREVIOUS_MONTH_RECOS,
                total_recos=self.TOTAL_RECOS,
            )

            report = vws_client.get_target_summary_report(target_id=target_id)

        (new_target,) = database.targets
        assert new_target.last_modified_date == last_modified_date
        assert report.status == TargetStatuses.SUCCESS

    @staticmethod
    def test_unknown_target() -> None:
        """Setting the counts of an unknown target is an error."""
        database = CloudDatabase()
        target_id = uuid.uuid4().hex

        with MockVWS() as mock:
            mock.add_cloud_database(cloud_database=database)
            with pytest.raises(
                expected_exception=ValueError,
                match=f'No target has the ID "{target_id}".',
            ):
                mock.set_target_recognition_counts(
                    target_id=target_id,
                    total_recos=1,
                )
