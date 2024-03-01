import pytest


@pytest.mark.usefixtures("verify_mock_vuforia")
class TestVuMarkInstanceGeneration:
    """
    Tests for generating VuMark instances.
    """

    def test_generate_vumark_instance(self) -> None:
        pass

    def test_target_does_not_exist(self) -> None:
        pass

    def test_instance_id_does_not_exist(self) -> None:
        pass

    def test_target_status_is_processing(self) -> None:
        pass

    def test_target_status_is_failed(self) -> None:
        pass

    def test_cloud_target(self) -> None:
        pass

    def test_invalid_accept_header(self) -> None:
        pass
