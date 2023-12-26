"""
Create licenses and target databases for the tests to run against.
"""

import datetime
import os

import vws_web_tools
from selenium import webdriver

time = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d-%H-%M-%S")
email_address = os.environ["VWS_EMAIL_ADDRESS"]
password = os.environ["VWS_PASSWORD"]
license_name = f"my-license-{time}"
driver = webdriver.Safari()
vws_web_tools.log_in(
    driver=driver,
    email_address=email_address,
    password=password,
)
vws_web_tools.wait_for_logged_in(driver=driver)
vws_web_tools.create_license(driver=driver, license_name=license_name)
