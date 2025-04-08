# Plan: Refactor Sim Personality Handling

This plan outlines the steps to refactor how Sim personality descriptions are handled in the `aisim` project. The goal is to store detailed personality data in individual files, generate descriptions using Ollama when needed, and load from files otherwise.

**Phase 1: Configuration & Ollama Client Update**

1.  **Modify `aisim/config/config.json`:**
    *   Add a new key `personality_prompt_template`. This template will guide Ollama in generating the description. It needs placeholders for the structured personality details and the Sim's sex.
    *   *Example Template:*
        ```json
        "personality_prompt_template": "Based on the following details:\nSex: {sex}\n{personality_details}\n\nWrite a brief, engaging personality description for this character in the second person (e.g., 'You are...'). Focus on the most salient traits and motivations."
        ```
2.  **Modify `aisim/src/ai/ollama_client.py`:**
    *   In the `__init__` method, load the new `personality_prompt_template` from the `config_manager`. Add validation to ensure the necessary placeholders (`{sex}`, `{personality_details}`) are present.
    *   Create a new **synchronous** method: `calculate_personality_description(self, personality_data: Dict, sex: str) -> str`.
        *   This method will receive the structured `personality_data` dictionary and the `sex` string.
        *   It will format the `personality_data` into a readable string (potentially adapting `_format_personality_for_prompt` from `personality.py`).
        *   It will populate the `personality_prompt_template` with the formatted details and sex.
        *   It will make a **synchronous** call to `self.client.generate(...)` using the populated prompt.
        *   It will handle the response, perform basic cleanup, and return the generated description string.
        *   It will include `try...except` blocks to catch potential errors during the Ollama API call and return a default error message (e.g., "Could not generate personality description.") if it fails.

**Phase 2: Core Logic Update**

3.  **Modify `aisim/src/core/sim.py`:**
    *   **Imports:** Add `import os` and `import json` at the top.
    *   **Personalities Directory:** Define the path `PERSONALITIES_DIR = "aisim/personalities"`.
    *   **Refactor `Sim.__init__`:**
        *   Remove the old direct calls to `_generate_personality` and `_format_personality_for_prompt` for setting `self.personality` and `self.personality_description`.
        *   **Ensure Directory Exists:** Add `os.makedirs(PERSONALITIES_DIR, exist_ok=True)` near the start of the personality handling section.
        *   **Construct File Path:** `personality_file = os.path.join(PERSONALITIES_DIR, f"{self.character_name}.json")`.
        *   **Implement Load or Generate Logic:**
            *   Check if `personality_file` exists.
            *   If yes: Try to load JSON, assign `self.personality` and `self.personality_description`. Handle `FileNotFoundError`, `JSONDecodeError`, `KeyError` by falling back to generation.
            *   If no (or loading failed): Generate structured personality (`_generate_personality`), call `ollama_client.calculate_personality_description` (synchronously), assign results, and save to file using a helper method.
    *   **(Recommended) Add Helper Method `_save_personality` to `Sim` class:**
        *   Takes `file_path` as an argument.
        *   Creates a dictionary with `personality` and `personality_description`.
        *   Uses `json.dump` to write the dictionary to the `file_path` with indentation.
        *   Includes `try...except` for `IOError`.

**Phase 3: Testing and Refinement**

4.  **Testing:**
    *   Delete any existing `aisim/personalities/` directory.
    *   Run the simulation.
    *   Verify `aisim/personalities/` directory and `.json` files are created.
    *   Inspect JSON files for correct structure and content (structured data + Ollama description).
    *   Restart simulation and verify personalities are loaded from files (check logs/output).
    *   Monitor for errors during file I/O or Ollama calls.

**Visual Plan (Mermaid):**

```mermaid
graph TD
    A[Start Sim __init__] --> B(Define Personalities Dir & File Path);
    B --> C{Personality File Exists?};
    C -- Yes --> D[Try Loading JSON];
    D -- Success --> E[Assign self.personality & self.description from File];
    D -- Failure --> F[Log Error];
    C -- No --> G[Generate Structured Personality (`_generate_personality`)];
    F --> G;
    G --> H[Call OllamaClient.calculate_personality_description (Sync)];
    H --> I[Assign self.personality & self.description from Generation];
    I --> J[Try Saving Personality to JSON File];
    E --> K[Continue Sim Initialization];
    J --> K;

    subgraph OllamaClient
        L[calculate_personality_description Method]
        M[Format Data + Get Template]
        N[Format Prompt]
        O[Call Ollama API (Sync)]
        P[Handle Response/Error]
        Q[Return Description String]
        M --> N --> O --> P --> Q
    end

    H --> L;
