"""
This module provides functions that related to returning text or images from a certain URL

Functions:
    google_search()

    fetch_and_process_html()
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

# Third-Party Library Imports
import aiohttp
from langchain_community.document_transformers import MarkdownifyTransformer
from PyPDF2 import PdfReader

# Local Application/Library-Specific Imports
from modules.configs import database_executor, fetch_html_executor, cse_api_call_count, cse_api_call_lock
from modules.database_handler import Document
from modules.text_processing import filter_content, split_markdown_chunks
from modules.webdriver_handler import create_drivers


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
    print(f"Making API request with params: {params}")
    async with cse_api_call_lock:
        cse_api_call_count += 1
        print(f"API call count: {cse_api_call_count}")

    async with session.get(url, params=params) as response:
        if response.status != 200:
            print(f"Error: API request failed with status code {response.status}")
            return []

        search_results = await response.json()
        print(f"API response: {search_results}")

        items = search_results.get('items', [])
        api_end = time.time() # Temp
        print(f"Time taken to get API response: {api_end - api_start}")

        if not items:
            print("No items found in search results.")
            return []

        # Add a delay before returning the results to avoid concurrency issues
        await asyncio.sleep(2)
        return [item.get('link') for item in items]
        

# Manages async operations of ONLY scrapping URL
async def fetch_html(driver, url, semaphore):
    # Accounts for if URL is a list by converting to string
    if isinstance(url, list):
        url = str(url[0])

    # If URL is a direct PDF link
    if url.lower().endswith('.pdf'):
        print("Scrapping PDF", url)
        pdf_content = await fetch_pdf_content(url, semaphore)
        clean_texts = split_markdown_chunks(pdf_content, 500)
        return clean_texts

    # If URL is a website link
    else:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(fetch_html_executor, fetch_html_sync, driver, url)


# Scraps HTML from website using webdriver and converts HTML to markdown
def fetch_html_sync(driver, url):
    try:
        print("scrapping HTML for:", url)

        selenium_start = time.time() # Temp
        driver.get(url)
        time.sleep(2)  # Have a delay for content to load on webpage
        html_content = driver.page_source
        selenium_end = time.time() # Temp
        print(f"Time taken for selenium to get page source for {url}: {selenium_end - selenium_start}")

        filtered_html_content = filter_content(html_content)
        html_document = Document(page_content=filtered_html_content, metadata={"source": url})
        md = MarkdownifyTransformer()
        converted_html = md.transform_documents([html_document])
        markdown_document = converted_html[0].page_content
        clean_texts = split_markdown_chunks(markdown_document, 500)

        return clean_texts

    except Exception as e:
        print(f"Failed to load {url} with error: {e}")
        return None
    finally:
        driver.quit()


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
                        print(f"Downloaded {len(pdf_content)} bytes of {pdf_url} at {chunk_end_time}")

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
                print(f"Time taken to fetch and process PDF {pdf_url}: {pdf_end_time - pdf_start_time} seconds")
                print(f"  Time taken to get API response for {pdf_url}: {api_end_time - api_start_time}")
                print(f"  Download time: {download_end_time - download_start_time} seconds")
                print(f"  Extraction time: {extract_end_time - extract_start_time} seconds")

                return "\n".join(text_content)

    except Exception as e:
        print(f"Failed to fetch PDF content from {pdf_url} with error: {e}")
        return None


######################################################## also includes scrapping images off urls ###############################################################


async def fetch_images_off_specific_url(url):
    # Use create_drivers to initialize a single driver
    drivers = await create_drivers(1)
    driver = drivers[0]  # Since create_drivers returns a list of drivers

    cleaned_html_list = await fetch_html(driver, url, semaphore=100) # Set semaphore to a arbitrarily large number to disable it
    cleaned_html = ''.join(cleaned_html_list)

    image_urls = await get_image_urls(cleaned_html)
    print("Image URLs:", image_urls)

    return image_urls
    driver.quit()


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
