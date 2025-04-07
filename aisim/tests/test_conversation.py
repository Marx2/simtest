import unittest
import time
import pygame
from unittest.mock import MagicMock, patch
from aisim.src.core.sim import Sim
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.city import City
from aisim.src.core.configuration import config_manager
# Import the functions directly from the interaction module
from aisim.src.core.interaction import handle_ollama_response, _initiate_conversation, _send_conversation_request

class TestConversation(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.ollama_client = OllamaClient() # Initialize real Ollama client

    def tearDown(self):
        pygame.quit()

    @patch('aisim.src.core.city.City._create_tile_map')
    @patch('aisim.src.core.sim.Sim._load_sprite_sheet')
    def test_sim_conversation(self, mock_load_sprite, mock_create_tile_map):
        # Mock OllamaClient and its response
        mock_load_sprite.return_value = ("Test_Sim", MagicMock())
        mock_create_tile_map.return_value = None

        response_text = "This is a test response from Ollama."

        # Create Sim instances
        sim1 = Sim(
            sim_id="sim1",
            x=10,
            y=20,
            ollama_client=self.ollama_client,
            enable_talking=True,
            sim_config={},
            bubble_display_time=5.0
        )
        sim1.first_name = "Alice"
        sim1.personality_description = "Kind and helpful"

        sim2 = Sim(
            sim_id="sim2",
            x=30,
            y=40,
            ollama_client=self.ollama_client,
            enable_talking=True,
            sim_config={},
            bubble_display_time=5.0
        )
        sim2.first_name = "Bob"
        sim2.personality_description = "Curious and friendly"

        # Create City instance
        city = City(800, 600)
        city.active_conversation_partners = set()

        # Set up interaction
        sim1.is_interacting = True
        sim2.is_interacting = True
        sim1.conversation_partner_id = "sim2"
        sim2.conversation_partner_id = "sim1"
        all_sims = [sim1, sim2]

        # Call handle_ollama_response for sim1
        # Pass sim1 as the first argument (representing 'self')
        handle_ollama_response(sim1, "Test response", time.time(), all_sims, city)

        # Assertions
        self.assertEqual(sim1.conversation_message, "Test response")
        self.assertEqual(sim2.conversation_history[-1]['line'], "Test response")
        self.assertFalse(sim1.is_my_turn_to_speak)
        self.assertTrue(sim2.is_my_turn_to_speak)

    @patch('aisim.src.core.city.City._create_tile_map')
    @patch('aisim.src.core.sim.Sim._load_sprite_sheet')
    def test_sim_conversation_ollama(self, mock_load_sprite, mock_create_tile_map):
        # This test uses the real Ollama client
        mock_load_sprite.return_value = ("Test_Sim", MagicMock())
        mock_create_tile_map.return_value = None

        # Create Sim instances
        sim1 = Sim(
            sim_id="sim1",
            x=10,
            y=20,
            ollama_client=self.ollama_client,
            enable_talking=True,
            sim_config={},
            bubble_display_time=5.0
        )
        sim1.first_name = "Alice"
        sim1.personality_description = "What is your name?"

        sim2 = Sim(
            sim_id="sim2",
            x=30,
            y=40,
            ollama_client=self.ollama_client,
            enable_talking=True,
            sim_config={},
            bubble_display_time=5.0
        )
        sim2.first_name = "Bob"
        sim2.personality_description = "My name is Bob"

        # Create City instance
        city = City(800, 600)
        city.active_conversation_partners = set()

        # Set up interaction
        sim1.is_interacting = True
        sim2.is_interacting = True
        sim1.conversation_partner_id = "sim2"
        sim2.conversation_partner_id = "sim1"
        all_sims = [sim1, sim2]
        # Let sim1 speak first in this test scenario
        sim1.is_my_turn_to_speak = True
        sim2.is_my_turn_to_speak = False

        # Call initiate_conversation and send_conversation_request from interaction module
        _initiate_conversation(sim1, sim2, city, all_sims, time.time())

        # Determine who speaks first based on the state set by _initiate_conversation
        if sim1.is_my_turn_to_speak:
            first_speaker = sim1
            second_speaker_listener = sim2
        else:
            first_speaker = sim2
            second_speaker_listener = sim1

        # Send the request using the determined first speaker
        # Pass the first_speaker as the 'self' argument for _send_conversation_request
        _send_conversation_request(first_speaker,first_speaker, second_speaker_listener, city, all_sims)

        # Wait for Ollama response (adjust sleep time if needed)
        time.sleep(5)

        # Check Ollama results (need to simulate polling or check directly)
        # This part is tricky without the main loop's polling mechanism
        # For now, we assume the response might be processed and check the message
        # A more robust test would mock the check_for_thought_results part

        # Assertions (Check the speaker who sent the request)
        self.assertIsNotNone(first_speaker.conversation_message, "Conversation message should not be None after response")
        self.assertGreater(len(first_speaker.conversation_message), 0, "Conversation message should not be empty after response")
        print(f"Sim {first_speaker.sim_id} conversation message: {first_speaker.conversation_message}")


if __name__ == '__main__':
    unittest.main()