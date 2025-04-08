import ollama
import json
# import os # No longer needed for CONFIG_PATH
import threading # Added
import queue # Added
from typing import Optional, Tuple, List, Dict # Added for type hinting
from aisim.src.core.configuration import config_manager # Import the centralized config manager
class OllamaClient:
    """Handles communication with the Ollama API, including asynchronous requests.""" # Updated docstring

    def __init__(self):
        """Initializes the Ollama client and result queue using centralized configuration.""" # Updated docstring
        # Get config values using the config_manager
        host = config_manager.get_entry('ollama.host', 'http://localhost:11434')
        self.model = config_manager.get_entry('ollama.model', 'phi3') # Provide a reasonable default model
        self.prompt_template = config_manager.get_entry('ollama.default_prompt_template', 'Default prompt: {situation}')
        self.conversation_prompt_template = config_manager.get_entry('ollama.conversation_prompt_template', self.prompt_template) # Fallback to default prompt template
        self.conversation_response_timeout = config_manager.get_entry('ollama.conversation_response_timeout', 30.0) # Default 30s
        self.max_concurrent_requests = config_manager.get_entry('ollama.max_concurrent_requests', 1) # Read max concurrent requests

        self.client = ollama.Client(host=host)
        self.results_queue = queue.Queue() # Queue to store results from threads
        self.active_requests = set() # Keep track of active requests per Sim ID
        print(f"Ollama client initialized. Host: {host}, Model: {self.model}")
        # Verify the conversation template has the required placeholders
        if not all(k in self.conversation_prompt_template for k in ['{my_name}', '{other_name}', '{history}', '{personality_info}']):
             print("Warning: conversation_prompt_template might be missing required placeholders ({my_name}, {other_name}, {history}, {personality_info})")
        # Load personality prompt template and verify placeholders
        self.personality_prompt_template = config_manager.get_entry('ollama.personality_prompt_template', 'Write a personality description.')
        if not all(k in self.personality_prompt_template for k in ['{sex}', '{personality_details}']):
            print("Warning: personality_prompt_template might be missing required placeholders ({sex}, {personality_details})")

    # Removed _load_config method as configuration is now handled by ConfigManager
    def _generate_worker(self, sim_id, situation_description):
        """Worker function to run Ollama generation in a separate thread."""
        # print(f"Ollama worker started for Sim {sim_id}") # Debug
        prompt = self.prompt_template.format(situation=situation_description)
        result = None
        try:
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            result = response.get('response', '').strip()
            # print(f"Ollama worker for Sim {sim_id} got result: {result}") # Debug
        except Exception as e:
            print(f"Error communicating with Ollama for Sim {sim_id}: {e}")
            result = f"({self.model} unavailable)" # Placeholder thought on error
        finally:
            # Put result (or error message) and sim_id onto the queue
            self.results_queue.put((sim_id, result))
            # Mark request as completed for this sim_id
            self.active_requests.discard(sim_id)
            # print(f"Ollama worker finished for Sim {sim_id}. Active requests: {self.active_requests}") # Debug


    def _generate_conversation_worker(self, sim_id: any, my_name: str, other_name: str, history: List[Dict[str, str]], personality_info: str):
        """Worker function to run Ollama conversation generation in a separate thread."""
        # Format history for the prompt
        history_str = "\n".join([f"{msg['speaker']}: {msg['line']}" for msg in history]) if history else "This is the start of the conversation."

        prompt = self.conversation_prompt_template.format(
            my_name=my_name,
            other_name=other_name,
            history=history_str,
            personality_info=personality_info # Use pre-formatted string
        )
        print(f"Sim {sim_id}\n---------\n {prompt}\n---------\n") # Debug
        result = None
        try:
            # Note: The ollama library itself doesn't have an explicit timeout for generate.
            # The timeout logic will need to be handled in the main loop based on self.conversation_response_timeout
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            result = response.get('response', '').strip()
            # Basic cleanup: remove potential self-prompting if the model includes it
            if result.startswith(f"{my_name}:"):
                result = result[len(f"{my_name}:"):].strip()
            print(f"Sim {sim_id}\n---------\n {result}\n---------\n") # Debug
        except Exception as e:
            print(f"Error communicating with Ollama for Sim {sim_id} (conversation): {e}")
            result = f"({self.model} unavailable)" # Placeholder thought on error
        finally:
            self.results_queue.put((sim_id, result))
            self.active_requests.discard(sim_id)


    def request_thought_generation(self, sim_id: any, situation_description: str) -> bool:
        """Requests thought generation asynchronously. Returns True if request started, False otherwise."""
        if sim_id in self.active_requests:
            return False
        self.active_requests.add(sim_id)
        thread = threading.Thread(target=self._generate_worker, args=(sim_id, situation_description), daemon=True)
        thread.start()
        return True

    def request_conversation_response(self, sim_id: any, my_name: str, other_name: str, history: List[Dict[str, str]], personality_info: str) -> bool:
        """Requests a conversation response asynchronously, including personality description. Returns True if request started, False otherwise."""
        # Check global concurrent request limit first
        if len(self.active_requests) >= self.max_concurrent_requests:
            # print(f"Sim {sim_id}: Cannot start conversation thread. Max concurrent requests ({self.max_concurrent_requests}) reached. Active: {self.active_requests}") # Debug
            return False
        # Then check if this specific sim already has a request
        if sim_id in self.active_requests:
            # print(f"Sim {sim_id}: Ollama request already active. Ignoring new conversation request.") # Debug
            return False

        # print(f"Starting Ollama conversation worker thread for Sim {sim_id}") # Debug
        # print(f"Sim {sim_id}: Attempting to start conversation thread. Active requests: {self.active_requests}. Params: sim_id={sim_id}, my_name={my_name}, other_name={other_name}, history={history}, personality_info={personality_info}") # Added logging
        self.active_requests.add(sim_id)
        thread = threading.Thread(target=self._generate_conversation_worker, args=(sim_id, my_name, other_name, history, personality_info), daemon=True)
        thread.start()
        return True

    def check_for_thought_results(self) -> Optional[Tuple[any, str]]:
        """Checks the queue for completed thought generation results. Non-blocking."""
        try:
            # Get result without blocking
            sim_id, result = self.results_queue.get_nowait()
            # print(f"Retrieved result for Sim {sim_id} from queue.") # Debug
            return sim_id, result
        except queue.Empty:
            # Queue is empty, no results available
            return None

    # Keep the synchronous version for potential testing or other uses
    def generate_thought_sync(self, situation_description):
        """Generates a thought synchronously (original method)."""
        prompt = self.prompt_template.format(situation=situation_description)
        try:
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            return response.get('response', '').strip()
        except Exception as e:
            print(f"Error communicating with Ollama (sync): {e}")
            return f"({self.model} unavailable)"

    def calculate_personality_description(self, personality_data: Dict, sex: str) -> str:
        """Generates a personality description synchronously using the Ollama API."""
        try:
            # Format personality data into a string
            # Use the helper method defined below
            personality_details = self._format_personality_data(personality_data, sex)

            # Format the prompt using the template
            prompt = self.personality_prompt_template.format(sex=sex, personality_details=personality_details)

            # Call the Ollama API
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            description = response.get('response', '').strip()
            return description
        except Exception as e:
            print(f"Error generating personality description: {e}")
            return "Could not generate personality description."

    def _format_personality_data(self, personality: Dict, sex: str) -> str:
        """Formats the personality dictionary into a readable string for the LLM prompt.
        Adapted from aisim.src.core.personality._format_personality_for_prompt"""
        lines = [f"Sex: {sex}"]  # Add sex at the beginning
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