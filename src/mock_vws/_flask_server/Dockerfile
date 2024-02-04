FROM python:3.12-slim as base
# We set this pretend version as we do not have Git in our path, and we do
# not care enough about having the version correct inside the Docker container
# to install it.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
COPY . /app
WORKDIR /app
RUN pip install --root-user-action=ignore --upgrade pip .
EXPOSE 5000
ENTRYPOINT ["python"]

FROM base as vws
ENV VWS_HOST=0.0.0.0
CMD ["src/mock_vws/_flask_server/vws.py"]

FROM base as vwq
ENV VWQ_HOST=0.0.0.0
CMD ["src/mock_vws/_flask_server/vwq.py"]

FROM base as target-manager
ENV TARGET_MANAGER_HOST=0.0.0.0
CMD ["src/mock_vws/_flask_server/target_manager.py"]
