from typing import List, Dict, Optional
import re
import logging
import srt 

class SRTParser:
    def __init__(self):
        self.time_pattern = re.compile(
            r'(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})'
        )
        self.html_tag_pattern = re.compile(r'<(/?\w+)(?:[^>]*)>')

    def parse(self, file_path: str) -> list[dict]:
        entries = []
        errors = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                raw_entries = re.split(r'\n\s*\n', content.strip())
            
                for idx, raw_entry in enumerate(raw_entries):
                    entry = self.parse_entry(raw_entry)
                    if entry:
                        entries.append(entry)
                    else:
                        errors.append(f"Entry {idx + 1} is invalid: {raw_entry[:100]}")

        except Exception as e:
            logging.error(f"SRT parsing failed: {str(e)}")
            return []

        if errors:
            logging.warning(f"Parsing completed with {len(errors)} issues.")
            for error in errors:
                logging.warning(error)

        return entries

    def parse_entry(self, raw_entry: str) -> Optional[Dict]:
        lines = [line.strip() for line in raw_entry.split('\n') if line.strip()]
        
        logging.debug(f"Parsing entry: {raw_entry[:100]}")

        if len(lines) < 3 or not self.time_pattern.search(lines[1]):
            logging.error(f"Entry is invalid or missing required lines: {lines}")
            return None

        time_match = self.time_pattern.search(lines[1])
        if not time_match:
            logging.error(f"Invalid time format in entry: {lines[1]}")
            return None

        try:
            start = self.parse_time(time_match.group(1))
            end = self.parse_time(time_match.group(2))
            if start >= end:
                logging.error(f"Start time is not before end time: {lines[1]}")
                return None
            return {
                'start_time': start,  # Ensure keys match exactly here
                'end_time': end,
                'duration': end - start,
                'text': self.clean_html(' '.join(lines[2:]))
            }
        except Exception as e:
            logging.error(f"Error parsing entry: {lines} - {str(e)}")
            return None

    def clean_html(self, text: str) -> str:
        allowed_tags = {'b', 'i', 'font', 'center'}
        text = re.sub(self.html_tag_pattern, lambda m: m.group() if m.group(1).replace('/', '') in allowed_tags else '', text)
        return text.replace('\n', ' ').strip()

    def parse_time(self, time_str: str) -> float:
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        try:
            if len(parts) == 3:
                hours, mins, secs_msecs = parts
                secs, msecs = (secs_msecs.split('.') if '.' in secs_msecs else (secs_msecs, '0'))
            elif len(parts) == 2:
                hours = '0'
                mins, secs_msecs = parts
                secs, msecs = (secs_msecs.split('.') if '.' in secs_msecs else (secs_msecs, '0'))
            else:
                raise ValueError("Invalid time format")
            total_seconds = (
                int(hours) * 3600 +
                int(mins) * 60 +
                int(secs) +
                int(msecs.ljust(3, '0')[:3]) / 1000.0
            )
            return total_seconds
        except Exception as e:
            logging.error(f"Time parse error: {time_str} - {e}")
            return 0.0
