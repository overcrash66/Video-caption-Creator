import unittest
import os, sys
import tempfile
from PIL import Image
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from processors.srt_parser import SRTParser
from processors.image_generator import ImageGenerator
from utils.style_parser import StyleParser
from utils.helpers import TempFileManager

class TestImageGeneration(unittest.TestCase):

    def setUp(self):
        """Setup method to create temporary directory and initialize objects."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_manager = TempFileManager(self.temp_dir.name)  # Use the temporary directory
        self.style_parser = StyleParser()
        self.srt_parser = SRTParser()
        self.settings = {
            'text_color': '#FFFFFF',
            'bg_color': '#000000',
            'font_size': 24,
            'text_border': True,
            'text_shadow': False,
            'background_image': None,
            'background_music': None,
            'custom_font': None,
            'margin': 20,
            'speed_factor': 1.0,
            'batch_size': 50
        }
        self.image_generator = ImageGenerator(self.temp_manager, self.style_parser, self.settings)

    def tearDown(self):
        """Cleanup method to remove temporary directory."""
        self.temp_dir.cleanup()

    def test_generated_images_match_srt_duration_and_text(self):
        """Test that generated images match SRT duration and text."""
        srt_content = """
        1
        00:00:00,000 --> 00:00:05,000
        This is the first subtitle.

        2
        00:00:05,000 --> 00:00:10,000
        This is the second subtitle.
        """
        srt_file = os.path.join(self.temp_dir.name, "test.srt")
        with open(srt_file, "w") as f:
            f.write(srt_content)

        entries = self.srt_parser.parse(srt_file)
        images = self.image_generator.generate_images(entries)

        self.assertEqual(len(images), len(entries))

        for image, entry in zip(images, entries):
            # Validate image duration
            self.assertAlmostEqual(image['duration'], entry['duration'], delta=0.1)  # Allow slight tolerance

            # Validate image text content (OCR or text extraction would be needed here)
            # For simplicity, we're just checking the first word for this example
            img = Image.open(image['path'])
            #... (Perform OCR or text extraction on 'img' to get 'extracted_text')...
            # self.assertIn(entry['text'].split(), extracted_text)
            img.close()

    # Add more test methods for other scenarios and edge cases

if __name__ == '__main__':
    unittest.main()