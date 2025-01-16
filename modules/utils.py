"""
This module provides general helper functions that assist in things like setting up the environment, handling languages, etc. 

Functions:
    initialize_environment()
    initialize_executors()
    shutdown_executors()
    reset_global_variables()
    handle_language()
"""


# Standard Library Imports
import tracemalloc
import logging
from concurrent.futures import ThreadPoolExecutor

# Third-Party Library Imports
import nest_asyncio


# Local Application/Library-Specific Imports
from modules.configs import (
    database_executor,
    cse_api_call_count,
    system_instructions
)


# Initialize environment for running generate_livestream
def initialize_environment():
    # Start tracemalloc to track memory allocations
    tracemalloc.start()
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    # Apply nest_asyncio to allow nested event loops
    nest_asyncio.apply()
    print("Environment initialized.")


def initialize_executors():
    global database_executor

    # Global ThreadPoolExecutors for managing different tasks
    database_executor = ThreadPoolExecutor(max_workers=10)


def shutdown_executors():
    global database_executor

    if database_executor:
        # Shutdown the ThreadPoolExecutor, waiting for currently running tasks to complete
        database_executor.shutdown(wait=True)
        print("Database executor shut down.")
    else:
        print("No database executor to shut down.")


# Resets counters so that they correctly function when create_script is reused
def reset_global_variables():
    global cse_api_call_count
    cse_api_call_count = 0


# Helper function to handle language-based parameter resolution
async def handle_language(language):
    print("language being used:", language)
    # Dictionary mapping language codes to parameters
    language_params = {
        'en': {
            'web_scrapper_system_instructions': system_instructions['web_scrapper_system_instructions_en'],
            'key_messages_system_instructions': system_instructions['key_messages_system_instructions_en'],
        },
        'ph': {
            'web_scrapper_system_instructions': system_instructions['web_scrapper_system_instructions_ph'],
            'key_messages_system_instructions': system_instructions['key_messages_system_instructions_ph'],
        },

        # Add more languages as needed
    }

    # Get the dictionary and return its values
    params = language_params.get(language)
    return params['web_scrapper_system_instructions'], params['key_messages_system_instructions']
