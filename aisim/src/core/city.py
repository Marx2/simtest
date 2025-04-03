import pygame
import networkx as nx
import math
# Constants
GRID_COLOR = (40, 40, 40)  # Dark grey
TILE_SIZE = 40 # Size of each grid cell in pixels

class City:
    """Represents the city environment."""
    def __init__(self, width, height):
        """Initializes the city grid."""
        self.width = width
        self.height = height
        self.grid_width = width // TILE_SIZE
        self.grid_height = height // TILE_SIZE
        self.graph = self._create_grid_graph()
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
                return math.dist(pos_u, pos_v)

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
        """Draws the city grid."""
        for x in range(0, self.width, TILE_SIZE):
            pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, self.height))
        for y in range(0, self.height, TILE_SIZE):
            pygame.draw.line(screen, GRID_COLOR, (0, y), (self.width, y))

        # TODO: Draw buildings, roads, obstacles etc. and update graph accordingly