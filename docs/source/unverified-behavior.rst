Unverified behavior
===================

The mock is kept honest by running one test suite against the real Vuforia Web Services and against each mock, and asserting the same things about each.
Not every claim which the mock makes can be checked that way, and a test which runs against the mocks only still passes, still counts towards coverage and still reads like verification.

This document lists every claim which the mock makes and which nobody has observed real Vuforia make, so that a user of the mock can tell which behaviors are copied from the service and which are copied from its documentation.

Categories
----------

Each claim below is one of these:

Temporarily unverifiable
   The behavior is observable in principle, but not right now.
   The credentials, the account scope or the account allowance needed to provoke it are missing.
   These are the ones which are expected to become verified.

Inherently unverifiable
   The behavior cannot be provoked against real Vuforia at all.
   These are mock-only forever.

Never attempted
   The mock implements something from Vuforia's public documentation and nobody has checked that the documentation is accurate.
   This is the category which bites: the mock looks verified, and a divergence appears in production.

.. _unverified-request-quota-exhaustion:

VuMark instance generation for a processing target
--------------------------------------------------

:Category: inherently-unverifiable
:API: VuMark Instance Generation API

The mock returns ``TargetStatusNotSuccess`` for an instance generation request for a VuMark target which is still processing.

VuMark targets are created through the Target Manager portal rather than through the API, so no test can hold a real VuMark target in the processing state.

.. _unverified-model-target-generation-failure:

Model Target generation failures
--------------------------------

:Category: inherently-unverifiable
:API: Model Target Web API

The mock can finish dataset generation with a ``failed`` status and an ``error`` object.

Real Vuforia cannot be made to fail generation on demand.

.. _unverified-model-target-generation-warning:

Model Target generation warnings
--------------------------------

:Category: never-attempted
:API: Model Target Web API

The mock can add a ``warning`` object to a dataset which finished successfully.

The shape of that object comes from Vuforia's documentation rather than from a warning which a real dataset carried.

.. _unverified-model-target-failed-dataset-name:

The name of a failed Model Target dataset
-----------------------------------------

:Category: inherently-unverifiable
:API: Model Target Web API

A download request for a dataset which is not ready reports the dataset's training status.
The mock reports ``not-started`` for the whole processing window, as real Vuforia does for a dataset which was just created, and ``failed`` for a dataset whose generation failed.

The name which real Vuforia reports for a failed dataset has not been seen, because generation cannot be made to fail.

.. _unverified-model-target-invalid-state-based-configuration:

Malformed State-Based configuration documents
---------------------------------------------

:Category: inherently-unverifiable
:API: Model Target Web API

The mock reports validation errors for malformed State-Based Model Target configuration documents.

Real Vuforia returns an internal server error for them, so there is no behavior to match.

.. _unverified-model-target-training-allowance:

The exhausted training allowance response
-----------------------------------------

:Category: inherently-unverifiable
:API: Model Target Web API

The mock can return Vuforia's ``TRAINING_ALLOWANCE_EXCEEDED`` response.

The response shape comes from a real rejection seen in CI rather than from documentation, but the allowance cannot be exhausted on demand, and cannot be restored afterwards, so no test can provoke it.

.. _unverified-model-target-signed-dataset-creation:

Signed Model Target dataset creation
------------------------------------

:Category: temporarily-unverifiable
:API: Model Target Web API

Creating a signed dataset, such as an advanced dataset with a state-based configuration, consumes the Vuforia account's Model Target training allowance.
The allowance is small, is shared across all CI jobs, and cannot be raised or reset.

These cases reach real Vuforia only when ``--verify-model-target-signing`` is given, so by default the mock's behavior for them is unverified.

.. _unverified-model-target-oauth2-client-credentials:

OAuth2 client-credential management
-----------------------------------

:Category: temporarily-unverifiable
:API: Model Target Web API

The mock serves the OAuth2 client-credential management routes, including creating, listing, updating and deleting credentials, and Vuforia's limit of 100 created credentials per account.

The Model Target test account does not have the scope for those routes, so they cannot be reached with the credentials which CI has.
