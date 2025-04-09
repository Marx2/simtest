import pygame
import networkx as nx
import math
import random
import os
# import json # No longer needed as we use config_manager

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
        self._load_tilesets()
        self._create_tile_map() # Create a map of which tile to draw where
        self.sims = [] # Initialize sims list
        self.active_conversation_partners = set() # Track sims currently talking
        self.pending_romance_analysis = set() # Track (sim_id1, sim_id2) pairs awaiting analysis
    def _load_tilesets(self):
        """Loads the required tileset images."""
        self.tilesets = {}
        self.tile_images = {} # Store individual tile surfaces
        try:
            # Load grass tileset (assuming it's a single image with multiple variations)
            grass_path = os.path.join(self.tileset_path, 'tileset-grassland-grass.png')
            grass_sheet = pygame.image.load(grass_path).convert_alpha()
            self.tilesets['grass'] = grass_sheet
            # Extract individual grass tiles (assuming 32x32)
            sheet_width, sheet_height = grass_sheet.get_size()
            for i in range(sheet_width // TILE_SIZE):
                tile_rect = pygame.Rect(i * TILE_SIZE, 0, TILE_SIZE, TILE_SIZE)
                self.tile_images[f'grass_{i}'] = grass_sheet.subsurface(tile_rect)

            # Load path tileset (similar logic)
            path_path = os.path.join(self.tileset_path, 'tileset-grassland-paths.png')
            path_sheet = pygame.image.load(path_path).convert_alpha()
            self.tilesets['path'] = path_sheet
            sheet_width, sheet_height = path_sheet.get_size()
            for r in range(sheet_height // TILE_SIZE):
                 for c in range(sheet_width // TILE_SIZE):
                    tile_rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    self.tile_images[f'path_{r}_{c}'] = path_sheet.subsurface(tile_rect)

            # Load props tileset (e.g., trees, fences)
            props_path = os.path.join(self.tileset_path, 'tileset-grassland-props.png')
            props_sheet = pygame.image.load(props_path).convert_alpha()
            self.tilesets['props'] = props_sheet
            # Extract individual prop tiles (assuming 32x32)
            sheet_width, sheet_height = props_sheet.get_size()
            for r in range(sheet_height // TILE_SIZE):
                 for c in range(sheet_width // TILE_SIZE):
                    tile_rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    # Use transparent key for props if needed, or just store
                    self.tile_images[f'prop_{r}_{c}'] = props_sheet.subsurface(tile_rect)


            print(f"Loaded {len(self.tile_images)} tiles.")

        except pygame.error as e:
            print(f"Error loading tilesets from {self.tileset_path}: {e}")
            self.tilesets = {} # Reset on error
            self.tile_images = {}

    def _create_tile_map(self):
        """Creates a 2D array representing the visual tile map."""
        self.tile_map = [[None for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        # Basic logic: Fill with random grass, add some paths and props
        for r in range(self.grid_height):
            for c in range(self.grid_width):
                # Default to random grass tile
                grass_tile_index = random.randint(0, (self.tilesets['grass'].get_width() // TILE_SIZE) - 1)
                self.tile_map[r][c] = f'grass_{grass_tile_index}'

        # Add a simple path (example)
        path_start_row = self.grid_height // 2
        for c in range(self.grid_width):
             # Basic path tile - needs more complex logic for corners/intersections
             # Using a simple straight path tile for now: path_0_1
             if f'path_0_1' in self.tile_images:
                self.tile_map[path_start_row][c] = 'path_0_1'

        # Add some random props (example trees - prop_0_0)
        if f'prop_0_0' in self.tile_images:
            for _ in range(50): # Add 50 random trees
                r = random.randint(0, self.grid_height - 1)
                c = random.randint(0, self.grid_width - 1)
                # Avoid placing on path for simplicity
                if r != path_start_row:
                    # Store prop to be drawn *over* the base tile
                    # We'll modify the draw loop later to handle layers
                    # For now, just replace the base tile (prop will overwrite)
                     self.tile_map[r][c] = 'prop_0_0'


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
        if not hasattr(self, 'tile_map') or not self.tile_map or not self.tile_images:
            # Fallback if tile map wasn't created (e.g., tileset loading failed)
            screen.fill((50, 50, 50)) # Dark grey background
            pygame.font.init() # Ensure font is initialized for fallback text
            fallback_font = pygame.font.SysFont(None, 30)
            text_surface = fallback_font.render("Error loading city assets!", True, (255, 0, 0))
            text_rect = text_surface.get_rect(center=(self.width / 2, self.height / 2))
            screen.blit(text_surface, text_rect)
            return

        # Draw tiles based on the tile_map
        for r in range(self.grid_height):
            for c in range(self.grid_width):
                tile_name = self.tile_map[r][c]
                if tile_name and tile_name in self.tile_images:
                    # Separate base tiles (grass/path) from props (trees)
                    # Draw base tile first
                    base_tile_name = tile_name
                    if tile_name.startswith('prop_'):
                         # Find underlying grass tile (simple logic for now)
                         grass_tile_index = (r + c) % (self.tilesets['grass'].get_width() // TILE_SIZE)
                         base_tile_name = f'grass_{grass_tile_index}'

                    if base_tile_name in self.tile_images:
                         screen.blit(self.tile_images[base_tile_name], (c * TILE_SIZE, r * TILE_SIZE))

                    # Draw prop tile on top if it exists
                    if tile_name.startswith('prop_'):
                         screen.blit(self.tile_images[tile_name], (c * TILE_SIZE, r * TILE_SIZE))

                else:
                    # Draw a fallback color if tile is missing or name is invalid
                    pygame.draw.rect(screen, self.grid_color, (c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE))

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