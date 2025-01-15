"""
This initializes the environment, and starts main program loop
"""

import asyncio
from modules.utils import initialize_environment
from modules.livestream_manager import generate_livestream

def main_program():
  # sets up environment for running code
  initialize_environment()

  # this provides all the media necessary for livestream - a TTS voice, images, key messages, etc.
  asyncio.run(generate_livestream(audio_already_playing = False))

main_program()