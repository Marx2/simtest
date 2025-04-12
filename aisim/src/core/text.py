import pygame
import os
from typing import Optional, Tuple, List, Dict, Any
from aisim.src.core.configuration import config_manager
import logging # Added for potential future use in wrap_text

# Note: Removed unused bubble drawing functions, font initialization,
# and related constants as they are handled by pygame_gui in main.py.

def wrap_text(text, font, max_width):
    """Wraps text to fit within a specified width, preserving paragraphs."""
    lines = []
    # Handle potential None or empty text
    if not text:
        return [""] # Return a list with an empty string for consistency

    if not font:
        logging.error("wrap_text called with no font provided.")
        # Cannot wrap without a font, return original text split by newlines
        return text.split('\n')

    # Split into paragraphs first to preserve line breaks
    paragraphs = text.split('\n')
    for paragraph in paragraphs:
        words = paragraph.split(' ')
        current_line = []
        while words:
            word = words.pop(0)
            # Handle empty words resulting from multiple spaces
            if not word:
                continue

            test_line = ' '.join(current_line + [word])
            try:
                # Check if the line fits
                if font.size(test_line)[0] <= max_width:
                    current_line.append(word)
                # If the line doesn't fit AND it's not the only word
                elif current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word] # Start new line with the word that didn't fit
                # If the line doesn't fit and it IS the only word (word is too long)
                else:
                    # Simple character-based wrap for overly long words
                    temp_word = ""
                    for char_index, char in enumerate(word):
                        if font.size(temp_word + char)[0] <= max_width:
                            temp_word += char
                        else:
                            # If even the first character doesn't fit, add it anyway
                            if char_index == 0:
                                lines.append(char)
                                temp_word = "" # Reset for next char
                            else:
                                lines.append(temp_word)
                                temp_word = char # Start new line part with current char
                    if temp_word: # Add the remainder of the long word
                        lines.append(temp_word)
                    current_line = [] # Reset current line after handling long word
            except pygame.error as e:
                 logging.error(f"Pygame error during text wrapping: {e}. Text: '{test_line}'")
                 # Fallback: add the word that caused the error as a new line
                 if current_line: # Add previous line if any
                     lines.append(' '.join(current_line))
                 lines.append(word) # Add the problematic word
                 current_line = [] # Reset

        # Add the last line of the paragraph if it has content
        if current_line:
            lines.append(' '.join(current_line))

    # Ensure at least one line is returned if text was just whitespace or empty
    if not lines and text.strip() == "":
        return [""]
    elif not lines: # If text was non-empty but resulted in no lines somehow (e.g., error)
        return [text] # Return original text as a single line as fallback
    return lines
