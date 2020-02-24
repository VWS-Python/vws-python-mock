from flask import Flask, jsonify, request
from requests import codes
from typing import Tuple, List
from mock_vws.database import VuforiaDatabase

STORAGE_FLASK_APP = Flask(__name__)

VUFORIA_DATABASES: List[VuforiaDatabase] = []

@STORAGE_FLASK_APP.route('/databases', methods=['GET'])
def get_databases() -> Tuple[str, int]:
    databases = [database.to_dict() for database in VUFORIA_DATABASES]
    return jsonify(databases), codes.OK


@STORAGE_FLASK_APP.route('/databases', methods=['POST'])
def create_database() -> Tuple[str, int]:
    server_access_key = request.json['server_access_key']
    server_secret_key = request.json['server_secret_key']
    client_access_key = request.json['client_access_key']
    client_secret_key = request.json['client_secret_key']
    database_name = request.json['database_name']
    # TODO this will have to be converted by enum
    state = request.json['state']

    database = VuforiaDatabase(
        server_access_key=server_access_key,
        server_secret_key=server_secret_key,
        client_access_key=client_access_key,
        client_secret_key=client_secret_key,
        database_name=database_name,
        state=state,
    )
    VUFORIA_DATABASES.append(database)
    return jsonify(database.to_dict()), codes.CREATED
