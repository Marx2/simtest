import math
from typing import List
import logging
logging.basicConfig(level=logging.DEBUG)
from aisim.src.core.configuration import config_manager
import random # Import random

__all__ = ['check_interactions', '_end_interaction'] # Explicitly export functions

INTERACTION_DISTANCE = config_manager.get_entry('simulation.interaction_distance')  # Max distance for interaction (pixels)
ENABLE_TALKING = config_manager.get_entry('simulation.enable_talking', False)
BUBBLE_DISPLAY_TIME = config_manager.get_entry('simulation.bubble_display_time_seconds', 5.0)
MAX_TOTAL_TURNS = config_manager.get_entry('ollama.conversation_max_turns', 4)

def check_interactions(self, all_sims, current_time, city): # Add city parameter
    """Checks for and handles interactions with nearby Sims"""
    ignore_interaction_time = config_manager.get_entry('simulation.ignore_interaction_time', 5.0)
    for other_sim in all_sims:
        if other_sim.sim_id == self.sim_id:
            continue  # Don't interact with self
        # print(f"Sim {self.sim_id}: Checking interaction with Sim {other_sim.sim_id}")

        dist = math.dist((self.x, self.y), (other_sim.x, other_sim.y))
        # print(f"Sim {self.sim_id}: current_time={current_time}, last_interaction_time={self.last_interaction_time}")
        # print(f"Sim {self.sim_id}: distance to Sim {other_sim.sim_id} = {dist}")

        # --- Interaction Start Condition ---
        can_interact_self = not self.is_interacting and (current_time - self.last_interaction_time > ignore_interaction_time)
        can_interact_other = not other_sim.is_interacting and (current_time - other_sim.last_interaction_time > ignore_interaction_time)
        # Initialize relationship if first meeting
        if other_sim.sim_id not in self.relationships:
            self.relationships[other_sim.sim_id] = {"friendship": 0.0, "romance": 0.0}
        if self.sim_id not in other_sim.relationships:
            other_sim.relationships[self.sim_id] = {"friendship": 0.0, "romance": 0.0}

        if dist < INTERACTION_DISTANCE and can_interact_self and can_interact_other and not is_interaction_in_progress(self, all_sims):
            # --- Potential Interaction Start ---
            # Don't stop movement or set is_interacting yet.
            # Check if a conversation is possible first.

            # Prevent overlapping (can happen even if not talking)
            overlap_distance = math.dist((self.x, self.y), (other_sim.x, other_sim.y))
            min_dist = 25 # Slightly increased min distance
            if overlap_distance < min_dist and overlap_distance > 0: # Avoid division by zero
                dx = self.x - other_sim.x
                dy = self.y - other_sim.y
                norm_dx = dx / overlap_distance
                norm_dy = dy / overlap_distance
                move_dist = (min_dist - overlap_distance) / 2
                self.x += norm_dx * move_dist
                self.y += norm_dy * move_dist
                other_sim.x -= norm_dx * move_dist
                other_sim.y -= norm_dy * move_dist

            # --- Initialize Conversation ---
            if ENABLE_TALKING == True:
                initiate_conversation(self, other_sim, city, all_sims, current_time)
            else:
                 self.conversation_history = None
                 other_sim.conversation_history = None
            
        # TODO: Use personality traits to influence interaction chance/outcome

        # --- Post-Interaction Start Logic (Relationship, Memory, Logging) ---
        # This part runs regardless of whether a conversation was started,
        # as long as the interaction condition was met.
        # Store interaction in memory
        # Basic interaction effect: slightly increase friendship
        friendship_increase = 0.01  # Placeholder
        self.relationships[other_sim.sim_id]["friendship"] = min(1.0, self.relationships[other_sim.sim_id]["friendship"] + friendship_increase)
        other_sim.relationships[self.sim_id]["friendship"] = min(1.0, other_sim.relationships[self.sim_id]["friendship"] + friendship_increase)

        interaction_event = {"type": "interaction", "with_sim_id": other_sim.sim_id, "friendship_change": friendship_increase}
        self.memory.append(interaction_event)
        other_sim.memory.append({"type": "interaction", "with_sim_id": self.sim_id, "friendship_change": friendship_increase})

        # Mood boost from positive interaction
        self.mood = min(1.0, self.mood + 0.05)
        other_sim.mood = min(1.0, other_sim.mood + 0.05)

def is_interaction_in_progress(sim1, all_sims):
    """Checks if any Sims are currently interacting. Exclude sim1 and his partner."""
    for sim in all_sims:
        if sim.sim_id == sim1.sim_id or sim.sim_id == sim1.conversation_partner_id:
            continue
        if sim.is_interacting:
            return True
    return False

def _end_interaction(self, city, all_sims: List['Sim']): # Add city parameter
    """Cleans up state at the end of an interaction, releasing the Ollama lock if held."""
    print(f"Sim {self.sim_id}: Ending interaction with partner ID {self.conversation_partner_id}")
    partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)

    # --- Release Ollama Lock if held ---
    # Check if the lock is held *before* resetting state, as state might be needed
    # to determine if this Sim *should* have been holding the lock.
    # Typically, the lock is released in handle_ollama_response, but this handles
    # premature ends (timeouts, errors, max turns).
    if city.ollama_client_locked:
        # It's possible the *partner* was waiting for a response and timed out,
        # or this sim timed out waiting to acquire the lock initially.
        # For simplicity, if _end_interaction is called and the lock is held, release it.
        # A more robust check might involve seeing who *was* waiting or whose turn it was.
        print(f"Sim {self.sim_id}: Releasing Ollama lock during _end_interaction.")
        city.ollama_client_locked = False

    # --- Capture data for romance analysis *before* clearing state ---
    final_history = self.conversation_history[:] if self.conversation_history else None
    sim1_id = self.sim_id
    sim1_name = self.first_name
    sim2_id = None
    sim2_name = None
    if partner: # Check if partner exists before accessing attributes
        sim2_id = partner.sim_id
        sim2_name = partner.first_name
    # --- End Capture ---

    # --- Reset Partner State (if partner exists and was interacting) ---
    if partner and partner.is_interacting:
            partner.is_interacting = False
            partner.talking_with = None # Optional, maybe remove later
            partner.conversation_history = None
            partner.conversation_message = None # Reset conversation bubble message
            partner.conversation_message_timer = 0.0 # Reset conversation bubble timer
            partner.is_my_turn_to_speak = False
            partner.waiting_for_ollama_response = False
            partner.conversation_partner_id = None
            partner.conversation_turns = 0

    # --- Reset Self State ---
    self.is_interacting = False
    self.talking_with = None # Optional, maybe remove later
    self.conversation_history = None
    self.conversation_message = None # Reset conversation bubble message
    self.conversation_message_timer = 0.0 # Reset conversation bubble timer
    self.is_my_turn_to_speak = False
    self.waiting_for_ollama_response = False
    self.conversation_partner_id = None
    self.conversation_turns = 0

    # --- Trigger Romance Analysis ---
    if final_history and sim2_id is not None: # Only analyze if there was history and a valid partner
        try:
            self.ollama_client.request_romance_analysis(
                sim1_id, sim1_name, sim2_id, sim2_name, final_history
            )
            # Add pair to pending analysis lock
            analysis_pair = tuple(sorted((sim1_id, sim2_id))) # Ensure consistent ordering
            city.pending_romance_analysis.add(analysis_pair)
            print(f"Added {analysis_pair} to pending romance analysis.") # Debug
        except AttributeError:
            print(f"ERROR: Sim {sim1_id} could not access ollama_client to request romance analysis.")
    elif not final_history:
        print(f"Skipping romance analysis between {sim1_name} and {sim2_name}: No conversation history.")
    # else: # No need for explicit else, handled by sim2_id check
    #     print(f"Skipping romance analysis for {sim1_name}: Partner was invalid.")

def handle_ollama_response(self, response_text: str, all_sims: List['Sim'], city):
    """Handles a response received from Ollama, releasing the lock and managing conversation state."""
    print(f"Sim {self.sim_id}: Received Ollama response: '{response_text}'")

    # --- Release Ollama Lock ---
    # This function is called when *any* Ollama response arrives (conversation).
    # The lock should only be held during conversation request/response cycles.
    # Release the lock if this response corresponds to the end of a conversation turn.
    # Note: The lock is acquired in _initiate_conversation or conversation_update.
    # The lock should be released here, after receiving the response for that turn.
    if self.waiting_for_ollama_response and self.is_interacting: # Check if we were actually waiting for a *conversation* response
        if city.ollama_client_locked:
            city.ollama_client_locked = False
            print(f"Sim {self.sim_id}: Released Ollama lock after receiving response.")
        else:
            # This case might happen if the interaction ended prematurely elsewhere
            logging.warning(f"Sim {self.sim_id}: Received conversation response, but Ollama lock was already released.")

    # Always mark as no longer waiting, regardless of lock state or interaction type
    self.waiting_for_ollama_response = False

    if self.is_interacting and self.conversation_partner_id is not None:
        # --- Handle Conversation Response ---
        self.conversation_message = response_text

        # Add to history
        new_entry = {"speaker": self.first_name, "line": response_text}
        if self.conversation_history is None: self.conversation_history = []
        self.conversation_history.append(new_entry)

        # Update partner
        partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
        if partner:
            if partner.conversation_history is None: partner.conversation_history = []
            partner.conversation_history.append(new_entry) # Share history
            # partner.is_my_turn_to_speak = True # It's partner's turn now
            partner.waiting_for_ollama_response = False # Partner isn't waiting yet (will wait on their update cycle)
            # partner.conversation_last_response_time = current_time # Don't reset partner's timer here
            print(f"Sim {self.sim_id}: Passed turn to {partner.sim_id}")
        else:
            print(f"Sim {self.sim_id}: ERROR - Partner {self.conversation_partner_id} not found during response handling! Ending interaction.")
            _end_interaction(self, city, all_sims) # End interaction if partner vanished

        # Update self state *after* processing partner
        # self.is_my_turn_to_speak = False # Not my turn anymore
        self.conversation_turns += 1 # Increment turn counter *after* successfully speaking
        # self.conversation_last_response_time = current_time # Don't reset self timer here, used for timeout *before* speaking

        # Check if max turns reached *after* this turn
        # Calculate max turns *per sim* based on total turns. Each sim speaks roughly half the total turns.
        # Use ceil division equivalent to handle odd max_total_turns gracefully: (N + 1) // 2
        max_turns_per_sim = (MAX_TOTAL_TURNS + 1) // 2

        if self.conversation_turns >= max_turns_per_sim:
            print(f"Sim {self.sim_id}: Reached max turns ({self.conversation_turns}/{max_turns_per_sim}) in conversation with {self.conversation_partner_id}. Ending interaction.")
            _end_interaction(self, city, all_sims) # End interaction after reaching max turns

    elif not self.is_interacting:
        # Ensure conversation bubble is cleared while not interacting
        self.conversation_message = None
        self.conversation_message_timer = 0.0


def initiate_conversation(initiator_sim, other_sim, city, all_sims, current_time):
    """Handles the conversation initiation logic between two Sims, respecting the Ollama lock."""
    # Global Conversation Lock Check
    if is_interaction_in_progress(initiator_sim, all_sims):
        return

    # Pending Romance Analysis Lock Check (Existing)
    analysis_pair = tuple(sorted((initiator_sim.sim_id, other_sim.sim_id))) # Ensure consistent ordering
    if analysis_pair in city.pending_romance_analysis:
        # print(f"Conversation between {initiator_sim.sim_id} and {other_sim.sim_id} blocked: Pending romance analysis.") # Debug
        return # Don't start conversation if analysis is pending for this pair

    # Decide who speaks first *before* trying the lock
    if random.choice([True, False]):
        first_speaker = initiator_sim
        second_speaker_listener = other_sim
    else:
        first_speaker = other_sim
        second_speaker_listener = initiator_sim

    # --- Attempt to acquire the Ollama client lock ---
    if not city.ollama_client_locked:
        # Lock is available, acquire it and proceed
        city.ollama_client_locked = True
        print(f"Sim {first_speaker.sim_id}: Acquired Ollama lock, initiating conversation with {second_speaker_listener.sim_id}")

        # Stop movement
        first_speaker.path = None
        first_speaker.target = None
        first_speaker.path_index = 0
        second_speaker_listener.path = None
        second_speaker_listener.target = None
        second_speaker_listener.path_index = 0

        # Set interaction state for both sims
        first_speaker.is_interacting = True
        second_speaker_listener.is_interacting = True
        first_speaker.last_interaction_time = current_time # Update interaction time
        second_speaker_listener.last_interaction_time = current_time

        # Initialize conversation details
        first_speaker.conversation_history = []
        second_speaker_listener.conversation_history = []
        first_speaker.conversation_partner_id = second_speaker_listener.sim_id
        second_speaker_listener.conversation_partner_id = first_speaker.sim_id
        first_speaker.conversation_turns = 0
        second_speaker_listener.conversation_turns = 0
        first_speaker.waiting_for_ollama_response = False # Will be set by _send_request
        second_speaker_listener.waiting_for_ollama_response = False
        first_speaker.conversation_last_response_time = current_time
        second_speaker_listener.conversation_last_response_time = current_time

        # Set turns
        first_speaker.is_my_turn_to_speak = True
        second_speaker_listener.is_my_turn_to_speak = False

        # --- Send the first conversation request ---
        # Note: We assume _send_conversation_request will be updated per Step 3 to accept
        # (speaker, partner, city, all_sims, current_time) and return bool
        request_successful = _send_conversation_request(first_speaker, second_speaker_listener, current_time)

        if not request_successful:
            # Request failed, release lock and end interaction immediately
            print(f"Sim {first_speaker.sim_id}: Initial conversation request failed. Releasing lock and ending interaction.")
            city.ollama_client_locked = False # Release the lock
            # End interaction for both (this should handle cleanup including removing from active_partners)
            _end_interaction(first_speaker, city, all_sims)
            _end_interaction(second_speaker_listener, city, all_sims)
        else:
            # Request sent successfully
            print(f"Sim {first_speaker.sim_id} speaks first. Initial request sent.")

    else:
        # Ollama lock is busy, cannot start conversation this cycle
        # print(f"Sim {initiator_sim.sim_id}: Could not initiate conversation with {other_sim.sim_id}. Ollama lock busy.")
        # Do nothing - sims remain available for other actions or future interaction attempts
        pass

# Note: The 'self' parameter is removed as this function operates on specific speaker/listener pairs
# and doesn't need the instance context in the same way _initiate_conversation might have.
# The necessary 'self' context (like ollama_client, relationships) comes from the 'speaker' object.
# Note: The 'self' parameter is removed as this function operates on specific speaker/listener pairs
# and doesn't need the instance context in the same way _initiate_conversation might have.
# The necessary 'self' context (like ollama_client, relationships) comes from the 'speaker' object.
def _send_conversation_request(speaker, listener, current_time: float) -> bool:
    """
    Sends conversation request to Ollama client for the 'speaker'.
    Assumes the Ollama lock is already held by the calling function.
    Returns True if the request was successfully sent, False otherwise.
    """
    # Get the romance level of the speaker towards the listener
    relationship_data = speaker.relationships.get(listener.sim_id, {})
    romance_level = relationship_data.get("romance", 0.0) # Default to 0.0
    # print(f"Sim {speaker.sim_id}: Romance towards {listener.first_name} for request = {romance_level:.2f}") # Debug

    try:
        # Make the request using the speaker's client
        request_sent_successfully = speaker.ollama_client.request_conversation_response(
            speaker.sim_id,
            speaker.first_name,
            listener.first_name,
            speaker.conversation_history, # Send speaker's current view of history
            speaker.personality_description,
            romance_level # Pass the romance level
        )

        if request_sent_successfully:
            # Update speaker state on successful request dispatch
            speaker.waiting_for_ollama_response = True
            speaker.conversation_last_response_time = current_time # Record time request was sent
            print(f"Sim {speaker.sim_id}: Conversation request sent. Waiting for response. Turn: {speaker.conversation_turns}")
            return True
        else:
            # The client itself indicated failure (e.g., queue full, internal error)
            logging.error(f"Sim {speaker.sim_id}: Ollama client failed to send conversation request (returned False).")
            # DO NOT release lock here - caller handles it based on False return
            return False

    except AttributeError as e:
        # Handle cases where ollama_client might be missing (shouldn't happen ideally)
        logging.error(f"Sim {speaker.sim_id}: Error accessing ollama_client: {e}")
        # DO NOT release lock here - caller handles it based on False return
        return False
    except Exception as e:
        # Catch any other unexpected errors during the request
        logging.error(f"Sim {speaker.sim_id}: Unexpected error sending conversation request: {e}")
        # DO NOT release lock here - caller handles it based on False return
        return False
