FROM ghcr.io/astral-sh/uv:0.13.1-python3.15-trixie-slim AS runtime
# We set this pretend version as we do not have Git in our path, and we do
# not care enough about having the version correct inside the Docker container
# to install it.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
# Avoid using root user. Use an explicit UID so the container does not rely on
# the host being able to resolve the account name.
# Create /app here because the legacy (non-BuildKit) builder creates
# WORKDIR directories owned by root, not the current user.
RUN useradd --create-home --shell /bin/bash --uid 10001 myuser \
    && mkdir /app \
    && chown 10001:10001 /app
USER 10001

# See https://pythonspeed.com/articles/activate-virtualenv-dockerfile/
# For why we use this method of activating the virtual environment.
ENV UV_PROJECT_ENVIRONMENT=/app/docker_venvs/.venv
ENV PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

WORKDIR /app

FROM runtime AS builder
# Install the locked dependencies before copying the source, so that
# source edits do not invalidate the dependency layer.
COPY --chown=10001:10001 pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-cache --no-dev --extra server --no-install-workspace
COPY --chown=10001:10001 . /app
RUN uv sync --locked --no-cache --no-dev --extra server --no-editable

FROM runtime AS base
COPY --from=builder --chown=10001:10001 /app/docker_venvs/.venv /app/docker_venvs/.venv
EXPOSE 5000
ENTRYPOINT ["python"]
HEALTHCHECK --interval=1s --timeout=10s --start-period=5s --retries=3 CMD ["python", "-m", "vws_mock_server.healthcheck"]

FROM base AS vws
ENV VWS_HOST=0.0.0.0
CMD ["-m", "vws_mock_server.vws"]

FROM base AS vwq
ENV VWQ_HOST=0.0.0.0
CMD ["-m", "vws_mock_server.vwq"]

FROM base AS target-manager
ENV TARGET_MANAGER_HOST=0.0.0.0
CMD ["-m", "vws_mock_server.target_manager"]
