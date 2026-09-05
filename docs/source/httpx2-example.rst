``MockVWS`` also intercepts requests made with `HTTPX2`_, with no need for ``httpx2.alias_httpx()``.

.. code-block:: python

   """Make a request to the Vuforia Web Services API mock using httpx2."""

   import httpx2

   from mock_vws import MockVWS
   from mock_vws.database import CloudDatabase

   with MockVWS() as mock:
       database = CloudDatabase()
       mock.add_cloud_database(cloud_database=database)
       # This will use the Vuforia mock.
       httpx2.get(url="https://vws.vuforia.com/summary", timeout=30)

Asynchronous ``httpx`` and `HTTPX2`_ clients are intercepted as well.

.. _HTTPX2: https://httpx2.pydantic.dev/
