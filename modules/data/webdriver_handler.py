"""
This module contains functions related to managing selenium's webdriver

Functions:
    initialize_chrome_driver()
    create_drivers()
"""

# Standard Library Imports
import uuid
import psutil
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Third-Party Library Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.remote_connection import RemoteConnection
from webdriver_manager.chrome import ChromeDriverManager


DRIVER_STARTUP_SEM = asyncio.Semaphore(2)

def cleanup_chromedrivers(session_tag: str):
    """
    Kill only Chrome/ChromeDriver processes containing the given session_tag.
    Requires a session_tag to avoid killing unrelated Chrome instances.
    """
    if not session_tag:
        raise ValueError("[cleanup_chromedrivers] session_tag is required to prevent killing all Chrome processes")

    killed = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = " ".join(proc.info.get('cmdline') or [])
            name = proc.info.get('name', '')
            if not name:
                continue
            if ('chrome' in name.lower() or 'chromedriver' in name.lower()) and session_tag in cmd:
                proc.kill()
                killed.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print(f"[cleanup_chromedrivers] Killed {len(killed)} processes with tag='{session_tag}'")
    return killed


# Creates chrome drivers with arguments suited to scraping urls
def initialize_chrome_driver():
    session_tag = f"chrome_session_{uuid.uuid4()}"

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--enable-javascript')
    chrome_options.add_argument(f"--user-data-dir=/tmp/{session_tag}") # tag visible in cmdline for cleanup_chromedrivers to kill zombie processes 
 

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

            # set driver settings
            driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
            driver.set_page_load_timeout(30)                      # 30 sec max for page load (otherwise, revert to backup)
            driver.command_executor._client_config.timeout = 30   # timeout for http hangs 

            try:
                import urllib3
                driver.command_executor._conn = urllib3.PoolManager(retries=0) # disable http retries
            except Exception as e:
                print(f"[initialize_chrome_driver] Could not disable retries: {e}")
            driver._session_tag = session_tag

            print(f"[initialize_chrome_driver] created a driver with tag: {session_tag}")
            return driver

        except Exception as e:
            print(f"[initialize_chrome_driver] Failed to initialize ChromeDriver. Retrying... ({retry_count + 1}/10)")
            print("[initialize_chrome_driver] Error exception:", e)
            retry_count += 1
            time.sleep(1)
    raise RuntimeError("Failed to initialize ChromeDriver after several attempts")


# calls initialize_chrome_driver asynchronously
async def create_drivers(num_of_drivers): # In most cases num_of_drivers = urls_to_return
    loop = asyncio.get_event_loop()

    async def _one():
      async with DRIVER_STARTUP_SEM:
          return await loop.run_in_executor(None, initialize_chrome_driver)
    drivers = await asyncio.gather(*[_one() for _ in range(num_of_drivers)])
    
    # print out session info for all drivers
    session_info = [
        f"  - Driver {i+1}: session_id={getattr(driver, 'session_id', None)} executor={getattr(driver.command_executor, '_url', None)}"
        for i, driver in enumerate(drivers)]
    session_info_str = "\n".join(session_info)
    print(f"[create_drivers] Created {len(drivers)} driver(s):\n{session_info_str}")
    return drivers
