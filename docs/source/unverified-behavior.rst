Unverified behavior
===================

The mock is kept honest by running one test suite against the real Vuforia
Web Services and against each mock, and asserting the same things about each.
Not every claim which the mock makes can be checked that way, and a test which
runs against the mocks only still passes, still counts towards coverage and
still reads like verification.

This document lists every claim which the mock makes and which nobody has
observed real Vuforia make, so that a user of the mock can tell which
behaviors are copied from the service and which are copied from its
documentation.

Categories
----------

Each claim below is one of these:

Temporarily unverifiable
   The behavior is observable in principle, but not right now.
   The credentials, the account scope or the account allowance needed to
   provoke it are missing.
   These are the ones which are expected to become verified.

Inherently unverifiable
   The behavior cannot be provoked against real Vuforia at all.
   These are mock-only forever.

Never attempted
   The mock implements something from Vuforia's public documentation and
   nobody has checked that the documentation is accurate.
   This is the category which bites: the mock looks verified, and a
   divergence appears in production.

A fourth category, ``no-vuforia-claim``, is used for tests rather than for
claims. It covers tests of the mock's own configuration API, of its target
manager, of its container and of test helpers, none of which say anything
about real Vuforia.

How this is enforced
--------------------

Every test which never runs against the real Vuforia declares its category
with the ``mock_only`` marker, which is defined in
``tests/mock_vws/verification.py``::

    @mock_only(
        reason=UnverifiedReason.INHERENTLY_UNVERIFIABLE,
        detail="Why real Vuforia cannot be asked this.",
    )

Collection fails if a test which never reaches real Vuforia does not carry
one, so a test which uses ``MockVWS()`` directly cannot avoid declaring
itself.
A marked test does not run against the real Vuforia even when it is
run over it as a parameter, so the declaration and the behavior are the same
thing rather than two things which can drift apart.

``verification.toml`` records the resulting verified and unverified split for
each API. ``python -m admin.verification_report`` checks that file against the
suite and against this document, and says which way each count moved:

.. code-block:: console

   $ python -m admin.verification_report
   $ python -m admin.verification_report --update

A test which gives up on verifying anything while it runs, such as one which
the account's Model Target training allowance rejects, is recorded as well.
``pytest`` reports those in a ``stopped verifying anything while running``
section, and ``--fail-on-runtime-unverified`` turns them into a failing run.

.. _unverified-request-quota-exhaustion:

Request quota exhaustion
------------------------

:Category: never-attempted
:API: VWS Target API

The mock returns a ``RequestQuotaReached`` response for a database created
with ``request_quota=0``.
The status code and the body shape come from Vuforia's documentation and from
the shape which other VWS errors have.

A real database with an exhausted request quota would verify this. No such
response has been seen.

.. _unverified-request-rate-limits:

Request rate limits
-------------------

:Category: never-attempted
:API: VWS Target API

Vuforia documents a limit of 15 requests per second for VWS endpoints in
general, 45 per second for ``GET /targets/{target_id}``, 10 per second for
``GET /duplicates/{target_id}`` and one per minute for ``GET /targets``.
The mock models the limits separately for each group of endpoints, and
applies them only when it is asked to.

Sending more than the documented number of requests to a real database, and
seeing what it returns, would verify this.

.. _unverified-additional-result-codes:

Additional result codes
-----------------------

:Category: never-attempted
:API: VWS Target API

``ProjectSuspended``, ``ProjectHasNoApiAccess``, ``TargetQuotaReached`` and
``TooManyRequests`` come from Vuforia's result codes table.
No response from a real database in any of those states has been seen, which
is why the mock's ``ProjectHasNoApiAccess`` casing is the table's casing
rather than an observed one.

A database put into each state by the Target Manager portal would verify
these.

.. _unverified-targets-over-one-million-images:

``GET /targets`` for very large databases
-----------------------------------------

:Category: never-attempted
:API: VWS Target API

Vuforia documents that ``GET /targets`` fails for a database with more than
one million images.
The mock does not implement this, so a user of the mock sees a successful
response where real Vuforia may not.

A database with more than a million images would verify this, which a test
account cannot hold.

.. _unverified-nginx-oversized-header-or-cookie:

Large headers and cookies
-------------------------

:Category: never-attempted
:API: Cross-cutting request handling

Vuforia runs behind NGINX, which is documented as returning a 400
(``BAD REQUEST``) response for a header or a cookie larger than 8 KiB.
The mock does not implement this, and no test sends such a request to either.

Sending a request with a header larger than 8 KiB to a real database would
verify this.

.. _unverified-reco-counts-report-not-ready:

A reco counts report which is not ready
---------------------------------------

:Category: never-attempted
:API: Reco Counts Report API

The URL which the mock returns for a reco counts report gives a 404 response
until the report is ready.

A request for a real report which caught it before it was generated would
verify this. Every real report requested so far has been ready by the time it
was asked for.

.. _unverified-reco-counts-report-row-order:

The order of reco counts report rows
------------------------------------

:Category: inherently-unverifiable
:API: Reco Counts Report API

The mock orders report rows by target ID.

Real Vuforia's recognition counts lag behind its queries by far longer than a
test runs, so no real report with rows in it has been seen, and no order has
been observed.

.. _unverified-seeded-recognition-counts:

Recognition counts in the target summary report
-----------------------------------------------

:Category: inherently-unverifiable
:API: VWS Target API

The mock does not count recognitions. Counts are set on a target instead, and
the target summary report and the reco counts report show them.

Real counts lag behind real queries by longer than a test runs, so no test can
make a real summary show a recognition.

.. _unverified-database-summary-processing-images:

Processing images in the database summary
-----------------------------------------

:Category: inherently-unverifiable
:API: VWS Target API

The mock's database summary is accurate immediately, so it counts an image
which is still processing.

The real summary lags behind the targets in the database, and sometimes skips
the processing state altogether, so it cannot be relied on to show one.

.. _unverified-vumark-processing-target:

VuMark instance generation for a processing target
--------------------------------------------------

:Category: inherently-unverifiable
:API: VuMark Instance Generation API

The mock returns ``TargetStatusNotSuccess`` for an instance generation request
for a VuMark target which is still processing.

VuMark targets are created through the Target Manager portal rather than
through the API, so no test can hold a real VuMark target in the processing
state.

.. _unverified-model-target-generation-failure:

Model Target generation failures
--------------------------------

:Category: inherently-unverifiable
:API: Model Target Web API

The mock can finish dataset generation with a ``failed`` status and an
``error`` object.

Real Vuforia cannot be made to fail generation on demand.

.. _unverified-model-target-generation-warning:

Model Target generation warnings
--------------------------------

:Category: never-attempted
:API: Model Target Web API

The mock can add a ``warning`` object to a dataset which finished
successfully.

The shape of that object comes from Vuforia's documentation rather than from a
warning which a real dataset carried.

.. _unverified-model-target-failed-dataset-name:

The name of a failed Model Target dataset
-----------------------------------------

:Category: inherently-unverifiable
:API: Model Target Web API

A download request for a dataset which is not ready reports the dataset's
training status.
The mock reports ``not-started`` for the whole processing window, as real
Vuforia does for a dataset which was just created, and ``failed`` for a
dataset whose generation failed.

The name which real Vuforia reports for a failed dataset has not been seen,
because generation cannot be made to fail.

.. _unverified-model-target-invalid-state-based-configuration:

Malformed State-Based configuration documents
---------------------------------------------

:Category: inherently-unverifiable
:API: Model Target Web API

The mock reports validation errors for malformed State-Based Model Target
configuration documents.

Real Vuforia returns an internal server error for them, so there is no
behavior to match.

.. _unverified-model-target-training-allowance:

The exhausted training allowance response
-----------------------------------------

:Category: inherently-unverifiable
:API: Model Target Web API

The mock can return Vuforia's ``TRAINING_ALLOWANCE_EXCEEDED`` response.

The response shape comes from a real rejection seen in CI rather than from
documentation, but the allowance cannot be exhausted on demand, and cannot be
restored afterwards, so no test can provoke it.

.. _unverified-model-target-signed-dataset-creation:

Signed Model Target dataset creation
------------------------------------

:Category: temporarily-unverifiable
:API: Model Target Web API

Creating a signed dataset, such as an advanced dataset with a state-based
configuration, consumes the Vuforia account's Model Target training
allowance.
The allowance is small, is shared across all CI jobs, and cannot be raised or
reset.

These cases reach real Vuforia only when ``--verify-model-target-signing`` is
given, so by default the mock's behavior for them is unverified.

.. _unverified-model-target-oauth2-client-credentials:

OAuth2 client-credential management
-----------------------------------

:Category: temporarily-unverifiable
:API: Model Target Web API

The mock serves the OAuth2 client-credential management routes, including
creating, listing, updating and deleting credentials, and Vuforia's limit of
100 created credentials per account.

The Model Target test account does not have the scope for those routes, so
they cannot be reached with the credentials which CI has.
