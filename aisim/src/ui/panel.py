import pygame
import pygame_gui
from typing import Dict, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports for type hints
if TYPE_CHECKING:
    from aisim.src.core.sim import Sim
    from pygame_gui import UIManager

# Import necessary functions (assuming mood is still needed here)
from aisim.src.core.mood import get_mood_description

def create_or_focus_sim_details_window(
    sim: 'Sim',
    manager: 'UIManager',
    sims_dict: Dict[str, 'Sim'],
    active_detail_windows: Dict[str, pygame_gui.elements.UIWindow],
    SCREEN_WIDTH: int,
    SCREEN_HEIGHT: int
):
    """Creates a new Sim detail window or focuses an existing one."""
    window_object_id = f"#sim_window_{sim.sim_id}"

    # Check if window already exists
    existing_window = None
    # Need a reliable way to find the window by object ID if manager allows it,
    # otherwise iterate through tracked windows. Let's use our tracking dict.
    if sim.sim_id in active_detail_windows:
         existing_window = active_detail_windows[sim.sim_id]
         # Check if the window actually still exists in the UI manager
         # (Could have been closed unexpectedly - though our close handler should prevent this)
         # A more robust check might involve querying the manager, but this is simpler for now.
         if existing_window:
             existing_window.focus() # Bring to front
             print(f"Focused existing window for {sim.full_name}")
             return # Don't create a new one

    # --- Create New Window ---
    print(f"Creating new window for {sim.full_name}")
    window_width = 450
    window_height = 450
    # Center the window initially
    window_x = (SCREEN_WIDTH - window_width) // 2
    window_y = (SCREEN_HEIGHT - window_height) // 2
    window_rect = pygame.Rect(window_x, window_y, window_width, window_height)

    # --- Format Content as HTML ---
    # Portrait (if available) - Requires image loading and embedding, complex for basic HTML.
    # Let's skip the portrait image in the text box for now. A dedicated image element might be better.

    mood_str = get_mood_description(sim.mood)
    basic_info = (
        f"<b>Name:</b> {sim.full_name}<br>"
        f"<b>ID:</b> {sim.sim_id[:8]}...<br>"
        f"<b>Sex:</b> {sim.sex}<br>"
        f"<b>Mood:</b> {mood_str} ({sim.mood:.2f})<br>"
        f"<b>Position:</b> ({sim.x:.1f}, {sim.y:.1f})<br>"
        f"<b>Tile:</b> {sim.current_tile}<br><br>"
    )

    personality_html = sim.personality_description.replace('\n', '<br>')
    personality_info = f"<b>Personality:</b><br>{personality_html}<br><br>"

    romance_info = "<b>Romance:</b><br>"
    if sim.relationships:
        sorted_relationships = sorted(sim.relationships.items(), key=lambda item: item[1].get('romance', 0.0), reverse=True)
        for other_id, values in sorted_relationships:
            other_sim = sims_dict.get(other_id)
            other_name = other_sim.full_name if other_sim else f"Unknown ({other_id[:6]})"
            friendship = values.get('friendship', 0.0)
            romance = values.get('romance', 0.0)
            romance_info += f"- {other_name}: F={friendship:.1f}, R={romance:.1f}<br>"
    else:
        romance_info += "- None<br>"
    romance_info += "<br>" # Add space after section

    conversation_history = "<b>Conversation History:</b><br>"
    if sim.conversation_history:
        for entry in sim.conversation_history:
            speaker = entry.get('speaker', 'Unknown')
            line = entry.get('line', '')
            # Basic HTML escaping (replace < and >) - more robust escaping might be needed
            line_escaped = line.replace('<', '<').replace('>', '>')
            conversation_history += f"<i>{speaker}:</i> {line_escaped}<br>"
    else:
        conversation_history += "- None<br>"

    full_html_content = basic_info + personality_info + romance_info + conversation_history

    # Create the window
    new_window = pygame_gui.elements.UIWindow(
        rect=window_rect,
        manager=manager,
        window_display_title=f"Details: {sim.full_name}",
        object_id=pygame_gui.core.ObjectID(object_id=window_object_id, class_id="@sim_details_window") # Use ObjectID
    )

    # Create the text box inside the window
    # Make the text box slightly smaller than the window's client area
    text_box_rect = pygame.Rect(0, 0, window_width - 30, window_height - 60) # Adjust padding as needed
    text_box_rect.center = (window_width // 2, window_height // 2 - 10) # Center within window approx

    pygame_gui.elements.UITextBox(
        relative_rect=text_box_rect,
        html_text=full_html_content,
        manager=manager,
        container=new_window, # Place inside the window
        anchors={'left': 'left', 'right': 'right', 'top': 'top', 'bottom': 'bottom'} # Anchor to window edges
    )

    # Track the new window
    active_detail_windows[sim.sim_id] = new_window