Using the mock redirects requests to Vuforia made with `httpx`_ to an in-memory implementation.

.. code-block:: python

   """Make a request to the Vuforia Web Services API mock."""

   import httpx

   from mock_vws import MockVWSForHttpx
   from mock_vws.database import CloudDatabase

   with MockVWSForHttpx() as mock:
       database = CloudDatabase()
       mock.add_cloud_database(cloud_database=database)
       # This will use the Vuforia mock.
       httpx.get(url="https://vws.vuforia.com/summary", timeout=30)

By default, an exception will be raised if any requests to unmocked addresses are made.

See :ref:`mock-api-reference` for details of what can be changed and how.

.. _httpx: https://pypi.org/project/httpx/
