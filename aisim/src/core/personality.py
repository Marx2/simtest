import random
from typing import Dict, List, Optional

# Note: SIM_CONFIG and ATTRIBUTES_DATA are no longer loaded globally here.
# They should be passed as arguments where needed.

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

def _format_personality_for_prompt(personality: Dict, sex: str) -> str:
    """Formats the personality dictionary into a readable string for the LLM prompt."""
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