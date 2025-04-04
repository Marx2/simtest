import pygame
import networkx as nx
import math
import random
from aisim.src.core.constants import TILE_SIZE

def get_tile_coords(x, y, grid_width, grid_height):
    """Converts pixel coordinates to grid tile coordinates (col, row)."""
    col = int(x // TILE_SIZE)
    row = int(y // TILE_SIZE)
    # Clamp to grid bounds
    col = max(0, min(col, grid_width - 1))
    row = max(0, min(row, grid_height - 1))
    return col, row

def get_node_from_coords(x, y, grid_width, grid_height):
    """Finds the graph node closest to the given pixel coordinates."""
    return get_tile_coords(x, y, grid_width, grid_height) # Node ID is the tile coord tuple

def get_coords_from_node(node, graph):
    """Gets the center pixel coordinates of a given graph node."""
    if node in graph.nodes:
        return graph.nodes[node]['pos']
    return None # Should not happen if node is valid

def get_path(start_coords, end_coords, graph, get_node_from_coords, get_coords_from_node, city_width, city_height):
    """Calculates the shortest path using A*."""
    start_node = get_node_from_coords(start_coords[0], start_coords[1], city_width, city_height)
    end_node = get_node_from_coords(end_coords[0], end_coords[1], city_width, city_height)

    if start_node == end_node:
        return None # Already at destination

    try:
        # A* heuristic: Euclidean distance
        def heuristic(u, v):
            pos_u = graph.nodes[u]['pos']
            pos_v = graph.nodes[v]['pos']
            return abs(pos_u[0] - pos_v[0]) + abs(pos_u[1] - pos_v[1])

        path_nodes = nx.astar_path(graph, start_node, end_node, heuristic=heuristic, weight='weight')
        # Convert node path back to coordinate path
        path_coords = [get_coords_from_node(node, graph) for node in path_nodes]
        return path_coords
    except nx.NetworkXNoPath:
        print(f"No path found between {start_node} and {end_node}")
        return None
    except nx.NodeNotFound:
        print(f"Node not found for path calculation: start={start_node}, end={end_node}")
        return None

def update(self, dt, city, weather_state, all_sims, logger, current_time, tile_size, direction_change_frequency):
    """Updates the Sim's state, following a path if available, and logs data."""
    if not hasattr(self, 'time_since_last_direction_change'):
        self.time_since_last_direction_change = 0.0
    if hasattr(self, 'is_interacting') and self.is_interacting:
        print(f"Sim {self.sim_id}: movement update skipped due to is_interacting=True, interaction_timer={self.interaction_timer}")
        return
        return
    # if logger:
        # print(f"Sim {self.sim_id} update: x={self.x:.2f}, y={self.y:.2f}, target={self.target}")
    if not self.path:
        self._find_new_path(city)
        if not self.path: # Still no path (e.g., couldn't find one)
            return # Wait until next update to try again

    # Follow the current path
    if self.path and self.path_index < len(self.path):
        target_x, target_y = self.path[self.path_index]
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx**2 + dy**2)

        if distance < TILE_SIZE/4: # Reached waypoint (1/4 tile distance)
            self.path_index += 1
            if self.path_index >= len(self.path): # Reached final destination
                self.path = None
                self.target = None
                self.path_index = 0
                # Generate thought upon arrival
                situation = f"arrived at location ({int(self.x)}, {int(self.y)}) on a {weather_state} day"
                self._generate_thought(situation)
                self.mood = min(1.0, self.mood + 0.1) # Mood boost for reaching destination
        else: # Move towards waypoint
            # Normalize direction vector
            norm_dx = dx / distance
            norm_dy = dy / distance
            # Move
            if random.random() < 0.01:  # Reduced chance to stop
                return
            self.x += norm_dx * self.speed * dt
            self.y += norm_dy * self.speed * dt
            
            # Determine the direction of movement
            new_angle = math.atan2(norm_dy, norm_dx)

            angle_difference = abs(new_angle - self.previous_angle)
            angle_threshold = math.pi / 2  # 90 degrees
            self.time_since_last_direction_change += dt
            # Check if enough time has passed since the last direction change
            if self.time_since_last_direction_change > direction_change_frequency:
                if angle_difference > angle_threshold:
                    if abs(norm_dx) > abs(norm_dy):
                        new_direction = 'right' if norm_dx > 0 else 'left'
                    else:
                        new_direction = 'down' if norm_dy > 0 else 'up'

                    self.current_direction = new_direction
                    self.previous_direction = new_direction
                    self.previous_angle = new_angle
                    self.time_since_last_direction_change = 0.0  # Reset the timer
                    print(f"Sim {self.sim_id}: Direction changed to {self.current_direction}")
            # Increment the timer
            print(f"Sim {self.sim_id}: Moving, direction={self.current_direction}")
    # Update thought timer
    if self.current_thought:
        self.thought_timer -= dt
        if self.thought_timer <= 0:
            self.current_thought = None
    else:
         # Path finished or invalid state, try finding a new one next update
         self.path = None
         self.target = None
         self.path_index = 0

    # --- Mood Update based on Weather ---
    if weather_state in ["Rainy", "Snowy"]:
        self.mood = max(-1.0, self.mood - 0.005 * dt) # Slowly decrease mood in bad weather
    elif weather_state == "Sunny":
         self.mood = min(1.0, self.mood + 0.003 * dt) # Slowly increase mood in good weather

    # --- Interaction Check ---
    self._check_interactions(all_sims, logger, current_time)

    # Clamp mood
    self.mood = max(-1.0, min(self.mood, 1.0))

    # --- Log Mood ---
    if logger:
        logger.log_mood(current_time, self.sim_id, self.mood)

def _find_new_path(self, city):
    """Finds a path to a new random destination within the city."""
    # Pick a random destination tile, with a bias against the center
    center_col = city.grid_width // 2
    center_row = city.grid_height // 2
    max_distance = max(center_col, center_row)
    
    while True:
        dest_col = random.randint(0, city.grid_width - 1)
        dest_row = random.randint(0, city.grid_height - 1)
        
        # Calculate distance from the center
        distance = math.sqrt((dest_col - center_col)**2 + (dest_row - center_row)**2)
        
        # Give higher probability to tiles further from the center
        probability = distance / max_distance
        if random.random() < probability:
            # print(f"Sim {self.sim_id}: New destination=({dest_col}, {dest_row})")
            break
    self.target = city.get_coords_from_node((dest_col, dest_row))

    if self.target:
        # print(f"Sim at ({self.x:.1f}, {self.y:.1f}) finding path to {self.target}") # Optional log
        new_path = city.get_path((self.x, self.y), self.target)
        if new_path and len(new_path) > 1: # Ensure path has more than just the start node
            self.path = new_path
            self.path_index = 1 # Start moving towards the second node in the path
            # print(f"Path found: {len(self.path)} steps") # Optional log
        else:
            # print("Path not found or too short.") # Optional log
            self.path = None
            self.target = None
            self.path_index = 0
    else:
         # print("Could not determine target coordinates.") # Optional log
         self.path = None
         self.target = None
         self.path_index = 0