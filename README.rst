VWS Mock
========

Mock the Vuforia Model Target Web API and VuMark generation with ``requests``, ``httpx``, or ``httpx2``.
Cloud Image Recognition, cloud image target management, and the VWQ service have been removed.

.. code-block:: console

   $ pip install vws-python-mock vws-python

The examples use ``vws-python`` as the client.

.. code-block:: python

   """Generate a VuMark instance using a mock."""

   from vws import VuMarkService
   from vws.vumark_accept import VuMarkAccept

   from mock_vws import MockVWS
   from mock_vws.database import VuMarkDatabase
   from mock_vws.target import VuMarkTarget

   target = VuMarkTarget(name="example-template")
   database = VuMarkDatabase(vumark_targets={target})
   with MockVWS() as mock:
       mock.add_vumark_database(vumark_database=database)
       client = VuMarkService(
           server_access_key=database.server_access_key,
           server_secret_key=database.server_secret_key,
       )
       result = client.generate_vumark_instance(
           target_id=target.target_id,
           instance_id="123",
           accept=VuMarkAccept.PNG,
       )
       assert result.startswith(b"\x89PNG")

See the `full documentation <https://vws-python.github.io/vws-python-mock/>`_ for Model Target configuration, HTTP transports, and containers.
