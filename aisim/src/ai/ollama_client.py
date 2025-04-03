import ollama
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.json')

class OllamaClient:
    """Handles communication with the Ollama API."""

    def __init__(self):
        """Loads configuration and initializes the Ollama client."""
        self.config = self._load_config()
        self.client = ollama.Client(host=self.config['ollama']['host'])
        self.model = self.config['ollama']['model']
        self.prompt_template = self.config['ollama']['default_prompt_template']
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

    def generate_thought(self, situation_description):
        """Generates a thought using the configured Ollama model."""
        prompt = self.prompt_template.format(situation=situation_description)
        try:
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            # TODO: Add more sophisticated error handling and response parsing
            return response.get('response', '').strip()
        except Exception as e:
            print(f"Error communicating with Ollama: {e}")
            return f"({self.model} unavailable)" # Placeholder thought on error

# Example usage (for testing)
if __name__ == '__main__':
    client = OllamaClient()
    thought = client.generate_thought("Just arrived at the park on a sunny day.")
    print(f"Generated thought: {thought}")
    thought = client.generate_thought("Walking in the rain.")
    print(f"Generated thought: {thought}")