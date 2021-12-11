FROM python:3.10.0-slim-buster
RUN apt update --yes
# git is needed for setuptools-scm.
RUN apt install --yes git
COPY . /app
WORKDIR /app
RUN pip install .
EXPOSE 5000
ENTRYPOINT ["python"]
