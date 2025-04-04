import pygame
import networkx as nx
import math
import random
from aisim.src.core.constants import TILE_SIZE

# from aisim.src.core.sim import _find_new_path

def get_tile_coords(x, y, grid_width, grid_height):
    """Converts pixel coordinates to grid tile coordinates (col, row)."""
    col = round(x / TILE_SIZE)
    row = round(y / TILE_SIZE)
    # Clamp to grid bounds
    col = max(0, min(col, grid_width - 1))
    row = max(0, min(row, grid_height - 1))
    return col, row

def get_node_from_coords(x, y, grid_width, grid_height):
    """Finds the graph node closest to the given pixel coordinates."""
    col, row = get_tile_coords(x, y, grid_width, grid_height)
    # print(f"get_node_from_coords called: x={x}, y={y}, grid_width={grid_width}, grid_height={grid_height}, col={col}, row={row}")
    return (col, row) # Node ID is the tile coord tuple

def get_coords_from_node(node, graph):
    """Gets the center pixel coordinates of a given graph node."""
    if node in graph.nodes:
        return graph.nodes[node]['pos']
    print(f"Node not found in graph: {node}")
    return (0, 0) # Should not happen if node is valid

def get_path(start_coords, end_coords, graph, get_node_from_coords, get_coords_from_node, city_width, city_height):
    """Calculates the shortest path using A*."""
    # Clamp end_coords to grid bounds
    end_x = max(0, min(end_coords[0], city_width - 1))
    end_y = max(0, min(end_coords[1], city_height - 1))
    end_coords = (end_x, end_y)
    # print(f"get_path called: start_coords={start_coords}, end_coords={end_coords}")
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
        # print(f"Path found from {start_node} to {end_node}: {path_nodes}") # Log found path nodes
        path_coords = [get_coords_from_node(node, graph) for node in path_nodes]
        return path_coords
    except nx.NetworkXNoPath:
        print(f"No path found between {start_node} and {end_node}")
        return None
    except nx.NodeNotFound as e:
        print(f"Node not found for path calculation: start={start_node}, end={end_node}, error={e}")
        return None

def update(sim, dt, city, weather_state, all_sims, logger, current_time, tile_size, direction_change_frequency):
    """Updates the Sim's state, following a path if available, and logs data."""
    # print(f"Sim {sim.sim_id}: movement update called, x={sim.x:.2f}, y={sim.y:.2f}, target={sim.target}, path={sim.path}, path_index={sim.path_index}")
    if not hasattr(sim, 'time_since_last_direction_change'):
        sim.time_since_last_direction_change = 0.0
    if hasattr(sim, 'is_interacting') and sim.is_interacting:
        # print(f"Sim {sim.sim_id}: movement update skipped due to is_interacting=True, interaction_timer={sim.interaction_timer}")
        return
    # if logger:
        # print(f"Sim {sim.sim_id} update: x={sim.x:.2f}, y={sim.y:.2f}, target={sim.target}")
    # Clamp Sim coordinates to grid bounds
    sim.x = max(0, min(sim.x, city.width - 1))
    sim.y = max(0, min(sim.y, city.height - 1))

    if not sim.path:
        # from aisim.src.core.sim import get_path, get_node_from_coords, get_coords_from_node
        sim.path = get_path((sim.x, sim.y), (random.randint(0, city.width), random.randint(0, city.height)), city.graph, get_node_from_coords, get_coords_from_node, city.width, city.height)
        # print(f"Sim {sim.sim_id}: New path assigned in movement_update: {sim.path}") # Log path assignment
        if not sim.path:  # Still no path (e.g., couldn't find one)
            return # Wait until next update to try again

    # Follow the current path
    if sim.path and sim.path_index < len(sim.path):
        target_x, target_y = sim.path[sim.path_index]
        dx = target_x - sim.x
        dy = target_y - sim.y
        distance = math.sqrt(dx**2 + dy**2)

        if distance < TILE_SIZE/4: # Reached waypoint (1/4 tile distance)
            # print(f"Sim {sim.sim_id}: Reached waypoint {sim.path_index} at ({sim.x:.1f}, {sim.y:.1f}), target was ({target_x:.1f}, {target_y:.1f})")
            sim.path_index += 1
            if sim.path_index >= len(sim.path): # Reached final destination
                # print(f"Sim {sim.sim_id}: Reached final destination at ({sim.x:.1f}, {sim.y:.1f})")
                sim.path = None
                sim.target = None
                sim.path_index = 0
                # Generate thought upon arrival
                situation = f"arrived at location ({int(sim.x)}, {int(sim.y)}) on a {weather_state} day"
                sim._generate_thought(situation)
                sim.mood = min(1.0, sim.mood + 0.1) # Mood boost for reaching destination
        else: # Move towards waypoint
            # Normalize direction vector
            norm_dx = dx / distance
            norm_dy = dy / distance
            # Move
            if random.random() < 0.01:  # Reduced chance to stop
                return
            sim.x += norm_dx * sim.speed * dt
            sim.y += norm_dy * sim.speed * dt

            # Determine the direction of movement
            new_angle = math.atan2(norm_dy, norm_dx)

            angle_difference = abs(new_angle - sim.previous_angle)
            angle_threshold = math.pi / 2  # 90 degrees
            sim.time_since_last_direction_change += dt
            # Check if enough time has passed since the last direction change
            if sim.time_since_last_direction_change > direction_change_frequency:
                if angle_difference > angle_threshold:
                    if abs(norm_dx) > abs(norm_dy):
                        new_direction = 'right' if norm_dx > 0 else 'left'
                    else:
                        new_direction = 'down' if norm_dy > 0 else 'up'

                    sim.current_direction = new_direction
                    sim.previous_direction = new_direction
                    sim.previous_angle = new_angle
                    sim.time_since_last_direction_change = 0.0  # Reset the timer
                    # print(f"Sim {sim.sim_id}: Direction changed to {sim.current_direction}")
            # Increment the timer
            # print(f"Sim {sim.sim_id}: Moving, direction={sim.current_direction}")
    # Update thought timer
    if sim.current_thought:
        sim.thought_timer -= dt
        if sim.thought_timer <= 0:
            sim.current_thought = None
    # else:
    #      # Path finished or invalid state, try finding a new one next update
    #      sim.path = None
    #      sim.target = None
    #      sim.path_index = 0

    # --- Mood Update based on Weather ---
    if weather_state in ["Rainy", "Snowy"]:
        sim.mood = max(-1.0, sim.mood - 0.005 * dt) # Slowly decrease mood in bad weather
    elif weather_state == "Sunny":
         sim.mood = min(1.0, sim.mood + 0.003 * dt) # Slowly increase mood in good weather

    # --- Interaction Check ---
    from aisim.src.core.sim import check_interactions
    check_interactions(sim, all_sims, logger, current_time)
    # Clamp mood
    sim.mood = max(-1.0, min(sim.mood, 1.0))
    sim.mood = max(-1.0, min(sim.mood, 1.0))

    # --- Log Mood ---
    if logger:
        logger.log_mood(current_time, sim.sim_id, sim.mood)
