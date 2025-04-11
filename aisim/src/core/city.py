import pygame
import networkx as nx
import random
import os
import json # Needed for sprite definitions

from aisim.src.core.movement import get_tile_coords, get_node_from_coords, get_coords_from_node, get_path
from aisim.src.core.configuration import config_manager # Import the centralized config manager
TILE_SIZE = config_manager.get_entry('city.tile_size')
PANEL_FONT_PATH = config_manager.get_entry('sim.panel_font_dir')

class City:
    """Represents the city environment."""
    def __init__(self, width, height):
        """Initializes the city grid."""
        print("City constructor called")
        self.width = width
        self.height = height
        self.grid_width = width // TILE_SIZE
        self.grid_height = height // TILE_SIZE
        
        # Get config values directly from config_manager
        self.grid_color = tuple(config_manager.get_entry('city.grid_color', [40, 40, 40]))
        self.tileset_path = config_manager.get_entry('city.tileset_path', 'aisim/src/graphics/v3')
        
        self.graph = self._create_grid_graph()
        self.sprite_definitions = []
        self.sprite_lookup = {}
        self.source_images = {}
        self._load_assets() # Renamed from _load_tilesets to reflect loading JSON too
        self._create_tile_map() # Create a map of which tile to draw where
        self.sims = [] # Initialize sims list
        self.pending_romance_analysis = set() # Track (sim_id1, sim_id2) pairs awaiting analysis
        self.ollama_client_locked = False # Global lock for Ollama client access during conversations
    def _load_assets(self):
        """Loads sprite definitions from JSON and the required tileset images."""
        sprite_def_path = config_manager.get_entry('city.sprite_definitions_path', 'aisim/config/sprite_definitions.json')
        self.sprite_definitions = []
        self.sprite_lookup = {}
        self.source_images = {}

        # 1. Load Sprite Definitions
        try:
            with open(sprite_def_path, 'r') as f:
                self.sprite_definitions = json.load(f)
            print(f"Loaded {len(self.sprite_definitions)} sprite definitions from {sprite_def_path}")
            # Create a lookup for faster access
            self.sprite_lookup = {s['name']: s for s in self.sprite_definitions}
        except FileNotFoundError:
            print(f"Error: Sprite definition file not found at {sprite_def_path}")
            return # Cannot proceed without definitions
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {sprite_def_path}: {e}")
            return # Cannot proceed with invalid definitions
        except Exception as e:
            print(f"An unexpected error occurred loading sprite definitions: {e}")
            return

        # 2. Load Source Images
        loaded_sources = set()
        for sprite_def in self.sprite_definitions:
            source_file = sprite_def.get('source_file')
            if not source_file:
                print(f"Warning: Sprite '{sprite_def.get('name', 'UNKNOWN')}' is missing 'source_file'. Skipping.")
                continue

            if source_file not in loaded_sources:
                try:
                    # Construct full path relative to workspace if necessary
                    # Assuming source_file paths in JSON are relative to workspace root
                    full_path = source_file # Adjust if paths are relative to something else
                    if not os.path.isabs(full_path):
                        # Assuming current working directory is workspace root
                        # Or use a base path if needed: full_path = os.path.join(WORKSPACE_ROOT, source_file)
                        pass # Keep path as relative for now, assuming pygame handles it from CWD

                    print(f"Loading source image: {full_path}")
                    image = pygame.image.load(full_path).convert_alpha()
                    self.source_images[source_file] = image
                    loaded_sources.add(source_file)
                except pygame.error as e:
                    print(f"Error loading source image {full_path}: {e}")
                    # Optionally remove definitions using this source? Or just let draw fail?
                except FileNotFoundError:
                     print(f"Error: Source image file not found: {full_path}")

        print(f"Loaded {len(self.source_images)} unique source images.")

    def _create_tile_map(self):
        """Creates a 2D array representing the visual tile map using loaded sprite definitions."""
        self.tile_map = [[None for _ in range(self.grid_width)] for _ in range(self.grid_height)]

        # Get lists of sprite names by type (simple name-based filtering)
        grass_sprites = [s['name'] for s in self.sprite_definitions if s['name'].startswith('grass_')]
        path_sprites = [s['name'] for s in self.sprite_definitions if s['name'].startswith('path_')]
        water_sprites = [s['name'] for s in self.sprite_definitions if s['name'].startswith('water_')]
        prop_sprites = [s['name'] for s in self.sprite_definitions if s['name'].startswith(('tree_', 'bush_', 'barrel', 'fence_', 'signpost_'))]

        if not grass_sprites:
             print("Warning: No grass sprites found in definitions. Map generation might fail.")
             # Optionally fill with a fallback or return
             default_grass = 'grass_plain_1' # Assume this exists? Risky.
        else:
             default_grass = random.choice(grass_sprites)

        # 1. Fill base with random grass
        for r in range(self.grid_height):
            for c in range(self.grid_width):
                self.tile_map[r][c] = random.choice(grass_sprites) if grass_sprites else None

        # 2. Add some water (example: a large pond)
        if 'water_pond_large' in self.sprite_lookup:
            pond_def = self.sprite_lookup['water_pond_large']
            pond_w_tiles = pond_def['width'] // TILE_SIZE
            pond_h_tiles = pond_def['height'] // TILE_SIZE
            # Place pond somewhere near center, avoiding edges
            if self.grid_width > pond_w_tiles + 4 and self.grid_height > pond_h_tiles + 4:
                r_start = (self.grid_height - pond_h_tiles) // 2
                c_start = (self.grid_width - pond_w_tiles) // 2
                # Place the main sprite name at top-left
                self.tile_map[r_start][c_start] = 'water_pond_large'
                # Mark other covered cells (optional, draw logic might handle overlap)
                # For simplicity, let draw handle overlap for now.
                # We might need to clear grass underneath if draw doesn't layer properly.
                for r_offset in range(pond_h_tiles):
                    for c_offset in range(pond_w_tiles):
                        if r_offset == 0 and c_offset == 0: continue # Skip top-left
                        # Mark as occupied or clear grass? Let's clear.
                        if r_start + r_offset < self.grid_height and c_start + c_offset < self.grid_width:
                             self.tile_map[r_start + r_offset][c_start + c_offset] = None # Indicate covered by large sprite

        # 3. Add simple paths (example: horizontal and vertical crossing)
        h_path_row = self.grid_height // 3
        v_path_col = self.grid_width // 2
        h_path_sprite = 'path_dirt_h_straight' if 'path_dirt_h_straight' in self.sprite_lookup else None
        v_path_sprite = 'path_dirt_v_straight' if 'path_dirt_v_straight' in self.sprite_lookup else None

        if h_path_sprite:
             for c in range(self.grid_width):
                 # Avoid overwriting the pond placement logic (crude check)
                 if self.tile_map[h_path_row][c] is None or self.tile_map[h_path_row][c].startswith('grass_'):
                    self.tile_map[h_path_row][c] = h_path_sprite

        if v_path_sprite:
            for r in range(self.grid_height):
                # Avoid overwriting the pond and horizontal path
                if self.tile_map[r][v_path_col] is None or self.tile_map[r][v_path_col].startswith('grass_'):
                    self.tile_map[r][v_path_col] = v_path_sprite
            # TODO: Add intersection tile if available

        # 4. Add random props
        num_props = 50
        for _ in range(num_props):
            if not prop_sprites: break
            prop_name = random.choice(prop_sprites)
            prop_def = self.sprite_lookup[prop_name]
            prop_w_tiles = (prop_def['width'] + TILE_SIZE - 1) // TILE_SIZE # Ceiling division
            prop_h_tiles = (prop_def['height'] + TILE_SIZE - 1) // TILE_SIZE

            # Try placing randomly, ensuring it fits and doesn't overwrite important things
            attempts = 0
            placed = False
            while attempts < 10 and not placed:
                r = random.randint(0, self.grid_height - prop_h_tiles)
                c = random.randint(0, self.grid_width - prop_w_tiles)

                # Check if area is suitable (e.g., grass) and clear
                can_place = True
                for ro in range(prop_h_tiles):
                    for co in range(prop_w_tiles):
                         if not (0 <= r + ro < self.grid_height and 0 <= c + co < self.grid_width):
                              can_place = False; break
                         tile = self.tile_map[r + ro][c + co]
                         if tile is None or tile.startswith(('path_', 'water_')) or \
                            (tile.startswith('prop_') and (ro > 0 or co > 0)): # Check if another prop occupies non-top-left
                             can_place = False; break
                    if not can_place: break

                if can_place:
                    # Place prop name at top-left
                    self.tile_map[r][c] = prop_name
                    # Clear other covered cells (similar to pond)
                    for ro in range(prop_h_tiles):
                        for co in range(prop_w_tiles):
                            if ro == 0 and co == 0: continue
                            self.tile_map[r + ro][c + co] = None # Mark as covered
                    placed = True
                attempts += 1

        print("Tile map created with new sprite logic.")


    def city_update(self, dt):
        """Updates the city state (placeholder)."""
        pass # No updates needed for a static grid/graph yet

    def _create_grid_graph(self):
        """Creates a NetworkX graph representing the walkable grid."""
        G = nx.Graph()
        half_tile = TILE_SIZE / 2
        print(f"City grid_width: {self.grid_width}, grid_height: {self.grid_height}")
        for r in range(self.grid_height):
            for c in range(self.grid_width):
                node_id = (c, r) # Use grid coords as node ID
                center_x = c * TILE_SIZE + half_tile
                center_y = r * TILE_SIZE + half_tile
                G.add_node(node_id, pos=(center_x, center_y))

                # Add edges to neighbors (right and down to avoid duplicates)
                # Check right neighbor
                if c + 1 < self.grid_width:
                    neighbor_id = (c + 1, r)
                    G.add_edge(node_id, neighbor_id, weight=1) # Assuming uniform cost for now
                # Check down neighbor
                if r + 1 < self.grid_height:
                    neighbor_id = (c, r + 1)
                    G.add_edge(node_id, neighbor_id, weight=1)
                # Check diagonal neighbor (bottom-right)
                if c + 1 < self.grid_width and r + 1 < self.grid_height:
                    neighbor_id = (c + 1, r + 1)
                    G.add_edge(node_id, neighbor_id, weight=1.4)  # Slightly higher cost for diagonal movement
        print(f"Graph has {len(G.nodes)} nodes.")
        return G


    def draw(self, screen):
        """Draws the city using the generated tile map, optionally adding debug borders."""
        # Initialize font for debug text if needed
        debug_font = None
        show_debug_borders = config_manager.get_entry('city.debug_border', False)
        if show_debug_borders:
            try:
                if not pygame.font.get_init(): pygame.font.init()
                debug_font = pygame.font.Font(PANEL_FONT_PATH, 12) # Small font for coordinates
            except Exception as e:
                print(f"Warning: Could not initialize font for debug borders: {e}")
                show_debug_borders = False # Disable if font fails

        # --- Check Assets ---
        if not hasattr(self, 'tile_map') or not self.tile_map or \
           not hasattr(self, 'sprite_lookup') or not self.sprite_lookup or \
           not hasattr(self, 'source_images') or not self.source_images:
            # Fallback if assets weren't loaded correctly
            screen.fill((50, 50, 50)) # Dark grey background
            if not pygame.font.get_init(): pygame.font.init() # Ensure font is initialized
            fallback_font = pygame.font.SysFont(None, 30)
            text_surface = fallback_font.render("Error loading city assets!", True, (255, 0, 0))
            text_rect = text_surface.get_rect(center=(self.width / 2, self.height / 2))
            screen.blit(text_surface, text_rect)
            return

        # --- Draw Tiles using Sprite Definitions ---
        # Get a default grass sprite for layering under props
        default_grass_name = next((s['name'] for s in self.sprite_definitions if s['name'].startswith('grass_')), None)

        for r in range(self.grid_height):
            for c in range(self.grid_width):
                tile_name = self.tile_map[r][c]
                dest_pos = (c * TILE_SIZE, r * TILE_SIZE)

                # Determine if the current tile is occupied by a larger sprite originating from top-left
                # If tile_name is None, it might be covered. Need a way to know what covers it to draw base?
                # For now, if None, draw default grass. If _create_tile_map clears correctly, this is okay.
                if tile_name is None:
                    if default_grass_name and default_grass_name in self.sprite_lookup:
                         sprite_def = self.sprite_lookup[default_grass_name]
                         if sprite_def['source_file'] in self.source_images:
                            source_img = self.source_images[sprite_def['source_file']]
                            source_rect = pygame.Rect(sprite_def['x'], sprite_def['y'], sprite_def['width'], sprite_def['height'])
                            screen.blit(source_img, dest_pos, area=source_rect)
                    else:
                         pygame.draw.rect(screen, self.grid_color, (*dest_pos, TILE_SIZE, TILE_SIZE))
                    continue # Move to next cell

                # If tile has a name, draw it
                if tile_name in self.sprite_lookup:
                    sprite_def = self.sprite_lookup[tile_name]
                    source_file = sprite_def['source_file']

                    if source_file in self.source_images:
                        source_img = self.source_images[source_file]
                        source_rect = pygame.Rect(sprite_def['x'], sprite_def['y'], sprite_def['width'], sprite_def['height'])

                        # Layering: If it's a prop, draw default grass underneath first
                        is_prop = sprite_def['name'].startswith(('tree_', 'bush_', 'barrel', 'fence_', 'signpost_'))
                        if is_prop:
                            if default_grass_name and default_grass_name in self.sprite_lookup:
                                base_def = self.sprite_lookup[default_grass_name]
                                if base_def['source_file'] in self.source_images:
                                    base_img = self.source_images[base_def['source_file']]
                                    base_rect = pygame.Rect(base_def['x'], base_def['y'], base_def['width'], base_def['height'])
                                    # Ensure base tile is 32x32 for standard grid cell
                                    if base_rect.width == TILE_SIZE and base_rect.height == TILE_SIZE:
                                       screen.blit(base_img, dest_pos, area=base_rect)

                        # Draw the actual sprite (prop, path, water, grass variant)
                        screen.blit(source_img, dest_pos, area=source_rect)
                    else:
                        # Source image missing
                        pygame.draw.rect(screen, (255, 0, 255), (*dest_pos, TILE_SIZE, TILE_SIZE)) # Magenta fallback
                else:
                    # Invalid tile name in map
                    pygame.draw.rect(screen, (255, 255, 0), (*dest_pos, TILE_SIZE, TILE_SIZE)) # Yellow fallback

        # --- Draw Debug Borders and Coordinates (if enabled) ---
        if show_debug_borders and debug_font:
            border_color = (0, 0, 0) # Black
            text_color = (255, 255, 255) # White
            for r in range(self.grid_height):
                for c in range(self.grid_width):
                    # Draw border
                    rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    pygame.draw.rect(screen, border_color, rect, 1) # width=1 for border

                    # Draw coordinates
                    coord_text = f"{c},{r}"
                    text_surf = debug_font.render(coord_text, True, text_color)
                    # Position text slightly inside the top-left corner
                    screen.blit(text_surf, (rect.x + 2, rect.y + 2))

        # TODO: Load and draw actual building sprites based on a building map layer.
        # The current logic only draws grass, paths, and props.