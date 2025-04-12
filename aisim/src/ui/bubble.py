import pygame
import pygame_gui
import logging
from typing import Dict, Set, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports for type hints
if TYPE_CHECKING:
    from aisim.src.core.sim import Sim
    from pygame_gui import UIManager
    from pygame_gui.elements import UILabel

def manage_conversation_bubbles(
    sims_dict: Dict[str, 'Sim'],
    active_bubble_labels: Dict[str, 'UILabel'],
    ui_manager: 'UIManager'
):
    """Creates, updates, positions, and removes conversation bubble UILabels."""

    sim_ids_with_active_bubbles: Set[str] = set() # Track sims that *should* have a bubble this frame

    for sim_id, sim in sims_dict.items():
        bubble_text = sim.conversation_message
        bubble_timer = sim.conversation_message_timer

        if bubble_text and bubble_timer > 0:
            sim_ids_with_active_bubbles.add(sim_id)
            sim_pos = (int(sim.x), int(sim.y))
            # Use sprite_height if available, otherwise default
            sprite_height = getattr(sim, 'sprite_height', 32)
            bubble_anchor_y = sim_pos[1] - sprite_height // 2 - 5 # Position above sprite

            if sim_id in active_bubble_labels:
                # --- Update Existing Bubble ---
                bubble_label = active_bubble_labels[sim_id]
                if bubble_label.text != bubble_text: # Update text if it changed
                     bubble_label.set_text(bubble_text)
                # Recalculate position based on current sim location and potential text change
                # We need to estimate width based on text to center it roughly
                # This is imperfect as label size adjusts after manager update.
                # A fixed width or using a different element might be better for precise centering.
                estimated_width = len(bubble_text) * 8 # Rough estimate
                bubble_rect = pygame.Rect(0, 0, estimated_width, 30) # Temp rect for positioning
                bubble_rect.midbottom = (sim_pos[0], bubble_anchor_y)
                bubble_label.set_relative_position(bubble_rect.topleft)
                bubble_label.show() # Ensure it's visible

            else:
                # --- Create New Bubble ---
                logging.info(f"Creating bubble for {sim.full_name}: {bubble_text}")
                # Estimate initial size and position
                estimated_width = len(bubble_text) * 8 + 20 # Add padding estimate
                estimated_height = 30 # Fixed height guess for label
                bubble_rect = pygame.Rect(0, 0, estimated_width, estimated_height)
                bubble_rect.midbottom = (sim_pos[0], bubble_anchor_y)

                # Create the label with a class_id for styling
                bubble_label = pygame_gui.elements.UILabel(
                    relative_rect=bubble_rect,
                    text=bubble_text,
                    manager=ui_manager,
                    object_id=f"#sim_bubble_{sim_id}", # Keep unique object ID
                    class_id="@sim_bubble" # Add class ID for theming
                )
                active_bubble_labels[sim_id] = bubble_label
        # else: Bubble should not be shown for this sim

    # --- Clean up expired / unused bubbles ---
    sim_ids_to_remove = []
    for sim_id, bubble_label in active_bubble_labels.items():
        if sim_id not in sim_ids_with_active_bubbles:
            logging.info(f"Killing bubble for Sim ID {sim_id}")
            bubble_label.kill()
            sim_ids_to_remove.append(sim_id)

    for sim_id in sim_ids_to_remove:
        del active_bubble_labels[sim_id]
    # --- End Conversation Bubble Management ---