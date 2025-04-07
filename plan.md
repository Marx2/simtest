# Plan: Centralize Configuration Reading

**Objective:** Refactor the `aisim` project to read configuration from `aisim/config/config.json` using a single, centralized module, eliminating duplicate code and improving maintainability.

**Current Situation:** Configuration loading logic (reading `config.json`, handling errors, setting defaults) is duplicated in:
*   `aisim/src/main.py`
*   `aisim/src/ai/ollama_client.py`
*   `aisim/src/core/city.py`

**Proposed Solution:**

1.  **Create a New Configuration Module:**
    *   Create a new file: `aisim/src/core/configuration.py`.
    *   Inside this file, define a class `ConfigManager`.
    *   The `ConfigManager` class will:
        *   Define the correct, constant path to `aisim/config/config.json`.
        *   Load the configuration from the JSON file during initialization (`__init__`).
        *   Implement robust error handling for `FileNotFoundError` and `json.JSONDecodeError`. If the file is missing or invalid, it will log a warning and store an empty dictionary or minimal defaults.
        *   Store the loaded configuration data in an instance variable (e.g., `self._config_data`).
        *   Provide a method `get_entry(self, key_path, default=None)`:
            *   Accepts a `key_path` string (e.g., `"simulation.fps"`) or a list of keys (e.g., `["simulation", "fps"]`) to access nested values.
            *   Safely navigates the loaded configuration data.
            *   Returns the requested value, or the provided `default` value if the key path is invalid or the key doesn't exist.
    *   Create a single instance of `ConfigManager` within the module (e.g., `config_manager = ConfigManager()`) that other modules can import and use.

2.  **Refactor Existing Modules:**
    *   **`aisim/src/main.py`**:
        *   Remove the `CONFIG_PATH` constant and the `load_config` function.
        *   Import the `config_manager` instance from `aisim.src.core.configuration`.
        *   Replace all configuration access (e.g., `config.get(...)`, `simulation_config.get(...)`) with calls to `config_manager.get_entry(...)`, providing appropriate key paths and default values.
    *   **`aisim/src/ai/ollama_client.py`**:
        *   Remove the `CONFIG_PATH` constant and the `_load_config` method.
        *   Remove the `self.config` attribute and its initialization.
        *   Import the `config_manager` instance.
        *   Replace all accesses to `self.config[...]` with calls to `config_manager.get_entry(...)`.
    *   **`aisim/src/core/city.py`**:
        *   Remove the `CONFIG_PATH` constant and the `_load_config` method.
        *   Remove the `self.config` attribute and its initialization.
        *   Import the `config_manager` instance.
        *   Replace all accesses to `self.config[...]` with calls to `config_manager.get_entry(...)`. Handle specific type conversions (like list to tuple for colors) *after* retrieving the value.
    *   **`aisim/src/core/movement.py`**:
        *   Remove the unused `CONFIG_PATH` constant.
        *   No direct changes needed within this file's functions, as configuration values are passed in.

**Visualization:**

```mermaid
graph TD
    subgraph Before
        M[main.py] -- reads --> C(config.json)
        O[ollama_client.py] -- reads --> C
        CT[city.py] -- reads --> C
        MV[movement.py] -- uses config from --> M
    end

    subgraph After
        CM[configuration.py] -- reads --> C2(config.json)
        M2[main.py] -- imports & uses --> CM
        O2[ollama_client.py] -- imports & uses --> CM
        CT2[city.py] -- imports & uses --> CM
        MV2[movement.py] -- uses config from --> M2
    end

    style C fill:#f9f,stroke:#333,stroke-width:2px
    style C2 fill:#f9f,stroke:#333,stroke-width:2px
    style CM fill:#ccf,stroke:#333,stroke-width:2px
