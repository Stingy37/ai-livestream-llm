"""
This module provides functions that handles everything related to interaction with vector database

Classes:
    Document
    Database

Functions:
    create_databases_handler()
    create_databases_for_query()
    create_unique_databases()
    create_merged_database()

    process_urls_for_database()
    process_text_to_db()

    rebuild_page_content

    find_relevant_docs_database()
    find_relevant_docs_query()
    similarity_search()
"""


# Standard Library Imports
import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# Third-Party Library Imports
from langchain_community.vectorstores import FAISS

# Local Application/Library-Specific Imports
import modules.configs as configs

from modules.configs import (
    google_search_urls_to_return,
    images_to_return,
    search_api_key,
    search_engine_id,
    system_instructions_generate_livestream,
    use_tts_api,
    websites_and_search_queries,
    embeddings
)
from modules.web_scraper import fetch_and_process_html, google_search
from modules.webdriver_handler import create_drivers


# Aligned with langchain's document class, instances of this class used to create database
class Document:
    def __init__(self, page_content, metadata, id = None):
        self.page_content = page_content
        self.metadata = metadata
        self.id = id or uuid.uuid4()

# Link FAISS database to its metadata (i.e. the website used)
class Database:
    def __init__(self, database, metadata):
        self.database = database
        self.metadata = metadata


'*************************************************************************** Handlers ********************************************************************'


# Used to handle all databases that need to be created
async def create_databases_handler(scenes_config):
    """
    Scrapes the URLs and initializes scene databases, and handles creation of databases used for judging
    Returns a list of dictionaries of the scene databases. Each dictionary has two keys called query and database_lists:
    {
        'query': query,
        'database_list': [database_class_one, database_class_two]
        where each database_class contains a FAISS database object and its metadata (metadata is another dictionary with 'website': url)
    }
    """
    database_tasks = [
        asyncio.create_task(
            scene_database_handler(
                search_queries = scene['search_queries'],
                search_api_key = search_api_key,
                search_engine_id = search_engine_id,
                do_google_search = False,
                websites_to_use = scene['websites'],
            )
        ) for scene in scenes_config
    ]
    scene_database_results = await asyncio.gather(*database_tasks)
    configs.database_results = scene_database_results # Make scene results globally accessible

    # Create the judge databases sequentially (b/c merging depends on unique databases)
    configs.unique_databases = await create_unique_databases(scene_database_results)
    configs.merged_database = await create_merged_database()

    # Only return the scene databases (to be used later to create scenes)
    return scene_database_results


# Handles ONLY creation of scene databases (i.e. the ones attached to a specific query)
async def scene_database_handler(search_queries, search_api_key, search_engine_id, do_google_search, websites_to_use):
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
    print("do_google_search value for ", query, ": ", do_google_search)

    # Determine how much drivers needed to scrape websites based on amount of URLs used
    if do_google_search:
        drivers_to_create = google_search_urls_to_return
    else:
        drivers_to_create = len(websites_to_use)

    driver_list = await create_drivers(drivers_to_create) # One driver created for every url

    if do_google_search: # Checks to see whether user wants to do google search or has predetermined URLs
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            urls_task = google_search(session, query, search_api_key, search_engine_id, number_to_return = google_search_urls_to_return, search_images = False)
            urls = await urls_task
    else:
        urls = websites_to_use # Assign urls directly without doing google search

    semaphore = asyncio.Semaphore(100) # Limit the number of concurrent tasks ONLY for PDFs - set high number to disable it

    print(f"Amount of drivers to scrap {len(urls)} urls: {len(driver_list)}")

    # Create async tasks for fetching and processing HTML
    tasks = [fetch_and_process_html(driver, url, process_to_db=True, semaphore=semaphore) for driver, url in zip(driver_list, urls)]
    database_list = await asyncio.gather(*tasks)

    return {'query': query, 'database_list': database_list}


'***************************************************************** Lower Level Functions ********************************************************************'


async def create_unique_databases(database_list):
    """
    Returns a list of non-duplicate database classes to better link website its corresponding database
    """
    flattened_database_list = [
        db
        for sublist in database_list
        for item in sublist
        for db in item['database_list']
    ]
    # Deduplicate based on the metadata
    unique_databases = []
    seen_metadata = set() # Basically just a python data structure that doesn't allow duplicates

    for db in flattened_database_list:
        # Access the metadata of the custom Database object
        meta = db.metadata['website']
        if meta not in seen_metadata:
            seen_metadata.add(meta)
            # Append the unique database class
            unique_databases.append(db)

    print("Unique databases created")
    return unique_databases


async def create_merged_database():
    """
    Create a single, merged database out of all the unique databases
    """
    all_documents = []
    for database in configs.unique_databases:
        db = database.database

        # Access the underlying dictionary of documents in the InMemoryDocstore.
        docs = list(db.docstore._dict.values())
        all_documents.extend(docs)

    # Rebuild a new Database class from the combined documents.
    merged_database = Database(database = FAISS.from_documents(all_documents, embeddings), metadata = 'Not used')
    print("Merged FAISS database created.")

    return merged_database


# Takes in clean_text (filtered markdown) and constructs database from it
def process_text_to_db(clean_texts, url):
    database_start_time = time.time()

    metadata = {'website': url}
    total_docs = [Document(page_content=text, metadata=metadata) for text in clean_texts]

    # Creating the FAISS vector database (CPU-bound operation)
    faiss_db = Database(database=FAISS.from_documents(total_docs, embeddings), metadata=metadata)
    database_end_time = time.time()
    print(f"Time taken to create database for {url}: {database_end_time - database_start_time}")

    return faiss_db


'**************************************************************** Similarity Search Functions ********************************************************************'


# Gets the most relevant passages from the constructed vector database
async def find_relevant_docs_database(query, database_list, max_workers = 10, num_of_docs_to_return = 2): # Default values for last 2 parameters
    """
    Async wrapper function used to call similarity_search
    Version: One query, multiple databases
    """
    metadata = []
    relevant_page_content = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(similarity_search, query, database, num_of_docs_to_return) for database in database_list]
        for future in as_completed(futures):
            result = future.result()
            if result:
                relevant_page_content.extend(result['relevant_page_content'])
                metadata.extend(result['metadata'])

    relevant_page_content_string = ", ".join(relevant_page_content)
    return [relevant_page_content_string, metadata]


# Multiple query version of find_relevant_docs (Could DRY with lamba / callbacks, but decreases readability & don't think my skill level is there yet)
async def find_relevant_docs_query(query_list, database, max_workers = 10, num_of_docs_to_return = 2): # Default values for last 2 parameters
    """
    Async wrapper function used to call similarity_search
    Version: multiple queries, one database
    """
    metadata = []
    relevant_page_content = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(similarity_search, query, database, num_of_docs_to_return) for query in query_list]
        for future in as_completed(futures):
            result = future.result()
            if result:
                relevant_page_content.extend(result['relevant_page_content'])
                metadata.extend(result['metadata'])

    relevant_page_content = list(dict.fromkeys(relevant_page_content))
    relevant_page_content_string = ", ".join(relevant_page_content)


# Returns passages in database with most similarity to query
def similarity_search(query, database, num_of_docs_to_return):
    database = database.database # Seperate database attribute from the metadata attribute (b/c the parameter database is now a class)

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


# Helper function used to retrieve a website's page content based off its database
async def rebuild_page_content(database):
    page_content = '\n'.join(map(str, database.docstore._dict.values()))
    return page_content
