"""
This module provides functions that coordinate playing of audio and time content delivery
(ie. downloads to local, processing scenes in sequence, etc.)

Functions:
    generate_livestream()
    collections_handler()
    scene_handler()
    process_one_scene()
"""


# Standard Library Imports
import asyncio
import importlib
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
from modules.database_handler import create_databases_handler, create_unique_databases
from modules.file_manager import download_file_handler, generate_scene_content, save_images_async
from modules.high_level_orchestrators import create_script_handler
from modules.utils import initialize_executors, reset_global_variables, shutdown_executors
from modules.web_scraper import fetch_images_off_specific_url


async def generate_livestream(audio_already_playing, first_call, collection_config):
    '***************************************************** Centralized configuration for all scenes ******************************************************'
    if first_call:
      # unpack everything from the provided configs
      scenes_config = collection_config["scenes"] # collection_config represents a dictionary with ALL extra parameters used in function call 
                                                  # to build the collection
      tt_storm_url = collection_config["tt_storm_url"]
      scenes_config_list = collection_config["scenes"] # List of dictionaries
                                                       # each dictionary contains info about a individual scene 
      total_collection_iterations = collection_config["total_collection_iterations"] # how many times to play this full collection 

      print("tt_storm_url:", tt_storm_url)
      print("scenes_config:", scenes_config_list)
      print("total_collection_iterations:", total_collection_iterations)

      # Add values to modules.config for access after the first call 
      configs.tt_storm_url = tt_storm_url
      configs.scenes_config_list = scenes_config_list
      configs.total_collection_iterations = total_collection_iterations

    else:
      # every call besides the first, use the saved configs 
      tt_storm_url = configs.tt_storm_url
      scenes_config_list = configs.scenes_config_list
      total_collection_iterations = configs.total_collection_iterations
    '****************************************************************************************************************************************************'

    database_task = asyncio.create_task(create_databases_handler(scenes_config_list))

    # Create an async task to scrape the specific storm URL
    image_scrape_task = asyncio.create_task(fetch_images_off_specific_url(
        url = tt_storm_url
    ))

    # Process results
    total_image_urls, (scene_database_results) = await asyncio.gather(
        image_scrape_task,
        database_task
    )

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
        for scene, db_result in zip(scenes_config_list, scene_database_results)
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
    """ controller for playing audio and downloads (ie. what actually goes into playing the livestream) """
    if audio_already_playing == False:
        await collections_handler(
            scenes_items,
            initial_previous_task = None, 
            total_collection_iterations = total_collection_iterations)

    if audio_already_playing == True:
        return scenes_items
    '****************************************************************************************************************************************************'


async def collections_handler(scenes_items, initial_previous_task, total_collection_iterations=2):
    """
    Orchestrates the playback and regeneration cycles of an entire collection of scenes.

    This function represents one full 'livestream cycle' (i.e. multiple scenes within scenes_items):
    - Iterates through a collection of scenes using `scene_handler()`
    - Optionally regenerates new scenes after the last iteration
    - Manages concurrent audio playback and next-collection generation

    Args:
        scenes_items (list): A list of scene data dictionaries, with each scene having its own entry.
        initial_previous_task (asyncio.Task or None): The audio task currently playing (if any).

    Returns:
        None
    """

    print("Entering 'collections_handler'")

    # First iteration: Returns 'final_audio_task', the last task in the sequence to be used as a param in future iterations
    configs.use_tts_api = True
    final_audio_task = await scene_handler(
        scenes_items, initial_previous_task
    )
    configs.use_tts_api = False

    # Iterate through the total number of collection playback cycles.
    # Each iteration represents one complete pass through all current scenes.
    for i in range(total_collection_iterations):
        print("Collection iteration number:", i)

        # On the final iteration of this collection cycle:
        # - Continue playing current scenes via `scene_handler()`
        # - Simultaneously generate a new batch of scenes via `generate_livestream()`
        # - When both complete, recursively call `collections_handler()` to begin the next cycle
        if i == (total_collection_iterations - 1): 
            clear_output(wait=True)

            # Generate new scene items concurrently
            generate_new_scene_items_task = asyncio.create_task(generate_livestream(
                    audio_already_playing = True,
                    first_call = False
                    # now, we don't reuse scene_configs and instead use what is saved inside modules.configs 
            ))

            # Play audio and generate new scenes concurrently
            print("Last iteration playing, updating scene_items concurrently")
            final_audio_task, new_scenes_items = await asyncio.gather(
                scene_handler(
                    scenes_items, initial_previous_task=final_audio_task
                ),
                generate_new_scene_items_task
            )

            # Recursive call with updated scene items AFTER generate_livestream is done 
            print("Calling 'collections_handler' with new_scene_items")
            await collections_handler(
                new_scenes_items, 
                initial_previous_task=final_audio_task, 
                total_collection_iterations=total_collection_iterations
            )

        # For all but the last iteration:
        # - Play through all scenes in sequence using `scene_handler()`
        # - `final_audio_task` holds the last scene’s audio playback task,
        #   which is passed forward so the next collection waits for it to finish.
        else:
            final_audio_task = await scene_handler(
                scenes_items, initial_previous_task=final_audio_task
            )


async def scene_handler(scenes_items, initial_previous_task):
    """
    Sequentially handles each scene in the given collection (scenes_items).

    For each scene in the collection (scenes_items):
      - Assigns a unique audio file name based on its index
      - Invokes `process_one_scene()` to play the current audio while generating the next scene
      - Returns the last audio task so the next collection can continue from it

    Args:
        scene_items (list): A list of scene content items for the current collection.
        previous_audio_task (asyncio.Task or None): The currently playing audio, if any.

    Returns:
        asyncio.Task: The final audio playback task for the collection.
    """

    previous_audio_task = initial_previous_task
    for index, scene_items in enumerate(scenes_items):
        if initial_previous_task and index == 0:
          print(f" {index+1} audio being generated, {len(scene_items)} audio being played")
        else:
          print(f" {index+1} audio being generated, {index} audio being played")
        audio_file_name = f"scene_{index+1}_audio"

        previous_audio_task = await process_one_scene(
            scene_items=scene_items,
            audio_file_name=audio_file_name,
            previous_audio_task=previous_audio_task
        )
    return previous_audio_task


async def process_one_scene(scene_items, audio_file_name, previous_audio_task=None):
    # Check for YouTube interactivity audio before proceeding (advanced feature, if statement redundant but not harmless otherwise)
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
            language='ph', # TEMP, SWITCH LANGUAGE CONFIGS TO BE GLOBALLY ACCESSIBLE
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
            language='ph',
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
            language='ph',
            audio_file_name=audio_file_name
        )
    # Download the items to the local computer
    await download_file_handler(saved_stream_items)

    # Start playing the audio for the current scene
    play_audio_task = asyncio.create_task(play_audio(audio_info))

    return play_audio_task  # Passed into this function again as previous_audio_task
