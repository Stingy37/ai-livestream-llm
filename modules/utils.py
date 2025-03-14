"""
This module provides general helper functions that assist in things like setting up the environment, handling languages, etc.

Functions:
    initialize_environment()
    initialize_executors()
    shutdown_executors()

    reset_global_variables()
    handle_language()

    monitor_file_changes()
    read_file()

    websites_and_search_queries_helper()
"""


# Standard Library Imports
import asyncio
import inspect
import logging
import os
import re
import tracemalloc
from concurrent.futures import ThreadPoolExecutor

# Third-Party Library Imports
import nest_asyncio


# Local Application/Library-Specific Imports
from modules.configs import (
    fetch_html_executor,
    database_executor,
    executor_list,
    cse_api_call_count,
    system_instructions_generate_livestream,
    websites_and_search_queries
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
    global database_executor, fetch_html_executor, executor_list

    # Global ThreadPoolExecutors for managing tasks
    database_executor = ThreadPoolExecutor(max_workers=15)
    fetch_html_executor = ThreadPoolExecutor(max_workers=15)

    executor_list = [database_executor, fetch_html_executor]

def shutdown_executors():
    global executor_list

    for executor in executor_list:
        # Shutdown the ThreadPoolExecutor, waiting for currently running tasks to complete
        executor.shutdown(wait=True)
        print(f"{executor} executor shut down.")
    else:
        print("No executor to shut down.")

    # Reset executor_list for usage later
    executor_list = []


# Resets counters so that they correctly function when create_script is reused
def reset_global_variables():
    global cse_api_call_count
    cse_api_call_count = 0


# Helper function to handle language-based parameter resolution
async def handle_language(language):
    print("language being used:", language)
    # Dictionary mapping language codes to parameters
    language_params = {
        'en': { # Refactor this later 
            'web_scrapper_system_instructions': system_instructions_generate_livestream['web_scrapper_system_instructions_en'],
            'key_messages_system_instructions': system_instructions_generate_livestream['key_messages_system_instructions_en'],
            'topic_system_instructions': system_instructions_generate_livestream['topic_system_instructions_en'],
        },
        'ph': {
            'web_scrapper_system_instructions': system_instructions_generate_livestream['web_scrapper_system_instructions_ph'],
            'key_messages_system_instructions': system_instructions_generate_livestream['key_messages_system_instructions_ph'],
            'topic_system_instructions': system_instructions_generate_livestream['topic_system_instructions_ph'],

        },
        'aus': {
            'web_scrapper_system_instructions': system_instructions_generate_livestream['web_scrapper_system_instructions_en'],
            'key_messages_system_instructions': system_instructions_generate_livestream['key_messages_system_instructions_en'],
            'topic_system_instructions': system_instructions_generate_livestream['topic_system_instructions_en'],
        },
        'us': {
            'web_scrapper_system_instructions': system_instructions_generate_livestream['web_scrapper_system_instructions_en'],
            'key_messages_system_instructions': system_instructions_generate_livestream['key_messages_system_instructions_en'],
            'topic_system_instructions': system_instructions_generate_livestream['topic_system_instructions_en'],
        }
        # Add more languages as needed
    }

    # Get the dictionary and return its values
    params = language_params.get(language)
    return params['web_scrapper_system_instructions'], params['key_messages_system_instructions'], params['topic_system_instructions']


def read_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return file.read().strip()
    return ""


# Monitor a certain file for changes, if so, send a signal via adding to queue and keep monitoring
async def monitor_file_changes(stop_event, file_path, signal_queue):
    last_mod_time = None
    await signal_queue.put(file_path)

    while not stop_event.is_set():
        try:
            current_mod_time = os.path.getmtime(file_path)

            if last_mod_time is None:
                last_mod_time = current_mod_time
            elif current_mod_time != last_mod_time:
                last_mod_time = current_mod_time
                await signal_queue.put(file_path)  # Do something when item is added to queue

        except FileNotFoundError:
            pass

        await asyncio.sleep(1)  # Checks every 1 second

    await asyncio.sleep(1)
    await signal_queue.put("sentinel_value") # Sentinel value to terminate await change_queue.get()

    print(f"End of monitor_file_changes reached for {file_path}")


# Provides a list of the current topics that were used while stop_event wasn't set (essentially stores past current topics)
async def create_current_topic_list(stop_event, change_queue):
    current_topic_list = []

    while not stop_event.is_set():
        file_path = await change_queue.get()
        if file_path == "sentinel_value":
            break
        try:
            topic = read_file(file_path)
            current_topic_list.append(topic)
        except:
            return []


    print(f"Stop event status: {stop_event.is_set()}")

    for index, topic in enumerate(current_topic_list):
         print(f"The current topic at index {index} is: {topic}")

    print(f"End of create_current_topic_list reached")

    return current_topic_list


# Helper function used only to retrieve website urls from configs
def websites_and_search_queries_helper(key):
    """
    Retrieve URLs associated with the given key from websites_and_search_queries. 
    - If it's a dictionary, return a list of its values (i.e. a list of URLs).
    - If it's a list, return the list directly.
    - Otherwise, return an empty list.
    """
    value = websites_and_search_queries.get(key)
    if isinstance(value, dict):
        return list(value.values())
    elif isinstance(value, list):
        return value
    else:
        return []
