"""
This module provides functions that help judge the LLM's generated scripts, and returns a
decision whether or not to proceed the judged script to content generation.

Functions:
    judge_handler()
    retrieve_primary_judge_info()
    retrieve_secondary_judge_info()
"""


# Standard Library Imports

# Third-Party Library Imports
from langchain_community.vectorstores import FAISS

# Local Application/Library-Specific Imports
from modules.configs import embeddings
from modules.database_handler import Database, find_relevant_docs_query, rebuild_page_content


async def judge_handler(input,):
    """
    Controller function for handling judging, returns a binary output indicating whether or not a given input is accurate.
    """
    primary_judge_info, secondary_judge_info = await asyncio.gather(
        retrieve_primary_judge_info(), # Have the URL param set automatically (depending on configs.scenes_config) 
        retrieve_secondary_judge_info()
    )

    # Format judging system instructions with the retrieved information

    # Get a response from ChatGPT


async def retrieve_primary_judge_info(url_to_rebuild):
    """
    Returns the primary information the judge will use, which is the entire page content of a reputable website.
    """
    for database in configs.unique_databases:
        if database.metadata['website'] == url_to_rebuild:
            page_content = await rebuild_page_content(database.database)
            return page_content
    return 'primary info failed to retrieve, rely on secondary info'


async def retrieve_secondary_judge_info():
    """
    Returns the secondary information the judge will use, which is information retrieved from a RAG system of all website databases.
    """
    # Used as queries in similarity search to retrieve context for judge
    accuracy_metrics = [
        'Storm stats (windspeed, pressure, radius of winds, etc.)',
        'Future storm path (where the storm is headed)',
        'Expected impacts (how much flooding, what warnings, etc.)'
        ]

    secondary_judge_info, _ = await find_relevant_docs_query(
        query_list = accuracy_metrics,
        database = merged_database,
        num_of_docs_to_return = 3
        )
    return secondary_judge_info
