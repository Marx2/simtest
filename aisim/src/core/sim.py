import pygame
import random
import math
import uuid
from ai.ollama_client import OllamaClient # Assuming correct path

# Constants
SIM_COLOR = (255, 255, 255)  # White
SIM_RADIUS = 5
MOVE_SPEED = 50  # Pixels per second
INTERACTION_DISTANCE = 20 # Max distance for interaction (pixels)
THOUGHT_DURATION = 5.0 # Seconds to display thought bubble
THOUGHT_COLOR = (240, 240, 240) # Light grey for thought text
THOUGHT_BG_COLOR = (50, 50, 50, 180) # Semi-transparent dark background

# Initialize font - needs pygame.init() called first, handle in main
pygame.font.init() # Ensure font module is initialized
SIM_FONT = pygame.font.SysFont(None, 18) # Default system font, size 18

class Sim:
    """Represents a single Sim in the simulation."""
    def __init__(self, sim_id, x, y, ollama_client: OllamaClient):
        """Initializes a Sim with ID, position, and Ollama client."""
        self.sim_id = sim_id  # Store the unique ID
        self.x = x
        self.y = y
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)) # Random color for now
        self.path = None
        self.path_index = 0
        self.target = None
        # Basic AI attributes
        self.personality = {
            "outgoing": random.uniform(0.0, 1.0), # Example trait (0=shy, 1=very outgoing)
            # TODO: Add more traits (e.g., agreeable, conscientious)
        }
        self.memory = [] # List to store significant events or interactions
        self.ollama_client = ollama_client
        self.current_thought = None
        self.thought_timer = 0.0
        self.relationships = {} # Key: other_sim_id, Value: {"friendship": float, "romance": float}
        self.mood = 0.0 # -1.0 (Sad) to 1.0 (Happy)

    def update(self, dt, city, weather_state, all_sims): # Pass all sims for interaction checks
        """Updates the Sim's state, following a path if available."""
        if not self.path:
            self._find_new_path(city)
            if not self.path: # Still no path (e.g., couldn't find one)
                return # Wait until next update to try again

        # Follow the current path
        if self.path and self.path_index < len(self.path):
            target_x, target_y = self.path[self.path_index]
            dx = target_x - self.x
            dy = target_y - self.y
            distance = math.sqrt(dx**2 + dy**2)

            if distance < SIM_RADIUS: # Reached waypoint
                self.path_index += 1
                if self.path_index >= len(self.path): # Reached final destination
                    self.path = None
                    self.target = None
                    self.path_index = 0
                    # Generate thought upon arrival
                    situation = f"arrived at location ({int(self.x)}, {int(self.y)}) on a {weather_state} day"
                    self._generate_thought(situation)
                    self.mood = min(1.0, self.mood + 0.1) # Mood boost for reaching destination
            else: # Move towards waypoint
                # Normalize direction vector
                norm_dx = dx / distance
                norm_dy = dy / distance
                # Move
                self.x += norm_dx * MOVE_SPEED * dt
                self.y += norm_dy * MOVE_SPEED * dt

        # Update thought timer
        if self.current_thought:
            self.thought_timer -= dt
            if self.thought_timer <= 0:
                self.current_thought = None
        else:
             # Path finished or invalid state, try finding a new one next update
             self.path = None
             self.target = None
             self.path_index = 0

        # --- Mood Update based on Weather ---
        if weather_state in ["Rainy", "Snowy"]:
            self.mood = max(-1.0, self.mood - 0.005 * dt) # Slowly decrease mood in bad weather
        elif weather_state == "Sunny":
             self.mood = min(1.0, self.mood + 0.003 * dt) # Slowly increase mood in good weather

        # --- Interaction Check ---
        self._check_interactions(all_sims)

        # Clamp mood
        self.mood = max(-1.0, min(self.mood, 1.0))

    def _generate_thought(self, situation_description):
        """Generates and stores a thought using Ollama."""
        # print(f"Sim generating thought for: {situation_description}") # Optional log
        thought_text = self.ollama_client.generate_thought(situation_description)
        if thought_text:
            self.current_thought = thought_text
            self.thought_timer = THOUGHT_DURATION
            self.memory.append({"type": "thought", "content": thought_text, "situation": situation_description})
            # print(f"Sim thought: {self.current_thought}") # Optional log
        else:
            self.current_thought = None # Ensure it's cleared if generation fails

    def _find_new_path(self, city):
        """Finds a path to a new random destination within the city."""
        # Pick a random destination tile
        dest_col = random.randint(0, city.grid_width - 1)
        dest_row = random.randint(0, city.grid_height - 1)
        self.target = city.get_coords_from_node((dest_col, dest_row))

        if self.target:
            # print(f"Sim at ({self.x:.1f}, {self.y:.1f}) finding path to {self.target}") # Optional log
            new_path = city.get_path((self.x, self.y), self.target)
            if new_path and len(new_path) > 1: # Ensure path has more than just the start node
                self.path = new_path
                self.path_index = 1 # Start moving towards the second node in the path
                # print(f"Path found: {len(self.path)} steps") # Optional log
            else:
                # print("Path not found or too short.") # Optional log
                self.path = None
                self.target = None
                self.path_index = 0
        else:
             # print("Could not determine target coordinates.") # Optional log
             self.path = None
             self.target = None
             self.path_index = 0

    def _check_interactions(self, all_sims):
        """Checks for and handles interactions with nearby Sims."""
        for other_sim in all_sims:
            if other_sim.sim_id == self.sim_id:
                continue # Don't interact with self

            dist = math.dist((self.x, self.y), (other_sim.x, other_sim.y))

            if dist < INTERACTION_DISTANCE:
                # TODO: Add cooldown to prevent constant interaction spam
                # TODO: Use personality traits to influence interaction chance/outcome
                # TODO: Add cooldown to prevent constant interaction spam

                # Initialize relationship if first meeting
                if other_sim.sim_id not in self.relationships:
                    self.relationships[other_sim.sim_id] = {"friendship": 0.0, "romance": 0.0}
                if self.sim_id not in other_sim.relationships:
                    other_sim.relationships[self.sim_id] = {"friendship": 0.0, "romance": 0.0}

                # Basic interaction effect: slightly increase friendship
                friendship_increase = 0.01 # Placeholder
                self.relationships[other_sim.sim_id]["friendship"] = min(1.0, self.relationships[other_sim.sim_id]["friendship"] + friendship_increase)
                other_sim.relationships[self.sim_id]["friendship"] = min(1.0, other_sim.relationships[self.sim_id]["friendship"] + friendship_increase)

                # Generate thoughts about the interaction
                situation_self = f"just met Sim {other_sim.sim_id[:4]}..." # Use short ID for prompt
                situation_other = f"just met Sim {self.sim_id[:4]}..."
                self._generate_thought(situation_self)
                # Note: This might trigger thoughts simultaneously, potentially overwriting quickly.
                # A more robust system might queue thoughts or handle conversations.
                other_sim._generate_thought(situation_other)

                # Store interaction in memory
                interaction_event = {"type": "interaction", "with_sim_id": other_sim.sim_id, "friendship_change": friendship_increase}
                self.memory.append(interaction_event)
                other_sim.memory.append({"type": "interaction", "with_sim_id": self.sim_id, "friendship_change": friendship_increase})

                # Mood boost from positive interaction
                self.mood = min(1.0, self.mood + 0.05)
                other_sim.mood = min(1.0, other_sim.mood + 0.05)


    def draw(self, screen):
        """Draws the Sim and its current thought on the screen."""
        # Draw Sim body - color influenced by mood
        # Lerp between blue (sad) -> white (neutral) -> yellow (happy)
        base_color = self.color # Keep original random color base
        mood_color = (0,0,0)
        if self.mood < 0: # Sad range (Blue tint)
            lerp_t = abs(self.mood) # 0 to 1
            mood_color = (
                int(base_color[0] * (1 - lerp_t) + 0 * lerp_t), # Less Red
                int(base_color[1] * (1 - lerp_t) + 0 * lerp_t), # Less Green
                int(base_color[2] * (1 - lerp_t) + 255 * lerp_t) # More Blue
            )
        else: # Happy range (Yellow tint)
            lerp_t = self.mood # 0 to 1
            mood_color = (
                int(base_color[0] * (1 - lerp_t) + 255 * lerp_t), # More Red
                int(base_color[1] * (1 - lerp_t) + 255 * lerp_t), # More Green
                int(base_color[2] * (1 - lerp_t) + 0 * lerp_t)   # Less Blue
            )
        # Clamp colors
        mood_color = tuple(max(0, min(c, 255)) for c in mood_color)

        sim_pos = (int(self.x), int(self.y))
        pygame.draw.circle(screen, mood_color, sim_pos, SIM_RADIUS)

        # Draw thought bubble if active
        if self.current_thought:
            thought_surface = SIM_FONT.render(self.current_thought, True, THOUGHT_COLOR)
            thought_rect = thought_surface.get_rect()

            # Position above the Sim
            bubble_padding = 5
            bubble_rect = pygame.Rect(
                sim_pos[0] - thought_rect.width / 2 - bubble_padding,
                sim_pos[1] - SIM_RADIUS - thought_rect.height - bubble_padding * 2,
                thought_rect.width + bubble_padding * 2,
                thought_rect.height + bubble_padding * 2
            )

            # Draw background bubble
            pygame.draw.rect(screen, THOUGHT_BG_COLOR, bubble_rect, border_radius=5)
            # Draw text
            screen.blit(thought_surface, (bubble_rect.x + bubble_padding, bubble_rect.y + bubble_padding))