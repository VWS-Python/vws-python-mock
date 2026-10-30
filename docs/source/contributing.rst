Contributing to |project|
=========================

Contributions to this repository must pass tests and linting.

CI is the canonical source of truth.

Install contribution dependencies
---------------------------------

Install Python dependencies in a virtual environment.

.. code-block:: console

   $ pip install --editable . --group dev

Spell checking requires ``enchant``.
This can be installed on macOS, for example, with `Homebrew`_:

.. code-block:: console

   $ brew install enchant

and on Ubuntu with ``apt``:

.. code-block:: console

   $ apt-get install -y enchant

Install ``pre-commit`` hooks:

.. code-block:: console

   $ prek install

Linting
-------

Run lint tools either by committing, or with:

.. code-block:: console

   $ prek run --all-files --hook-stage pre-commit --verbose
   $ prek run --all-files --hook-stage pre-push --verbose
   $ prek run --all-files --hook-stage manual --verbose

.. _Homebrew: https://brew.sh

Running Tests
-------------

Create an environment variable file for secrets:

.. code-block:: console

   $ cp vuforia_secrets.env.example vuforia_secrets.env

Some tests require Vuforia credentials.
To run these tests, add the Vuforia credentials to the file :file:`vuforia_secrets.env`.
See :ref:`connecting-to-vuforia`.

Then run ``pytest``:

.. code-block:: console

   $ pytest

.. _connecting-to-vuforia:

Connecting to Vuforia
---------------------

Local mock tests use synthetic credentials and do not need a Vuforia account.
Real-service checks use VuMark database credentials and separate Model Target OAuth2 credentials.
Use ``admin/create_secrets_files.py`` to provision the supported credentials.
See :doc:`ci-setup` for the encrypted archive setup.

Skipping Some Tests
-------------------

The tests run against several backends: the real Vuforia, the in-memory mock, and the Flask applications of the mock served in the test process.
The last of these exercises the handlers which the Docker deployment runs, but not the split between its containers.
The tests in ``server/tests/vws_mock_server_tests/test_docker.py`` build and run the containers for that.
The `pytest-multi-backend`_ plugin adds options which skip some tests:

.. code-block:: text

   --skip-backend=real   Skip tests against the real Vuforia
   --skip-backend=mock   Skip tests against the in-memory mock Vuforia
   --skip-backend=flask_in_process
                         Skip tests against the Flask applications served
                         in the test process
   --skip-marker=requires_docker_build
                         Skip tests which build and run the Docker images

Give an option once per backend or marker to skip.

.. _pytest-multi-backend: https://adamtheturtle.github.io/pytest-multi-backend/

Shared backend setup
--------------------

Adapters supply ``base_vws_url`` and the VuMark/Model Target credential fixtures.
``verify_mock_vuforia`` sets up VuMark generation, and ``verify_model_target_mock_vuforia`` sets up Model Targets.
Their mock-only counterparts are ``mock_only_vuforia`` and ``model_target_mock_only_vuforia``.
Setup fixtures yield ``None`` and leave backend selection inside the adapter.

Installed contract tests
------------------------

The ``contract-tests`` project builds ``vws-mock-contract-tests`` with an explicit shared fixture plugin.
The ``test-backends`` project builds the core repository's adapter plugin separately.
See :file:`contract-tests/README.rst` for installation, invocation and revision compatibility.

Container deployment tests
--------------------------

The deployment tests build and run three separate services through the Docker Python SDK.
They use the Docker engine selected by the current Docker configuration by default:

.. code-block:: console

   $ uv run --group=dev pytest server/tests/vws_mock_server_tests/test_docker.py

.. _socktainer-setup:

To run the same tests with Apple's container runtime, complete the runtime installation steps in :ref:`apple-container-setup`, then install `Socktainer`_ 1.5.2 or later.
It provides the Docker-compatible API used by the Python deployment tests:

.. code-block:: console

   $ brew install socktainer
   $ socktainer --no-auto-start --no-docker-context

Keep Socktainer running in that terminal.
In another terminal, select its socket for the test command:

.. code-block:: console

   $ DOCKER_HOST="unix://$HOME/.socktainer/container.sock" \
       uv run --group=dev pytest server/tests/vws_mock_server_tests/test_docker.py

The deployment tests automatically negotiate the API version.

Both configurations exercise native health checks, published HTTP ports, application behavior and restarts.
Running the mock directly with Apple's CLI uses the same images and is documented in :ref:`apple-container-setup`.
The target manager uses an automatically published port.
VWS keeps an explicit loopback binding so its report download URLs are known before startup.
Test containers, image tags and networks are removed after the run, including when setup fails.
Hosted CI continues to use Docker.
Apple deployment validation runs on a local Mac.

.. _Socktainer: https://github.com/socktainer/socktainer


Verifying signed Model Target requests
--------------------------------------

Creating an advanced Model Target dataset with a state-based configuration or a standard dataset with inline CAD data is a "signed" request: the real Vuforia signs the trained dataset, and each signing consumes the account's Model Target training allowance.
The allowance is small (roughly 20 signings), it is shared by every CI job and every concurrent run, and it cannot be raised or reset.
Verifying signed requests on every run exhausted the allowance within hours and then made every CI run fail with ``TRAINING_ALLOWANCE_EXCEEDED``.

The signed test cases therefore run against the mock backends on every run, but are skipped against the real Vuforia by default.
To verify them against the real Vuforia, for example after the allowance has recovered, opt in with:

.. code-block:: text

   --verify-model-target-signing
                         Run signed Model Target dataset tests against
                         the real Vuforia

The equivalent unsigned requests (a standard dataset, or an advanced dataset without a state-based configuration) are far cheaper and are verified against the real Vuforia on every run.
With enough traffic even unsigned dataset creation can be rejected with ``TRAINING_ALLOWANCE_EXCEEDED``; an unexpected allowance rejection is reported as an expected failure rather than a test failure, and the affected tests pass again automatically once the allowance recovers.

Retrying transient real Model Target failures
---------------------------------------------

The load balancer in front of the real Model Target Web API sometimes answers a perfectly good request with a gateway error, or drops the connection.
That is nothing to do with the contract under test, and a rerun of the same job passes, so a small number of retries is applied to requests which are safe to repeat.

The policy is in ``tests/mock_vws/utils/model_target_retries.py``.
It applies only while a test is running against the real Model Target backend, and only to ``GET`` requests: repeating a dataset creation can create a second dataset and can consume the account's Model Target training allowance, so mutating requests are sent exactly once.
Three attempts are made, with an exponential backoff with jitter of up to ten seconds, using ``tenacity``.
A request which still fails transiently on the last attempt is not hidden: the response is returned as it is, so the assertion reports the real status and body.

The mock backends are unaffected, so tests which configure a mock to answer with a 5xx still get that response immediately.

This is separate from the repository-wide ``pytest-retry`` configuration, which retries a test only when it fails with one of the exception types returned by ``pytest_set_filtered_exceptions`` in the top level ``conftest.py``.
The Model Target tests assert on ``requests.Response`` objects, so a gateway error reaches ``pytest-retry`` as an ``AssertionError`` and is never retried by it.
Widening that allowlist would retry every failing assertion in the suite, which is why the Model Target policy sits in the request helper instead, before the assertion.

Documentation
-------------

Documentation is built on Read the Docs.

Run the following commands to build and view documentation locally:

.. code-block:: console

   $ uv run --group=dev sphinx-build -M html docs/source docs/build -W
   $ python -c 'import os, webbrowser; webbrowser.open("file://" + os.path.abspath("docs/build/html/index.html"))'

Continuous Integration
----------------------

See :doc:`ci-setup`.

Release Process
---------------

See :doc:`release-process`.

Release notes
-------------

Write user-facing changes as Markdown in ``newsfragments/<issue>.change.md``.
Towncrier writes one Markdown file per version, used directly for GitHub release notes.
Invalid fragment names fail release assembly.
