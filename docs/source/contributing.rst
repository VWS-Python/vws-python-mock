Contributing
============

Contributions to this repository must pass tests and linting.

CI is the canonical source of truth.

Install contribution dependencies
---------------------------------

Install Python dependencies in a virtual environment.

.. prompt:: bash

   pip install --editable .[dev]

Spell checking requires ``enchant``.
This can be installed on macOS, for example, with `Homebrew`_:

.. prompt:: bash

   brew install enchant

and on Ubuntu with ``apt``:

.. prompt:: bash

   apt-get install -y enchant

Linting
-------

Run lint tools:

.. prompt:: bash

   make lint

To fix some lint errors, run the following:

.. prompt:: bash

   make fix-lint

.. _Homebrew: https://brew.sh

Running Tests
-------------

Create an environment variable file for secrets:

.. prompt:: bash

   cp vuforia_secrets.env.example vuforia_secrets.env

Some tests require Vuforia credentials.
To run these tests, add the Vuforia credentials to the file :file:`vuforia_secrets.env`.
See :ref:`connecting-to-vuforia`.

Then run ``pytest``:

.. prompt:: bash

   pytest

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

Two databases are necessary in order to run all the tests.
One of those must be an inactive project.
To create an inactive project, delete the license key associated with a database.

Targets sometimes get stuck at the "Processing" stage meaning that they cannot be deleted.
When this happens, create a new target database to use for testing.

To create databases without using the browser, use :file:`admin/create_secrets_files.py`.
See instructions in that file.

.. _Vuforia License Manager: https://developer.vuforia.com/vui/develop/licenses
.. _Vuforia Target Manager: https://developer.vuforia.com/vui/develop/databases

Skipping Some Tests
-------------------

Use the following custom ``pytest`` options to skip some tests:

.. prompt:: bash

  --skip-real           Skip tests for Real Vuforia
  --skip-mock           Skip tests for In Memory Mock Vuforia
  --skip-docker_in_memory
                        Skip tests for In Memory version of Docker application
  --skip-docker_build_tests
                        Skip tests for building Docker images

Documentation
-------------

Documentation is built on Read the Docs.

Run the following commands to build and view documentation locally:

.. prompt:: bash

   make docs
   make open-docs

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

The ``request_count`` in a database summary is always ``0``.

The documentation for the target summary report says "Note: tracking_rating and ``reco_rating`` are provided only when status = success.".
However, ``reco_rating`` is never provided and ``tracking_rating`` is provided even when the status is "failed".

.. _Vuforia Query Web API: https://library.vuforia.com/web-api/vuforia-query-web-api

Release Process
---------------

See :doc:`release-process`.
