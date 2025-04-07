# aisim/src/core/panel.py
import pygame
import os
from aisim.src.core.configuration import config_manager

# Font will be initialized lazily inside draw_bubble
PANEL_FONT = None
# PANEL_FONT_PATH = config_manager.get_entry('sim.panel_font_dir')
PANEL_FONT_PATH = ''

# Get colors from config with defaults
TEXT_COLOR = tuple(config_manager.get_entry('ui.text_color', [240, 240, 240]))
BG_COLOR = tuple(config_manager.get_entry('ui.bg_color', [50, 50, 50, 180]))

def wrap_text(text, font, max_width):
    """Helper function to wrap text to fit within a specified width."""
    words = text.split(' ')
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        # Use font.size to check width
        if font.size(test_line)[0] <= max_width:
            current_line.append(word)
        else:
            # Only add non-empty lines
            if current_line:
                lines.append(' '.join(current_line))
            # Handle very long words that exceed max_width alone
            if font.size(word)[0] > max_width:
                 # Simple split (might break words awkwardly) - consider more robust hyphenation
                 # For now, just add the long word as its own line
                 lines.append(word)
                 current_line = []
            else:
                 current_line = [word]


    if current_line:
        lines.append(' '.join(current_line))
    return lines


def draw_bubble(screen, text, position, font=None, text_color=TEXT_COLOR, bg_color=BG_COLOR, max_width=150, padding=10, offset_y=-30):
    """Draws a text bubble above a given position."""
    global PANEL_FONT # Declare intent to modify the global variable

    # Lazy font initialization
    if font is None:
        if PANEL_FONT is None:
            try:
                # Ensure font module is initialized (should be by main.py, but check)
                if not pygame.font.get_init():
                    pygame.font.init()
                           # Load the emoji-supporting font
                if os.path.exists(PANEL_FONT_PATH):
                    PANEL_FONT = pygame.font.Font(PANEL_FONT_PATH, 18)
                else:
                    PANEL_FONT = pygame.font.SysFont(None, 18)
            except pygame.error as e:
                 print(f"Error initializing default font in panel.py: {e}")
                 # Fallback or re-raise? For now, let it fail if font init fails.
                 return # Cannot draw without a font
        font = PANEL_FONT # Use the global default if no specific font passed

    if not text or not font: # Also check if font initialization failed
        return

    lines = wrap_text(text, font, max_width)
    if not lines: # Don't draw if wrapping results in no lines
        return

    # Calculate total height and max width of the text block
    line_height = font.get_linesize()
    total_height = len(lines) * line_height
    try:
        actual_max_width = max(font.size(line)[0] for line in lines)
    except ValueError: # Handle case where lines might be empty after wrapping
        return

    # Calculate bubble dimensions
    bubble_width = actual_max_width + (2 * padding)
    bubble_height = total_height + (2 * padding)
    bubble_x = position[0] - bubble_width // 2
    bubble_y = position[1] + offset_y - bubble_height # Position above the target point

    # Draw bubble background
    bubble_rect = pygame.Rect(bubble_x, bubble_y, bubble_width, bubble_height)
    # Use Surface with SRCALPHA for transparency
    bubble_surface = pygame.Surface((bubble_width, bubble_height), pygame.SRCALPHA)
    pygame.draw.rect(bubble_surface, bg_color, bubble_surface.get_rect(), border_radius=5)

    # Draw each line of text onto the bubble surface
    text_start_y = padding # Start text drawing inside the padding
    for i, line in enumerate(lines):
        text_surface = font.render(line, True, text_color)
        # Center text horizontally within the bubble's padded area
        text_rect = text_surface.get_rect(centerx=bubble_width / 2, y=text_start_y + i * line_height)
        bubble_surface.blit(text_surface, text_rect)

    # Blit the complete bubble surface onto the main screen
    screen.blit(bubble_surface, (bubble_x, bubble_y))