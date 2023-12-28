"""
Helpers for testing the usage of the mocks.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from vws import VWS
from vws.reports import TargetStatuses

if TYPE_CHECKING:
    import io

    from mock_vws.database import VuforiaDatabase


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
        name="example",
        width=1,
        image=image,
        active_flag=True,
        application_metadata=None,
    )
    start_time = datetime.datetime.now(tz=datetime.UTC)

    while (
        vws_client.get_target_record(target_id=target_id).status
        == TargetStatuses.PROCESSING
    ):
        pass

    return (
        datetime.datetime.now(tz=datetime.UTC) - start_time
    ).total_seconds()
