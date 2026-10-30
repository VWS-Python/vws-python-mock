Differences between the mock and the real Vuforia Web Services
==============================================================

The mock attempts to be realistic, but it was built without access to the source code of the original API.
Please report any issues `here <https://github.com/VWS-Python/vws-python-mock/issues>`__.

Configurable Model Target failures
----------------------------------

Use :paramref:`mock_vws.MockVWS.model_target_failure_response` to return a particular HTTP failure from selected Model Target dataset request phases.
The OAuth2 token request is still handled normally, so this exercises client behavior after successful token acquisition::

    from mock_vws import (
        MockVWS,
        ModelTargetFailureResponse,
        ModelTargetRequest,
    )

    failure = ModelTargetFailureResponse(
        status_code=503,
        headers={"Content-Type": "text/plain", "Retry-After": "10"},
        body=b"Temporarily unavailable",
        requests=frozenset({ModelTargetRequest.STATUS}),
    )

    with MockVWS(model_target_failure_response=failure):
        # Model Target status calls return the configured response.
        ...

Omit ``requests`` to affect create, status, download, and delete requests.
Other phases retain their normal behavior.
This configuration works with the in-process ``requests``, ``httpx`` and ``httpx2`` backends and is not supported by the Flask/Docker backend.

VuMark instance images
----------------------

The mock returns a fixed minimal image in the requested format.
The ``instance_id`` value is not encoded into the response image.
Real Vuforia encodes the instance ID into the VuMark pattern.

Model Target datasets
---------------------

The Model Target Web API mock supports OAuth2 token requests, standard and advanced dataset creation, status polling, dataset downloads, and deletion.
The generated dataset download is a small valid ``full-dataset.zip`` with the same ``MTDataset.dat`` and ``MTDataset.xml`` filenames as Vuforia.
Its contents are synthetic request metadata and minimal XML, not a real Vuforia Engine Model Target dataset.
Use :paramref:`mock_vws.MockVWS.model_target_generation_failure` to make in-process Model Target datasets finish with a ``failed`` status and an ``error`` object.
The failure is returned after the configured :paramref:`~mock_vws.MockVWS.processing_time_seconds`, so callers can test both processing and failed states.
This configuration is not supported by the Flask/Docker backend.
Use :paramref:`mock_vws.MockVWS.model_target_training_allowance_exceeded` to make in-process Model Target dataset creation return Vuforia's ``TRAINING_ALLOWANCE_EXCEEDED`` response.
Set the ``MODEL_TARGET_TRAINING_ALLOWANCE_EXCEEDED`` environment variable to ``true`` to configure the same response in the Flask/Docker backend. Use :paramref:`mock_vws.MockVWS.model_target_generation_warning` to make successful in-process Model Target datasets include a Vuforia-shaped ``warning`` object after processing completes. This configuration is not supported by the Flask/Docker backend.
Model Target API routes require a three-part JSON Web Token with JSON object header and payload parts, a non-``none`` ``alg`` value, and a non-empty base64url-encoded signature, such as the token returned by the mock OAuth2 route.
The mock does not verify token signatures, payload claims such as expiry, or token revocation.
The OAuth2 route supports both the ``client_credentials`` and ``password`` grants.
Tokens returned by the mock contain explicit scopes, and standard and advanced dataset routes require their corresponding Model Target scope.
A token carrying ``modeltargets.all`` can access both route families.
The OAuth2 client-credentials management routes support creating, listing, updating and deleting credentials, including Vuforia's limit of 100 created credentials per account.

Dataset creation request bodies which are valid JSON but not JSON objects are reported as missing every required top-level field.
Dataset creation request bodies which cannot be decoded as UTF-8 are reported as invalid JSON, as malformed JSON bodies are.
An OAuth2 token request body which cannot be decoded as UTF-8 is treated as one which does not name a grant type.
Dataset creation requests are validated for the required top-level ``models``, ``name`` and ``targetSdk`` fields, for those fields' types, for each ``models`` entry being a JSON object, and for the number of models.
Each model is validated for the required ``name`` field, for exactly one of ``cadDataUrl`` and ``cadDataBlob`` being given, for the types of the ``automaticColoring``, ``cadDataBlob``, ``cadDataFormat``, ``cadDataUrl``, ``motionHint``, ``name``, ``optimizeTrackingFor``, ``simplify`` and ``trackingMode`` fields, for each of the ``automaticColoring``, ``cadDataFormat``, ``motionHint``, ``optimizeTrackingFor``, ``simplify`` and ``trackingMode`` fields being one of the values which the Model Target OpenAPI specification documents for it when the field is given, and for ``views`` being a JSON array when it is given.
The optional ``stateBasedConfigurationJsonString`` field must be a string containing a JSON object with a ``states`` object.
The ``realisticAppearance`` model field is validated in the same way for advanced datasets; the OpenAPI specification does not document it as a standard dataset model field, so standard dataset creation does not validate it.
Each ``views`` entry is validated for being a JSON object, for the required ``name`` field, and for the types of ``name`` and the optional ``guideViewPosition`` field.
State-Based Model Target views require ``guideViewPosition``, matching real Vuforia.
An optional ``states`` field must be an array of strings.
Each named state must be declared by the model's ``stateBasedConfigurationJsonString``.
Omitting the field makes the view available to every configured state.
Each ``guideViewPosition`` object is validated for the required ``rotation`` and ``translation`` fields, for those fields being JSON arrays, and for the elements of those arrays being JSON numbers.
The mock does not validate the contents of each model further, such as whether ``cadDataUrl`` values are reachable, whether ``cadDataBlob`` values are valid base64-encoded archives of the named ``cadDataFormat``, whether ``cadDataFormat`` is given alongside ``cadDataBlob``, the lengths of ``rotation`` and ``translation`` arrays, or ``targetSdk`` version numbers.
It also does not validate the state configuration beyond its top-level ``states`` object.

For unknown Model Target datasets, the mock returns an error whose ``target`` is ``userId:mock``.
Real Vuforia uses ``userId:<numeric-user-id>`` where the numeric portion is per-account.

Standard and advanced routes share datasets by UUID.
Access to each route family is separated by its corresponding OAuth scope.

Some Model Target Web API paths remain mock-only in ``tests/mock_vws/model_target_web_api``.
Downloads of still-processing datasets are mock-only because exercising the path against real Vuforia would require creating a dataset on every test run.
The mock drives the processing window deterministically.
A download request for a dataset which is not ready reports the dataset's training status.
The mock reports ``not-started`` for the whole processing window, as real Vuforia does for a dataset which was just created, and ``failed`` for a dataset whose generation failed.

.. admonition:: Unverified assumption

   :ref:`unverified-model-target-failed-dataset-name`

Some malformed State-Based Model Target configuration documents remain mock-only because real Vuforia returns an internal server error for them.
