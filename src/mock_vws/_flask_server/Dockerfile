FROM python:3.13-slim AS base
# We set this pretend version as we do not have Git in our path, and we do
# not care enough about having the version correct inside the Docker container
# to install it.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
# Avoid using root user.
# This avoids having to use ``--root-user-action=ignore`` with pip.
RUN useradd -ms /bin/bash myuser
USER myuser
COPY --chown=myuser:myuser . /app

# See https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
# For why we use this method of activating the virtual environment.
ENV VIRTUAL_ENV=/app/docker_venvs/.venv
ENV UV_PROJECT_ENVIRONMENT=/app/docker_venvs/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app
RUN python3 -m venv $VIRTUAL_ENV && \
    pip install --no-cache-dir uv==0.10.4 && \
    uv sync --no-cache
EXPOSE 5000
ENTRYPOINT ["python"]
HEALTHCHECK --interval=1s --timeout=10s --start-period=5s --retries=3 CMD ["python", "/app/src/mock_vws/_flask_server/healthcheck.py"]

FROM base AS vws
ENV VWS_HOST=0.0.0.0
CMD ["src/mock_vws/_flask_server/vws.py"]

FROM base AS vwq
ENV VWQ_HOST=0.0.0.0
CMD ["src/mock_vws/_flask_server/vwq.py"]

FROM base AS target-manager
ENV TARGET_MANAGER_HOST=0.0.0.0
CMD ["src/mock_vws/_flask_server/target_manager.py"]
