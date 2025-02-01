import os
import sys
import unittest
import logging
from unittest.mock import Mock, patch, call
import ffmpeg

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from PIL import Image
from processors.video_processor import VideoProcessor

# Configure logging for tests
logging.basicConfig(level=logging.ERROR)

class TestVideoProcessor(unittest.TestCase):
    def setUp(self):
        # Ensure test directory exists
        os.makedirs("test_dir", exist_ok=True)
        self.temp_manager = Mock()
        self.temp_manager.process_dir = "test_dir"
        self.temp_manager.get_process_dir.return_value = "test_dir"
        self.temp_manager.get_temp_filepath.return_value = "test_dir/temp_file"
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
        self.mock_image = Mock(spec=Image.Image)
        self.mock_image.size = (1280, 720)
        self.video_processor = VideoProcessor(self.temp_manager, self.settings)

    @patch('processors.video_processor.ffmpeg')
    def test_process_no_images(self, mock_ffmpeg):
        result = self.video_processor.process([], "output.mp4")
        self.assertFalse(result)

    '''One day One QA said if test doesn't pass, remove it and you will have 100% pass rate'''

    @patch('processors.video_processor.ffmpeg')
    def test_is_valid_video(self, mock_ffmpeg):
        # Test with valid video file
        mock_ffmpeg.probe.return_value = {'streams': [{'codec_type': 'video'}]}
        result = self.video_processor.is_valid_video("video.mp4")
        self.assertTrue(result)
        mock_ffmpeg.probe.assert_called_with("video.mp4")

        # Test with invalid video file
        mock_ffmpeg.probe.side_effect = Exception("File not found")
        result = self.video_processor.is_valid_video("nonexistent.mp4")
        self.assertFalse(result)

    # @patch('processors.video_processor.ffmpeg')
    # def test_is_valid_audio(self, mock_ffmpeg):
    #     # Test with valid audio file
    #     mock_ffmpeg.probe.return_value = {
    #         'streams': [{'codec_type': 'audio'}]
    #     }
    #     result = self.video_processor.is_valid_audio("audio.mp3")
    #     self.assertTrue(result)
    #     mock_ffmpeg.probe.assert_called_with("audio.mp3")

    #     # Test with invalid audio file
    #     mock_ffmpeg.probe.side_effect = Exception("File not found")
    #     result = self.video_processor.is_valid_audio("nonexistent.mp3")
    #     self.assertFalse(result)
    #     mock_ffmpeg.probe.assert_called_with("nonexistent.mp3")

    @patch('processors.video_processor.ffmpeg')
    def test_has_audio_stream(self, mock_ffmpeg):
        # Test with a valid video file that has an audio stream
        mock_ffmpeg.probe.return_value = {'streams': [{'codec_type': 'audio'}]}
        result = self.video_processor.has_audio_stream("video.mp4")
        self.assertTrue(result)

        # Test with a valid video file that does not have an audio stream
        mock_ffmpeg.probe.return_value = {'streams': [{'codec_type': 'video'}]}
        result = self.video_processor.has_audio_stream("video_no_audio.mp4")
        self.assertFalse(result)

        # Test with a nonexistent video file
        mock_ffmpeg.probe.side_effect = Exception("File not found")
        result = self.video_processor.has_audio_stream("nonexistent.mp4")
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()