import unittest
import time
import pygame
from unittest.mock import MagicMock, patch
from aisim.src.core.sim import Sim
from aisim.src.ai.ollama_client import OllamaClient
from aisim.src.core.city import City
from aisim.src.core.interaction import handle_ollama_response, initiate_conversation, _send_conversation_request

class TestConversation(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.ollama_client = OllamaClient() # Initialize real Ollama client
        self.ollama_client.max_concurrent_requests = 2

    def tearDown(self):
        pygame.quit()

    @patch('aisim.src.core.city.City._create_tile_map')
    @patch('aisim.src.core.sim.Sim._load_sprite_sheet')
    def test_sim_conversation(self, mock_load_sprite, mock_create_tile_map):
        # Mock OllamaClient and its response
        mock_load_sprite.return_value = ("Abigail_Chen", MagicMock())
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
        sim1.first_name = "Abigail_Chen"
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
        sim2.first_name = "Adam_Smith"
        sim2.personality_description = "Curious and friendly"

        # Create City instance
        city = City(800, 600)

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
        mock_load_sprite.return_value = ("Abigail_Chen", MagicMock())
        mock_create_tile_map.return_value = None

        # Create Sim instances - personalities will be loaded automatically
        sim1 = Sim(
            sim_id="sim1",
            x=10,
            y=20,
            ollama_client=self.ollama_client,
            enable_talking=True,
            sim_config={"character_name": "Abigail_Chen"},
            bubble_display_time=5.0
        )

        sim2 = Sim(
            sim_id="sim2",
            x=30,
            y=40,
            ollama_client=self.ollama_client,
            enable_talking=True,
            sim_config={"character_name": "Adam_Smith"},
            bubble_display_time=5.0
        )

        # Create City instance
        city = City(800, 600)

        # Set up interaction (Note: _initiate_conversation will set these)
        all_sims = [sim1, sim2]
        # Let sim1 speak first in this test scenario
        sim1.is_my_turn_to_speak = True
        sim2.is_my_turn_to_speak = False

        # Call initiate_conversation and send_conversation_request from interaction module
        initiate_conversation(sim1, sim2, city, all_sims, time.time())

        # Determine who the first speaker was for assertion purposes later
        if sim1.is_my_turn_to_speak:
             first_speaker = sim1
             second_speaker_listener = sim2
        else:
             first_speaker = sim2
             second_speaker_listener = sim1

        # Simulate polling for the response
        response_processed = False
        start_time = time.time()
        timeout = 10.0 # seconds

        while time.time() - start_time < timeout:
            result = self.ollama_client.check_for_thought_results()
            if result:
                sim_id, response_text = result
                print(f"Test received result for {sim_id}: {response_text}") # Debug log
                # Find the sim instance that corresponds to the sim_id
                sim_instance = next((s for s in all_sims if s.sim_id == sim_id), None)
                if sim_instance:
                     # Call the handler function from the interaction module
                     handle_ollama_response(sim_instance, response_text, time.time(), all_sims, city)
                     # Check if the response was for the first speaker
                     if sim_id == first_speaker.sim_id:
                           response_processed = True
                           break # Exit loop once the first speaker's response is handled
                else:
                     print(f"Test Warning: Received result for unknown sim_id {sim_id}")
            time.sleep(0.1) # Short sleep to avoid busy-waiting

        if not response_processed:
             print(f"Test Warning: Timed out waiting for response from {first_speaker.sim_id}")

        # Assertions (Check the speaker who sent the request)
        self.assertIsNotNone(first_speaker.conversation_message, "Conversation message should not be None after response")
        self.assertGreater(len(first_speaker.conversation_message), 0, "Conversation message should not be empty after response")
        print(f"Sim {first_speaker.sim_id} conversation message: {first_speaker.conversation_message}")

        # Assertions (Check the listener who should receive the response next turn)
        self.assertIsNotNone(second_speaker_listener.conversation_history[-1]['line'], "Conversation history should not be None after response")
        self.assertGreater(len(second_speaker_listener.conversation_history[-1]['line']), 0, "Conversation history should not be empty after response")
        print(f"Sim {second_speaker_listener.sim_id} conversation history: {second_speaker_listener.conversation_history}")


if __name__ == '__main__':
    unittest.main()