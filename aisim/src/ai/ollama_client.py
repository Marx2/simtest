import ollama
# import os # No longer needed for CONFIG_PATH
import threading # Added
import queue # Added
from typing import Optional, Tuple, List, Dict, Any # Added Any for Dict values
from aisim.src.core.configuration import config_manager # Import the centralized config manager
class OllamaClient:
    """Handles communication with the Ollama API, including asynchronous requests.""" # Updated docstring

    def __init__(self):
        """Initializes the Ollama client and result queue using centralized configuration.""" # Updated docstring
        # Get config values using the config_manager
        host = config_manager.get_entry('ollama.host', 'http://localhost:11434')
        self.model = config_manager.get_entry('ollama.model', 'phi3') # Provide a reasonable default model
        self.prompt_template = config_manager.get_entry('ollama.default_prompt_template', 'Default prompt: {situation}')
        # Load the list of conversation prompt templates
        self.conversation_prompt_levels = config_manager.get_entry('ollama.conversation_prompt_levels', [])
        self.conversation_response_timeout = config_manager.get_entry('ollama.conversation_response_timeout', 30.0) # Default 30s
        self.max_concurrent_requests = config_manager.get_entry('ollama.max_concurrent_requests', 1) # Read max concurrent requests

        self.client = ollama.Client(host=host)
        self.results_queue = queue.Queue() # Queue to store results from threads
        self.active_requests = set() # Keep track of active requests per Sim ID
        print(f"Ollama client initialized. Host: {host}, Model: {self.model}")
        # Verify the conversation prompt levels list
        if not isinstance(self.conversation_prompt_levels, list) or len(self.conversation_prompt_levels) != 10:
            print(f"Error: 'ollama.conversation_prompt_levels' must be a list of 10 strings in config. Found: {self.conversation_prompt_levels}")
            self.conversation_prompt_levels = [self.prompt_template] * 10 # Fallback to default template for all levels
        else:
             # Optionally, verify placeholders in each template (can be verbose)
             for i, template in enumerate(self.conversation_prompt_levels):
                 if not all(k in template for k in ['{my_name}', '{other_name}', '{history}', '{personality_info}']):
                     print(f"Warning: conversation_prompt_levels[{i}] might be missing required placeholders.")
        # Load personality prompt template and verify placeholders
        self.personality_prompt_template = config_manager.get_entry('ollama.personality_prompt_template', 'Write a personality description.')
        if not all(k in self.personality_prompt_template for k in ['{sex}', '{personality_details}']):
            print("Warning: personality_prompt_template might be missing required placeholders ({sex}, {personality_details})")
        # Load romance analysis prompt template
        self.romance_analysis_prompt_template = config_manager.get_entry('ollama.romance_analysis_prompt_template', 'Analyze romance: {history}')
        if not all(k in self.romance_analysis_prompt_template for k in ['{sim1_name}', '{sim2_name}', '{history}']):
            print("Warning: romance_analysis_prompt_template might be missing required placeholders ({sim1_name}, {sim2_name}, {history})")

    def _generate_conversation_worker(self, sim_id: any, my_name: str, other_name: str, history: List[Dict[str, str]], personality_info: str, romance_level: float):
        """Worker function to run Ollama conversation generation in a separate thread."""
        # Format history for the prompt
        history_str = "\n".join([f"{msg['speaker']}: {msg['line']}" for msg in history]) if history else "This is the start of the conversation."

        # Select prompt based on romance level (0.0 to 1.0)
        clamped_level = max(0.0, min(1.0, romance_level))
        prompt_index = min(len(self.conversation_prompt_levels) - 1, int(clamped_level * len(self.conversation_prompt_levels))) # Ensure index is valid
        selected_template = self.conversation_prompt_levels[prompt_index]

        prompt = selected_template.format(
            my_name=my_name,
            other_name=other_name,
            history=history_str,
            personality_info=personality_info # Use pre-formatted string
        )
        # print(f"Sim {sim_id}\n---------\n {prompt}\n---------\n") # Debug
        result = None
        try:
            # Note: The ollama library itself doesn't have an explicit timeout for generate.
            # The timeout logic will need to be handled in the main loop based on self.conversation_response_timeout
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            result = response.get('response', '').strip()
            # Basic cleanup: remove potential self-prompting if the model includes it
            if result.startswith(f"{my_name}:"):
                result = result[len(f"{my_name}:"):].strip()
            # print(f"Sim {sim_id}\n---------\n {result}\n---------\n") # Debug
        except Exception as e:
            print(f"Error communicating with Ollama for Sim {sim_id} (conversation): {e}")
            result = f"({self.model} unavailable)" # Placeholder conversation response on error
        finally:
            # Put structured result onto the queue
            result_data = {'type': 'conversation', 'sim_id': sim_id, 'data': result}
            self.results_queue.put(result_data)
            self.active_requests.discard(sim_id)

    def request_conversation_response(self, sim_id: any, my_name: str, other_name: str, history: List[Dict[str, str]], personality_info: str, romance_level: float) -> bool:
        """Requests a conversation response asynchronously, selecting prompt based on romance_level. Returns True if request started, False otherwise."""
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
        thread = threading.Thread(target=self._generate_conversation_worker, args=(sim_id, my_name, other_name, history, personality_info, romance_level), daemon=True)
        thread.start()
        return True

    def _generate_romance_analysis_worker(self, sim1_id: Any, sim1_name: str, sim2_id: Any, sim2_name: str, history: List[Dict[str, str]]):
        """Worker function to analyze conversation history for romance change."""
        history_str = "\n".join([f"{msg['speaker']}: {msg['line']}" for msg in history]) if history else "No conversation history."
        prompt = self.romance_analysis_prompt_template.format(
            sim1_name=sim1_name,
            sim2_name=sim2_name,
            history=history_str
        )
        analysis_result = "NEUTRAL" # Default
        try:
            print(f"Analyzing romance between {sim1_name} ({sim1_id}) and {sim2_name} ({sim2_id})...") # Debug
            # print(f"Analysis Prompt:\n{prompt}") # Verbose Debug
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            raw_result = response.get('response', '').strip().upper()
            # Basic validation: ensure it's one of the expected values
            if raw_result in ["INCREASE", "DECREASE", "NEUTRAL"]:
                analysis_result = raw_result
                print(f"Romance analysis result: {analysis_result}") # Debug
            else:
                print(f"Warning: Unexpected romance analysis result '{raw_result}'. Defaulting to NEUTRAL.")
        except Exception as e:
            print(f"Error during romance analysis between {sim1_id} and {sim2_id}: {e}")
            analysis_result = "NEUTRAL" # Default to neutral on error
        finally:
            # Put structured result onto the queue
            result_data = {
                'type': 'romance_analysis',
                'sim1_id': sim1_id,
                'sim2_id': sim2_id,
                'data': analysis_result # INCREASE, DECREASE, or NEUTRAL
            }
            self.results_queue.put(result_data)
            # Note: No need to manage active_requests here as analysis runs post-interaction.

    def request_romance_analysis(self, sim1_id: Any, sim1_name: str, sim2_id: Any, sim2_name: str, history: List[Dict[str, str]]) -> bool:
        """Requests asynchronous analysis of conversation romance level."""
        print(f"Starting romance analysis worker thread for interaction between {sim1_id} and {sim2_id}") # Debug
        thread = threading.Thread(
            target=self._generate_romance_analysis_worker,
            args=(sim1_id, sim1_name, sim2_id, sim2_name, history),
            daemon=True
        )
        thread.start()
        return True # Assume thread start is successful for now

    def check_for_results(self) -> Optional[Dict[str, Any]]:
        """Checks the queue for any completed results (conversation, analysis). Non-blocking."""
        try:
            # Get result dictionary without blocking
            result_data = self.results_queue.get_nowait()
            # print(f"Retrieved result from queue: {result_data}") # Debug
            return result_data
        except queue.Empty:
            # Queue is empty, no results available
            return None

    # --- The methods below were added/modified for romance analysis ---

    def _generate_romance_analysis_worker(self, sim1_id: Any, sim1_name: str, sim2_id: Any, sim2_name: str, history: List[Dict[str, str]]):
        """Worker function to analyze conversation history for romance change."""
        history_str = "\n".join([f"{msg['speaker']}: {msg['line']}" for msg in history]) if history else "No conversation history."
        prompt = self.romance_analysis_prompt_template.format(
            sim1_name=sim1_name,
            sim2_name=sim2_name,
            history=history_str
        )
        analysis_result = "NEUTRAL" # Default
        try:
            print(f"Analyzing romance between {sim1_name} ({sim1_id}) and {sim2_name} ({sim2_id})...") # Debug
            # print(f"Analysis Prompt:\n{prompt}") # Verbose Debug
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            raw_result = response.get('response', '').strip().upper()
            # Basic validation: ensure it's one of the expected values
            if raw_result in ["INCREASE", "DECREASE", "NEUTRAL"]:
                analysis_result = raw_result
                print(f"Romance analysis result: {analysis_result}") # Debug
            else:
                print(f"Warning: Unexpected romance analysis result '{raw_result}'. Defaulting to NEUTRAL.")
        except Exception as e:
            print(f"Error during romance analysis between {sim1_id} and {sim2_id}: {e}")
            analysis_result = "NEUTRAL" # Default to neutral on error
        finally:
            # Put structured result onto the queue
            result_data = {
                'type': 'romance_analysis',
                'sim1_id': sim1_id,
                'sim2_id': sim2_id,
                'data': analysis_result # INCREASE, DECREASE, or NEUTRAL
            }
            self.results_queue.put(result_data)
            # Note: No need to manage active_requests here as analysis runs post-interaction.

    def request_romance_analysis(self, sim1_id: Any, sim1_name: str, sim2_id: Any, sim2_name: str, history: List[Dict[str, str]]) -> bool:
        """Requests asynchronous analysis of conversation romance level."""
        print(f"Starting romance analysis worker thread for interaction between {sim1_id} and {sim2_id}") # Debug
        thread = threading.Thread(
            target=self._generate_romance_analysis_worker,
            args=(sim1_id, sim1_name, sim2_id, sim2_name, history),
            daemon=True
        )
        thread.start()
        return True # Assume thread start is successful for now

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