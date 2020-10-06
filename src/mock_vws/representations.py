from typing import List, Optional, TypedDict, Union


class TargetDict(TypedDict):
    """
    A dictionary type which represents a target.
    """

    name: str
    width: float
    image_base64: str
    active_flag: bool
    processing_time_seconds: Union[int, float]
    processed_tracking_rating: int
    application_metadata: Optional[str]
    target_id: str
    last_modified_date: str
    delete_date_optional: Optional[str]
    upload_date: str


class DatabaseDict(TypedDict):
    """
    A dictionary type which represents a database.
    """

    database_name: str
    server_access_key: str
    server_secret_key: str
    client_access_key: str
    client_secret_key: str
    state_name: str
    targets: List[TargetDict]
