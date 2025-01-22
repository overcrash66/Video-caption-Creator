import re
import logging
from typing import List, Dict, Optional

class SRTParser:
    def __init__(self):
        self.time_pattern = re.compile(
            r'(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})'
        )

    def parse(self, file_path: str) -> List[Dict]:
        entries = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                raw_entries = re.split(r'\n\s*\n|\r\n\s*\r\n', content.strip())
                
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

        time_match = self.time_pattern.search(lines[1])
        if not time_match:
            return None

        start_time = self.parse_time(time_match.group(1))
        end_time = self.parse_time(time_match.group(2))
        text = ' '.join(lines[2:])

        return {
            'start': start_time,
            'end': end_time,
            'duration': end_time - start_time,
            'text': text
        }

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