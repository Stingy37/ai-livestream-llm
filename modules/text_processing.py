"""
This module provides everything related to processing text, particularly in preparing HTML for vector database
"""


# Standard Library Imports
import re

# Local Application/Library-Specific Imports
from modules.configs import splitter_pattern


# Gets rid of unnecessarily large pieces of HTML
def filter_content(content):
    return re.sub(r'data:image\/[a-zA-Z]+;base64,[^\s]+', '', content)


# Splits a website's markdown into small chunks for vector database
def split_markdown_chunks(markdown_document, max_words):
    clean_texts = re.split(splitter_pattern, markdown_document, flags=re.MULTILINE) # splitter_pattern can be found in config.py
    final_chunks = []
    for text in clean_texts:
        words = text.split()
        if len(words) > max_words:
            chunk_start = 0
            while chunk_start < len(words):
                chunk_end = min(chunk_start + max_words, len(words))
                final_chunks.append(" ".join(words[chunk_start:chunk_end]))
                chunk_start = chunk_end
        else:
            final_chunks.append(text)
    return final_chunks


# remove empty lines to make displaying in OBS scrolling possible
def filter_key_messages(message_to_filter, spaces=40):
    # Split the message into lines
    lines = message_to_filter.strip().split("\n")
    # Remove any empty lines and strip leading/trailing spaces from each line
    filtered_lines = [line.strip() for line in lines if line.strip()]
    space_separator = " " * spaces
    # Join the lines back together with the specified number of spaces between each line
    filtered_message = space_separator.join(filtered_lines)
    filtered_message = " " * spaces + filtered_message
    return filtered_message
