import random
import pygame

class Weather:
    """Manages the simulation's weather system."""

    STATES = ["Sunny", "Cloudy", "Rainy", "Snowy"]
    # Basic colors for visualization
    COLORS = {
        "Sunny": (135, 206, 250),  # Sky Blue
        "Cloudy": (169, 169, 169),  # Dark Gray
        "Rainy": (100, 100, 100),   # Darker Gray
        "Snowy": (200, 200, 200)   # Light Gray
    }
    # TRANSITION_TIME = 10.0 # Removed, now loaded from config

    def __init__(self, config):
        """Initializes the weather system using simulation config."""
        self.config = config
        self.transition_time = self.config.get('weather_transition_time', 15.0) # Default 15s
        self.current_state = random.choice(self.STATES)
        self.time_since_last_change = 0.0
        print(f"Initial weather: {self.current_state} (Changes every {self.transition_time}s)")

    def update(self, dt):
        """Updates the weather state based on time."""
        enable_weather_changes = self.config.get('weather', {}).get('enable_weather_changes', False)
        if not enable_weather_changes:
            return

        self.time_since_last_change += dt
        if self.time_since_last_change >= self.transition_time:
            self.time_since_last_change = 0.0
            old_state = self.current_state
            # Avoid immediately switching back to the same state
            possible_new_states = [s for s in self.STATES if s != old_state]
            self.current_state = random.choice(possible_new_states)
            print(f"Weather changed from {old_state} to {self.current_state}")  # Log change

    def get_current_color(self):
        """Returns the background color for the current weather."""
        return self.COLORS.get(self.current_state, (0, 0, 0)) # Default to black

    def draw_effects(self, screen):
        """Draws weather effects (placeholder)."""
        # TODO: Implement rain particles, snow effects, etc.
        if self.current_state == "Rainy":
            # Simple placeholder: slightly tint screen blueish
            tint = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            tint.fill((0, 0, 50, 30)) # Semi-transparent blue overlay
            screen.blit(tint, (0,0))
        elif self.current_state == "Snowy":
             # Simple placeholder: slightly tint screen whitish
            tint = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            tint.fill((200, 200, 220, 20)) # Semi-transparent white overlay
            screen.blit(tint, (0,0))