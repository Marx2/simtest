import pygame
import os
import sys
import sys
import random
import uuid
import os
from aisim.src.core.configuration import config_manager # Import the centralized config manager
from aisim.src.core.sim import Sim # Import Sim class (constants are now internal or loaded from config)
from aisim.src.core.weather import Weather
from aisim.src.core.city import City, TILE_SIZE # Import TILE_SIZE constant
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core import interaction
from aisim.src.core.panel import draw_panel_details
from aisim.src.core.text import draw_bubble,initialize_fonts

print(f"Current working directory: {os.getcwd()}")
print(f"Python sys.path: {sys.path}")
SCREEN_WIDTH = config_manager.get_entry('simulation.screen_width', 800) # Default width
SCREEN_HEIGHT = config_manager.get_entry('simulation.screen_height', 600) # Default height
WINDOW_TITLE = config_manager.get_entry('simulation.window_title', "AI Simulation") # Default title

def main():
    # Get config values using the centralized manager
    fps = config_manager.get_entry('simulation.fps', 60)
    initial_sims = config_manager.get_entry('simulation.initial_sims', 10)
    sim_creation_config = config_manager.get_entry('sim', {}) # Pass the whole 'sim' section if Sim expects it
    movement_direction_change_frequency = config_manager.get_entry('movement.direction_change_frequency', 5.0)
    pygame.init() # Pygame init needs to happen before font loading in Sim
    initialize_fonts()
    # Create AI Client
    ollama_client = OllamaClient() # Reads its own config section
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()
    PANEL_FONT_PATH = config_manager.get_entry('sim.panel_font_dir')
    ui_font = pygame.font.Font(PANEL_FONT_PATH, 18) # Font for UI text
    log_font = pygame.font.Font(PANEL_FONT_PATH, 14) # Smaller font for event log
    # Create Simulation Components
    weather = Weather(config_manager, SCREEN_WIDTH, SCREEN_HEIGHT) # Pass the main config manager
    city = City(SCREEN_WIDTH, SCREEN_HEIGHT) # City will use config_manager internally now

    # Store sims in a dictionary for easy lookup by ID
    sims_dict = {}
    sims_dict = initialize_sims(initial_sims, sims_dict, ollama_client, sim_creation_config, SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE)

    # Add sims to city
    city.sims = list(sims_dict.values()) # City might still expect a list

    running = True
    paused = False
    time_scale = 1.0 # Normal speed
    time_scales = {pygame.K_1: 1.0, pygame.K_2: 2.0, pygame.K_4: 4.0, pygame.K_0: 10.0} # Add 0 for 10x

    current_sim_time = 0.0 # Track total simulation time passed
    selected_sim = None # Track the currently selected Sim (for bottom log)
    selected_tile_info = None # Track the last clicked tile info
    detailed_sim = None # Track the Sim for the details panel
    last_click_time = 0
    last_clicked_sim_id = None
    DOUBLE_CLICK_TIME = 500 # Milliseconds
    panel_state = {} # Initialize panel state dictionary
    scrollbar_dragging = False # Track if scrollbar handle is being dragged
    drag_start_y = 0
    drag_start_offset = 0
    show_test_bubble = False # Flag to show the test bubble
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
                elif event.key == pygame.K_ESCAPE and detailed_sim: # Close panel with Escape
                    detailed_sim = None
                    panel_state = {} # Clear state when closing
                elif event.key == pygame.K_e: # Toggle test bubble
                     show_test_bubble = not show_test_bubble
                     print(f"Test bubble {'enabled' if show_test_bubble else 'disabled'}")
            # --- MOUSE BUTTON DOWN ---
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    mouse_x, mouse_y = event.pos
                    current_time_ms = pygame.time.get_ticks()
                    panel_interacted = False # Flag if click was handled by the panel UI

                    # --- Panel Interaction Check (if panel is open) ---
                    if detailed_sim:
                        # Use the correct panel dimensions
                        panel_width_check = 450
                        panel_height_check = 450
                        panel_x_check = (SCREEN_WIDTH - panel_width_check) // 2
                        panel_y_check = (SCREEN_HEIGHT - panel_height_check) // 2
                        panel_rect_check = pygame.Rect(panel_x_check, panel_y_check, panel_width_check, panel_height_check)

                        if panel_rect_check.collidepoint(mouse_x, mouse_y):
                            # Check close button first
                            if panel_state.get("close_button_rect") and panel_state["close_button_rect"].collidepoint(mouse_x, mouse_y):
                                print("Clicked panel close button")
                                detailed_sim = None
                                panel_state = {} # Clear state
                                panel_interacted = True
                            # Check headers if close wasn't clicked
                            elif not panel_interacted:
                                for section, rect in panel_state.get("header_rects", {}).items():
                                    if rect.collidepoint(mouse_x, mouse_y):
                                        state_key = f"{section}_expanded"
                                        panel_state[state_key] = not panel_state.get(state_key, True) # Toggle
                                        panel_state["scroll_offset"] = 0 # Reset scroll
                                        print(f"Toggled section '{section}' to {panel_state[state_key]}")
                                        panel_interacted = True
                                        break
                            # Check scrollbar if headers weren't clicked
                            elif not panel_interacted:
                                handle_rect = panel_state.get("scrollbar_handle_rect")
                                track_rect = panel_state.get("scrollbar_track_rect")
                                max_scroll = panel_state.get("max_scroll", 0)

                                if handle_rect and handle_rect.collidepoint(mouse_x, mouse_y):
                                    scrollbar_dragging = True
                                    drag_start_y = mouse_y
                                    drag_start_offset = panel_state.get("scroll_offset", 0)
                                    print("Started dragging scrollbar handle")
                                    panel_interacted = True
                                elif track_rect and track_rect.collidepoint(mouse_x, mouse_y):
                                    # Click on track: Page up/down
                                    panel_visible_height = panel_height_check - 2 * 15 # padding
                                    current_offset = panel_state.get("scroll_offset", 0)
                                    if handle_rect and mouse_y < handle_rect.centery: # Clicked above handle
                                        panel_state["scroll_offset"] = max(0, current_offset - panel_visible_height)
                                    else: # Clicked below handle or no handle visible
                                        panel_state["scroll_offset"] = min(max_scroll, current_offset + panel_visible_height)
                                    # Clamp
                                    panel_state["scroll_offset"] = max(0, min(max_scroll, panel_state["scroll_offset"]))
                                    print(f"Clicked scrollbar track. New offset: {panel_state['scroll_offset']}")
                                    panel_interacted = True
                            # If click was inside panel but not on interactive element, set flag
                            if not panel_interacted:
                                panel_interacted = True # Still counts as interacting with panel background

                    # --- Process click on Sim/Background only if panel wasn't interacted with ---
                    if not panel_interacted:
                        clicked_on_sim_object = None
                        min_dist_sq = float('inf')

                        # Find the closest sim to the click
                        for sim in sims_dict.values():
                            sim_rect = pygame.Rect(sim.x - sim.sprite_width // 2, sim.y - sim.sprite_height // 2, sim.sprite_width, sim.sprite_height)
                            if sim_rect.collidepoint(mouse_x, mouse_y):
                                 dist_sq = (sim.x - mouse_x)**2 + (sim.y - mouse_y)**2
                                 if dist_sq < min_dist_sq:
                                     min_dist_sq = dist_sq
                                     clicked_on_sim_object = sim

                        # Handle Sim Click (Double/Single)
                        if clicked_on_sim_object:
                            time_since_last_click = current_time_ms - last_click_time
                            if clicked_on_sim_object.sim_id == last_clicked_sim_id and time_since_last_click < DOUBLE_CLICK_TIME:
                                print(f"Double-clicked Sim: {clicked_on_sim_object.sim_id}")
                                detailed_sim = clicked_on_sim_object
                                selected_sim = clicked_on_sim_object
                                selected_tile_info = None
                                panel_state = { # Initialize panel state
                                    "scroll_offset": 0, "personality_expanded": True,
                                    "romance_expanded": True, "history_expanded": True,
                                    "close_button_rect": None, "header_rects": {},
                                    "scrollbar_handle_rect": None, "scrollbar_track_rect": None,
                                    "max_scroll": 0
                                }
                                last_click_time = 0
                                last_clicked_sim_id = None
                            else: # Single Click
                                print(f"Single-clicked Sim: {clicked_on_sim_object.sim_id}")
                                selected_sim = clicked_on_sim_object
                                selected_tile_info = None
                                # Don't close panel on single click
                                last_click_time = current_time_ms
                                last_clicked_sim_id = clicked_on_sim_object.sim_id
                        # Handle Background Click
                        else:
                            selected_sim = None
                            # Don't close panel on background click
                            last_click_time = 0
                            last_clicked_sim_id = None
                            # Calculate tile info
                            tile_col = mouse_x // TILE_SIZE
                            tile_row = mouse_y // TILE_SIZE
                            if 0 <= tile_row < city.grid_height and 0 <= tile_col < city.grid_width:
                                tile_name = city.tile_map[tile_row][tile_col]
                                tile_type = "unknown"
                                if tile_name:
                                    if tile_name.startswith('grass_'): tile_type = "grass"
                                    elif tile_name.startswith('path_'): tile_type = "path"
                                    elif tile_name.startswith('prop_'): tile_type = "prop"
                                selected_tile_info = {'coords': (tile_col, tile_row), 'type': tile_type}
                                print(f"Clicked empty space at tile {selected_tile_info['coords']} - Type: {selected_tile_info['type']}")
                            else:
                                selected_tile_info = None
                                print("Clicked empty space outside grid")

            # --- MOUSE WHEEL ---
            elif event.type == pygame.MOUSEWHEEL:
                 if detailed_sim:
                     mouse_pos = pygame.mouse.get_pos()
                     panel_width_scroll = 450
                     panel_height_scroll = 450
                     panel_x_scroll = (SCREEN_WIDTH - panel_width_scroll) // 2
                     panel_y_scroll = (SCREEN_HEIGHT - panel_height_scroll) // 2
                     panel_rect_scroll = pygame.Rect(panel_x_scroll, panel_y_scroll, panel_width_scroll, panel_height_scroll)

                     if panel_rect_scroll.collidepoint(mouse_pos):
                         scroll_speed = 30
                         current_offset = panel_state.get("scroll_offset", 0)
                         max_scroll = panel_state.get("max_scroll", 0)
                         panel_state["scroll_offset"] = current_offset - event.y * scroll_speed
                         panel_state["scroll_offset"] = max(0, min(max_scroll, panel_state["scroll_offset"])) # Clamp

            # --- MOUSE MOTION (for scrollbar dragging) ---
            elif event.type == pygame.MOUSEMOTION:
                 if scrollbar_dragging and detailed_sim:
                     mouse_x, mouse_y = event.pos
                     delta_y = mouse_y - drag_start_y

                     handle_rect = panel_state.get("scrollbar_handle_rect")
                     track_rect = panel_state.get("scrollbar_track_rect")
                     max_scroll = panel_state.get("max_scroll", 0)

                     if handle_rect and track_rect and max_scroll > 0:
                         scrollable_track_height = track_rect.height - handle_rect.height
                         if scrollable_track_height > 0:
                              scroll_ratio = max_scroll / scrollable_track_height
                              delta_offset = delta_y * scroll_ratio
                              new_offset = drag_start_offset + delta_offset
                              panel_state["scroll_offset"] = max(0, min(max_scroll, new_offset)) # Clamp

            # --- MOUSE BUTTON UP (stop scrollbar dragging) ---
            elif event.type == pygame.MOUSEBUTTONUP:
                 if event.button == 1: # Left button release
                     if scrollbar_dragging:
                         scrollbar_dragging = False
                         print("Stopped dragging scrollbar handle")

        # --- Game Logic Update --- (This block is now OUTSIDE the event loop)
        raw_dt = clock.tick(fps) / 1000.0 # Get raw delta time

        # Apply time controls
        if paused:
            dt = 0.0 # No time passes if paused
        else:
            dt = raw_dt * time_scale # Apply speed multiplier

        # Only update simulation state if time is passing
        if dt > 0:
            current_sim_time += dt # Increment simulation time
            all_sims_list = list(sims_dict.values()) # Get list for passing to update
            for sim in all_sims_list:
                # Pass city.TILE_SIZE to sim.update for arrival checks
                sim.sim_update(dt, city, weather.current_state, all_sims_list, current_sim_time, TILE_SIZE, movement_direction_change_frequency) # Use retrieved frequency
            weather.weather_update(dt)
            city.city_update(dt) # Update city state (currently does nothing)

            # --- Poll for Ollama Results (Conversation Responses, Analysis) ---
            while True:
                result_data = ollama_client.check_for_results() # Use the updated method
                if result_data is None:
                    break # No more results in the queue for now

                result_type = result_data.get('type')

                if result_type == 'conversation':
                    sim_id = result_data.get('sim_id')
                    response_text = result_data.get('data')
                    target_sim = sims_dict.get(sim_id)
                    if target_sim and response_text:
                        # Pass conversation response to the interaction handler
                        interaction.handle_ollama_response(target_sim, response_text, all_sims_list, city)
                    elif not target_sim:
                        print(f"Warning: Received 'conversation' result for unknown Sim ID: {sim_id}")

                elif result_type == 'romance_analysis':
                    sim1_id = result_data.get('sim1_id')
                    sim2_id = result_data.get('sim2_id')
                    analysis_result = result_data.get('data') # INCREASE, DECREASE, NEUTRAL

                    sim1 = sims_dict.get(sim1_id)
                    sim2 = sims_dict.get(sim2_id)
                    romance_change_step = config_manager.get_entry('simulation.romance_change_step', 0.05) # Get from config

                    if sim1 and sim2 and analysis_result:
                        change = 0.0
                        if analysis_result == "INCREASE":
                            change = romance_change_step
                        elif analysis_result == "DECREASE":
                            change = -romance_change_step

                        if change != 0.0:
                            # Update Sim 1's relationship towards Sim 2
                            if sim2_id in sim1.relationships:
                                current_romance_1 = sim1.relationships[sim2_id].get("romance", 0.0)
                                new_romance_1 = max(0.0, min(1.0, current_romance_1 + change))
                                sim1.relationships[sim2_id]["romance"] = new_romance_1
                                print(f"Romance {sim1.first_name} -> {sim2.first_name}: {current_romance_1:.2f} -> {new_romance_1:.2f} ({analysis_result})")
                            else: # Initialize if somehow missing
                                sim1.relationships[sim2_id] = {"friendship": 0.0, "romance": max(0.0, min(1.0, change))}
                                print(f"Romance {sim1.first_name} -> {sim2.first_name}: Initialized to {sim1.relationships[sim2_id]['romance']:.2f} ({analysis_result})")

                            # Update Sim 2's relationship towards Sim 1
                            if sim1_id in sim2.relationships:
                                current_romance_2 = sim2.relationships[sim1_id].get("romance", 0.0)
                                new_romance_2 = max(0.0, min(1.0, current_romance_2 + change))
                                sim2.relationships[sim1_id]["romance"] = new_romance_2
                                print(f"Romance {sim2.first_name} -> {sim1.first_name}: {current_romance_2:.2f} -> {new_romance_2:.2f} ({analysis_result})")
                            else: # Initialize if somehow missing
                                sim2.relationships[sim1_id] = {"friendship": 0.0, "romance": max(0.0, min(1.0, change))}
                                print(f"Romance {sim2.first_name} -> {sim1.first_name}: Initialized to {sim2.relationships[sim1_id]['romance']:.2f} ({analysis_result})")
                        else:
                             print(f"Romance analysis between {sim1.first_name} and {sim2.first_name}: NEUTRAL, no change.")

                    elif not sim1:
                        print(f"Warning: Received 'romance_analysis' for unknown Sim1 ID: {sim1_id}")
                    elif not sim2:
                        print(f"Warning: Received 'romance_analysis' for unknown Sim2 ID: {sim2_id}")

                    # --- Remove pair from pending analysis lock ---
                    if sim1_id and sim2_id:
                        analysis_pair = tuple(sorted((sim1_id, sim2_id)))
                        city.pending_romance_analysis.discard(analysis_pair)
                        # print(f"Removed {analysis_pair} from pending romance analysis.") # Debug

                else:
                    print(f"Warning: Received unknown result type from Ollama queue: {result_type}")
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
        # Assuming Weather class is refactored or handles its config access internally
        if config_manager.get_entry('weather.enable_weather_changes', False): # Check directly via config_manager
            remaining_time = max(0, weather.change_frequency - weather.time_since_last_change)
            countdown_text = f"Next change in: {int(remaining_time)}s" # Cast to int
            countdown_surface = ui_font.render(countdown_text, True, (220, 220, 220)) # Slightly dimmer white
            countdown_rect = countdown_surface.get_rect(topright=(SCREEN_WIDTH - 10, weather_rect.bottom + 5)) # Position below weather text
            screen.blit(countdown_surface, countdown_rect)


        # --- Display Info at Bottom Left (Sim Log or Tile Info) ---
        log_y = SCREEN_HEIGHT - 15 # Base y position near bottom
        log_x = 10                 # Base x position near left

        if selected_sim:
            # --- Display Sim Info and Log ---
            # Calculate position for the Sim ID text based on log count
            num_logs = len(selected_sim.memory[-5:]) if selected_sim.memory else 0
            info_y_pos = log_y - (num_logs + 1) * 15 # Position above logs

            # Render and blit Sim ID text
            id_text = f"Selected: {selected_sim.full_name} (Mood: {selected_sim.mood:.2f})"
            id_surface = log_font.render(id_text, True, (255, 255, 255))
            screen.blit(id_surface, (log_x, info_y_pos))

        elif selected_tile_info:
            # --- Display Clicked Tile Info ---
            coords = selected_tile_info['coords']
            tile_type = selected_tile_info['type']
            tile_text = f"Tile: {coords} - Type: {tile_type}"
            tile_surface = log_font.render(tile_text, True, (255, 255, 255)) # Use log font

            # Position one line up from the very bottom edge (similar to Sim ID when no logs)
            info_y_pos = log_y - 15
            screen.blit(tile_surface, (log_x, info_y_pos))


        # --- Draw Sim Details Panel ---
        if detailed_sim:
            # Call the new function to draw the panel
            # The function now returns the potentially clamped scroll offset
            # Call the updated function, passing the panel_state dictionary
            # The function now modifies panel_state directly and doesn't return the offset
            draw_panel_details(
                screen,
                detailed_sim,
                panel_state, # Pass the state dictionary
                sims_dict,
                ui_font,
                log_font,
                SCREEN_WIDTH,
                SCREEN_HEIGHT
            )

        # --- Draw Test Bubble ---
        if show_test_bubble:
            test_text = "Test Bubble! 👋🤔🎉✨ Emojis!"
            test_pos = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2) # Center screen
            # Call draw_bubble - it will use its internal default fonts if None passed
            draw_bubble(screen, test_text, test_pos) # Use defaults from panel.py

        pygame.display.flip() # Update the full display Surface to the screen


    # --- End of main loop ---
    pygame.quit()
    sys.exit()

def initialize_sims(initial_sims, sims_dict, ollama_client, sim_creation_config, SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE):
    for _ in range(initial_sims): # Use retrieved initial_sims
        new_sim = Sim(
            sim_id=str(uuid.uuid4()),  # Generate unique ID
            x=max(0, min(random.randint(0, SCREEN_WIDTH), SCREEN_WIDTH - TILE_SIZE - 1)),
            y=max(0, min(random.randint(0, SCREEN_HEIGHT), SCREEN_HEIGHT - TILE_SIZE - 1)),
            ollama_client=ollama_client, # Pass the client instance
            sim_config=sim_creation_config, # Pass the retrieved sim config dictionary
        )
        sims_dict[new_sim.sim_id] = new_sim
    return sims_dict

if __name__ == "__main__":
    main()