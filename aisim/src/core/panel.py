import pygame
from aisim.src.core.configuration import config_manager
from aisim.src.core.mood import get_mood_description
# Forward declare Sim type hint to avoid circular import issues
from aisim.src.core.text import wrap_text


HIGH_ROMANCE_THRESHOLD = config_manager.get_entry('simulation.high_romance_threshold', 0.7)
RED_COLOR = (255, 0, 0)

def draw_panel_details(screen, detailed_sim, panel_scroll_offset, sims_dict, ui_font, log_font, SCREEN_WIDTH, SCREEN_HEIGHT):
    """Draws the detailed information panel for a selected Sim."""
    panel_width = 450
    panel_height = 450 # Increased height
    panel_x = (SCREEN_WIDTH - panel_width) // 2
    panel_y = (SCREEN_HEIGHT - panel_height) // 2
    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    panel_bg_color = (40, 40, 60, 230) # Semi-transparent dark blue/purple
    panel_border_color = (150, 150, 180)
    text_color = (230, 230, 230)
    padding = 15
    line_spacing = 5 # Extra space between lines/sections
    scrollbar_width = 10
    scrollbar_handle_color = (150, 150, 180)

    # --- Calculate Content Height (Estimate before drawing) ---
    # This is an estimation pass. We'll refine drawing positions later.
    estimated_content_height = padding # Start with top padding
    portrait_size = 64 if detailed_sim.get_portrait() else 0
    info_font = ui_font
    line_h_info = info_font.get_linesize()
    line_h_log = log_font.get_linesize()

    # Height for basic info block (consider portrait height)
    basic_info_height = 6 * line_h_info # Name, ID, Sex, Mood, Position, Tile
    estimated_content_height += max(portrait_size, basic_info_height) + line_spacing

    # Height for Personality
    estimated_content_height += line_h_log # Title
    pers_lines = wrap_text(detailed_sim.personality_description, log_font, panel_width - 2 * padding - scrollbar_width)
    estimated_content_height += len(pers_lines) * line_h_log + line_spacing

    # Height for Romance Section
    estimated_content_height += line_h_log # Title
    if detailed_sim.relationships:
         estimated_content_height += len(detailed_sim.relationships) * line_h_log
    else:
         estimated_content_height += line_h_log # "None" line
    # estimated_content_height += line_spacing # Space before next section (if any)
    estimated_content_height += line_spacing # Space before conv history

    # Height for Conversation History
    estimated_content_height += line_h_log # Title
    content_width_for_estimation = panel_width - 2 * padding - scrollbar_width # Width for wrapping text
    if detailed_sim.conversation_history:
        for entry in detailed_sim.conversation_history:
            role = entry.get('role', '??')
            content = entry.get('content', '')
            entry_text = f"{role.capitalize()}: {content}"
            wrapped_lines = wrap_text(entry_text, log_font, content_width_for_estimation)
            estimated_content_height += len(wrapped_lines) * line_h_log
    else:
        estimated_content_height += line_h_log # "None" line

    estimated_content_height += padding # Bottom padding
    estimated_content_height += padding # Bottom padding

    # --- Clamp Scroll Offset ---
    panel_visible_height = panel_height - 2 * padding
    max_scroll = max(0, estimated_content_height - panel_visible_height) # Max scroll is content height minus visible area
    # Note: panel_scroll_offset is passed in, but we still need to clamp it based on calculated max_scroll
    panel_scroll_offset = max(0, min(panel_scroll_offset, max_scroll))

    # --- Draw Panel Background and Border ---
    pygame.draw.rect(screen, panel_bg_color, panel_rect, border_radius=10)
    pygame.draw.rect(screen, panel_border_color, panel_rect, width=2, border_radius=10)

    # --- Set Clipping Region for Content ---
    # Slightly smaller than panel_rect to avoid drawing over the border
    content_clip_rect = panel_rect.inflate(-padding // 2, -padding // 2)
    screen.set_clip(content_clip_rect)

    # --- Draw Content (with scroll offset) ---
    current_y = panel_y + padding - panel_scroll_offset # Apply scroll offset

    # Portrait
    portrait = detailed_sim.get_portrait()
    if portrait:
        # Scale portrait up slightly for visibility
        portrait_size = 64
        scaled_portrait = pygame.transform.scale(portrait, (portrait_size, portrait_size))
        portrait_x = panel_x + padding
        # Draw portrait considering scroll offset
        screen.blit(scaled_portrait, (portrait_x, current_y))
        text_start_x = portrait_x + portrait_size + padding
    else:
        portrait_size = 0 # No portrait height offset needed
        text_start_x = panel_x + padding

    # Store the Y position after the portrait to align the start of the text block
    text_block_start_y = current_y

    # Basic Info (Name, ID, Sex, Mood) - next to portrait
    info_font = ui_font # Use slightly larger font
    line_h = line_h_info # Use precalculated line height

    name_text = f"Name: {detailed_sim.full_name}"
    name_surf = info_font.render(name_text, True, text_color)
    screen.blit(name_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    id_text = f"ID: {detailed_sim.sim_id[:8]}..." # Shorten ID
    id_surf = info_font.render(id_text, True, text_color)
    screen.blit(id_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    sex_text = f"Sex: {detailed_sim.sex}"
    sex_surf = info_font.render(sex_text, True, text_color)
    screen.blit(sex_surf, (text_start_x, text_block_start_y)) # Use text_block_start_y
    text_block_start_y += line_h # Increment text_block_start_y

    mood_str = get_mood_description(detailed_sim.mood)
    mood_text = f"Mood: {mood_str} ({detailed_sim.mood:.2f})"
    mood_surf = info_font.render(mood_text, True, text_color)
    screen.blit(mood_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h # Increment Y after drawing mood

    # Add Position (x, y)
    pos_text = f"Position: ({detailed_sim.x:.1f}, {detailed_sim.y:.1f})"
    pos_surf = info_font.render(pos_text, True, text_color)
    screen.blit(pos_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    # Add Current Tile
    tile_text = f"Tile: {detailed_sim.current_tile}" # Assumes current_tile is a tuple (col, row) or None
    tile_surf = info_font.render(tile_text, True, text_color)
    screen.blit(tile_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    # Ensure text doesn't overlap portrait if portrait is tall
    # current_y now represents the bottom edge after the portrait OR the text block, whichever is lower
    current_y = max(panel_y + padding - panel_scroll_offset + portrait_size, text_block_start_y) + line_spacing

    # Personality Description
    current_y += line_spacing # Add space before section
    pers_title_surf = log_font.render("Personality:", True, text_color)
    screen.blit(pers_title_surf, (panel_x + padding, current_y))
    current_y += line_h_log

    # Use the pre-wrapped lines from height calculation
    # pers_lines = wrap_text(detailed_sim.personality_description, log_font, content_width) # Already done
    for line in pers_lines:
        # Simple check: Don't draw if the line *starts* way below the panel
        if current_y > panel_y + panel_height:
             break
        # More precise check: Don't draw if the line *ends* way above the panel
        if current_y + line_h_log < panel_y:
            current_y += line_h_log # Still need to advance Y even if not drawing
            continue

        line_surf = log_font.render(line, True, text_color)
        screen.blit(line_surf, (panel_x + padding, current_y))
        current_y += line_h_log

    # Romance Section
    current_y += line_spacing # Add space before section
    rom_title_surf = log_font.render("Romance:", True, text_color)
    screen.blit(rom_title_surf, (panel_x + padding, current_y))
    current_y += line_h_log

    if detailed_sim.relationships:
        for other_id, values in sorted(detailed_sim.relationships.items()): # Sort for consistent order
            # Simple visibility checks
            if current_y > panel_y + panel_height: break
            if current_y + line_h_log < panel_y:
                current_y += line_h_log
                continue

            other_sim = sims_dict.get(other_id)
            other_name = other_sim.full_name if other_sim else f"Unknown ({other_id[:6]})"
            friendship = values.get('friendship', 0.0)
            romance = values.get('romance', 0.0)

            # Determine color based on romance level
            current_text_color = RED_COLOR if romance >= HIGH_ROMANCE_THRESHOLD else text_color

            # Format text
            rom_text = f"- {other_name}: F={friendship:.1f}, R={romance:.1f}"
            rom_surf = log_font.render(rom_text, True, current_text_color) # Use determined color
            screen.blit(rom_surf, (panel_x + padding, current_y))
            current_y += line_h_log
    else:
         # Simple visibility checks
         if not (current_y > panel_y + panel_height or current_y + line_h_log < panel_y):
            no_rom_surf = log_font.render("- None", True, text_color)
            screen.blit(no_rom_surf, (panel_x + padding, current_y))
         current_y += line_h_log # Still advance Y

    # Conversation History
    current_y += line_spacing # Add space before section
    conv_title_surf = log_font.render("Conversation History:", True, text_color)
    screen.blit(conv_title_surf, (panel_x + padding, current_y))
    current_y += line_h_log

    content_width = panel_width - 2 * padding - scrollbar_width # Available width for text
    if detailed_sim.conversation_history:
        for entry in detailed_sim.conversation_history:
            speaker = entry.get('speaker', 'Unknown') # Use 'speaker' key
            line = entry.get('line', '') # Use 'line' key
            entry_text = f"{speaker}: {line}" # Format with correct variables
            # Wrap conversation entry text if needed
            wrapped_lines = wrap_text(entry_text, log_font, content_width)
            for line in wrapped_lines:
                # Simple visibility checks
                if current_y > panel_y + panel_height: break
                if current_y + line_h_log < panel_y:
                    current_y += line_h_log
                    continue

                line_surf = log_font.render(line, True, text_color)
                screen.blit(line_surf, (panel_x + padding, current_y))
                current_y += line_h_log
            if current_y > panel_y + panel_height: break # Break outer loop too if needed
    else:
        # Simple visibility checks
        if not (current_y > panel_y + panel_height or current_y + line_h_log < panel_y):
            no_conv_surf = log_font.render("- None", True, text_color)
            screen.blit(no_conv_surf, (panel_x + padding, current_y))
        current_y += line_h_log # Still advance Y

    # --- Remove Clipping ---
    screen.set_clip(None)

    # --- Draw Scrollbar ---
    if max_scroll > 0: # Only draw if scrolling is possible
        # Scrollbar Track
        track_rect = pygame.Rect(panel_x + panel_width - scrollbar_width - padding // 2, panel_y + padding // 2, scrollbar_width, panel_height - padding)
        # pygame.draw.rect(screen, (30, 30, 40), track_rect, border_radius=5) # Optional track background

        # Scrollbar Handle
        handle_height = max(15, panel_visible_height * (panel_visible_height / estimated_content_height)) # Min height 15px
        handle_y_ratio = panel_scroll_offset / max_scroll if max_scroll > 0 else 0 # Avoid division by zero
        handle_y = track_rect.y + handle_y_ratio * (track_rect.height - handle_height)
        handle_rect = pygame.Rect(track_rect.x, handle_y, scrollbar_width, handle_height)
        pygame.draw.rect(screen, scrollbar_handle_color, handle_rect, border_radius=5)

    # Return the clamped scroll offset in case it was adjusted
    return panel_scroll_offset

