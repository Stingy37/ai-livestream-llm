"""
This module provides functions that coordinate the content generate aspect of the program
(ie. in charge of organizing calls to lower level functions in other modules)

Functions:
    create_script_handler()
    create_script()
    main()
    async_parallel_run()
    get_intermediate_answer()
"""


# Standard Library Imports
import asyncio

# Third-Party Library Imports
import aiohttp

# Local Application/Library-Specific Imports
from modules.core.configs import (
    google_search_urls_to_return,
    images_to_return,
    search_api_key,
    search_engine_id,
)
from modules.data.database_handler import find_relevant_docs_database
from modules.generation.openai_handler import generate_text, return_gpt_answer
from modules.core.utils import handle_language
from modules.core.schema import SceneItems, SceneDatabaseResults

# Sets up variables + environment for create_script, then handles what it returns
async def create_script_handler(
    queries_dictionary_list: SceneDatabaseResults,
    websites_used: list[str],
    final_script_system_instructions: str,
    language: str
) -> SceneItems:
    (web_scrapper_system_instructions,
     key_messages_system_instructions,
     topic_system_instructions) = await handle_language(language)

    loop = asyncio.get_event_loop()

    # Capture the result returned by the async function
    items_generated = loop.run_until_complete(create_script(
        queries_dictionary_list,
        websites_used,
        final_script_system_instructions,
        web_scrapper_system_instructions,
        key_messages_system_instructions,
        topic_system_instructions,
        k_value_similarity_search = 4
        ))
    return items_generated


# Uses intermediate answer from "process_urls_and_get_intermediate_answer" to return final products (script + key messages)
async def create_script(queries_dictionary_list, websites_used,
               final_script_system_instructions,
               web_scrapper_system_instructions,
               key_messages_system_instructions,
               topic_system_instructions,
               k_value_similarity_search):
    """
    Creates items to be used in livestream with the results from lower level orchestrators
    """

    results = asyncio.run(async_parallel_run(
        queries_dictionary_list, websites_used,
        k_value_similarity_search,
        web_scrapper_system_instructions,
        ))

    '****************************************************************************************************************************************************'

    intermediate_gpt_answers = []

    # Gets GPT answer and image url from each thread to combine them
    for result in results:
        intermediate_gpt_answers.append(result['intermediate_gpt_answer'])

    # Intermediate answer for usage in creating finished script (ie. draft)
    combined_answers = "\n\n".join(intermediate_gpt_answers)

    script_task = asyncio.create_task(generate_text(combined_answers, final_script_system_instructions, item_being_generated = "news_script"))
    key_messages_task = asyncio.create_task(generate_text(combined_answers, key_messages_system_instructions, item_being_generated = "key_messages"))
    topic_task = asyncio.create_task(generate_text(combined_answers, topic_system_instructions, item_being_generated = "topic"))

    script, key_messages, topic = await asyncio.gather(script_task, key_messages_task, topic_task)

    '************************************************ Determines what to return based on parameters ******************************************************'


    return {"script": script, "images": None, "key_messages": key_messages, "topic": topic}


# Uses task gathering to run "process_urls_and_get_intermediate_answer" in parallel
async def async_parallel_run(queries_dictionary_list, websites_used, k_value_similarity_search, web_scrapper_system_instructions):
    tasks = []

    for query_dict in queries_dictionary_list:
        print(f"[async_parallel_run] added a new get_intermediate_answer task for [{query_dict['query']}]'s databases")
        tasks.append(get_intermediate_answer(query_dict, websites_used, k_value_similarity_search, web_scrapper_system_instructions))

    print("[async_parallel_run] executing tasks")
    print("[async_parallel_run]", tasks)

    # Results is a dictionary containing intermediate GPT answer
    results_dict = await asyncio.gather(*tasks)
    return results_dict


# Handles image urls and returns intermediate ChatGPT answer for usage later (Runs for each query)
async def get_intermediate_answer(query_dict, websites_used, k_value_similarity_search, web_scrapper_system_instructions):

      relevant_information = await find_relevant_docs_database(
          query = query_dict['query'],
          database_list = query_dict['database_list'],
          max_workers = len(websites_used),
          num_of_docs_to_return = k_value_similarity_search
          )
      page_content, metadata = relevant_information

      formatted_web_scrapper_system_instructions = web_scrapper_system_instructions.format(
          page_content_placeholder = page_content,
          metadata_placeholder = metadata
      )
      gpt_answer = await return_gpt_answer(formatted_web_scrapper_system_instructions, query_dict['query'])

      return {"intermediate_gpt_answer": gpt_answer}
