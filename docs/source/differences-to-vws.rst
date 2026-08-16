Differences between the mock and the real Vuforia Web Services
==============================================================

The mock attempts to be realistic, but it was built without access to the source code of the original API.
Please report any issues `here <https://github.com/VWS-Python/vws-python-mock/issues>`__.

Image matching
--------------

Vuforia's image matching is proprietary and we do not intend to accurately copy it.
Instead, we aim for simple algorithms which are fast and are good enough for testing purposes.
The image matcher is configurable, using :paramref:`~mock_vws.MockVWS.match_checker`.

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

Image quality and ratings
-------------------------

Targets are assigned a rating between 0 and 5 of how good they are for tracking purposes.
In the mock this is calculated from the image quality, differently to how Vuforia does this.
This is customizable with the :paramref:`~mock_vws.MockVWS.target_tracking_rater` parameter.

Image targets which are not suited to detection are given 'failed' statuses.
The criteria for these images is not defined by the Vuforia documentation.
The mock is more forgiving than the real Vuforia Web Services.
Therefore, an image given a 'success' status by the mock may not be given a 'success' status by the real Vuforia Web Services.

Result ordering
---------------

The real Query API orders results by match score, with the best match first.
The mock has no match score, so it cannot reproduce that order.
Instead, the mock orders the targets it returns by upload date and then by target ID.
This makes repeated runs agree with each other, but it means that the mock's order is not a ranking.
Do not rely on the first result of a mock query being the best match.

This affects which results survive ``max_num_results``, and which result gets target data with ``include_target_data=top``.

``GET /targets`` and ``GET /duplicates/{target_id}`` use the same order.
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

The mock uses the fixed sample value ``us-east-2, us-west-2`` for
``x-aws-region`` response headers. The regions returned by the real Vuforia
Web Services can differ, so tests should not rely on the mock's exact value.

NGINX Error cases
-----------------

Vuforia uses NGINX.
This has error handling which is not duplicated in the mock.
For example, Vuforia returns a 400 (``BAD REQUEST``) response if a header or cookie is given which is larger than 8 KiB.

Result codes
------------

Result codes are returned by requests to Vuforia to help with debugging.
See `VWS API Result Codes <https://developer.vuforia.com/library/web-api/cloud-targets-web-services-api#result-codes>`_ for details of the available result codes.
There are some result codes which the mock cannot return.

These are:

* ``DateRangeError``

Request quota exhaustion
------------------------

The mock returns ``RequestQuotaReached`` when a
:class:`mock_vws.database.CloudDatabase` is created with
``request_quota=0``. This behavior follows the public Vuforia documentation,
but the response has not been verified against a real database with an
exhausted quota.

Request rate limits
-------------------

Vuforia documents a request rate limit of 15 requests per second for VWS
endpoints in general, with 45 requests per second for
``GET /targets/{target_id}``, 10 requests per second for
``GET /duplicates/{target_id}``, and 1 request per minute for ``GET /targets``.

The mock models these limits separately for each group of endpoints, but it
applies no limit by default. The documented numbers have not been verified
against a real database, and applying a limit of 1 request per minute to
``GET /targets`` by default would break the tests of anything which uses the
mock. Set ``request_rate_limits`` to
:data:`mock_vws.request_rate_limits.DOCUMENTED_REQUEST_RATE_LIMITS` to apply
the documented limits::

    from mock_vws import MockVWS
    from mock_vws.database import CloudDatabase
    from mock_vws.request_rate_limits import DOCUMENTED_REQUEST_RATE_LIMITS

    database = CloudDatabase(
        request_rate_limits=DOCUMENTED_REQUEST_RATE_LIMITS,
    )

    with MockVWS() as mock:
        mock.add_cloud_database(cloud_database=database)
        # A second ``GET /targets`` request within a minute returns
        # ``TooManyRequests``.
        ...

``requests_per_second_limit`` remains available. It applies one limit to all
VWS endpoints together, and it is tracked separately from the per-endpoint
limits.

Vuforia also documents that ``GET /targets`` fails for databases with more than
1 million images. The mock does not implement this, as the behavior is not
reproducible against a test account.

Configurable Cloud Query failures
---------------------------------

The Vuforia Cloud Query API documents failure responses with JSON, arbitrary
content, or no body. Use
:paramref:`mock_vws.MockVWS.cloud_query_failure_response` to make every Cloud
Query request return a particular documented failure shape through the
in-process ``requests`` and ``httpx`` backends::

    from mock_vws import CloudQueryFailureResponse, MockVWS

    failure = CloudQueryFailureResponse(
        status_code=503,
        headers={"Content-Type": "text/plain", "Retry-After": "10"},
        body=b"Temporarily unavailable",
    )

    with MockVWS(cloud_query_failure_response=failure):
        # Cloud Query calls return the configured response.
        ...

The configured response bypasses normal Cloud Query validation and image
matching. Omitting it preserves the normal successful-query behavior. This
configuration is not supported by the Flask/Docker backend.

Other configurable result codes
-------------------------------

The mock also supports four other result codes which have not been verified
against real databases in the corresponding states:

* ``TargetQuotaReached`` is returned when adding a target to a
  :class:`mock_vws.database.CloudDatabase` which already contains
  ``target_quota`` targets.
* ``ProjectSuspended`` is returned by VWS endpoints when a database uses the
  :attr:`mock_vws.states.States.PROJECT_SUSPENDED` state.
* ``ProjectHasNoApiAccess`` is returned by VWS endpoints when a database uses
  the :attr:`mock_vws.states.States.PROJECT_HAS_NO_API_ACCESS` state.
  This casing comes from Vuforia's result codes table, as no response from a
  real database in this state has been seen.
  ``vws-python`` and ``vws-cli`` map this result code by the
  ``ProjectHasNoAPIAccess`` spelling, so they do not recognize this response
  until they are updated.
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

Dataset creation request bodies which are valid JSON but not JSON objects are
reported as missing every required top-level field.
Dataset creation request bodies which cannot be decoded as UTF-8 are reported
as invalid JSON, as malformed JSON bodies are.
An OAuth2 token request body which cannot be decoded as UTF-8 is treated as one
which does not name a grant type.
Dataset creation requests are validated for the required top-level ``models``,
``name`` and ``targetSdk`` fields, for those fields' types, for each ``models``
entry being a JSON object, and for the number of models.
Each model is validated for the required ``name`` field, for exactly one of
``cadDataUrl`` and ``cadDataBlob`` being given, for the types of the
``automaticColoring``, ``cadDataBlob``, ``cadDataFormat``, ``cadDataUrl``,
``motionHint``, ``name``, ``optimizeTrackingFor``, ``simplify`` and
``trackingMode`` fields, for each of the ``automaticColoring``,
``cadDataFormat``, ``motionHint``, ``optimizeTrackingFor``, ``simplify`` and
``trackingMode`` fields being one of the values which the Model Target OpenAPI
specification documents for it when the field is given, and for ``views``
being a JSON array when it is given. The optional
``stateBasedConfigurationJsonString`` field must be a string containing a JSON
object with a ``states`` object.
The ``realisticAppearance`` model field is validated in the same way for
advanced datasets; the OpenAPI specification does not document it as a
standard dataset model field, so standard dataset creation does not validate
it.
Each ``views`` entry is validated for being a JSON object, for the required
``name`` field, and for the types of ``name`` and the optional
``guideViewPosition`` field.
State-Based Model Target views require ``guideViewPosition``, matching real
Vuforia.
An optional ``states`` field must be an array of strings. Each named state must
be declared by the model's ``stateBasedConfigurationJsonString``. Omitting the
field makes the view available to every configured state.
Each ``guideViewPosition`` object is validated for the required ``rotation``
and ``translation`` fields, for those fields being JSON arrays, and for the
elements of those arrays being JSON numbers.
The mock does not validate the contents of each model further, such as whether
``cadDataUrl`` values are reachable, whether ``cadDataBlob`` values are valid
base64-encoded archives of the named ``cadDataFormat``, whether
``cadDataFormat`` is given alongside ``cadDataBlob``, the lengths of
``rotation`` and ``translation`` arrays, or ``targetSdk`` version numbers.
It also does not validate the state configuration beyond its top-level
``states`` object.

For unknown Model Target datasets, the mock returns an error whose ``target`` is ``userId:mock``.
Real Vuforia uses ``userId:<numeric-user-id>`` where the numeric portion is per-account.

Standard and advanced routes share datasets by UUID. Access to each route
family is separated by its corresponding OAuth scope.

Some Model Target Web API paths remain mock-only in
``tests/mock_vws/test_model_target_web_api.py::TestAdditionalBehaviors``.
Downloads of still-processing datasets are mock-only because exercising the path against real Vuforia would require creating a dataset on every test run; the mock drives the processing window deterministically.
A download request for a dataset which is not ready reports the dataset's
training status. The mock reports ``not-started`` for the whole processing
window, as real Vuforia does for a dataset which was just created, and
``failed`` for a dataset whose generation failed. The name which real Vuforia
reports for a failed dataset has not been observed.
Some malformed State-Based Model Target configuration documents remain
mock-only because real Vuforia returns an internal server error for them.

Reco counts reports
-------------------

The mock does not count recognitions, so a generated reco counts report
contains only the ``target_id,reco_count`` header row, ending with a carriage
return and a line feed.
That is what real Vuforia returns for a database with no recognitions.
The mock returns the same report for the current month and the previous month.
As with real Vuforia, the report is served with a ``text/plain`` content type
rather than a CSV one.

Real Vuforia assigns a database an ID, which the target manager shows.
The ID of a database in the mock is
:paramref:`mock_vws.database.CloudDatabase.database_id`, which defaults to a
random string, so the path of a request to this endpoint is built by reading
that attribute rather than by looking the ID up.
As real Vuforia does, the mock returns a 401 response with the
``AuthenticationFailure`` result code for a request which is signed with valid
server keys but which names any other database, including one named by its
name rather than by its ID.

Real Vuforia returns a presigned URL for cloud storage.
The mock returns a URL served by the mock itself, without the query
parameters of a presigned URL, so the mock's URL never expires where a real
one expires after just under seven days.
The URL returned by the Flask and Docker mock is built from the
:envvar:`VWS_BASE_URL` environment variable.
The report takes :paramref:`~mock_vws.MockVWS.processing_time_seconds`
seconds to generate in the mock.
The documentation says a real report takes between a few seconds and one
hour, but a report for a database with no recognitions has been observed
ready within seconds.

Real Vuforia names the report file after the requested month, and does so
differently for each of the two months it accepts.
A report for the current month is named for the date and the hour, such as
``2026-08-08-21.csv``, and a report for the previous month is named for the
month, such as ``2026-07.csv``.
The mock names every report after an opaque report identifier, so the
requested month cannot be recovered from the mock's URL, and two requests for
the same month never give the same URL.

The mock's URL returns a 404 response until the report is ready, and requires
no authorization.
The lack of authorization matches real Vuforia, whose URL carries its own
signature.
The 404 has not been verified, because no request for a real report has caught
one before it was generated.

Paths which the mock does not serve
-----------------------------------

Real Vuforia gives an empty body with a 404 response only for a request to a
path which does not start with a served path, such as
``/some-random-endpoint``.
For any other request which it does not serve, such as ``DELETE /summary`` or
``GET /targetsfoo``, it gives an HTML "Not Found" page which names the method
and the path of the request.
The Flask and Docker mock gives an empty body for all of these.

The ``requests`` and ``httpx`` backends mock only the paths which the mock
serves, so a request to any other path raises a connection error rather than
giving the 404 response which real Vuforia gives.

Header cases
------------

The mock does not necessarily match Vuforia for all header cases.
