``MockVWS`` intercepts requests to Vuforia made with `requests`_ or `httpx`_.

.. code-block:: python

    """Make a request to the Vuforia Web Services API mock."""

    import requests

    from mock_vws import MockVWS
    from mock_vws.database import CloudDatabase

    with MockVWS() as mock:
        database = CloudDatabase()
        mock.add_cloud_database(cloud_database=database)
        # This will use the Vuforia mock.
        requests.get(url="https://vws.vuforia.com/summary", timeout=30)

By default, an exception will be raised if any requests to unmocked addresses are made.

See :ref:`mock-api-reference` for details of what can be changed and how.

.. _requests: https://pypi.org/project/requests/
.. _httpx: https://pypi.org/project/httpx/
