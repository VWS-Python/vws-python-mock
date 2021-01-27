FROM python:3.9.1-slim-buster
RUN apt update --yes
# git is needed for setuptools-scm.
# gcc is needed to create the wheel for backports.zoneinfo, at least on Apple
# Silicon.
RUN apt install --yes git gcc
COPY . /app
WORKDIR /app
RUN pip install .
EXPOSE 5000
ENTRYPOINT ["python"]
