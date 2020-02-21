from flask import Flask, jsonify
from requests import codes
from typing import Tuple

STORAGE_FLASK_APP = Flask(__name__)

VUFORIA_DATABASES = []

@STORAGE_FLASK_APP.route('/databases', methods=['GET'])
def get_databases() -> Tuple[str, int]:
    databases = [database.to_dict() for database in VUFORIA_DATABASES]
    return jsonify(databases), codes.OK


@STORAGE_FLASK_APP.route('/databases', methods=['POST'])
def create_database() -> Tuple[str, int]:
    database = {}
    return jsonify(database), codes.CREATED
