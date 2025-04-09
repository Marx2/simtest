# aisim/src/core/panel.py
import pygame
import os
# from __future__ import annotations # Not strictly necessary if using string hints
from typing import Optional
from aisim.src.core.configuration import config_manager
from aisim.src.core.mood import get_mood_description
# Forward declare Sim type hint to avoid circular import issues
if False: # This block is never executed but helps type checkers
    from aisim.src.core.sim import Sim

# Font will be initialized lazily inside draw_bubble
PANEL_FONT = None
PANEL_EMOJI_FONT = None
PANEL_FONT_PATH = config_manager.get_entry('sim.panel_font_dir')
PANEL_EMOJI_FONT_PATH = config_manager.get_entry('sim.panel_font_emoji_dir') # Added emoji font path

# Get colors from config with defaults
TEXT_COLOR = tuple(config_manager.get_entry('ui.text_color', [240, 240, 240]))
BG_COLOR = tuple(config_manager.get_entry('ui.bg_color', [50, 50, 50, 180]))
HIGH_ROMANCE_THRESHOLD = config_manager.get_entry('simulation.high_romance_threshold', 0.7)
RED_COLOR = (255, 0, 0)
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

def draw_bubble(screen, text, position, font=None, text_color=TEXT_COLOR, bg_color=BG_COLOR, max_width=150, padding=10, offset_y=-30, sim1: Optional['Sim'] = None, sim2: Optional['Sim'] = None):
    """Draws a text bubble above a given position."""
    global PANEL_FONT, PANEL_EMOJI_FONT # Declare intent to modify the global variables

    # Lazy font initialization
    if font is None:
        # Initialize regular font
        if PANEL_FONT is None:
            try:
                if not pygame.font.get_init(): pygame.font.init()
                if PANEL_FONT_PATH and os.path.exists(PANEL_FONT_PATH):
                    PANEL_FONT = pygame.font.Font(PANEL_FONT_PATH, 14)  # Regular text at 14px
                    print(f"Loaded panel font: {PANEL_FONT_PATH}")
                else:
                    PANEL_FONT = pygame.font.SysFont(None, 14) # Fallback
                    print(f"Panel font path not found or invalid, using SysFont: {PANEL_FONT_PATH}")
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
        # Calculate the Y position for the baseline/center of this line's vertical space
        line_center_y = current_y + line_data['height'] // 2

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

def draw_panel_details(screen, detailed_sim, panel_scroll_offset, sims_dict, ui_font, log_font, SCREEN_WIDTH, SCREEN_HEIGHT):
    """Draws the detailed information panel for a selected Sim."""
    panel_width = 450
    panel_height = 450 # Increased height
    panel_x = (SCREEN_WIDTH - panel_width) // 2
    panel_y = (SCREEN_HEIGHT - panel_height) // 2
    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    panel_bg_color = (40, 40, 60, 230) # Semi-transparent dark blue/purple
    panel_border_color = (150, 150, 180)
    text_color = (230, 230, 230)
    padding = 15
    line_spacing = 5 # Extra space between lines/sections
    scrollbar_width = 10
    scrollbar_handle_color = (150, 150, 180)

    # --- Calculate Content Height (Estimate before drawing) ---
    # This is an estimation pass. We'll refine drawing positions later.
    estimated_content_height = padding # Start with top padding
    portrait_size = 64 if detailed_sim.get_portrait() else 0
    info_font = ui_font
    line_h_info = info_font.get_linesize()
    line_h_log = log_font.get_linesize()

    # Height for basic info block (consider portrait height)
    basic_info_height = 6 * line_h_info # Name, ID, Sex, Mood, Position, Tile
    estimated_content_height += max(portrait_size, basic_info_height) + line_spacing

    # Height for Personality
    estimated_content_height += line_h_log # Title
    pers_lines = wrap_text(detailed_sim.personality_description, log_font, panel_width - 2 * padding - scrollbar_width)
    estimated_content_height += len(pers_lines) * line_h_log + line_spacing

    # Height for Romance Section
    estimated_content_height += line_h_log # Title
    if detailed_sim.relationships:
         estimated_content_height += len(detailed_sim.relationships) * line_h_log
    else:
         estimated_content_height += line_h_log # "None" line
    # estimated_content_height += line_spacing # Space before next section (if any)
    estimated_content_height += line_spacing # Space before conv history

    # Height for Conversation History
    estimated_content_height += line_h_log # Title
    content_width_for_estimation = panel_width - 2 * padding - scrollbar_width # Width for wrapping text
    if detailed_sim.conversation_history:
        for entry in detailed_sim.conversation_history:
            role = entry.get('role', '??')
            content = entry.get('content', '')
            entry_text = f"{role.capitalize()}: {content}"
            wrapped_lines = wrap_text(entry_text, log_font, content_width_for_estimation)
            estimated_content_height += len(wrapped_lines) * line_h_log
    else:
        estimated_content_height += line_h_log # "None" line

    estimated_content_height += padding # Bottom padding
    estimated_content_height += padding # Bottom padding

    # --- Clamp Scroll Offset ---
    panel_visible_height = panel_height - 2 * padding
    max_scroll = max(0, estimated_content_height - panel_visible_height) # Max scroll is content height minus visible area
    # Note: panel_scroll_offset is passed in, but we still need to clamp it based on calculated max_scroll
    panel_scroll_offset = max(0, min(panel_scroll_offset, max_scroll))

    # --- Draw Panel Background and Border ---
    pygame.draw.rect(screen, panel_bg_color, panel_rect, border_radius=10)
    pygame.draw.rect(screen, panel_border_color, panel_rect, width=2, border_radius=10)

    # --- Set Clipping Region for Content ---
    # Slightly smaller than panel_rect to avoid drawing over the border
    content_clip_rect = panel_rect.inflate(-padding // 2, -padding // 2)
    screen.set_clip(content_clip_rect)

    # --- Draw Content (with scroll offset) ---
    current_y = panel_y + padding - panel_scroll_offset # Apply scroll offset

    # Portrait
    portrait = detailed_sim.get_portrait()
    if portrait:
        # Scale portrait up slightly for visibility
        portrait_size = 64
        scaled_portrait = pygame.transform.scale(portrait, (portrait_size, portrait_size))
        portrait_x = panel_x + padding
        # Draw portrait considering scroll offset
        screen.blit(scaled_portrait, (portrait_x, current_y))
        text_start_x = portrait_x + portrait_size + padding
    else:
        portrait_size = 0 # No portrait height offset needed
        text_start_x = panel_x + padding

    # Store the Y position after the portrait to align the start of the text block
    text_block_start_y = current_y

    # Basic Info (Name, ID, Sex, Mood) - next to portrait
    info_font = ui_font # Use slightly larger font
    line_h = line_h_info # Use precalculated line height

    name_text = f"Name: {detailed_sim.full_name}"
    name_surf = info_font.render(name_text, True, text_color)
    screen.blit(name_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    id_text = f"ID: {detailed_sim.sim_id[:8]}..." # Shorten ID
    id_surf = info_font.render(id_text, True, text_color)
    screen.blit(id_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    sex_text = f"Sex: {detailed_sim.sex}"
    sex_surf = info_font.render(sex_text, True, text_color)
    screen.blit(sex_surf, (text_start_x, text_block_start_y)) # Use text_block_start_y
    text_block_start_y += line_h # Increment text_block_start_y

    mood_str = get_mood_description(detailed_sim.mood)
    mood_text = f"Mood: {mood_str} ({detailed_sim.mood:.2f})"
    mood_surf = info_font.render(mood_text, True, text_color)
    screen.blit(mood_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h # Increment Y after drawing mood

    # Add Position (x, y)
    pos_text = f"Position: ({detailed_sim.x:.1f}, {detailed_sim.y:.1f})"
    pos_surf = info_font.render(pos_text, True, text_color)
    screen.blit(pos_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    # Add Current Tile
    tile_text = f"Tile: {detailed_sim.current_tile}" # Assumes current_tile is a tuple (col, row) or None
    tile_surf = info_font.render(tile_text, True, text_color)
    screen.blit(tile_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    # Ensure text doesn't overlap portrait if portrait is tall
    # current_y now represents the bottom edge after the portrait OR the text block, whichever is lower
    current_y = max(panel_y + padding - panel_scroll_offset + portrait_size, text_block_start_y) + line_spacing

    # Personality Description
    current_y += line_spacing # Add space before section
    pers_title_surf = log_font.render("Personality:", True, text_color)
    screen.blit(pers_title_surf, (panel_x + padding, current_y))
    current_y += line_h_log

    # Use the pre-wrapped lines from height calculation
    # pers_lines = wrap_text(detailed_sim.personality_description, log_font, content_width) # Already done
    for line in pers_lines:
        # Simple check: Don't draw if the line *starts* way below the panel
        if current_y > panel_y + panel_height:
             break
        # More precise check: Don't draw if the line *ends* way above the panel
        if current_y + line_h_log < panel_y:
            current_y += line_h_log # Still need to advance Y even if not drawing
            continue

        line_surf = log_font.render(line, True, text_color)
        screen.blit(line_surf, (panel_x + padding, current_y))
        current_y += line_h_log

    # Romance Section
    current_y += line_spacing # Add space before section
    rom_title_surf = log_font.render("Romance:", True, text_color)
    screen.blit(rom_title_surf, (panel_x + padding, current_y))
    current_y += line_h_log

    if detailed_sim.relationships:
        for other_id, values in sorted(detailed_sim.relationships.items()): # Sort for consistent order
            # Simple visibility checks
            if current_y > panel_y + panel_height: break
            if current_y + line_h_log < panel_y:
                current_y += line_h_log
                continue

            other_sim = sims_dict.get(other_id)
            other_name = other_sim.full_name if other_sim else f"Unknown ({other_id[:6]})"
            friendship = values.get('friendship', 0.0)
            romance = values.get('romance', 0.0)

            # Determine color based on romance level
            current_text_color = RED_COLOR if romance >= HIGH_ROMANCE_THRESHOLD else text_color

            # Format text
            rom_text = f"- {other_name}: F={friendship:.1f}, R={romance:.1f}"
            rom_surf = log_font.render(rom_text, True, current_text_color) # Use determined color
            screen.blit(rom_surf, (panel_x + padding, current_y))
            current_y += line_h_log
    else:
         # Simple visibility checks
         if not (current_y > panel_y + panel_height or current_y + line_h_log < panel_y):
            no_rom_surf = log_font.render("- None", True, text_color)
            screen.blit(no_rom_surf, (panel_x + padding, current_y))
         current_y += line_h_log # Still advance Y

    # Conversation History
    current_y += line_spacing # Add space before section
    conv_title_surf = log_font.render("Conversation History:", True, text_color)
    screen.blit(conv_title_surf, (panel_x + padding, current_y))
    current_y += line_h_log

    content_width = panel_width - 2 * padding - scrollbar_width # Available width for text
    if detailed_sim.conversation_history:
        for entry in detailed_sim.conversation_history:
            role = entry.get('role', '??')
            content = entry.get('content', '')
            entry_text = f"{role.capitalize()}: {content}"
            # Wrap conversation entry text if needed
            wrapped_lines = wrap_text(entry_text, log_font, content_width)
            for line in wrapped_lines:
                # Simple visibility checks
                if current_y > panel_y + panel_height: break
                if current_y + line_h_log < panel_y:
                    current_y += line_h_log
                    continue

                line_surf = log_font.render(line, True, text_color)
                screen.blit(line_surf, (panel_x + padding, current_y))
                current_y += line_h_log
            if current_y > panel_y + panel_height: break # Break outer loop too if needed
    else:
        # Simple visibility checks
        if not (current_y > panel_y + panel_height or current_y + line_h_log < panel_y):
            no_conv_surf = log_font.render("- None", True, text_color)
            screen.blit(no_conv_surf, (panel_x + padding, current_y))
        current_y += line_h_log # Still advance Y

    # --- Remove Clipping ---
    screen.set_clip(None)

    # --- Draw Scrollbar ---
    if max_scroll > 0: # Only draw if scrolling is possible
        # Scrollbar Track
        track_rect = pygame.Rect(panel_x + panel_width - scrollbar_width - padding // 2, panel_y + padding // 2, scrollbar_width, panel_height - padding)
        # pygame.draw.rect(screen, (30, 30, 40), track_rect, border_radius=5) # Optional track background

        # Scrollbar Handle
        handle_height = max(15, panel_visible_height * (panel_visible_height / estimated_content_height)) # Min height 15px
        handle_y_ratio = panel_scroll_offset / max_scroll if max_scroll > 0 else 0 # Avoid division by zero
        handle_y = track_rect.y + handle_y_ratio * (track_rect.height - handle_height)
        handle_rect = pygame.Rect(track_rect.x, handle_y, scrollbar_width, handle_height)
        pygame.draw.rect(screen, scrollbar_handle_color, handle_rect, border_radius=5)

    # Return the clamped scroll offset in case it was adjusted
    return panel_scroll_offset

