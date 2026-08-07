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
* ``ProjectHasNoAPIAccess`` is returned by VWS endpoints when a database uses
  the :attr:`mock_vws.states.States.PROJECT_HAS_NO_API_ACCESS` state.
* ``TooManyRequests`` is returned when a
  :class:`mock_vws.database.CloudDatabase` exceeds its
  ``requests_per_second_limit``. Set the limit to ``0`` to return this result
  code for every VWS request. By default, the mock does not apply a per-second
  request limit.

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
The generated dataset download is a small valid zip file containing request metadata, not a real Vuforia Engine Model Target dataset.
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

Dataset creation requests are validated for the required top-level ``models``,
``name`` and ``targetSdk`` fields, for those fields' types, for each ``models``
entry being a JSON object, and for the number of models.
Each model is validated for the required ``cadDataUrl`` and ``name`` fields,
for those fields' types, and for ``views`` being a JSON array when it is given.
Each ``views`` entry is validated for being a JSON object, for the required
``guideViewPosition`` and ``name`` fields, and for those fields' types.
Each ``guideViewPosition`` object is validated for the required ``rotation``
and ``translation`` fields, for those fields being JSON arrays, and for the
elements of those arrays being JSON numbers.
The mock does not validate the contents of each model further, such as whether
``cadDataUrl`` values are reachable, the lengths of ``rotation`` and
``translation`` arrays, or ``targetSdk`` version numbers.

For unknown Model Target datasets, the mock returns an error whose ``target`` is ``userId:mock``.
Real Vuforia uses ``userId:<numeric-user-id>`` where the numeric portion is per-account.

Two Model Target Web API error paths remain mock-only in ``tests/mock_vws/test_model_target_web_api.py::TestMockOnlyErrors``.
Downloads of still-processing datasets are mock-only because exercising the path against real Vuforia would require creating a dataset on every test run; the mock drives the processing window deterministically.
Advanced-dataset creation with more than 20 models is mock-only because the available test account lacks the advanced-dataset scope and real Vuforia rejects the request with a 403 before validating model counts.

Reco counts reports
-------------------

The mock does not count recognitions, so a generated reco counts report
contains only the ``target_id,reco_count`` header row.
The mock returns the same report for the current month and the previous month.

The mock does not use the database ID in the request path.
It uses the database which matches the request's server keys, and it accepts
any database ID.

Real Vuforia returns a presigned URL for cloud storage, and the report takes
between a few seconds and one hour to generate.
The mock returns a URL served by the mock itself, without the query
parameters of a presigned URL, and the report takes
:paramref:`~mock_vws.MockVWS.processing_time_seconds` seconds to generate.
The URL returned by the Flask and Docker mock is built from the
:envvar:`VWS_BASE_URL` environment variable.
As with real Vuforia, the URL returns a 404 response until the report is
ready, and it requires no authorization.

The ``Fail`` result code returned for a ``month`` which is not in the
``YYYY-mm`` form, and for a ``month`` which is neither the current month nor
the previous month, has not been verified against real Vuforia.
The columns of the CSV report, and the headers of the download response, have
not been verified against a real report either.

Header cases
------------

The mock does not necessarily match Vuforia for all header cases.
