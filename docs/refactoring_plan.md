# Refactoring Plan: Integrating `pygame_gui` into `aisim`

This document outlines the plan to refactor the `aisim` project to use the `pygame_gui` library for its user interface elements, replacing the current manual implementation.

## Goals

*   Replace manual UI drawing (details panel, status text, bottom info) with `pygame_gui` components.
*   Simplify event handling by leveraging `pygame_gui`'s UIManager.
*   Improve UI maintainability and extensibility.
*   Remove redundant code related to manual UI implementation.

## Steps

1.  **Setup & Initialization:**
    *   Ensure `pygame_gui` is installed (`pip install pygame_gui`).
    *   Import `pygame_gui` in `main.py`.
    *   Initialize `pygame_gui.UIManager` in `main.py` after setting the display mode, passing the screen dimensions.
    *   Create a basic `pygame_gui` theme file (e.g., `theme.json`) to define fonts, colors, and element styles, replacing the manual font loading in `main.py` and `text.py`. Load this theme into the UIManager.

2.  **Event Loop Refactoring (`main.py`):**
    *   Inside the main event loop (`for event in pygame.event.get():`), pass every event to the UIManager: `manager.process_events(event)`.
    *   Keep essential non-GUI event checks (`pygame.QUIT`, keyboard shortcuts for pause 'P', time scale '1'/'2'/'4'/'0').
    *   **Remove:** Manual mouse button down logic for detecting clicks *specifically for opening/closing the panel and selecting sims for the bottom log*. Also remove the manual mouse wheel handling logic for panel scrolling. The double-click detection logic will be modified.

3.  **Main Loop Update & Draw Refactoring (`main.py`):**
    *   Calculate `time_delta` (likely `raw_dt = clock.tick(fps) / 1000.0`).
    *   Call `manager.update(time_delta)` each frame *before* drawing.
    *   Call `manager.draw_ui(screen)` *after* drawing all game world elements (city, sims, weather effects) but *before* `pygame.display.flip()`.

4.  **Details Panel Replacement:**
    *   **Remove:** The `draw_panel_details` function entirely from `aisim/src/core/panel.py` (and eventually the file itself). Remove the call to `draw_panel_details` in `main.py`. Remove the `panel_scroll_offset` variable.
    *   **Modify Double-Click:** Keep the logic to detect a double-click on a Sim sprite. Instead of setting `detailed_sim = clicked_on_sim_object`, this action should now:
        *   Check if a details window for this Sim already exists. If so, bring it to the front.
        *   If not, create a new `pygame_gui.elements.UIWindow`.
        *   Inside the window, create a `pygame_gui.elements.UITextBox`. Populate its `html_text` attribute with the Sim's details (portrait image tag, name, ID, mood, personality, relationships, conversation history, using basic HTML for formatting like bolding titles and line breaks `<br>`). `UITextBox` handles scrolling automatically.
    *   Manage the lifecycle of these windows (e.g., store references, handle the close button).

5.  **UI Overlays Replacement (`main.py`):**
    *   **Status Text (Top-Left/Top-Right):** Replace manual `ui_font.render` and `screen.blit` for Pause/Speed and Weather status/countdown with `pygame_gui.elements.UILabel` elements. Anchor these labels appropriately using `pygame_gui`'s layout system. Update their text using `label.set_text()` when game state changes (pause, speed, weather).
    *   **Bottom Info (Bottom-Left):** Replace manual `log_font.render` and `screen.blit` for selected Sim info/log or selected Tile info with a `pygame_gui.elements.UILabel` or a small `pygame_gui.elements.UITextBox` anchored to the bottom-left. Update its content based on `selected_sim` or `selected_tile_info`.

6.  **Cleanup:**
    *   Delete the file `aisim/src/core/panel.py`.
    *   Analyze `aisim/src/core/text.py`. If `wrap_text` and `draw_bubble` are no longer needed (as `pygame_gui` handles text wrapping and the bubble might be removed or replaced), delete this file as well. Remove related imports.
    *   Remove the manual font loading (`ui_font`, `log_font`) if the theme handles all necessary fonts.

## Visual Plan (Mermaid Diagram)

```mermaid
graph TD
    A[Start main.py] --> B(Initialize Pygame & Core Components);
    B --> C(Initialize pygame_gui.UIManager with Theme);
    C --> D{Main Loop};

    subgraph Event Handling
        D --> E{Process Events};
        E -- Pygame Event --> F[UIManager.process_events(event)];
        E -- Pygame Event --> G[Handle Non-UI Input (Quit, Pause, Speed)];
        F -- UI Element Event --> H(Handle GUI Action e.g., Window Close);
        G -- Double-Click Sim Sprite --> I(Create/Show Sim Details UIWindow);
        G -- Single-Click Sim Sprite --> J(Update Bottom Sim Info UILabel);
        G -- Click Empty Space --> K(Update Bottom Tile Info UILabel);
    end

    subgraph Update Logic
        D --> L(Update Game State (Sims, Weather, City));
        L --> M(UIManager.update(time_delta));
    end

    subgraph Drawing
        M --> N(Draw Game World (City, Sims, Weather));
        N --> O(UIManager.draw_ui(screen));
        O --> P(pygame.display.flip());
        P --> D;
    end

    subgraph GUI Elements
        I -- Creates --> Q[pygame_gui.UIWindow];
        Q -- Contains --> R[pygame_gui.UITextBox (Sim Details)];
        J -- Updates --> S[pygame_gui.UILabel (Bottom Info)];
        K -- Updates --> S;
        T[pygame_gui.UILabel (Status)] --> O;
        U[pygame_gui.UILabel (Weather)] --> O;
    end

    subgraph To Be Removed
        V[draw_panel_details function];
        W[Manual Panel Scrolling];
        X[Manual UI Text Rendering];
        Y[aisim/src/core/panel.py];
        Z[aisim/src/core/text.py?];
    end

```

## Summary of Changes

*   **Heavily Modify:** `aisim/src/main.py` (integrate UIManager, change event loop, drawing, UI creation).
*   **Delete:** `aisim/src/core/panel.py`, potentially `aisim/src/core/text.py`.
*   **Create:** `theme.json` (or similar) for `pygame_gui`.