"""
This module provides functions related to audio generation, which combined essentially serves as TTS
"""


# Standard Library Imports
import asyncio
import time

# Third-Party Library Imports
from IPython.display import Audio, display

# Local Application/Library-Specific Imports
import modules.configs as configs # Must import entire module to use use_tts_api as flag

from modules.configs import client
from pydub import AudioSegment


async def generate_audio_handler(generated_items, file_name, tts_flag_override = False):
  generate_audio_start = time.time()

  # Handle voice (choose correct accent)
  voice = {
      'aus': 'fable'
  }.get(configs.scenes_config['language'], 'shimmer') # Essentially switch-case, default value is shimmer

  # Gets script from generated_items
  script_to_read = generated_items['script']

  # splits the given script into halves in case it is too long for OpenAI TTS Model
  part1 = script_to_read[:len(script_to_read)//2]
  part2 = script_to_read[len(script_to_read)//2:]

  print(part1)
  print('*********************************************')
  print(part2)

  # Generates parts (adds some silence at the start)
  await generate_audio_parts(part1, part2, voice, file_name, tts_flag_override)

  # Load the audio files
  audio_part1, audio_part2, audio_part3 = await load_audio_files(file_name)

  # Combine the audio files
  combined_audio = audio_part1 + audio_part2 + audio_part3

  # Export the combined audio file
  combined_file_name = f"combined_output_{file_name}.mp3"
  combined_audio = combined_audio[:60000] # Truncate to ___ seconds for testing purposes, comment line out if otherwise
  combined_audio.export(combined_file_name, format="mp3")

  # Get the duration of the combined audio
  audio_duration = combined_audio.duration_seconds
  print("Length of MainSummary scene audio:", audio_duration)

  # Log the amount of time it takes to generate audio
  generate_audio_end = time.time()
  print(f"Time taken to generate audio: {generate_audio_end - generate_audio_start}")

  # Return combined audio export full file name and duration for usage in play_audio
  return {"name": combined_file_name, "duration_seconds": audio_duration}


# Generates 3 mp3 files for use in load_audio_files
async def generate_audio_parts(part1, part2, voice, file_name, tts_flag_override):
    await asyncio.gather(
        generate_voice_recording(part1, voice, f"output_part1_{file_name}.mp3", tts_flag_override),
        generate_voice_recording(part2, voice, f"output_part2_{file_name}.mp3", tts_flag_override),
        generate_empty_audio(file_name)
    )


async def generate_voice_recording(message, voice, file_name, tts_flag_override):
    # Check if the voice recording already exists in Google Colab's file system
    if configs.use_tts_api == False and tts_flag_override == False:
        print(f"File '{file_name}' already exists. Skipping TTS API call.")
        return

    # Send request to OpenAI TTS model if file doesn't exist
    else:
      print(f"TTS API called for File '{file_name}'")
      response = await client.audio.speech.create(
          model="tts-1-hd",
          voice=voice,
          input=str(message)
      )

    # Stream the response to a file
    response.stream_to_file(file_name)
    print(f"Audio saved to '{file_name}'")


# Adds some silence to beginning to wait for Image ZIP file + Key messages to download
async def generate_empty_audio(file_name):
    empty_audio = AudioSegment.silent(duration=5000)  # 5 seconds of silence
    await asyncio.to_thread(empty_audio.export, f"empty_audio_{file_name}.mp3", format="mp3")


# Load the audio files concurrently, to be joined into combined audio
async def load_audio_files(file_name):
    audio_part1_task = asyncio.to_thread(AudioSegment.from_mp3, f"empty_audio_{file_name}.mp3")
    audio_part2_task = asyncio.to_thread(AudioSegment.from_mp3, f"output_part1_{file_name}.mp3")
    audio_part3_task = asyncio.to_thread(AudioSegment.from_mp3, f"output_part2_{file_name}.mp3")

    audio_part1, audio_part2, audio_part3 = await asyncio.gather(audio_part1_task, audio_part2_task, audio_part3_task)
    return audio_part1, audio_part2, audio_part3


async def play_audio(file_info):
    # Get info (duration and name) from file_info
    print("file_info:", file_info)
    audio_duration = file_info['duration_seconds']
    file_name = file_info['name']

    # Play the given audio file in Colab
    actual_finish_time_start = time.time()

    # Create a display handle for the audio
    audio_display = display(Audio(file_name, autoplay=True), display_id=True)
    await asyncio.sleep(audio_duration)

    # Clear the specific display after the audio has played
    audio_display.update("\n\n")

    # Debugging
    actual_finish_time_end = time.time()
    print(f"actual finish time taken for {file_name} to play: {actual_finish_time_end - actual_finish_time_start}")
    print(f"{file_name} audio done playing, expected finish time: {audio_duration}")

