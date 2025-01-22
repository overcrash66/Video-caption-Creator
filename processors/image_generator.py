from PIL import Image, ImageDraw, ImageFont
import html
import logging
import os
from typing import Dict, List, Optional
from utils.style_parser import StyleParser
from concurrent import futures

class ImageGenerator:
    def __init__(self, temp_manager, style_parser: StyleParser, settings: dict):
        self.temp_manager = temp_manager
        self.style_parser = style_parser
        self.settings = settings.copy()
    
    def create_base_image(self) -> Image.Image:
        """Create base image using stored settings"""
        bg_image = self.settings.get('background_image')
        bg_color = self.settings.get('bg_color', '#000000')
        
        if bg_image:
            try:
                img = Image.open(bg_image)
                return img.convert('RGB').resize((1280, 720))
            except Exception as e:
                logging.error(f"Background image error: {str(e)}")
        return Image.new('RGB', (1280, 720), bg_color)

    def generate_images(self, entries: List[Dict]) -> List[Dict]:
        generated = []
        for idx, entry in enumerate(entries):
            if self.has_style_tags(entry['text']):
                img_info = self.generate_styled_image(entry, idx)
            else:
                img_info = self.generate_simple_image(entry, idx)
            if img_info:
                generated.append(img_info)
        return generated

    def generate_preview(self, text: str, preview_settings: Dict) -> Image.Image:
        img = self.create_base_image()
        draw = ImageDraw.Draw(img)
        y = 10
        
        styled_parts = self.style_parser.parse(text)['parts']
        for part in styled_parts:
            font = self.get_font(
                part['style'].get('face', 'Arial'),
                part['style'].get('size', preview_settings['font_size']),
                part['style'].get('bold', False),
                part['style'].get('italic', False),
                preview_settings.get('custom_font')
            )
            
            if preview_settings.get('text_shadow', False):
                self.draw_text_with_shadow(draw, part['text'], (20, y), font, preview_settings)
                
            if preview_settings.get('text_border', False):
                self.draw_text_border(draw, part['text'], (20, y), font)
                
            draw.text((20, y), part['text'], font=font, fill=preview_settings.get('text_color', '#FFFFFF'))
            y += font.getbbox(part['text'])[3] + 5
            
        return img

    def generate_simple_image(self, entry: Dict, idx: int) -> Optional[Dict]:
        try:
            margin = self.settings.get('margin', 20)
            font_size = self.settings.get('font_size', 24)
            text_color = self.settings.get('text_color', '#FFFFFF')
            speed_factor = self.settings.get('speed_factor', 1.0)
            custom_font = self.settings.get('custom_font')
            
            img = self.create_base_image()
            draw = ImageDraw.Draw(img)

            text = html.unescape(entry['text'])
            font = self.get_font('Arial', font_size, False, False, custom_font)
            
            border_offset = 4
            max_width = 1280 - (margin * 2) - border_offset
            max_height = 720 - (margin * 2) - border_offset
            
            wrapped = self.wrap_text(text, font, max_width)
            line_heights = [font.getbbox(line)[3] for line in wrapped]
            total_height = sum(line_heights)
            
            y_position = max(
                margin,
                min((720 - total_height) // 2, 720 - total_height - margin)
            )
            
            for line, line_height in zip(wrapped, line_heights):
                line_width = font.getlength(line)
                x_position = max(
                    margin,
                    min((1280 - line_width) // 2, 1280 - line_width - margin)
                )
                
                self.draw_text_line(draw, line, (x_position, y_position), font)
                y_position += line_height
                
            path = os.path.join(self.temp_manager.image_dir, f"frame_{idx:06d}.png")
            img.save(path)
            return {'path': path, 'duration': entry['duration'] / speed_factor}
        except Exception as e:
            logging.error(f"Simple image failed: {str(e)}")
            return None

    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        lines = []
        for paragraph in text.split('\n'):
            current_line = []
            current_length = 0
            words = paragraph.split(' ')
            
            for word in words:
                word_length = font.getlength(word)
                if word_length > max_width:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = []
                    lines.append(word)
                    continue
                    
                if current_length + font.getlength(word + ' ') > max_width:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = font.getlength(word + ' ')
                else:
                    current_line.append(word)
                    current_length += font.getlength(word + ' ')
                    
            if current_line:
                lines.append(' '.join(current_line))
        return lines

    def generate_styled_image(self, entry: Dict, idx: int) -> Optional[Dict]:
        try:
            margin = self.settings.get('margin', 20)
            font_size = self.settings.get('font_size', 24)
            speed_factor = self.settings.get('speed_factor', 1.0)
            custom_font = self.settings.get('custom_font')
            
            img = self.create_base_image()
            draw = ImageDraw.Draw(img)
            styled = self.style_parser.parse(entry['text'])
            y_position = margin
            
            for part in styled['parts']:
                part_font_size = part['style'].get('size', font_size)
                font = self.get_font(
                    part['style'].get('face', 'Arial'),
                    part_font_size,
                    part['style'].get('bold', False),
                    part['style'].get('italic', False),
                    custom_font
                )
                
                wrapped = self.wrap_text(part['text'], font, 1280 - (margin * 2))
                
                for line in wrapped:
                    line_width = font.getlength(line)
                    x_position = max(
                        margin,
                        min((1280 - line_width) // 2, 1280 - line_width - margin)
                    )
                    
                    line_height = font.getbbox(line)[3]
                    if y_position + line_height > 720 - margin:
                        break
                    
                    self.draw_text_line(draw, line, (x_position, y_position), font)
                    y_position += line_height + 5
                    
            path = os.path.join(self.temp_manager.image_dir, f"styled_{idx:06d}.png")
            img.save(path)
            return {'path': path, 'duration': entry['duration'] / speed_factor}
        except Exception as e:
            logging.error(f"Styled image failed: {str(e)}")
            return None

    def get_font(self, face: str, size: int, bold: bool, italic: bool, custom_font: Optional[str]):
        try:
            if custom_font:
                return ImageFont.truetype(custom_font, size)
            else:
                font_path = None
                if bold and italic:
                    font_path = "arialbi.ttf"
                elif bold:
                    font_path = "arialbd.ttf"
                elif italic:
                    font_path = "ariali.ttf"
                else:
                    font_path = "arial.ttf"
                return ImageFont.truetype(font_path, size)
        except IOError:
            try:
                return ImageFont.truetype(face, size)
            except:
                return ImageFont.load_default(size)

    def draw_text_with_shadow(self, draw, text: str, position: tuple, font: ImageFont.FreeTypeFont, settings: Dict):
        x, y = position
        shadow_color = (0, 0, 0)
        for i in range(3):
            draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
            draw.text((x - 2, y + 2), text, font=font, fill=shadow_color)
            draw.text((x + 2, y - 2), text, font=font, fill=shadow_color)
            draw.text((x - 2, y - 2), text, font=font, fill=shadow_color)    

    def draw_text_border(self, draw, text: str, position: tuple, font: ImageFont.FreeTypeFont):
        x, y = position
        border_color = (0, 0, 0)
        offsets = [-2, -1, 0, 1, 2]
        
        for dx in offsets:
            for dy in offsets:
                if dx == 0 and dy == 0:
                    continue
                draw.text((x+dx, y+dy), text, font=font, fill=border_color)

    def draw_text_line(self, draw, text: str, position: tuple, font: ImageFont.FreeTypeFont):
        text_color = self.settings.get('text_color', '#FFFFFF')
        border = self.settings.get('text_border', False)
        if border:
            self.draw_text_border(draw, text, position, font)
        draw.text(position, text, font=font, fill=text_color)

    def has_style_tags(self, text: str) -> bool:
        return any(tag in text for tag in ['<b>', '<i>', '<font'])