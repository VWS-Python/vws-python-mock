Differences between the mock and the real Vuforia Web Services
==============================================================

The mock attempts to be realistic, but it was built without access to the source code of the original API.
Please report any issues `here <https://github.com/VWS-Python/vws-python-mock/issues>`__.

This document mixes three kinds of statement, and it says which is which:

* A deliberate difference, where the mock does something else on purpose.
  The image matchers are one.
* Behavior which the mock does not implement.
* An unverified assumption, where the mock follows Vuforia's documentation and nobody has checked that the documentation is accurate.
  Each of these carries a note pointing at its entry in :doc:`unverified-behavior`, which says what would verify it.
  These are the ones which can bite: the mock passes its tests, your tests pass, and the divergence appears in production.

Image matching
--------------

Vuforia's image matching is proprietary and we do not intend to accurately copy it.
Instead, we aim for simple algorithms which are fast and are good enough for testing purposes.
The image matchers are configurable, using :paramref:`~mock_vws.MockVWS.query_match_checker` and :paramref:`~mock_vws.MockVWS.duplicate_match_checker`.

Speed and summary accuracy
--------------------------

The mock responds much more quickly than the real Vuforia Web Services.

Targets in the mock are set to 'processing' for half a second by default.
This is customizable, with the :paramref:`~mock_vws.MockVWS.processing_time_seconds` parameter.
In the real Vuforia Web Services, the processing stage takes varying lengths of time.

The database summary in the real Vuforia Web Services takes some time to account for images and recognitions.
Sometimes the real summary skips image states such as the processing state.
The mock is accurate immediately with regards to images.

The mock does not count recognitions.
Real Vuforia's recognition counts lag behind its queries by far longer than a
test runs, so a query in the mock does not change any count either.
Set the counts you want to see instead:
:paramref:`mock_vws.database.CloudDatabase.total_recos`,
:paramref:`mock_vws.database.CloudDatabase.current_month_recos`,
:paramref:`mock_vws.database.CloudDatabase.previous_month_recos` and
:paramref:`mock_vws.database.CloudDatabase.reco_threshold` for the database
summary report, and
:meth:`mock_vws.MockVWS.set_target_recognition_counts` for the counts of a
target, which the target summary report and the reco counts report show.
Targets are created by API requests, so their counts are set after the target
is created.
The Flask and Docker mock has an equivalent target manager endpoint, described
in :doc:`docker`.

Image quality and ratings
-------------------------

Targets are assigned a rating between 0 and 5 of how good they are for tracking purposes.
In the mock this is calculated from the image quality, differently to how Vuforia does this.
This is customizable with the :paramref:`~mock_vws.MockVWS.target_tracking_rater` parameter.

A target which is being processed after an upload reports a rating of -1 for a short time, and then the image's rating, while it is still processing.
An update does not start a new -1 window: it returns the target to the processing state and reports the new image's rating straight away.
The mock does the same, in proportion to :paramref:`~mock_vws.MockVWS.processing_time_seconds` rather than to the real timings.

Image targets which are not suited to detection are given 'failed' statuses.
The criteria for these images is not defined by the Vuforia documentation.
The mock is more forgiving than the real Vuforia Web Services.
Therefore, an image given a 'success' status by the mock may not be given a 'success' status by the real Vuforia Web Services.

Result ordering
---------------

The real Query API orders results by match score, with the best match first.
The mock does the same, with the score which its image matcher gives each match.
That matcher is not Vuforia's, so the mock's ranking is not Vuforia's ranking.
The order decides which results survive ``max_num_results``, and which result gets target data with ``include_target_data=top``.

Matches with the same score, which is every match of :class:`~mock_vws.image_matchers.ExactMatcher`, are ordered by upload date and then by target ID.
The real Vuforia Web Services give no such guarantee.

``GET /duplicates/{target_id}`` is ordered by match score too, and ``GET /targets`` by upload date and then by target ID.
The real Vuforia Web Services do not document an order for those endpoints.

Matching recently deleted targets
---------------------------------

Vuforia may match targets which have been deleted within the last few seconds.
In the mock, targets are not matched after they have been deleted.

Accepted date formats for the Query API
---------------------------------------

The Query API documentation is not clear on which date formats are expected exactly in the ``Date`` header.
The mock is strict.
That is, it accepts only a few date formats, and rejects all others.
If you find a date format which is accepted by the real Query API but rejected by the mock, please create a GitHub issue.

Unknown fields in Query API requests
------------------------------------

The `Vuforia Query Web API`_ documentation states that the API accepts requests with unknown data fields, and ignores the unknown fields.
The real Query API does not do this.
It returns a 400 (``BAD REQUEST``) response with the ``UnknownParameters`` result code when a multipart field other than ``image``, ``max_num_results`` or ``include_target_data`` is given.
The mock matches the real Query API rather than the documentation.

.. _Vuforia Query Web API: https://developer.vuforia.com/library/vuforia-engine/web-api/vuforia-query-web-api/

Targets stuck in processing
---------------------------

On the real Vuforia Web Services, targets sometimes get stuck in the processing state.
For example, targets with the name ``\uffff`` get stuck in the processing state.
On the mock, no targets get stuck in the processing state.

Database summary quotas
-----------------------

The database summary endpoint returns quotas which match the quotas given for a free license.

``transfer-encoding`` headers
-----------------------------

Sometimes the real Query API sends responses with ``transfer-encoding: chunked`` and no ``Content-Length`` header.
The mock does not do this.

``Content-Encoding`` headers
----------------------------

The real Query API sends some responses with ``Content-Encoding: gzip``.
The mock Query API sends all responses with ``Content-Encoding: gzip``.

``x-aws-region`` headers
------------------------

The mock uses the fixed sample value ``us-east-2, us-west-2`` for ``x-aws-region`` response headers.
The regions returned by the real Vuforia Web Services can differ, so tests should not rely on the mock's exact value.

.. _differences-nginx-error-cases:

NGINX Error cases
-----------------

Vuforia uses NGINX in front of both the Target API and the Query API.
NGINX reads each request header line into an 8 KiB buffer, and returns a 400 (``BAD REQUEST``) response with an HTML body titled ``400 Request Header Or Cookie Too Large`` for a line which does not fit.
The line's terminating CRLF also counts towards the buffer, so the longest accepted line is 8190 bytes, where a line is the header name, a colon, a space and the value.
This was observed against real Vuforia on 2026-09-08.

The mock returns that response for any header line longer than 8190 bytes.
The mock does not implement the following related behaviors, which were observed in the same session:

* The Target API's Envoy layer lets a ``Cookie`` line slightly over the limit through.
  A ``Cookie`` line of 8193 bytes was accepted and one of 8300 bytes was rejected.
* The Target API's AWS load balancer rejects a header line of 16384 bytes or more itself, with a shorter HTML body and a ``Server: awselb/2.0`` header.
  A ``Cookie`` line of that size passes the load balancer and is rejected by NGINX instead.
* The Query API's application server rejects a request whose headers total about 8 KiB with a 431 (``REQUEST HEADER FIELDS TOO LARGE``) HTML response before the NGINX limit is reached.
  With the headers which a query normally has, a header line of 7500 bytes was accepted and one of 8000 bytes was rejected this way.
* The Model Target Web API, the OAuth2 token endpoint and reco counts report downloads in the mock do not apply the limit.

Result codes
------------

Result codes are returned by requests to Vuforia to help with debugging.
See `VWS API Result Codes <https://developer.vuforia.com/library/vuforia-engine/web-api/cloud-targets-web-services-api/#result-codes>`_ for details of the available result codes.
There are some result codes which the mock cannot return.

These are:

* ``DateRangeError``

Request quota exhaustion
------------------------

The mock returns ``RequestQuotaReached`` when a :class:`mock_vws.database.CloudDatabase` is created with ``request_quota=0``.
This behavior follows the public Vuforia documentation.

.. admonition:: Unverified assumption

   :ref:`unverified-request-quota-exhaustion`

Request rate limits
-------------------

Vuforia documents a request rate limit of 15 requests per second for VWS endpoints in general, with 45 requests per second for ``GET /targets/{target_id}``, 10 requests per second for ``GET /duplicates/{target_id}``, and 1 request per minute for ``GET /targets``.

The limits were checked against real Vuforia on 2026-09-08, by sending bursts of requests to read-only endpoints:

* ``GET /targets`` accepts two requests per minute, not one.
  The window is a fixed clock minute: two requests at 40 seconds past the minute were accepted, a third was rejected, and a request three seconds into the next minute was accepted again.
* The per-second limits are enforced roughly, not exactly.
  Bursts of 40 concurrent ``GET /summary`` requests saw between 17 and 37 succeed against the documented 15, and a burst of 120 ``GET /targets/{target_id}`` requests saw 74 succeed against the documented 45, so the limiter appears to be spread over more than one instance or window.
* A limit is keyed on the server access key in the ``Authorization`` header, so one database's burst does not affect another database.
  Vuforia applies the limit before checking the signature, so a request with a bad signature counts towards the limit, and a request over the limit gets a ``429`` response whether or not it is signed correctly.
  Requests without an ``Authorization`` header are not rate limited.
* A rate-limited request gets a ``429`` (``TOO MANY REQUESTS``) response from Envoy with an empty body, no ``Content-Type`` header and an ``x-envoy-ratelimited: true`` header.
  Vuforia has an Envoy layer at its edge and another in front of the application, and either may reject the request.
  Only a rejection by the inner layer carries an ``x-envoy-upstream-service-time`` header, which the mock always includes.
  The ``TooManyRequests`` result code from Vuforia's result codes table does not appear.

The mock returns the empty Envoy response, applies each limit before checking the request's signature, and tracks each limit separately for each database and each group of endpoints.
The mock's windows are rolling rather than clock-aligned, so two ``GET /targets`` requests block a third until a minute has passed since the first, and the mock enforces the per-second limits exactly.
The mock only limits requests whose access key belongs to a database, because the limits are configured on the database.

The mock applies no limit by default.
Applying a limit of two requests per minute to ``GET /targets`` by default would break the tests of anything which uses the mock.

Set ``request_rate_limits`` to
:data:`mock_vws.request_rate_limits.DOCUMENTED_REQUEST_RATE_LIMITS` to apply
the limits which real Vuforia applies::

    from mock_vws import MockVWS
    from mock_vws.database import CloudDatabase
    from mock_vws.request_rate_limits import DOCUMENTED_REQUEST_RATE_LIMITS

    database = CloudDatabase(
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        # A third ``GET /targets`` request within a minute gets a ``429``
        # response.
        ...

``requests_per_second_limit`` remains available.
It applies one limit to all VWS endpoints together, and it is tracked separately from the per-endpoint limits.

Vuforia also documents that ``GET /targets`` fails for databases with more than 1 million images, which the mock does not implement.

.. admonition:: Unverified assumption

   :ref:`unverified-targets-over-one-million-images`

Configurable Cloud Query failures
---------------------------------

The Vuforia Cloud Query API documents failure responses with JSON, arbitrary
content, or no body. Use
:paramref:`mock_vws.MockVWS.cloud_query_failure_response` to make every Cloud
Query request return a particular documented failure shape through the
in-process ``requests``, ``httpx`` and ``httpx2`` backends::

    from mock_vws import CloudQueryFailureResponse, MockVWS

    failure = CloudQueryFailureResponse(
        status_code=503,
        headers={"Content-Type": "text/plain", "Retry-After": "10"},
        body=b"Temporarily unavailable",
    )

    with MockVWS(cloud_query_failure_response=failure):
        # Cloud Query calls return the configured response.
        ...

The configured response bypasses normal Cloud Query validation and image matching.
Omitting it preserves the normal successful-query behavior.
This configuration is not supported by the Flask/Docker backend.

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

Other configurable result codes
-------------------------------

The mock also supports four other result codes.
``ProjectSuspended`` has been seen from a real database.
The other three come from Vuforia's result codes table rather than from a response which a real database gave:

.. admonition:: Unverified assumptions

   :ref:`unverified-project-suspended`

   :ref:`unverified-additional-result-codes`


* ``TargetQuotaReached`` is returned when adding a target to a
  :class:`mock_vws.database.CloudDatabase` which already contains
  ``target_quota`` targets.
* ``ProjectSuspended`` is returned with status code 403 by every VWS endpoint
  when a database uses the
  :attr:`mock_vws.states.States.PROJECT_SUSPENDED` state.
  Real Vuforia has returned this result code for a database which passed its
  monthly recognition threshold, but its status code, body and headers were
  not recorded, and reads such as ``GET /targets`` and the database summary
  kept working there.
* ``ProjectHasNoApiAccess`` is returned by VWS endpoints when a database uses the :attr:`mock_vws.states.States.PROJECT_HAS_NO_API_ACCESS` state.
  This casing comes from Vuforia's result codes table, as no response from a real database in this state has been seen.
  ``vws-python`` and ``vws-cli`` map this result code by the ``ProjectHasNoAPIAccess`` spelling, so they do not recognize this response until they are updated.
* ``TooManyRequests`` is returned when a
  :class:`mock_vws.database.CloudDatabase` exceeds a configured request rate
  limit. Set ``requests_per_second_limit`` to ``0`` to return this result code
  for every VWS request.

``Content-Length`` headers
--------------------------

When the given ``Content-Length`` header does not match the length of the given data, the mock server (written with Flask) will not behave as the real Vuforia Web Services behaves.

VuMark instance images
----------------------

The mock returns a fixed minimal image in the requested format.
The ``instance_id`` value is not encoded into the response image.
Real Vuforia encodes the instance ID into the VuMark pattern.

Model Target datasets
---------------------

The Model Target Web API mock supports OAuth2 token requests, standard and advanced dataset creation, status polling, dataset downloads, and deletion.
The generated dataset download is a small valid ``full-dataset.zip`` with the
same ``MTDataset.dat`` and ``MTDataset.xml`` filenames as Vuforia. Its contents
are synthetic request metadata and minimal XML, not a real Vuforia Engine
Model Target dataset.
Use :paramref:`mock_vws.MockVWS.model_target_generation_failure` to make
in-process Model Target datasets finish with a ``failed`` status and an
``error`` object. The failure is returned after the configured
:paramref:`~mock_vws.MockVWS.processing_time_seconds`, so callers can test
both processing and failed states. This configuration is not supported by the
Flask/Docker backend.
Use
:paramref:`mock_vws.MockVWS.model_target_training_allowance_exceeded` to make
in-process Model Target dataset creation return Vuforia's
``TRAINING_ALLOWANCE_EXCEEDED`` response. Set the
:envvar:`MODEL_TARGET_TRAINING_ALLOWANCE_EXCEEDED` environment variable to
``true`` to configure the same response in the Flask/Docker backend.
Use :paramref:`mock_vws.MockVWS.model_target_generation_warning` to make
successful in-process Model Target datasets include a Vuforia-shaped
``warning`` object after processing completes. This configuration is not
supported by the Flask/Docker backend.
Model Target API routes require a three-part JSON Web Token with JSON object
header and payload parts, a non-``none`` ``alg`` value, and a non-empty
base64url-encoded signature, such as the token returned by the mock OAuth2
route.
The mock does not verify token signatures, payload claims such as expiry, or
token revocation.
The OAuth2 route supports both the ``client_credentials`` and ``password``
grants. Tokens returned by the mock contain explicit scopes, and
standard and advanced dataset routes require their corresponding Model Target
scope. A token carrying ``modeltargets.all`` can access both route families.
The OAuth2 client-credentials management routes support creating, listing,
updating and deleting credentials, including Vuforia's limit of 100 created
credentials per account.

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

Some Model Target Web API paths remain mock-only in ``tests/mock_vws/test_model_target_web_api.py::TestAdditionalBehaviors``.
Downloads of still-processing datasets are mock-only because exercising the path against real Vuforia would require creating a dataset on every test run; the mock drives the processing window deterministically.
A download request for a dataset which is not ready reports the dataset's training status.
The mock reports ``not-started`` for the whole processing window, as real Vuforia does for a dataset which was just created, and ``failed`` for a dataset whose generation failed.

.. admonition:: Unverified assumption

   :ref:`unverified-model-target-failed-dataset-name`

Some malformed State-Based Model Target configuration documents remain mock-only because real Vuforia returns an internal server error for them.

Reco counts reports
-------------------

The mock does not count recognitions, so a generated reco counts report contains only the ``target_id,reco_count`` header row, ending with a carriage return and a line feed, until recognition counts are set on targets.
That is what real Vuforia returns for a database with no recognitions.

A report for the current month has a row for each target with a non-zero ``current_month_recos``, and a report for the previous month has a row for each target with a non-zero ``previous_month_recos``.
Each row ends with a carriage return and a line feed, as the header row does.
The mock takes the counts when the report is requested, so counts which are set after that are not in that report.
The mock orders the rows by target ID.

.. admonition:: Unverified assumption

   :ref:`unverified-reco-counts-report-row-order`

Setting recognition counts is mock-only, because real Vuforia's counts are delayed for longer than a test runs, so the tests for reports with rows in ``tests/mock_vws/test_reco_counts_report.py`` run against the mocks only.
As with real Vuforia, the report is served with a ``text/plain`` content type rather than a CSV one.

Real Vuforia assigns a database an ID, which the target manager shows.
The ID of a database in the mock is
:paramref:`mock_vws.database.CloudDatabase.database_id`, which defaults to a
random string, so the path of a request to this endpoint is built by reading
that attribute rather than by looking the ID up.
As real Vuforia does, the mock returns a 401 response with the
``AuthenticationFailure`` result code for a request which is signed with valid
server keys but which names any other database, including one named by its
name rather than by its ID.

Real Vuforia returns a presigned URL for cloud storage, of this form:

.. code-block:: text

   https://guacamole-targetstore-production-targets.s3.us-west-1.amazonaws.com/reports/{database_id}/{file_name}.csv
     ?X-Amz-Security-Token=...
     &X-Amz-Algorithm=AWS4-HMAC-SHA256
     &X-Amz-Date=20260808T210052Z
     &X-Amz-SignedHeaders=host
     &X-Amz-Credential=.../20260808/us-west-1/s3/aws4_request
     &X-Amz-Expires=604799
     &X-Amz-Signature=...

The mock returns a URL with the same path and the same query parameters,
served by the mock itself rather than by cloud storage.
The URL returned by the Flask and Docker mock is built from the
:envvar:`VWS_BASE_URL` environment variable.
The credential, the security token and the signature are placeholders of
the right shape.
The mock does not check the signature, so a URL whose signature or file name
has been changed, which real Vuforia refuses with a ``SignatureDoesNotMatch``
error document, is served by the mock as if it were signed.

Real Vuforia names the report file after the requested month, and does so differently for each of the two months it accepts.
A report for the current month is named for the UTC date and hour, such as ``2026-08-08-21.csv``, and a report for the previous month is named for the month, such as ``2026-07.csv``.
The mock does the same, so two requests for the same month in the same hour name the same file, and two requests for the previous month always do.
Real Vuforia does not generate the report again for such a request: the URL which the second request returns serves the file which the first request generated, unchanged.
The mock does the same, so recognition counts set between the two requests are not in the report which the second URL serves.

The URL expires ``X-Amz-Expires`` seconds after its ``X-Amz-Date``, which is one second under seven days.
Real Vuforia's storage checks that the URL is in date before it checks the signature, so a URL whose ``X-Amz-Date`` or ``X-Amz-Expires`` has been edited to put it out of date gives the same 403 response as a URL which has expired, even though the edit invalidates the signature.
The mock honors those two parameters in the same way, so code which handles a stale URL can be tested by editing them.
The 403 response is the XML ``AccessDenied`` error document which Amazon S3 gives, with a ``Request has expired`` message, the expiry time and the server time.
A URL without those parameters gives the ``AccessDenied`` error document with an ``Access Denied`` message, as it does on real Vuforia.

Until the report is ready, the URL gives a 404 response with the XML ``NoSuchKey`` error document which Amazon S3 gives, naming the file's key.
The mock does the same, and the mock gives the same response for a file which no request generated.
The mock's error documents carry random request identifiers where Amazon's carry its own.
The report takes :paramref:`~mock_vws.MockVWS.processing_time_seconds` seconds to generate in the mock.
The documentation says a real report takes between a few seconds and one hour, but a real report has been observed ready within a second of the request, and the 404 response has been observed by fetching the URL straight after the request.
The download requires no authorization beyond the query parameters of the URL, as on real Vuforia.

Paths which the mock does not serve
-----------------------------------

Real Vuforia gives an empty body with a 404 response only for a request to a path which does not start with a served path, such as ``/some-random-endpoint``.
For any other request which it does not serve, such as ``DELETE /summary`` or ``GET /targetsfoo``, it gives an HTML "Not Found" page which names the method and the path of the request.
The Flask and Docker mock reproduces both response shapes.

The ``requests``, ``httpx`` and ``httpx2`` backends mock only the paths which the mock serves, so a request to any other path raises a connection error rather than giving the 404 response which real Vuforia gives.

Header cases
------------

The mock does not necessarily match Vuforia for all header cases.
