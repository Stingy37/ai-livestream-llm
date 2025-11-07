"""
This module provides functions related to saving (to colab), loading (from colab), and downloading (to local) files

Functions:
    generate_scene_content()

    save_stream_items_to_colab()
    save_text_file()
    save_images_async()
    save_image()
    clear_directory()

    download_file_handler()
    download_file()
    create_download_js()
"""


# Standard Library Imports
import asyncio
import base64
import os
import random
import shutil
import zipfile

# Third-Party Library Imports
import aiohttp
from IPython.display import display, Javascript

# Local Application/Library-Specific Imports
from modules.audio_handler import generate_audio_handler
from modules.configs import tt_scrap_headers
from modules.schema import (
    SavedStreamItems,
    SceneItems,
    AudioInfo,
    GenerateSceneReturn,
    FilePath,
    ScrapedImageList
)


async def generate_scene_content(
    items: SceneItems,
    language: str,
    audio_file_name: str
) -> GenerateSceneReturn:
    """
    Function to generate audio and save items for a scene.
    """
    save_stream_items_task = asyncio.create_task(save_stream_items_to_colab(items))
    generate_audio_task = asyncio.create_task(generate_audio_handler(items, file_name=audio_file_name))

    # Run both tasks concurrently and unpack the results
    saved_stream_items, audio_info = await asyncio.gather(save_stream_items_task, generate_audio_task)
    return saved_stream_items, audio_info


# Saves key messages and images to colab env for download later
async def save_stream_items_to_colab(item_information):
    key_messages = item_information.get('key_messages')
    topic = item_information.get('topic')
    image_urls = item_information.get('images')

    tasks = []

    # Create tasks only for existing items
    if key_messages:
        key_messages_save_task = asyncio.create_task(save_text_file(key_messages, filename="key_messages.txt"))
        tasks.append(key_messages_save_task)

    if image_urls:
        image_save_task = asyncio.create_task(save_images_async(image_urls))
        tasks.append(image_save_task)

    if topic:
        topic_save_task = asyncio.create_task(save_text_file(topic, filename="current_topic.txt"))
        tasks.append(topic_save_task)

    # Gather all tasks
    results = await asyncio.gather(*tasks)

    text_filename = results[0] if key_messages else None
    image_zip_filename = results[1] if key_messages and image_urls else results[0] if image_urls else None
    topic_filename = results[-1] if topic else None

    print("text_filename:", text_filename)
    print("image_zip_filename:", image_zip_filename)
    print("topic_filename:", topic_filename)
    return text_filename, image_zip_filename, topic_filename


# Saves text file to google colab env for usage later
async def save_text_file(text, filename):
    with open(filename, 'w') as file:
        file.write(text)

    return filename


#################################################################### saving images ##############################################################################


# Creates a ZIP file from colab folder containing images and saves to local computer
async def save_images_async(total_image_urls):

    images_save_directory = "/content/images_for_stream"
    zip_file_path = "/content/images_for_stream.zip"

    # Clear the Google Colab directory
    clear_directory(images_save_directory)

    # Create a list to hold all the tasks
    tasks = []

    # Create an asynchronous session
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
        # Iterate over the image URLs
        for i, url in enumerate(total_image_urls):
            save_path = os.path.join(images_save_directory, f'image_{i}.jpg')
            # Create a task for each download
            tasks.append(save_image(session, url, save_path))
            await asyncio.sleep(1)

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    # Create a zip file of the images
    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
        for root, dirs, image_files in os.walk(images_save_directory):
            for image_file in image_files:
                zipf.write(os.path.join(root, image_file), image_file)

    filename = os.path.basename(zip_file_path)
    return filename


# This clears the image directory to prevent duplicates or leftover images from previous runs
def clear_directory(directory):
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)


# Saves images to a Google Colab folder for usage later
async def save_image(session, url, save_path):
    try:
        headers = tt_scrap_headers # For modularity later, make header a passable parameter
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                with open(save_path, 'wb') as file:
                    file.write(await response.read())
            else:
                print(f"Failed to download image from {url}: Status code {response.status}")
    except aiohttp.ClientError as e:
        print(f"Client error occurred while downloading image from {url}: {e}")
    except Exception as e:
        print(f"Unexpected error downloading image from {url}: {e}")


############################################################## Download / Saving to local computer ##############################################################


# Function to handle downloading multiple files in parallel
async def download_file_handler(file_names_to_download):

    # Handles single strings by turning it into a list
    if isinstance(file_names_to_download, str):
        file_names_to_download = [file_names_to_download]

    # Don't do anything if there is nothing to download
    if file_names_to_download is None:
      print("No file names provided.")
      return

    print(f"Received file names to download: {file_names_to_download}")

    # Filter out None values
    valid_file_names = [file_name for file_name in file_names_to_download if file_name is not None]
    print(f"Valid file names: {valid_file_names}")

    last_delay = None
    for file_name in valid_file_names:
        while True:
            delay = random.randint(1, 10)  # Choose a random integer between 1 and 15
            if last_delay is None or abs(delay - last_delay) > 4:  # Ensure the new delay is at least 3 seconds apart
                last_delay = delay
                break
        await asyncio.sleep(delay)  # Adds a random delay between downloads to solve Automator issues
        download_file(file_name)


# Saves downloads to local computer
def download_file(file_name):
    print(f"Starting download task for: {file_name}")

    # Read the file content
    with open(file_name, 'rb') as f:
        file_content = f.read()

    # Generate and execute the JavaScript to trigger the download
    download_js = create_download_js(file_name, file_content)
    display(Javascript(download_js))


# Uses JS to bypass cell execution problem when saving to local
def create_download_js(filename, file_content):
    # Encode file content to base64
    b64_content = base64.b64encode(file_content).decode()
    mime_type = 'application/octet-stream'

    if filename.endswith('.txt'):
        mime_type = 'text/plain'
    elif filename.endswith('.zip'):
        mime_type = 'application/zip'
    # Add more file type checks if needed

    return f"""
    var link = document.createElement('a');
    link.href = 'data:{mime_type};base64,{b64_content}';
    link.download = '{filename}';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    """
