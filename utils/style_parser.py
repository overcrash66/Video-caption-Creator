import re
from typing import Dict, List, Optional
import logging

class StyleParser:
    def __init__(self, supported_tags: Optional[List[str]] = None):
        """
        Initialize the StyleParser with optional custom supported tags.
        """
        self.supported_tags = supported_tags if supported_tags else {'b', 'i', 'center', 'font'}
        self.tag_pattern = re.compile(r'(<[^>]+>|</[^>]+>|[^<]+)')
        self.font_pattern = re.compile(r"<font\s+([^>]*)>", re.IGNORECASE)
        self.attr_pattern = re.compile(r"(\w+)=['\"]([^'\"]*)['\"]", re.IGNORECASE)

    def parse(self, text: str) -> Dict:
        """
        Parse the input text and extract styles.
        """
        styles = {'parts': [], 'current_style': {}}
        tag_stack = []
        style_stack = []

        for segment in self.tag_pattern.findall(text):
            if segment.startswith('<'):
                self._process_tag(segment, styles, tag_stack, style_stack)
            else:
                styles['parts'].append({
                    'text': segment,
                    'style': styles['current_style'].copy()
                })

        return styles

    def _process_tag(self, tag: str, styles: Dict, tag_stack: List[str], style_stack: List[Dict]):
        """
        Process a single tag and update the current style.
        """
        tag_lower = tag.lower()
        if tag_lower.startswith('</'):
            closing_tag = tag_lower[2:-1]
            if closing_tag in self.supported_tags:
                if tag_stack and tag_stack[-1] == closing_tag:
                    tag_stack.pop()
                    if style_stack:
                        styles['current_style'] = style_stack.pop()
        else:
            tag_name = tag_lower[1:-1].split()[0]
            if tag_name in self.supported_tags:
                style_stack.append(styles['current_style'].copy())
                self._apply_style(tag, tag_name, styles)
                tag_stack.append(tag_name)

    def _apply_style(self, tag: str, tag_name: str, styles: Dict):
        """
        Apply the style based on the tag.
        """
        tag_lower = tag.lower()
        if tag_name == 'b':
            styles['current_style']['bold'] = True
        elif tag_name == 'i':
            styles['current_style']['italic'] = True
        elif tag_name == 'center':
            styles['current_style']['align'] = 'center'
        elif tag_name == 'font':
            attrs = self._parse_font_attributes(tag_lower)
            styles['current_style'].update(attrs)
        logging.debug(f"Applied style: {styles['current_style']}")

    def _parse_font_attributes(self, tag: str) -> Dict:
        """
        Parse attributes from a <font> tag.
        """
        attrs = {}
        match = self.font_pattern.search(tag)
        if match:
            for name, value in self.attr_pattern.findall(match.group(1)):
                name_lower = name.lower()
                value = value.strip()
                if name_lower == 'size':
                    try:
                        attrs['size'] = int(value)
                    except ValueError:
                        logging.warning(f"Invalid font size: {value}")
                elif name_lower == 'face':
                    attrs['face'] = value
        return attrs