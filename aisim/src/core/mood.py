def get_mood_description(mood_value):
        """Converts mood float (-1 to 1) to a descriptive string."""
        if mood_value < -0.7: return "Very Sad"
        if mood_value < -0.3: return "Sad"
        if mood_value < 0.3: return "Neutral"
        if mood_value < 0.7: return "Happy"
        return "Very Happy"
