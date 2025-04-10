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
    panel_scroll_offset = 0 # Initialize scroll offset
    show_test_bubble = False # Flag to show the test bubble
    while running:
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:  # Close panel on Escape
                    detailed_sim = None
                elif event.key == pygame.K_p: # Toggle pause
                    paused = not paused
                elif event.key in time_scales: # Change speed
                     time_scale = time_scales[event.key]
                     print(f"Time scale set to: {time_scale}x")
                elif event.key == pygame.K_e: # Toggle test bubble
                     show_test_bubble = not show_test_bubble
                     print(f"Test bubble {'enabled' if show_test_bubble else 'disabled'}")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    mouse_x, mouse_y = event.pos
                    mouse_pos = event.pos  # Store mouse position
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
                            selected_tile_info = None # Clear tile info when selecting sim
                            panel_scroll_offset = 0 # Reset scroll on new panel
                            # Reset double-click tracking
                            last_click_time = 0
                            last_clicked_sim_id = None
                        else:
                            # --- Single Click on a Sim ---
                            print(f"Single-clicked Sim: {clicked_on_sim_object.sim_id}")
                            selected_sim = clicked_on_sim_object # Select for log view
                            selected_tile_info = None # Clear tile info when selecting sim
                            detailed_sim = None # Close details panel on single click
                            # Update tracking for potential double-click
                            last_click_time = current_time_ms
                            last_clicked_sim_id = clicked_on_sim_object.sim_id
                    else:
                        # --- Clicked on Empty Space ---
                        selected_sim = None # Deselect for log view
                        detailed_sim = None # Close details panel
                        last_click_time = 0 # Reset double-click tracking
                        last_clicked_sim_id = None

                        # Calculate tile coordinates from mouse position
                        tile_col = mouse_x // TILE_SIZE
                        tile_row = mouse_y // TILE_SIZE

                        # Check if click is within grid bounds
                        if 0 <= tile_row < city.grid_height and 0 <= tile_col < city.grid_width:
                            tile_name = city.tile_map[tile_row][tile_col]
                            tile_type = "unknown" # Default
                            if tile_name:
                                if tile_name.startswith('grass_'):
                                    tile_type = "grass"
                                elif tile_name.startswith('path_'):
                                    tile_type = "path"
                                elif tile_name.startswith('prop_'):
                                    tile_type = "prop" # e.g., tree

                            selected_tile_info = {'coords': (tile_col, tile_row), 'type': tile_type}
                            print(f"Clicked empty space at tile {selected_tile_info['coords']} - Type: {selected_tile_info['type']}")
                        else:
                            selected_tile_info = None # Clicked outside grid
                            print("Clicked empty space outside grid")

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
        # dt is the time passed since the last frame (the smallest time unit) scaled by time_scale 
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
            # Initialize panel sections expanded state
            panel_sections_expanded = {'personality': False, 'romance': False, 'conversation_history': False}

            # The function now returns the potentially clamped scroll offset
            panel_details_result = draw_panel_details(
                screen=screen,
                detailed_sim=detailed_sim,
                panel_scroll_offset=panel_scroll_offset,
                sims_dict=sims_dict,
                ui_font=ui_font,
                log_font=log_font,
                SCREEN_WIDTH=SCREEN_WIDTH,
                SCREEN_HEIGHT=SCREEN_HEIGHT,
                panel_sections_expanded=panel_sections_expanded,
                mouse_pos=mouse_pos
            )

            if panel_details_result is None:
                detailed_sim = None
            else:
                panel_scroll_offset = panel_details_result

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