``MockVWS`` intercepts requests to Vuforia made with `requests`_, `httpx`_ or `HTTPX2`_.

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

A ``MockVWS`` instance can also decorate a function:

.. code-block:: python

    """Make a request to the Vuforia mock from a decorated function."""

    import requests

    from mock_vws import MockVWS
    from mock_vws.database import CloudDatabase

    mock = MockVWS()
    mock.add_cloud_database(cloud_database=CloudDatabase())


    @mock
    def get_summary() -> None:
        """Make a request which uses the Vuforia mock."""
        requests.get(url="https://vws.vuforia.com/summary", timeout=30)


    get_summary()

Each call of a decorated function gets its own databases and targets, so decorated functions do not affect each other.
A ``with`` block, by contrast, shares one set of databases and targets with every other use of the same instance.

See :ref:`mock-api-reference` for details of what can be changed and how.

.. _requests: https://pypi.org/project/requests/
.. _httpx: https://pypi.org/project/httpx/
.. _HTTPX2: https://httpx2.pydantic.dev/
