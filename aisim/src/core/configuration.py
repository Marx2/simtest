import json
import os
import logging
from typing import Any, Optional, Union, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the path to the configuration file relative to this script's location
# Go up two levels from core directory (src/core -> src -> aisim) then into config
CONFIG_FILE_NAME = 'config.json'
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'config', CONFIG_FILE_NAME)

class ConfigManager:
    """
    Manages loading and accessing configuration settings from a JSON file.
    Provides a centralized way to read configuration values with error handling.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern."""
        if not cls._instance:
            cls._instance = super(ConfigManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        """
        Initializes the ConfigManager, loading the configuration data.
        Ensures initialization only happens once for the singleton instance.
        """
        # Prevent re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._config_data = self._load_config()
        self._initialized = True
        logging.info(f"ConfigManager initialized. Loaded config from: {CONFIG_PATH}")

    def _load_config(self) -> dict:
        """Loads the configuration from the JSON file."""
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return config
        except FileNotFoundError:
            logging.warning(f"Configuration file not found at {CONFIG_PATH}. Using empty config.")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from config file {CONFIG_PATH}: {e}. Using empty config.")
            return {}
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading config from {CONFIG_PATH}: {e}. Using empty config.")
            return {}

    def get_entry(self, key_path: Union[str, List[str]], default: Optional[Any] = None) -> Any:
        """
        Retrieves a configuration value using a dot-separated string or a list of keys.

        Args:
            key_path: A string with keys separated by dots (e.g., "simulation.fps")
                      or a list of keys (e.g., ["simulation", "fps"]).
            default: The value to return if the key path is not found or invalid.

        Returns:
            The configuration value found at the key path, or the default value.
        """
        if isinstance(key_path, str):
            keys = key_path.split('.')
        elif isinstance(key_path, list):
            keys = key_path
        else:
            logging.warning(f"Invalid key_path type: {type(key_path)}. Must be string or list.")
            return default

        value = self._config_data
        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                else:
                    # Handle cases where an intermediate key leads to a non-dict value
                    logging.warning(f"Config path traversal error: Key '{key}' accessed on non-dictionary item in path '{key_path}'.")
                    return default
            return value
        except KeyError:
            # Key not found at some level
            # logging.debug(f"Config key path '{key_path}' not found. Returning default: {default}") # Optional: Log missing keys
            return default
        except Exception as e:
            logging.error(f"Unexpected error accessing config key path '{key_path}': {e}. Returning default.")
            return default

# Create a single, shared instance of the ConfigManager
config_manager = ConfigManager()
