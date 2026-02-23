"""Add INACTIVE_VUMARK_* credentials to existing secrets files.

Usage:
    export VWS_EMAIL_ADDRESS=...
    export VWS_PASSWORD=...
    export SECRETS_DIR=ci_secrets
    export PASSPHRASE_FOR_VUFORIA_SECRETS=...
    python admin/add_inactive_vumark_secrets.py

This script:
1. Creates a new inactive VuMark database via the Vuforia web UI.
2. Appends INACTIVE_VUMARK_* credentials to every
   vuforia_secrets_*.env file in SECRETS_DIR (skipping files that
   already have those fields).
3. Re-creates secrets.tar from SECRETS_DIR and re-encrypts to
   secrets.tar.gpg.
"""

import datetime
import os
import subprocess
import sys
from pathlib import Path

import vws_web_tools


def _create_and_get_inactive_vumark_details(
    email_address: str,
    password: str,
) -> "vws_web_tools.VuMarkDatabaseDict":
    """Create an inactive VuMark database and return its details."""
    time = datetime.datetime.now(tz=datetime.UTC).strftime(
        format="%Y-%m-%d-%H-%M-%S",
    )
    vumark_license_name = f"my-inactive-vumark-license-{time}"
    vumark_database_name = f"my-inactive-vumark-database-{time}"

    driver = vws_web_tools.create_chrome_driver()
    try:
        vws_web_tools.log_in(
            driver=driver,
            email_address=email_address,
            password=password,
        )
        vws_web_tools.wait_for_logged_in(driver=driver)
        vws_web_tools.create_license(
            driver=driver, license_name=vumark_license_name
        )
        vws_web_tools.create_vumark_database(
            driver=driver,
            database_name=vumark_database_name,
        )
        vumark_database_details = vws_web_tools.get_vumark_database_details(
            driver=driver,
            database_name=vumark_database_name,
        )
        vws_web_tools.delete_license(
            driver=driver, license_name=vumark_license_name
        )
    finally:
        driver.quit()

    return vumark_database_details


def main() -> None:
    """Create inactive VuMark credentials and update existing secrets."""
    email_address = os.environ["VWS_EMAIL_ADDRESS"]
    password = os.environ["VWS_PASSWORD"]
    secrets_dir = Path(os.environ.get("SECRETS_DIR", "ci_secrets"))
    passphrase = os.environ["PASSPHRASE_FOR_VUFORIA_SECRETS"]

    sys.stdout.write("Creating inactive VuMark database...\n")
    details = _create_and_get_inactive_vumark_details(
        email_address=email_address,
        password=password,
    )

    db_name = details["database_name"]
    access_key = details["server_access_key"]
    secret_key = details["server_secret_key"]
    new_lines = (
        "\nINACTIVE_VUMARK_VUFORIA_TARGET_MANAGER_DATABASE_NAME="
        f"{db_name}\n"
        "INACTIVE_VUMARK_VUFORIA_SERVER_ACCESS_KEY="
        f"{access_key}\n"
        "INACTIVE_VUMARK_VUFORIA_SERVER_SECRET_KEY="
        f"{secret_key}\n"
    )

    env_files = sorted(secrets_dir.glob("vuforia_secrets_*.env"))
    if not env_files:
        msg = f"No vuforia_secrets_*.env files found in {secrets_dir}"
        raise FileNotFoundError(msg)

    updated = 0
    skipped = 0
    for env_file in env_files:
        content = env_file.read_text()
        already_has = (
            "INACTIVE_VUMARK_VUFORIA_TARGET_MANAGER_DATABASE_NAME" in content
        )
        if already_has:
            skipped += 1
            continue
        env_file.write_text(content.rstrip("\n") + new_lines)
        updated += 1

    sys.stdout.write(
        f"Updated {updated} file(s), skipped {skipped}"
        " (already had fields).\n",
    )

    subprocess.run(  # noqa: S603
        ["tar", "cvf", "secrets.tar", str(secrets_dir)],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    sys.stdout.write("secrets.tar created.\n")

    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "gpg",
            "--yes",
            "--batch",
            f"--passphrase={passphrase}",
            "--symmetric",
            "--cipher-algo",
            "AES256",
            "secrets.tar",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    sys.stdout.write("secrets.tar.gpg updated.\n")


if __name__ == "__main__":
    main()
