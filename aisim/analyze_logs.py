import argparse
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
import os
import glob
from collections import defaultdict

def find_latest_logs(log_dir="aisim/logs"):
    """Finds the most recent mood and interaction log files."""
    mood_pattern = os.path.join(log_dir, "mood_log_*.csv")
    interaction_pattern = os.path.join(log_dir, "interaction_log_*.csv")

    mood_files = glob.glob(mood_pattern)
    interaction_files = glob.glob(interaction_pattern)

    if not mood_files or not interaction_files:
        print("Error: No log files found in directory:", log_dir)
        return None, None

    latest_mood_log = max(mood_files, key=os.path.getctime)
    latest_interaction_log = max(interaction_files, key=os.path.getctime)

    # Basic check if logs seem to belong together (same timestamp prefix)
    mood_ts = os.path.basename(latest_mood_log).split('_')[2]
    interaction_ts = os.path.basename(latest_interaction_log).split('_')[2]
    if mood_ts != interaction_ts:
        print("Warning: Latest mood and interaction logs might be from different runs.")

    return latest_mood_log, latest_interaction_log

def plot_mood_trends(mood_log_path, output_dir="aisim/plots"):
    """Plots the average mood and individual Sim moods over time."""
    if not mood_log_path:
        return
    print(f"Analyzing mood log: {mood_log_path}")
    try:
        df = pd.read_csv(mood_log_path)
    except pd.errors.EmptyDataError:
        print("Mood log file is empty.")
        return
    except FileNotFoundError:
        print(f"Error: Mood log file not found: {mood_log_path}")
        return

    if df.empty:
        print("Mood log contains no data.")
        return

    # Ensure timestamp is numeric
    df['timestamp'] = pd.to_numeric(df['timestamp'])
    df['mood'] = pd.to_numeric(df['mood'])

    # Calculate average mood
    avg_mood = df.groupby('timestamp')['mood'].mean()

    # Plotting
    plt.figure(figsize=(12, 6))

    # Plot individual sim moods (optional, can be messy with many sims)
    # for sim_id, group in df.groupby('sim_id'):
    #     plt.plot(group['timestamp'], group['mood'], label=f"Sim {sim_id[:4]}...", alpha=0.3)

    # Plot average mood
    plt.plot(avg_mood.index, avg_mood.values, label='Average Mood', color='red', linewidth=2)

    plt.xlabel("Simulation Time (s)")
    plt.ylabel("Mood (-1 to 1)")
    plt.title("Sim Happiness Trends")
    plt.ylim(-1.1, 1.1)
    plt.grid(True)
    plt.legend()

    os.makedirs(output_dir, exist_ok=True)
    plot_filename = os.path.join(output_dir, f"mood_trends_{os.path.basename(mood_log_path).replace('.csv', '.png')}")
    plt.savefig(plot_filename)
    print(f"Mood trends plot saved to: {plot_filename}")
    plt.close()


def plot_social_network(interaction_log_path, output_dir="aisim/plots"):
    """Builds and plots the social network based on final friendship scores."""
    if not interaction_log_path:
        return
    print(f"Analyzing interaction log: {interaction_log_path}")
    try:
        df = pd.read_csv(interaction_log_path)
    except pd.errors.EmptyDataError:
        print("Interaction log file is empty.")
        return
    except FileNotFoundError:
        print(f"Error: Interaction log file not found: {interaction_log_path}")
        return

    if df.empty:
        print("Interaction log contains no data.")
        return

    # Calculate final friendship scores (simple sum for now)
    # A more robust way would be to track relationship state over time
    final_friendship = defaultdict(float)
    for _, row in df.iterrows():
        # Interactions are logged one-way, sum changes for both directions
        # This assumes the log captures the change applied to sim1's relationship towards sim2
        pair = tuple(sorted((row['sim1_id'], row['sim2_id'])))
        final_friendship[pair] += row['friendship_change']

    # Build graph
    G = nx.Graph()
    edges_with_weights = []
    nodes = set()

    for (sim1, sim2), friendship in final_friendship.items():
        if friendship > 0: # Only add edges for positive relationships
            weight = friendship # Use final score as weight (influences layout/color)
            G.add_edge(sim1[:6], sim2[:6], weight=weight) # Use short IDs for nodes
            edges_with_weights.append(weight)
            nodes.add(sim1[:6])
            nodes.add(sim2[:6])

    if not G.edges:
        print("No positive relationships found to build social network graph.")
        return

    # Plotting
    plt.figure(figsize=(10, 10))
    pos = nx.spring_layout(G, k=0.5, iterations=50) # Layout algorithm

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color='skyblue', alpha=0.8)

    # Draw edges with width/color based on weight
    edge_widths = [w * 5 for w in edges_with_weights] # Scale weights for visibility
    nx.draw_networkx_edges(G, pos, width=edge_widths, edge_color='gray', alpha=0.5)

    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=8)

    plt.title("Social Network Map (Friendship)")
    plt.axis('off') # Hide axes

    os.makedirs(output_dir, exist_ok=True)
    plot_filename = os.path.join(output_dir, f"social_network_{os.path.basename(interaction_log_path).replace('.csv', '.png')}")
    plt.savefig(plot_filename)
    print(f"Social network plot saved to: {plot_filename}")
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze AI Sims simulation logs.")
    parser.add_argument("--mood_log", help="Path to the mood log CSV file.")
    parser.add_argument("--interaction_log", help="Path to the interaction log CSV file.")
    parser.add_argument("--log_dir", default="aisim/logs", help="Directory containing log files (if specific files not provided).")

    args = parser.parse_args()

    mood_log = args.mood_log
    interaction_log = args.interaction_log

    if not mood_log or not interaction_log:
        print("Specific log files not provided, searching for latest logs in:", args.log_dir)
        mood_log, interaction_log = find_latest_logs(args.log_dir)

    if mood_log:
        plot_mood_trends(mood_log)
    else:
        print("Skipping mood trend plot (no log file found/specified).")

    if interaction_log:
        plot_social_network(interaction_log)
    else:
        print("Skipping social network plot (no log file found/specified).")