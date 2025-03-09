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
import os
from IPython.display import clear_output

# Third-Party Library Imports
from mutagen.mp3 import MP3

# Local Application/Library-Specific Imports
import modules.configs as configs # Import 'configs' module directly to change global states

from modules.audio_handler import play_audio
from modules.configs import (
    google_search_urls_to_return,
    images_to_return,
    search_api_key,
    search_engine_id,
    system_instructions_generate_livestream,
    use_tts_api,
    websites_and_search_queries
)
from modules.database_handler import create_databases_handler
from modules.file_manager import download_file_handler, generate_scene_content, save_images_async
from modules.high_level_orchestrators import create_script_handler
from modules.utils import initialize_executors, reset_global_variables, shutdown_executors, add_to_configs
from modules.web_scraper import fetch_images_off_specific_url


async def generate_livestream(audio_already_playing, first_call, **scenes_config):
    '***************************************************** Centralized configuration for all scenes ******************************************************'
    if first_call:
      tt_storm_url = scenes_config['tt_storm_url'] 
      scenes_config = scenes_config['scenes']  

      # Add values to modules.config for access after the first call
      add_to_configs(tt_storm_url, scenes_config) 

    else:
      tt_storm_url = configs.tt_storm_url
      scenes_config = configs.scenes_config
    '****************************************************************************************************************************************************'

    database_tasks = [
        asyncio.create_task(
            create_databases_handler(
                search_queries = scene['search_queries'],
                search_api_key = search_api_key,
                search_engine_id = search_engine_id,
                do_google_search = False,
                websites_to_use = scene['websites'],
            )
        ) for scene in scenes_config['scenes']
    ]

    # Create an async task to scrape the specific storm URL
    image_scrape_task = asyncio.create_task(fetch_images_off_specific_url(
        url = tt_storm_url
    ))

    # Process results
    total_image_urls, (database_results) = await asyncio.gather(
        image_scrape_task,
        asyncio.gather(*database_tasks)
    )
    configs.database_results = database_results

    '****************************************************************************************************************************************************'
    """ controller for generating scripts and items """

    # Reset counters to ensure functionality when code is rerun
    reset_global_variables()

    # Initialize executors
    initialize_executors()

    # Create scene tasks dynamically based on the configurations
    scene_tasks = [
        asyncio.create_task(
            create_script_handler(
                queries_dictionary_list = db_result,  # Corresponding database result
                websites_used = scene['websites'],
                final_script_system_instructions = scene['system_instructions'],
                language = scene['language'],
            )
        )
        for scene, db_result in zip(scenes_config, database_results)
    ]
    # Execute all scene tasks concurrently
    gathered_results = await asyncio.gather(image_scrape_task, *scene_tasks)
    total_image_urls = gathered_results[0]
    scenes_items = gathered_results[1:]

    # Shutdown executors
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
            scenes_items,
            initial_previous_task = None)

    if audio_already_playing == True:
        return scenes_items
    '****************************************************************************************************************************************************'


async def controller_play_audio_and_download_handler(scenes_items, initial_previous_task):
    print("Entering 'controller_play_audio_and_download_handler'")

    # First iteration: Returns 'final_audio_task', the last task in the sequence to be used as a param in future iterations
    configs.use_tts_api = True
    final_audio_task = await controller_play_audio_and_download(
        scenes_items, initial_previous_task
    )
    configs.use_tts_api = False

    # Play i more iterations determined by range() and handles updating scene_items on last iteration
    total_iterations = 10
    for i in range(total_iterations):
        print("Iteration number:", i)
        if i == (total_iterations - 1):  # If last iteration, play audio and update scene_items concurrently
            clear_output(wait=True)

            # Generate new scene items concurrently
            generate_new_scene_items_task = asyncio.create_task(generate_livestream(
                    audio_already_playing = True,
                    first_call = False
            ))

            # Play audio and generate new scenes concurrently
            print("Last iteration playing, updating scene_items concurrently")
            final_audio_task, new_scenes_items = await asyncio.gather(
                controller_play_audio_and_download(
                    scenes_items, initial_previous_task=final_audio_task
                ),
                generate_new_scene_items_task
            )

            # Recursive call with updated scene items
            print("Calling 'controller_play_audio_and_download_handler' with new_scene_items")
            await controller_play_audio_and_download_handler(
                new_scenes_items, initial_previous_task=final_audio_task
            )
        else:
            # Normal iteration without generating new content
            final_audio_task = await controller_play_audio_and_download(
                scenes_items, initial_previous_task=final_audio_task
            )


async def controller_play_audio_and_download(scenes_items, initial_previous_task):
    previous_audio_task = initial_previous_task
    for index, scene_items in enumerate(scenes_items):
        if initial_previous_task and index == 0:
          print(f" {index+1} audio being generated, {len(scene_items)} audio being played")
        else:
          print(f" {index+1} audio being generated, {index} audio being played")

        audio_file_name = f"scene_{index+1}_audio"

        previous_audio_task = await process_scene(
            scene_items=scene_items,
            audio_file_name=audio_file_name,
            previous_audio_task=previous_audio_task
        )
    return previous_audio_task


async def process_scene(scene_items, audio_file_name, previous_audio_task=None):
    # Check for YouTube interactivity audio before proceeding
    if os.path.exists('combined_output_youtube_interactivity.mp3'):
        print("YouTube interactivity audio detected. Playing before processing the next scene.")

        if previous_audio_task:  # If previous audio is already playing
            await previous_audio_task

        youtube_audio_task = asyncio.create_task(play_audio({
            'name': 'combined_output_youtube_interactivity.mp3',
            'duration_seconds': MP3('combined_output_youtube_interactivity.mp3').info.length
        }))
        generate_scene_task = asyncio.create_task(generate_scene_content(
            items=scene_items,
            language='aus', # TEMP, SWITCH LANGUAGE CONFIGS TO BE GLOBALLY ACCESSIBLE
            audio_file_name=audio_file_name
        ))
        _, (saved_stream_items, audio_info) = await asyncio.gather(
            youtube_audio_task,
            generate_scene_task
        )
        os.remove('combined_output_youtube_interactivity.mp3')
        print("YouTube interactivity audio played and removed.")

    elif previous_audio_task:
        # If previous audio is already playing and no YouTube interactivity audio
        generate_scene_task = asyncio.create_task(generate_scene_content(
            items=scene_items,
            language='aus', # TEMP, SWITCH LANGUAGE CONFIGS TO BE GLOBALLY ACCESSIBLE
            audio_file_name=audio_file_name
        ))
        _, (saved_stream_items, audio_info) = await asyncio.gather(
            previous_audio_task,
            generate_scene_task
        )
    else:
        # If there's no previous audio and no YouTube interactivity, just generate the scene content
        saved_stream_items, audio_info = await generate_scene_content(
            items=scene_items,
            language='aus', # TEMP, SWITCH LANGUAGE CONFIGS TO BE GLOBALLY ACCESSIBLE
            audio_file_name=audio_file_name
        )
    # Download the items to the local computer
    await download_file_handler(saved_stream_items)

    # Start playing the audio for the current scene
    play_audio_task = asyncio.create_task(play_audio(audio_info))

    return play_audio_task  # Passed into this function again as previous_audio_task
