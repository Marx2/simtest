import random
import pygame
import logging # Added missing import
class Weather:
    """Manages the simulation's weather system."""


    def __init__(self, config_manager, screen_width, screen_height):
        """Initializes the weather system using simulation config."""
        self.config_manager = config_manager

        # Use config_manager directly with full paths
        self.change_frequency = self.config_manager.get_entry('weather.weather_change_frequency', 60.0)
        self.transition_duration = self.config_manager.get_entry('simulation.weather_transition_time', 1.0)

        # Initialize states and colors from config_manager
        self.states = self.config_manager.get_entry('weather.states', ["Sunny", "Cloudy", "Rainy", "Snowy"])
        default_colors = { # Define default here for clarity
                "Sunny": [135, 206, 250],
                "Cloudy": [169, 169, 169],
                "Rainy": [100, 100, 100],
                "Snowy": [200, 200, 200]
            }
        self.colors = {
            state: tuple(color)
            for state, color in self.config_manager.get_entry('weather.colors', default_colors).items()
        }

        self.current_state = random.choice(self.states)
        self.time_since_last_change = 0.0
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.raindrops = [] # List to store raindrop positions [(x, y), ...]
        self.max_raindrops = 200
        self.snowflakes = [] # List to store snowflake positions [(x, y, size), ...]
        self.max_snowflakes = 150 # Fewer, larger flakes
        self.is_transitioning = False
        self.transition_timer = 0.0

        logging.info(f"Initial weather: {self.current_state} (Changes possible every {self.change_frequency}s, transition: {self.transition_duration}s)")

    def weather_update(self, dt):
        """Updates the weather state based on time and manages effects."""
        enable_weather_changes = self.config_manager.get_entry('weather.enable_weather_changes', False)
        if not enable_weather_changes:
            # Still update effects even if weather type doesn't change
            self._effects_update(dt)
            return

        self.time_since_last_change += dt
        if self.time_since_last_change >= self.change_frequency:
            self.time_since_last_change = 0.0
            old_state = self.current_state
            # Avoid immediately switching back to the same state
            possible_new_states = [s for s in self.states if s != old_state]
            if not possible_new_states: # Handle case where there's only one state
                possible_new_states = self.states
            self.current_state = random.choice(possible_new_states)
            logging.info(f"Weather changed from {old_state} to {self.current_state}")  # Log change
            # Start transition effect
            self.is_transitioning = True
            self.transition_timer = self.transition_duration


        # Update transition timer
        if self.is_transitioning:
            self.transition_timer -= dt
            if self.transition_timer <= 0:
                self.is_transitioning = False
                self.transition_timer = 0

        # Update ongoing visual effects
        self._effects_update(dt)


    def get_current_color(self):
        """Returns the background color for the current weather."""
        # Base color remains the same, effects are overlays
        return self.colors.get(self.current_state, (0, 0, 0)) # Default to black

    def _effects_update(self, dt):
        """Updates the state of ongoing effects like rain."""
        if self.current_state == "Rainy":
            # Add new raindrops if below max
            num_to_add = max(0, self.max_raindrops - len(self.raindrops))
            for _ in range(min(num_to_add, 5)): # Add up to 5 new drops per frame, respecting max
                x = random.randint(0, self.screen_width)
                y = random.randint(-self.screen_height // 2, 0) # Start off-screen top
                self.raindrops.append([x, y])

            # Move raindrops
            rain_speed = 300 * dt # Pixels per second
            new_drops = []
            for drop in self.raindrops:
                drop[1] += rain_speed
                if drop[1] < self.screen_height: # Keep drops within screen height
                    new_drops.append(drop)
            self.raindrops = new_drops
        else:
            self.raindrops = [] # Clear raindrops if not raining

        if self.current_state == "Snowy":
            # Add new snowflakes if below max
            num_to_add = max(0, self.max_snowflakes - len(self.snowflakes))
            for _ in range(min(num_to_add, 2)): # Add up to 2 new flakes per frame, respecting max
                x = random.randint(0, self.screen_width)
                y = random.randint(-self.screen_height // 4, 0) # Start off-screen top
                size = random.randint(2, 5) # Varying snowflake sizes
                self.snowflakes.append([x, y, size])

            # Move snowflakes (slower than rain, with drift)
            snow_speed = 80 * dt # Pixels per second (slower)
            drift_speed = 20 * dt
            new_flakes = []
            for flake in self.snowflakes:
                flake[1] += snow_speed
                flake[0] += random.uniform(-drift_speed, drift_speed) # Horizontal drift
                # Wrap around horizontally if needed
                if flake[0] < 0: flake[0] = self.screen_width
                if flake[0] > self.screen_width: flake[0] = 0

                if flake[1] < self.screen_height: # Keep flakes within screen height
                    new_flakes.append(flake)
            self.snowflakes = new_flakes
        else:
            self.snowflakes = [] # Clear snowflakes if not snowy


    def draw_effects(self, screen):
        """Draws weather effects like rain, snow, or screen tints, and transition effects."""
        if self.current_state == "Sunny":
             # Subtle yellow tint for brightness
            tint = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            tint.fill((255, 255, 0, 10)) # Very subtle yellow overlay
            screen.blit(tint, (0,0))
        elif self.current_state == "Cloudy":
             # Subtle gray tint
            tint = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            tint.fill((100, 100, 100, 15)) # Subtle gray overlay
            screen.blit(tint, (0,0))
        elif self.current_state == "Rainy":
            # Draw raindrops
            rain_color = (173, 216, 230) # Light blue
            for drop in self.raindrops:
                start_pos = (int(drop[0]), int(drop[1]))
                end_pos = (int(drop[0]), int(drop[1] + 5)) # Short line for drop
                pygame.draw.line(screen, rain_color, start_pos, end_pos, 1)

            # Darker tint for rain
            tint = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            tint.fill((50, 50, 70, 40)) # Darker blue/gray overlay
            screen.blit(tint, (0,0))
        elif self.current_state == "Snowy":
            # Draw snowflakes
            snow_color = (255, 255, 255) # White
            for flake in self.snowflakes:
                # Draw simple circles for snowflakes
                pygame.draw.circle(screen, snow_color, (int(flake[0]), int(flake[1])), flake[2])

            # Keep the whitish tint
            tint = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            tint.fill((200, 200, 220, 20)) # Semi-transparent white overlay
            screen.blit(tint, (0,0))

        # Draw transition effect (if active) - overlay on top
        if self.is_transitioning:
            # Simple fade to white and back effect
            progress = (self.transition_duration - self.transition_timer) / self.transition_duration
            # Alpha goes from 0 -> 128 -> 0
            alpha = int(128 * (1 - abs(2 * progress - 1)))
            flash_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            flash_surface.fill((255, 255, 255, alpha)) # White flash
            screen.blit(flash_surface, (0, 0))