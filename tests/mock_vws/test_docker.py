"""
Tests for running the mock server in Docker.
"""

import docker
from pathlib import Path

def test_build_and_run():
    repository_root = Path(__file__).parent.parent.parent
    client = docker.from_env()
    # Build containers
    dockerfile_dir = repository_root / 'src/mock_vws/_flask_server/Dockerfile'

    base_dockerfile = dockerfile_dir / 'Dockerfile-base'
    storage_dockerfile = dockerfile_dir / 'Dockerfile-storage'
    vws_dockerfile = dockerfile_dir / 'Dockerfile-vws'
    vwq_dockerfile = dockerfile_dir / 'Dockerfile-vwq'
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
    storage_container = client.containers.run(image=storage_image, detach=True)
    vws_container = client.containers.run(image=vws_image, detach=True)
    vwq_container = client.containers.run(image=vwq_image, detach=True)
    # Run containers

    # Add target using vws_python
    pass
