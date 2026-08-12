"""Flask server for the mock Vuforia web service."""

# The Docker documentation is generated from the settings classes, so
# each setting is described where it is defined.  Settings which more
# than one application reads are described here, once.
TARGET_MANAGER_BASE_URL_DESCRIPTION = """\
The base URL of the target manager container, as seen from this container.

This must include a scheme, for example
``http://vuforia-target-manager-mock:5000``.
"""

RESPONSE_DELAY_SECONDS_DESCRIPTION = """\
The number of seconds to wait before sending each response.
"""
