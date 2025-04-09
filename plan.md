# Conversation Redesign Plan

This plan details the steps to refactor the conversation logic in the `aisim` project based on the user's requirements, including an explicit Ollama client lock, turn-based flow, and specific bubble display timing.

**Assumptions:**

*   The `City` class (likely in `aisim/src/core/city.py`) manages shared simulation state, including the list of active Sims and global flags.
*   The core game loop calls `sim.update()` for each Sim.
*   Existing functions like `_find_sim_by_id` are available.

**Plan Steps:**

**1. Introduce Global Ollama Lock:**

*   **File:** `aisim/src/core/city.py` (or equivalent central state manager)
*   **Change:** Add a new boolean attribute:
    ```python
    # In City.__init__
    self.ollama_client_locked = False
    ```
*   **Reset:** Ensure this flag is reset to `False` if the simulation restarts.

**2. Modify Conversation Initiation (`interaction.py`):**

*   **File:** `aisim/src/core/interaction.py`
*   **Function:** `_initiate_conversation`
*   **Changes:**
    *   After determining `first_speaker` and `second_speaker_listener`.
    *   Remove the immediate setting of `is_interacting = True`.
    *   Attempt to acquire the `city.ollama_client_locked` flag.
    *   If lock acquired:
        *   Set `city.ollama_client_locked = True`.
        *   Set `is_interacting = True` for both Sims.
        *   Stop movement (`path = None`, `target = None`, etc.).
        *   Initialize conversation state (`conversation_history`, `partner_id`, etc.).
        *   Set `first_speaker.is_my_turn_to_speak = True`, `second_speaker_listener.is_my_turn_to_speak = False`.
        *   Add Sims to `city.active_conversation_partners`.
        *   Call `_send_conversation_request` for the `first_speaker`.
        *   If `_send_conversation_request` fails, release the lock (`city.ollama_client_locked = False`) and call `_end_interaction` for both Sims.
    *   If lock *not* acquired:
        *   Do nothing; the conversation cannot start this cycle. Sims remain available.

**3. Refine `_send_conversation_request` (`interaction.py`):**

*   **File:** `aisim/src/core/interaction.py`
*   **Function:** `_send_conversation_request`
*   **Changes:**
    *   Modify signature to accept `current_time: float` and return `bool` (success/failure).
    *   Assume the Ollama lock is *already held* when called.
    *   Wrap the `ollama_client.request_conversation_response` call in a `try...except`.
    *   If the request is sent successfully (`request_conversation_response` returns true):
        *   Set `speaker.waiting_for_ollama_response = True`.
        *   Set `speaker.conversation_last_response_time = current_time`.
        *   Return `True`.
    *   If the request fails (returns `False` or raises an exception):
        *   Log the error.
        *   Return `False`. (The calling function is responsible for releasing the lock).

**4. Modify `handle_ollama_response` (`interaction.py`):**

*   **File:** `aisim/src/core/interaction.py`
*   **Function:** `handle_ollama_response`
*   **Changes:**
    *   Check if `city.ollama_client_locked` is `True` and release it (`city.ollama_client_locked = False`). Log a warning if it was already `False`.
    *   Set `self.waiting_for_ollama_response = False`.
    *   If `self.is_interacting`:
        *   Set `self.conversation_message = response_text`.
        *   Set `self.conversation_message_timer = self.bubble_display_time`.
        *   Add response to `self.conversation_history`.
        *   Find the `partner`.
        *   If `partner` found:
            *   Add response to `partner.conversation_history`.
            *   Set `partner.is_my_turn_to_speak = True`.
        *   Set `self.is_my_turn_to_speak = False`.
        *   Increment `self.conversation_turns`.
        *   Check for max turns and call `_end_interaction` if reached.
    *   Else (handle regular thought):
        *   Set `self.current_thought = response_text`.
        *   Set `self.thought_timer = THOUGHT_DURATION`.

**5. Modify `conversation_update` (`sim.py`):**

*   **File:** `aisim/src/core/sim.py`
*   **Function:** `conversation_update`
*   **Changes:**
    *   Check for timeouts and max turns (existing logic).
    *   If `self.is_my_turn_to_speak` and not `self.waiting_for_ollama_response`:
        *   Attempt to acquire the `city.ollama_client_locked` flag.
        *   If lock acquired (`city.ollama_client_locked = True`):
            *   Find the `partner`.
            *   If `partner` found:
                *   Call `_send_conversation_request(self, partner, city, all_sims, current_time)`.
                *   If request fails (`_send_conversation_request` returns `False`):
                    *   Release the lock (`city.ollama_client_locked = False`).
                    *   Log failure. Consider ending interaction after multiple failures.
            *   If `partner` not found:
                *   Release the lock (`city.ollama_client_locked = False`).
                *   Call `_end_interaction`.
        *   If lock *not* acquired:
            *   Log that the Sim is waiting for the lock. Do nothing else this cycle.

**6. Refine Bubble Display Logic (`sim.py`):**

*   **File:** `aisim/src/core/sim.py`
*   **Function:** `draw`
*   **Changes:**
    *   Decrement `self.conversation_message_timer` if `self.conversation_message` exists.
    *   Find the `partner`.
    *   Check if the `partner` is currently displaying *their* bubble (`partner.conversation_message` exists and `partner.conversation_message_timer > 0`).
    *   Condition to clear *own* bubble (`self.conversation_message = None`):
        *   Partner *is* displaying their bubble.
        *   Own bubble message exists (`self.conversation_message is not None`).
        *   Own bubble timer has expired (`self.conversation_message_timer <= 0`).
    *   Determine `bubble_text_to_display`: Use `self.conversation_message` if it exists and timer > 0, otherwise fallback to `self.current_thought`.
    *   If `bubble_text_to_display` is set, call `draw_bubble`.

**7. State Management Review:**

*   Ensure `_end_interaction` correctly resets all relevant conversation state for both Sims, including `conversation_message`, `conversation_message_timer`, and `is_interacting`.
*   Modify `_end_interaction` to check if the Sim ending the interaction currently holds the `city.ollama_client_locked` and release it if necessary.

**8. Movement Handling (Clarification):**

*   **Stopping:** Handled in Step 2 (`_initiate_conversation`) by setting `path` and `target` to `None` after the lock is acquired.
*   **Resuming:** Handled implicitly. When `_end_interaction` sets `is_interacting = False`, the main `sim_update` logic will trigger pathfinding on the next cycle if `path` is `None`.

**Mermaid Diagram:**

```mermaid
sequenceDiagram
    participant SimA
    participant SimB
    participant City
    participant OllamaClient

    Note over SimA, SimB: Proximity detected, available

    SimA->>City: Check interaction possibility (SimA, SimB)
    City-->>SimA: OK

    Note over SimA, SimB: Randomly choose SimA first

    SimA->>City: Attempt Ollama Lock
    alt Lock Available
        City->>SimA: Lock Acquired (ollama_client_locked = true)
        Note over SimA, SimB: Set is_interacting=True, stop movement, init state...
        SimA->>OllamaClient: Request conversation response (Turn 1)
        SimA-->>SimA: waiting_for_ollama_response = True
        SimA-->>SimA: Start response timeout timer
    else Lock Busy
        City->>SimA: Lock Busy
        Note over SimA, SimB: Cannot start conversation now. Wait.
    end

    OllamaClient-->>SimA: Receive response (Text A)
    SimA->>City: Release Ollama Lock (ollama_client_locked = false)
    SimA-->>SimA: waiting_for_ollama_response = False
    SimA-->>SimA: conversation_message = Text A
    SimA-->>SimA: Start conversation_message_timer (bubble_display_time)
    SimA-->>SimB: Share history + Text A
    SimA-->>SimB: is_my_turn_to_speak = True
    SimA-->>SimA: is_my_turn_to_speak = False

    Note over SimA: Draw bubble A (timer > 0)

    loop Update Cycles
        alt SimB's turn & NOT waiting & Lock Available
            SimB->>City: Attempt Ollama Lock
            City->>SimB: Lock Acquired (ollama_client_locked = true)
            SimB->>OllamaClient: Request conversation response (Turn 2)
            SimB-->>SimB: waiting_for_ollama_response = True
            SimB-->>SimB: Start response timeout timer
            break Loop
        else SimB's turn & Lock Busy
             Note over SimB: Wait for lock...
        else Not SimB's turn OR Already Waiting
             Note over SimB: Do nothing this cycle...
        end
    end

    OllamaClient-->>SimB: Receive response (Text B)
    SimB->>City: Release Ollama Lock (ollama_client_locked = false)
    SimB-->>SimB: waiting_for_ollama_response = False
    SimB-->>SimB: conversation_message = Text B
    SimB-->>SimB: Start conversation_message_timer (bubble_display_time)
    SimB-->>SimA: Share history + Text B
    SimB-->>SimA: is_my_turn_to_speak = True
    SimB-->>SimB: is_my_turn_to_speak = False

    Note over SimA: Draw Check: SimA bubble timer running? SimB now has message?
    alt SimA timer <= 0 AND SimB has message
        SimA-->>SimA: conversation_message = None (Hide bubble A)
        Note over SimA: Stop drawing bubble A
    else
        Note over SimA: Continue drawing bubble A
    end

    Note over SimB: Draw bubble B (timer > 0)

    Note over SimA, SimB: Process continues until max turns or timeout...
