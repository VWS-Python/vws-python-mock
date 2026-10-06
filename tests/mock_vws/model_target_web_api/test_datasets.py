"""Tests for datasets through the Model Target Web API.

Verified fake tests for State-Based Model Targets.

The advanced (signed) cases are verified against the real Vuforia
only when ``--verify-model-target-signing`` is given: see
``_SIGNED_REQUEST_SKIP_REASON``.
Additional verified and mock-only Model Target behaviors.
"""

import base64
import io
import json
import time
import zipfile
from http import HTTPStatus
from uuid import uuid4

import pytest
import requests
from beartype import beartype

from mock_vws import MockVWS, ModelTargetGenerationFailure
from mock_vws.model_target import (
    ModelTargetDataset,
    ModelTargetDatasetType,
)
from tests.mock_vws.fixtures.model_target_prepared_requests import (
    credentials_for_backend,
    get_access_token,
)
from tests.mock_vws.fixtures.vuforia_backends import (
    VERIFY_MODEL_TARGET_SIGNING_OPTION,
    VuforiaBackend,
)
from tests.mock_vws.model_target_web_api.helpers import (
    MOCK_BEARER_TOKEN,
    MODEL,
    STATE_CONFIGURATION,
    UNAUTHENTICATED_DATASET_REQUEST,
    VIEW,
    VWS_HOST,
    access_token_for_backend,
    parse_response_json,
    response_targeted_error,
    response_validation_error,
)
from tests.mock_vws.utils.assertions import (
    assert_model_target_status,
)
from tests.mock_vws.utils.model_target_retries import model_target_get


@beartype
def _dataset_request(*, cad_data_url: str) -> dict[str, object]:
    """Return a standard Model Target dataset request."""
    return {
        "name": f"dataset-{uuid4().hex}",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model-name",
                "cadDataUrl": cad_data_url,
                "views": [VIEW],
            },
        ],
    }


@beartype
def _cad_data_blob() -> str:
    """Return a base64-encoded zipped model for inline CAD data."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(file=zip_buffer, mode="w") as zip_file:
        zip_file.writestr(
            zinfo_or_arcname="model.gltf",
            data=json.dumps(obj={"asset": {"version": "2.0"}}),
        )
    return base64.b64encode(s=zip_buffer.getvalue()).decode(encoding="ascii")


@beartype
def _blob_dataset_request() -> dict[str, object]:
    """Return a standard dataset request with inline CAD data."""
    return {
        "name": f"dataset-{uuid4().hex}",
        "targetSdk": "10.18",
        "models": [
            {
                "name": "model-name",
                "cadDataBlob": _cad_data_blob(),
                "cadDataFormat": "ZIP",
                "views": [VIEW],
            },
        ],
    }


# Creating an advanced dataset with a state-based configuration or a standard
# dataset with inline CAD data is a "signed" request: the real Vuforia signs
# the trained dataset, and each signing consumes the account's allowance. The
# allowance is tiny (roughly 20 signings, under ten CI runs' worth), it
# is shared by every CI job and every concurrent run, and it cannot be
# raised or reset by us.  Verifying this behavior on every run therefore
# burns the whole allowance within hours and then turns every CI run red
# with ``TRAINING_ALLOWANCE_EXCEEDED`` - which is exactly what happened
# when it ran unconditionally.  The equivalent unsigned requests (a
# standard dataset, or an advanced dataset without a state-based
# configuration) are far cheaper and stay enabled, though with enough
# traffic they can also hit the allowance; an unexpected allowance
# rejection is reported as an expected failure by
# ``assert_model_target_status`` rather than failing the run.
_SIGNED_REQUEST_SKIP_REASON = (
    "Signed Model Target requests consume the real Vuforia account's "
    "small, shared, non-resettable training allowance, so they are not "
    "verified against the real Vuforia by default. Pass "
    f"{VERIFY_MODEL_TARGET_SIGNING_OPTION} to verify them, for example "
    "after the allowance has recovered. The mock backends always run "
    "this test."
)


def _skip_unrequested_real_signing(
    *,
    request: pytest.FixtureRequest,
    backend: VuforiaBackend,
) -> None:
    """Skip a signing request against real Vuforia unless opted in."""
    if backend is VuforiaBackend.REAL and not request.config.getoption(
        name=VERIFY_MODEL_TARGET_SIGNING_OPTION,
    ):
        pytest.skip(reason=_SIGNED_REQUEST_SKIP_REASON)


@pytest.mark.parametrize(
    argnames="dataset_path",
    argvalues=[
        pytest.param("/modeltargets/datasets", id="standard"),
        pytest.param(
            "/modeltargets/advancedDatasets",
            id="advanced",
        ),
    ],
)
@pytest.mark.parametrize(
    argnames="view_updates",
    argvalues=[
        pytest.param({}, id="all-states"),
        pytest.param(
            {"states": ["assembled"]},
            id="selected-states",
        ),
    ],
)
def test_state_based_dataset(
    *,
    request: pytest.FixtureRequest,
    verify_model_target_mock_vuforia: VuforiaBackend,
    dataset_path: str,
    view_updates: dict[str, object],
) -> None:
    """State-Based Model Target fields survive a dataset round
    trip.
    """
    _skip_unrequested_real_signing(
        request=request,
        backend=verify_model_target_mock_vuforia,
    )
    body = {
        **UNAUTHENTICATED_DATASET_REQUEST,
        "models": [
            {
                **MODEL,
                "stateBasedConfigurationJsonString": (STATE_CONFIGURATION),
                "views": [{**VIEW, **view_updates}],
            },
        ],
    }
    access_token = access_token_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    create_response = requests.post(
        url=f"{VWS_HOST}{dataset_path}",
        headers=headers,
        json=body,
        timeout=30,
    )

    assert_model_target_status(
        response=create_response,
        status_codes=HTTPStatus.CREATED,
    )
    dataset_uuid = parse_response_json(response=create_response)["uuid"]
    assert isinstance(dataset_uuid, str)
    delete_response = requests.delete(
        url=f"{VWS_HOST}{dataset_path}/{dataset_uuid}",
        headers=headers,
        timeout=30,
    )
    assert_model_target_status(
        response=delete_response,
        status_codes=HTTPStatus.OK,
    )


def test_view_states_are_a_subset(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """A view cannot select a state absent from the configuration."""
    body = {
        **UNAUTHENTICATED_DATASET_REQUEST,
        "models": [
            {
                **MODEL,
                "stateBasedConfigurationJsonString": (STATE_CONFIGURATION),
                "views": [{**VIEW, "states": ["unknown"]}],
            },
        ],
    }
    access_token = access_token_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    response = requests.post(
        url=f"{VWS_HOST}/modeltargets/datasets",
        headers={"Authorization": f"Bearer {access_token}"},
        json=body,
        timeout=30,
    )

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    error = response_validation_error(response=response)
    assert error["code"] == "BAD_REQUEST"
    assert [detail["message"] for detail in error["details"]] == [
        "states in entrypoint view-name' must be a subset of all states",
    ]
    assert error["details"][0]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    argnames=("model_updates", "view_updates", "expected_message"),
    argvalues=[
        pytest.param(
            {"stateBasedConfigurationJsonString": 1},
            {},
            (
                "/models(0)/stateBasedConfigurationJsonString: "
                "error.expected.jsstring"
            ),
            id="configuration-not-string",
        ),
        pytest.param(
            {"stateBasedConfigurationJsonString": "{"},
            {},
            (
                "/models(0)/stateBasedConfigurationJsonString: "
                "error.expected.validjson"
            ),
            id="configuration-not-json",
        ),
        pytest.param(
            {"stateBasedConfigurationJsonString": "{}"},
            {},
            (
                "/models(0)/stateBasedConfigurationJsonString/states: "
                "error.expected.jsobject"
            ),
            id="configuration-states-not-object",
        ),
        pytest.param(
            {"stateBasedConfigurationJsonString": "[]"},
            {},
            (
                "/models(0)/stateBasedConfigurationJsonString/states: "
                "error.expected.jsobject"
            ),
            id="configuration-not-object",
        ),
        pytest.param(
            {"stateBasedConfigurationJsonString": STATE_CONFIGURATION},
            {"states": "assembled"},
            "/models(0)/views(0)/states: error.expected.jsarray",
            id="view-states-not-array",
        ),
        pytest.param(
            {"stateBasedConfigurationJsonString": STATE_CONFIGURATION},
            {"states": ["assembled", 1]},
            ("/models(0)/views(0)/states(1): error.expected.jsstring"),
            id="view-state-not-string",
        ),
        pytest.param(
            {},
            {"states": ["assembled"]},
            (
                "/models(0)/stateBasedConfigurationJsonString: element "
                "is required when view states are given"
            ),
            id="view-states-without-configuration",
        ),
    ],
)
def test_invalid_state_based_dataset(
    *,
    model_target_mock_only_vuforia: VuforiaBackend,
    model_updates: dict[str, object],
    view_updates: dict[str, object],
    expected_message: str,
) -> None:
    """Invalid State-Based Model Target fields are rejected."""
    body = {
        **UNAUTHENTICATED_DATASET_REQUEST,
        "models": [
            {
                **MODEL,
                **model_updates,
                "views": [{**VIEW, **view_updates}],
            },
        ],
    }
    access_token = access_token_for_backend(
        backend=model_target_mock_only_vuforia,
    )
    response = requests.post(
        url=f"{VWS_HOST}/modeltargets/datasets",
        headers={"Authorization": f"Bearer {access_token}"},
        json=body,
        timeout=30,
    )

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    error = response_validation_error(response=response)
    assert error["code"] == "BAD_REQUEST"
    assert [detail["message"] for detail in error["details"]] == [
        expected_message,
    ]
    assert error["details"][0]["code"] == "VALIDATION_ERROR"


def test_advanced_realistic_appearance_not_in_enum(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """Advanced dataset requests with a ``realisticAppearance`` value
    outside the documented enumeration are rejected.

    The Model Target OpenAPI specification documents
    ``realisticAppearance`` as a model field for advanced datasets
    only.
    """
    credentials = credentials_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    body = {
        **UNAUTHENTICATED_DATASET_REQUEST,
        "models": [
            {
                **MODEL,
                "cadDataUrl": credentials.cad_data_url,
                "realisticAppearance": "yes",
            },
        ],
    }
    access_token = get_access_token(
        credentials=credentials,
        backend=verify_model_target_mock_vuforia,
    )
    advanced_response = requests.post(
        url=f"{VWS_HOST}/modeltargets/advancedDatasets",
        headers={"Authorization": f"Bearer {access_token}"},
        json=body,
        timeout=30,
    )

    assert_model_target_status(
        response=advanced_response,
        status_codes=HTTPStatus.BAD_REQUEST,
    )
    error = response_validation_error(response=advanced_response)
    assert error["code"] == "BAD_REQUEST"
    assert [detail["message"] for detail in error["details"]] == [
        '`realisticAppearance` must be one of "true", "false", "auto".` ',
    ]
    assert error["details"][0]["code"] == "VALIDATION_ERROR"


def test_oauth2_token_body_not_utf_8(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """An OAuth2 token request with a body which is not valid UTF-8 is
    treated as one which does not name a grant type.

    Real Vuforia also treats a body that cannot be decoded as an empty
    form.
    """
    credentials = credentials_for_backend(
        backend=verify_model_target_mock_vuforia,
    )

    response = requests.post(
        url=f"{VWS_HOST}/oauth2/token",
        auth=(credentials.client_id, credentials.client_secret),
        data=b"\xff",
        timeout=30,
    )

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.OK,
    )
    assert response.json()["token_type"] == "bearer"


def test_processing_dataset_cannot_be_downloaded() -> None:
    """A dataset cannot be downloaded while it is still processing.

    Mock-only because exercising this against real Vuforia would require
    creating a dataset on every test run; the mock lets us drive the
    processing window deterministically.
    """
    with MockVWS(processing_time_seconds=60):
        create_response = requests.post(
            url=f"{VWS_HOST}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            json=UNAUTHENTICATED_DATASET_REQUEST,
            timeout=30,
        )
        dataset_uuid = parse_response_json(response=create_response)["uuid"]
        assert isinstance(dataset_uuid, str)
        response = requests.get(
            url=(f"{VWS_HOST}/modeltargets/datasets/{dataset_uuid}/dataset"),
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            timeout=30,
        )

    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.UNPROCESSABLE_ENTITY,
    )
    error = response_targeted_error(response=response)
    assert error["code"] == "UNSUPPORTED_STATE"
    assert error["message"] == (
        f"Training status for dataset {dataset_uuid} is not-started != done"
    )
    assert error["target"] == dataset_uuid


def test_failed_dataset_cannot_be_downloaded() -> None:
    """A dataset which failed generation cannot be downloaded, and the
    error reports the failed training status rather than the
    ``not-started`` status which a still-processing dataset reports.

    Mock-only because a generation failure cannot be provoked on demand
    against real Vuforia, so the training status name it reports for a
    failed dataset has not been observed.
    """
    failure = ModelTargetGenerationFailure(message="CAD model is invalid")
    with MockVWS(
        processing_time_seconds=0,
        model_target_generation_failure=failure,
    ):
        create_response = requests.post(
            url=f"{VWS_HOST}/modeltargets/datasets",
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            json=UNAUTHENTICATED_DATASET_REQUEST,
            timeout=30,
        )
        dataset_uuid = parse_response_json(response=create_response)["uuid"]
        assert isinstance(dataset_uuid, str)
        status_response = requests.get(
            url=f"{VWS_HOST}/modeltargets/datasets/{dataset_uuid}/status",
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            timeout=30,
        )
        response = requests.get(
            url=(f"{VWS_HOST}/modeltargets/datasets/{dataset_uuid}/dataset"),
            headers={"Authorization": f"Bearer {MOCK_BEARER_TOKEN}"},
            timeout=30,
        )

    assert status_response.json()["status"] == "failed"
    assert_model_target_status(
        response=response,
        status_codes=HTTPStatus.UNPROCESSABLE_ENTITY,
    )
    error = response_targeted_error(response=response)
    assert error["code"] == "UNSUPPORTED_STATE"
    assert error["message"] == (
        f"Training status for dataset {dataset_uuid} is failed != done"
    )
    assert error["target"] == dataset_uuid


@pytest.mark.parametrize(
    argnames=("created_path", "other_path"),
    argvalues=[
        pytest.param(
            "/modeltargets/datasets",
            "/modeltargets/advancedDatasets",
            id="standard-dataset-via-advanced-routes",
        ),
        pytest.param(
            "/modeltargets/advancedDatasets",
            "/modeltargets/datasets",
            id="advanced-dataset-via-standard-routes",
        ),
    ],
)
def test_dataset_is_visible_to_the_other_dataset_type(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
    created_path: str,
    other_path: str,
) -> None:
    """Standard and advanced routes share datasets by UUID."""
    access_token = access_token_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    create_response = requests.post(
        url=f"{VWS_HOST}{created_path}",
        headers=headers,
        json=_dataset_request(
            cad_data_url=credentials_for_backend(
                backend=verify_model_target_mock_vuforia,
            ).cad_data_url,
        ),
        timeout=30,
    )
    assert_model_target_status(
        response=create_response,
        status_codes=HTTPStatus.CREATED,
    )
    dataset_uuid: object = create_response.json()["uuid"]
    assert isinstance(dataset_uuid, str)

    try:
        other_status_response = model_target_get(
            url=f"{VWS_HOST}{other_path}/{dataset_uuid}/status",
            headers=headers,
            timeout=30,
        )
        other_delete_response = requests.delete(
            url=f"{VWS_HOST}{other_path}/{dataset_uuid}",
            headers=headers,
            timeout=30,
        )
        own_status_response = model_target_get(
            url=(
                f"{VWS_HOST}{created_path}/"
                f"{create_response.json()['uuid']}/status"
            ),
            headers=headers,
            timeout=30,
        )
    finally:
        delete_response = requests.delete(
            url=f"{VWS_HOST}{created_path}/{dataset_uuid}",
            headers=headers,
            timeout=30,
        )
        assert_model_target_status(
            response=delete_response,
            status_codes={
                HTTPStatus.OK,
                HTTPStatus.NO_CONTENT,
            },
        )

    assert_model_target_status(
        response=other_status_response,
        status_codes=HTTPStatus.OK,
    )
    assert_model_target_status(
        response=other_delete_response,
        status_codes={
            HTTPStatus.OK,
            HTTPStatus.NO_CONTENT,
        },
    )
    assert_model_target_status(
        response=own_status_response,
        status_codes=HTTPStatus.OK,
    )


def test_create_status_and_delete(
    *,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """A standard dataset works through the shared advanced routes.

    Standard generation is fast enough for verified CI coverage. Real
    Vuforia exposes its completed artifact through both route families,
    so this also verifies the advanced status and download endpoints.
    """
    credentials = credentials_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    access_token = get_access_token(
        credentials=credentials,
        backend=verify_model_target_mock_vuforia,
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    create_response = requests.post(
        url=f"{VWS_HOST}/modeltargets/datasets",
        headers=headers,
        json=_dataset_request(cad_data_url=credentials.cad_data_url),
        timeout=30,
    )

    assert_model_target_status(
        response=create_response,
        status_codes=HTTPStatus.CREATED,
    )
    create_response_json = parse_response_json(response=create_response)
    dataset_uuid: object = create_response_json["uuid"]
    assert isinstance(dataset_uuid, str)

    try:
        status_response = model_target_get(
            url=(
                f"{VWS_HOST}/modeltargets/advancedDatasets/"
                f"{dataset_uuid}/status"
            ),
            headers=headers,
            timeout=30,
        )

        assert_model_target_status(
            response=status_response,
            status_codes=HTTPStatus.OK,
        )
        status_response_json = parse_response_json(response=status_response)
        assert status_response_json["status"] in {
            "processing",
            "done",
            "failed",
        }
        assert isinstance(status_response_json["createdAt"], str)

        deadline = time.monotonic() + 60
        while (
            status_response_json["status"] == "processing"
            and time.monotonic() < deadline
        ):
            time.sleep(1)
            status_response = model_target_get(
                url=(
                    f"{VWS_HOST}/modeltargets/advancedDatasets/"
                    f"{dataset_uuid}/status"
                ),
                headers=headers,
                timeout=30,
            )
            assert_model_target_status(
                response=status_response,
                status_codes=HTTPStatus.OK,
            )
            status_response_json = status_response.json()

        assert status_response_json["status"] == "done"
        assert isinstance(status_response_json["completedAt"], str)
        assert set(status_response_json) == {
            "completedAt",
            "createdAt",
            "status",
            "uuid",
        }

        download_response = model_target_get(
            url=(
                f"{VWS_HOST}/modeltargets/advancedDatasets/"
                f"{dataset_uuid}/dataset"
            ),
            headers=headers,
            timeout=30,
        )
        assert_model_target_status(
            response=download_response,
            status_codes=HTTPStatus.OK,
        )
        assert download_response.headers["Content-Type"] == ("application/zip")
        assert download_response.headers["Content-Disposition"] == (
            "attachment; filename=full-dataset.zip"
        )
        with zipfile.ZipFile(
            file=io.BytesIO(initial_bytes=download_response.content),
        ) as archive:
            assert archive.namelist() == ["MTDataset.dat", "MTDataset.xml"]
    finally:
        delete_response = requests.delete(
            url=f"{VWS_HOST}/modeltargets/datasets/{dataset_uuid}",
            headers=headers,
            timeout=30,
        )
        assert_model_target_status(
            response=delete_response,
            status_codes={
                HTTPStatus.OK,
                HTTPStatus.NO_CONTENT,
            },
        )


def test_create_with_cad_data_blob(
    *,
    request: pytest.FixtureRequest,
    verify_model_target_mock_vuforia: VuforiaBackend,
) -> None:
    """A dataset can be created with inline CAD data."""
    _skip_unrequested_real_signing(
        request=request,
        backend=verify_model_target_mock_vuforia,
    )
    credentials = credentials_for_backend(
        backend=verify_model_target_mock_vuforia,
    )
    access_token = get_access_token(
        credentials=credentials,
        backend=verify_model_target_mock_vuforia,
    )
    headers = {"Authorization": f"Bearer {access_token}"}

    create_response = requests.post(
        url=f"{VWS_HOST}/modeltargets/datasets",
        headers=headers,
        json=_blob_dataset_request(),
        timeout=30,
    )

    assert_model_target_status(
        response=create_response,
        status_codes=HTTPStatus.CREATED,
    )
    create_response_json = parse_response_json(response=create_response)
    dataset_uuid = create_response_json["uuid"]
    assert isinstance(dataset_uuid, str)

    # There is nothing to assert between creating and deleting the
    # dataset, so the delete does not need a ``finally`` block to avoid
    # leaving a dataset behind on real Vuforia.
    delete_response = requests.delete(
        url=f"{VWS_HOST}/modeltargets/datasets/{dataset_uuid}",
        headers=headers,
        timeout=30,
    )
    assert_model_target_status(
        response=delete_response,
        status_codes={
            HTTPStatus.OK,
            HTTPStatus.NO_CONTENT,
        },
    )


@pytest.mark.parametrize(
    argnames=("processing_time_seconds", "status", "time_field"),
    argvalues=[
        pytest.param(3600.0, "processing", "eta", id="processing"),
        pytest.param(0.0, "done", "completedAt", id="done"),
    ],
)
def test_status_uses_matching_time_field(
    *,
    processing_time_seconds: float,
    status: str,
    time_field: str,
) -> None:
    """Each status includes only its matching timestamp field."""
    dataset = ModelTargetDataset(
        request_body={},
        dataset_type=ModelTargetDatasetType.STANDARD,
        processing_time_seconds=processing_time_seconds,
        generation_failure=None,
        generation_warning=None,
        uuid_="dataset-uuid",
    )

    body = dataset.status_body()

    assert body["status"] == status
    assert body["uuid"] == "dataset-uuid"
    assert {"eta", "completedAt"} & body.keys() == {time_field}
