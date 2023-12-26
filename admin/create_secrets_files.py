"""
Create licenses and target databases for the tests to run against.

Usage:

    $ export VWS_EMAIL_ADDRESS=...
    $ export VWS_PASSWORD=...
    # For ``make update-secrets`` to work, this has to be ``./ci_secrets``, or
    # you have to copy the secrets there later.
    $ export NEW_SECRETS_DIR=...
    $ export EXISTING_SECRETS_FILE=/existing/file/with/inactive/db/creds
    # You may have to run this a few times, but it is idempotent.
    $ python admin/create_secrets_files.py

"""

import datetime
import os
import sys
import textwrap
from pathlib import Path

import vws_web_tools
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException

email_address = os.environ["VWS_EMAIL_ADDRESS"]
password = os.environ["VWS_PASSWORD"]
new_secrets_dir = Path(os.environ["NEW_SECRETS_DIR"]).expanduser()
existing_secrets_file = Path(os.environ["EXISTING_SECRETS_FILE"]).expanduser()
assert existing_secrets_file.exists(), existing_secrets_file
load_dotenv(dotenv_path=existing_secrets_file)
new_secrets_dir.mkdir(exist_ok=True)

num_databases = 100
required_files = [
    (new_secrets_dir / f"vuforia_secrets_{i}.env")
    for i in range(num_databases)
]
files_to_create = [file for file in required_files if not file.exists()]
start_number = len(list(new_secrets_dir.glob("*")))
driver = None

while files_to_create:
    if driver is None:
        # With Safari we get a bunch of errors / timeouts.
        driver = webdriver.Chrome()
    file = files_to_create[-1]
    sys.stdout.write(f"Creating database {file.name}\n")
    time = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d-%H-%M-%S")
    license_name = f"my-license-{time}"
    database_name = f"my-database-{time}"

    vws_web_tools.log_in(
        driver=driver,
        email_address=email_address,
        password=password,
    )
    vws_web_tools.wait_for_logged_in(driver=driver)
    try:
        vws_web_tools.create_license(driver=driver, license_name=license_name)
    except TimeoutException:
        sys.stderr.write("Timed out waiting for license creation\n")
        driver.quit()
        driver = None
        continue

    vws_web_tools.create_database(
        driver=driver,
        database_name=database_name,
        license_name=license_name,
    )

    try:
        database_details = vws_web_tools.get_database_details(
            driver=driver,
            database_name=database_name,
        )
    except TimeoutException:
        sys.stderr.write("Timed out waiting for database to be created\n")
        continue
    finally:
        driver.quit()
        driver = None

    file_contents = textwrap.dedent(
        f"""\
        VUFORIA_TARGET_MANAGER_DATABASE_NAME={database_details["database_name"]}
        VUFORIA_SERVER_ACCESS_KEY={database_details["server_access_key"]}
        VUFORIA_SERVER_SECRET_KEY={database_details["server_secret_key"]}
        VUFORIA_CLIENT_ACCESS_KEY={database_details["client_access_key"]}
        VUFORIA_CLIENT_SECRET_KEY={database_details["client_secret_key"]}

        INACTIVE_VUFORIA_TARGET_MANAGER_DATABASE_NAME={os.environ["INACTIVE_VUFORIA_TARGET_MANAGER_DATABASE_NAME"]}
        INACTIVE_VUFORIA_SERVER_ACCESS_KEY={os.environ["INACTIVE_VUFORIA_SERVER_ACCESS_KEY"]}
        INACTIVE_VUFORIA_SERVER_SECRET_KEY={os.environ["INACTIVE_VUFORIA_SERVER_SECRET_KEY"]}
        INACTIVE_VUFORIA_CLIENT_ACCESS_KEY={os.environ["INACTIVE_VUFORIA_CLIENT_ACCESS_KEY"]}
        INACTIVE_VUFORIA_CLIENT_SECRET_KEY={os.environ["INACTIVE_VUFORIA_CLIENT_SECRET_KEY"]}
        """,
    )

    file.write_text(file_contents)
    sys.stdout.write(f"Created database {file.name}\n")
    files_to_create.pop()
