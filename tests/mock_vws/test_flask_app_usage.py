"""
Tests for the usage of the mock Flask application.
"""

class TestProcessingTime:
    """
    Tests for the time taken to process targets in the mock.
    """

    def test_default(self, image_file_failed_state: io.BytesIO) -> None:
        """
        By default, targets in the mock take 0.5 seconds to be processed.
        """
        database = VuforiaDatabase()
        vws_client = VWS(
            server_access_key=database.server_access_key,
            server_secret_key=database.server_secret_key,
        )
        with MockVWS() as mock:
            mock.add_database(database=database)

            target_id = vws_client.add_target(
                name='example',
                width=1,
                image=image_file_failed_state,
                active_flag=True,
                application_metadata=None,
            )
            start_time = datetime.now()

            while True:
                target_details = vws_client.get_target_record(
                    target_id=target_id,
                )

                status = target_details.status
                if status != TargetStatuses.PROCESSING:
                    elapsed_time = datetime.now() - start_time
                    # There is a race condition in this test - if it starts to
                    # fail, maybe extend the acceptable range.
                    assert elapsed_time < timedelta(seconds=0.55)
                    assert elapsed_time > timedelta(seconds=0.49)
                    return

class TestCustomQueryRecognizesDeletionSeconds:
    """
    Tests for setting the amount of time after a target has been deleted
    until it is not recognized by the query endpoint.
    """

class TestCustomQueryProcessDeletionSeconds:
    """
    Tests for setting the amount of time after a target has been deleted
    until it is not processed by the query endpoint.
    """

class TestDatabaseManagement:
    """
    TODO
    """

    def test_duplicate_keys(self) -> None:
        """
        It is not possible to have multiple databases with matching keys.
        """
        # Add one
        # Add another different
        # Add another conflict
        pass

    def test_give_no_details(self):
        # Random stuff
        pass

    def test_delete_database(self):
        # Add one
        # Delete
        # Add another one same
