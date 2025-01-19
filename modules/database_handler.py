"""
This module provides functions that handles everything related to interaction with vector database

Classes:
    Document

Functions:
    create_databases_handler()
    create_databases_for_query()
    process_urls_for_database()
    process_text_to_db()
    find_relevant_docs()
    similarity_search_database()
"""


# Standard Library Imports
import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# Third-Party Library Imports
from langchain_community.vectorstores import FAISS

# Local Application/Library-Specific Imports
from modules.configs import embeddings
from modules.web_scraper import fetch_and_process_html, google_search
from modules.webdriver_handler import create_drivers

# Aligned with langchain's document class, instances of this class used to create database
class Document:
    def __init__(self, page_content, metadata, id = None):
        self.page_content = page_content
        self.metadata = metadata
        self.id = id or uuid.uuid4()

# Used to create a database for each scene
async def create_databases_handler(search_queries, search_api_key, search_engine_id, do_google_search, websites_to_use):
    """
    Scrapes the URLs and initializes the vector databases.
    Returns a list of databases corresponding to each query.
    """
    tasks = []
    for query in search_queries.values():
        tasks.append(
            create_databases_for_query( # returns a dictionary containing query + database_list as keys
                query,
                search_api_key,
                search_engine_id,
                do_google_search,
                websites_to_use,
            )
        )
    queries_dictionary_list = await asyncio.gather(*tasks)
    return queries_dictionary_list


async def create_databases_for_query(query, search_api_key, search_engine_id, do_google_search, websites_to_use):

    '******************************************** Handle whether or not Google Search is used *******************************************************'
    print("do_google_search value for ", query, ": ", do_google_search)

    # Determine how much drivers needed to scrape websites based on amount of URLs used
    if do_google_search:
        drivers_to_create = google_search_urls_to_return
    else:
        drivers_to_create = len(websites_to_use)

    driver_list = await create_drivers(drivers_to_create) # One driver created for every url

    '***************************************** This uses the Google CSE Api to return website URLs **************************************************'

    if do_google_search: # Checks to see whether user wants to do google search or has predetermined URLs
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            urls_task = google_search(session, query, search_api_key, search_engine_id, number_to_return = google_search_urls_to_return, search_images = False)
            urls = await urls_task
    else:
        urls = websites_to_use # Assign urls directly without doing google search

    '********************************** scraps website URLs and returns a list containing databases for each url ***********************************'

    semaphore = asyncio.Semaphore(100) # Limit the number of concurrent tasks ONLY for PDFs - set high number to disable it

    print(f"Amount of drivers to scrap {len(urls)} urls: {len(driver_list)}")

    # Create async tasks for fetching and processing HTML
    tasks = [fetch_and_process_html(driver, url, process_to_db=True, semaphore=semaphore) for driver, url in zip(driver_list, urls)]
    database_list = await asyncio.gather(*tasks)

    return {'query': query, 'database_list': database_list}


# Takes in clean_text (filtered markdown) and constructs database from it
def process_text_to_db(clean_texts, url):
    database_start_time = time.time()

    metadata = {'website': url}
    total_docs = [Document(page_content=text, metadata=metadata) for text in clean_texts]

    # Creating the FAISS vector database (CPU-bound operation)
    faiss_db = FAISS.from_documents(total_docs, embeddings)
    database_end_time = time.time()
    print(f"Time taken to create database for {url}: {database_end_time - database_start_time}")

    return faiss_db



# Gets the most relevant passages from the constructed vector database
async def find_relevant_docs(query, database_list, urls_used, num_of_docs_to_return):
    metadata = []
    relevant_page_content = []

    with ThreadPoolExecutor(max_workers=urls_used) as executor:
        futures = [executor.submit(similarity_search_database, query, database, num_of_docs_to_return) for database in database_list]
        for future in as_completed(futures):
            result = future.result()
            if result:
                relevant_page_content.extend(result['relevant_page_content'])
                metadata.extend(result['metadata'])

    relevant_page_content_string = ", ".join(relevant_page_content)
    return [relevant_page_content_string, metadata]


# Returns passages in database with most similarity to query
def similarity_search_database(query, database, num_of_docs_to_return):
    # Handle when URL fails to fetch
    if database is None:
        return {
            'relevant_page_content': ['None'],
            'metadata': ['None']
        }
    docs = database.similarity_search_with_score(query, k= num_of_docs_to_return )
    return {
        'relevant_page_content': [doc[0].page_content for doc in docs],
        'metadata': [doc[0].metadata for doc in docs]
    }
