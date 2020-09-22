"""
Tests for running the mock server in Docker.
"""

import docker
from pathlib import Path

def test_build_and_run():
    repository_root = Path(__file__).parent.parent.parent
    client = docker.from_env()
    # Build containers
    dockerfile_path = repository_root / 'src/mock_vws/_flask_server/Dockerfile'
    image, build_logs = client.images.build(
        path=str(repository_root),
        dockerfile=str(dockerfile_path),
    )
    container = client.containers.run(image=image, detach=True)
    # Run containers

    # Add target using vws_python
    pass
