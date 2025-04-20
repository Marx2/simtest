import pygame
import os
import sys
import random
import uuid
import os
import pygame_gui # Import pygame_gui
from aisim.src.core.configuration import config_manager # Import the centralized config manager
from aisim.src.core.sim import Sim # Import Sim class (constants are now internal or loaded from config)
from aisim.src.core.weather import Weather
from aisim.src.core.city import City, TILE_SIZE # Import TILE_SIZE constant
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core import interaction
from aisim.src.core.mood import get_mood_description # Needed for Sim details window (in panel.py)
from aisim.src.ui.panel import create_or_focus_sim_details_window # Import the moved function
from aisim.src.ui.bubble import manage_conversation_bubbles # Import the moved function
print(f"Current working directory: {os.getcwd()}")
print(f"Python sys.path: {sys.path}")
SCREEN_WIDTH = config_manager.get_entry('simulation.screen_width', 800) # Default width
SCREEN_HEIGHT = config_manager.get_entry('simulation.screen_height', 600) # Default height
WINDOW_TITLE = config_manager.get_entry('simulation.window_title', "AI Simulation") # Default title

# Dictionary to store active Sim detail windows {sim_id: UIWindow}
active_detail_windows = {} # {sim_id: UIWindow}
active_bubble_labels = {} # {sim_id: UILabel}
# Function create_or_focus_sim_details_window moved to aisim.src.ui.panel

def main():
    # Get config values using the centralized manager
    fps = config_manager.get_entry('simulation.fps', 60)
    initial_sims = config_manager.get_entry('simulation.initial_sims', 10)
    sim_creation_config = config_manager.get_entry('sim', {}) # Pass the whole 'sim' section if Sim expects it
    movement_direction_change_frequency = config_manager.get_entry('movement.direction_change_frequency', 5.0)
    pygame.init() # Pygame init needs to happen before font loading in Sim
    # initialize_fonts() # Removed - Handled by pygame_gui theme
    # Create AI Client
    ollama_client = OllamaClient() # Reads its own config section
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    # --- Pygame GUI Setup ---
    ui_manager = pygame_gui.UIManager((SCREEN_WIDTH, SCREEN_HEIGHT), 'aisim/config/theme.json')

    # --- Create Static UI Labels ---
    # Status Label (Top-Left)
    status_label_rect = pygame.Rect(0, 0, 150, 25)
    status_label_rect.topleft = (10, 10)
    status_label = pygame_gui.elements.UILabel(
        relative_rect=status_label_rect,
        text="Speed: 1.0x",
        manager=ui_manager,
        anchors={'left': 'left', 'top': 'top'}
    )

    # Weather Label (Top-Right)
    weather_label_rect = pygame.Rect(0, 0, 200, 25)
    weather_label_rect.topright = (-10, 10)
    weather_label = pygame_gui.elements.UILabel(
        relative_rect=weather_label_rect,
        text="Weather: Sunny",
        manager=ui_manager,
        anchors={'right': 'right', 'top': 'top'}
    )
     # Weather Countdown Label (Below Weather)
    countdown_label_rect = pygame.Rect(0, 0, 200, 25)
    countdown_label_rect.topright = (-10, 35) # Position below weather_label
    countdown_label = pygame_gui.elements.UILabel(
        relative_rect=countdown_label_rect,
        text="", # Initially empty or placeholder
        manager=ui_manager,
        anchors={'right': 'right', 'top': 'top'}
    )

    # Bottom Info Label (Bottom-Left)
    bottom_info_label_rect = pygame.Rect(0, 0, SCREEN_WIDTH - 20, 25) # Wide label
    bottom_info_label_rect.bottomleft = (10, -10)
    bottom_info_label = pygame_gui.elements.UILabel(
        relative_rect=bottom_info_label_rect,
        text="Click on a Sim or Tile",
        manager=ui_manager,
        anchors={'left': 'left', 'bottom': 'bottom', 'right': 'right'} # Anchor left and bottom
    )
    # --- End Static UI Labels ---
    # --- End Pygame GUI Setup ---

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
    selected_sim = None # Track the currently selected Sim (for bottom label)
    selected_tile_info = None # Track the last clicked tile info
    last_click_time = 0
    last_clicked_sim_id = None
    DOUBLE_CLICK_TIME = 500 # Milliseconds
    while running:
        # Event handling
        time_delta = clock.tick(fps) / 1000.0 # Calculate time_delta here for UIManager

        for event in pygame.event.get():
            ui_manager.process_events(event) # Pass events to the UI Manager
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p: # Toggle pause
                    paused = not paused
                elif event.key in time_scales: # Change speed
                     time_scale = time_scales[event.key]
                     print(f"Time scale set to: {time_scale}x")
                # ADDED: Manual weather change trigger
                elif event.key == pygame.K_w:
                    print("W key pressed - forcing next weather state.")
                    weather.force_next_weather() # Call the new method
            # --- Mouse Button Down Logic (Refactored for GUI) ---
            elif event.type == pygame.MOUSEBUTTONDOWN:
                 if event.button == 1: # Left click
                    # Check if the click was handled by the GUI first
                    # Note: pygame_gui doesn't directly tell us if a click was *on* a GUI element easily here.
                    # We rely on the fact that GUI elements will consume the event if clicked.
                    # A more robust way might involve checking mouse position against GUI element rects,
                    # but let's try the simpler approach first. We assume if we reach here,
                    # the click was likely *not* on an interactive GUI element like a button or window drag bar.
                    # However, clicking *inside* a non-interactive part of a window might still reach here.

                    mouse_x, mouse_y = event.pos
                    current_time_ms = pygame.time.get_ticks()
                    clicked_on_sim_object = None
                    min_dist_sq = float('inf')

                    # Find the closest sim to the click (same logic as before)
                    for sim in sims_dict.values():
                        sim_rect = pygame.Rect(sim.x - sim.sprite_width // 2, sim.y - sim.sprite_height // 2, sim.sprite_width, sim.sprite_height)
                        if sim_rect.collidepoint(mouse_x, mouse_y):
                             dist_sq = (sim.x - mouse_x)**2 + (sim.y - mouse_y)**2
                             if dist_sq < min_dist_sq:
                                 min_dist_sq = dist_sq
                                 clicked_on_sim_object = sim

                    # --- Handle Click Logic (Refactored Actions) ---
                    if clicked_on_sim_object:
                        # --- Double Click Check ---
                        time_since_last_click = current_time_ms - last_click_time
                        if clicked_on_sim_object.sim_id == last_clicked_sim_id and time_since_last_click < DOUBLE_CLICK_TIME:
                            print(f"Double-clicked Sim: {clicked_on_sim_object.sim_id}")
                            # --- Action: Create or Focus Sim Details Window (Call moved function) ---
                            create_or_focus_sim_details_window(
                                clicked_on_sim_object, ui_manager, sims_dict, active_detail_windows, SCREEN_WIDTH, SCREEN_HEIGHT
                            )
                            selected_sim = clicked_on_sim_object # Keep track for bottom label
                            selected_tile_info = None
                            # Reset double-click tracking
                            last_click_time = 0
                            last_clicked_sim_id = None
                        else:
                            # --- Single Click on a Sim ---
                            print(f"Single-clicked Sim: {clicked_on_sim_object.sim_id}")
                            selected_sim = clicked_on_sim_object # Keep track for bottom label
                            selected_tile_info = None
                            # Close *all* Sim detail windows? Or just deselect? Let's just update the label for now.
                            # detailed_sim = None # No longer used
                            # Update tracking for potential double-click
                            last_click_time = current_time_ms
                            last_clicked_sim_id = clicked_on_sim_object.sim_id
                    else:
                        # --- Clicked on Empty Space ---
                        selected_sim = None # Deselect for label
                        # detailed_sim = None # No longer used
                        last_click_time = 0 # Reset double-click tracking
                        last_clicked_sim_id = None

                        # Calculate tile coordinates (same logic as before)
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

            # --- Pygame GUI Event Handling ---
            elif event.type == pygame_gui.UI_WINDOW_CLOSE:
                 # Check if the closed window is one of our tracked Sim detail windows
                 closed_window_element = event.ui_element
                 sim_id_to_remove = None
                 for sim_id, window in active_detail_windows.items():
                     if window == closed_window_element:
                         sim_id_to_remove = sim_id
                         break
                 if sim_id_to_remove:
                     print(f"Sim detail window for {sim_id_to_remove} closed by user.")
                     del active_detail_windows[sim_id_to_remove]
                 else:
                     print(f"GUI Window Closed (not a tracked Sim window): {event.ui_element}")
                 # We might need to remove the window reference from our tracking dict here.

            # Add other GUI event handlers as needed (e.g., button presses)
            # elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            #     if event.ui_element == some_button:
            #         print("Button pressed!")
        # Calculate delta time (time since last frame) - Moved before event loop

        # Apply time controls
        # dt is the time passed since the last frame (the smallest time unit) scaled by time_scale
        if paused:
            dt = 0.0 # No time passes if paused
        else:
            # Use time_delta calculated before event loop for consistency
            dt = time_delta * time_scale # Apply speed multiplier
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

                else:
                    print(f"Warning: Received unknown result type from Ollama queue: {result_type}")

        # --- Update UI Label Text ---
        # Status Label
        if paused:
            status_label.set_text("PAUSED")
        else:
            status_label.set_text(f"Speed: {time_scale}x")

        # Weather Label
        weather_label.set_text(f"Weather: {weather.current_state}")

        # Weather Countdown Label
        if config_manager.get_entry('weather.enable_weather_changes', False):
            remaining_time = max(0, weather.change_frequency - weather.time_since_last_change)
            countdown_label.set_text(f"Next change in: {int(remaining_time)}s")
            countdown_label.show() # Ensure it's visible
        else:
            countdown_label.hide() # Hide if weather changes are disabled

        # Bottom Info Label
        if selected_sim:
             bottom_info_label.set_text(f"Selected: {selected_sim.full_name} (Mood: {selected_sim.mood:.2f})")
        elif selected_tile_info:
             coords = selected_tile_info['coords']
             tile_type = selected_tile_info['type']
             bottom_info_label.set_text(f"Tile: {coords} - Type: {tile_type}")
        else:
             bottom_info_label.set_text("Click Sim (Single=Select, Double=Details) or Tile")
        # --- End Update UI Label Text ---

        # --- Update UI Manager ---
        ui_manager.update(time_delta) # Update GUI elements

        # --- Drawing --- (Always draw, even when paused)
        screen.fill(weather.get_current_color()) # Use weather color for background
        # Draw city grid first
        city.draw(screen)

        # Draw simulation elements (Sims)
        for sim in sims_dict.values(): # Iterate over dict values
            sim.draw(screen, dt, all_sims_list)
        weather.draw_effects(screen) # Draw weather effects over sims

        # --- Manage Conversation Bubbles (Call moved function) ---
        manage_conversation_bubbles(sims_dict, active_bubble_labels, ui_manager)


        # --- Draw UI Elements using Pygame GUI ---
        ui_manager.draw_ui(screen)
        # Removed manual drawing of status text, weather text, bottom info, and details panel

        # Removed test bubble drawing logic
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