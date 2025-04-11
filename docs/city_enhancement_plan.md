# City Map Enhancement Plan

**Goal:** Enhance the `aisim` city generation by utilizing detailed sprites from four specified tileset files, creating a more visually sophisticated and logically structured map.

**Tilesets:**
*   `aisim/src/graphics/v3/tileset-grassland-grass.png`
*   `aisim/src/graphics/v3/tileset-grassland-paths.png`
*   `aisim/src/graphics/v3/tileset-grassland-props.png`
*   `aisim/src/graphics/v3/tileset-grassland-water.png`

**Base Tile Size:** 32x32 pixels

**Plan:**

1.  **Sprite Analysis & Metadata Definition:**
    *   **Action:** Manually inspect each of the four PNG tileset files.
    *   **Details:** For each distinct visual element (sprite):
        *   Assign a unique, descriptive `name`.
        *   Determine its top-left `x` and `y` coordinates.
        *   Determine its `width` and `height` in pixels (multiples of 32x32).
        *   Note the `source_file`.
        *   Determine if the sprite `can_be_rotated`.
    *   **Output:** A structured list of sprite definitions.

2.  **Create Sprite Metadata File (`sprite_definitions.json`):**
    *   **Action:** Create a new file at `aisim/config/sprite_definitions.json`.
    *   **Content:** Populate with sprite definitions from Step 1. Structure as a JSON array of objects:
        ```json
        [
          {
            "name": "sprite_name",
            "source_file": "path/to/image.png",
            "x": 0,
            "y": 0,
            "width": 32,
            "height": 32,
            "can_be_rotated": false
          },
          // ... more sprites
        ]
        ```

3.  **Analyze Current City Generation (`city.py`):**
    *   **Action:** Read `aisim/src/core/city.py`.
    *   **Goal:** Understand current map generation, data structures, and rendering.

4.  **Refactor `city.py` for New Sprites:**
    *   **Action:** Modify `aisim/src/core/city.py`.
    *   **Details:**
        *   Load `aisim/config/sprite_definitions.json`.
        *   Update map data structure for sprite references.
        *   Rewrite map generation algorithm:
            *   Implement logic for placing grass, water, paths, props using sprites.
            *   Ensure logical path connections.
            *   Place props appropriately (respecting `can_be_rotated` and context).
        *   Update rendering logic to draw map using detailed sprites from source PNGs based on metadata.

5.  **Analyze Current Documentation (`documentation.md`):**
    *   **Action:** Read `docs/documentation.md`.
    *   **Goal:** Identify relevant sections for update.

6.  **Update Documentation (`documentation.md`):**
    *   **Action:** Modify `docs/documentation.md`.
    *   **Details:**
        *   Remove/replace old plan/description.
        *   Add section detailing the new city generation process, tilesets, and `sprite_definitions.json`.

**Diagram:**

```mermaid
graph TD
    A[Analyze Tileset PNGs] --> B(Define Sprite Metadata);
    B --> C{Create sprite_definitions.json};
    D[Read city.py] --> E{Refactor city.py};
    C --> E;
    F[Read documentation.md] --> G{Update documentation.md};
    E --> G;

    subgraph Preparation
        A
        B
    end

    subgraph Implementation
        C
        D
        E
    end

    subgraph Documentation
        F
        G
    end