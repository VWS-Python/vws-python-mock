from typing import Tuple

from flask import Flask
from requests import codes

CLOUDRECO_FLASK_APP = Flask(__name__)


@CLOUDRECO_FLASK_APP.route('/v1/query', methods=['POST'])
def query() -> Tuple[str, int]:
    return '', codes.OK
