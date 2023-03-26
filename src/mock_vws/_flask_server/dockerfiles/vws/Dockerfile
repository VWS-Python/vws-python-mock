FROM python:3.11-slim-buster
RUN apt update && apt install -y gcc g++ libgl1-mesa-glx libglib2.0-0
COPY . /app
# We set this pretend version as we do not have Git in our path, and we do
# not care enough about having the version correct inside the Docker container
# to install it.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
ENV VWS_HOST=0.0.0.0
WORKDIR /app
RUN pip install --upgrade .
EXPOSE 5000
ENTRYPOINT ["python"]
CMD ["src/mock_vws/_flask_server/vws.py"]
