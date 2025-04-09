import pygame
import random
import os
from typing import List, Dict, Optional
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.interaction import _send_conversation_request # Import the function
from aisim.src.core.interaction import check_interactions, _end_interaction
from aisim.src.core.movement import get_coords_from_node, get_path, get_node_from_coords, movement_update
from aisim.src.core.text import draw_bubble
from aisim.src.core.personality import _assign_sex, load_or_generate_personality_for_sim
from aisim.src.core.configuration import config_manager # Import the centralized config manager

TILE_SIZE = config_manager.get_entry('city.tile_size', 32) # Add default value
BUBBLE_DISPLAY_TIME = config_manager.get_entry('simulation.bubble_display_time_seconds', 5.0)

# Initialize font - needs pygame.init() - Ensure font module is initialized
pygame.font.init()
class Sim:
    """Represents a single Sim in the simulation."""

    def __init__(self, sim_id, x, y, ollama_client: OllamaClient, sim_config: Dict):
        """Initializes a Sim with ID, position, Ollama client, config, and bubble display time."""
        self.sim_id = sim_id  # Store the unique ID
        self.is_interacting = False
        self.talking_with = None # sim_id of the sim they are talking to
        self.sprite_sheet = None
        self.character_name, self.sprite_sheet = self._load_sprite_sheet()
        self.current_direction = 'front'
        self.previous_direction = 'front'
        self.previous_angle = 0.0
        self.first_name, self.last_name = self.character_name.split("_") if "_" in self.character_name else (self.character_name, "")
        self.full_name = self.character_name.replace("_", " ") # Use space for full name display
        self.sex = _assign_sex(self.first_name, sim_config) # Assign sex using imported function
        self.x = x
        self.y = y
        self.current_tile = None # Initialize current tile attribute
        self.speed = random.uniform(30, 70)  # Random speed for each sim
        self.sim_color = tuple(sim_config.get("sim_color", [255, 255, 255])) # Load from config, fallback white
        self.sprite_width = sim_config.get("sprite_width", 32)
        self.sprite_height = sim_config.get("sprite_height", 32)
        self.interaction_distance = sim_config.get("interaction_distance", 20)
        self.sim_radius = sim_config.get("sim_radius", 5)
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)) # Keep random visual color distinct from fallback
        self.path = None
        self.path_index = 0
        self.target = None
        self.ollama_client = ollama_client # Assign ollama_client earlier for use in personality gen
        self.personality = {}
        self.personality_description = "Personality not set."
        load_or_generate_personality_for_sim(self, sim_config)
        self.memory = []  # List to store significant events or interactions
        self.current_thought = None
        self.thought_timer = 0.0
        self.relationships = {}  # Key: other_sim_id, Value: {"friendship": float, "romance": float}
        self.mood = 0.0  # -1.0 (Sad) to 1.0 (Happy)
        self.last_interaction_time = 0.0  # Time of last interaction
        # Animation attributes
        self.animation_frame = 0
        self.animation_timer = 0.0
        self.animation_speed = 0.15 # Time between frames in seconds
        # Conversation attributes
        self.conversation_history: Optional[List[Dict[str, str]]] = None
        self.is_my_turn_to_speak: bool = False
        self.waiting_for_ollama_response: bool = False
        self.conversation_partner_id: Optional[any] = None # Store partner ID
        self.conversation_turns: int = 0
        self.conversation_last_response_time: float = 0.0
        self.conversation_message: Optional[str] = None # Separate attribute for conversation text
        self.conversation_message_timer: float = 0.0 # Timer for conversation bubble
    
    def sim_update(self, dt, city, weather_state, all_sims: List['Sim'], current_time, tile_size, direction_change_frequency): # Add tile_size and type hint
        """Updates the Sim's state, following a path if available, and logs data."""
        self.tile_size = tile_size
        self.is_blocked = False # Reset blocked status
        # print(f"Sim {self.sim_id}: update called at start, x={self.x:.2f}, y={self.y:.2f}, target={self.target}, is_interacting={self.is_interacting}, path={self.path}")
        # Call the movement update method
        movement_update(self, dt, city, weather_state, all_sims, current_time, tile_size, direction_change_frequency)
        self.animation_update(dt) # Update animation frame
        if hasattr(self, 'last_update_time') and self.last_update_time == current_time:
            return
        self.last_update_time = current_time
        # --- Conversation Logic ---
        if self.is_interacting:
            # Handle conversation updates in a separate method
            self.conversation_update(dt, city, all_sims, current_time)
            # If the conversation ended within update_conversation, is_interacting might be False now.
            # We might need to return early if _end_interaction was called inside update_conversation.
            # Let's check if the sim is still interacting after the call.
            if not self.is_interacting:
                 return # Interaction ended, stop further processing in update

        else:
            if not self.path:
                target_x = random.randint(0, city.grid_width - 1) * TILE_SIZE
                target_y = random.randint(0, city.grid_height - 1) * TILE_SIZE
                self.path = get_path((self.x, self.y), (target_x, target_y), city.graph, get_node_from_coords, get_coords_from_node, city.width, city.height)
            if not self.path:  # Still no path (e.g., couldn't find one)
                return

        # Update thought timer (for non-conversation thoughts)
        if self.current_thought:
            self.thought_timer -= dt
            if self.thought_timer <= 0:
                self.current_thought = None

        # --- Mood Update based on Weather ---
        if weather_state in ["Rainy", "Snowy"]:
            self.mood = max(-1.0, self.mood - 0.005 * dt)  # Slowly decrease mood in bad weather
        elif weather_state == "Sunny":
            self.mood = min(1.0, self.mood + 0.003 * dt)  # Slowly increase mood in good weather

        # --- Interaction Check ---
        # Pass the city object to check_interactions
        check_interactions(self, all_sims, current_time, city)

        # Clamp mood
        self.mood = max(-1.0, min(self.mood, 1.0))

    def conversation_update(self, dt, city, all_sims: List['Sim'], current_time):
        """Handles the logic for ongoing conversations."""
        # This method assumes self.is_interacting is True when called

        # Check for conversation timeout (if waiting too long for a response)
        # Note: Using self.ollama_client requires ollama_client to be passed or accessible
        if self.waiting_for_ollama_response and (current_time - self.conversation_last_response_time > self.ollama_client.conversation_response_timeout):
            print(f"Sim {self.sim_id}: Conversation with {self.conversation_partner_id} timed out.")
            _end_interaction(self, city, all_sims) # Assumes _end_interaction is accessible globally or imported
            return # Stop further processing within this method

        # Check for max turns reached
        # Note: Using self.ollama_client requires ollama_client to be passed or accessible
        if self.conversation_turns >= config_manager.get_entry('ollama.conversation_max_turns', 6):
             print(f"Sim {self.sim_id}: Conversation with {self.conversation_partner_id} reached max turns.")
             _end_interaction(self, city, all_sims) # Assumes _end_interaction is accessible
             return # Stop further processing within this method

        # --- Turn-Based Speaking Logic with Lock ---
        if self.is_my_turn_to_speak and not self.waiting_for_ollama_response:
            # print(f"Sim {self.sim_id}: My turn, attempting to speak. Lock state: {city.ollama_client_locked}")
            # Attempt to acquire the global Ollama lock
            if not city.ollama_client_locked:
                city.ollama_client_locked = True # Acquire lock
                print(f"Sim {self.sim_id}: Acquired Ollama lock. Preparing to send request.")

                partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
                if partner:
                    # Call the imported _send_conversation_request function
                    # Pass self as speaker, partner as listener
                    request_successful = _send_conversation_request(self, partner, current_time)

                    if not request_successful:
                        # Request failed (Ollama client error, etc.)
                        print(f"Sim {self.sim_id}: _send_conversation_request failed. Releasing lock.")
                        city.ollama_client_locked = False # Release the lock
                        # Consider ending interaction after multiple failures? For now, just log and release.
                        # Maybe add a failure counter later.
                        # _end_interaction(self, city, all_sims) # Don't end immediately, allow retry next cycle?
                else:
                    # Partner not found, end interaction and release lock
                    print(f"Sim {self.sim_id}: ERROR - Conversation partner {self.conversation_partner_id} not found during turn! Ending interaction.")
                    city.ollama_client_locked = False # Release the lock before ending
                    _end_interaction(self, city, all_sims)
                    return # Stop processing this conversation update

            # else:
                # Lock is busy, wait for the next cycle
                # print(f"Sim {self.sim_id}: Waiting for Ollama lock to become available.")
                # Do nothing this cycle, will retry on the next update


    def _find_sim_by_id(self, sim_id_to_find: any, all_sims: List['Sim']) -> Optional['Sim']:
        """Helper to find a Sim object by its ID."""
        for sim in all_sims:
            if sim.sim_id == sim_id_to_find:
                return sim
        return None

    def animation_update(self, dt):
        """Updates the animation frame based on elapsed time."""
        if not self.is_interacting:
            self.animation_timer += dt
            if self.animation_timer >= self.animation_speed:
                self.animation_timer -= self.animation_speed
                self.animation_frame = (self.animation_frame + 1) % 3 # Cycle through 3 columns (0, 1, 2)

    def _get_sprite(self):
        """Returns the appropriate sub-sprite based on the direction and animation frame."""
        if not self.sprite_sheet:
            return None

        # Define the dimensions of each sub-sprite
        width = self.sprite_width
        height = self.sprite_height

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
        else: # Default/idle (e.g., 'front') - use 'down' row
            row = 0

        # Use the current animation frame for the column
        col = self.animation_frame

        # Calculate the position of the sub-sprite in the sprite sheet
        x = col * width
        y = row * height

        # Extract the sub-sprite
        sprite = pygame.Surface((width, height), pygame.SRCALPHA)
        sprite.blit(self.sprite_sheet, (0, 0), (x, y, width, height))

        return sprite

    def get_portrait(self):
        """Returns the front-facing, non-animated portrait sprite."""
        if not self.sprite_sheet:
            return None

        width = self.sprite_width
        height = self.sprite_height
        row = 0  # Front-facing row
        col = 0  # First animation frame

        # Calculate the position of the sub-sprite in the sprite sheet
        x = col * width
        y = row * height

        # Extract the sub-sprite
        portrait = pygame.Surface((width, height), pygame.SRCALPHA)
        portrait.blit(self.sprite_sheet, (0, 0), (x, y, width, height))

        return portrait


    def _load_sprite_sheet(self):
       """Loads a random Sim's sprite sheet from the character sprites directory."""
       try:
           character_sprite_dir = config_manager.get_entry('sim.character_sprite_dir')
           if not character_sprite_dir or not os.path.isdir(character_sprite_dir):
               print(f"Error: Character sprite directory not found or not configured in Sim._load_sprite_sheet: {character_sprite_dir}")
               return "Unknown_Sim", None # Return default on error

           available_characters = [f for f in os.listdir(character_sprite_dir) if f.endswith('.png')]
           if not available_characters:
               print("No character sprites found in directory:", character_sprite_dir)
               return "Unknown_Sim", None # Return default name if no sprites found

           chosen_sprite = random.choice(available_characters)
           sprite_path = os.path.join(character_sprite_dir, chosen_sprite) # Use the loaded directory path
           sprite_sheet = pygame.image.load(sprite_path).convert_alpha()
           character_name = chosen_sprite[:-4]  # Remove ".png" extension
           return character_name, sprite_sheet
       except Exception as e:
           print(f"Error loading sprite sheet: {e}")
           return "Unknown_Sim", None # Return a default name if loading fails
    def draw(self, screen, dt, all_sims):
        """Draws the Sim and its current thought on the screen."""
        sim_pos = (int(self.x), int(self.y))

        # Get the sprite based on the current direction
        sprite = self._get_sprite() # Get sprite based on direction and animation frame

        # Draw Sim sprite or fallback circle
        if sprite:
            # Center the sprite on the sim's position
            screen.blit(sprite, (sim_pos[0] - self.sprite_width // 2, sim_pos[1] - self.sprite_height // 2))
        else:
            # Fallback: draw a colored circle
            pygame.draw.circle(screen, self.sim_color, sim_pos, self.sim_radius) # Use configured fallback color and radius

        # # --- Bubble Display Logic ---
        # Find partner if interacting
        if self.is_interacting:
            print(f"sim: {self.sim_id}, self.conversation_message_timer: {self.conversation_message_timer}, dt: {dt}, is_my_turn_to_speak: {self.is_my_turn_to_speak}, waiting_for_ollama_response: {self.waiting_for_ollama_response}")
            # set partner if not set yet
            if self.conversation_partner_id:
                partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
            else:
                partner = None
            # count down only if I have message to display
            if self.conversation_message and self.is_my_turn_to_speak:
                if self.conversation_message_timer <= 0:
                    # Reset conversation message and timer
                    self.conversation_message = None
                    bubble_text_to_display = None
                    self.is_my_turn_to_speak = False
                    partner.is_my_turn_to_speak = True # Set partner's turn to speak
                    partner.conversation_message_timer = BUBBLE_DISPLAY_TIME # Start bubble timer
                else:
                    # continue with existing message until timer passes
                    bubble_text_to_display = self.conversation_message
                    # Decrement conversation timer
                    self.conversation_message_timer -= dt
            else:
                # No message to display, set to None
                bubble_text_to_display = None

            # --- Draw Bubble if text is available ---
            # print(f"SIM {self.character_name} Drawing bubble: {bubble_text_to_display == True}")
            if bubble_text_to_display:
                # Call the unified draw_bubble function
                draw_bubble(screen, bubble_text_to_display, sim_pos, sim1=self, sim2=partner)


