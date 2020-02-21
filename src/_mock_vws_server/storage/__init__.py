from flask import Flask, jsonify

STORAGE_FLASK_APP = Flask(__name__)


@STORAGE_FLASK_APP.route('/databases', methods=['GET'])
def get_databases() -> str:
    databases = []
    return jsonify(databases)
