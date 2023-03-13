"""
Tools for making Vuforia queries.
"""

from __future__ import annotations

import base64
import datetime
import io
import uuid
from email.message import EmailMessage
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image
import numpy
import multipart

from mock_vws.target import Target
from mock_vws._base64_decoding import decode_base64
from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._mock_common import json_dump
from mock_vws.database import VuforiaDatabase
from brisque import BRISQUE

def _quality(target: Target) -> float:
    """
    Args:
        target: A target.

    Returns:
        The quality of the target.
    """
    image_file = io.BytesIO(initial_bytes=target.image_value)
    image = Image.open(fp=image_file)
    image_array = numpy.asarray(a=image)
    obj = BRISQUE(url=False)
    score = obj.score(img=image_array)
    return score

class ActiveMatchingTargetsDeleteProcessing(Exception):
    """
    There is at least one active target which matches and was recently deleted.
    """


def get_query_match_response_text(
    request_headers: dict[str, str],
    request_body: bytes,
    request_method: str,
    request_path: str,
    databases: set[VuforiaDatabase],
    query_processes_deletion_seconds: int | float,
    query_recognizes_deletion_seconds: int | float,
) -> str:
    """
    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.
        query_recognizes_deletion_seconds: The number of seconds after a target
            has been deleted that the query endpoint will still recognize the
            target for.
        query_processes_deletion_seconds: The number of seconds after a target
            deletion is recognized that the query endpoint will return a 500
            response on a match.

    Returns:
        The response text for a query endpoint request.

    Raises:
        ActiveMatchingTargetsDeleteProcessing: There is at least one active
            target which matches and was recently deleted.
    """
    body_file = io.BytesIO(request_body)

    email_message = EmailMessage()
    email_message["content-type"] = request_headers["Content-Type"]
    boundary = email_message.get_boundary()
    assert isinstance(boundary, str)

    parsed = multipart.MultipartParser(stream=body_file, boundary=boundary)

    parsed_max_num_results = parsed.get("max_num_results")
    if parsed_max_num_results is None:
        max_num_results = "1"
    else:
        max_num_results = parsed_max_num_results.value

    parsed_include_target_data = parsed.get("include_target_data")
    if parsed_include_target_data is None:
        include_target_data = "top"
    else:
        include_target_data = parsed_include_target_data.value.lower()

    image_value = parsed.get("image").raw
    gmt = ZoneInfo("GMT")
    now = datetime.datetime.now(tz=gmt)

    processing_timedelta = datetime.timedelta(
        seconds=query_processes_deletion_seconds,
    )

    recognition_timedelta = datetime.timedelta(
        seconds=query_recognizes_deletion_seconds,
    )

    database = get_database_matching_client_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    assert isinstance(database, VuforiaDatabase)

    matching_targets = [
        target
        for target in database.targets
        if target.image_value == image_value
    ]

    not_deleted_matches = [
        target
        for target in matching_targets
        if target.active_flag
        and not target.delete_date
        and target.status == TargetStatuses.SUCCESS.value
    ]

    deletion_not_recognized_matches = [
        target
        for target in matching_targets
        if target.active_flag
        and target.delete_date
        and (now - target.delete_date) < recognition_timedelta
    ]

    active_matching_targets_delete_processing = [
        target
        for target in matching_targets
        if target.active_flag
        and target.delete_date
        and (now - target.delete_date)
        < (recognition_timedelta + processing_timedelta)
        and target not in deletion_not_recognized_matches
    ]

    if active_matching_targets_delete_processing:
        raise ActiveMatchingTargetsDeleteProcessing

    all_quality_matches = not_deleted_matches + deletion_not_recognized_matches
    matches = [match for match in all_quality_matches if _quality(target=match) > 0.0]

    results: list[dict[str, Any]] = []
    for target in matches:
        target_timestamp = target.last_modified_date.timestamp()
        if target.application_metadata is None:
            application_metadata = None
        else:
            application_metadata = base64.b64encode(
                decode_base64(encoded_data=target.application_metadata),
            ).decode("ascii")
        target_data = {
            "target_timestamp": int(target_timestamp),
            "name": target.name,
            "application_metadata": application_metadata,
        }

        if include_target_data == "all" or (
            include_target_data == "top" and not results
        ):
            result = {
                "target_id": target.target_id,
                "target_data": target_data,
            }
        else:
            result = {
                "target_id": target.target_id,
            }

        results.append(result)

    results = results[: int(max_num_results)]
    body = {
        "result_code": ResultCodes.SUCCESS.value,
        "results": results,
        "query_id": uuid.uuid4().hex,
    }

    return json_dump(body)
