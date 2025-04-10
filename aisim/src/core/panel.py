import pygame
from aisim.src.core.configuration import config_manager
from aisim.src.core.mood import get_mood_description
# Forward declare Sim type hint to avoid circular import issues
from aisim.src.core.text import wrap_text


HIGH_ROMANCE_THRESHOLD = config_manager.get_entry('simulation.high_romance_threshold', 0.7)
RED_COLOR = (255, 0, 0)
TEXT_COLOR = (230, 230, 230) # Define globally for reuse
HEADER_COLOR = (200, 200, 255) # Slightly different color for headers
CLOSE_BUTTON_COLOR = (200, 50, 50)
CLOSE_BUTTON_TEXT_COLOR = (255, 255, 255)

# Modified function signature
def draw_panel_details(screen, detailed_sim, panel_state, sims_dict, ui_font, log_font, SCREEN_WIDTH, SCREEN_HEIGHT):
    """Draws the detailed information panel for a selected Sim with expandable sections."""
    panel_width = 450
    panel_height = 450 # Increased height
    panel_x = (SCREEN_WIDTH - panel_width) // 2
    panel_y = (SCREEN_HEIGHT - panel_height) // 2
    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    panel_bg_color = (40, 40, 60, 230) # Semi-transparent dark blue/purple
    panel_border_color = (150, 150, 180)
    padding = 15
    line_spacing = 5 # Extra space between lines/sections
    scrollbar_width = 10
    scrollbar_handle_color = (150, 150, 180)

    # --- Extract States ---
    personality_expanded = panel_state.get("personality_expanded", True)
    romance_expanded = panel_state.get("romance_expanded", True)
    history_expanded = panel_state.get("history_expanded", True)
    panel_scroll_offset = panel_state.get("scroll_offset", 0)

    # --- Close Button ---
    close_button_size = 20
    close_button_padding = 5
    close_button_rect = pygame.Rect(
        panel_x + panel_width - close_button_size - close_button_padding,
        panel_y + close_button_padding,
        close_button_size,
        close_button_size
    )
    panel_state["close_button_rect"] = close_button_rect # Store for click detection

    # --- Calculate Content Height (Estimate before drawing, conditional) ---
    estimated_content_height = padding # Start with top padding
    portrait_size = 64 if detailed_sim.get_portrait() else 0
    info_font = ui_font
    line_h_info = info_font.get_linesize()
    line_h_log = log_font.get_linesize()
    header_rects = {} # Reset header rects for this draw call

    # Height for basic info block (consider portrait height)
    basic_info_height = 6 * line_h_info # Name, ID, Sex, Mood, Position, Tile
    estimated_content_height += max(portrait_size, basic_info_height) + line_spacing

    # Pre-calculate wrapped lines to avoid doing it twice
    content_width_for_text = panel_width - 2 * padding - scrollbar_width
    pers_lines = wrap_text(detailed_sim.personality_description, log_font, content_width_for_text)
    hist_entries_wrapped = []
    if detailed_sim.conversation_history:
        for entry in detailed_sim.conversation_history:
            speaker = entry.get('speaker', 'Unknown')
            line = entry.get('line', '')
            entry_text = f"{speaker}: {line}"
            hist_entries_wrapped.append(wrap_text(entry_text, log_font, content_width_for_text))
    else:
        # Represent "None" as a list containing one line for consistent handling
        hist_entries_wrapped.append(wrap_text("- None", log_font, content_width_for_text))


    # Height for Personality Section (Header + Content if expanded)
    estimated_content_height += line_spacing # Space before section
    estimated_content_height += line_h_log # Title height
    if personality_expanded:
        estimated_content_height += len(pers_lines) * line_h_log

    # Height for Romance Section (Header + Content if expanded)
    estimated_content_height += line_spacing # Space before section
    estimated_content_height += line_h_log # Title height
    if romance_expanded:
        if detailed_sim.relationships:
             estimated_content_height += len(detailed_sim.relationships) * line_h_log
        else:
             estimated_content_height += line_h_log # "None" line

    # Height for Conversation History (Header + Content if expanded)
    estimated_content_height += line_spacing # Space before section
    estimated_content_height += line_h_log # Title height
    if history_expanded:
        if hist_entries_wrapped:
             for wrapped_entry in hist_entries_wrapped:
                 estimated_content_height += len(wrapped_entry) * line_h_log
        # else: # Already handled by adding ["- None"] to hist_entries_wrapped

    estimated_content_height += padding # Bottom padding

    # --- Clamp Scroll Offset ---
    panel_visible_height = panel_height - 2 * padding
    max_scroll = max(0, estimated_content_height - panel_visible_height)
    panel_scroll_offset = max(0, min(panel_scroll_offset, max_scroll))
    panel_state["scroll_offset"] = panel_scroll_offset # Update state with clamped value

    # --- Draw Panel Background and Border ---
    pygame.draw.rect(screen, panel_bg_color, panel_rect, border_radius=10)
    pygame.draw.rect(screen, panel_border_color, panel_rect, width=2, border_radius=10)

    # --- Draw Close Button ---
    pygame.draw.rect(screen, CLOSE_BUTTON_COLOR, close_button_rect) # Red background
    close_text_surf = ui_font.render("X", True, CLOSE_BUTTON_TEXT_COLOR) # White 'X'
    close_text_rect = close_text_surf.get_rect(center=close_button_rect.center)
    screen.blit(close_text_surf, close_text_rect)

    # --- Set Clipping Region for Content ---
    # Clip slightly inside the border and below the close button area
    clip_top_offset = close_button_rect.bottom - panel_y + padding // 2
    content_clip_rect = pygame.Rect(
        panel_x + padding // 2,
        panel_y + clip_top_offset,
        panel_width - padding,
        panel_height - clip_top_offset - padding // 2
    )
    # Ensure clip rect has positive dimensions
    if content_clip_rect.width > 0 and content_clip_rect.height > 0:
        screen.set_clip(content_clip_rect)
    else:
         # Avoid setting an invalid clip rect if panel is too small
         screen.set_clip(None) # Or set a minimal valid clip

    # --- Draw Content (with scroll offset) ---
    # Start drawing content relative to the top of the clipping area
    current_y = content_clip_rect.top - panel_scroll_offset # Apply scroll offset

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

    # text_block_start_y needs to be relative to the *initial* current_y before portrait/info drawing
    text_block_start_y = current_y

    # Basic Info (Name, ID, Sex, Mood, Position, Tile) - next to portrait
    line_h = line_h_info

    name_text = f"Name: {detailed_sim.full_name}"
    name_surf = info_font.render(name_text, True, TEXT_COLOR)
    screen.blit(name_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    id_text = f"ID: {detailed_sim.sim_id[:8]}..."
    id_surf = info_font.render(id_text, True, TEXT_COLOR)
    screen.blit(id_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    sex_text = f"Sex: {detailed_sim.sex}"
    sex_surf = info_font.render(sex_text, True, TEXT_COLOR)
    screen.blit(sex_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    mood_str = get_mood_description(detailed_sim.mood)
    mood_text = f"Mood: {mood_str} ({detailed_sim.mood:.2f})"
    mood_surf = info_font.render(mood_text, True, TEXT_COLOR)
    screen.blit(mood_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    pos_text = f"Position: ({detailed_sim.x:.1f}, {detailed_sim.y:.1f})"
    pos_surf = info_font.render(pos_text, True, TEXT_COLOR)
    screen.blit(pos_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    tile_text = f"Tile: {detailed_sim.current_tile}"
    tile_surf = info_font.render(tile_text, True, TEXT_COLOR)
    screen.blit(tile_surf, (text_start_x, text_block_start_y))
    text_block_start_y += line_h

    # Update current_y based on the bottom of the portrait OR the text block, relative to the initial starting point
    current_y = max(current_y + portrait_size, text_block_start_y) + line_spacing

    # --- Personality Section ---
    current_y += line_spacing
    pers_title_text = "Personality [-]" if personality_expanded else "Personality [+]"
    pers_title_surf = log_font.render(pers_title_text, True, HEADER_COLOR)
    pers_title_rect = pers_title_surf.get_rect(topleft=(panel_x + padding, current_y))
    header_rects["personality"] = pers_title_rect # Store for click detection
    # Check visibility before drawing header
    if not (pers_title_rect.bottom < content_clip_rect.top or pers_title_rect.top > content_clip_rect.bottom):
        screen.blit(pers_title_surf, pers_title_rect)
    current_y += line_h_log

    if personality_expanded:
        for line in pers_lines:
            line_top = current_y
            line_bottom = current_y + line_h_log
            # Check if line is within the visible clipped area
            if line_bottom < content_clip_rect.top or line_top > content_clip_rect.bottom:
                current_y += line_h_log
                continue # Skip drawing but advance Y
            line_surf = log_font.render(line, True, TEXT_COLOR)
            screen.blit(line_surf, (panel_x + padding, current_y))
            current_y += line_h_log

    # --- Romance Section ---
    current_y += line_spacing
    rom_title_text = "Romance [-]" if romance_expanded else "Romance [+]"
    rom_title_surf = log_font.render(rom_title_text, True, HEADER_COLOR)
    rom_title_rect = rom_title_surf.get_rect(topleft=(panel_x + padding, current_y))
    header_rects["romance"] = rom_title_rect # Store for click detection
    if not (rom_title_rect.bottom < content_clip_rect.top or rom_title_rect.top > content_clip_rect.bottom):
        screen.blit(rom_title_surf, rom_title_rect)
    current_y += line_h_log

    if romance_expanded:
        if detailed_sim.relationships:
            for other_id, values in sorted(detailed_sim.relationships.items()):
                line_top = current_y
                line_bottom = current_y + line_h_log
                if line_bottom < content_clip_rect.top or line_top > content_clip_rect.bottom:
                    current_y += line_h_log
                    continue

                other_sim = sims_dict.get(other_id)
                other_name = other_sim.full_name if other_sim else f"Unknown ({other_id[:6]})"
                friendship = values.get('friendship', 0.0)
                romance = values.get('romance', 0.0)
                current_text_color = RED_COLOR if romance >= HIGH_ROMANCE_THRESHOLD else TEXT_COLOR
                rom_text = f"- {other_name}: F={friendship:.1f}, R={romance:.1f}"
                rom_surf = log_font.render(rom_text, True, current_text_color)
                screen.blit(rom_surf, (panel_x + padding, current_y))
                current_y += line_h_log
        else:
            line_top = current_y
            line_bottom = current_y + line_h_log
            if not (line_bottom < content_clip_rect.top or line_top > content_clip_rect.bottom):
                no_rom_surf = log_font.render("- None", True, TEXT_COLOR)
                screen.blit(no_rom_surf, (panel_x + padding, current_y))
            current_y += line_h_log

    # --- Conversation History Section ---
    current_y += line_spacing
    hist_title_text = "Conversation History [-]" if history_expanded else "Conversation History [+]"
    hist_title_surf = log_font.render(hist_title_text, True, HEADER_COLOR)
    hist_title_rect = hist_title_surf.get_rect(topleft=(panel_x + padding, current_y))
    header_rects["history"] = hist_title_rect # Store for click detection
    if not (hist_title_rect.bottom < content_clip_rect.top or hist_title_rect.top > content_clip_rect.bottom):
        screen.blit(hist_title_surf, hist_title_rect)
    current_y += line_h_log

    if history_expanded:
        if hist_entries_wrapped:
            for wrapped_entry in hist_entries_wrapped:
                for line in wrapped_entry:
                    line_top = current_y
                    line_bottom = current_y + line_h_log
                    if line_bottom < content_clip_rect.top or line_top > content_clip_rect.bottom:
                        current_y += line_h_log
                        continue
                    line_surf = log_font.render(line, True, TEXT_COLOR)
                    screen.blit(line_surf, (panel_x + padding, current_y))
                    current_y += line_h_log
                # Add a small visual break between entries if needed (optional)
                # current_y += line_spacing / 2
        # else: # Handled by pre-calculation and drawing "- None" if list contains only that

    # --- Remove Clipping ---
    screen.set_clip(None)

    # --- Draw Scrollbar ---
    # Adjust scrollbar track to respect clipping area
    scrollbar_track_rect = pygame.Rect(
        panel_x + panel_width - scrollbar_width - padding // 2,
        content_clip_rect.y, # Start track where content clip starts
        scrollbar_width,
        content_clip_rect.height # Track height matches clip height
    )

    if max_scroll > 0 and scrollbar_track_rect.height > 0: # Check track height too
        # Calculate handle height relative to the *track* height
        handle_height = max(15, scrollbar_track_rect.height * (panel_visible_height / estimated_content_height))
        handle_height = min(handle_height, scrollbar_track_rect.height) # Cannot be taller than track

        handle_y_ratio = panel_scroll_offset / max_scroll if max_scroll > 0 else 0
        # Calculate handle position within the track
        handle_y = scrollbar_track_rect.y + handle_y_ratio * (scrollbar_track_rect.height - handle_height)

        handle_rect = pygame.Rect(scrollbar_track_rect.x, handle_y, scrollbar_width, handle_height)
        pygame.draw.rect(screen, scrollbar_handle_color, handle_rect, border_radius=5)
        # Store the handle rect in panel_state for drag detection in main.py
        panel_state["scrollbar_handle_rect"] = handle_rect
        panel_state["scrollbar_track_rect"] = scrollbar_track_rect # Store track too for calculations
        panel_state["max_scroll"] = max_scroll # Store max_scroll

    # --- Store header rects in panel_state ---
    panel_state["header_rects"] = header_rects

    # The function modifies panel_state directly. No explicit return value needed.
