"""
This module provides functions related to interacting with OpenAI's API and returning an answer

Functions:
    generate_text()
    return_gpt_answer()
"""


# Standard Library Imports
import asyncio
import logging

# Third-Party Library Imports
import openai
from openai import APIError, RateLimitError

# Local Application/Library-Specific Imports
from modules.configs import client
from modules.text_processing import filter_key_messages


async def generate_text(combined_answers, system_instructions, item_being_generated):
    print(f"generating {item_being_generated}")
    gpt_answer = await return_gpt_answer(system_instructions, combined_answers)

    if item_being_generated == "key_messages":
      key_messages_filtered = filter_key_messages(gpt_answer)
      return key_messages_filtered
    else:
      return gpt_answer


# Generic function to use ChatGPT with retries
async def return_gpt_answer(system, user, max_retries=3):
    for attempt in range(max_retries):
        try:
            completion = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return completion.choices[0].message.content.strip()
        except openai.APITimeoutError as e:
            logging.warning(f"OpenAI API Timeout Error (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)  # Wait for 2 seconds before retrying
            else:
                return "Error: OpenAI API Timeout"
        except (APIError, RateLimitError) as e:
            logging.error(f"An OpenAI API error occurred (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                return "Error: Unable to generate response"
        except Exception as e:
            logging.error(f"An unexpected error occurred (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                return "Error: Unable to generate response"
