"""The recognition-count operation supplied by a mock backend.

Neither mock counts recognitions, because real Vuforia's counts lag behind
its queries by longer than a test runs. Each mock instead has its own way of
being told what the counts are.
"""

from typing import Protocol, runtime_checkable

from mock_vws.database import CloudDatabase


@runtime_checkable
class SeedRecognitionCounts(Protocol):
    """A backend operation which sets recognition counts on a target."""

    def __call__(
        self,
        *,
        vuforia_database: CloudDatabase,
        target_id: str,
        current_month_recos: int,
        previous_month_recos: int,
        total_recos: int,
    ) -> None:
        """Set the target's recognition counts on the running mock backend.

        Args:
            vuforia_database: The database which the target is in.
            target_id: The ID of the target to set recognition counts of.
            current_month_recos: The number of recognitions in the current
                month.
            previous_month_recos: The number of recognitions in the previous
                month.
            total_recos: The total number of recognitions of the target.
        """
        ...
