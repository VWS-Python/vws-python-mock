from typing import Set

import requests

from mock_vws.database import VuforiaDatabase

from ._constants import STORAGE_BASE_URL


def get_all_databases() -> Set[VuforiaDatabase]:
    response = requests.get(url=STORAGE_BASE_URL + '/databases')
    return set(
        VuforiaDatabase.from_dict(database_dict=database_dict)
        for database_dict in response.json()
    )
