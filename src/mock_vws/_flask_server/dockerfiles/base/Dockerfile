FROM python:3.8-slim-buster
RUN apt update --yes
RUN apt install --yes git
RUN apt install --yes gcc
COPY . /app
WORKDIR /app
RUN pip install --upgrade pip setuptools wheel
RUN pip install .
EXPOSE 5000
ENTRYPOINT ["python"]
