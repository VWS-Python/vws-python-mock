import base64
import datetime
import io
from typing import Set

import pytz
import requests

from mock_vws.database import VuforiaDatabase
from mock_vws.states import States
from mock_vws.target import Target

from ._constants import STORAGE_BASE_URL


def get_all_databases() -> Set[VuforiaDatabase]:
    # TODO use the storage URL to get details then cast to VuforiaDatabase
    response = requests.get(url=STORAGE_BASE_URL + '/databases')
    response_json = response.json()
    databases = set()
    for database_dict in response_json:
        database_name = database_dict['database_name']
        server_access_key = database_dict['server_access_key']
        server_secret_key = database_dict['server_secret_key']
        client_access_key = database_dict['client_access_key']
        client_secret_key = database_dict['client_secret_key']
        state = States(database_dict['state_value'])
        # TODO state

        new_database = VuforiaDatabase(
            database_name=database_name,
            server_access_key=server_access_key,
            server_secret_key=server_secret_key,
            client_access_key=client_access_key,
            client_secret_key=client_secret_key,
            state=state,
        )

        for target_dict in database_dict['targets']:
            # TODO fill this in
            name = target_dict['name']
            active_flag = target_dict['active_flag']
            width = target_dict['width']
            image_base64 = target_dict['image_base64']
            image_bytes = base64.b64decode(image_base64)
            image = io.BytesIO(image_bytes)
            processing_time_seconds = target_dict['processing_time_seconds']
            application_metadata = target_dict['application_metadata']

            target = Target(
                name=name,
                active_flag=active_flag,
                width=width,
                image=image,
                processing_time_seconds=processing_time_seconds,
                application_metadata=application_metadata,
            )
            target.target_id = target_dict['target_id']
            gmt = pytz.timezone('GMT')
            target.last_modified_date = datetime.datetime.fromordinal(
                target_dict['last_modified_date_ordinal']
            )
            target.last_modified_date = target.last_modified_date.replace(
                tzinfo=gmt
            )
            target.upload_date = datetime.datetime.fromordinal(
                target_dict['upload_date_ordinal']
            )
            target.upload_date = target.upload_date.replace(tzinfo=gmt)
            delete_date_optional_ordinal = target_dict[
                'delete_date_optional_ordinal']
            if delete_date_optional_ordinal:
                target.delete_date = datetime.datetime.fromordinal(
                    delete_date_optional_ordinal
                )
                target.delete_date = target.delete_date.replace(tzinfo=gmt)
            new_database.targets.append(target)

        databases.add(new_database)

    return databases
