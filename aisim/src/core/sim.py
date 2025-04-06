import pygame
import random
import math
import uuid
import textwrap
import os
import json # Added for personality attributes
from typing import List, Dict, Optional # Add typing
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.interaction import check_interactions
from aisim.src.core.city import TILE_SIZE  # Import TILE_SIZE constant
from aisim.src.core.movement import get_coords_from_node, get_path, get_node_from_coords, change_direction
from aisim.src.core.movement import update as movement_update

import os

# Define the directory containing character sprites
CHARACTER_SPRITE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'graphics', 'characters')

def get_character_names():
    """Extracts character names from sprite filenames in the specified directory."""
    names = []
    for filename in os.listdir(CHARACTER_SPRITE_DIR):
        if filename.endswith(".png"):
            name = filename[:-4]  # Remove ".png" extension
            names.append(name)
    return names

CHARACTER_NAMES = get_character_names()


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

# --- Personality Generation Setup ---
ATTRIBUTES_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'attributes.json')
try:
    with open(ATTRIBUTES_FILE_PATH, 'r') as f:
        ATTRIBUTES_DATA = json.load(f)
except FileNotFoundError:
    print(f"Error: Attributes file not found at {ATTRIBUTES_FILE_PATH}")
    ATTRIBUTES_DATA = {} # Default to empty if file not found
except json.JSONDecodeError:
    print(f"Error: Could not decode JSON from {ATTRIBUTES_FILE_PATH}")
    ATTRIBUTES_DATA = {}

# Simple list for sex assignment heuristic
FEMALE_NAMES = {"Ayesha", "Carmen", "Hailey", "Isabella", "Jane", "Jennifer", "Latoya", "Maria", "Mei", "Tamara", "Yuriko", "Abigail"}

def _assign_sex(first_name):
    """Assigns sex based on a simple heuristic using common female names."""
    return "Female" if first_name in FEMALE_NAMES else "Male"

def _generate_personality(attributes_data):
    """Generates a random personality dictionary based on loaded attributes."""
    if not attributes_data:
        return {} # Return empty if attributes couldn't be loaded

    personality = {}
    num_traits = 3
    num_hobbies = 3
    num_quirks = 2

    # Personality Traits (Mix positive/negative)
    positive_traits = attributes_data.get("personality_traits", {}).get("positive", [])
    negative_traits = attributes_data.get("personality_traits", {}).get("negative", [])
    all_traits = positive_traits + negative_traits
    if all_traits:
        personality["personality_traits"] = random.sample(all_traits, k=min(num_traits, len(all_traits)))

    # Motivation
    motivations = attributes_data.get("life_motivations", [])
    if motivations: personality["motivation"] = random.choice(motivations)

    # Hobbies
    hobbies_list = attributes_data.get("hobbies", [])
    if hobbies_list: personality["hobbies"] = random.sample(hobbies_list, k=min(num_hobbies, len(hobbies_list)))

    # Emotional Profile
    emo_profile = {}
    emo_attrs = attributes_data.get("emotional_profile", {})
    level_to_num = {"Low": random.randint(0, 33), "Moderate": random.randint(34, 66), "High": random.randint(67, 100)}
    key_map_emo = {
        "anxiety_level": "anxiety",
        "impulse_control": "impulse_control",
        "social_energy": "social_energy"
        # Add mappings for other desired emotional keys from attributes.json if needed
    }
    num_keys_emo = ["anxiety", "impulse_control"] # Keys to convert to numbers

    for json_key, output_key in key_map_emo.items():
        options = emo_attrs.get(json_key, [])
        if options:
            chosen_value = random.choice(options)
            if output_key in num_keys_emo and chosen_value in level_to_num:
                 emo_profile[output_key] = level_to_num[chosen_value]
            else:
                 emo_profile[output_key] = chosen_value
    if emo_profile: personality["emotional_profile"] = emo_profile

    # Romantic Profile
    rom_profile = {}
    rom_attrs = attributes_data.get("romantic_profile", {})
    key_map_rom = {
        "sexual_orientation": "orientation",
        "libido": "libido",
        "kinkiness": "kinkiness",
        "relationship_goal": "relationship_goal"
    }
    for json_key, output_key in key_map_rom.items():
        options = rom_attrs.get(json_key, [])
        if options: rom_profile[output_key] = random.choice(options)
    if rom_profile: personality["romantic_profile"] = rom_profile

    # Cultural Background
    cult_profile = {}
    cult_attrs = attributes_data.get("cultural_background", {})
    key_map_cult = {
        "ethnicity": "ethnicity",
        "socioeconomic_status": "socioeconomic_status",
        "education_level": "education"
    }
    for json_key, output_key in key_map_cult.items():
        options = cult_attrs.get(json_key, [])
        if options: cult_profile[output_key] = random.choice(options)
    if cult_profile: personality["cultural_background"] = cult_profile

    # Career Style
    career_styles = attributes_data.get("career_style", [])
    if career_styles: personality["career_style"] = random.choice(career_styles)

    # Lifestyle Habits
    life_profile = {}
    life_attrs = attributes_data.get("lifestyle_habits", {})
    key_map_life = {
        "sleep_schedule": "sleep_schedule",
        "cleanliness": "cleanliness",
        "health_focus": "health_focus"
    }
    for json_key, output_key in key_map_life.items():
        options = life_attrs.get(json_key, [])
        if options: life_profile[output_key] = random.choice(options)
    if life_profile: personality["lifestyle_habits"] = life_profile

    # Quirks
    quirks_list = attributes_data.get("quirks_and_flaws", [])
    if quirks_list: personality["quirks"] = random.sample(quirks_list, k=min(num_quirks, len(quirks_list)))

    return personality

def _format_personality_for_prompt(personality: Dict, sex: str) -> str:
    """Formats the personality dictionary into a readable string for the LLM prompt."""
    # ... (Insert the _format_personality_for_prompt function code here) ...
    if not personality:
        return "No specific personality details available."

    lines = [f"Your Sex: {sex}"] # Add sex at the beginning
    lines.append("Your Personality:")
    if traits := personality.get("personality_traits"):
        lines.append(f"- Traits: {', '.join(traits)}")
    if motivation := personality.get("motivation"):
        lines.append(f"- Motivation: {motivation}")
    if hobbies := personality.get("hobbies"):
        lines.append(f"- Hobbies: {', '.join(hobbies)}")

    if emo_profile := personality.get("emotional_profile"):
        emo_parts = []
        if anxiety := emo_profile.get("anxiety"): emo_parts.append(f"Anxiety ({anxiety}/100)")
        if impulse := emo_profile.get("impulse_control"): emo_parts.append(f"Impulse Control ({impulse}/100)")
        if social := emo_profile.get("social_energy"): emo_parts.append(f"Social Energy ({social})")
        if emo_parts: lines.append(f"- Emotional Profile: {', '.join(emo_parts)}")

    if rom_profile := personality.get("romantic_profile"):
        rom_parts = []
        if orientation := rom_profile.get("orientation"): rom_parts.append(orientation)
        if libido := rom_profile.get("libido"): rom_parts.append(f"{libido} Libido")
        if kink := rom_profile.get("kinkiness"): rom_parts.append(f"{kink} Kinkiness")
        if goal := rom_profile.get("relationship_goal"): rom_parts.append(f"{goal} Goal")
        if rom_parts: lines.append(f"- Romantic Profile: {', '.join(rom_parts)}")

    if cult_profile := personality.get("cultural_background"):
        cult_parts = []
        if eth := cult_profile.get("ethnicity"): cult_parts.append(eth)
        if ses := cult_profile.get("socioeconomic_status"): cult_parts.append(ses)
        if edu := cult_profile.get("education"): cult_parts.append(f"{edu} Educated")
        if cult_parts: lines.append(f"- Background: {', '.join(cult_parts)}")

    if career := personality.get("career_style"):
        lines.append(f"- Career Style: {career}")

    if life_habits := personality.get("lifestyle_habits"):
        life_parts = []
        if sleep := life_habits.get("sleep_schedule"): life_parts.append(sleep)
        if clean := life_habits.get("cleanliness"): life_parts.append(clean)
        if health := life_habits.get("health_focus"): life_parts.append(f"{health} Health Focus")
        if life_parts: lines.append(f"- Habits: {', '.join(life_parts)}")

    if quirks := personality.get("quirks"):
        lines.append(f"- Quirks: {', '.join(quirks)}")

    return "\n".join(lines)
# --- End Personality Generation Setup ---


class Sim:
    """Represents a single Sim in the simulation."""

    def __init__(self, sim_id, x, y, ollama_client: OllamaClient, enable_talking: bool, bubble_display_time: float = 5.0):
        """Initializes a Sim with ID, position, Ollama client, and bubble display time."""
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
        self.sex = _assign_sex(self.first_name) # Assign sex
        self.x = x
        self.y = y
        self.speed = random.uniform(30, 70)  # Random speed for each sim
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))  # Fallback color
        # self.sprite = self._load_sprite() # Load character sprite
        self.path = None
        self.path_index = 0
        self.target = None
        # --- Personality ---
        self.personality = _generate_personality(ATTRIBUTES_DATA) # Keep the dictionary
        self.personality_description = _format_personality_for_prompt(self.personality, self.sex) # Pre-calculate description string, passing sex
        # --- End Personality ---
        self.memory = []  # List to store significant events or interactions
        self.ollama_client = ollama_client
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
    def update(self, dt, city, weather_state, all_sims: List['Sim'], logger, current_time, tile_size, direction_change_frequency): # Add tile_size and type hint
        """Updates the Sim's state, following a path if available, and logs data."""
        self.tile_size = tile_size
        self.is_blocked = False # Reset blocked status
        # print(f"Sim {self.sim_id}: update called at start, x={self.x:.2f}, y={self.y:.2f}, target={self.target}, is_interacting={self.is_interacting}, path={self.path}")
        # Call the movement update method
        movement_update(self, dt, city, weather_state, all_sims, logger, current_time, tile_size, direction_change_frequency)
        self.check_collision(all_sims)
        if self.is_blocked:
            self.handle_blocked(dt, city, direction_change_frequency)
        self.update_animation(dt) # Update animation frame
        if hasattr(self, 'last_update_time') and self.last_update_time == current_time:
            return
        self.last_update_time = current_time
        # print(f"Sim {self.sim_id}: update called at start, is_interacting={self.is_interacting}, interaction_timer={self.interaction_timer}, path={self.path}, target={self.target}, is_interacting={self.is_interacting}")
        # --- Conversation Logic ---
        if self.is_interacting:
            self.interaction_timer += dt # Keep track of total interaction time if needed

            # Check for conversation timeout (if waiting too long for a response)
            if self.waiting_for_ollama_response and (current_time - self.conversation_last_response_time > self.ollama_client.conversation_response_timeout):
                print(f"Sim {self.sim_id}: Conversation with {self.conversation_partner_id} timed out.")
                self._end_interaction(all_sims)
                return # Stop further processing for this sim in this update

            # Check for max turns reached
            if self.conversation_turns >= self.ollama_client.config['ollama'].get('conversation_max_turns', 6):
                 print(f"Sim {self.sim_id}: Conversation with {self.conversation_partner_id} reached max turns.")
                 self._end_interaction(all_sims)
                 return # Stop further processing

            # If it's my turn and I'm not waiting for a response, request one
            if self.is_my_turn_to_speak and not self.waiting_for_ollama_response:
                partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
                if partner:
                    print(f"Sim {self.sim_id}: Requesting conversation response (Turn {self.conversation_turns}). History: {self.conversation_history}")
                    request_sent = self.ollama_client.request_conversation_response(
                        self.sim_id,
                        self.first_name,
                        partner.first_name,
                        self.conversation_history,
                        self.personality_description # Pass pre-calculated description string
                    )
                    if request_sent:
                        self.waiting_for_ollama_response = True
                        self.conversation_last_response_time = current_time # Reset timeout timer
                    else:
                        print(f"Sim {self.sim_id}: Failed to send conversation request (maybe Ollama busy?).")
                        # Optionally handle failure, e.g., end interaction after a few failed attempts
                else:
                     print(f"Sim {self.sim_id}: ERROR - Conversation partner {self.conversation_partner_id} not found!")
                     self._end_interaction(all_sims) # End interaction if partner is lost
                     return

        # if logger:
        #     print(f"Sim {self.sim_id} update: x={self.x:.2f}, y={self.y:.2f}, target={self.target}, is_interacting={self.is_interacting}")
        if not self.is_interacting:
            if not self.path:
                self.path = get_path((self.x, self.y), (random.randint(0, city.width), random.randint(0, city.height)), city.graph, get_node_from_coords, get_coords_from_node, city.width, city.height)
            if not self.path:  # Still no path (e.g., couldn't find one)
                return

        # Update thought timer (for non-conversation thoughts)
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

    def check_collision(self, all_sims):
        """Checks for collision with other sims."""
        for other_sim in all_sims:
            if other_sim is not self:
                distance = math.sqrt((self.x - other_sim.x) ** 2 + (self.y - other_sim.y) ** 2)
                if distance < 30:  # Increased collision distance
                    self.is_blocked = True
                    break

    def handle_blocked(self, dt, city, direction_change_frequency):
        """Handles the Sim when it's blocked."""
        self.block_timer = getattr(self, 'block_timer', 0.0) + dt
        block_duration = 1.0  # Duration to stop in seconds
        if self.block_timer < block_duration:
            return  # Stay blocked

        self.block_timer = 0.0  # Reset timer
        # print(f"direction_change_frequency: {direction_change_frequency}")
        change_direction(self, city, direction_change_frequency)

    def _find_sim_by_id(self, sim_id_to_find: any, all_sims: List['Sim']) -> Optional['Sim']:
        """Helper to find a Sim object by its ID."""
        for sim in all_sims:
            if sim.sim_id == sim_id_to_find:
                return sim
        return None

    def _end_interaction(self, all_sims: List['Sim']):
        """Cleans up state at the end of an interaction."""
        print(f"Sim {self.sim_id}: Ending interaction with {self.conversation_partner_id}")
        partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
        if partner and partner.is_interacting:
             partner.is_interacting = False
             partner.talking_with = None
             partner.conversation_history = None
             partner.is_my_turn_to_speak = False
             partner.waiting_for_ollama_response = False
             partner.conversation_partner_id = None
             partner.conversation_turns = 0
             partner.interaction_timer = 0.0 # Reset partner timer too

        self.is_interacting = False
        self.talking_with = None # Keep talking_with for compatibility? Maybe remove.
        self.conversation_history = None
        self.is_my_turn_to_speak = False
        self.waiting_for_ollama_response = False
        self.conversation_partner_id = None
        self.conversation_turns = 0
        self.interaction_timer = 0.0 # Reset timer


    def handle_ollama_response(self, response_text: str, current_time: float, all_sims: List['Sim']):
        """Handles a response received from Ollama."""
        print(f"Sim {self.sim_id}: Received Ollama response: '{response_text}'")
        self.waiting_for_ollama_response = False # No longer waiting

        if self.is_interacting and self.conversation_partner_id is not None:
            # --- Handle Conversation Response ---
            # Use the new attributes for conversation messages
            self.conversation_message = response_text
            self.conversation_message_timer = self.bubble_display_time # Use configured duration
            # self.current_thought = None # Clear regular thought if starting conversation response? Optional.

            # Add to history
            new_entry = {"speaker": self.first_name, "line": response_text}
            if self.conversation_history is None: self.conversation_history = [] # Should be initialized, but safety check
            self.conversation_history.append(new_entry)

            # Update partner
            partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
            if partner:
                if partner.conversation_history is None: partner.conversation_history = []
                partner.conversation_history.append(new_entry) # Share history
                partner.is_my_turn_to_speak = True # It's partner's turn now
                partner.waiting_for_ollama_response = False # Partner isn't waiting yet
                partner.conversation_last_response_time = current_time # Update partner's timer too, maybe? Or just initiator? Let's update both.
                print(f"Sim {self.sim_id}: Passed turn to {partner.sim_id}")
            else:
                print(f"Sim {self.sim_id}: ERROR - Partner {self.conversation_partner_id} not found during response handling!")
                self._end_interaction(all_sims) # End if partner vanished

            # Update self
            self.is_my_turn_to_speak = False # Not my turn anymore
            self.conversation_turns += 1 # Increment turn counter *after* speaking
            self.conversation_last_response_time = current_time # Reset timeout timer

            # Check if max turns reached *after* this turn
            if self.conversation_turns >= self.ollama_client.config['ollama'].get('conversation_max_turns', 6):
                 print(f"Sim {self.sim_id}: Conversation with {self.conversation_partner_id} reached max turns after response.")
                 self._end_interaction(all_sims)

        else:
            # --- Handle Regular Thought ---
            self.current_thought = response_text
            self.thought_timer = THOUGHT_DURATION


    def _generate_thought(self, situation_description):
        """Requests non-conversational thought generation asynchronously using Ollama."""
        # Only generate if talking is enabled AND not currently in a conversation
        if self.enable_talking and not self.is_interacting:
            print(f"Sim {self.sim_id}: Requesting standard thought for: {situation_description}")
            request_sent = self.ollama_client.request_thought_generation(self.sim_id, situation_description)
            if not request_sent:
                print(f"Sim {self.sim_id}: Standard thought generation request ignored (already active).")
            # else:
                # print(f"Sim {self.sim_id}: Standard thought generation requested.")
        # else:
            # print(f"Sim {self.sim_id} talking blocked (interacting or disabled)")

    def update_animation(self, dt):
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

        width = SPRITE_WIDTH
        height = SPRITE_HEIGHT
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
           available_characters = [f for f in os.listdir(CHARACTER_SPRITE_DIR) if f.endswith('.png')]
           if not available_characters:
               print("No character sprites found!")
               return None, None

           chosen_sprite = random.choice(available_characters)
           sprite_path = os.path.join(CHARACTER_SPRITE_DIR, chosen_sprite)
           sprite_sheet = pygame.image.load(sprite_path).convert_alpha()
           character_name = chosen_sprite[:-4]  # Remove ".png" extension
           return character_name, sprite_sheet
       except Exception as e:
           print(f"Error loading sprite sheet: {e}")
           return "Unknown_Sim", None # Return a default name if loading fails
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

        # --- Draw Thought/Conversation Bubbles ---
        bubble_text = None
        bubble_timer = 0.0

        # Prioritize showing conversation message if available
        if self.conversation_message:
            bubble_text = self.conversation_message
            bubble_timer = self.conversation_message_timer
        elif self.current_thought: # Fallback to regular thought
            bubble_text = self.current_thought
            bubble_timer = self.thought_timer

        if bubble_text:
            wrapped_lines = wrap_text(bubble_text, SIM_FONT, MAX_BUBBLE_WIDTH - 10) # Use bubble_text here

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
