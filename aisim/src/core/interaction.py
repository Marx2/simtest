import math
import json
import random # Import random

INTERACTION_DISTANCE = 40  # Max distance for interaction (pixels)

def check_interactions(self, all_sims, logger, current_time):
    """Checks for and handles interactions with nearby Sims, logging them."""
    INTERACTION_COOLDOWN = 1.0  # Minimum time between interactions (seconds)
    # Load configuration
    with open('aisim/config/config.json', 'r') as config_file:
        config = json.load(config_file)
    ignore_interaction_time = config['simulation'].get('ignore_interaction_time', 5.0)  # Default to 5.0 if not found
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
            # --- Start Interaction ---
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
            self.last_interaction_time = current_time # Update last interaction time
            other_sim.last_interaction_time = current_time

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
                print(f"Sim {self.sim_id} & {other_sim.sim_id}: Initializing conversation.")
                # Reset conversation state for both
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

                # Decide who speaks first (randomly)
                if random.choice([True, False]):
                    first_speaker = self
                    second_speaker = other_sim
                else:
                    first_speaker = other_sim
                    second_speaker = self

                first_speaker.is_my_turn_to_speak = True
                second_speaker.is_my_turn_to_speak = False

                print(f"Sim {first_speaker.sim_id} speaks first.")

                # Request the first response
                request_sent = first_speaker.ollama_client.request_conversation_response(
                    first_speaker.sim_id,
                    first_speaker.first_name,
                    second_speaker.first_name,
                    first_speaker.conversation_history # Initially empty
                )
                if request_sent:
                    first_speaker.waiting_for_ollama_response = True
                    first_speaker.conversation_last_response_time = current_time # Start timeout timer
                    print(f"Sim {first_speaker.sim_id}: Initial conversation request sent.")
                else:
                    print(f"Sim {first_speaker.sim_id}: FAILED to send initial conversation request!")
                    # If the first request fails, maybe end the interaction immediately?
                    self._end_interaction(all_sims) # Assuming _end_interaction exists on Sim
                    other_sim._end_interaction(all_sims) # End for both

            else:
                 # If talking is disabled, maybe just have a short interaction timer like before?
                 # Or just end immediately? For now, let's assume they just stand briefly.
                 # The Sim.update logic will need a way to end non-talking interactions.
                 # Let's add a flag or check conversation_history is None in Sim.update end logic.
                 self.conversation_history = None # Explicitly mark as non-talking interaction
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
