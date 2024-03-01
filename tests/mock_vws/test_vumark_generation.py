import pytest


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestVuMarkInstanceGeneration:
    """
    Tests for generating VuMark instances.
    """

    # Content type: svg+xml, image/png, application/pdf
    def test_generate_vumark_instance(self) -> None:
        target_id = "..."
        url = "https://vws.vuforia.com/targets/{target_id}/instances"
        # TODO: Fill this in

    def test_target_does_not_exist(self) -> None:
        url = "https://vws.vuforia.com/targets/{target_id}/instances"

    def test_invalid_instance_id(self) -> None:
        # Negative, too large, float, illegal characters
        # too many hex characters
        # string too long
        pass

    def test_target_status_is_processing(self) -> None:
        pass

    def test_target_status_is_failed(self) -> None:
        pass

    def test_cloud_target(self) -> None:
        pass

    def test_invalid_accept_header(self) -> None:
        pass


# TODO: Fill in tests
# TODO: Look at query / cloud target validators for tests
# TODO: Make a VuMark instance database
# TODO: Make a VuMark instance in the database
# TODO: Add VuMark database credentials to secrets
# TODO: Add new secrets to GitHub Actions
