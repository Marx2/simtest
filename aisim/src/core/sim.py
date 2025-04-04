import pygame
import random
import math
import uuid
import textwrap
import os
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.interaction import check_interactions
from aisim.src.core.city import TILE_SIZE  # Import TILE_SIZE constant
from aisim.src.core.movement import get_coords_from_node, get_path, get_node_from_coords
from aisim.src.core.movement import update as movement_update

# Common first and last names for Sims
FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer",
               "Michael", "Linda", "William", "Elizabeth", "David", "Barbara",
               "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller",
             "Davis", "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson",
             "Taylor", "Thomas", "Hernandez", "Moore", "Martin", "Jackson"]


def wrap_text(text, font, max_width):
    """Helper function to wrap text to fit within a specified width."""
    words = text.split(' ')
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        if font.size(test_line)[0] <= max_width:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]

    if current_line:
        lines.append(' '.join(current_line))
    return lines


# Constants
SIM_COLOR = (255, 255, 255)  # White (fallback)
SPRITE_WIDTH = 32  # Based on tile size
SPRITE_HEIGHT = 32
INTERACTION_DISTANCE = 20  # Max distance for interaction (pixels)
THOUGHT_DURATION = 5.0  # Seconds to display thought bubble
THOUGHT_COLOR = (240, 240, 240)  # Light grey for thought text
THOUGHT_BG_COLOR = (50, 50, 50, 180)  # Semi-transparent dark background
SIM_RADIUS = 5  # REMOVED

# Initialize font - needs pygame.init() - Ensure font module is initialized
pygame.font.init()
SIM_FONT = pygame.font.SysFont(None, 18)  # Default system font, size 18


class Sim:
    """Represents a single Sim in the simulation."""

    def __init__(self, sim_id, x, y, ollama_client: OllamaClient, enable_talking: bool):
        """Initializes a Sim with ID, position, and Ollama client."""
        self.sim_id = sim_id  # Store the unique ID
        self.is_interacting = False
        self.interaction_timer = 0.0
        self.talking_with = None # sim_id of the sim they are talking to
        self.sprite_sheet = None
        self._load_sprite_sheet()
        self.current_direction = 'front'
        self.previous_direction = 'front'
        self.previous_angle = 0.0
        self.first_name = random.choice(FIRST_NAMES)
        self.last_name = random.choice(LAST_NAMES)
        self.full_name = f"{self.first_name} {self.last_name}"
        self.x = x
        self.y = y
        self.speed = random.uniform(30, 70)  # Random speed for each sim
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))  # Fallback color
        # self.sprite = self._load_sprite() # Load character sprite
        self.path = None
        self.path_index = 0
        self.target = None
        # Basic AI attributes
        self.personality = {
            "outgoing": random.uniform(0.0, 1.0)  # Example trait (0=shy, 1=very outgoing)
        }
        self.memory = []  # List to store significant events or interactions
        self.ollama_client = ollama_client
        self.current_thought = None
        self.thought_timer = 0.0
        self.relationships = {}  # Key: other_sim_id, Value: {"friendship": float, "romance": float}
        self.mood = 0.0  # -1.0 (Sad) to 1.0 (Happy)
        self.last_interaction_time = 0.0  # Time of last interaction
        self.enable_talking = enable_talking
        self.can_talk = False  # Flag to control thought generation
        # Animation attributes
        self.animation_frame = 0
        self.animation_timer = 0.0
        self.animation_speed = 0.15 # Time between frames in seconds
    # REMOVED DUPLICATE _load_sprite method
    def update(self, dt, city, weather_state, all_sims, logger, current_time, tile_size, direction_change_frequency): # Add tile_size
        """Updates the Sim's state, following a path if available, and logs data."""
        # print(f"Sim {self.sim_id}: update called at start, x={self.x:.2f}, y={self.y:.2f}, target={self.target}, is_interacting={self.is_interacting}, path={self.path}")
        # Call the movement update method
        movement_update(self, dt, city, weather_state, all_sims, logger, current_time, tile_size, direction_change_frequency)
        self.update_animation(dt) # Update animation frame
        if hasattr(self, 'last_update_time') and self.last_update_time == current_time:
            return
        self.last_update_time = current_time
        # print(f"Sim {self.sim_id}: update called at start, is_interacting={self.is_interacting}, interaction_timer={self.interaction_timer}, path={self.path}, target={self.target}, is_interacting={self.is_interacting}")
        if self.is_interacting:
            self.interaction_timer += dt
            # print(f"Sim {self.sim_id}: is_interacting=True, interaction_timer={self.interaction_timer}")
            # print(f"Sim {self.sim_id}: is_interacting=True, interaction_timer={self.interaction_timer}")
            if self.interaction_timer > random.uniform(3, 20):
                self.is_interacting = False
                self.talking_with = None
                # print(f"Sim {self.sim_id}: interaction timer expired, is_interacting set to False")
                return

        # if logger:
        #     print(f"Sim {self.sim_id} update: x={self.x:.2f}, y={self.y:.2f}, target={self.target}, is_interacting={self.is_interacting}")
        if not self.is_interacting:
            if not self.path:
                self.path = get_path((self.x, self.y), (random.randint(0, city.width), random.randint(0, city.height)), city.graph, get_node_from_coords, get_coords_from_node, city.width, city.height)
            if not self.path:  # Still no path (e.g., couldn't find one)
                return

        # Update thought timer
        if self.current_thought:
            self.thought_timer -= dt
            if self.thought_timer <= 0:
                self.current_thought = None
        # Removed redundant path reset logic that was causing Sims to stop

        # --- Mood Update based on Weather ---
        if weather_state in ["Rainy", "Snowy"]:
            self.mood = max(-1.0, self.mood - 0.005 * dt)  # Slowly decrease mood in bad weather
        elif weather_state == "Sunny":
            self.mood = min(1.0, self.mood + 0.003 * dt)  # Slowly increase mood in good weather

        # --- Interaction Check ---
        check_interactions(self, all_sims, logger, current_time)

        # Clamp mood
        self.mood = max(-1.0, min(self.mood, 1.0))

        # --- Log Mood ---
        if logger:
            logger.log_mood(current_time, self.sim_id, self.mood)

    def _generate_thought(self, situation_description):
        """Generates and stores a thought using Ollama."""
        # print(f"Sim generating thought for: {situation_description}") # Optional log
        if (self.enable_talking and self.can_talk):
            thought_text = self.ollama_client.generate_thought(situation_description)
            if thought_text:
                self.current_thought = thought_text
                self.thought_timer = THOUGHT_DURATION
            print(f"Sim {self.sim_id}: Attempting to generate thought, enable_talking={self.enable_talking}, can_talk={self.can_talk}")
            thought_text = self.ollama_client.generate_thought(situation_description)
            if thought_text:
                self.current_thought = thought_text
                self.thought_timer = THOUGHT_DURATION
            else:
                print(f"Sim {self.sim_id} failed to generate thought for: {situation_description}")
        else:
            print(f"Sim {self.sim_id} talking blocked")

    def update_animation(self, dt):
        """Updates the animation frame based on elapsed time."""
        self.animation_timer += dt
        if self.animation_timer >= self.animation_speed:
            self.animation_timer -= self.animation_speed
            self.animation_frame = (self.animation_frame + 1) % 3 # Cycle through 3 columns (0, 1, 2)

    def _get_sprite(self):
        """Returns the appropriate sub-sprite based on the direction and animation frame."""
        if not self.sprite_sheet:
            return None

        # Define the dimensions of each sub-sprite
        width = SPRITE_WIDTH
        height = SPRITE_HEIGHT

        # Determine row based on direction (0-based index)
        # Row 0: down (Task desc: Row 1)
        # Row 1: left (Task desc: Row 2)
        # Row 2: right (Task desc: Row 3)
        # Row 3: up (Task desc: Row 4)
        if self.current_direction == 'down':
            row = 0
        elif self.current_direction == 'left':
            row = 1
        elif self.current_direction == 'right':
            row = 2
        elif self.current_direction == 'up':
            row = 3
        else: # Default/idle (e.g., 'front') - use 'down' row, middle frame
            row = 0
            self.animation_frame = 1 # Use middle frame when idle/front

        # Use the current animation frame for the column
        col = self.animation_frame

        # Calculate the position of the sub-sprite in the sprite sheet
        x = col * width
        y = row * height

        # Extract the sub-sprite
        sprite = pygame.Surface((width, height), pygame.SRCALPHA)
        sprite.blit(self.sprite_sheet, (0, 0), (x, y, width, height))

        return sprite


    def _load_sprite_sheet(self):
        """Loads the Sim's sprite sheet from a predefined path."""
        try:
            sprite_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'graphics', 'characters', 'Abigail_Chen.png')
            self.sprite_sheet = pygame.image.load(sprite_path).convert_alpha()
        except Exception as e:
            print(f"Error loading sprite sheet: {e}")
            self.sprite_sheet = None
        return self.sprite_sheet


    def draw(self, screen):
        """Draws the Sim and its current thought on the screen."""
        sim_pos = (int(self.x), int(self.y))

        # Get the sprite based on the current direction
        sprite = self._get_sprite() # Get sprite based on direction and animation frame

        # Draw Sim sprite or fallback circle
        if sprite:
            # Center the sprite on the sim's position
            sprite_rect = sprite.get_rect(center=sim_pos)
            screen.blit(sprite, sprite_rect)
        else:
            # Fallback: Draw mood-colored circle
            base_color = self.color  # Keep original random color base
            mood_color = (0, 0, 0)
            if self.mood < 0:  # Sad range (Blue tint)
                lerp_t = abs(self.mood)  # 0 to 1
                mood_color = (
                    int(base_color[0] * (1 - lerp_t) + 0 * lerp_t),  # Less Red
                    int(base_color[1] * (1 - lerp_t) + 0 * lerp_t),  # Less Green
                    int(base_color[2] * (1 - lerp_t) + 255 * lerp_t)  # More Blue
                )
            else:  # Happy range (Yellow tint)
                lerp_t = self.mood  # 0 to 1
                mood_color = (
                    int(base_color[0] * (1 - lerp_t) + 255 * lerp_t),  # More Red
                    int(base_color[1] * (1 - lerp_t) + 255 * lerp_t),  # More Green
                    int(base_color[2] * (1 - lerp_t) + 0 * lerp_t)   # Less Blue
                )
            # Clamp colors
            mood_color = tuple(max(0, min(c, 255)) for c in mood_color)
            pygame.draw.circle(screen, mood_color, sim_pos, SIM_RADIUS)

        # Draw thought bubble if active
        MAX_BUBBLE_WIDTH = 200  # Maximum width for thought bubbles
        bubble_padding = 5
        line_height = SIM_FONT.get_linesize()
        
        bubble_rect = pygame.Rect(0, 0, 0, 0) # Initialize bubble_rect

        if self.current_thought:
            wrapped_lines = wrap_text(self.current_thought, SIM_FONT, MAX_BUBBLE_WIDTH - 10)

            # Calculate total height needed
            total_height = len(wrapped_lines) * line_height
            
            # Find the widest line
            max_line_width = max(SIM_FONT.size(line)[0] for line in wrapped_lines)

            # Position above the Sim
            bubble_rect = pygame.Rect(
                sim_pos[0] - max_line_width / 2 - bubble_padding,
                sim_pos[1] - SPRITE_HEIGHT - total_height - bubble_padding * 2,
                max_line_width + bubble_padding * 2,
                total_height + bubble_padding * 2
            )

            # Draw background bubble
            pygame.draw.rect(screen, THOUGHT_BG_COLOR, bubble_rect, border_radius=5)

            # Draw each line of text
            y_offset = bubble_rect.y + bubble_padding
            for line in wrapped_lines:
                line_surface = SIM_FONT.render(line, True, THOUGHT_COLOR)
                screen.blit(line_surface, (bubble_rect.x + bubble_padding, y_offset))
                y_offset += line_height