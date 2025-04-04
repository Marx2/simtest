import math

INTERACTION_DISTANCE = 40  # Max distance for interaction (pixels)

def check_interactions(self, all_sims, logger, current_time):
    """Checks for and handles interactions with nearby Sims, logging them."""
    INTERACTION_COOLDOWN = 1.0  # Minimum time between interactions (seconds)
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

        if dist < INTERACTION_DISTANCE and current_time - self.last_interaction_time >= INTERACTION_COOLDOWN and not (self.is_interacting or other_sim.is_interacting):
            # Stop both sims upon interaction
            print(f"Sim {self.sim_id}: Interacting with Sim {other_sim.sim_id}")
            self.path = None
            self.target = None
            self.path_index = 0
            other_sim.path = None
            other_sim.target = None
            other_sim.path_index = 0
            self.is_interacting = True
            other_sim.is_interacting = True
            self.interaction_timer = 0.0
            other_sim.interaction_timer = 0.0
            self.talking_with = other_sim.sim_id
            other_sim.talking_with = self.sim_id
            # Update last interaction time
            self.last_interaction_time = current_time
            other_sim.last_interaction_time = current_time
            
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

        # Generate thoughts about the interaction
        if self.enable_talking and self.can_talk:
            situation_self = f"just met {other_sim.first_name}..."  # Use first name for prompt
            situation_other = f"just met {self.first_name}..."
            self._generate_thought(situation_self)
            # Note: This might trigger thoughts simultaneously, potentially overwriting quickly.
            # A more robust system might queue thoughts or handle conversations.
            other_sim._generate_thought(situation_other)
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
