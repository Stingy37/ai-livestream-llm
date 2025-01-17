"""
This module provides functions that handles everything related to interaction vector database

Classes:
    Document

Functions:
    process_html_to_db()
    find_relevant_docs()
    similarity_search_database()
"""


# Standard Library Imports
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# Third-Party Library Imports
from langchain_community.vectorstores import FAISS

# Local Application/Library-Specific Imports
from modules.configs import embeddings


# Aligned with langchain's document class, instances of this class used to create database
class Document:
    def __init__(self, page_content, metadata, id = None):
        self.page_content = page_content
        self.metadata = metadata
        self.id = id or uuid.uuid4()


def process_html_to_db(clean_texts, url):
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
