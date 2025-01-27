import re
import logging
from typing import List, Dict, Optional

class SRTParser:
    def __init__(self):
        self.time_pattern = re.compile(
            r'(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})'
        )
        self.html_tag_pattern = re.compile(r'<(/?\w+)(?:[^>]*)>')

    def parse(self, file_path: str) -> List[Dict]:
        entries = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                raw_entries = re.split(r'\n\s*\n', content.strip())
            
                for raw_entry in raw_entries:
                    entry = self.parse_entry(raw_entry)
                    if entry:
                        entries.append(entry)
        except Exception as e:
            logging.error(f"SRT parsing failed: {str(e)}")
        return entries

    def parse_entry(self, raw_entry: str) -> Optional[Dict]:
        lines = [line.strip() for line in raw_entry.split('\n') if line.strip()]
        if len(lines) < 3:
            return None

        # Extract and validate timecode
        time_match = self.time_pattern.search(lines[1])
        if not time_match:
            logging.error(f"Invalid time format in entry: {lines[1]}")
            return None

        try:
            start = self.parse_time(time_match.group(1))
            end = self.parse_time(time_match.group(2))
            return {
                'start': start,
                'end': end,
                'duration': end - start,
                'text': self.clean_html(' '.join(lines[2:]))
            }
        except Exception as e:
            logging.error(f"Error parsing entry: {str(e)}")
            return None

    def clean_html(self, text: str) -> str:
        """Preserve essential HTML tags while cleaning"""
        allowed_tags = {'b', 'i', 'font', 'center'}
        text = re.sub(self.html_tag_pattern, lambda m: m.group() if m.group(1) in allowed_tags else '', text)
        return text.replace('\n', ' ').strip()

    def parse_time(self, time_str: str) -> float:
        time_str = time_str.replace(',', '.').replace(';', ':')
        parts = re.split(r'[:.]', time_str)
        try:
            if len(parts) == 4:
                hours, mins, secs, msecs = parts
            elif len(parts) == 3:
                hours, mins, secs = parts
                msecs = '0'
            else:
                raise ValueError("Invalid time format")
                
            return (
                int(hours) * 3600 + 
                int(mins) * 60 + 
                int(secs) + 
                int(msecs.ljust(3, '0')[:3])/1000
            )
        except Exception as e:
            logging.error(f"Time parse error: {time_str} - {e}")
            return 0.0