Changelog
=========

.. towncrier release notes start

2026.09.08
----------

- The response delay and client timeout simulation is now provided by the ``mock-response-delay`` package.

- The mock now returns NGINX's ``400 Request Header Or Cookie Too Large`` response for any request header line longer than 8190 bytes, as real Vuforia does.

- Match real Vuforia's request rate limiting, which was checked against it on 2026-09-08.
  ``DOCUMENTED_REQUEST_RATE_LIMITS`` now allows two ``GET /targets`` requests per minute rather than one, a rate-limited request gets Envoy's empty-bodied ``429`` response rather than a JSON ``TooManyRequests`` body, and the limits are applied before the request's signature is checked.

2026.09.06
----------

- Add ``MockVWS.set_target_recognition_counts`` and a matching target manager endpoint for the Flask and Docker mock, for setting the recognition counts which the target summary report and the reco counts report show for a target.
  A reco counts report now has a row for each target with recognitions in the requested month, and the recognition counts and recognition threshold of a cloud database are kept when the database is created in the Flask and Docker mock.

- Order Query API and ``GET /duplicates/{target_id}`` results by match score, with the best match first, as the real Query API does.
  Matches with equal scores keep the existing upload date and then target ID order.

  Image matchers now return a score, or ``None`` for no match, rather than a ``bool``.
  ``StructuralSimilarityMatcher`` returns the images' SSIM score, and ``ExactMatcher`` gives every match the same score.
  A custom ``query_match_checker`` or ``duplicate_match_checker`` which returns a ``bool`` now raises a ``TypeError``; return a score, such as ``1.0``, for a match and ``None`` for no match instead.
  The mock's ranking is its matcher's opinion, not Vuforia's proprietary one, so the mock's order still need not agree with the real Query API's order.

- Respond, rather than failing to respond, to a request body which is not UTF-8 and to a query request whose ``multipart/form-data`` body ends before its closing boundary.

- Return a ``400`` response which names the offending field and the accepted values, rather than a ``500`` response, when the target manager container is given an invalid cloud database or VuMark database to create.
  Return a ``404`` response, rather than a ``500`` response, when the target manager container is asked to add a target to a database which does not exist.

- Say which claims about the real Vuforia Web Services the mock has not had checked against them. :doc:`unverified-behavior` lists each such claim and what would verify it, and ``differences-to-vws`` marks the unverified assumptions among its deliberate differences.

- Return a ``BadImage`` response, rather than failing to respond, when an image given to the Target API is truncated before the end of its image data.

- ``MockVWS`` now intercepts ``httpx2`` requests, synchronous and asynchronous, alongside ``requests`` and ``httpx``. The ``httpx2`` path uses native ``httpx2`` requests and responses, and does not need ``httpx2.alias_httpx()``.

- Fix nested ``MockVWS`` instances on the ``httpx`` backend: an inner mock is now the only one which answers while it is running, matching the ``requests`` and ``httpx2`` backends. Previously the outer mock kept answering and requests to the inner mock's URL were refused.

- Return a response, rather than raising an uncaught ``JSONDecodeError``, when an empty body is given to a VWS endpoint which takes a JSON body.
  As real Vuforia does, ``POST /targets`` and ``PUT /targets/<target_id>`` now return a 500 ``Fail`` response, the reco counts report endpoint returns a 400 ``Fail`` response, and the VuMark instance generation endpoint returns a 400 ``BadRequest`` response.

2026.08.26.1
------------

- Add configurable Model Target HTTP failure responses for selected dataset request phases.

2026.08.26
----------

- Guard the state which the Docker containers share between requests with a lock.
  The containers serve requests on threads, so concurrent requests, such as those made by a test suite which runs in parallel, could previously race with each other: listing databases while a target was added could return a 500 response, and a target which was being updated or deleted could briefly be missing from a database.

- Give each call of a function decorated with a ``MockVWS`` instance its own databases and targets.
  Previously, every use of an instance shared one set of databases and targets, so decorating two test functions with one instance made them affect each other.
  A database can still be inspected during a call, and its targets are what they were before the call again once it returns.
  Using an instance as a context manager is unchanged: a ``with`` block still shares its state with every other use of the same instance.

- - Add configurable Model Target ``TRAINING_ALLOWANCE_EXCEEDED`` responses to the in-process and Flask/Docker mocks.

2026.08.14
----------

- Give ``CloudDatabase`` a ``database_id``, and reject a reco counts report request whose path names a database which the request's server keys do not belong to, as real Vuforia does.

- Return a response, rather than raising an uncaught ``PIL.Image.DecompressionBombError``, when an image with a small file size but a huge number of pixels is given to ``POST /targets`` or ``POST /v1/query``.
  As real Vuforia does, ``POST /targets`` now returns the ``ImageTooLarge`` result code for an image with more than 37748736 pixels, and the Query API applies no pixel count limit.

- Return targets in a deterministic order from the Query API, ``GET /targets``
  and ``GET /duplicates/{target_id}``.  Targets are ordered by upload date and
  then by target ID, so repeated runs agree with each other.  This order is not
  Vuforia's match score order.

- Document the Docker containers' configuration with the environment variable names and values which the applications actually read, starting with ``TARGET_MANAGER_BASE_URL``.

- Build the Docker images from a committed ``uv.lock`` with a ``.dockerignore``, so that image contents are reproducible from a commit, source edits no longer invalidate the dependency layer, and repository files such as tests and documentation are no longer copied into the images.

- Store Model Target datasets in the target manager service rather than in the VWS application. In the Docker deployment, datasets now survive a restart of the VWS container, matching how cloud databases and their targets are stored. The VWS application also no longer imports the target manager module's state: it constructs its own request rate limiter and reco counts report store.

- Report the Docker containers as unhealthy without a traceback in the health check probe output while nothing is yet listening on the port.

- Support ``cadDataBlob`` and ``cadDataFormat`` in Model Target dataset creation requests, and require exactly one of ``cadDataUrl`` and ``cadDataBlob`` for each model.

- Reject Model Target Web API and OAuth2 token requests with a ``Content-Length`` header which is not an integer, matching the load balancer in front of real Vuforia.

- Reject Model Target dataset creation requests with wrongly typed ``name``, ``targetSdk`` or ``models`` entry values.

- Treat standard and advanced Model Target datasets as separate resources: status, download and delete requests made through the other dataset type's routes now return the unknown-dataset error rather than acting on the dataset.

- Reject Model Target dataset creation requests with values outside the documented enumerations for the ``automaticColoring``, ``motionHint``, ``optimizeTrackingFor``, ``realisticAppearance``, ``simplify`` and ``trackingMode`` model fields.

- Report the ``failed`` training status when downloading a Model Target dataset whose generation failed, rather than the ``not-started`` status which a still-processing dataset reports.

- Add configurable failed Model Target dataset status responses.

- Add configurable Model Target dataset generation warning responses.

- Reject Model Target dataset creation requests with ``guideViewPosition`` objects which are missing ``rotation`` or ``translation``, or which have ``rotation`` or ``translation`` values that are not JSON arrays.

- Reject Model Target dataset creation requests with ``guideViewPosition`` ``rotation`` or ``translation`` arrays which contain values that are not JSON numbers.

- Reject Model Target bearer tokens whose JWT payload is not a JSON object.

- Reject Model Target bearer tokens with empty or malformed JWT signatures.

- Reject Model Target dataset creation requests with models which are missing ``name``, or which have wrongly typed ``cadDataUrl``, ``name`` or ``views`` values.

- Reject Model Target dataset creation requests with a body which is valid JSON but not a JSON object, rather than raising an error in the mock.

- Accept State-Based Model Target configuration and validate per-view state selections against its declared states.

- Reject Model Target dataset creation requests with ``views`` entries which are not JSON objects, which are missing ``guideViewPosition`` or ``name``, or which have wrongly typed ``guideViewPosition`` or ``name`` values.

- Model VWS request rate limits per endpoint with the new
  ``CloudDatabase.request_rate_limits`` setting, including the limits which
  Vuforia documents as ``mock_vws.request_rate_limits.DOCUMENTED_REQUEST_RATE_LIMITS``.
  No request rate limit is applied by default.

- Change the ``ProjectHasNoAPIAccess`` result code to ``ProjectHasNoApiAccess``, matching Vuforia's result codes table.

- Add the reco counts report endpoint, and a download URL for the generated CSV report.

- Preserve the recognition count fields, the reco rating and the reco threshold when dumping a ``CloudDatabase`` or an ``ImageTarget`` to a dictionary and loading it back.

- Rate an image of a single color as ``0`` rather than raising an uncaught ``ZeroDivisionError``.

- Return a 404 response from the Flask and Docker mock for a request to a path which it does not serve, and for a request to a served path with a method which that path does not serve, as real Vuforia does, rather than raising an error.

- Reject VuMark instance generation requests whose ``instance_id`` is not a string with a ``BadRequest`` result, as real Vuforia does, and move the ``instance_id`` checks into validators shared by both mock backends.

- Reject Model Target dataset creation requests with a body which cannot be decoded as UTF-8, rather than raising an error in the mock, and decode OAuth2 token request bodies leniently.

2026.08.04.2
------------

- Replace the PyTorch image-quality stack with OpenCV and a lightweight BRISQUE
  implementation. This reduces dependency download and installation sizes and
  removes the need to configure PyTorch's CPU-only package index.

- Allow VuMark generation requests to be configured to return ``QuotaExceeded``, ``LicenseCheckFailed``, or ``AuthorizationFailed`` responses.

- Cloud databases with ``request_quota=0`` now return a
  ``RequestQuotaReached`` response from VWS endpoints.

- Add a mock implementation of the Model Target Web API, including OAuth2 token creation, standard and advanced dataset creation, status polling, dataset download, and deletion.

- Improve Model Target Web API mock authentication failure responses, including
  malformed and unsecured JSON Web Token headers.

- Match real Vuforia Model Target dataset creation validation error shape, including per-request UUID, details list, and status codes (415 for unsupported media type, 400 with ``BAD_REQUEST`` validation details).

- Match real Vuforia Model Target unknown-dataset response shape (``NOT_FOUND`` code, ``Could not find a model-view database with uuid <uuid>`` message, ``userId:`` target).
  Keep each Model Target dataset status response internally consistent when processing completes while the response is being generated.

- Make synthetic Model Target dataset zip downloads byte-for-byte reproducible.

- Match real Vuforia Model Target Web API error responses for invalid request bodies, invalid dataset creation payloads, unknown datasets, and downloads of still-processing datasets.

- Add configurable ``TargetQuotaReached``, ``ProjectSuspended``, and
  ``ProjectHasNoAPIAccess`` responses from VWS endpoints.

- Add configurable ``TooManyRequests`` responses from VWS endpoints using the
  ``CloudDatabase.requests_per_second_limit`` setting.

- Add ``CloudQueryFailureResponse`` and the ``MockVWS.cloud_query_failure_response`` parameter for returning configurable Cloud Query failure status codes, headers, and raw bodies through the ``requests`` and ``httpx`` backends.

2026.04.26
----------


2026.02.22.3
------------


- ``MockVWS`` now intercepts both ``requests`` (via ``responses``) and ``httpx`` (via ``respx``) simultaneously.
  ``MockVWSForHttpx`` has been removed: ``MockVWS`` handles both HTTP libraries.

2026.02.22.2
------------


2026.02.22.1
------------


2026.02.22
----------


2026.02.21
----------


- Add ``VuMarkTarget`` class for VuMark template targets, alongside the renamed ``ImageTarget`` class (previously ``Target``).
  ``ImageTarget`` is for image-based targets and ``VuMarkTarget`` is for VuMark template targets.
  Both can be stored in a ``VuforiaDatabase``.

2026.02.18.2
------------


2026.02.18.1
------------


2026.02.18
----------


2026.02.15.5
------------


2026.02.15.4
------------


- Add ``sleep_fn`` parameter to ``MockVWS`` for injecting a custom delay strategy, enabling deterministic and fast tests without monkey-patching.

2026.02.15.3
------------


- Add ``response_delay_seconds`` parameter to ``MockVWS`` for simulating slow server responses and testing timeout handling.
- Add ``response_delay_seconds`` setting to the Flask mock (``VWSSettings`` and ``VWQSettings``) for simulating slow server responses.

2025.03.10.1
------------

2025.03.10
----------

2025.02.21
----------

2025.02.18
----------

2024.08.30
------------

2024.07.15
------------

- Support passing data as strings.

2024.07.02.1
------------

- Fix installation on Windows now that ``numpy`` 2.0.0 has been released.

2024.02.16
------------

- Add a structural similarity image matcher.

2018.12.01.0
------------

- Distribute type information.

2018.09.10.0
------------

- Initial release
