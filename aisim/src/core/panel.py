import pygame
from aisim.src.core.configuration import config_manager
from aisim.src.core.mood import get_mood_description
# Forward declare Sim type hint to avoid circular import issues
from aisim.src.core.text import wrap_text


HIGH_ROMANCE_THRESHOLD = config_manager.get_entry('simulation.high_romance_threshold', 0.7)
RED_COLOR = (255, 0, 0)

def draw_panel_details(screen, detailed_sim, panel_scroll_offset, sims_dict, ui_font, log_font, SCREEN_WIDTH, SCREEN_HEIGHT, panel_sections_expanded, mouse_pos):
    """Draws the detailed information panel for a selected Sim with expandable sections."""
    panel_width = 450
    panel_height = 450  # Increased height
    panel_x = (SCREEN_WIDTH - panel_width) // 2
    panel_y = (SCREEN_HEIGHT - panel_height) // 2
    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    panel_bg_color = (40, 40, 60, 230)  # Semi-transparent dark blue/purple
    panel_border_color = (150, 150, 180)
    text_color = (230, 230, 230)
    padding = 15
    line_spacing = 5  # Extra space between lines/sections
    scrollbar_width = 10
    scrollbar_handle_color = (150, 150, 180)
    section_title_height = 25

    # --- Calculate Content Height (Estimate before drawing) ---
    estimated_content_height = padding  # Start with top padding
    portrait_size = 64 if detailed_sim.get_portrait() else 0
    info_font = ui_font
    line_h_info = info_font.get_linesize()
    line_h_log = log_font.get_linesize()

    # Height for basic info block (consider portrait height)
    basic_info_height = 6 * line_h_info  # Name, ID, Sex, Mood, Position, Tile
    estimated_content_height += max(portrait_size, basic_info_height) + line_spacing

    # Section heights, taking into account expansion state
    personality_height = calculate_personality_height(detailed_sim, log_font, panel_width, padding, scrollbar_width, line_h_log) if panel_sections_expanded['personality'] else section_title_height
    romance_height = calculate_romance_height(detailed_sim, sims_dict, line_h_log) if panel_sections_expanded['romance'] else section_title_height
    conversation_history_height = calculate_conversation_history_height(detailed_sim, log_font, panel_width, padding, scrollbar_width, line_h_log) if panel_sections_expanded['conversation_history'] else section_title_height

    estimated_content_height += personality_height + romance_height + conversation_history_height + 3 * line_spacing
    estimated_content_height += padding  # Bottom padding

    # --- Clamp Scroll Offset ---
    panel_visible_height = panel_height - 2 * padding
    max_scroll = max(0, estimated_content_height - panel_visible_height)
    panel_scroll_offset = max(0, min(panel_scroll_offset, max_scroll))

    # --- Draw Panel Background and Border ---
    pygame.draw.rect(screen, panel_bg_color, panel_rect, border_radius=10)
    pygame.draw.rect(screen, panel_border_color, panel_rect, width=2, border_radius=10)

    # --- Set Clipping Region for Content ---
    content_clip_rect = panel_rect.inflate(-padding // 2, -padding // 2)
    screen.set_clip(content_clip_rect)

    # --- Draw Content (with scroll offset) ---
    current_y = panel_y + padding - panel_scroll_offset

    # Portrait
    portrait = detailed_sim.get_portrait()
    if portrait:
        portrait_size = 64
        scaled_portrait = pygame.transform.scale(portrait, (portrait_size, portrait_size))
        portrait_x = panel_x + padding
        screen.blit(scaled_portrait, (portrait_x, current_y))
        text_start_x = portrait_x + portrait_size + padding
    else:
        portrait_size = 0
        text_start_x = panel_x + padding

    text_block_start_y = current_y

    # Basic Info (Name, ID, Sex, Mood) - next to portrait
    info_font = ui_font
    line_h = line_h_info

    name_text = f"Name: {detailed_sim.full_name}"
    name_surf = info_font.render(name_text, True, text_color)
    screen.blit(name_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    id_text = f"ID: {detailed_sim.sim_id[:8]}..."
    id_surf = info_font.render(id_text, True, text_color)
    screen.blit(id_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    sex_text = f"Sex: {detailed_sim.sex}"
    sex_surf = info_font.render(sex_text, True, text_color)
    screen.blit(sex_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    mood_str = get_mood_description(detailed_sim.mood)
    mood_text = f"Mood: {mood_str} ({detailed_sim.mood:.2f})"
    mood_surf = info_font.render(mood_text, True, text_color)
    screen.blit(mood_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    pos_text = f"Position: ({detailed_sim.x:.1f}, {detailed_sim.y:.1f})"
    pos_surf = info_font.render(pos_text, True, text_color)
    screen.blit(pos_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    tile_text = f"Tile: {detailed_sim.current_tile}"
    tile_surf = info_font.render(tile_text, True, text_color)
    screen.blit(tile_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    current_y = max(panel_y + padding - panel_scroll_offset + portrait_size, text_block_start_y) + line_spacing

    # Draw sections
    current_y = draw_personality_section(screen, detailed_sim, panel_x, current_y, padding, log_font, text_color, panel_sections_expanded['personality'], panel_width, scrollbar_width)
    current_y = draw_romance_section(screen, detailed_sim, sims_dict, panel_x, current_y, padding, log_font, text_color, RED_COLOR, HIGH_ROMANCE_THRESHOLD, panel_sections_expanded['romance'])
    current_y = draw_conversation_history_section(screen, detailed_sim, panel_x, current_y, padding, log_font, text_color, panel_sections_expanded['conversation_history'], panel_width, scrollbar_width)

    # --- Remove Clipping ---
    screen.set_clip(None)

    # --- Draw Scrollbar ---
    if max_scroll > 0:
        track_rect = pygame.Rect(panel_x + panel_width - scrollbar_width - padding // 2, panel_y + padding // 2, scrollbar_width, panel_height - padding)
        handle_height = max(15, panel_visible_height * (panel_visible_height / estimated_content_height))
        handle_y_ratio = panel_scroll_offset / max_scroll if max_scroll > 0 else 0
        handle_y = track_rect.y + handle_y_ratio * (track_rect.height - handle_height)
        # Close button
        close_button_rect = pygame.Rect(panel_x + panel_width - 25, panel_y + 5, 20, 20)
        pygame.draw.rect(screen, (200, 50, 50), close_button_rect)
        font = pygame.font.Font(None, 20)
        text_surface = font.render("X", True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=close_button_rect.center)
        screen.blit(text_surface, text_rect)

        # Check for close button click
        if close_button_rect.collidepoint(mouse_pos):
            return None  # Signal to close the panel

        handle_rect = pygame.Rect(track_rect.x, handle_y, scrollbar_width, handle_height)
        pygame.draw.rect(screen, scrollbar_handle_color, handle_rect, border_radius=5)
    return panel_scroll_offset

def calculate_personality_height(detailed_sim, log_font, panel_width, padding, scrollbar_width, line_h_log):
    """Calculates the height of the personality section."""
    height = 0
    height += 25  # Title height
    pers_lines = wrap_text(detailed_sim.personality_description, log_font, panel_width - 2 * padding - scrollbar_width)
    height += len(pers_lines) * line_h_log
    return height

def calculate_romance_height(detailed_sim, sims_dict, line_h_log):
    """Calculates the height of the romance section."""
    height = 0
    height += 25  # Title height
    if detailed_sim.relationships:
        height += len(detailed_sim.relationships) * line_h_log
    else:
        height += line_h_log  # "None" line
    return height

def calculate_conversation_history_height(detailed_sim, log_font, panel_width, padding, scrollbar_width, line_h_log):
    """Calculates the height of the conversation history section."""
    height = 0
    height += 25  # Title height
    content_width = panel_width - 2 * padding - scrollbar_width
    if detailed_sim.conversation_history:
        for entry in detailed_sim.conversation_history:
            speaker = entry.get('speaker', 'Unknown')
            line = entry.get('line', '')
            entry_text = f"{speaker}: {line}"
            wrapped_lines = wrap_text(entry_text, log_font, content_width)
            height += len(wrapped_lines) * line_h_log
    else:
        height += line_h_log  # "None" line
    return height

def draw_personality_section(screen, detailed_sim, panel_x, current_y, padding, log_font, text_color, expanded, panel_width, scrollbar_width):
    """Draws the personality section of the panel."""
    line_h_log = log_font.get_linesize()
    section_title_height = 25
    pers_title_surf = log_font.render("Personality:", True, text_color)
    screen.blit(pers_title_surf, (panel_x + padding, current_y))
    current_y += section_title_height

    if expanded:
        pers_lines = wrap_text(detailed_sim.personality_description, log_font, panel_width - 2 * padding - scrollbar_width)
        for line in pers_lines:
            line_surf = log_font.render(line, True, text_color)
            screen.blit(line_surf, (panel_x + padding, current_y))
            current_y += line_h_log
    return current_y

def draw_romance_section(screen, detailed_sim, sims_dict, panel_x, current_y, padding, log_font, text_color, red_color, high_romance_threshold, expanded):
    """Draws the romance section of the panel."""
    line_h_log = log_font.get_linesize()
    section_title_height = 25
    rom_title_surf = log_font.render("Romance:", True, text_color)
    screen.blit(rom_title_surf, (panel_x + padding, current_y))
    current_y += section_title_height

    if expanded:
        if detailed_sim.relationships:
            for other_id, values in sorted(detailed_sim.relationships.items()):
                other_sim = sims_dict.get(other_id)
                other_name = other_sim.full_name if other_sim else f"Unknown ({other_id[:6]})"
                friendship = values.get('friendship', 0.0)
                romance = values.get('romance', 0.0)
                current_text_color = red_color if romance >= high_romance_threshold else text_color
                rom_text = f"- {other_name}: F={friendship:.1f}, R={romance:.1f}"
                rom_surf = log_font.render(rom_text, True, current_text_color)
                screen.blit(rom_surf, (panel_x + padding, current_y))
                current_y += line_h_log
        else:
            no_rom_surf = log_font.render("- None", True, text_color)
            screen.blit(no_rom_surf, (panel_x + padding, current_y))
            current_y += line_h_log
    return current_y

def draw_conversation_history_section(screen, detailed_sim, panel_x, current_y, padding, log_font, text_color, expanded, panel_width, scrollbar_width):
    """Draws the conversation history section of the panel."""
    line_h_log = log_font.get_linesize()
    section_title_height = 25
    conv_title_surf = log_font.render("Conversation History:", True, text_color)
    screen.blit(conv_title_surf, (panel_x + padding, current_y))
    current_y += section_title_height

    if expanded:
        content_width = panel_width - 2 * padding - scrollbar_width
        if detailed_sim.conversation_history:
            for entry in detailed_sim.conversation_history:
                speaker = entry.get('speaker', 'Unknown')
                line = entry.get('line', '')
                entry_text = f"{speaker}: {line}"
                wrapped_lines = wrap_text(entry_text, log_font, content_width)
                for line in wrapped_lines:
                    line_surf = log_font.render(line, True, text_color)
                    screen.blit(line_surf, (panel_x + padding, current_y))
                    current_y += line_h_log
        else:
            no_conv_surf = log_font.render("- None", True, text_color)
            screen.blit(no_conv_surf, (panel_x + padding, current_y))
            current_y += line_h_log
    return current_y
