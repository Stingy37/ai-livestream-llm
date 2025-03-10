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


# Helper function to add new values to global configs file
def add_to_configs(*values):
    # Look at call stack's previous frame to get caller's local variables as a dictionary
    caller_locals = inspect.currentframe().f_back.f_locals
    value_names = []

    for value in values:
        found_name = None
        # Compares the values passed in as parameters to the same parameters except in the call stack frame (in the call stack, the name is attached to the value)
        for local_value_name, local_value in caller_locals.items():
            if value is local_value:
                found_name = local_value_name
                value_names.append(found_name)
                break
        if found_name is None:
            raise ValueError(f"Unable to add value: {value} to module.configs") # Stop the program b/c it's a fatal error

    config_path = os.path.abspath("ai-livestream-llm/modules/configs.py")

    print("Current working directory:", os.getcwd())
    print("Config path exists:", os.path.exists(config_path))
    print("config_path:", config_path)

    with open(config_path, "r") as f:
        config_content = f.read()

    new_lines = []

    # Remove any existing duplicate configs in module.configs
    for value_name, value in zip(value_names, values):
        pattern = rf'^\s*{re.escape(value_name)}\s*=.*\n'
        config_content = re.sub(pattern, '', config_content, flags=re.MULTILINE)
        new_lines.append(f"{value_name} = {repr(value)}")

    # Handle divider
    divider = "# ################################################### Temporary, session based configs ########################################################"
    divider_pattern = rf'^{re.escape(divider)}.*$'
    config_content = re.sub(divider_pattern, '', config_content, flags=re.MULTILINE)

    # Clean up extra blank lines
    config_content = re.sub(r'\n{2,}$', '\n', config_content, flags=re.MULTILINE)

    # Prepare new block with new configs
    new_block = "\n\n\n" + divider + "\n" + "\n".join(new_lines) + "\n\n"

    # Write the cleaned-up original content plus the new configs
    with open(config_path, "w") as f:
        f.write(config_content.rstrip() + new_block)
