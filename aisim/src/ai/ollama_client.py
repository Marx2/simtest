import ollama
import json
import os
import threading # Added
import queue # Added
from typing import Optional, Tuple # Added for type hinting

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.json')
class OllamaClient:
    """Handles communication with the Ollama API, including asynchronous requests.""" # Updated docstring

    def __init__(self):
        """Loads configuration and initializes the Ollama client and result queue.""" # Updated docstring
        self.config = self._load_config()
        self.client = ollama.Client(host=self.config['ollama']['host'])
        self.model = self.config['ollama']['model']
        self.prompt_template = self.config['ollama']['default_prompt_template']
        self.results_queue = queue.Queue() # Added: Queue to store results from threads
        self.active_requests = set() # Added: Keep track of active requests per Sim ID
        print(f"Ollama client initialized. Host: {self.config['ollama']['host']}, Model: {self.model}")

    def _load_config(self):
        """Loads the configuration from config.json."""
        try:
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Configuration file not found at {CONFIG_PATH}")
            # Return default config as fallback
            return {
                "ollama": {
                    "host": "http://localhost:11434",
                    "model": "deepseek-r1:7b",
                    "default_prompt_template": "You are a character in a life simulation. Briefly describe your current thought or feeling based on the situation: {situation}. Keep it concise, like a thought bubble."
                }
            }
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {CONFIG_PATH}")
            raise # Re-raise error as it's critical

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


    def request_thought_generation(self, sim_id, situation_description):
        """Requests thought generation asynchronously. Returns True if request started, False otherwise."""
        # Only start a new request if one isn't already active for this Sim
        if sim_id in self.active_requests:
            # print(f"Ollama request already active for Sim {sim_id}. Ignoring new request.") # Debug
            return False

        # print(f"Starting Ollama worker thread for Sim {sim_id}") # Debug
        self.active_requests.add(sim_id)
        thread = threading.Thread(target=self._generate_worker, args=(sim_id, situation_description), daemon=True)
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

# Example usage (for testing)
if __name__ == '__main__':
    client = OllamaClient()

    # Test synchronous call
    thought_sync = client.generate_thought_sync("Just arrived at the park on a sunny day.")
    print(f"Generated thought (sync): {thought_sync}")

    # Test asynchronous call
    print("\nRequesting async thoughts...")
    client.request_thought_generation("sim1", "Walking in the rain.")
    client.request_thought_generation("sim2", "Seeing a friend across the street.")
    client.request_thought_generation("sim1", "This should be ignored (already active).") # Test duplicate request

    print("Checking for results...")
    import time
    results_received = 0
    start_time = time.time()
    while results_received < 2 and time.time() - start_time < 10: # Wait up to 10 seconds
        result = client.check_for_thought_results()
        if result:
            sim_id, thought = result
            print(f"Received async thought for {sim_id}: {thought}")
            results_received += 1
        else:
            print(".", end="", flush=True)
            time.sleep(0.5)

    if results_received < 2:
        print("\nDid not receive all results in time.")
    else:
        print("\nReceived all expected results.")