"""Tests for reports through the Flask app."""

import requests
from vws import VWS

from mock_vws.database import CloudDatabase
from tests.mock_vws.flask_app.helpers import EXAMPLE_URL_FOR_TARGET_MANAGER


class TestRecognitionCounts:
    """Tests for recognition counts in the Flask mock.

    The in-memory mock uses the ``CloudDatabase`` object which it is given,
    so it shows whatever counts that object has. The Flask mock keeps its
    databases in the target manager service, so the counts have to survive
    the trip through it.
    """

    CURRENT_MONTH_RECOS = 3
    PREVIOUS_MONTH_RECOS = 5
    TOTAL_RECOS = 8
    RECO_THRESHOLD = 20

    def test_seeded_database_counts(self) -> None:
        """The Flask mock preserves the counts of a seeded database."""
        database = CloudDatabase(
            current_month_recos=self.CURRENT_MONTH_RECOS,
            previous_month_recos=self.PREVIOUS_MONTH_RECOS,
            total_recos=self.TOTAL_RECOS,
            reco_threshold=self.RECO_THRESHOLD,
        )
        databases_url = EXAMPLE_URL_FOR_TARGET_MANAGER + "/cloud_databases"
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

        report = client.get_database_summary_report()

        assert report.current_month_recos == self.CURRENT_MONTH_RECOS
        assert report.previous_month_recos == self.PREVIOUS_MONTH_RECOS
        assert report.total_recos == self.TOTAL_RECOS
        assert report.reco_threshold == self.RECO_THRESHOLD
