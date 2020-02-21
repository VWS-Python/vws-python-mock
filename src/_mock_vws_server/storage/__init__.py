from flask import Flask, jsonify
from requests import codes
from typing import Tuple

STORAGE_FLASK_APP = Flask(__name__)


@STORAGE_FLASK_APP.route('/databases', methods=['GET'])
def get_databases() -> Tuple[str, int]:
    databases = []
    return jsonify(databases), codes.OK


@STORAGE_FLASK_APP.route('/databases', methods=['POST'])
def create_database() -> Tuple[str, int]:
    database = {}
    return jsonify(database), codes.CREATED
