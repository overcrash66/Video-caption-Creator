import unittest
from unittest.mock import Mock, patch
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from processors.image_generator import ImageGenerator
from PIL import Image
import os

class TestImageGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_manager = Mock()
        self.temp_manager.image_dir = "/tmp"
        self.style_parser = Mock()
        self.settings = {
            'font_size': 24,
            'margin': 20,
            'text_color': '#FFFFFF',
            'text_border': True,
            'text_shadow': False,
            'bg_color': '#000000',
            'default_duration': 5,
            'speed_factor': 1.2
        }
        self.image_generator = ImageGenerator(self.temp_manager, self.style_parser, self.settings)

    @patch('processors.image_generator.ImageGenerator._save_image')
    @patch('processors.image_generator.ImageGenerator._validate_image', return_value=True)
    def test_generate_images_valid_entries(self, mock_validate_image, mock_save_image):
        entries = [
            {'start_time': 0, 'end_time': 5, 'text': 'Hello World'},
            {'start_time': 6, 'end_time': 10, 'text': 'This is a test'}
        ]
        self.style_parser.parse.return_value = {'parts': [{'text': 'Hello World', 'style': {}}]}
        
        result = self.image_generator.generate_images(entries)
        
        self.assertEqual(len(result), 2)
        self.assertTrue(all('path' in img_info and 'duration' in img_info for img_info in result))
        self.assertGreaterEqual(result[0]['duration'], 4)
        self.assertLessEqual(result[0]['duration'], 5)
        self.assertGreaterEqual(result[1]['duration'], 4)
        self.assertLessEqual(result[1]['duration'], 5)

    @patch('processors.image_generator.ImageGenerator._save_image')
    @patch('processors.image_generator.ImageGenerator._validate_image', return_value=True)
    def test_generate_images_invalid_entries(self, mock_validate_image, mock_save_image):
        entries = [
            {'start_time': 0, 'end_time': 5, 'text': 'Hello World'},
            'invalid_entry',
            {'start_time': 6, 'end_time': 10, 'text': 'This is a test'}
        ]
        self.style_parser.parse.return_value = {'parts': [{'text': 'Hello World', 'style': {}}]}
        
        result = self.image_generator.generate_images(entries)
        
        self.assertEqual(len(result), 2)
        self.assertTrue(all('path' in img_info and 'duration' in img_info for img_info in result))
        self.assertGreaterEqual(result[0]['duration'], 4)
        self.assertLessEqual(result[0]['duration'], 5)
        self.assertGreaterEqual(result[1]['duration'], 4)
        self.assertLessEqual(result[1]['duration'], 5)

    @patch('processors.image_generator.ImageGenerator._save_image')
    @patch('processors.image_generator.ImageGenerator._validate_image', return_value=True)
    def test_generate_images_missing_fields(self, mock_validate_image, mock_save_image):
        entries = [
            {'start_time': 0, 'text': 'Hello World'},
            {'end_time': 10, 'text': 'This is a test'}
        ]
        self.style_parser.parse.return_value = {'parts': [{'text': 'Hello World', 'style': {}}]}
        
        result = self.image_generator.generate_images(entries)
        
        self.assertEqual(len(result), 0)

if __name__ == '__main__':
    unittest.main()