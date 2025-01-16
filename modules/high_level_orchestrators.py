"""
This module provides functions that coordinate the content generate aspect of the program
(ie. in charge of organizing calls to lower level functions in other modules)

Functions: 
    create_script()
    main()
    async_parallel_run()
    process_urls_and_get_intermediate_answer()
"""


# Standard Library Imports
import asyncio

# Third-Party Library Imports
import aiohttp

# Local Application/Library-Specific Imports
from modules.configs import (
    google_search_urls_to_return,
    images_to_return,
    search_api_key,
    search_engine_id,
)
from modules.database_handler import find_relevant_docs
from modules.openai_handler import generate_text, return_gpt_answer
from modules.utils import handle_language
from modules.web_scraper import fetch_and_process_html, google_search
from modules.webdriver_handler import create_drivers


# Entry point for asyncio program (creating a script)
async def create_script(search_queries_list, image_search_queries, final_script_system_instructions, return_images, do_google_search,
                        websites_to_use, k_value_similarity_search, language):
    (web_scrapper_system_instructions,
     key_messages_system_instructions, 
     topic_system_instructions) = await handle_language(language)

    loop = asyncio.get_event_loop()

    # Capture the result returned by the async function
    items_generated = loop.run_until_complete(main(search_queries_list, final_script_system_instructions, search_api_key, search_engine_id, image_search_queries, return_images, do_google_search,
                                                   websites_to_use, k_value_similarity_search, web_scrapper_system_instructions, key_messages_system_instructions, topic_system_instructions))
    return items_generated


# Uses intermediate answer from "process_urls_and_get_intermediate_answer" to return final products (script + key messages)
async def main(search_queries, final_script_system_instructions, search_api_key, search_engine_id, image_search_queries,
               return_images, do_google_search, websites_to_use, k_value_similarity_search, web_scrapper_system_instructions, key_messages_system_instructions, topic_system_instructions):
    print(image_search_queries)
    results = asyncio.run(async_parallel_run(search_queries, search_api_key, search_engine_id, image_search_queries,
                                             do_google_search, websites_to_use, k_value_similarity_search, web_scrapper_system_instructions))

    script_gpt_answers = []
    total_image_urls = []

    '****************************************************************************************************************************************************'

    # Gets GPT answer and image url from each thread to combine them
    for result in results:
      if 'gpt_answer' in result:
          script_gpt_answers.append(result['gpt_answer'])
      if 'total_image_urls' in result:
          total_image_urls.extend(result['total_image_urls'])

    # Intermediate answer for usage in creating finished script (ie. draft)
    combined_answers = "\n\n".join(script_gpt_answers)

    script_task = asyncio.create_task(generate_text(combined_answers, final_script_system_instructions, item_being_generated = "news_script"))
    key_messages_task = asyncio.create_task(generate_text(combined_answers, key_messages_system_instructions, item_being_generated = "key_messages"))
    topic_task = asyncio.create_task(generate_text(combined_answers, topic_system_instructions, item_being_generated = "topic")) 
    script, key_messages, topic = await asyncio.gather(script_task, key_messages_task, topic_task)

    '************************************************ Determines what to return based on parameters ******************************************************'

    if return_images == True:
        return {"script": script, "images": total_image_urls, "key_messages": key_messages, "topic": topic}
    else:
        return {"script": script, "images": None, "key_messages": key_messages, "topic": topic}


# Uses task gathering to run "process_urls_and_get_intermediate_answer" in parallel
async def async_parallel_run(search_queries, search_api_key, search_engine_id, image_search_queries,
                             do_google_search, websites_to_use, k_value_similarity_search, web_scrapper_system_instructions):
    tasks = []

    for query in search_queries.values():
        print("added a new task")
        tasks.append(process_urls_and_get_intermediate_answer(query, search_api_key, search_engine_id, False, do_google_search,
                                                              websites_to_use, k_value_similarity_search=k_value_similarity_search, web_scrapper_system_instructions = web_scrapper_system_instructions))

    if image_search_queries: # makes sure image_search_queries isnt none (disabled)
      for image_query in image_search_queries.values():
          print("added a new task")
          tasks.append(process_urls_and_get_intermediate_answer(image_query, search_api_key, search_engine_id, is_image_search = True, do_google_search = True,
                                                                websites_to_use = None, k_value_similarity_search=k_value_similarity_search, web_scrapper_system_instructions = web_scrapper_system_instructions)) # Assumes that image search queries will always use Google

    print("executing tasks")
    print(tasks)

    # Results contain intermediate GPT answer and image urls
    results = await asyncio.gather(*tasks)
    return results


# Handles image urls and returns intermediate ChatGPT answer for usage later (Runs for each query)
async def process_urls_and_get_intermediate_answer(query, search_api_key, search_engine_id, is_image_search, do_google_search, websites_to_use,
                                                   k_value_similarity_search, web_scrapper_system_instructions):

    '******************************************** Handle whether or not Google Search is used *******************************************************'
    print("do_google_search value for ", query, ": ", do_google_search)

    # Set urls_to_return based on whether or not google search is used
    if do_google_search == True:
        drivers_to_create = google_search_urls_to_return # Return X urls for each query (ex. 1 query = 2 urls, if returning 2 urls for each query)
    else:
        drivers_to_create = len(websites_to_use)

    '******************************************* This creates web drivers needed to scrape HTML ******************************************************'
    if is_image_search:
      print("no drivers needed")
    else:
      driver_list = await create_drivers(drivers_to_create) # 1 driver created to scrap 1 website ( if return 2 urls, need 2 drivers)

    '*********************************** This uses the Google CSE Api to return image or website URLs ************************************************'
    total_image_urls = []

    if do_google_search: # Checks to see whether user wants to do google search or has predetermined URLs
        async with aiohttp.ClientSession() as session:
            if is_image_search:
                image_urls_task = google_search(session, query, search_api_key, search_engine_id, number_to_return = images_to_return, search_images = True)
                image_urls = await image_urls_task

                total_image_urls.extend(image_urls)
            else:
                urls_task = google_search(session, query, search_api_key, search_engine_id, number_to_return = google_search_urls_to_return, search_images = False)
                urls = await urls_task
    else:
        if is_image_search:
            image_urls = []  # No image URLs needed if do_google_search is False
        else:
            urls = websites_to_use # Assign urls directly without doing google search

    if is_image_search:
        print("Image URLs for query [", query, "]:")
        print(image_urls)
        print('*****************')
    else:
        print("URLs for query [", query, "]:")
        print(urls)
        print('*****************')

    '****************************************** Handles website URLs and returns a intermediate GPT answer ***************************************'

    if is_image_search:
      return {"total_image_urls": total_image_urls}
    else:

      semaphore = asyncio.Semaphore(100) # Limit the number of concurrent tasks ONLY for PDFs - set high number to disable it

      # Create async tasks for fetching and processing HTML
      tasks = [fetch_and_process_html(driver, url, process_to_db=True, semaphore=semaphore) for driver, url in zip(driver_list, urls)]
      database_list = await asyncio.gather(*tasks)

      relevant_information = await find_relevant_docs(query, database_list, urls_used = drivers_to_create, num_of_docs_to_return = k_value_similarity_search)
      relevant_info_1, relevant_info_2 = relevant_information

      formatted_web_scrapper_system_instructions = web_scrapper_system_instructions.format(
          relevant_info_placeholder1 = relevant_info_1,
          relevant_info_placeholder2 = relevant_info_2
      )

      gpt_answer = await return_gpt_answer(formatted_web_scrapper_system_instructions, query)

      return {"gpt_answer": gpt_answer}
