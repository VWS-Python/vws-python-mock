"""
Tests for running the mock server in Docker.
"""

import docker
from pathlib import Path
import requests
from vws import VWS, CloudRecoService
from mock_vws.database import VuforiaDatabase
import json
import uuid

def test_build_and_run():
    repository_root = Path(__file__).parent.parent.parent
    client = docker.from_env()

    dockerfile_dir = repository_root / 'src/mock_vws/_flask_server/dockerfiles'
    base_dockerfile = dockerfile_dir / 'base' / 'Dockerfile'
    storage_dockerfile = dockerfile_dir / 'storage' / 'Dockerfile'
    vws_dockerfile = dockerfile_dir / 'vws' / 'Dockerfile'
    vwq_dockerfile = dockerfile_dir / 'vwq' / 'Dockerfile'

    base_tag = 'vws-mock:base'
    base_image, build_logs = client.images.build(
        path=str(repository_root),
        dockerfile=str(base_dockerfile),
        tag=base_tag,
    )

    storage_image, build_logs = client.images.build(
        path=str(repository_root),
        dockerfile=str(storage_dockerfile),
    )
    vws_image, build_logs = client.images.build(
        path=str(repository_root),
        dockerfile=str(vws_dockerfile),
    )
    vwq_image, build_logs = client.images.build(
        path=str(repository_root),
        dockerfile=str(vwq_dockerfile),
    )

    database = VuforiaDatabase()
    # TODO Randomize this once we pass it through to the Flask app, probably
    # with an environment variable.
    # storage_container_name = 'vws-mock-storage-' + uuid.uuid4().hex

    storage_container_name = 'vws-mock-storage'
    storage_exposed_port = '5000'

    storage_container = client.containers.run(
        image=storage_image,
        detach=True,
        name=storage_container_name,
        publish_all_ports=True,
    )
    vws_container = client.containers.run(
        image=vws_image,
        detach=True,
        name='vws-mock-vws-' + uuid.uuid4().hex,
    )
    vwq_container = client.containers.run(
        image=vwq_image,
        detach=True,
        name='vws-mock-vwq-' + uuid.uuid4().hex,
    )

    storage_container.reload()

    response = requests.post(
        url=f'http://0.0.0.0:{storage_exposed_port}',
        json=database.to_dict(),
    )

    # add_database_cmd = [
    #     'python',
    #     '-c',
    #     'import requests; requests.post(data=' + json.dumps(database.to_dict()) + ')',
    # ]
    # exit_code, output = storage_container.exec_run(cmd=add_database_cmd)

    import pdb; pdb.set_trace()
    # Add database to storage

    # Add target using vws_python
    vws_client = VWS(
        server_access_key=database.server_access_key,
        server_secret_key=database.server_secret_key,
    )

    # Query for target
    cloud_reco_client = CloudRecoService(
        client_access_key=database.client_access_key,
        client_secret_key=database.client_secret_key,
    )

    # Clean up containers
    pass
