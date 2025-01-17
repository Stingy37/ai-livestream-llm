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
"""


# Standard Library Imports
import os
import logging
import tracemalloc
from concurrent.futures import ThreadPoolExecutor

# Third-Party Library Imports
import nest_asyncio


# Local Application/Library-Specific Imports
from modules.configs import (
    database_executor,
    cse_api_call_count,
    system_instructions_generate_livestream
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
            'web_scrapper_system_instructions': system_instructions_generate_livestream['web_scrapper_system_instructions_en'],
            'key_messages_system_instructions': system_instructions_generate_livestream['key_messages_system_instructions_en'],
            'topic_system_instructions': system_instructions_generate_livestream['topic_system_instructions_en'],

        },
        'ph': {
            'web_scrapper_system_instructions': system_instructions_generate_livestream['web_scrapper_system_instructions_ph'],
            'key_messages_system_instructions': system_instructions_generate_livestream['key_messages_system_instructions_ph'],
            'topic_system_instructions': system_instructions_generate_livestream['topic_system_instructions_ph'],

        },

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

    # As long as stop_event references same asyncio.event object, setting it anywhere will cause stop_event.is_set() to be true
    while not stop_event.is_set():
        try:
            current_mod_time = os.path.getmtime(file_path)

            if last_mod_time is None:
                last_mod_time = current_mod_time
            elif current_mod_time != last_mod_time:
                last_mod_time = current_mod_time
                await signal_queue.put(file_path)

        except FileNotFoundError:
            print(f"File {file_path} does not exist.")

        await asyncio.sleep(1) # Checks every 1 second 

    print("Monitoring for " + file_path + " ended")

# Provides a list of the current topics that were used while stop_event wasn't set (essentially stores past current topics)
async def create_current_topic_list(stop_event, change_queue):
    current_topic_list = []

    while not stop_event.is_set():
        file_path = await change_queue.get()
        current_topic_list.append(read_file(file_path))
        for index, topic in enumerate(current_topic_list):
            print(f"The current topic at index {index} is: {topic}")

    return current_topic_list

