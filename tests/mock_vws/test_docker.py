"""
Tests for running the mock server in Docker.
"""

import docker
from pathlib import Path
import requests

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
    storage_container = client.containers.run(
        image=storage_image,
        detach=True,
        publish_all_ports=True,
    )
    storage_container.reload()
    import pdb; pdb.set_trace()
    # vws_container = client.containers.run(image=vws_image, detach=True)
    # vwq_container = client.containers.run(image=vwq_image, detach=True)
    # Run containers

    # Add target using vws_python
    pass
