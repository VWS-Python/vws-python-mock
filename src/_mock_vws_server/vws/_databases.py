
import base64
import datetime
import email.utils
import io
import json
import uuid
import pytz
from typing import Set, Tuple, Dict

import requests
from flask import Flask, Response, request
from flask_json_schema import JsonSchema, JsonValidationError
from requests import codes
from mock_vws._constants import ResultCodes, TargetStatuses
from mock_vws._database_matchers import get_database_matching_server_keys
from mock_vws._mock_common import json_dump
from mock_vws.database import VuforiaDatabase
from mock_vws.target import Target
from mock_vws.states import States

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
            width= target_dict['width']
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
            # import pdb; pdb.set_trace()
            target.last_modified_date = datetime.datetime.fromordinal(target_dict['last_modified_date_ordinal'])
            target.last_modified_date = target.last_modified_date.replace(tzinfo=gmt)
            delete_date_optional_ordinal = target_dict['delete_date_optional_ordinal']
            if delete_date_optional_ordinal:
                target.delete_date = datetime.datetime.fromordinal(delete_date_optional_ordinal)
                target.delete_date = target.delete_date.replace(tzinfo=gmt)
            new_database.targets.append(target)

        databases.add(new_database)

    return databases
