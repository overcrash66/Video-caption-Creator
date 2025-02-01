import unittest
import os, sys
import tempfile
from PIL import Image
import pytesseract
# Configure Tesseract path - update this path according to your system
if sys.platform.startswith('win'):
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if not os.path.exists(tesseract_path):
        raise RuntimeError(f"Tesseract not found at {tesseract_path}. Please install it first.")
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
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
            'speed_factor': 1.2,
            'batch_size': 50
        }
        self.image_generator = ImageGenerator(self.temp_manager, self.style_parser, self.settings)

    def tearDown(self):
        """Cleanup method to remove temporary directory."""
        self.temp_dir.cleanup()

    def test_generated_images_match_srt_duration_and_text(self):
        """Test that generated images match SRT duration and text."""
        srt_content = """1
        00:00:00,000 --> 00:00:05,000
        This is the first subtitle.
        
        2
        00:00:05,000 --> 00:00:10,000
        This is the second subtitle."""
        srt_file = os.path.join(self.temp_dir.name, "test.srt")
        with open(srt_file, "w", encoding='utf-8') as f:
            f.write(srt_content)

        entries = self.srt_parser.parse(srt_file)
        images = self.image_generator.generate_images(entries)

        self.assertEqual(len(images), len(entries))

        for image, entry in zip(images, entries):
            # Validate image duration
            self.assertAlmostEqual(image['duration'], entry['duration'], delta=0.7)  # Allow slight tolerance
            # Validate image text content using OCR
            img = Image.open(image['path'])
            extracted_text = pytesseract.image_to_string(img)
            self.assertIn(entry['text'].strip(), extracted_text.strip())
            img.close()

    # Add more test methods for other scenarios and edge cases

if __name__ == '__main__':
    unittest.main()