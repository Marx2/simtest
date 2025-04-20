import os
import random
import json
import logging # Added missing import
from typing import Dict
from aisim.src.core.configuration import config_manager # Import the centralized config manager

PERSONALITIES_DIR = config_manager.get_entry('sim.personalities_path') # Directory to store personality files

# --- Load Attributes Data ---
ATTRIBUTES_DATA = {} # Default empty
ATTRIBUTES_FILE_PATH = config_manager.get_entry('sim.attributes_file_path')
if ATTRIBUTES_FILE_PATH:
    try:
        with open(ATTRIBUTES_FILE_PATH, 'r') as f:
            ATTRIBUTES_DATA = json.load(f)
    except FileNotFoundError:
        logging.error(f"Attributes file not found at {ATTRIBUTES_FILE_PATH}")
    except json.JSONDecodeError:
        logging.error(f"Could not decode JSON from {ATTRIBUTES_FILE_PATH}")
else:
    logging.warning("'sim.attributes_file_path' not configured")

def load_or_generate_personality_for_sim(self, sim_config: Dict):
    """Loads personality from file if exists, otherwise generates and saves it."""
    os.makedirs(PERSONALITIES_DIR, exist_ok=True) # Ensure directory exists
    personality_file = os.path.join(PERSONALITIES_DIR, f"{self.character_name}.json")

    if os.path.exists(personality_file):
        try:
            with open(personality_file, 'r') as f:
                data = json.load(f)
            self.personality = data.get("personality", {}) # Load structured data
            self.personality_description = data.get("personality_description", "Error: Description missing in file.") # Load description
            logging.info(f"Loaded personality for {self.full_name} from {personality_file}")
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logging.error(f"Error loading personality for {self.full_name} from {personality_file}: {e}. Regenerating.")
            # Fallback to generation if loading fails
            self.personality = _generate_personality(ATTRIBUTES_DATA, sim_config.get("personality", {}))
            self.personality_description = self.ollama_client.calculate_personality_description(self.personality, self.sex)
            save_personality(self, personality_file) # Attempt to save the newly generated data
    else:
        logging.info(f"Personality file not found for {self.full_name}. Generating...")
        # Generate personality (structured)
        self.personality = _generate_personality(ATTRIBUTES_DATA, sim_config.get("personality", {}))
        # Generate description (via Ollama)
        self.personality_description = self.ollama_client.calculate_personality_description(self.personality, self.sex)
        # Save to file
        save_personality(self, personality_file)

def save_personality(self, file_path):
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
        logging.info(f"Saved personality for {self.full_name} to {file_path}")
    except IOError as e:
        logging.error(f"Error saving personality for {self.full_name} to {file_path}: {e}")

def _assign_sex(first_name: str, sim_config: Dict) -> str:
    """Assigns sex based on a simple heuristic using common female names from config."""
    # Load female names from config, default to empty list, convert to set for efficient lookup
    female_names_set = set(sim_config.get("female_names", []))
    return "Female" if first_name in female_names_set else "Male"

def _generate_personality(attributes_data: Dict, personality_config: Dict) -> Dict:
    """Generates a random personality dictionary based on loaded attributes and config."""
    if not attributes_data:
        return {} # Return empty if attributes couldn't be loaded

    personality = {}
    num_traits = personality_config.get("num_traits", 3)
    num_hobbies = personality_config.get("num_hobbies", 3)
    num_quirks = personality_config.get("num_quirks", 2)

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


