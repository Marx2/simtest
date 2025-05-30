import networkx as nx
import math
import random
from aisim.src.core.configuration import config_manager # Import the centralized config manager

TILE_SIZE = config_manager.get_entry('city.tile_size')
def get_tile_coords(x, y, grid_width, grid_height):
    """Converts pixel coordinates to grid tile coordinates (col, row)."""
    col = math.floor(x / TILE_SIZE)
    row = math.floor(y / TILE_SIZE)
    # Clamp to grid bounds
    col = max(0, min(col, grid_width - 1))
    row = max(0, min(row, grid_height - 1))
    return col, row

def get_node_from_coords(x, y, grid_width, grid_height):
    """Finds the graph node closest to the given pixel coordinates."""
    col, row = get_tile_coords(x, y, grid_width, grid_height)
    return (col, row) # Node ID is the tile coord tuple

def get_coords_from_node(node, graph):
    """Gets the center pixel coordinates of a given graph node."""
    if node in graph.nodes:
        return graph.nodes[node]['pos']
    logging.warning(f"Node not found in graph: {node}")
    return (0, 0) # Should not happen if node is valid

def get_path(start_coords, end_coords, graph, city_width, city_height):
    """Calculates the shortest path using A*."""
    # Clamp end_coords to grid bounds
    end_x = max(0, min(end_coords[0], city_width - 1))
    end_y = max(0, min(end_coords[1], city_height - 1))
    end_coords = (end_x, end_y)
    # logging.debug(f"get_path called: start_coords={start_coords}, end_coords={end_coords}")
    start_node = get_node_from_coords(start_coords[0], start_coords[1], city_width, city_height)
    start_node = (max(0, min(start_node[0], city_width // TILE_SIZE - 1)), max(0, min(start_node[1], city_height // TILE_SIZE - 1)))
    end_node = get_node_from_coords(end_coords[0], end_coords[1], city_width, city_height)
    # Clamp start and end nodes to grid bounds
    start_node = (max(0, min(start_node[0], city_width // TILE_SIZE - 1)), max(0, min(start_node[1], city_height // TILE_SIZE - 1)))
    end_node = (max(0, min(end_node[0], city_width // TILE_SIZE - 1)), max(0, min(end_node[1], city_height // TILE_SIZE - 1)))

    if start_node == end_node:
        return None  # Already at destination

    try:
        # A* heuristic: Euclidean distance
        def heuristic(u, v):
            pos_u = graph.nodes[u]['pos']
            pos_v = graph.nodes[v]['pos']
            return abs(pos_u[0] - pos_v[0]) + abs(pos_u[1] - pos_v[1])

        path_nodes = nx.astar_path(graph, start_node, end_node, heuristic=heuristic, weight='weight')
        # Convert node path back to coordinate path
        # logging.debug(f"Path found from {start_node} to {end_node}: {path_nodes}") # Log found path nodes
        path_coords = [get_coords_from_node(node, graph) for node in path_nodes]
        return path_coords
    except nx.NetworkXNoPath:
        logging.warning(f"No path found between {start_node} and {end_node}")
        return None
    except nx.NodeNotFound as e:
        logging.error(f"Node not found for path calculation: start={start_node}, end={end_node}, error={e}")
        return None

def movement_update(sim, dt, city, weather_state, all_sims, current_time, tile_size, direction_change_frequency):
    """Updates the Sim's state, following a path if available, checks for collisions, and logs data."""
    sim.is_blocked = False # Reset blocked status at the start of movement update

    # Clamp Sim coordinates to grid bounds *first*
    sim.x = max(0, min(sim.x, city.width - 1))
    sim.y = max(0, min(sim.y, city.height - 1))

    # Update current tile based on position *before* any early returns
    sim.current_tile = get_tile_coords(sim.x, sim.y, city.grid_width, city.grid_height)

    # logging.debug(f"Sim {sim.sim_id}: movement update called, x={sim.x:.2f}, y={sim.y:.2f}, current_tile={sim.current_tile}, target={sim.target}, path={sim.path}, path_index={sim.path_index}")
    if not hasattr(sim, 'time_since_last_direction_change'):
        sim.time_since_last_direction_change = 0.0

    # If interacting, no further movement logic is needed, but tile is updated
    if hasattr(sim, 'is_interacting') and sim.is_interacting:
        return

    # Only assign a new path if not interacting and no path exists
    if not sim.path and not sim.is_interacting:
        sim.path = get_path((sim.x, sim.y), (random.randint(0, city.width), random.randint(0, city.height)), city.graph, city.width, city.height)
        # logging.debug(f"Sim {sim.sim_id}: New path assigned in movement_update: {sim.path}") # Log path assignment
        if not sim.path:  # Still no path (e.g., couldn't find one)
            return # Wait until next update to try again
    # Follow the current path
    if sim.path and sim.path_index < len(sim.path):
        target_x, target_y = sim.path[sim.path_index]
        dx = target_x - sim.x
        dy = target_y - sim.y
        distance = math.sqrt(dx**2 + dy**2)

        if distance < TILE_SIZE/4: # Reached waypoint (1/4 tile distance)
            # logging.debug(f"Sim {sim.sim_id}: Reached waypoint {sim.path_index} at ({sim.x:.1f}, {sim.y:.1f}), target was ({target_x:.1f}, {target_y:.1f})")
            sim.path_index += 1
            if sim.path_index >= len(sim.path): # Reached final destination
                # logging.debug(f"Sim {sim.sim_id}: Reached final destination at ({sim.x:.1f}, {sim.y:.1f})")
                sim.path = None
                sim.target = None
                sim.path_index = 0
                sim.mood = min(1.0, sim.mood + 0.1) # Mood boost for reaching destination
        else: # Move towards waypoint
            # Normalize direction vector
            norm_dx = dx / distance
            norm_dy = dy / distance
            # --- Collision Detection ---
            # Predict next position and tile
            next_x = sim.x + norm_dx * sim.speed * dt
            next_y = sim.y + norm_dy * sim.speed * dt
            next_tile = get_tile_coords(next_x, next_y, city.grid_width, city.grid_height)

            # --- Collision Detection BEFORE Movement ---
            collision_detected = False
            for other_sim in all_sims:
                if other_sim.sim_id == sim.sim_id:
                    continue  # Don't check collision with self

                # Ensure both tiles are valid before comparing
                if (other_sim.current_tile is not None and
                    next_tile is not None and
                    len(other_sim.current_tile) == 2 and
                    len(next_tile) == 2 and
                    other_sim.current_tile == next_tile): # Direct tuple comparison
                    # Collision detected, change direction immediately
                    collision_detected = True
                    # logging.debug(f"Sim {sim.sim_id}: Predicted collision at tile {next_tile} with Sim {other_sim.sim_id}. Changing direction.")
                    change_direction(sim, city, direction_change_frequency)
                    break  # Found a collision, no need to check further

            if collision_detected:
                # No movement this frame due to collision
                sim.is_blocked = True
                return # Stop movement processing for this frame

            # --- Move (if no collision) ---
            if random.random() < 0.01:  # Reduced chance to stop
                return
            # is_blocked check might be redundant now due to early return, but keep for safety
            if not sim.is_blocked:
                sim.x = next_x # Use pre-calculated next position
                sim.y = next_y # Use pre-calculated next position

            # Determine the direction of movement
            new_angle = math.atan2(norm_dy, norm_dx)

            angle_difference = abs(new_angle - sim.previous_angle)
            angle_threshold = math.pi / 2  # 90 degrees
            sim.time_since_last_direction_change += dt
            # Check if enough time has passed since the last direction change
            if abs(norm_dx) > abs(norm_dy):
                new_direction = 'right' if norm_dx > 0 else 'left'
            else:
                new_direction = 'down' if norm_dy > 0 else 'up'

            if sim.current_direction != new_direction:
                sim.current_direction = new_direction
                sim.previous_direction = new_direction
                sim.previous_angle = new_angle
                sim.time_since_last_direction_change = 0.0  # Reset the timer
                sim.animation_frame = 0 # Reset animation frame

    # --- Mood Update based on Weather ---
    if weather_state in ["Rainy", "Snowy"]:
        sim.mood = max(-1.0, sim.mood - 0.005 * dt) # Slowly decrease mood in bad weather
    elif weather_state == "Sunny":
         sim.mood = min(1.0, sim.mood + 0.003 * dt) # Slowly increase mood in good weather

    # --- Interaction Check ---
    # Clamp mood
    sim.mood = max(-1.0, min(sim.mood, 1.0))

    # Current tile is now updated at the beginning of the function

def change_direction(sim, city, direction_change_frequency):
    """Changes the Sim's direction."""
    # Stop following the current path
    sim.path = None
    sim.target = None

    # Get available directions
    available_directions = get_available_directions(sim, city)

    if available_directions:
        # Choose a random direction
        # Choose a random available direction
        new_direction = random.choice(available_directions)
        # print(f"Sim {sim.sim_id}: Available directions: {available_directions}, chosen direction: {new_direction}")
        # Update the Sim's path
        sim.path = get_path((sim.x, sim.y), new_direction, city.graph, city.width, city.height)
        if sim.path:
            sim.path_index = 0
            sim.target = sim.path[sim.path_index]
            # logging.debug(f"Sim {sim.sim_id}: Changed direction to {new_direction}")
        # else:
            # logging.debug(f"Sim {sim.sim_id}: No path found after changing direction.")

    else:
        new_direction = None
        # logging.debug(f"Sim {sim.sim_id}: No path found in new direction {new_direction}")

def get_available_directions(sim, city):
    """Gets available directions for the Sim to move in."""
    directions = []
    current_node = get_node_from_coords(sim.x, sim.y, city.width, city.height)
    if current_node:
        # logging.debug(f"Sim {sim.sim_id}: current_node = {current_node}")
        if current_node not in city.graph.nodes:
            # logging.warning(f"Sim {sim.sim_id}: current_node {current_node} not in city.graph.nodes")
            return []
        neighbors = list(city.graph.neighbors(current_node))
        for neighbor in neighbors:
            neighbor_coords = get_coords_from_node(neighbor, city.graph)
            if neighbor_coords:
                # Check if any sim is interacting at the neighbor coords
                is_interacting = False
                for other_sim in city.sims:
                    if other_sim.is_interacting and math.dist((other_sim.x, other_sim.y), neighbor_coords) < 10:
                        is_interacting = True
                    break
                if not is_interacting:
                    directions.append(neighbor_coords)
    # logging.debug(f"Sim {sim.sim_id}: Available directions: {directions}")
    return directions
