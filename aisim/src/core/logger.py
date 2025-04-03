import csv
import os
import datetime

class Logger:
    """Handles logging simulation data to CSV files."""

    def __init__(self, log_dir="aisim/logs"):
        """Initializes the logger and creates log files."""
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.mood_log_path = os.path.join(self.log_dir, f"mood_log_{timestamp_str}.csv")
        self.interaction_log_path = os.path.join(self.log_dir, f"interaction_log_{timestamp_str}.csv")

        self._setup_files()

    def _setup_files(self):
        """Opens log files and writes headers."""
        # Mood Log
        self.mood_file = open(self.mood_log_path, 'w', newline='')
        self.mood_writer = csv.writer(self.mood_file)
        self.mood_writer.writerow(['timestamp', 'sim_id', 'mood'])
        print(f"Logging mood to: {self.mood_log_path}")

        # Interaction Log
        self.interaction_file = open(self.interaction_log_path, 'w', newline='')
        self.interaction_writer = csv.writer(self.interaction_file)
        self.interaction_writer.writerow(['timestamp', 'sim1_id', 'sim2_id', 'friendship_change'])
        print(f"Logging interactions to: {self.interaction_log_path}")

    def log_mood(self, timestamp, sim_id, mood):
        """Logs a Sim's mood at a specific timestamp."""
        if self.mood_writer:
            self.mood_writer.writerow([f"{timestamp:.2f}", sim_id, f"{mood:.3f}"])

    def log_interaction(self, timestamp, sim1_id, sim2_id, friendship_change):
        """Logs an interaction between two Sims."""
        if self.interaction_writer:
             # Log interaction from sim1's perspective (sim2 could be logged separately if needed)
            self.interaction_writer.writerow([f"{timestamp:.2f}", sim1_id, sim2_id, f"{friendship_change:.3f}"])

    def close(self):
        """Closes the log files."""
        if self.mood_file:
            self.mood_file.close()
            self.mood_file = None
            self.mood_writer = None
            print("Mood log closed.")
        if self.interaction_file:
            self.interaction_file.close()
            self.interaction_file = None
            self.interaction_writer = None
            print("Interaction log closed.")