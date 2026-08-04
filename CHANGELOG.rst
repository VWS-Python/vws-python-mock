Changelog
=========

.. towncrier release notes start

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
  ``MockVWSForHttpx`` has been removed — ``MockVWS`` handles both HTTP libraries.

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
