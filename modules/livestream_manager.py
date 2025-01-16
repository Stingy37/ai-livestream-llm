"""
This module provides functions that coordinate playing of audio and time content delivery
(ie. downloads to local, processing scenes in sequence, etc.)

Functions:
    generate_livestream()
    controller_play_audio_and_download_handler()
    controller_play_audio_and_download()
    process_scene()
"""


# Standard Library Imports
import asyncio
from IPython.display import clear_output

# Local Application/Library-Specific Imports
from modules.audio_handler import play_audio
from modules.configs import system_instructions_generate_livestream, websites_and_search_queries
from modules.file_manager import download_file_handler, generate_scene_content, save_images_async
from modules.high_level_orchestrators import create_script
from modules.utils import initialize_executors, reset_global_variables, shutdown_executors
from modules.web_scraper import fetch_images_off_specific_url


async def generate_livestream(audio_already_playing):
    '****************************************************************************************************************************************************'
    """ controller for downloading images off of tropical tidbits """

    # Create an async task to scrape the specific URL - executed in junction with tasks in second controller
    image_scrape_task = asyncio.create_task(fetch_images_off_specific_url(
        url = websites_and_search_queries['tropical_tidbits_storm_url']
    ))

    '****************************************************************************************************************************************************'
    """ controller for generating scripts and items """

    # Reset counters to ensure functionality when code is rerun
    reset_global_variables()

    # Creates scripts and items for various scenes
    first_scene_task = asyncio.create_task(
        create_script(
            search_queries_list = websites_and_search_queries['tropics_main_search_queries'], # Universal across all languages
            image_search_queries = None,
            final_script_system_instructions = system_instructions_generate_livestream['tropics_news_reporter_system_instructions_en'],
            return_images = False,
            do_google_search = False,
            websites_to_use = websites_and_search_queries['tropics_forecast_websites_ph'],
            k_value_similarity_search = 4,
            language = "en" # supported languages: en, cn, vt, jp, ph
            )) # Returns items object that contains script, image urls if enabled, key messages, and topic

    second_scene_task = asyncio.create_task(
        create_script(
            search_queries_list = websites_and_search_queries['city_forecast_queries_one_ph'], # This is also the google search terms, if do_google_search = True
            image_search_queries = None,
            final_script_system_instructions = system_instructions_generate_livestream['city_forecast_system_instructions_ph'],
            return_images = False,
            do_google_search = False,
            websites_to_use = websites_and_search_queries['city_forecast_websites_one_ph'],
            k_value_similarity_search = 4,
            language = "ph" # supported languages: en, cn, vt, jp, ph
            ))

    third_scene_task = asyncio.create_task(
        create_script(
            search_queries_list = websites_and_search_queries['city_forecast_queries_two_ph'], # This is also the google search terms, if do_google_search = True
            image_search_queries = None,
            final_script_system_instructions = system_instructions_generate_livestream['city_forecast_system_instructions_ph'],
            return_images = False,
            do_google_search = False,
            websites_to_use = websites_and_search_queries['city_forecast_websites_two_ph'],
            k_value_similarity_search = 4,
            language = "ph" # supported languages: en, cn, vt, jp, ph
            ))

    initialize_executors() # initializes executors used in n_scene_tasks
    # Execute image and scene tasks concurrently, and handles unpacking them
    total_image_urls, (first_scene_items, second_scene_items, third_scene_items) = await asyncio.gather(
        image_scrape_task,
        asyncio.gather(first_scene_task, second_scene_task, third_scene_task)
    )
    shutdown_executors()


    '****************************************************************************************************************************************************'
    """ controller for saving specific url images to colab env. """

    # Save images and then downloads to local system
    images_zip_filename = await save_images_async(total_image_urls)
    await download_file_handler(images_zip_filename)

    '****************************************************************************************************************************************************'
    """ controller for playing audio and downloads (ie. livestream timeline ) """
    if audio_already_playing == False:
        await controller_play_audio_and_download_handler(
            first_scene_items,
            second_scene_items,
            third_scene_items,
            initial_previous_task = None)

    if audio_already_playing == True:
        return first_scene_items, second_scene_items, third_scene_items
    '****************************************************************************************************************************************************'


async def controller_play_audio_and_download_handler(first_scene_items, second_scene_items, third_scene_items, initial_previous_task):
    global use_tts_api

    print("Entering 'controller_play_audio_and_download_handler'")

    # First iteration: Returns 'play_audio_task_three', the last task in the sequence to be used as a param in future iterations
    use_tts_api = True
    play_audio_task_three = await controller_play_audio_and_download(first_scene_items, second_scene_items, third_scene_items, initial_previous_task = initial_previous_task)
    use_tts_api = False

    # Play i more iterations determined by range() and handles updating scene_items on last iteration
    total_iterations = 1
    for i in range(total_iterations):
        print("Iteration number:", i)
        if i == (total_iterations - 1):  # If last iteration, play audio and update scene_items concurrently

            # Avoid cell output size limit by clearing output
            clear_output(wait=True)

            # Create a task to generate up-to-date scene_items on last iteration
            generate_new_scene_items_task = asyncio.create_task(generate_livestream(audio_already_playing = True))

            print("Last iteration playing, updating scene_items concurrently")
            play_audio_and_generate_scene_items = await asyncio.gather(
                controller_play_audio_and_download(first_scene_items, second_scene_items, third_scene_items, initial_previous_task = play_audio_task_three),
                generate_new_scene_items_task
            )

            # Unpack the new scene items to call this function again and last audio task
            print("Generated new_scene_items")
            play_audio_task_three, (new_first_scene_items, new_second_scene_items, new_third_scene_items) = play_audio_and_generate_scene_items

            # Call the handler again with the new content
            print("Calling 'controller_play_audio_and_download_handler' with new_scene_items")
            await controller_play_audio_and_download_handler(new_first_scene_items, new_second_scene_items, new_third_scene_items, initial_previous_task = play_audio_task_three)

        else:
            # Normal iteration without generating new content
            print(f"play_audio_task_three completion status before being passed in: {play_audio_task_three.done()}")
            # Create a new task for this iteration
            play_audio_task_three = await controller_play_audio_and_download(
                first_scene_items,
                second_scene_items,
                third_scene_items,
                initial_previous_task = play_audio_task_three
            )


async def controller_play_audio_and_download(first_scene_items, second_scene_items, third_scene_items, initial_previous_task):
    # Process the first scene
    if initial_previous_task:
        print("1st audio being generated, 3/3 audio being played")
        play_audio_task_one = await process_scene(
            scene_items = first_scene_items,
            audio_file_name = "first_scene_audio",
            previous_audio_task = initial_previous_task
        )
    else:
        print("1st audio being generated, none audio being played")
        play_audio_task_one = await process_scene(
        scene_items = first_scene_items,
        audio_file_name = "first_scene_audio",
        previous_audio_task = initial_previous_task
    )

    # Process the second scene while the first audio plays
    print("2nd audio being generated, 1/3 audio being played")
    play_audio_task_two = await process_scene(
        scene_items = second_scene_items,
        audio_file_name = "second_scene_audio",
        previous_audio_task = play_audio_task_one
    )

    # Process the third scene while the second audio plays
    print("3rd audio being generated, 2/3 audio being played")
    play_audio_task_three = await process_scene(
        scene_items = third_scene_items,
        audio_file_name = "third_scene_audio",
        previous_audio_task = play_audio_task_two
    )

    return play_audio_task_three


async def process_scene(scene_items, audio_file_name, previous_audio_task=None):
    # If there was a previous audio playing, don't wait for it to finish yet
    if previous_audio_task:
        # Start generating the next scene content while the previous audio plays
        generate_scene_task = asyncio.create_task(generate_scene_content(
            items = scene_items,
            audio_file_name = audio_file_name
        ))

        # Wait for both tasks concurrently (previous audio + generating new scene)
        _, (saved_stream_items, audio_info) = await asyncio.gather(
            previous_audio_task,
            generate_scene_task
        )
    else:
        # If there's no previous audio, just generate the scene content
        saved_stream_items, audio_info = await generate_scene_content(
            items = scene_items,
            audio_file_name = audio_file_name
        )

    # Download the items to the local computer
    await download_file_handler(saved_stream_items)

    # Start playing the audio for the current scene
    play_audio_task = asyncio.create_task(play_audio(audio_info))

    return play_audio_task # Passed into this function again as previous_audio_task
