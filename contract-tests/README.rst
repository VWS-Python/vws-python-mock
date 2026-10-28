VWS mock contract tests
=======================

This project contains shared fixtures, helpers and contracts for the Vuforia Web Services and Model Target APIs.
It is a development dependency for projects which implement the Vuforia APIs.

Build and install
-----------------

Build all workspace wheels from the repository root:

.. code-block:: console

   $ uv build --all-packages --wheel --out-dir dist
   $ uv pip install dist/*.whl

The initial package version is ``0.0.0``.
Install the suite, core library and built-in adapter package from the same repository commit.
For Git installations, use the ``contract-tests`` and ``test-backends`` subdirectories at that commit.

Run the installed suite from outside the source checkout:

.. code-block:: console

   $ python -m pytest \
       -p vws_mock_contract_tests.fixtures.plugin \
       -p vws_mock_test_backends.vuforia_backends \
       --pyargs vws_mock_contract_tests \
       --skip-backend=real

The shared plugin provides clients, prepared requests and the retry allowlist.
The adapter plugin supplies service URLs, credentials, capabilities and setup fixtures.
Public setup fixtures yield ``None`` once the service is ready and keep backend selection internal.
Another repository can supply its own explicitly loaded adapter plugin.
The shared package has no dependency on the mock implementation or Flask.

Core CI compatibility
---------------------

Import-only modules under ``tests/mock_vws`` preserve the existing CI selectors.
The assertions have one source in ``vws_mock_contract_tests``.
Core coverage measures the packaged source and omits the forwarding modules.
The root test configuration avoids collecting the packaged tests a second time.

The consumer integration test builds wheels and checks them in a fresh environment:

.. code-block:: console

   $ uv run --group=dev pytest \
       --confcutdir=contract-tests/consumer \
       -c contract-tests/consumer/pytest.ini \
       contract-tests/consumer/test_installed_suite.py

The consumer's dependency and lifecycle checks are explicit pytest plugins.
