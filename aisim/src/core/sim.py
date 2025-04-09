import pygame
import random
import math
import os
import json
from typing import List, Dict, Optional
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.interaction import check_interactions, _end_interaction
from aisim.src.core.movement import get_coords_from_node, get_path, get_node_from_coords, change_direction, movement_update
from aisim.src.core.text import draw_bubble
from aisim.src.core.personality import _assign_sex, _generate_personality, _format_personality_for_prompt
from aisim.src.core.configuration import config_manager # Import the centralized config manager

TILE_SIZE = config_manager.get_entry('city.tile_size', 32) # Add default value
PERSONALITIES_DIR = config_manager.get_entry('sim.personalities_path') # Directory to store personality files

# --- Load Attributes Data ---
ATTRIBUTES_DATA = {} # Default empty
ATTRIBUTES_FILE_PATH = config_manager.get_entry('sim.attributes_file_path')
if ATTRIBUTES_FILE_PATH:
    try:
        with open(ATTRIBUTES_FILE_PATH, 'r') as f:
            ATTRIBUTES_DATA = json.load(f)
    except FileNotFoundError:
        print(f"Error: Attributes file not found at {ATTRIBUTES_FILE_PATH}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {ATTRIBUTES_FILE_PATH}")
else:
    print("Warning: 'sim.attributes_file_path' not configured")

def get_character_names():
    """Extracts character names from sprite filenames in the specified directory."""
    names = []
    character_sprite_dir = config_manager.get_entry('sim.character_sprite_dir')
    if not character_sprite_dir or not os.path.isdir(character_sprite_dir):
        print(f"Error: Character sprite directory not found or not configured: {character_sprite_dir}")
        return []
    for filename in os.listdir(character_sprite_dir):
        if filename.endswith(".png"):
            name = filename[:-4]  # Remove ".png" extension
            names.append(name)
    return names

CHARACTER_NAMES = get_character_names()

# Initialize font - needs pygame.init() - Ensure font module is initialized
pygame.font.init()

# Personality generation moved to aisim.src.core.personality


class Sim:
    """Represents a single Sim in the simulation."""

    def __init__(self, sim_id, x, y, ollama_client: OllamaClient, enable_talking: bool, sim_config: Dict, bubble_display_time: float = 5.0):
        """Initializes a Sim with ID, position, Ollama client, config, and bubble display time."""
        self.sim_id = sim_id  # Store the unique ID
        self.is_interacting = False
        self.interaction_timer = 0.0
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
        # self.sprite = self._load_sprite() # Load character sprite
        self.path = None
        self.path_index = 0
        self.target = None
        # --- Personality (Load or Generate) ---
        self.ollama_client = ollama_client # Assign ollama_client earlier for use in personality gen
        self.personality = {}
        self.personality_description = "Personality not set."
        self._load_or_generate_personality(sim_config)
        # --- End Personality ---
        self.memory = []  # List to store significant events or interactions
        # self.ollama_client = ollama_client # Moved up
        self.current_thought = None
        self.thought_timer = 0.0
        self.relationships = {}  # Key: other_sim_id, Value: {"friendship": float, "romance": float}
        self.mood = 0.0  # -1.0 (Sad) to 1.0 (Happy)
        self.last_interaction_time = 0.0  # Time of last interaction
        self.enable_talking = enable_talking
        self.can_talk = False  # Flag to control thought generation (might be deprecated by conversation logic)
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
        self.bubble_display_time: float = bubble_display_time # Store configured bubble time
        self.conversation_message: Optional[str] = None # Separate attribute for conversation text
        self.conversation_message_timer: float = 0.0 # Timer for conversation bubble
    # REMOVED DUPLICATE _load_sprite method
    def sim_update(self, dt, city, weather_state, all_sims: List['Sim'], logger, current_time, tile_size, direction_change_frequency): # Add tile_size and type hint
        """Updates the Sim's state, following a path if available, and logs data."""
        self.tile_size = tile_size
        self.is_blocked = False # Reset blocked status
        # print(f"Sim {self.sim_id}: update called at start, x={self.x:.2f}, y={self.y:.2f}, target={self.target}, is_interacting={self.is_interacting}, path={self.path}")
        # Call the movement update method
        movement_update(self, dt, city, weather_state, all_sims, logger, current_time, tile_size, direction_change_frequency)
        self.animation_update(dt) # Update animation frame
        if hasattr(self, 'last_update_time') and self.last_update_time == current_time:
            return
        self.last_update_time = current_time
        # print(f"Sim {self.sim_id}: update called at start, is_interacting={self.is_interacting}, interaction_timer={self.interaction_timer}, path={self.path}, target={self.target}, is_interacting={self.is_interacting}")
        # --- Conversation Logic ---
        if self.is_interacting:
            # Handle conversation updates in a separate method
            self.conversation_update(dt, city, all_sims, current_time)
            # If the conversation ended within update_conversation, is_interacting might be False now.
            # We might need to return early if _end_interaction was called inside update_conversation.
            # Let's check if the sim is still interacting after the call.
            if not self.is_interacting:
                 return # Interaction ended, stop further processing in update

        # if logger:
        #     print(f"Sim {self.sim_id} update: x={self.x:.2f}, y={self.y:.2f}, target={self.target}, is_interacting={self.is_interacting}")
        if not self.is_interacting:
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
        check_interactions(self, all_sims, logger, current_time, city)

        # Clamp mood
        self.mood = max(-1.0, min(self.mood, 1.0))

        # --- Log Mood ---
        if logger:
            logger.log_mood(current_time, self.sim_id, self.mood)
    def conversation_update(self, dt, city, all_sims: List['Sim'], current_time):
        """Handles the logic for ongoing conversations."""
        # This method assumes self.is_interacting is True when called

        self.interaction_timer += dt # Keep track of total interaction time if needed

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

        # If it's my turn and I'm not waiting for a response, request one
        if self.is_my_turn_to_speak and not self.waiting_for_ollama_response:
            print(f"Sim {self.sim_id}: It's my turn to speak. conversation_turns={self.conversation_turns}, waiting_for_ollama_response={self.waiting_for_ollama_response}")
            partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
            if partner:
                print(f"Sim {self.sim_id}: Requesting conversation response (Turn {self.conversation_turns}). History: {self.conversation_history}")
                # Get the romance level towards the partner
                relationship_data = self.relationships.get(self.conversation_partner_id, {}) # Default to empty dict if no relationship entry
                romance_level = relationship_data.get("romance", 0.0) # Default to 0.0 if 'romance' key missing
                print(f"Sim {self.sim_id}: Romance level towards {partner.first_name} ({self.conversation_partner_id}) = {romance_level:.2f}") # Debug log

                # Note: Using self.ollama_client requires ollama_client to be passed or accessible
                request_sent = self.ollama_client.request_conversation_response(
                    self.sim_id,
                    self.first_name,
                    partner.first_name,
                    self.conversation_history,
                    self.personality_description, # Pass pre-calculated description string
                    romance_level # Pass the calculated romance level
                )
                if request_sent:
                    self.waiting_for_ollama_response = True
                    self.conversation_last_response_time = current_time # Reset timeout timer
                else:
                    print(f"Sim {self.sim_id}: Failed to send conversation request (maybe Ollama busy?).")
                    # Optionally handle failure, e.g., end interaction after a few failed attempts
            else:
                 print(f"Sim {self.sim_id}: ERROR - Conversation partner {self.conversation_partner_id} not found!")
                 _end_interaction(self, city, all_sims) # Assumes _end_interaction is accessible
                 return # Stop further processing within this method


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

        # Draw conversation or thought bubble using the imported function
        bubble_text = None
        bubble_text = None
        is_conversation = False # Flag to track bubble type
        if self.conversation_message:
            # Decrement timer only when message exists
            self.conversation_message_timer -= dt # Use delta time for consistent display
            if self.conversation_message_timer > 0: # Check if timer still positive
                 bubble_text = self.conversation_message
                 is_conversation = True # It's a conversation bubble
            else:
                 self.conversation_message = None # Clear message after time
                 self.conversation_message_timer = 0.0 # Reset timer
        elif self.current_thought:
             # Handle non-conversation thought display timer (if needed, or remove if thoughts are transient)
             # Assuming current_thought display is handled by its own timer logic elsewhere
             bubble_text = self.current_thought
             # Keep is_conversation as False

        if bubble_text: # Check if timer > 0 removed as it's handled above
            # --- Determine arguments for draw_bubble ---
            sim1_arg = self
            sim2_arg = None
            partner = None # Initialize partner

            if is_conversation and self.conversation_partner_id:
                partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
                if partner:
                    sim2_arg = partner # Set partner as sim2 for romance check

            # --- Handle Overlapping Bubbles (if still needed, based on partner found) ---
            bubble_pos = sim_pos # Start with original position
            if is_conversation and partner and partner.conversation_message: # Check if partner *also* has a message
                distance = self.x - partner.x
                # Use config or a constant for bubble width if needed for overlap check
                bubble_width_estimate = 150
                if abs(distance) < bubble_width_estimate:
                    # Alternate bubble position based on relative position or ID
                    # Let's try moving *this* bubble slightly if partner is to the left
                    if partner.x < self.x:
                         bubble_pos = (sim_pos[0] + bubble_width_estimate // 4, sim_pos[1])
                    else:
                         bubble_pos = (sim_pos[0] - bubble_width_estimate // 4, sim_pos[1])
                    # More sophisticated overlap avoidance might be needed

            # --- Call draw_bubble with Sim arguments ---
            draw_bubble(screen, bubble_text, bubble_pos, sim1=sim1_arg, sim2=sim2_arg)


    def _load_or_generate_personality(self, sim_config: Dict):
        """Loads personality from file if exists, otherwise generates and saves it."""
        os.makedirs(PERSONALITIES_DIR, exist_ok=True) # Ensure directory exists
        personality_file = os.path.join(PERSONALITIES_DIR, f"{self.character_name}.json")

        if os.path.exists(personality_file):
            try:
                with open(personality_file, 'r') as f:
                    data = json.load(f)
                self.personality = data.get("personality", {}) # Load structured data
                self.personality_description = data.get("personality_description", "Error: Description missing in file.") # Load description
                print(f"Loaded personality for {self.full_name} from {personality_file}")
            except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                print(f"Error loading personality for {self.full_name} from {personality_file}: {e}. Regenerating.")
                # Fallback to generation if loading fails
                self.personality = _generate_personality(ATTRIBUTES_DATA, sim_config.get("personality", {}))
                self.personality_description = self.ollama_client.calculate_personality_description(self.personality, self.sex)
                self._save_personality(personality_file) # Attempt to save the newly generated data
        else:
            print(f"Personality file not found for {self.full_name}. Generating...")
            # Generate personality (structured)
            self.personality = _generate_personality(ATTRIBUTES_DATA, sim_config.get("personality", {}))
            # Generate description (via Ollama)
            self.personality_description = self.ollama_client.calculate_personality_description(self.personality, self.sex)
            # Save to file
            self._save_personality(personality_file)

    def _save_personality(self, file_path):
        """Saves the current personality and description to a JSON file."""
        data_to_save = {
            "personality": self.personality,
            "personality_description": self.personality_description
        }
        try:
            # Ensure directory exists just before writing (redundant if called after _load_or_generate_personality, but safe)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Saved personality for {self.full_name} to {file_path}")
        except IOError as e:
            print(f"Error saving personality for {self.full_name} to {file_path}: {e}")
