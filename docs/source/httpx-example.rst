``MockVWS`` also intercepts requests made with `httpx`_.

.. code-block:: python

   """Make a request to the Vuforia Web Services API mock using httpx."""

   import httpx

   from mock_vws import MockVWS
   from mock_vws.database import CloudDatabase

   with MockVWS() as mock:
       database = CloudDatabase()
       mock.add_cloud_database(cloud_database=database)
       # This will use the Vuforia mock.
       httpx.get(url="https://vws.vuforia.com/summary", timeout=30)

.. _httpx: https://pypi.org/project/httpx/
