FROM python:3.9.1-slim-buster
RUN apt update --yes
# git is needed for setuptools-scm.
RUN apt install --yes git
COPY . /app
WORKDIR /app
RUN pip install .
EXPOSE 5000
ENTRYPOINT ["python"]
CMD ["src/mock_vws/_flask_server/target_manager.py"]
