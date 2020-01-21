from flask import Flask

VWS_FLASK_APP = Flask(__name__)

@VWS_FLASK_APP.route('/targets', methods=['POST'])
def _():
    return ''
