Differences between the mock and the real Vuforia Web Services
==============================================================

The mock attempts to be realistic, but it was built without access to the source code of the original API.
Please report any issues `here <https://github.com/VWS-Python/vws-python-mock/issues>`__.

Image matching
--------------

Vuforia's image matching is proprietary and we do not intend to accurately copy it.
Instead, we aim for simple algorithms which are fast and are good enough for testing purposes.
The image matcher is configurable, using :paramref:`~mock_vws.MockVWS.match_checker`.

Speed and summary accuracy
--------------------------

The mock responds much more quickly than the real Vuforia Web Services.

Targets in the mock are set to 'processing' for half a second by default.
This is customizable, with the :paramref:`~mock_vws.MockVWS.processing_time_seconds` parameter.
In the real Vuforia Web Services, the processing stage takes varying lengths of time.

The database summary in the real Vuforia Web Services takes some time to account for images and recognitions.
Sometimes the real summary skips image states such as the processing state.
The mock is accurate immediately with regards to images.
The mock does not count recognitions.

Image quality and ratings
-------------------------

Targets are assigned a rating between 0 and 5 of how good they are for tracking purposes.
In the mock this is calculated from the image quality, differently to how Vuforia does this.
This is customizable with the :paramref:`~mock_vws.MockVWS.target_tracking_rater` parameter.

Image targets which are not suited to detection are given 'failed' statuses.
The criteria for these images is not defined by the Vuforia documentation.
The mock is more forgiving than the real Vuforia Web Services.
Therefore, an image given a 'success' status by the mock may not be given a 'success' status by the real Vuforia Web Services.

Accepted date formats for the Query API
---------------------------------------

The Query API documentation is not clear on which date formats are expected exactly in the ``Date`` header.
The mock is strict.
That is, it accepts only a few date formats, and rejects all others.
If you find a date format which is accepted by the real Query API but rejected by the mock, please create a GitHub issue.

Targets stuck in processing
---------------------------

On the real Vuforia Web Services, targets sometimes get stuck in the processing state.
For example, targets with the name ``\uffff`` get stuck in the processing state.
On the mock, no targets get stuck in the processing state.

Database summary quotas
-----------------------

The database summary endpoint returns quotas which match the quotas given for a free license.

``transfer-encoding`` headers
-----------------------------

Sometimes the real Query API sends responses with ``transfer-encoding: chunked`` and no ``Content-Length`` header.
The mock does not do this.

``Content-Encoding`` headers
----------------------------

The real Query API sends some responses with ``Content-Encoding: gzip``.
The mock Query API sends all responses with ``Content-Encoding: gzip``.

NGINX Error cases
-----------------

Vuforia uses NGINX.
This has error handling which is not duplicated in the mock.
For example, Vuforia returns a 400 (``BAD REQUEST``) response if a header or cookie is given which is larger than 8 KiB.

Result codes
------------

Result codes are returned by requests to Vuforia to help with debugging.
See `VWS API Result Codes <https://library.vuforia.com/web-api/cloud-targets-web-services-api#result-codes>`_ for details of the available result codes.
There are some result codes which the mock cannot return.

These are:

* ``DateRangeError``
* ``ProjectHasNoAPIAccess``
* ``ProjectSuspended``
* ``RequestQuotaReached``
* ``TargetQuotaReached``
* ``TooManyRequests``

``Content-Length`` headers
--------------------------

When the given ``Content-Length`` header does not match the length of the given data, the mock server (written with Flask) will not behave as the real Vuforia Web Services behaves.

Header cases
------------

The mock does not necessarily match Vuforia for all header cases.
