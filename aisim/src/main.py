import pygame
import os
import sys
print(f"Current working directory: {os.getcwd()}")
print(f"Python sys.path: {sys.path}")
import sys
import random
import uuid
import json
import os
from aisim.src.core.sim import Sim
from aisim.src.core.weather import Weather
from aisim.src.core.city import City, TILE_SIZE # Import TILE_SIZE constant
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.logger import Logger
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
    weather = Weather(sim_config) # Pass simulation config
    city = City(SCREEN_WIDTH, SCREEN_HEIGHT)
    enable_talking = config['simulation']['enable_talking']
    sims = [
        Sim(
            str(uuid.uuid4()), # Generate unique ID
            random.randint(0, SCREEN_WIDTH),
            random.randint(0, SCREEN_HEIGHT),
            ollama_client, # Pass the client instance
            enable_talking # Enable/disable talking from config
        ) for _ in range(sim_config['initial_sims'])
    ]
    # Allow sims to talk after display is initialized
    logger = Logger() # Create logger instance

    running = True
    paused = False
    time_scale = 1.0 # Normal speed
    time_scales = {pygame.K_1: 1.0, pygame.K_2: 2.0, pygame.K_4: 4.0, pygame.K_0: 10.0} # Add 0 for 10x

    current_sim_time = 0.0 # Track total simulation time passed
    selected_sim = None # Track the currently selected Sim


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
                    clicked_sim = None
                    min_dist_sq = float('inf')
                    # Find the closest sim to the click, within a small radius
                    for sim in sims:
                        dist_sq = (sim.x - mouse_x)**2 + (sim.y - mouse_y)**2
                        if dist_sq < 400 and dist_sq < min_dist_sq: # Click within ~20px radius (4x typical Sim radius)
                            min_dist_sq = dist_sq
                            clicked_sim = sim
                    if clicked_sim:
                        selected_sim = clicked_sim
                        print(f"Selected Sim: {selected_sim.sim_id}")
                    else:
                        selected_sim = None # Deselect if clicking empty space
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
            for sim in sims:
                # Pass city.TILE_SIZE to sim.update for arrival checks
                sim.update(dt, city, weather.current_state, sims, logger, current_sim_time, TILE_SIZE, config['movement']['direction_change_frequency']) # Use imported TILE_SIZE
                # Interaction check is now called within sim.update, remove explicit call here
            #   sim._check_interactions(sims, logger, current_sim_time) # Removed redundant call
            weather.update(dt)
            city.update(dt) # Update city state (currently does nothing)

        # --- Drawing --- (Always draw, even when paused)
        screen.fill(weather.get_current_color()) # Use weather color for background

        # Draw city grid first
        city.draw(screen)

        # Draw simulation elements (Sims)
        for sim in sims:
            sim.draw(screen)
        weather.draw_effects(screen) # Draw weather effects over sims

        # Draw UI Text (Pause/Speed)
        if paused:
            status_text = "PAUSED"
        else:
            status_text = f"Speed: {time_scale}x"
        status_surface = ui_font.render(status_text, True, (255, 255, 255))
        screen.blit(status_surface, (10, 10)) # Top-left corner

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
        pygame.display.flip()  # Update the full display Surface to the screen
        for sim in sims:
            sim.can_talk = True



    # --- End of main loop ---
    logger.close() # Close log files cleanly
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()