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


VUMARK_TEMPLATE_SVG_FILE_PATH = Path(__file__).with_name("vumark_template.svg")


def _create_and_get_database_details(
    driver: "WebDriver",
    email_address: str,
    password: str,
    license_name: str,
    database_name: str,
) -> "DatabaseDict":
    """Create a cloud database and get its details.

    Returns database details.
    """
    vws_web_tools.log_in(
        driver=driver,
        email_address=email_address,
        password=password,
    )
    vws_web_tools.wait_for_logged_in(driver=driver)
    vws_web_tools.create_license(driver=driver, license_name=license_name)

    vws_web_tools.create_cloud_database(
        driver=driver,
        database_name=database_name,
        license_name=license_name,
    )

    return vws_web_tools.get_database_details(
        driver=driver,
        database_name=database_name,
    )


def _create_and_get_vumark_details(
    driver: "WebDriver",
    vumark_database_name: str,
) -> "VuMarkDatabaseDict":
    """Create a VuMark database and get its details.

    Returns VuMark database details.
    """
    vws_web_tools.create_vumark_database(
        driver=driver,
        database_name=vumark_database_name,
    )

    return vws_web_tools.get_vumark_database_details(
        driver=driver,
        database_name=vumark_database_name,
    )


def _generate_secrets_file_content(
    database_details: "DatabaseDict",
    vumark_details: "VuMarkDatabaseDict",
    inactive_database_details: "DatabaseDict",
    vumark_target_id: str,
) -> str:
    """Generate the content of a secrets file."""
    return textwrap.dedent(
        text=f"""\
        VUFORIA_TARGET_MANAGER_DATABASE_NAME={database_details["database_name"]}
        VUFORIA_SERVER_ACCESS_KEY={database_details["server_access_key"]}
        VUFORIA_SERVER_SECRET_KEY={database_details["server_secret_key"]}
        VUFORIA_CLIENT_ACCESS_KEY={database_details["client_access_key"]}
        VUFORIA_CLIENT_SECRET_KEY={database_details["client_secret_key"]}

        INACTIVE_VUFORIA_TARGET_MANAGER_DATABASE_NAME={inactive_database_details["database_name"]}
        INACTIVE_VUFORIA_SERVER_ACCESS_KEY={inactive_database_details["server_access_key"]}
        INACTIVE_VUFORIA_SERVER_SECRET_KEY={inactive_database_details["server_secret_key"]}
        INACTIVE_VUFORIA_CLIENT_ACCESS_KEY={inactive_database_details["client_access_key"]}
        INACTIVE_VUFORIA_CLIENT_SECRET_KEY={inactive_database_details["client_secret_key"]}

        VUMARK_VUFORIA_TARGET_MANAGER_DATABASE_NAME={vumark_details["database_name"]}
        VUMARK_VUFORIA_TARGET_ID={vumark_target_id}
        VUMARK_VUFORIA_SERVER_ACCESS_KEY={vumark_details["server_access_key"]}
        VUMARK_VUFORIA_SERVER_SECRET_KEY={vumark_details["server_secret_key"]}
        """,
    )


def _create_and_get_vumark_target_id(
    driver: "WebDriver",
    vumark_database_name: str,
    vumark_template_name: str,
) -> str:
    """Upload a VuMark template and get its target ID."""
    target_id = vws_web_tools.upload_vumark_template(
        driver=driver,
        database_name=vumark_database_name,
        svg_file_path=VUMARK_TEMPLATE_SVG_FILE_PATH,
        template_name=vumark_template_name,
        width=100.0,
    )
    if isinstance(target_id, str):
        return target_id

    msg = "Expected `upload_vumark_template` to return a string target ID."
    raise RuntimeError(msg)


def _create_vuforia_resource_names() -> tuple[str, str, str, str]:
    """Create names for Vuforia resources."""
    time = datetime.datetime.now(tz=datetime.UTC).strftime(
        format="%Y-%m-%d-%H-%M-%S",
    )
    return (
        f"my-license-{time}",
        f"my-database-{time}",
        f"my-vumark-database-{time}",
        f"my-vumark-template-{time}",
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
    inactive_database_details: DatabaseDict = {
        "database_name": os.environ[
            "INACTIVE_VUFORIA_TARGET_MANAGER_DATABASE_NAME"
        ],
        "server_access_key": os.environ["INACTIVE_VUFORIA_SERVER_ACCESS_KEY"],
        "server_secret_key": os.environ["INACTIVE_VUFORIA_SERVER_SECRET_KEY"],
        "client_access_key": os.environ["INACTIVE_VUFORIA_CLIENT_ACCESS_KEY"],
        "client_secret_key": os.environ["INACTIVE_VUFORIA_CLIENT_SECRET_KEY"],
    }
    new_secrets_dir.mkdir(exist_ok=True)

    num_databases = 100
    required_files = [
        (new_secrets_dir / f"vuforia_secrets_{i}.env")
        for i in range(num_databases)
    ]
    files_to_create = [file for file in required_files if not file.exists()]
    driver: WebDriver | None = None

    while files_to_create:
        if driver is None:
            driver = vws_web_tools.create_chrome_driver()
        file = files_to_create[-1]
        sys.stdout.write(f"Creating database {file.name}\n")
        (
            license_name,
            database_name,
            vumark_database_name,
            vumark_template_name,
        ) = _create_vuforia_resource_names()

        try:
            database_details = _create_and_get_database_details(
                driver=driver,
                email_address=email_address,
                password=password,
                license_name=license_name,
                database_name=database_name,
            )
        except TimeoutException:
            sys.stderr.write(
                "Timed out waiting for database setup/details after retries\n"
            )
            driver.quit()
            driver = None
            continue

        try:
            vumark_details = _create_and_get_vumark_details(
                driver=driver,
                vumark_database_name=vumark_database_name,
            )
        except TimeoutException:
            sys.stderr.write(
                "Timed out waiting for VuMark setup/details after retries\n"
            )
            driver.quit()
            driver = None
            continue

        try:
            vumark_target_id = _create_and_get_vumark_target_id(
                driver=driver,
                vumark_database_name=vumark_database_name,
                vumark_template_name=vumark_template_name,
            )
        except TimeoutException:
            sys.stderr.write(
                "Timed out waiting for VuMark template upload after retries\n"
            )
            driver.quit()
            driver = None
            continue

        driver.quit()
        driver = None

        file_contents = _generate_secrets_file_content(
            database_details=database_details,
            vumark_details=vumark_details,
            inactive_database_details=inactive_database_details,
            vumark_target_id=vumark_target_id,
        )
        file.write_text(data=file_contents)
        sys.stdout.write(f"Created database {file.name}\n")
        files_to_create.pop()


if __name__ == "__main__":
    main()
