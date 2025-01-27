import re
from typing import Dict
import logging

class StyleParser:
    def __init__(self):
        self.tag_pattern = re.compile(r'(<[^>]+>|</[^>]+>|[^<]+)')
        self.font_pattern = re.compile(r"<font\s+([^>]*)>", re.IGNORECASE)
        self.attr_pattern = re.compile(r"(\w+)=['\"]([^'\"]*)['\"]", re.IGNORECASE)
        self.style_tags = {'b', 'i', 'center', 'font'}

    def parse(self, text: str) -> Dict:
        styles = {'parts': [], 'current_style': {}}
        tag_stack = []
        style_stack = []
        for segment in self.tag_pattern.findall(text):
            if segment.startswith('<'):
                self.process_tag(segment, styles, tag_stack, style_stack)
            else:
                styles['parts'].append({
                    'text': segment,
                    'style': styles['current_style'].copy()
                })
        return styles

    def process_tag(self, tag: str, styles: Dict, tag_stack: list, style_stack: list):
        tag_lower = tag.lower()
        if tag_lower.startswith('</'):
            closing_tag = tag_lower[2:-1]
            if closing_tag in self.style_tags:
                if tag_stack and tag_stack[-1] == closing_tag:
                    tag_stack.pop()
                    if style_stack:
                        styles['current_style'] = style_stack.pop()
        else:
            tag_name = tag_lower[1:-1].split()[0]
            if tag_name in self.style_tags:
                style_stack.append(styles['current_style'].copy())
                self.apply_style(tag, tag_name, styles)
                tag_stack.append(tag_name)

    def apply_style(self, tag: str, tag_name: str, styles: Dict):
        tag_lower = tag.lower()
        if tag_name == 'b':
            styles['current_style']['bold'] = True
        elif tag_name == 'i':
            styles['current_style']['italic'] = True
        elif tag_name == 'center':
            styles['current_style']['align'] = 'center'  # Apply center alignment
        elif tag_name == 'font':
            attrs = self.parse_font_attributes(tag_lower)
            styles['current_style'].update(attrs)
        logging.debug(f"Applied style: {styles['current_style']}")

    def parse_font_attributes(self, tag: str) -> Dict:
        attrs = {}
        match = self.font_pattern.search(tag)
        if match:
            for name, value in self.attr_pattern.findall(match.group(1)):
                name_lower = name.lower()
                value = value.strip()
                if name_lower == 'size':
                    if value.isdigit():
                        attrs['size'] = int(value)
                elif name_lower == 'face':
                    attrs['face'] = value
        return attrs