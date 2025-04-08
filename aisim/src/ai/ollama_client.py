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
        print(f"Sim {sim_id}: {prompt}")
        result = None
        try:
            # Note: The ollama library itself doesn't have an explicit timeout for generate.
            # The timeout logic will need to be handled in the main loop based on self.conversation_response_timeout
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            result = response.get('response', '').strip()
            # Basic cleanup: remove potential self-prompting if the model includes it
            if result.startswith(f"{my_name}:"):
                result = result[len(f"{my_name}:"):].strip()
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