"""Create licenses and target databases for the tests to run against.

See the instructions in the contributing guide in the documentation.
"""

import datetime
import os
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import vws_web_tools
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from vws_web_tools import DatabaseDict, VuMarkDatabaseDict


def _create_and_get_database_details(
    driver: "WebDriver",
    email_address: str,
    password: str,
    license_name: str,
    database_name: str,
) -> "DatabaseDict | None":
    """Create a cloud database and get its details.

    Returns database details or None if a timeout occurs.
    """
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
        return None

    vws_web_tools.create_cloud_database(
        driver=driver,
        database_name=database_name,
        license_name=license_name,
    )

    try:
        return vws_web_tools.get_database_details(
            driver=driver,
            database_name=database_name,
        )
    except TimeoutException:
        sys.stderr.write("Timed out waiting for database to be created\n")
        return None


def _create_and_get_vumark_details(
    driver: "WebDriver",
    vumark_database_name: str,
) -> "VuMarkDatabaseDict | None":
    """Create a VuMark database and get its details.

    Returns VuMark database details or None if a timeout occurs.
    """
    try:
        vws_web_tools.create_vumark_database(
            driver=driver,
            database_name=vumark_database_name,
        )
    except TimeoutException:
        sys.stderr.write("Timed out waiting for VuMark database creation\n")
        return None

    try:
        return vws_web_tools.get_vumark_database_details(
            driver=driver,
            database_name=vumark_database_name,
        )
    except TimeoutException:
        sys.stderr.write(
            "Timed out waiting for VuMark database to be created\n"
        )
        return None


def _generate_secrets_file_content(
    database_details: "DatabaseDict",
    vumark_details: "VuMarkDatabaseDict",
) -> str:
    """Generate the content of a secrets file."""
    return textwrap.dedent(
        text=f"""\
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

        VUMARK_VUFORIA_TARGET_MANAGER_DATABASE_NAME={vumark_details["database_name"]}
        VUMARK_VUFORIA_SERVER_ACCESS_KEY={vumark_details["server_access_key"]}
        VUMARK_VUFORIA_SERVER_SECRET_KEY={vumark_details["server_secret_key"]}
        """,
    )


def main() -> None:
    """Create secrets files."""
    email_address = os.environ["VWS_EMAIL_ADDRESS"]
    password = os.environ["VWS_PASSWORD"]
    new_secrets_dir = Path(os.environ["NEW_SECRETS_DIR"]).expanduser()
    existing_secrets_file = Path(
        os.environ["EXISTING_SECRETS_FILE"]
    ).expanduser()
    if not existing_secrets_file.exists():
        msg = f"Existing secrets file does not exist: {existing_secrets_file}"
        raise FileNotFoundError(msg)
    load_dotenv(dotenv_path=existing_secrets_file)
    new_secrets_dir.mkdir(exist_ok=True)

    num_databases = 100
    required_files = [
        (new_secrets_dir / f"vuforia_secrets_{i}.env")
        for i in range(num_databases)
    ]
    files_to_create = [file for file in required_files if not file.exists()]
    shared_vumark_details: VuMarkDatabaseDict | None = None

    while shared_vumark_details is None:
        vumark_driver = vws_web_tools.create_chrome_driver()
        time = datetime.datetime.now(tz=datetime.UTC).strftime(
            format="%Y-%m-%d-%H-%M-%S",
        )
        vumark_database_name = f"my-vumark-database-{time}"
        vws_web_tools.log_in(
            driver=vumark_driver,
            email_address=email_address,
            password=password,
        )
        vws_web_tools.wait_for_logged_in(driver=vumark_driver)
        shared_vumark_details = _create_and_get_vumark_details(
            driver=vumark_driver,
            vumark_database_name=vumark_database_name,
        )
        vumark_driver.quit()

    driver: WebDriver | None = None
    while files_to_create:
        if driver is None:
            driver = vws_web_tools.create_chrome_driver()
        file = files_to_create[-1]
        sys.stdout.write(f"Creating database {file.name}\n")
        time = datetime.datetime.now(tz=datetime.UTC).strftime(
            format="%Y-%m-%d-%H-%M-%S",
        )
        license_name = f"my-license-{time}"
        database_name = f"my-database-{time}"

        database_details = _create_and_get_database_details(
            driver=driver,
            email_address=email_address,
            password=password,
            license_name=license_name,
            database_name=database_name,
        )
        if database_details is None:
            driver.quit()
            driver = None
            continue

        driver.quit()
        driver = None

        file_contents = _generate_secrets_file_content(
            database_details=database_details,
            vumark_details=shared_vumark_details,
        )
        file.write_text(data=file_contents)
        sys.stdout.write(f"Created database {file.name}\n")
        files_to_create.pop()


if __name__ == "__main__":
    main()
