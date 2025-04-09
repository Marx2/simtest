import pygame
import os
from typing import Optional
# from aisim.src.core.sim import Sim
from aisim.src.core.configuration import config_manager

# Font will be initialized lazily inside draw_bubble
# global PANEL_FONT, PANEL_EMOJI_FONT # Declare intent to modify the global variables
PANEL_FONT = None
PANEL_EMOJI_FONT = None
PANEL_FONT_PATH = config_manager.get_entry('sim.panel_font_dir')
PANEL_EMOJI_FONT_PATH = config_manager.get_entry('sim.panel_font_emoji_dir') # Added emoji font path
HIGH_ROMANCE_THRESHOLD = config_manager.get_entry('simulation.high_romance_threshold', 0.7)

# Get colors from config with defaults
TEXT_COLOR = tuple(config_manager.get_entry('ui.text_color', [240, 240, 240]))
BG_COLOR = tuple(config_manager.get_entry('ui.bg_color', [50, 50, 50, 180]))
RED_COLOR = (255, 0, 0)

def initialize_fonts(font=None):
    global PANEL_FONT, PANEL_EMOJI_FONT
    if font is None:
        # Initialize regular font
        if PANEL_FONT is None:
            try:
                if not pygame.font.get_init(): pygame.font.init()
                if PANEL_FONT_PATH and os.path.exists(PANEL_FONT_PATH):
                    try:
                        PANEL_FONT = pygame.font.Font(PANEL_FONT_PATH, 14)  # Regular text at 14px
                        print(f"Loaded panel font: {PANEL_FONT_PATH}")
                    except pygame.error as e:
                        print(f"Error loading font {PANEL_FONT_PATH}: {e}")
                        PANEL_FONT = pygame.font.SysFont(None, 14) # Fallback
                        print("Using fallback system font.")
                else:
                    PANEL_FONT = pygame.font.SysFont(None, 14) # Fallback
                    print(f"Panel font path not found or invalid: {PANEL_FONT_PATH}. Using fallback system font.")
            except pygame.error as e:
                 print(f"Error initializing panel font '{PANEL_FONT_PATH}': {e}")
                 return # Cannot draw without a font

        # Initialize emoji font
        if PANEL_EMOJI_FONT is None:
            emoji_font_size = 8 # Keep the smaller size for now
            loaded_emoji_font = False
            try:
                if not pygame.font.get_init(): pygame.font.init()

                # Try loading configured font path first
                if PANEL_EMOJI_FONT_PATH and os.path.exists(PANEL_EMOJI_FONT_PATH):
                    try:
                        PANEL_EMOJI_FONT = pygame.font.Font(PANEL_EMOJI_FONT_PATH, emoji_font_size)
                        print(f"Loaded configured emoji font: {PANEL_EMOJI_FONT_PATH} (size {emoji_font_size})")
                        loaded_emoji_font = True
                    except pygame.error as e:
                        print(f"Error loading configured emoji font '{PANEL_EMOJI_FONT_PATH}': {e}. Trying fallback.")

                # Try NotoEmoji-Regular.ttf as a fallback if configured failed or wasn't set
                if not loaded_emoji_font:
                    # Construct path relative to this file or use a known relative path
                    # Assuming panel.py is in aisim/src/core/
                    noto_path = os.path.join(os.path.dirname(__file__), '..', 'graphics', 'fonts', 'NotoEmoji-Regular.ttf')
                    if os.path.exists(noto_path):
                         try:
                              PANEL_EMOJI_FONT = pygame.font.Font(noto_path, emoji_font_size)
                              print(f"Loaded fallback NotoEmoji font: {noto_path} (size {emoji_font_size})")
                              loaded_emoji_font = True
                         except pygame.error as e:
                              print(f"Error loading fallback NotoEmoji font '{noto_path}': {e}. Using main font.")
                    else:
                        print(f"Fallback NotoEmoji font not found at '{noto_path}'.")

                # Final fallback: use the main panel font
                if not loaded_emoji_font:
                    print("Failed to load any specific emoji font. Using main panel font as final fallback.")
                    PANEL_EMOJI_FONT = PANEL_FONT

            except Exception as e: # Catch potential font init errors or other issues
                 print(f"General error during emoji font initialization: {e}")
                 PANEL_EMOJI_FONT = PANEL_FONT # Ensure fallback on any error

        # Use the global default if no specific font passed in the function call
        font = PANEL_FONT # Main font reference
        return font

def draw_bubble(screen, text, position, font=None, text_color=TEXT_COLOR, bg_color=BG_COLOR, max_width=150, padding=10, offset_y=-30, sim1: Optional['Sim'] = None, sim2: Optional['Sim'] = None):
    """Draws a text bubble above a given position."""

    font = initialize_fonts(font) # Initialize fonts if not already done
    if not text or not font: # Also check if font initialization failed
        return

    # Determine text color based on romance level if sims are provided
    final_text_color = text_color # Start with default
    if sim1 and sim2:
        # Check relationship from sim1's perspective (the owner of the bubble)
        relation_to_sim2 = sim1.relationships.get(sim2.sim_id)
        if relation_to_sim2 and relation_to_sim2.get("romance", 0.0) >= HIGH_ROMANCE_THRESHOLD:
            final_text_color = RED_COLOR # Red color for high romance
            # print(f"Debug: High romance detected between {sim1.first_name} and {sim2.first_name}. Using RED.") # Optional debug

    lines = wrap_text_compact(text, font, max_width)
    if not lines: # Don't draw if wrapping results in no lines
        return

    # --- Measurement Phase ---
    if not PANEL_FONT or not PANEL_EMOJI_FONT:
        print("Error: Fonts not initialized, cannot draw bubble.")
        return

    measured_lines = []
    max_measured_width = 0
    # Target height for scaling emojis (use text font line size)
    target_emoji_height = PANEL_FONT.get_linesize()
    base_line_height = target_emoji_height # Use text font linesize for empty/text lines
    total_content_height = 0

    for line_text in lines:
        if not line_text:
            # Use base font line height for empty lines
            measured_lines.append({'text': '', 'width': 0, 'height': base_line_height, 'segments': []})
            total_content_height += base_line_height
            continue

        segments = []
        current_segment_text = ""
        current_is_emoji = None
        line_width = 0
        line_max_actual_height = 0 # Track max *rendered* height within this line

        for char in line_text:
            char_is_emoji = is_emoji(char)
            # Determine font for the *current* character being processed
            char_font = PANEL_EMOJI_FONT if char_is_emoji else PANEL_FONT

            if not char_font: # Safety check if a font failed to load
                print(f"Warning: Font not available for character '{char}'")
                continue

            if current_is_emoji is None: # First char
                current_is_emoji = char_is_emoji
                current_segment_text += char
            elif char_is_emoji == current_is_emoji: # Continue segment
                current_segment_text += char
            else: # End previous segment
                prev_font = PANEL_EMOJI_FONT if current_is_emoji else PANEL_FONT
                if current_segment_text and prev_font: # Ensure segment and font are valid
                    try:
                        # Render to measure actual dimensions
                        temp_surf = prev_font.render(current_segment_text, True, final_text_color) # Use final_text_color
                        original_width = temp_surf.get_width()
                        original_height = temp_surf.get_height()

                        # --- Scale Emoji Surface if needed ---
                        scaled_width = original_width
                        scaled_height = original_height
                        is_emoji_segment = current_is_emoji # Check type of segment being finalized

                        if is_emoji_segment and original_height > target_emoji_height and target_emoji_height > 0:
                            scale_factor = target_emoji_height / original_height
                            scaled_width = int(original_width * scale_factor)
                            scaled_height = target_emoji_height # Set to target
                            # print(f"    Scaling emoji segment '{current_segment_text}' from H:{original_height} to H:{scaled_height} (Factor: {scale_factor:.2f})")
                            # Note: Scaling done during render phase to save memory unless surfaces stored

                        # DEBUG PRINT: Print measured segment dimensions (before potential scaling)
                        # print(f"  [Measure] Segment: '{current_segment_text}', Original W: {original_width}, H: {original_height} -> Used W: {scaled_width}, H: {scaled_height}")

                        # Store dimensions (potentially scaled) for layout
                        segments.append({
                            'text': current_segment_text,
                            'font': prev_font,
                            'is_emoji': is_emoji_segment, # Store if it's an emoji segment
                            'original_width': original_width, # Store original for potential re-render
                            'original_height': original_height,
                            'width': scaled_width, # Use scaled width for layout
                            'height': scaled_height # Use scaled height for layout
                        })
                        line_width += scaled_width # Add scaled width to line width
                        line_max_actual_height = max(line_max_actual_height, scaled_height) # Use scaled height for max line height

                    except pygame.error as e:
                        print(f"Error measuring segment '{current_segment_text}': {e}")

                # Start new segment
                current_segment_text = char
                current_is_emoji = char_is_emoji # Update type for the new segment

        # Add the last segment
        if current_segment_text:
            last_font = PANEL_EMOJI_FONT if current_is_emoji else PANEL_FONT
            if last_font:
                try:
                    # Render to measure actual dimensions
                    temp_surf = last_font.render(current_segment_text, True, final_text_color) # Use final_text_color
                    original_width = temp_surf.get_width()
                    original_height = temp_surf.get_height()

                    # --- Scale Emoji Surface if needed ---
                    scaled_width = original_width
                    scaled_height = original_height
                    is_emoji_segment = current_is_emoji # Check type of the final segment

                    if is_emoji_segment and original_height > target_emoji_height and target_emoji_height > 0:
                        scale_factor = target_emoji_height / original_height
                        scaled_width = int(original_width * scale_factor)
                        scaled_height = target_emoji_height
                        # print(f"    Scaling final emoji segment '{current_segment_text}' from H:{original_height} to H:{scaled_height} (Factor: {scale_factor:.2f})")
                        # Scaling done during render phase

                    # DEBUG PRINT: Print measured final segment dimensions
                    # print(f"  [Measure] Final Segment: '{current_segment_text}', Original W: {original_width}, H: {original_height} -> Used W: {scaled_width}, H: {scaled_height}")

                    # Store dimensions (potentially scaled)
                    segments.append({
                        'text': current_segment_text,
                        'font': last_font,
                        'is_emoji': is_emoji_segment,
                        'original_width': original_width,
                        'original_height': original_height,
                        'width': scaled_width,
                        'height': scaled_height
                    })
                    line_width += scaled_width
                    line_max_actual_height = max(line_max_actual_height, scaled_height)

                except pygame.error as e:
                    print(f"Error measuring final segment '{current_segment_text}': {e}")

        # Ensure line has at least the base height if all segments rendered shorter
        line_effective_height = max(line_max_actual_height, base_line_height)

        # Store measured data for the line using effective height
        measured_lines.append({'text': line_text, 'width': line_width, 'height': line_effective_height, 'segments': segments})
        max_measured_width = max(max_measured_width, line_width)
        # Use the effective line height for total height calculation
        total_content_height += line_effective_height

    # --- Dimension Calculation Phase ---
    bubble_width = max_measured_width + (2 * padding)
    # Bubble height now based on sum of effective heights per line
    bubble_height = total_content_height + (2 * padding)
    # Bubble position calculation remains the same
    bubble_x = position[0] - bubble_width // 2
    bubble_y = position[1] + offset_y - bubble_height # Position above the target point
    screen_height = screen.get_height()
    if bubble_y < 0:
        bubble_y = 0

    # --- Render Phase ---
    # Surface creation uses updated bubble_height
    try:
        bubble_surface = pygame.Surface((int(bubble_width), int(bubble_height)), pygame.SRCALPHA) # Ensure integer dimensions
        bubble_surface.fill((0,0,0,0)) # Ensure transparent background
        pygame.draw.rect(bubble_surface, bg_color, bubble_surface.get_rect(), border_radius=5)
    except (pygame.error, ValueError) as e: # Catch potential errors like negative size
         print(f"Error creating bubble surface (width={bubble_width}, height={bubble_height}): {e}")
         return # Cannot proceed if surface creation fails

    current_y = padding
    for line_data in measured_lines:
        if not line_data['text']:
            current_y += line_data['height'] # Advance Y based on stored height (base_line_height)
            continue

        # Center the line horizontally based on its measured width
        start_x = (bubble_width - line_data['width']) // 2
        start_x = max(padding, start_x) # Ensure it respects padding

        current_x = start_x

        for segment in line_data['segments']:
            if not segment['font']:
                print(f"Warning: Font missing for segment '{segment['text']}'. Skipping render.")
                continue
            try:
                # Re-render the segment
                text_surface = segment['font'].render(segment['text'], True, final_text_color) # Use final_text_color

                # Scale if it's an emoji segment and scaling is needed
                blit_surface = text_surface
                final_width = segment['width'] # Use potentially scaled width stored from measurement
                final_height = segment['height'] # Use potentially scaled height

                if segment['is_emoji'] and segment['original_height'] > target_emoji_height and target_emoji_height > 0:
                     # Re-calculate scale factor and scale
                     # Avoids storing many surfaces, but recalculates scale
                     scale_factor = target_emoji_height / segment['original_height']
                     scaled_width_render = int(segment['original_width'] * scale_factor)
                     # Ensure final_width/height match calculation
                     final_width = scaled_width_render
                     final_height = target_emoji_height
                     try:
                         blit_surface = pygame.transform.smoothscale(text_surface, (final_width, final_height))
                     except (ValueError, pygame.error) as scale_err:
                         print(f"Error scaling surface for '{segment['text']}': {scale_err}")
                         blit_surface = text_surface # Fallback to unscaled if error
                         final_width = segment['original_width']
                         final_height = segment['original_height']


                # Calculate blit position using potentially scaled dimensions
                # Align bottom edge using the line's max height (line_data['height'])
                segment_rect = blit_surface.get_rect()
                segment_rect.left = int(current_x)
                segment_rect.bottom = int(current_y + line_data['height']) # Align bottom edge to line bottom

                bubble_surface.blit(blit_surface, segment_rect)
                current_x += final_width # Advance by the width actually used for blitting

            except pygame.error as e:
                 print(f"Error rendering segment '{segment['text']}' with font {segment['font']}: {e}")
            except AttributeError:
                 print(f"Error: Font object invalid for segment '{segment['text']}'. Font: {segment['font']}")

        current_y += line_data['height'] # Move to the next line position based on the current line's max height

    # Blit the complete bubble surface onto the main screen
    screen.blit(bubble_surface, (int(bubble_x), int(bubble_y))) # Ensure integer coordinates

def is_emoji(char):
    """Returns True if the character is likely an emoji."""
    # Using a simple codepoint range check is often sufficient and avoids
    # dependency on unicodedata if not available or needed elsewhere.
    # More comprehensive checks can be added if required.
    codepoint = ord(char)
    # Basic Multilingual Plane Supplement + Supplementary Multilingual Plane (covers many emojis)
    is_bmp_emoji = (
        (0x2600 <= codepoint <= 0x27BF) or  # Miscellaneous Symbols
        (0x1F300 <= codepoint <= 0x1F5FF) or  # Misc Symbols and Pictographs
        (0x1F600 <= codepoint <= 0x1F64F) or  # Emoticons
        (0x1F680 <= codepoint <= 0x1F6FF) or  # Transport and Map
        (0x1FA70 <= codepoint <= 0x1FAFF)     # Symbols and Pictographs Extended-A
    )
    # Check for specific characters if needed, e.g., variation selectors
    is_variation_selector = (0xFE00 <= codepoint <= 0xFE0F)

    # More complex checks involving specific ranges or properties can be added.
    # This basic check covers a wide range of common emojis.
    # Consider adding checks for ZWJ sequences or flags if needed later.
    return is_bmp_emoji # Ignoring variation selectors for basic check
def wrap_text(text, font, max_width):
    """Wraps text to fit within a specified width."""
    lines = []
    # Handle potential None or empty text
    if not text:
        return [""]
    # Split into paragraphs first to preserve line breaks
    paragraphs = text.split('\n')
    for paragraph in paragraphs:
        words = paragraph.split(' ')
        current_line = []
        while words:
            word = words.pop(0)
            test_line = ' '.join(current_line + [word])
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
                for char in word:
                    if font.size(temp_word + char)[0] <= max_width:
                        temp_word += char
                    else:
                        lines.append(temp_word)
                        temp_word = char
                if temp_word: # Add the remainder of the long word
                    lines.append(temp_word)
                current_line = [] # Reset current line after handling long word
        # Add the last line of the paragraph if it has content
        if current_line:
            lines.append(' '.join(current_line))
        # Add an empty line between paragraphs if the original text had one
    # Ensure at least one line is returned if text was just whitespace
    if not lines and text.strip() == "":
        return [""]
    elif not lines: # If text was non-empty but resulted in no lines somehow
        return [text] # Return original text as a single line
    return lines

def wrap_text_compact(text, font, max_width):
    """Helper function to wrap text to fit within a specified width."""
    words = text.split(' ')
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        # Use font.size to check width
        if font.size(test_line)[0] <= max_width:
            current_line.append(word)
        else:
            # Only add non-empty lines
            if current_line:
                lines.append(' '.join(current_line))
            # Handle very long words that exceed max_width alone
            if font.size(word)[0] > max_width:
                 # Simple split (might break words awkwardly) - consider more robust hyphenation
                 # For now, just add the long word as its own line
                 lines.append(word)
                 current_line = []
            else:
                 current_line = [word]


    if current_line:
        lines.append(' '.join(current_line))
    return lines
