"""Sample Model Target requests shared across tests."""

import json

VIEW: dict[str, object] = {
    "name": "view-name",
    "guideViewPosition": {
        "translation": [0, 0, 5],
        "rotation": [0, 0, 0, 1],
    },
}


MODEL: dict[str, object] = {
    "name": "model-name",
    "cadDataUrl": "https://example.com/model.glb",
    "views": [VIEW],
}


UNAUTHENTICATED_DATASET_REQUEST: dict[str, object] = {
    "name": "dataset-name",
    "targetSdk": "10.18",
    "models": [MODEL],
}


STATE_CONFIGURATION = json.dumps(
    obj={
        "version": "1.0",
        "default_state": "assembled",
        "states": {
            "assembled": {"base_scene": 0},
            "disassembled": {"base_scene": 0},
        },
    },
)
