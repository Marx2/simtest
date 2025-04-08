# Plan: Romance Level Adjustment Based on Conversation History

**Goal:** Analyze the conversation history between two Sims using an LLM after their interaction ends and adjust their mutual romance levels based on the analysis.

**Core Idea:**

1.  When a conversation finishes (in `interaction._end_interaction`), trigger an asynchronous LLM request via `OllamaClient` to analyze the conversation history.
2.  The LLM will return a simple indicator (`INCREASE`, `DECREASE`, `NEUTRAL`).
3.  The main simulation loop (`main.py`) will poll for these analysis results (alongside existing thought/conversation results).
4.  Upon receiving an analysis result, the main loop will update the `relationships` dictionary for both involved Sims.

**Detailed Plan:**

1.  **Configuration (`aisim/config/config.json`):**
    *   Add a new prompt template specifically for romance analysis within the `ollama` section. This prompt will instruct the LLM to analyze the provided history (`{history}`) between `{sim1_name}` and `{sim2_name}` and output only one word: `INCREASE`, `DECREASE`, or `NEUTRAL`.
    *   Example Key: `"romance_analysis_prompt_template"`
    *   Add a configuration value for the magnitude of the romance change, e.g., `"romance_change_step": 0.05` (within the `simulation` or `sim` section).

2.  **Ollama Client (`aisim/src/ai/ollama_client.py`):**
    *   **Result Queue:** Modify the `self.results_queue` to store structured dictionaries instead of simple tuples. This allows distinguishing different result types.
        *   Example structure: `{'type': 'romance_analysis', 'sim1_id': id1, 'sim2_id': id2, 'data': 'INCREASE'}` or `{'type': 'thought', 'sim_id': id, 'data': text}`.
    *   **New Worker:** Create a new asynchronous worker function `_generate_romance_analysis_worker(self, sim1_id, sim1_name, sim2_id, sim2_name, history)`:
        *   Loads the `romance_analysis_prompt_template` from config.
        *   Formats the prompt with the provided names and history.
        *   Calls `self.client.generate`.
        *   Parses the response to get `INCREASE`, `DECREASE`, or `NEUTRAL`.
        *   Puts a structured dictionary (like the example above) onto `self.results_queue`.
        *   Handles potential errors.
    *   **New Request Method:** Create a new public method `request_romance_analysis(self, sim1_id, sim1_name, sim2_id, sim2_name, history)`:
        *   Starts the `_generate_romance_analysis_worker` in a new thread.
        *   Returns `True` if started, `False` otherwise.
    *   **Update Result Check:** Modify `check_for_thought_results` (perhaps rename to `check_for_results`) to retrieve and return the structured dictionary from the queue.

3.  **Interaction Logic (`aisim/src/core/interaction.py`):**
    *   Modify `_end_interaction(self, city, all_sims)`:
        *   **Before** clearing `self.conversation_history` and `partner.conversation_history`, capture the history (e.g., `final_history = self.conversation_history[:]`).
        *   Get the partner Sim object (`partner = self._find_sim_by_id(...)`).
        *   Store `self.sim_id`, `self.first_name`, `partner.sim_id`, `partner.first_name`.
        *   **After** getting the necessary data but **before** clearing the partner's state, call the new `self.ollama_client.request_romance_analysis` method with the captured IDs, names, and `final_history`, but only if `final_history` is not empty/None.
        *   Proceed with clearing the state for both Sims as currently implemented.

4.  **Main Loop (`aisim/src/main.py`):**
    *   Modify the result polling loop (currently lines 187-201):
        *   Call the updated `ollama_client.check_for_results()`.
        *   Check the `'type'` field of the returned dictionary.
        *   If `'type'` is `'thought'` or indicates a regular conversation response, pass it to `interaction.handle_ollama_response` as before.
        *   **If `'type'` is `'romance_analysis'**:
            *   Extract `sim1_id`, `sim2_id`, and `analysis_result` (`'INCREASE'`, `'DECREASE'`, `'NEUTRAL'`) from the dictionary.
            *   Retrieve `sim1 = sims_dict.get(sim1_id)` and `sim2 = sims_dict.get(sim2_id)`.
            *   Get the `romance_change_step` from `config_manager`.
            *   If `sim1` and `sim2` exist:
                *   Calculate the change amount based on `analysis_result` and `romance_change_step`.
                *   Update `sim1.relationships[sim2_id]['romance']` (clamping between 0.0 and 1.0).
                *   Update `sim2.relationships[sim1_id]['romance']` (clamping between 0.0 and 1.0).
                *   Log this change (e.g., `print(f"Romance between {sim1.first_name} and {sim2.first_name} {analysis_result}d.")`).

**Sequence Diagram:**

```mermaid
sequenceDiagram
    participant SimA as Sim A (in interaction)
    participant SimB as Sim B (in interaction)
    participant Interaction as interaction.py
    participant MainLoop as main.py
    participant OllamaClient as ollama_client.py
    participant LLM

    Note over SimA, SimB: Conversation ends...
    Interaction->>Interaction: In _end_interaction(): Capture history, IDs, names
    Interaction->>OllamaClient: request_romance_analysis(ids, names, history)
    Interaction->>Interaction: Clear SimA & SimB state
    OllamaClient->>+LLM: generate(prompt=romance_analysis)
    Note over OllamaClient: Worker thread puts result dict in queue

    loop Main Game Loop
        MainLoop->>OllamaClient: check_for_results()
        alt Ollama has result
            OllamaClient-->>MainLoop: Returns result_dict
            alt result_dict['type'] == 'romance_analysis'
                MainLoop->>MainLoop: Find sim1, sim2 in sims_dict
                MainLoop->>MainLoop: Get romance_change_step from config
                MainLoop->>SimA: Update relationships[sim2_id]['romance']
                MainLoop->>SimB: Update relationships[sim1_id]['romance']
                MainLoop->>MainLoop: Log change
            else result_dict['type'] == 'thought'/'conversation'
                MainLoop->>Interaction: handle_ollama_response(sim, text, ...)
            end
        else No result from Ollama
            MainLoop->>MainLoop: Continue simulation updates...
        end
    end
    LLM->>-OllamaClient: Returns analysis text
