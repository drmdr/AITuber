import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add project root to sys.path to allow imports from x_poster
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from x_poster.morning_greet_poster import generate_ai_comment

class TestMorningGreetPoster(unittest.TestCase):

    def setUp(self):
        """Set up common test data."""
        self.config = {
            "gemini_api_key": "fake_api_key",
            "character_name": "テストキャラ",
            "persona": "テストペルソナ"
        }
        self.service_name = "Test Service"
        self.max_length = 100

    @patch('x_poster.morning_greet_poster.genai.GenerativeModel')
    def test_generate_ai_comment_for_nft_service(self, mock_generative_model):
        """
        Test if the correct prompt is generated for an NFT-related service.
        """
        # Arrange
        mock_model_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "category": "NFT",
            "ja": "テストコメント",
            "en": "Test comment"
        })
        mock_model_instance.generate_content.return_value = mock_response
        mock_generative_model.return_value = mock_model_instance

        service_description_nft = "This is a cool NFT project."

        # Act
        generate_ai_comment(self.config, self.service_name, service_description_nft, self.max_length)

        # Assert
        mock_model_instance.generate_content.assert_called_once()
        args, kwargs = mock_model_instance.generate_content.call_args
        actual_prompt = args[0]

        self.assertIn("「持ってる人いる？」「ミントした？」", actual_prompt)
        self.assertNotIn("「使ったことある？」「みんなはどう思う？」", actual_prompt)

    @patch('x_poster.morning_greet_poster.genai.GenerativeModel')
    def test_generate_ai_comment_for_web_service(self, mock_generative_model):
        """
        Test if the correct prompt is generated for a non-NFT (web) service.
        """
        # Arrange
        mock_model_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "category": "Webサービス",
            "ja": "テストコメント",
            "en": "Test comment"
        })
        mock_model_instance.generate_content.return_value = mock_response
        mock_generative_model.return_value = mock_model_instance

        service_description_web = "This is a useful web service."

        # Act
        generate_ai_comment(self.config, self.service_name, service_description_web, self.max_length)

        # Assert
        mock_model_instance.generate_content.assert_called_once()
        args, kwargs = mock_model_instance.generate_content.call_args
        actual_prompt = args[0]

        self.assertIn("「使ったことある？」「みんなはどう思う？」", actual_prompt)
        self.assertNotIn("「持ってる人いる？」「ミントした？」", actual_prompt)

if __name__ == '__main__':
    unittest.main()
