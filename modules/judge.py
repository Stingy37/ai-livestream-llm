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
import modules.configs as configs

from modules.configs import (
    embeddings,
    system_instructions_generate_livestream,
    websites_and_search_queries
)
from modules.database_handler import Database, find_relevant_docs_query, rebuild_page_content


async def judge_handler(input): # Modularize further by getting the topic from scenes_config_list['a_certain_key']
    """
    Controller function for handling judging, returns a binary output indicating whether or not a given input is accurate.
    """
    # Handle language internally (b/c thats what other functions are doing)
    language_specific_values = await judge_language_handler()
    primary_info_url = language_specific_values['primary_info_url']

    # Get context for judge
    primary_judge_info, secondary_judge_info = await asyncio.gather(
        retrieve_primary_judge_info(primary_info_url), # Have the URL param set automatically (depending on configs.scenes_config_list)
        retrieve_secondary_judge_info()
    )

    # Format judging system instructions with the retrieved context
    judge_system_instructions = system_instructions_generate_livestream['judge_system_instructions'].format(
         primary_judge_info_placeholder = primary_judge_info,
         secondary_judge_info_placeholder = secondary_judge_info
      )

    # Get a response from ChatGPT


async def judge_language_handler():
    """
    Determines the primary information url based off the current language being used. Returns a dictionary containing language specific values:
    {
      'primary_info_url': 'weather_agency_for_language'
    }
    """
    # Takes advantage of config keys being {topic}_{language}
    language = configs.scenes_config_list[0]['language']

    key = f"tropics_forecast_websites_{language}" # Could modularize this further later by making the topic a parameter too
    websites_used = websites_and_search_queries.get(key)

    primary_info_url = websites_used.get('primary_website', 'no_url_retrieved') # Where no_url_retrieved is default value
    return {'primary_info_url': primary_info_url}


async def retrieve_primary_judge_info(url_to_rebuild):
    """
    Returns the primary information the judge will use, which is the entire page content of a reputable website.
    """
    # Return entire website's page content
    for database in configs.unique_databases:
        if database.metadata['website'] == url_to_rebuild:
            page_content = await rebuild_page_content(database.database)
            return page_content
    return 'primary info failed to retrieve, rely on secondary info'


async def retrieve_secondary_judge_info():
    """
    Returns the secondary information the judge will use, which is information retrieved from a RAG system of all website databases.
    """
    # Used as queries in similarity search to retrieve secondary context for judge
    accuracy_metrics = [
        'Storm stats (windspeed, pressure, radius of winds, etc.)',
        'Future storm path (where the storm is headed)',
        'Expected impacts (how much flooding, what warnings, etc.)'
        ]

    secondary_judge_info, _ = await find_relevant_docs_query(
        query_list = accuracy_metrics,
        database = configs.merged_database,
        num_of_docs_to_return = 1
        )
    return secondary_judge_info
