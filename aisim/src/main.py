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
import os # Keep os import
from aisim.src.core.sim import Sim, SPRITE_WIDTH, SPRITE_HEIGHT # Import Sim and sprite constants
from aisim.src.core.weather import Weather
from aisim.src.core.city import City, TILE_SIZE # Import TILE_SIZE constant
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.logger import Logger
from aisim.src.core.sim import THOUGHT_DURATION # Added import
# Constants (Defaults, will be overridden by config)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
WINDOW_TITLE = "AI Sims Simulation"
FPS = 60
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')

def load_config():
    """Loads simulation configuration."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            # Apply defaults if keys are missing
            config.setdefault('simulation', {})
            config['simulation'].setdefault('initial_sims', 10)
            config['simulation'].setdefault('fps', 60)
            config['simulation'].setdefault('enable_talking', False)
            return config
    except FileNotFoundError:
        print(f"Warning: Config file not found at {CONFIG_PATH}. Using defaults.")
        return {"simulation": {"initial_sims": 10, "fps": 60}}
    except json.JSONDecodeError:
        print(f"Warning: Error decoding config file {CONFIG_PATH}. Using defaults.")
        return {"simulation": {"initial_sims": 10, "fps": 60}}

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
    # Load config first
    # Load config first
    config = load_config()
    sim_config = config['simulation']
    fps = sim_config['fps']

    pygame.init() # Pygame init needs to happen before font loading in Sim
    # Create AI Client
    ollama_client = OllamaClient() # Reads its own config section
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()
    ui_font = pygame.font.SysFont(None, 24) # Font for UI text
    log_font = pygame.font.SysFont(None, 18) # Smaller font for event log
    # Create Simulation Components
    weather = Weather(config, SCREEN_WIDTH, SCREEN_HEIGHT) # Pass FULL config and screen dimensions
    city = City(SCREEN_WIDTH, SCREEN_HEIGHT)
    enable_talking = config['simulation']['enable_talking']

    # Store sims in a dictionary for easy lookup by ID
    sims_dict = {}
    for _ in range(sim_config['initial_sims']):
        new_sim = Sim(
            str(uuid.uuid4()),  # Generate unique ID
            max(0, min(random.randint(0, SCREEN_WIDTH), SCREEN_WIDTH - TILE_SIZE -1)),
            max(0, min(random.randint(0, SCREEN_HEIGHT), SCREEN_HEIGHT - TILE_SIZE -1)),
            ollama_client, # Pass the client instance
            enable_talking, # Enable/disable talking from config
            sim_config.get('bubble_display_time_seconds', 5.0) # Pass bubble duration, default 5.0
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
                        sim_rect = pygame.Rect(sim.x - SPRITE_WIDTH // 2, sim.y - SPRITE_HEIGHT // 2, SPRITE_WIDTH, SPRITE_HEIGHT)
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
                sim.update(dt, city, weather.current_state, all_sims_list, logger, current_sim_time, TILE_SIZE, config['movement']['direction_change_frequency']) # Use imported TILE_SIZE
                # Interaction check is now called within sim.update, remove explicit call here
            #   sim._check_interactions(sims, logger, current_sim_time) # Removed redundant call
            weather.update(dt)
            city.update(dt) # Update city state (currently does nothing)

            # --- Poll for Ollama Results (Thoughts & Conversation Responses) ---
            while True:
                result = ollama_client.check_for_thought_results()
                if result is None:
                    break # No more results in the queue for now

                sim_id, response_text = result
                target_sim = sims_dict.get(sim_id)

                if target_sim and response_text:
                    # Pass the response to the Sim's handler method
                    target_sim.handle_ollama_response(response_text, current_sim_time, all_sims_list)
                elif not target_sim:
                     print(f"Warning: Received Ollama result for unknown Sim ID: {sim_id}")
                # The old direct setting of current_thought/thought_timer is now handled within handle_ollama_response

        # --- Drawing --- (Always draw, even when paused)
        screen.fill(weather.get_current_color()) # Use weather color for background

        # Draw city grid first
        city.draw(screen)

        # Draw simulation elements (Sims)
        for sim in sims_dict.values(): # Iterate over dict values
            sim.draw(screen)
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
        if weather.weather_config.get('enable_weather_changes', False): # Only show if changes are enabled
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

            # Draw background and border
            pygame.draw.rect(screen, panel_bg_color, panel_rect, border_radius=10)
            pygame.draw.rect(screen, panel_border_color, panel_rect, width=2, border_radius=10)

            # --- Content ---
            current_y = panel_y + padding
            content_width = panel_width - 2 * padding

            # Portrait
            portrait = detailed_sim.get_portrait()
            if portrait:
                # Scale portrait up slightly for visibility
                portrait_size = 64
                scaled_portrait = pygame.transform.scale(portrait, (portrait_size, portrait_size))
                portrait_x = panel_x + padding
                screen.blit(scaled_portrait, (portrait_x, current_y))
                text_start_x = portrait_x + portrait_size + padding
                text_width = content_width - portrait_size - padding
            else:
                portrait_size = 0 # No portrait height offset needed
                text_start_x = panel_x + padding
                text_width = content_width

            # Basic Info (Name, ID, Sex, Mood) - next to portrait
            info_font = ui_font # Use slightly larger font
            line_h = info_font.get_linesize()

            name_text = f"Name: {detailed_sim.full_name}"
            name_surf = info_font.render(name_text, True, text_color)
            screen.blit(name_surf, (text_start_x, current_y))
            current_y += line_h

            id_text = f"ID: {detailed_sim.sim_id[:8]}..." # Shorten ID
            id_surf = info_font.render(id_text, True, text_color)
            screen.blit(id_surf, (text_start_x, current_y))
            current_y += line_h

            sex_text = f"Sex: {detailed_sim.sex}"
            sex_surf = info_font.render(sex_text, True, text_color)
            screen.blit(sex_surf, (text_start_x, current_y))
            current_y += line_h

            mood_str = get_mood_description(detailed_sim.mood)
            mood_text = f"Mood: {mood_str} ({detailed_sim.mood:.2f})"
            mood_surf = info_font.render(mood_text, True, text_color)
            screen.blit(mood_surf, (text_start_x, current_y))
            current_y += line_h

            # Ensure text doesn't overlap portrait if portrait is tall
            current_y = max(current_y, panel_y + padding + portrait_size + line_spacing)

            # Personality Description
            current_y += line_spacing # Add space before section
            pers_title_surf = log_font.render("Personality:", True, text_color) # Use smaller font for title/body
            screen.blit(pers_title_surf, (panel_x + padding, current_y))
            current_y += log_font.get_linesize()

            pers_lines = wrap_text(detailed_sim.personality_description, log_font, content_width)
            for line in pers_lines:
                if current_y + log_font.get_linesize() > panel_y + panel_height - padding: # Check bounds
                     # Optional: Draw ellipsis or indicator that content is truncated
                     break
                line_surf = log_font.render(line, True, text_color)
                screen.blit(line_surf, (panel_x + padding, current_y))
                current_y += log_font.get_linesize()

            # Relationships
            current_y += line_spacing # Add space before section
            rel_title_surf = log_font.render("Relationships:", True, text_color)
            screen.blit(rel_title_surf, (panel_x + padding, current_y))
            current_y += log_font.get_linesize()

            if detailed_sim.relationships:
                for other_id, values in detailed_sim.relationships.items():
                    if current_y + log_font.get_linesize() > panel_y + panel_height - padding: break # Check bounds
                    other_sim = sims_dict.get(other_id)
                    other_name = other_sim.full_name if other_sim else f"Unknown ({other_id[:6]})"
                    friendship = values.get('friendship', 0.0)
                    romance = values.get('romance', 0.0) # Assuming romance might exist
                    rel_text = f"- {other_name}: F={friendship:.1f}"
                    if 'romance' in values: # Only show romance if it exists
                        rel_text += f", R={romance:.1f}"
                    rel_surf = log_font.render(rel_text, True, text_color)
                    screen.blit(rel_surf, (panel_x + padding, current_y))
                    current_y += log_font.get_linesize()
            else:
                 if current_y + log_font.get_linesize() <= panel_y + panel_height - padding: # Check bounds
                    no_rel_surf = log_font.render("- None", True, text_color)
                    screen.blit(no_rel_surf, (panel_x + padding, current_y))
                    current_y += log_font.get_linesize()


        pygame.display.flip() # Update the full display Surface to the screen
        for sim in sims_dict.values(): # Iterate over dict values
            sim.can_talk = True # Reset talking flag (consider if this is still needed)


    # --- End of main loop ---
    logger.close() # Close log files cleanly
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()