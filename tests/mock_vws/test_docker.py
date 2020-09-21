"""
Tests for running the mock server in Docker.
"""

import docker

def test_build_and_run():
    client = docker.from_env()
    # Build containers
    dockerfile_path = ...
    image, build_logs = client.images.build(path=dockerfile_path)
    container = client.containers.run(image=image, detach=True)
    # Run containers

    # Add target using vws_python
    pass
