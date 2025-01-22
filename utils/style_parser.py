import re
from typing import Dict

class StyleParser:
    def __init__(self):
        self.tag_pattern = re.compile(r'(<[^>]+>|<\/[^>]+>|[^<]+)')

    def parse(self, text: str) -> Dict:
        styles = {'parts': [], 'current_style': {}}
        for segment in self.tag_pattern.findall(text):
            self.process_segment(segment, styles)
        return styles

    def process_segment(self, segment: str, styles: Dict):
        if segment.startswith('<b>'):
            styles['current_style']['bold'] = True
        elif segment.startswith('</b>'):
            styles['current_style'].pop('bold', None)
        elif segment.startswith('<i>'):
            styles['current_style']['italic'] = True
        elif segment.startswith('</i>'):
            styles['current_style'].pop('italic', None)
        elif segment.startswith('<font'):
            self.process_font_tag(segment, styles)
        elif segment.startswith('</font>'):
            styles['current_style'].pop('size', None)
            styles['current_style'].pop('face', None)
        else:
            styles['parts'].append({
                'text': segment,
                'style': styles['current_style'].copy()
            })

    def process_font_tag(self, tag: str, styles: Dict):
        size_match = re.search(r"size=['\"](\d+)['\"]", tag)
        if size_match:
            styles['current_style']['size'] = int(size_match.group(1))
        
        face_match = re.search(r"face=['\"](.+?)['\"]", tag)
        if face_match:
            styles['current_style']['face'] = face_match.group(1)