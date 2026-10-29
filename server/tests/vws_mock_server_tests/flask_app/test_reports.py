"""Tests for reports through the Flask app."""

import requests
from vws import VWS

from mock_vws.database import CloudDatabase

# Tests for recognition counts in the Flask mock.
#
# The in-memory mock uses the ``CloudDatabase`` object which it is given,
# so it shows whatever counts that object has. The Flask mock keeps its
# databases in the target manager service, so the counts have to survive
# the trip through it.

_CURRENT_MONTH_RECOS = 3
_PREVIOUS_MONTH_RECOS = 5
_TOTAL_RECOS = 8
_RECO_THRESHOLD = 20


def test_seeded_database_counts(target_manager_url: str) -> None:
    """The Flask mock preserves the counts of a seeded database."""
    database = CloudDatabase(
        current_month_recos=_CURRENT_MONTH_RECOS,
        previous_month_recos=_PREVIOUS_MONTH_RECOS,
        total_recos=_TOTAL_RECOS,
        reco_threshold=_RECO_THRESHOLD,
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

    report = client.get_database_summary_report()

    assert report.current_month_recos == _CURRENT_MONTH_RECOS
    assert report.previous_month_recos == _PREVIOUS_MONTH_RECOS
    assert report.total_recos == _TOTAL_RECOS
    assert report.reco_threshold == _RECO_THRESHOLD
