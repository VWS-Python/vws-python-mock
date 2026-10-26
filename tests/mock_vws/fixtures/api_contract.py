"""Shared API fixtures supplied independently of backend adapters."""

import base64
import binascii
import contextlib
import io
import uuid
from dataclasses import dataclass

import pytest
from beartype import beartype
from tenacity import retry
from tenacity.retry import retry_if_not_result
from tenacity.stop import stop_after_attempt
from vws import VWS, CloudRecoService
from vws.exceptions.custom_exceptions import TargetProcessingTimeoutError
from vws.exceptions.vws_exceptions import (
    TargetStatusProcessingError,
    UnknownTargetError,
)
from vws.reports import TargetStatusAndRecord, TargetStatuses

from tests.mock_vws.fixtures.credentials import CloudDatabaseCredentials
from tests.mock_vws.utils import Endpoint, ModelTargetEndpoint
from tests.mock_vws.utils.retries import (
    RETRY_ON_TARGET_NOT_YET_VISIBLE,
    TRANSIENT_VWS_EXCEPTIONS,
    retry_transient_vws_failures,
)

# The number of targets to add before giving up on getting one which
# processes with a 'success' status.
_TARGET_SUCCESS_ATTEMPTS = 3


@pytest.fixture(name="vws_client")
def fixture_vws_client(
    *,
    vuforia_database: CloudDatabaseCredentials,
    base_vws_url: str,
    vws_client_class: type[VWS],
) -> VWS:
    """A VWS client for an active VWS database."""
    return vws_client_class(
        server_access_key=vuforia_database.server_access_key,
        server_secret_key=vuforia_database.server_secret_key,
        base_vws_url=base_vws_url,
    )


@pytest.fixture
def cloud_reco_client(
    *,
    vuforia_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> CloudRecoService:
    """A query client for an active VWS database."""
    return CloudRecoService(
        client_access_key=vuforia_database.client_access_key,
        client_secret_key=vuforia_database.client_secret_key,
        base_vwq_url=base_vwq_url,
    )


@pytest.fixture(name="inactive_vws_client")
def fixture_inactive_vws_client(
    *,
    inactive_cloud_database: CloudDatabaseCredentials,
    base_vws_url: str,
) -> VWS:
    """A client for an inactive VWS database."""
    return VWS(
        server_access_key=inactive_cloud_database.server_access_key,
        server_secret_key=inactive_cloud_database.server_secret_key,
        base_vws_url=base_vws_url,
    )


@pytest.fixture
def inactive_cloud_reco_client(
    *,
    inactive_cloud_database: CloudDatabaseCredentials,
    base_vwq_url: str,
) -> CloudRecoService:
    """A query client for an inactive VWS database."""
    return CloudRecoService(
        client_access_key=inactive_cloud_database.client_access_key,
        client_secret_key=inactive_cloud_database.client_secret_key,
        base_vwq_url=base_vwq_url,
    )


@beartype
@retry_transient_vws_failures
def _add_target(*, vws_client: VWS, image: io.BytesIO) -> str:
    """Add a target, which is then in the processing state.

    We retry on transient failures here because pytest-retry does not
    retry on exceptions raised in fixtures.

    See
    https://github.com/str0zzapreti/pytest-retry/issues/33.

    Returns:
        The ID of the added target.
    """
    return vws_client.add_target(
        name=uuid.uuid4().hex,
        width=1,
        image=image,
        active_flag=True,
        application_metadata=None,
    )


@beartype
@retry_transient_vws_failures
@RETRY_ON_TARGET_NOT_YET_VISIBLE
def _get_processed_target(
    *, vws_client: VWS, target_id_: str
) -> TargetStatusAndRecord:
    """Wait for and read a known target without repeating its creation.

    Real Vuforia sometimes reports a target which it has just created as
    unknown, because the target is not yet visible to the read path. We know
    the target exists, because Vuforia gave us its ID, so we retry rather
    than fail.
    """
    vws_client.wait_for_target_processed(target_id=target_id_)
    return vws_client.get_target_record(target_id=target_id_)


@dataclass(frozen=True, kw_only=True)
class _TargetProcessingResult:
    """The ID and processing status of an uploaded target."""

    target_id: str
    status: TargetStatuses


@beartype
def _target_processed_successfully(result: _TargetProcessingResult) -> bool:
    """Return whether an uploaded target finished processing
    successfully.
    """
    return result.status == TargetStatuses.SUCCESS


@beartype
@retry(
    retry=retry_if_not_result(predicate=_target_processed_successfully),
    stop=stop_after_attempt(max_attempt_number=_TARGET_SUCCESS_ATTEMPTS),
    reraise=True,
)
def _add_target_which_processed_successfully(
    *,
    vws_client: VWS,
    image: io.BytesIO,
) -> _TargetProcessingResult:
    """Add a target which finishes processing with a 'success' status.

    Real Vuforia sometimes rates the given image badly enough to give the
    target a 'failed' status, so we delete such a target and add another
    one.

    Returns:
        The ID and processing status of the added target.
    """
    target_id_ = _add_target(vws_client=vws_client, image=image)
    try:
        target_details = _get_processed_target(
            vws_client=vws_client,
            target_id_=target_id_,
        )
    except (
        *TRANSIENT_VWS_EXCEPTIONS,
        UnknownTargetError,
        TargetProcessingTimeoutError,
    ):  # pragma: no cover
        # Setup owns the target until it can return it to the test. Cleanup
        # is best effort: transient failures, a processing target, or one
        # already gone must not hide the setup error.
        # The real adapter also clears remaining targets before the next test.
        with contextlib.suppress(
            *TRANSIENT_VWS_EXCEPTIONS,
            TargetStatusProcessingError,
            UnknownTargetError,
        ):
            vws_client.delete_target(target_id=target_id_)
        raise
    # Failed processing is nondeterministic against the live service.
    if target_details.status != TargetStatuses.SUCCESS:
        vws_client.delete_target(target_id=target_id_)  # pragma: no cover
    return _TargetProcessingResult(
        target_id=target_id_,
        status=target_details.status,
    )


@pytest.fixture
def target_id(*, high_quality_image: io.BytesIO, vws_client: VWS) -> str:
    """Return the target ID of a target in the database which has finished
    processing with a 'success' status.

    We use ``high_quality_image`` rather than
    ``image_file_success_state_low_rating``. The latter is a randomly
    generated 5x5 image, and real Vuforia often gives such an image a
    'failed' status. No test which uses this fixture needs a low rating.
    """
    result = _add_target_which_processed_successfully(
        vws_client=vws_client,
        image=high_quality_image,
    )
    return result.target_id


@pytest.fixture
def unprocessed_target_id(
    *,
    high_quality_image: io.BytesIO,
    vws_client: VWS,
) -> str:
    """Return the target ID of a target which was just added to the
    database.

    The target is in the processing state, or it has just left it. Use
    this rather than ``target_id`` for tests which do not need a
    processed target, as waiting for processing is slow against real
    Vuforia.
    """
    return _add_target(vws_client=vws_client, image=high_quality_image)


@pytest.fixture(
    params=[
        "add_target",
        "database_summary",
        "delete_target",
        "get_duplicates",
        "get_target",
        "target_list",
        "target_summary",
        "update_target",
        "query",
        "vumark_generate_instance",
        "reco_counts_report",
    ],
)
def endpoint(*, request: pytest.FixtureRequest) -> Endpoint:
    """
    Return details of an endpoint for the Target API or the Query
    API.

    The reco counts report download endpoint is not included because it
    deliberately takes no authorization, standing in for a presigned URL, so
    the cross-cutting ``Authorization`` and ``Date`` header concerns do not
    apply to it.
    """
    fixture_name = request.param
    assert isinstance(fixture_name, str)
    endpoint_fixture = request.getfixturevalue(argname=fixture_name)
    assert isinstance(endpoint_fixture, Endpoint)
    return endpoint_fixture


@pytest.fixture(
    params=[
        "create_standard_dataset",
        "create_advanced_dataset",
        "standard_dataset_status",
        "advanced_dataset_status",
        "download_standard_dataset",
        "download_advanced_dataset",
        "delete_standard_dataset",
        "delete_advanced_dataset",
    ],
)
def model_target_endpoint(
    *,
    request: pytest.FixtureRequest,
) -> ModelTargetEndpoint:
    """Return details of an endpoint for the Model Target Web API.

    The OAuth2 token endpoint is not included because it takes HTTP Basic
    credentials rather than a bearer token, so the cross-cutting bearer
    token concerns do not apply to it.
    """
    fixture_name = request.param
    assert isinstance(fixture_name, str)
    endpoint_fixture = request.getfixturevalue(argname=fixture_name)
    assert isinstance(endpoint_fixture, ModelTargetEndpoint)
    return endpoint_fixture


@pytest.fixture(
    params=[
        pytest.param(
            "abcde",
            id="Length is one more than a multiple of four.",
        ),
        pytest.param(
            # We choose XN because it is different when decoded then encoded:
            #
            #
            # prints ``XA==``.
            "XN",
            id="Length is two more than a multiple of four.",
        ),
        pytest.param(
            "XNA",
            id="Length is three more than a multiple of four.",
        ),
    ],
)
def not_base64_encoded_processable(*, request: pytest.FixtureRequest) -> str:
    """Return a string which is not decodable as base64 data, but Vuforia
    will
    respond as if this is valid base64 data.

    ``UNPROCESSABLE_ENTITY`` when this is given.
    """
    not_base64_encoded_string = request.param
    assert isinstance(not_base64_encoded_string, str)

    with pytest.raises(expected_exception=binascii.Error):
        _ = base64.b64decode(s=not_base64_encoded_string, validate=True)

    return not_base64_encoded_string


@pytest.fixture(
    params=[
        pytest.param(
            'aaa"',
            id="Includes a character which is not a base64 digit.",
        ),
        pytest.param('"', id="Not a base64 character."),
    ],
)
def not_base64_encoded_not_processable(
    *,
    request: pytest.FixtureRequest,
) -> str:
    """
    Return a string which is not decodable as base64 data, and Vuforia
    will
    return an ``UNPROCESSABLE_ENTITY`` response when this is given.
    """
    not_base64_encoded_string = request.param
    assert isinstance(not_base64_encoded_string, str)

    with pytest.raises(expected_exception=binascii.Error):
        _ = base64.b64decode(s=not_base64_encoded_string, validate=True)

    return not_base64_encoded_string
