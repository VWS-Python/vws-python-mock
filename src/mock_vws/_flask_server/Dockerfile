FROM ghcr.io/astral-sh/uv:0.10.4-python3.13-trixie-slim AS base
# We set this pretend version as we do not have Git in our path, and we do
# not care enough about having the version correct inside the Docker container
# to install it.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
# Avoid using root user.
RUN useradd -ms /bin/bash myuser
USER myuser
COPY --chown=myuser:myuser . /app

# See https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
# For why we use this method of activating the virtual environment.
ENV UV_PROJECT_ENVIRONMENT=/app/docker_venvs/.venv
ENV PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

WORKDIR /app
RUN uv sync --no-cache
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
