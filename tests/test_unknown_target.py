"""
Tests for passing invalid target IDs to helpers which require a target ID to
be given.
"""

from vws import VWS


class TestInvalidGivenID:
    """
    Tests for giving an invalid ID to helpers which require a target ID to be
    given.
    """

    def test_invalid_given_id(self, client: VWS) -> None:
        """
        Giving an invalid ID to a helper which requires a target ID to be given
        causes an ``UnknownTarget`` exception to be raised.
        """
        funcs = (
            client.get_target_record,
            client.get_target_summary_report,
            client.delete_target,
        )

        for func in funcs:
            func(target_id='x')
