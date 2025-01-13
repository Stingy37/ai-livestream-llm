"""
This module contains functions related to managing selenium's webdriver
"""

# Standard Library Imports
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Third-Party Library Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


# Creates chrome drivers with arguments suited to scraping urls
def initialize_chrome_driver():
    print("created a driver")
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--enable-javascript')

    # Disable image loading
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)


    retry_count = 0
    while retry_count < 10:
        try:
            chromedriver_dir = ChromeDriverManager().install()
            chromedriver_path = os.path.join(os.path.dirname(chromedriver_dir), 'chromedriver')

            # Ensure the chromedriver is executable
            if not os.access(chromedriver_path, os.X_OK):
              os.chmod(chromedriver_path, 0o755)

            # print(f"Using chromedriver at: {chromedriver_path}")
            driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
            return driver
        except Exception as e:
            print(f"Failed to initialize ChromeDriver. Retrying... ({retry_count + 1}/10)")
            print("Error exception:", e)
            retry_count += 1
            time.sleep(1)
    raise RuntimeError("Failed to initialize ChromeDriver after several attempts")


# Calls initialize_chrome_driver asynchronously
async def create_drivers(num_of_drivers): # In most cases num_of_drivers = urls_to_return
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        drivers = await loop.run_in_executor(executor, lambda: [initialize_chrome_driver() for _ in range(num_of_drivers)])
    return drivers