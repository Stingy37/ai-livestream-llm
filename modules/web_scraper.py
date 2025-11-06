"""
This module provides functions that related to returning text or images from a certain URL

Functions:
    google_search()

    fetch_and_process_slot()
    fetch_html()
    fetch_html_sync()
    fetch_pdf_content()

    fetch_images_off_specific_url()
    get_image_urls()
"""

# Standard Library Imports
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import re
from io import BytesIO
from itertools import count

# Third-Party Library Imports
import aiohttp
from langchain_community.document_transformers import MarkdownifyTransformer
from PyPDF2 import PdfReader

# Local Application/Library-Specific Imports
from modules.configs import database_executor, fetch_html_executor, cse_api_call_count, cse_api_call_lock
from modules.text_processing import filter_content, split_markdown_chunks
from modules.webdriver_handler import create_drivers
from modules.schema import ScrapedImageList, URL


#################################################################### debug info for webdrivers ###################################################


_SCRAPE_COUNTER = count(1)

def _new_scrape_id(prefix: str = "S") -> str:
    """Return a monotonic scrape id like 'S0001'."""
    return f"{prefix}{next(_SCRAPE_COUNTER):04d}"

def _driver_debug_info(driver):
    """Return (session_id, command_executor_url) for logging."""
    sid = getattr(driver, "session_id", None)
    try:
        ce_url = getattr(driver.command_executor, "_url", None)
    except Exception:
        ce_url = None
    return sid, ce_url


################################################################## google search not used ###################################################


# Searches google using queries from constants.py as the search term and returns URLs
async def google_search(session, query, api_key, se_id, number_to_return, search_images):
    global cse_api_call_count  # Counts how much times CSE API is called

    two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    url = 'https://www.googleapis.com/customsearch/v1'
    params = {
        'q': query,
        'key': api_key,
        'cx': se_id,
        'num': number_to_return,
        'gl': None,  # Geolocks the region
        'dateRestrict': 'd2',  # Restrict results to the last 2 days
        'searchType': 'image' if search_images else None
    }

    # Remove None values from params
    params = {k: v for k, v in params.items() if v is not None}

    api_start = time.time() # Temp
    print(f"[google_search] Making API request with params: {params}")
    async with cse_api_call_lock:
        cse_api_call_count += 1
        print(f"[google_search] API call count: {cse_api_call_count}")

    async with session.get(url, params=params) as response:
        if response.status != 200:
            print(f"[google_search] Error: API request failed with status code {response.status}")
            return []

        search_results = await response.json()
        print(f"[google_search] API response: {search_results}")

        items = search_results.get('items', [])
        api_end = time.time() # Temp
        print(f"[google_search] Time taken to get API response: {api_end - api_start}")

        if not items:
            print("[google_search] No items found in search results.")
            return []

        # Add a delay before returning the results to avoid concurrency issues
        await asyncio.sleep(2)
        return [item.get('link') for item in items]


#####################################################################################################################################


# Manages async operations of scrapping HTML AND creation of database (Not in this module)
async def fetch_and_process_slot(driver, primary_url, backup_url, process_to_db, semaphore, scrape_id = None):
    """
    Called by database handler and initiates the whole scraping process for one primary / backup slow

    Try primary URL; on failure and if backup_url exists, try backup with the same driver.
    Quit the driver once both attempts are done.
    """
    # Create/attach a scrape id for this slot
    if scrape_id is None:
        scrape_id = _new_scrape_id()
    try:
        setattr(driver, "_scrape_id", scrape_id)
    except Exception:
        pass

    sess, ce = _driver_debug_info(driver)
    print(f"[fetch_and_process_slot {scrape_id} sess={sess} ce={ce}] start primary={primary_url} backup={backup_url}")


    try:
        # primary scraping attempt (don't quit driver yet)
        clean_texts = await fetch_html(driver, primary_url, semaphore, should_quit=False, scrape_id=scrape_id, attempt="primary") 
                                                                        # should_quit parameter is kind of redundant because
                                                                        # we ALWAYS fall back & quit driver here, refactor later
        url_for_metadata = primary_url

        # fallback scraping attempt
        if not clean_texts and backup_url:
            # always quit and respawn the driver ("bad" active driver remains from failed attempt, must get rid of it)
            print(f"[fetch_and_process_slot {scrape_id}] respawning driver for backup")
            try:
                driver.quit()
            except Exception:
                pass
            await asyncio.sleep(1)
            
            # create a fresh driver for this slot
            new_driver = (await create_drivers(1))[0]
            setattr(new_driver, "_scrape_id", scrape_id)
            driver = new_driver

            # now scrap with the (newly) created driver
            print(f"[fetch_and_process_slot {scrape_id}] Primary failed for {primary_url}, trying backup: {backup_url}")
            clean_texts = await fetch_html(driver, backup_url, semaphore, should_quit=False, scrape_id=scrape_id, attempt="backup")
            url_for_metadata = backup_url

        # process to database
        if clean_texts and process_to_db:
            from modules.database_handler import process_text_to_db
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(database_executor, process_text_to_db, clean_texts, url_for_metadata)
        # if user doesn't ask to process_to_db, we just return clean_text
        #     NOTE -> (the processing to database part should be refactored out of here for better modularity & no circular imports)
        return clean_texts if clean_texts else None
    finally:
        # always release this driver here (so, even if backup fails the driver is still released, regardless of what should_quit is)
        try:
            print(f"[fetch_and_process_slot {scrape_id}] quitting driver")
            driver.quit()
        except Exception:
            pass


# Manages async operations of scrapping urls
async def fetch_html(driver, url, semaphore, should_quit=True, scrape_id: str | None = None, attempt: str = "primary"):
    if isinstance(url, list):
        url = str(url[0])

    # handle pdfs if the url is a pdf
    if url.lower().endswith('.pdf'):
        print(f"[fetch_html {scrape_id} {attempt}] Scrapping PDF {url}")
        pdf_content = await fetch_pdf_content(url, semaphore)
        clean_texts = split_markdown_chunks(pdf_content, 500)
        return clean_texts

    # handle web urls (non-pdf)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(fetch_html_executor, fetch_html_sync, driver, url, should_quit, scrape_id, attempt)


# Scraps HTML from website using webdriver and converts HTML to markdown
def fetch_html_sync(driver, url, should_quit=True, scrape_id: str | None = None, attempt: str = "primary"):  
                                  # |- we pass should_quit = false if we want to reuse the same driver for backups
    from modules.database_handler import Document
    try:
        # try to recover id/session info from driver if not provided (for debug print statements)
        sid = getattr(driver, "_scrape_id", scrape_id)
        session_id, ce_url = _driver_debug_info(driver)
        print(f"[fetch_html_sync {sid} sess={session_id} ce={ce_url} attempt={attempt}] scrapping HTML for: {url}")

         # set timeout for pages (NOTE -> moved to when we init chromedrivers)

        # scrap with selenium
        selenium_start = time.time()
        driver.get(url)
        time.sleep(2)
        html_content = driver.page_source
        selenium_end = time.time()
        print(f"[fetch_html_sync {sid} sess={session_id}] page_source OK in {selenium_end - selenium_start:.2f}s for {url}")

        # clean the scrapped html (for building database later)
        filtered_html_content = filter_content(html_content)
        html_document = Document(page_content=filtered_html_content, metadata={"source": url})
        md = MarkdownifyTransformer()
        converted_html = md.transform_documents([html_document])
        markdown_document = converted_html[0].page_content
        clean_texts = split_markdown_chunks(markdown_document, 500)
        return clean_texts

    # except block for scrap failures, finally block for quiting drivers 
    except Exception as e:
        sid = getattr(driver, "_scrape_id", scrape_id)
        session_id, ce_url = _driver_debug_info(driver)
        print(f"[fetch_html_sync {sid} sess={session_id} ce={ce_url}] Failed to load {url} with error: {e}")
        return None
    finally:
        if should_quit:
            try:
                sid = getattr(driver, "_scrape_id", scrape_id)
                print(f"[fetch_html_sync {sid}] quitting driver")
                driver.quit()
            except Exception:
                pass


# Asynchronously fetches text from PDFs
async def fetch_pdf_content(pdf_url, semaphore):
    pdf_start_time = time.time()
    try:
        async with semaphore:  # Use a semaphore to limit concurrency if needed
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
                # Download the PDF using streaming
                download_start_time = time.time()
                async with session.get(pdf_url) as response:
                    api_start_time = time.time()
                    response.raise_for_status()

                    content_length = response.headers.get('Content-Length')
                    api_end_time = time.time()

                    download_chunk_size = 64 * 1024
                    pdf_content = bytearray()

                    async for chunk in response.content.iter_chunked(download_chunk_size):
                        pdf_content.extend(chunk)
                        chunk_end_time = time.time()
                        print(f"[fetch_pdf_content] Downloaded {len(pdf_content)} bytes of {pdf_url} at {chunk_end_time}")

                download_end_time = time.time()

                pdf_file = BytesIO(pdf_content)
                pdf_reader = PdfReader(pdf_file)
                text_content = []

                extract_start_time = time.time()
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text_content.append(page.extract_text())
                extract_end_time = time.time()

                pdf_end_time = time.time()
                print(f"[fetch_pdf_content] Time taken to fetch and process PDF {pdf_url}: {pdf_end_time - pdf_start_time} seconds")
                print(f"[fetch_pdf_content]   Time taken to get API response for {pdf_url}: {api_end_time - api_start_time}")
                print(f"[fetch_pdf_content]   Download time: {download_end_time - download_start_time} seconds")
                print(f"[fetch_pdf_content]   Extraction time: {extract_end_time - extract_start_time} seconds")

                return "\n".join(text_content)

    except Exception as e:
        print(f"[fetch_pdf_content] Failed to fetch PDF content from {pdf_url} with error: {e}")
        return None


######################################################## also includes scrapping images off urls ###############################################################


async def fetch_images_off_specific_url(url: URL) -> ScrapedImageList:
    # Use create_drivers to initialize a single driver
    drivers = await create_drivers(1)
    driver = drivers[0]

    print(f"[fetch_images_off_specific_url] url to fetch image urls from: {url}")
    cleaned_html_list = await fetch_html(driver, url, semaphore=100) # Set semaphore to a arbitrarily large number to disable it
    cleaned_html = ''.join(cleaned_html_list)

    image_urls = await get_image_urls(cleaned_html)
    print("[fetch_images_off_specific_url] Image URLs:", image_urls)

    print(f"[fetch_images_off_specific_url] quitting driver")
    driver.quit()

    return image_urls


async def get_image_urls(cleaned_html):
    image_urls = []

    # Define the base URL mapping (make more flexible later)
    base_url_mapping = {
        "geps": "https://www.tropicaltidbits.com/storminfo/",
        "sfcplot": "https://www.tropicaltidbits.com/storminfo/sfcplots/",
        "tracks": "https://www.tropicaltidbits.com/storminfo/",
        "gefs": "https://www.tropicaltidbits.com/storminfo/",
        "intensity": "https://www.tropicaltidbits.com/storminfo/"
    }

    # Find all image file names ending with .png in the cleaned_html
    image_file_names = re.findall(r'\b\w+\.png\b', cleaned_html)

    # Construct full URLs based on the base URL mapping
    for file_name in image_file_names:
        for keyword, base_url in base_url_mapping.items():
            if keyword in file_name:
                image_urls.append(base_url + file_name)
                break

    # Remove duplicates by converting the list to a set and back to a list
    image_urls = list(set(image_urls))

    return image_urls
