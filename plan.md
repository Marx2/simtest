# Plan: Implement Relationship-Based Conversation Prompts

**Objective:** Modify the AI Sim conversation system to use different prompts based on the romantic relationship level between Sims.

**Phase 1: Configuration Update**

1.  **Modify `aisim/config/config.json`:**
    *   Remove the existing `conversation_prompt_template` key.
    *   Add a new key `conversation_prompt_levels` which will be an array (list) of 10 strings.
    *   Populate this list with placeholder prompts (e.g., "Placeholder Prompt - Level 1 [Shy]", ..., "Placeholder Prompt - Level 10 [Intimate]").

**Phase 2: Code Modifications**

1.  **Update `aisim/src/ai/ollama_client.py`:**
    *   **`__init__`:**
        *   Load `ollama.conversation_prompt_levels` into `self.conversation_prompt_levels`.
        *   Add validation to ensure it's a list with 10 elements.
    *   **`_generate_conversation_worker`:**
        *   Add a `romance_level: float` parameter.
        *   Implement logic to select the prompt index based on `romance_level` (0.0-0.09 -> index 0, ..., 0.9-1.0 -> index 9).
        *   Use the selected template for the prompt.
    *   **`request_conversation_response`:**
        *   Add a `romance_level: float` parameter.
        *   Pass `romance_level` when creating the `_generate_conversation_worker` thread.

2.  **Update `aisim/src/core/sim.py`:**
    *   **`conversation_update`:**
        *   In the call to `self.ollama_client.request_conversation_response`, retrieve the current Sim's `romance` level towards the partner from `self.relationships`.
        *   Pass the retrieved `romance_level` as an argument.

**Phase 3: Consideration**

*   **Relationship Dynamics:** The plan focuses on *using* the `romance` value. Additional code (outside this scope) is needed to *update* these values based on simulation events for the system to be dynamic.

**Visual Flow (Sequence Diagram):**

```mermaid
sequenceDiagram
    participant SimA as Sim A (caller)
    participant OllamaClient as Ollama Client
    participant SimB as Sim B (partner)

    Note over SimA: In conversation_update()
    SimA->>SimA: Get partner_id (SimB's ID)
    SimA->>SimA: Get romance_level = self.relationships[partner_id]["romance"]
    SimA->>OllamaClient: request_conversation_response(..., romance_level)
    OllamaClient->>OllamaClient: Create _generate_conversation_worker thread(..., romance_level)
    Note over OllamaClient: Inside worker thread
    OllamaClient->>OllamaClient: Calculate prompt_index from romance_level
    OllamaClient->>OllamaClient: Select prompt_template = self.conversation_prompt_levels[prompt_index]
    OllamaClient->>OllamaClient: Format prompt using selected_template
    OllamaClient->>Ollama API: generate(prompt)
    Ollama API-->>OllamaClient: response
    OllamaClient->>OllamaClient: Put (sim_id, response) in queue
    Note over SimA: Later, in check_for_thought_results() or similar
    SimA->>OllamaClient: check_for_results()
    OllamaClient-->>SimA: Return (sim_id, response)
    SimA->>SimA: Process response (e.g., update conversation_history, display bubble)
```

**Next Steps:** Implement the changes described above in Code mode.

---
