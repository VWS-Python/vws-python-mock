|Build Status| |codecov| |Updates|

VWS Python Mock
===============

Python mock for the Vuforia Web Services (VWS) API and the Vuforia Web Query API.

Contributing
------------

See `CONTRIBUTING.rst <./CONTRIBUTING.rst>`_ for details on how to contribute to this project.

Installation
------------

.. code:: sh

    pip install vws-python-mock

This requires Python 3.7+.
Get in touch with ``adamdangoor@gmail.com`` if you would like to use this with another language.

Mocking Vuforia
---------------

Requests made to Vuforia can be mocked.
Using the mock redirects requests to Vuforia made with ``requests`` to an in-memory implementation.

.. code:: python

    import requests
    from mock_vws import MockVWS

    with MockVWS():
        # This will use the Vuforia mock.
        requests.get('https://vws.vuforia.com/summary')

However, an exception will be raised if any requests to unmocked addresses are made.

Allowing HTTP requests to unmocked addresses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This can be done by setting the parameter ``real_http`` to ``True`` in the context manager’s instantiation.

For example:

.. code:: python

    import requests
    from mock_vws import MockVWS

    with MockVWS(real_http=True):
        # This will use the Vuforia mock.
        requests.get('https://vws.vuforia.com/summary')
        # No exception is raised when a request is made to an unmocked address.
        requests.get('http://example.com')

Authentication
~~~~~~~~~~~~~~

Connecting to the Vuforia Web Services requires an access key and a secret key.
The mock also requires these keys as it provides realistic authentication support.

By default, the mock uses random strings as the access and secret keys.

It is possible to access these keys when using the context manager as follows:

.. code:: python

    from mock_vws import MockVWS

    with MockVWS() as mock:
        access_key = mock.server_access_key
        secret_key = mock.server_secret_key

To set custom keys, set any of the following parameters in the context manager’s instantiation:

-  ``server_access_key``
-  ``server_secret_key``
-  ``client_access_key``
-  ``client_secret_key``

The mock does not check whether the access and secret keys are valid.
It only checks whether the keys used to set up the mock instance match those used to create requests.

Setting the database name
~~~~~~~~~~~~~~~~~~~~~~~~~

This can be done with the ``database_name`` parameter.
By default this is a random string.

Mocking error states
~~~~~~~~~~~~~~~~~~~~

Sometimes Vuforia is in an error state, where requests don’t work.
You may want your application to handle these states gracefully, and so it is possible to make the mock emulate these states.

To change the state, use the ``state`` parameter when calling the mock.

.. code:: python

    import requests
    from mock_vws import MockVWS, States

    def my_function():
        with MockVWS(state=States.PROJECT_INACTIVE) as mock:
            ...

The states available in ``States`` are:

- ``WORKING``.
  This is the default state of the mock.
- ``PROJECT_INACTIVE``.
  This happens when the license key has been deleted.

The mock is tested against the real Vuforia Web Services.
This ensures that the implemented features of the mock behave, at least to some extent, like the real Vuforia Web Services.
However, the mocks of these error states are based on observations as they cannot be reliably reproduced.

Custom base URLs
~~~~~~~~~~~~~~~~

``MockVWS`` mocks the Vuforia Web Services (VWS) API and the Vuforia Web Query API.
These APIs have base URLs ``https://vws.vuforia.com`` and ``https://cloudreco.vuforia.com`` respectively.

``MockVWS`` takes the optional parameters ``base_vws_url`` and ``base_vwq_url`` to modify the base URLs of the mocked endpoints.

Processing time
~~~~~~~~~~~~~~~

Vuforia Web Services processes targets for varying lengths of time.
The mock, by default, processes targets for half a second.
To change the processing time, use the ``processing_time_seconds`` parameter.

Differences between the mock and the real Vuforia Web Services
--------------------------------------------------------------

The mock attempts to be realistic, but it was built without access to the source code of the original API.
Please report any issues `here <https://github.com/adamtheturtle/vws-python-mock/issues>`__.
There is no attempt to make the image matching realistic.

Speed and summary accuracy
~~~~~~~~~~~~~~~~~~~~~~~~~~

The mock responds much more quickly than the real Vuforia Web Services.

Targets in the mock are set to ‘processing’ for half a second by default.
This is customisable, with the ``processing_time_seconds`` parameter.
In the real Vuforia Web Services, the processing stage takes varying lengths of time.

The database summary in the real Vuforia Web Services takes some time to account for images.
Sometimes the real summary skips image states such as the processing state.
The mock is accurate immediately.

Image quality and ratings
~~~~~~~~~~~~~~~~~~~~~~~~~

Targets are assigned a rating between 0 and 5 of how good they are for tracking purposes.
In the mock this is a random number between 0 and 5.

Image targets which are not suited to detection are given ‘failed’ statuses.
The criteria for these images is not defined by the Vuforia documentation.
The mock is more forgiving than the real Vuforia Web Services.
Therefore, an image given a ‘success’ status by the mock may not be given a ‘success’ status by the real Vuforia Web Services.

When updating an image for a target on the real Vuforia Web Services, the rating may stay the same.
The mock changes the rating for a target to a different random number when the image is changed.

Matching targets in the processing state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Matching a target which is in the processing state sometimes returns a successful response with no results.
Sometimes a 500 (INTERNAL SERVER ERROR) response is given.
The mock always gives a 500 response.

Matching deleted targets
~~~~~~~~~~~~~~~~~~~~~~~~

Matching a target which has been deleted returns a 500 (INTERNAL SERVER ERROR) response within the first few seconds.
This timeframe is not consistent on the real Vuforia Web Services.
On the mock, this timeframe is three seconds by default.
``MockVWS`` takes a parameter ``query_recognizes_deletion_seconds`` to change this.

Accepted date formats for the Query API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Query API documentation is not clear on which date formats are expected exactly in the ``Date`` header.
The mock is strict.
That is, it accepts only a few date formats, and rejects all others.
If you find a date format which is accepted by the real Query API but rejected by the mock, please create a GitHub issue.

Targets stuck in processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~

On the real Vuforia Web Services, targets sometimes get stuck in the processing state.
For example, targets with the name ``\uffff`` get stuck in the processing state.
On the mock, no targets get stuck in the processing state.

Database summary quotas
~~~~~~~~~~~~~~~~~~~~~~~

The database summary endpoint returns quotas which match the quotas given for a free license.

.. |Build Status| image:: https://travis-ci.org/adamtheturtle/vws-python-mock.svg?branch=master
   :target: https://travis-ci.com/adamtheturtle/vws-python-mock
.. |codecov| image:: https://codecov.io/gh/adamtheturtle/vws-python-mock/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/adamtheturtle/vws-python-mock
.. |Updates| image:: https://pyup.io/repos/github/adamtheturtle/vws-python-mock/shield.svg
   :target: https://pyup.io/repos/github/adamtheturtle/vws-python-mock/
