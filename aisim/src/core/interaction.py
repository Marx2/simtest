import math
import time
from typing import List
import logging
logging.basicConfig(level=logging.DEBUG)
from aisim.src.core.configuration import config_manager
import json
import random # Import random

__all__ = ['check_interactions', '_end_interaction'] # Explicitly export functions

INTERACTION_DISTANCE = config_manager.get_entry('simulation.interaction_distance')  # Max distance for interaction (pixels)
THOUGHT_DURATION = config_manager.get_entry('simulation.thought_duration')  # Seconds to display thought bubble

def check_interactions(self, all_sims, logger, current_time, city): # Add city parameter
    """Checks for and handles interactions with nearby Sims, logging them."""
    INTERACTION_COOLDOWN = 1.0  # Minimum time between interactions (seconds)
    ignore_interaction_time = config_manager.get_entry('simulation.ignore_interaction_time', 5.0)
    # if logger:
    #     print(f"Sim {self.sim_id} checking interactions, enable_talking={self.enable_talking}, is_interacting={self.is_interacting}")
    # print(f"Sim {self.sim_id}: Checking interactions, is_interacting={self.is_interacting}")
    for other_sim in all_sims:
        if other_sim.sim_id == self.sim_id:
            continue  # Don't interact with self
        # print(f"Sim {self.sim_id}: Checking interaction with Sim {other_sim.sim_id}")

        dist = math.dist((self.x, self.y), (other_sim.x, other_sim.y))
        # print(f"Sim {self.sim_id}: current_time={current_time}, last_interaction_time={self.last_interaction_time}")
        # print(f"Sim {self.sim_id}: distance to Sim {other_sim.sim_id} = {dist}")
        # print(f"Sim in distance: {(dist < INTERACTION_DISTANCE)}, time: {(current_time - self.last_interaction_time)}, >= {INTERACTION_COOLDOWN}")

        # --- Interaction Start Condition ---
        can_interact_self = not self.is_interacting and (current_time - self.last_interaction_time > ignore_interaction_time)
        can_interact_other = not other_sim.is_interacting and (current_time - other_sim.last_interaction_time > ignore_interaction_time)

        if dist < INTERACTION_DISTANCE and can_interact_self and can_interact_other:
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
            # Prevent overlapping
            # (Keep the existing overlap prevention logic)
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
            if self.enable_talking and other_sim.enable_talking:
                _initiate_conversation(self, other_sim, city, all_sims, current_time)

            # If talking is disabled, or if the global lock prevented the conversation:
            # The sims might still be close enough to trigger the initial `if dist < INTERACTION_DISTANCE...`
            # but we don't want them to get stuck in `is_interacting = True` if no conversation happened.
            # The code now correctly avoids setting `is_interacting = True` unless the conversation lock passes.
            # If talking was disabled from the start:
            elif not self.enable_talking or not other_sim.enable_talking:
                 # Mark as non-talking interaction (if needed for other logic)
                 # but DO NOT set is_interacting = True here.
                 self.conversation_history = None
                 other_sim.conversation_history = None

        # TODO: Use personality traits to influence interaction chance/outcome

        # Initialize relationship if first meeting
        if other_sim.sim_id not in self.relationships:
            self.relationships[other_sim.sim_id] = {"friendship": 0.0, "romance": 0.0}
        if self.sim_id not in other_sim.relationships:
            other_sim.relationships[self.sim_id] = {"friendship": 0.0, "romance": 0.0}

        # Basic interaction effect: slightly increase friendship
        friendship_increase = 0.01  # Placeholder
        self.relationships[other_sim.sim_id]["friendship"] = min(1.0, self.relationships[other_sim.sim_id]["friendship"] + friendship_increase)
        other_sim.relationships[self.sim_id]["friendship"] = min(1.0, other_sim.relationships[self.sim_id]["friendship"] + friendship_increase)

        # --- Post-Interaction Start Logic (Relationship, Memory, Logging) ---
        # This part runs regardless of whether a conversation was started,
        # as long as the interaction condition was met.
        # Store interaction in memory
        interaction_event = {"type": "interaction", "with_sim_id": other_sim.sim_id, "friendship_change": friendship_increase}
        self.memory.append(interaction_event)
        other_sim.memory.append({"type": "interaction", "with_sim_id": self.sim_id, "friendship_change": friendship_increase})

        # Log interaction
        if logger:
            logger.log_interaction(current_time, self.sim_id, other_sim.sim_id, friendship_increase)
        # Mood boost from positive interaction
        self.mood = min(1.0, self.mood + 0.05)
        other_sim.mood = min(1.0, other_sim.mood + 0.05)

def _end_interaction(self, city, all_sims: List['Sim']): # Add city parameter
    """Cleans up state at the end of an interaction."""
    # print(f"Sim {self.sim_id}: Ending interaction with {self.conversation_partner_id}")
    partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)

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

    if partner and partner.is_interacting: # Now clear partner state if valid
            partner.is_interacting = False
            partner.talking_with = None
            partner.conversation_history = None
            partner.is_my_turn_to_speak = False
            partner.waiting_for_ollama_response = False
            partner.conversation_partner_id = None
            partner.conversation_turns = 0
            partner.interaction_timer = 0.0 # Reset partner timer too
            # Remove partner from active conversations
            if partner.sim_id in city.active_conversation_partners:
                city.active_conversation_partners.remove(partner.sim_id)
                # print(f"Sim {partner.sim_id} removed from active conversations.")

    self.is_interacting = False
    self.talking_with = None # Keep talking_with for compatibility? Maybe remove.
    self.conversation_history = None
    self.is_my_turn_to_speak = False
    self.waiting_for_ollama_response = False
    self.conversation_partner_id = None
    self.conversation_turns = 0
    self.interaction_timer = 0.0 # Reset timer

    # Remove self from active conversations
    if self.sim_id in city.active_conversation_partners:
        city.active_conversation_partners.remove(self.sim_id)
        # print(f"Sim {self.sim_id} removed from active conversations.")

    # --- Trigger Romance Analysis ---
    if final_history and sim2_id is not None: # Only analyze if there was history and a valid partner
        try:
            self.ollama_client.request_romance_analysis(
                sim1_id, sim1_name, sim2_id, sim2_name, final_history
            )
        except AttributeError:
            print(f"ERROR: Sim {sim1_id} could not access ollama_client to request romance analysis.")
    elif not final_history:
        print(f"Skipping romance analysis between {sim1_name} and {sim2_name}: No conversation history.")
    # else: # No need for explicit else, handled by sim2_id check
    #     print(f"Skipping romance analysis for {sim1_name}: Partner was invalid.")

def handle_ollama_response(self, response_text: str, current_time: float, all_sims: List['Sim'], city):
    """Handles a response received from Ollama."""
    print(f"Sim {self.sim_id}: Received Ollama response: '{response_text}'")
    self.waiting_for_ollama_response = False # No longer waiting

    if self.is_interacting and self.conversation_partner_id is not None:
        # --- Handle Conversation Response ---
        # Use the new attributes for conversation messages
        self.conversation_message = response_text
        self.conversation_message_timer = self.bubble_display_time # Use configured duration
        # self.current_thought = None # Clear regular thought if starting conversation response? Optional.

        # Add to history
        new_entry = {"speaker": self.first_name, "line": response_text}
        if self.conversation_history is None: self.conversation_history = [] # Should be initialized, but safety check
        self.conversation_history.append(new_entry)

        # Update partner
        partner = self._find_sim_by_id(self.conversation_partner_id, all_sims)
        if partner:
            if partner.conversation_history is None: partner.conversation_history = []
            partner.conversation_history.append(new_entry) # Share history
            partner.is_my_turn_to_speak = True # It's partner's turn now
            partner.waiting_for_ollama_response = False # Partner isn't waiting yet
            partner.conversation_last_response_time = current_time # Update partner's timer too, maybe? Or just initiator? Let's update both.
            print(f"Sim {self.sim_id}: Passed turn to {partner.sim_id}")
        else:
            print(f"Sim {self.sim_id}: ERROR - Partner {self.conversation_partner_id} not found during response handling!")
            _end_interaction(self, city, all_sims)

        # Update self
        self.is_my_turn_to_speak = False # Not my turn anymore
        self.conversation_turns += 1 # Increment turn counter *after* speaking
        self.conversation_last_response_time = current_time # Reset timeout timer

        # Check if max turns reached *after* this turn
        max_total_turns = config_manager.get_entry('ollama.conversation_max_turns', 4) # Use default consistent with config
        max_turns_per_sim = max_total_turns // 2 # Integer division for turns per sim
        if self.conversation_turns >= max_turns_per_sim:
                print(f"Sim {self.sim_id}: Conversation with {self.conversation_partner_id} reached max turns ({max_total_turns} total) after response.")
                _end_interaction(self, city, all_sims)

    else:
        # --- Handle Regular Thought ---
        self.current_thought = response_text
        self.thought_timer = THOUGHT_DURATION


def _initiate_conversation(self, other_sim, city, all_sims, current_time):
    """Handles the conversation initiation logic between two Sims."""
    # Global Conversation Lock Check
    if self.sim_id in city.active_conversation_partners or other_sim.sim_id in city.active_conversation_partners:
        return

    # Lock Conversation Globally & Start Interaction State
    print(f"Sim {self.sim_id}: Starting interaction with Sim {other_sim.sim_id}")

    # Stop movement
    self.path = None
    self.target = None
    self.path_index = 0
    other_sim.path = None
    other_sim.target = None
    other_sim.path_index = 0

    # Set interaction state
    self.is_interacting = True
    other_sim.is_interacting = True
    self.interaction_timer = 0.0
    other_sim.interaction_timer = 0.0
    self.last_interaction_time = current_time
    other_sim.last_interaction_time = current_time

    # Add to global lock
    city.active_conversation_partners.add(self.sim_id)
    city.active_conversation_partners.add(other_sim.sim_id)
    # print(f"Sim {self.sim_id} & {other_sim.sim_id}: Locked conversation. Active: {city.active_conversation_partners}")

    # Initialize conversation details
    print(f"Sim {self.sim_id} & {other_sim.sim_id}: Initializing conversation details.")
    self.conversation_history = []
    other_sim.conversation_history = []
    self.conversation_partner_id = other_sim.sim_id
    other_sim.conversation_partner_id = self.sim_id
    self.conversation_turns = 0
    other_sim.conversation_turns = 0
    self.waiting_for_ollama_response = False
    other_sim.waiting_for_ollama_response = False
    self.conversation_last_response_time = current_time
    other_sim.conversation_last_response_time = current_time

    # Decide who speaks first
    if random.choice([True, False]):
        first_speaker = self
        second_speaker_listener = other_sim
    else:
        first_speaker = other_sim
        second_speaker_listener = self

    first_speaker.is_my_turn_to_speak = True
    second_speaker_listener.is_my_turn_to_speak = False

    print(f"Sim {first_speaker.sim_id} speaks first.")
    _send_conversation_request(self, first_speaker, second_speaker_listener, city, all_sims)

def _send_conversation_request(self, first_speaker, second_speaker_listener, city, all_sims):
    """Sends conversation request to Ollama client."""
    # Get the romance level of the first speaker towards the listener
    relationship_data = first_speaker.relationships.get(second_speaker_listener.sim_id, {})
    romance_level = relationship_data.get("romance", 0.0) # Default to 0.0
    print(f"Sim {first_speaker.sim_id}: Romance towards {second_speaker_listener.first_name} for initial request = {romance_level:.2f}") # Debug

    request_sent = first_speaker.ollama_client.request_conversation_response(
        first_speaker.sim_id,
        first_speaker.first_name,
        second_speaker_listener.first_name,
        first_speaker.conversation_history,
        first_speaker.personality_description,
        romance_level # Pass the romance level
    )
    if request_sent:
        first_speaker.waiting_for_ollama_response = True
        first_speaker.conversation_last_response_time = time.time()
        print(f"Sim {first_speaker.sim_id}: Initial conversation request sent. Turn: {first_speaker.conversation_turns}")
    else:
        # print(f"Sim {first_speaker.sim_id}: FAILED to send initial conversation request!")
        _end_interaction(self, city, all_sims)
        _end_interaction(second_speaker_listener, city, all_sims)

def _generate_thought(self, situation_description):
    """Requests non-conversational thought generation asynchronously using Ollama."""
    # Only generate if talking is enabled AND not currently in a conversation
    if self.enable_talking and not self.is_interacting:
        print(f"Sim {self.sim_id}: Requesting standard thought for: {situation_description}")
        request_sent = self.ollama_client.request_thought_generation(self.sim_id, situation_description)
        if not request_sent:
            print(f"Sim {self.sim_id}: Standard thought generation request ignored (already active).")
