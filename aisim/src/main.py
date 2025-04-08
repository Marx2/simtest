import pygame
import os
import sys
print(f"Current working directory: {os.getcwd()}")
print(f"Python sys.path: {sys.path}")
import sys
import random
import uuid
import json
import textwrap # Added for panel text wrapping
# Keep os import if needed elsewhere, otherwise remove if only used for CONFIG_PATH
import os
from aisim.src.core.configuration import config_manager # Import the centralized config manager
from aisim.src.core.sim import Sim # Import Sim class (constants are now internal or loaded from config)
from aisim.src.core.weather import Weather
from aisim.src.core.city import City, TILE_SIZE # Import TILE_SIZE constant
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.logger import Logger
from aisim.src.core.interaction import THOUGHT_DURATION # Added import
# Constants (Defaults, will be overridden by config)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
WINDOW_TITLE = "AI Sims Simulation"
FPS = 60 # Keep default FPS if needed before config load, otherwise remove

# --- Helper Functions ---
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
        if paragraph != paragraphs[-1]: # Don't add extra space after the last paragraph
             lines.append("") # Add empty string to represent paragraph break
    # Ensure at least one line is returned if text was just whitespace
    if not lines and text.strip() == "":
        return [""]
    elif not lines: # If text was non-empty but resulted in no lines somehow
        return [text] # Return original text as a single line
    return lines


def get_mood_description(mood_value):
    """Converts mood float (-1 to 1) to a descriptive string."""
    if mood_value < -0.7: return "Very Sad"
    if mood_value < -0.3: return "Sad"
    if mood_value < 0.3: return "Neutral"
    if mood_value < 0.7: return "Happy"
    return "Very Happy"

# --- End Helper Functions ---
def main():
    # Get config values using the centralized manager
    fps = config_manager.get_entry('simulation.fps', 60)
    initial_sims = config_manager.get_entry('simulation.initial_sims', 10)
    enable_talking = config_manager.get_entry('simulation.enable_talking', False)
    bubble_display_time = config_manager.get_entry('simulation.bubble_display_time_seconds', 5.0)
    sim_creation_config = config_manager.get_entry('sim', {}) # Pass the whole 'sim' section if Sim expects it
    weather_config = config_manager.get_entry('weather', {}) # Get weather specific config
    movement_direction_change_frequency = config_manager.get_entry('movement.direction_change_frequency', 5.0)
    pygame.init() # Pygame init needs to happen before font loading in Sim
    # Create AI Client
    ollama_client = OllamaClient() # Reads its own config section
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()
    ui_font = pygame.font.SysFont(None, 24) # Font for UI text
    log_font = pygame.font.SysFont(None, 18) # Smaller font for event log
    # Create Simulation Components
    weather = Weather(weather_config, SCREEN_WIDTH, SCREEN_HEIGHT) # Pass weather config section
    city = City(SCREEN_WIDTH, SCREEN_HEIGHT) # City will use config_manager internally now
    # enable_talking is retrieved above

    # Store sims in a dictionary for easy lookup by ID
    sims_dict = {}
    for _ in range(initial_sims): # Use retrieved initial_sims
        new_sim = Sim(
            sim_id=str(uuid.uuid4()),  # Generate unique ID
            x=max(0, min(random.randint(0, SCREEN_WIDTH), SCREEN_WIDTH - TILE_SIZE -1)),
            y=max(0, min(random.randint(0, SCREEN_HEIGHT), SCREEN_HEIGHT - TILE_SIZE -1)),
            ollama_client=ollama_client, # Pass the client instance
            enable_talking=enable_talking, # Use retrieved enable_talking
            sim_config=sim_creation_config, # Pass the retrieved sim config dictionary
            bubble_display_time=bubble_display_time # Pass retrieved bubble_display_time
        )
        sims_dict[new_sim.sim_id] = new_sim

    # Add sims to city
    city.sims = list(sims_dict.values()) # City might still expect a list
    # Allow sims to talk after display is initialized
    logger = Logger() # Create logger instance

    running = True
    paused = False
    time_scale = 1.0 # Normal speed
    time_scales = {pygame.K_1: 1.0, pygame.K_2: 2.0, pygame.K_4: 4.0, pygame.K_0: 10.0} # Add 0 for 10x

    current_sim_time = 0.0 # Track total simulation time passed
    selected_sim = None # Track the currently selected Sim (for bottom log)
    detailed_sim = None # Track the Sim for the details panel
    last_click_time = 0
    last_clicked_sim_id = None
    DOUBLE_CLICK_TIME = 500 # Milliseconds
    panel_scroll_offset = 0 # Initialize scroll offset
    while running:
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p: # Toggle pause
                    paused = not paused
                elif event.key in time_scales: # Change speed
                     time_scale = time_scales[event.key]
                     print(f"Time scale set to: {time_scale}x")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    mouse_x, mouse_y = event.pos
                    current_time_ms = pygame.time.get_ticks()
                    clicked_on_sim_object = None
                    min_dist_sq = float('inf')

                    # Find the closest sim to the click
                    for sim in sims_dict.values():
                        # Use sprite dimensions for click detection if available
                        # Use sim's own sprite dimensions now loaded from config
                        sim_rect = pygame.Rect(sim.x - sim.sprite_width // 2, sim.y - sim.sprite_height // 2, sim.sprite_width, sim.sprite_height)
                        if sim_rect.collidepoint(mouse_x, mouse_y):
                             # Calculate distance for tie-breaking if multiple sprites overlap
                             dist_sq = (sim.x - mouse_x)**2 + (sim.y - mouse_y)**2
                             if dist_sq < min_dist_sq:
                                 min_dist_sq = dist_sq
                                 clicked_on_sim_object = sim
                             # print(f"Clicked on Sim {sim.sim_id} rect") # Debug print

                    # --- Handle Click Logic ---
                    if clicked_on_sim_object:
                        # --- Double Click Check ---
                        time_since_last_click = current_time_ms - last_click_time
                        if clicked_on_sim_object.sim_id == last_clicked_sim_id and time_since_last_click < DOUBLE_CLICK_TIME:
                            print(f"Double-clicked Sim: {clicked_on_sim_object.sim_id}")
                            detailed_sim = clicked_on_sim_object # Show details panel
                            selected_sim = clicked_on_sim_object # Also select for log view
                            panel_scroll_offset = 0 # Reset scroll on new panel
                            # Reset double-click tracking
                            last_click_time = 0
                            last_clicked_sim_id = None
                        else:
                            # --- Single Click on a Sim ---
                            print(f"Single-clicked Sim: {clicked_on_sim_object.sim_id}")
                            selected_sim = clicked_on_sim_object # Select for log view
                            detailed_sim = None # Close details panel on single click
                            # Update tracking for potential double-click
                            last_click_time = current_time_ms
                            last_clicked_sim_id = clicked_on_sim_object.sim_id
                    else:
                        # --- Clicked on Empty Space ---
                        print("Clicked empty space")
                        selected_sim = None # Deselect for log view
                        detailed_sim = None # Close details panel
                        last_click_time = 0 # Reset double-click tracking
                        last_clicked_sim_id = None
            elif event.type == pygame.MOUSEWHEEL:
                 # Handle panel scrolling only if the panel is open
                 if detailed_sim:
                     mouse_pos = pygame.mouse.get_pos()
                     # Define panel_rect here or ensure it's accessible
                     # Re-calculate panel_rect based on current state if needed
                     panel_width = 350
                     panel_height = 450
                     panel_x = (SCREEN_WIDTH - panel_width) // 2
                     panel_y = (SCREEN_HEIGHT - panel_height) // 2
                     panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)

                     if panel_rect.collidepoint(mouse_pos):
                         # Adjust scroll offset based on wheel direction
                         scroll_speed = 30 # Pixels per wheel tick
                         panel_scroll_offset -= event.y * scroll_speed
                         # Clamping will happen during drawing after content height is known


        # Calculate delta time (time since last frame)
        raw_dt = clock.tick(fps) / 1000.0 # Get raw delta time

        # Apply time controls
        if paused:
            dt = 0.0 # No time passes if paused
        else:
            dt = raw_dt * time_scale # Apply speed multiplier
        # Game logic updates
        # Only update simulation logic if time is passing
        if dt > 0: # Only update simulation state if not paused
            current_sim_time += dt # Increment simulation time
            all_sims_list = list(sims_dict.values()) # Get list for passing to update
            for sim in all_sims_list:
                # Pass city.TILE_SIZE to sim.update for arrival checks
                sim.sim_update(dt, city, weather.current_state, all_sims_list, logger, current_sim_time, TILE_SIZE, movement_direction_change_frequency) # Use retrieved frequency
                # Interaction check is now called within sim.update, remove explicit call here
            #   sim._check_interactions(sims, logger, current_sim_time) # Removed redundant call
            weather.weather_update(dt)
            city.city_update(dt) # Update city state (currently does nothing)

            # --- Poll for Ollama Results (Thoughts & Conversation Responses) ---
            while True:
                result = ollama_client.check_for_thought_results()
                if result is None:
                    break # No more results in the queue for now

                sim_id, response_text = result
                target_sim = sims_dict.get(sim_id)

                if target_sim and response_text:
                    # Pass the response to the interaction module's handler method
                    from aisim.src.core import interaction
                    interaction.handle_ollama_response(target_sim, response_text, current_sim_time, all_sims_list, city)
                elif not target_sim:
                     print(f"Warning: Received Ollama result for unknown Sim ID: {sim_id}")
                # The old direct setting of current_thought/thought_timer is now handled within handle_ollama_response

        # --- Drawing --- (Always draw, even when paused)
        screen.fill(weather.get_current_color()) # Use weather color for background

        # Draw city grid first
        city.draw(screen)

        # Draw simulation elements (Sims)
        for sim in sims_dict.values(): # Iterate over dict values
            sim.draw(screen, dt, all_sims_list)
        weather.draw_effects(screen) # Draw weather effects over sims

        # Draw UI Text (Pause/Speed)
        if paused:
            status_text = "PAUSED"
        else:
            status_text = f"Speed: {time_scale}x"
        status_surface = ui_font.render(status_text, True, (255, 255, 255))
        screen.blit(status_surface, (10, 10)) # Top-left corner

        # Draw Weather Status (Top-right)
        weather_text = f"Weather: {weather.current_state}"
        weather_surface = ui_font.render(weather_text, True, (255, 255, 255))
        weather_rect = weather_surface.get_rect(topright=(SCREEN_WIDTH - 10, 10))
        screen.blit(weather_surface, weather_rect)

        # Draw Weather Countdown Timer (Below Weather Status)
        # Weather object now uses config_manager internally or was initialized with its config
        # Assuming Weather class is refactored or handles its config access internally
        if config_manager.get_entry('weather.enable_weather_changes', False): # Check directly via config_manager
            remaining_time = max(0, weather.change_frequency - weather.time_since_last_change)
            countdown_text = f"Next change in: {int(remaining_time)}s" # Cast to int
            countdown_surface = ui_font.render(countdown_text, True, (220, 220, 220)) # Slightly dimmer white
            countdown_rect = countdown_surface.get_rect(topright=(SCREEN_WIDTH - 10, weather_rect.bottom + 5)) # Position below weather text
            screen.blit(countdown_surface, countdown_rect)


        # Draw Event Log for selected Sim
        if selected_sim:
            log_y = SCREEN_HEIGHT - 15 # Start near bottom
            log_x = 10
            # Display Sim ID
            id_text = f"Selected: {selected_sim.full_name} (Mood: {selected_sim.mood:.2f})"
            id_surface = log_font.render(id_text, True, (255, 255, 255))
            screen.blit(id_surface, (log_x, log_y - (len(selected_sim.memory[-5:]) + 1) * 15 )) # Position above logs

        # Display last 5 memory entries
        if selected_sim and selected_sim.memory:
            for entry in selected_sim.memory[-5:]: # Get last 5 entries
                entry_text = ""
            entry_text = ""
            if entry['type'] == 'thought':
                    entry_text = f"[Thought] {entry['content'][:60]}..." # Truncate long thoughts
            elif entry['type'] == 'interaction':
                    entry_text = f"[Interact] w/ {entry['with_sim_id'][:6]} (F_chg: {entry['friendship_change']:.2f})"

            log_surface = log_font.render(entry_text, True, (200, 200, 200))
            screen.blit(log_surface, (log_x, log_y))
            log_y -= 15 # Move up for next line


        # --- Draw Sim Details Panel ---
        if detailed_sim:
            panel_width = 350
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
            scrollbar_color = (100, 100, 120)
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

            # Height for Relationships
            estimated_content_height += line_h_log # Title
            if detailed_sim.relationships:
                 estimated_content_height += len(detailed_sim.relationships) * line_h_log
            else:
                 estimated_content_height += line_h_log # "None" line
            estimated_content_height += padding # Bottom padding

            # --- Clamp Scroll Offset ---
            panel_visible_height = panel_height - 2 * padding
            max_scroll = max(0, estimated_content_height - panel_visible_height) # Max scroll is content height minus visible area
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
            content_width = panel_width - 2 * padding - scrollbar_width # Adjust width for scrollbar

            # Portrait
            portrait = detailed_sim.get_portrait()
            if portrait:
                # Scale portrait up slightly for visibility
                portrait_size = 64
                scaled_portrait = pygame.transform.scale(portrait, (portrait_size, portrait_size))
                portrait_x = panel_x + padding
                screen.blit(scaled_portrait, (portrait_x, current_y))
                # Draw portrait considering scroll offset
                screen.blit(scaled_portrait, (portrait_x, current_y))
                text_start_x = portrait_x + portrait_size + padding
                # text_width = content_width - portrait_size - padding # Already adjusted content_width
            else:
                portrait_size = 0 # No portrait height offset needed
                text_start_x = panel_x + padding
                # text_width = content_width # Already adjusted content_width

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

            # Relationships
            current_y += line_spacing # Add space before section
            rel_title_surf = log_font.render("Relationships:", True, text_color)
            screen.blit(rel_title_surf, (panel_x + padding, current_y))
            current_y += line_h_log

            if detailed_sim.relationships:
                for other_id, values in sorted(detailed_sim.relationships.items()): # Sort for consistent order
                    # Simple visibility checks like above
                    if current_y > panel_y + panel_height: break
                    if current_y + line_h_log < panel_y:
                        current_y += line_h_log
                        continue

                    other_sim = sims_dict.get(other_id)
                    other_name = other_sim.full_name if other_sim else f"Unknown ({other_id[:6]})"
                    friendship = values.get('friendship', 0.0)
                    romance = values.get('romance', 0.0)
                    rel_text = f"- {other_name}: F={friendship:.1f}"
                    if 'romance' in values:
                        rel_text += f", R={romance:.1f}"
                    rel_surf = log_font.render(rel_text, True, text_color)
                    screen.blit(rel_surf, (panel_x + padding, current_y))
                    current_y += line_h_log
            else:
                 # Simple visibility checks like above
                 if not (current_y > panel_y + panel_height or current_y + line_h_log < panel_y):
                    no_rel_surf = log_font.render("- None", True, text_color)
                    screen.blit(no_rel_surf, (panel_x + padding, current_y))
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
                handle_y_ratio = panel_scroll_offset / max_scroll
                handle_y = track_rect.y + handle_y_ratio * (track_rect.height - handle_height)
                handle_rect = pygame.Rect(track_rect.x, handle_y, scrollbar_width, handle_height)
                pygame.draw.rect(screen, scrollbar_handle_color, handle_rect, border_radius=5)


        pygame.display.flip() # Update the full display Surface to the screen
        for sim in sims_dict.values(): # Iterate over dict values
            sim.can_talk = True # Reset talking flag (consider if this is still needed)


    # --- End of main loop ---
    logger.close() # Close log files cleanly
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()