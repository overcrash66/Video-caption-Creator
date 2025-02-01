import unittest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from unittest.mock import patch, mock_open
from processors.srt_parser import SRTParser

class TestSRTParser(unittest.TestCase):
    def setUp(self):
        self.parser = SRTParser()

    @patch("builtins.open", new_callable=mock_open, read_data="1\n00:00:01,000 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n")
    def test_parse_valid_file(self, mock_file):
        result = self.parser.parse("dummy_path.srt")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['text'], "Hello")
        self.assertEqual(result[1]['text'], "World")

    @patch("builtins.open", new_callable=mock_open, read_data="1\n00:00:01,000 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:02,000\nWorld\n")
    def test_parse_invalid_time(self, mock_file):
        result = self.parser.parse("dummy_path.srt")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], "Hello")

    @patch("builtins.open", new_callable=mock_open, read_data="1\n00:00:01,000 --> 00:00:02,000\nHello\n\n2\nInvalid time\nWorld\n")
    def test_parse_invalid_format(self, mock_file):
        result = self.parser.parse("dummy_path.srt")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], "Hello")

    @patch("builtins.open", new_callable=mock_open, read_data="")
    def test_parse_empty_file(self, mock_file):
        result = self.parser.parse("dummy_path.srt")
        self.assertEqual(result, [])

    @patch("builtins.open", new_callable=mock_open, read_data="1\n00:00:01,000 --> 00:00:02,000\n<b>Hello</b>\n\n2\n00:00:03,000 --> 00:00:04,000\n<i>World</i>\n")
    def test_parse_with_html_tags(self, mock_file):
        result = self.parser.parse("dummy_path.srt")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['text'], "<b>Hello</b>")
        self.assertEqual(result[1]['text'], "<i>World</i>")

if __name__ == "__main__":
    unittest.main()