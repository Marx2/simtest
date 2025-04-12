import pygame
import pygame_gui
import logging
from typing import Dict, Set, TYPE_CHECKING
from aisim.src.core.text import wrap_text  # Import the wrapping function

# Use TYPE_CHECKING to avoid circular imports for type hints
if TYPE_CHECKING:
    from aisim.src.core.sim import Sim
    from pygame_gui import UIManager
    from pygame_gui.elements import UILabel

MAX_BUBBLE_WIDTH = 180  # Max width in pixels for the bubble content


def manage_conversation_bubbles(
    sims_dict: Dict[str, 'Sim'],
    active_bubble_labels: Dict[str, 'UILabel'],
    ui_manager: 'UIManager'
):
    """Creates, updates, positions, and removes conversation bubble UILabels."""

    sim_ids_with_active_bubbles: Set[str] = set()  # Track sims that *should* have a bubble this frame

    for sim_id, sim in sims_dict.items():
        bubble_text = sim.conversation_message
        bubble_timer = sim.conversation_message_timer

        if bubble_text and bubble_timer > 0:
            sim_ids_with_active_bubbles.add(sim_id)
            sim_pos = (int(sim.x), int(sim.y))
            # Use sprite_height if available, otherwise default
            sprite_height = getattr(sim, 'sprite_height', 32)
            bubble_anchor_y = sim_pos[1] - sprite_height // 2 - 5  # Position above sprite

            # Get the font used by the bubble style for wrapping/measuring
            # This might require accessing the theme data more directly if just manager isn't enough
            # For simplicity, let's assume we can get a default font or the label uses one we can access
            # A more robust way might involve passing the font or theme object
            try:
                # Attempt to get font details from the theme for the specific class
                # Note: This specific method might not exist, adjust based on pygame_gui capabilities
                # Fallback to a default font if theme access is complex/unavailable
                bubble_font = ui_manager.get_theme().get_font('@sim_bubble')
            except Exception:
                # Fallback if theme font access fails
                bubble_font = pygame.font.Font(None, 14)  # Default fallback
                logging.warning("Could not get bubble font from theme, using fallback.")

            if sim_id in active_bubble_labels:
                # --- Update Existing Bubble ---
                bubble_label = active_bubble_labels[sim_id]
                current_label_text = bubble_label.text  # Get text with potential newlines

                # Wrap the *original* bubble_text for comparison and potential update
                wrapped_lines = wrap_text(bubble_text, bubble_font, MAX_BUBBLE_WIDTH)
                new_wrapped_text = "\n".join(wrapped_lines)

                if current_label_text != new_wrapped_text:
                    logging.debug(f"Updating bubble text for {sim_id}")
                    bubble_label.set_text(new_wrapped_text)
                    # Allow the UIManager to update the label's size based on new text
                    # We only need to reposition it based on its new rect later

                # Reposition based on current sim location and label's current rect
                # Get the *current* rect after potential text update and manager processing
                current_rect = bubble_label.get_relative_rect()
                current_rect.midbottom = (sim_pos[0], bubble_anchor_y)
                bubble_label.set_relative_position(current_rect.topleft)  # Set position based on midbottom anchor
                bubble_label.show()  # Ensure it's visible

            else:
                # --- Create New Bubble ---
                logging.info(f"Creating bubble for {sim.full_name}: {bubble_text}")

                # Wrap the text first
                wrapped_lines = wrap_text(bubble_text, bubble_font, MAX_BUBBLE_WIDTH)
                wrapped_text = "\n".join(wrapped_lines)

                # Create the label with wrapped text.
                # Use a minimal rect initially; pygame_gui will resize it.
                initial_rect = pygame.Rect(0, 0, -1, -1)  # Auto-sizing rect

                # Create the label, using object_id for class styling
                bubble_label = pygame_gui.elements.UILabel(
                    relative_rect=initial_rect,
                    text=wrapped_text,
                    manager=ui_manager,
                    object_id="@sim_bubble"  # Use class ID in object_id for theming
                )
                # Now that the label exists and has its size calculated by pygame_gui,
                # get its actual rect and position it correctly.
                label_rect = bubble_label.get_relative_rect()
                label_rect.midbottom = (sim_pos[0], bubble_anchor_y)
                bubble_label.set_relative_position(label_rect.topleft)  # Set final position

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