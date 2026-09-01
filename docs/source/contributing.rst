Contributing to |project|
=========================

Contributions to this repository must pass tests and linting.

CI is the canonical source of truth.

Install contribution dependencies
---------------------------------

Install Python dependencies in a virtual environment.

.. code-block:: console

   $ pip install --editable '.[dev]'

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

To connect to Vuforia, Vuforia target databases must be created via the Vuforia Web UI.
Then, secret keys must be set as environment variables.

The test infrastructure allows those keys to be set in the file :file:`vuforia_secrets.env`.
See :file:`vuforia_secrets.env.example` for the environment variables to set.

Do not use a target database that you are using for other purposes.
This is because the test suite adds and deletes targets.

To create a target database, first create a license key in the `Vuforia License Manager`_.
Then, add a database from the `Vuforia Target Manager`_.

To find the environment variables to set in the :file:`vuforia_secrets.env` file, visit the Target Database in the `Vuforia Target Manager`_ and view the "Database Access Keys".

Two Cloud databases are necessary in order to run all the Cloud Target tests.
One of those must be an inactive project.
The script creates the inactive project automatically by deleting its license.

VuMark tests require one VuMark database.

Targets sometimes get stuck at the "Processing" stage meaning that they cannot be deleted.
When this happens, create a new target database to use for testing.

To create databases without using the browser, use :file:`admin/create_secrets_files.py`:

.. code-block:: bash

      $ export VWS_EMAIL_ADDRESS=...
      $ export VWS_PASSWORD=...
      $ export NEW_SECRETS_DIR=...
      # You may have to run this a few times, but it is idempotent.
      $ python admin/create_secrets_files.py
      # Each generated file gets its own active Cloud database credentials.

For the complete archive and GitHub Actions setup procedure, see
:doc:`ci-setup`.

.. _Vuforia License Manager: https://developer.vuforia.com/vui/develop/licenses
.. _Vuforia Target Manager: https://developer.vuforia.com/vui/develop/databases

Skipping Some Tests
-------------------

Use the following custom ``pytest`` options to skip some tests:

.. code-block:: text

   --skip-real           Skip tests for Real Vuforia
   --skip-mock           Skip tests for In Memory Mock Vuforia
   --skip-docker_in_memory
                         Skip tests for In Memory version of Docker application
   --skip-docker_build_tests
                         Skip tests for building Docker images

Verifying signed Model Target requests
--------------------------------------

Creating an advanced Model Target dataset with a state-based configuration is a "signed" request: the real Vuforia signs the trained dataset, and each signing consumes the account's Model Target training allowance.
The allowance is small (roughly 20 signings), it is shared by every CI job and every concurrent run, and it cannot be raised or reset.
Verifying signed requests on every run exhausted the allowance within hours and then made every CI run fail with ``TRAINING_ALLOWANCE_EXCEEDED``.

The signed test cases therefore run against the mock backends on every run, but are skipped against the real Vuforia by default.
To verify them against the real Vuforia, for example after the allowance has recovered, opt in with:

.. code-block:: text

   --verify-model-target-signing
                         Run signed Model Target dataset tests against
                         the real Vuforia

The equivalent unsigned requests (a standard dataset, or an advanced dataset without a state-based configuration) are far cheaper and are verified against the real Vuforia on every run.
With enough traffic even unsigned dataset creation can be rejected with ``TRAINING_ALLOWANCE_EXCEEDED``; an unexpected allowance rejection is reported as an expected failure (xfail) rather than a test failure, and the affected tests pass again automatically once the allowance recovers.

Documentation
-------------

Documentation is built on Read the Docs.

Run the following commands to build and view documentation locally:

.. code-block:: console

   $ uv run --extra=dev sphinx-build -M html docs/source docs/build -W
   $ python -c 'import os, webbrowser; webbrowser.open("file://" + os.path.abspath("docs/build/html/index.html"))'

Continuous Integration
----------------------

See :doc:`ci-setup`.

Learnings about VWS
-------------------

Vuforia Web Services, at the time of writing, does not behave exactly as documented.

The following list includes details of differences between VWS and expected or documented behavior.

When attempting to delete a target immediately after creating it, a ``FORBIDDEN`` response is returned.
This is because the target goes into a processing state.

``image`` is required for ``POST /targets``, but it is documented as not mandatory.

The ``tracking_rating`` returned by ``GET /targets/<target_id>`` can be -1.

The database summary from ``GET /summary`` has multiple undocumented return fields.

The database summary from ``GET /summary`` is not immediately accurate.

The documentation page `Vuforia Query Web API`_ states that the ``Content-Type`` header must be set to ``multipart/form-data``.
However, it must be set to ``multipart/form-data; boundary=<BOUNDARY>`` where ``<BOUNDARY>`` is the boundary used when encoding the form data.

The documentation page `Vuforia Query Web API`_ states that ``Content-Type`` will be the only response header.
This is not the case.

The documentation page `Vuforia Query Web API`_ states that 10 is the maximum allowed value of ``max_num_results``.
However, the maximum allowed value is 50.

A response to an invalid query may have an ``application/json`` content type but include text (not JSON) data.

After deleting a target, for up to approximately 30 seconds, matching it with a query returns a 500 response.

A target with the name ``\uffff`` gets stuck in processing.

The documentation page `Vuforia Query Web API`_ states that "The API accepts requests with unknown data fields, and ignore the unknown fields.".
This is not the case.

The documentation page `Vuforia Query Web API`_ states "Maximum image size: 2.1 MPixel. 512 KiB for JPEG, 2MiB for PNG".
However, JPEG images up to 2MiB are accepted.

There is no documented limit on the number of pixels in an image, but ``POST /targets`` returns ``ImageTooLarge`` for an image with more than 37748736 pixels, whatever its file size, aspect ratio or color space.
An image of a single color has a tiny file size whatever its dimensions, which is how this limit is reached.
The Query API applies no such limit.
It applies only its maximum width and height of 30000 pixels.

The ``request_count`` in a database summary is always ``0``.

The documentation for the target summary report says "Note: tracking_rating and ``reco_rating`` are provided only when status = success.".
However, ``reco_rating`` is never provided and ``tracking_rating`` is provided even when the status is "failed".

.. _Vuforia Query Web API: https://developer.vuforia.com/library/vuforia-engine/web-api/vuforia-query-web-api/

Release Process
---------------

See :doc:`release-process`.
