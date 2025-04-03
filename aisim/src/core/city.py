import pygame
import networkx as nx
import math
import random
import os

# Constants
GRID_COLOR = (40, 40, 40)  # Dark grey for fallback
TILE_SIZE = 32 # Assuming 32x32 tiles from assets
TILESET_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'static_dirs', 'assets', 'the_ville', 'visuals', 'map_assets', 'v3')

class City:
    """Represents the city environment."""
    def __init__(self, width, height):
        """Initializes the city grid."""
        self.width = width
        self.height = height
        self.grid_width = width // TILE_SIZE
        self.grid_height = height // TILE_SIZE
        self.graph = self._create_grid_graph()
        self._load_tilesets()
        self._create_tile_map() # Create a map of which tile to draw where

    def _load_tilesets(self):
        """Loads the required tileset images."""
        self.tilesets = {}
        self.tile_images = {} # Store individual tile surfaces
        try:
            # Load grass tileset (assuming it's a single image with multiple variations)
            grass_path = os.path.join(TILESET_PATH, 'tileset-grassland-grass.png')
            grass_sheet = pygame.image.load(grass_path).convert_alpha()
            self.tilesets['grass'] = grass_sheet
            # Extract individual grass tiles (assuming 32x32)
            sheet_width, sheet_height = grass_sheet.get_size()
            for i in range(sheet_width // TILE_SIZE):
                tile_rect = pygame.Rect(i * TILE_SIZE, 0, TILE_SIZE, TILE_SIZE)
                self.tile_images[f'grass_{i}'] = grass_sheet.subsurface(tile_rect)

            # Load path tileset (similar logic)
            path_path = os.path.join(TILESET_PATH, 'tileset-grassland-paths.png')
            path_sheet = pygame.image.load(path_path).convert_alpha()
            self.tilesets['path'] = path_sheet
            sheet_width, sheet_height = path_sheet.get_size()
            for r in range(sheet_height // TILE_SIZE):
                 for c in range(sheet_width // TILE_SIZE):
                    tile_rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    self.tile_images[f'path_{r}_{c}'] = path_sheet.subsurface(tile_rect)

            # Load props tileset (e.g., trees, fences)
            props_path = os.path.join(TILESET_PATH, 'tileset-grassland-props.png')
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
            print(f"Error loading tilesets from {TILESET_PATH}: {e}")
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


    def update(self, dt):
        """Updates the city state (placeholder)."""
        pass # No updates needed for a static grid/graph yet

    def _create_grid_graph(self):
        """Creates a NetworkX graph representing the walkable grid."""
        G = nx.Graph()
        half_tile = TILE_SIZE / 2
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
        return G

    def get_tile_coords(self, x, y):
        """Converts pixel coordinates to grid tile coordinates (col, row)."""
        col = int(x // TILE_SIZE)
        row = int(y // TILE_SIZE)
        # Clamp to grid bounds
        col = max(0, min(col, self.grid_width - 1))
        row = max(0, min(row, self.grid_height - 1))
        return col, row

    def get_node_from_coords(self, x, y):
        """Finds the graph node closest to the given pixel coordinates."""
        return self.get_tile_coords(x, y) # Node ID is the tile coord tuple

    def get_coords_from_node(self, node):
        """Gets the center pixel coordinates of a given graph node."""
        if node in self.graph.nodes:
            return self.graph.nodes[node]['pos']
        return None # Should not happen if node is valid

    def get_path(self, start_coords, end_coords):
        """Calculates the shortest path using A*."""
        start_node = self.get_node_from_coords(start_coords[0], start_coords[1])
        end_node = self.get_node_from_coords(end_coords[0], end_coords[1])

        if start_node == end_node:
            return None # Already at destination

        try:
            # A* heuristic: Euclidean distance
            def heuristic(u, v):
                pos_u = self.graph.nodes[u]['pos']
                pos_v = self.graph.nodes[v]['pos']
                return abs(pos_u[0] - pos_v[0]) + abs(pos_u[1] - pos_v[1])

            path_nodes = nx.astar_path(self.graph, start_node, end_node, heuristic=heuristic, weight='weight')
            # Convert node path back to coordinate path
            path_coords = [self.get_coords_from_node(node) for node in path_nodes]
            return path_coords
        except nx.NetworkXNoPath:
            print(f"No path found between {start_node} and {end_node}")
            return None
        except nx.NodeNotFound:
             print(f"Node not found for path calculation: start={start_node}, end={end_node}")
             return None
    def draw(self, screen):
        """Draws the city using the generated tile map."""
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
                    pygame.draw.rect(screen, GRID_COLOR, (c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE))

        # TODO: Load and draw actual building sprites based on a building map layer.
        # The current logic only draws grass, paths, and props.