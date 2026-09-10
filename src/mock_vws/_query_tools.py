"""Tools for making Vuforia queries."""

import base64
import uuid

from beartype import beartype

from mock_vws._base64_decoding import decode_base64
from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._matching import matching_targets
from mock_vws._mock_common import json_dump
from mock_vws._query_validators import ValidatedQuery
from mock_vws.image_matchers import ImageMatcher
from mock_vws.model_target import JSONValue


@beartype
def get_query_match_response_text(
    *,
    validated_query: ValidatedQuery,
    query_match_checker: ImageMatcher,
) -> str:
    """
    Args:
        validated_query: The database and the parsed body which the query
            validators resolved the request to.
        query_match_checker: A callable which takes two image values and
            returns a match score, or ``None`` if they do not match.

    Returns:
        The response text for a query endpoint request.
    """
    fields = validated_query.form.fields
    max_num_results = fields.get("max_num_results", "1")
    include_target_data = fields.get("include_target_data", "top").lower()
    image_value = validated_query.form.files["image"]
    database = validated_query.database

    matches_best_first = matching_targets(
        matcher=query_match_checker,
        image_content=image_value,
        targets=database.targets,
    )

    not_deleted_matches = [
        target
        for target in matches_best_first
        if target.active_flag
        # In the real Vuforia, targets which have just
        # been deleted may still get recognized.
        # We document this difference in ``differences-to-vws.rst``.
        and not bool(target.delete_date)
        and target.status == TargetStatuses.SUCCESS.value
    ]

    all_quality_matches = not_deleted_matches
    minimum_rating = 0
    matches = [
        match
        for match in all_quality_matches
        if match.tracking_rating > minimum_rating
    ]

    results: list[JSONValue] = []
    for target in matches:
        target_timestamp = target.last_modified_date.timestamp()
        if target.application_metadata is None:
            application_metadata = None
        else:
            application_metadata = base64.b64encode(
                s=decode_base64(encoded_data=target.application_metadata),
            ).decode(encoding="ascii")
        target_data: dict[str, JSONValue] = {
            "target_timestamp": int(target_timestamp),
            "name": target.name,
            "application_metadata": application_metadata,
        }

        result: dict[str, JSONValue] = {
            "target_id": target.target_id,
        }
        if include_target_data == "all" or (
            include_target_data == "top" and not bool(results)
        ):
            result["target_data"] = target_data

        results.append(result)

    results = results[: int(max_num_results)]
    body: dict[str, JSONValue] = {
        "result_code": ResultCodes.SUCCESS.value,
        "results": results,
        "query_id": uuid.uuid4().hex,
    }

    return json_dump(body=body)
