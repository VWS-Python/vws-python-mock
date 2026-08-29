"""Tools for making Vuforia queries."""

import base64
import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from beartype import beartype

from mock_vws._base64_decoding import decode_base64
from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_client_keys
from mock_vws._mock_common import json_dump, sorted_targets
from mock_vws._query_validators.multipart import parse_multipart
from mock_vws.database import CloudDatabase
from mock_vws.image_matchers import ImageMatcher


@beartype
def get_query_match_response_text(
    *,
    request_headers: Mapping[str, str],
    request_body: bytes,
    request_method: str,
    request_path: str,
    databases: Iterable[CloudDatabase],
    query_match_checker: ImageMatcher,
) -> str:
    """
    Args:
        request_path: The path of the request.
        request_headers: The headers sent with the request.
        request_body: The body of the request.
        request_method: The HTTP method of the request.
        databases: All Vuforia databases.
        query_match_checker: A callable which takes two image values and
            returns whether they match.

    Returns:
        The response text for a query endpoint request.
    """
    fields, files = parse_multipart(
        request_headers=request_headers,
        request_body=request_body,
    )

    max_num_results = fields.get(key="max_num_results", default="1")
    include_target_data = fields.get(
        key="include_target_data",
        default="top",
    ).lower()

    image_part = files["image"]
    image_value = image_part.stream.read()

    database = get_database_matching_client_keys(
        request_headers=request_headers,
        request_body=request_body,
        request_method=request_method,
        request_path=request_path,
        databases=databases,
    )

    matching_targets = [
        target
        for target in sorted_targets(targets=database.targets)
        if query_match_checker(
            first_image_content=target.image_value,
            second_image_content=image_value,
        )
    ]

    not_deleted_matches = [
        target
        for target in matching_targets
        if target.active_flag
        # In the real Vuforia, targets which have just
        # been deleted may still get recognized.
        # We document this difference in ``differences-to-vws.rst``.
        and not target.delete_date
        and target.status == TargetStatuses.SUCCESS.value
    ]

    all_quality_matches = not_deleted_matches
    minimum_rating = 0
    matches = [
        match
        for match in all_quality_matches
        if match.tracking_rating > minimum_rating
    ]

    results: list[dict[str, Any]] = []
    for target in matches:
        target_timestamp = target.last_modified_date.timestamp()
        if target.application_metadata is None:
            application_metadata = None
        else:
            application_metadata = base64.b64encode(
                s=decode_base64(encoded_data=target.application_metadata),
            ).decode(encoding="ascii")
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

    return json_dump(body=body)
