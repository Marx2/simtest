import pygame
import sys
import random
import uuid
import json
import os
from core.sim import Sim
from core.weather import Weather
from core.city import City
from ai.ollama_client import OllamaClient

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
            return config
    except FileNotFoundError:
        print(f"Warning: Config file not found at {CONFIG_PATH}. Using defaults.")
        return {"simulation": {"initial_sims": 10, "fps": 60}}
    except json.JSONDecodeError:
        print(f"Warning: Error decoding config file {CONFIG_PATH}. Using defaults.")
        return {"simulation": {"initial_sims": 10, "fps": 60}}


def main():
    """Main function to run the simulation."""
    # Load config first
    config = load_config()
    sim_config = config['simulation']
    fps = sim_config['fps']

    pygame.init() # Pygame init needs to happen before font loading in Sim
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()
    ui_font = pygame.font.SysFont(None, 24) # Font for UI text
    # Create AI Client
    ollama_client = OllamaClient() # Reads its own config section

    # Create Simulation Components
    weather = Weather()
    city = City(SCREEN_WIDTH, SCREEN_HEIGHT)
    sims = [
        Sim(
            str(uuid.uuid4()), # Generate unique ID
            random.randint(0, SCREEN_WIDTH),
            random.randint(0, SCREEN_HEIGHT),
            ollama_client # Pass the client instance
        ) for _ in range(sim_config['initial_sims'])
    ]

    running = True
    paused = False
    time_scale = 1.0 # Normal speed
    time_scales = {pygame.K_1: 1.0, pygame.K_2: 2.0, pygame.K_4: 4.0, pygame.K_0: 10.0} # Add 0 for 10x

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

        # Calculate delta time (time since last frame)
        raw_dt = clock.tick(fps) / 1000.0 # Get raw delta time

        # Apply time controls
        if paused:
            dt = 0.0 # No time passes if paused
        else:
            dt = raw_dt * time_scale # Apply speed multiplier
        # Game logic updates
        # Only update simulation logic if time is passing
        if dt > 0:
            for sim in sims:
                sim.update(dt, city, weather.current_state, sims) # Pass all sims
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

        pygame.display.flip()  # Update the full display Surface to the screen

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()