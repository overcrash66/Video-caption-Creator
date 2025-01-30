from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageOps
import html
import logging
import os
from typing import Dict, List, Optional
from utils.style_parser import StyleParser

class ImageGenerator:
    def __init__(self, temp_manager, style_parser: StyleParser, settings: dict):
        self.temp_manager = temp_manager
        self.style_parser = style_parser
        self.settings = settings.copy()
        self.font_cache = {}

    def generate_images(self, entries: List[Dict]) -> List[Dict]:
        generated = [None] * len(entries)  # Pre-allocate to maintain positions
    
        for idx, entry in enumerate(entries):
            logging.debug(f"Processing entry {idx}: {entry}")

            if not isinstance(entry, dict):
                logging.error(f"Entry {idx} is not a dictionary: {entry}")
                continue

            if 'start_time' not in entry or 'end_time' not in entry:
                logging.error(f"Entry {idx} is missing 'start_time' or 'end_time': {entry}")
                continue

            try:
                if self._has_style_tags(entry['text']):
                    img_info = self.generate_styled_image(entry, idx)
                else:
                    img_info = self.generate_simple_image(entry, idx)
            
                if img_info and self._validate_image(img_info['path']):
                    generated[idx] = img_info  # Maintain original index position
            except Exception as e:
                logging.error(f"Image generation failed for entry {idx}: {str(e)}")
    
        return [img for img in generated if img is not None]  # Filter out None values

    def generate_preview(self, text: str) -> Image.Image:
        img = self.create_base_image()
        draw = ImageDraw.Draw(img)
        y = self.settings.get('margin', 20)
        
        styled_parts = self.style_parser.parse(text)['parts']
        for part in styled_parts:
            font = self.get_font(
                part['style'].get('face', 'Arial'),
                part['style'].get('size', self.settings.get('font_size', 24)),
                part['style'].get('bold', False),
                part['style'].get('italic', False)
            )
            
            if self.settings.get('text_shadow', False):
                self.draw_text_shadow(draw, part['text'], (20, y), font)
                
            if self.settings.get('text_border', True):
                self.draw_text_border(draw, part['text'], (20, y), font)
                
            draw.text((20, y), part['text'], font=font, 
                     fill=self.settings.get('text_color', '#FFFFFF'))
            y += font.getbbox(part['text'])[3] + 5
            
        return img

    def generate_simple_image(self, entry: Dict, idx: int) -> Optional[Dict]:
        try:
            img = self.create_base_image().convert('RGB')
            draw = ImageDraw.Draw(img)
            text = html.unescape(entry['text'])
            font_size = self.settings.get('font_size', 24)
            margin = self.settings.get('margin', 20)
            
            font = self.get_font('Arial', font_size, False, False)
            wrapped = self.wrap_text(text, font, 1280 - (2 * margin))
            
            total_height = sum(font.getbbox(line)[3] for line in wrapped)
            y = max(margin, (720 - total_height) // 2)
            
            for line in wrapped:
                bbox = font.getbbox(line)
                x = max(margin, (1280 - bbox[2]) // 2)
                
                if self.settings.get('text_border', True):
                    self.draw_text_border(draw, line, (x, y), font)
                    
                draw.text((x, y), line, font=font, 
                         fill=self.settings.get('text_color', '#FFFFFF'))
                y += bbox[3]
                
            path = os.path.join(self.temp_manager.image_dir, f"frame_{idx:08d}.png")
            self._save_image(img, path)
            
            if 'end_time' in entry and 'start_time' in entry:
                duration = entry['end_time'] - entry['start_time']
            else:
                duration = self.settings.get('default_duration', 5)  # Default duration if not provided
                
            return {
                'path': path,
                'duration': duration
            }
        except Exception as e:
            logging.error(f"Simple image failed: {str(e)}")
            return None

    def generate_styled_image(self, entry: Dict, idx: int) -> Optional[Dict]:
        try:
            img = self.create_base_image()
            draw = ImageDraw.Draw(img)
            styled = self.style_parser.parse(entry['text'])
            
            y = self.settings.get('margin', 20)
            for part in styled['parts']:
                font = self.get_font(
                    part['style'].get('face', 'Arial'),
                    part['style'].get('size', self.settings['font_size']),
                    part['style'].get('bold', False),
                    part['style'].get('italic', False)
                )
                
                x = self.settings.get('margin', 20)
                if part['style'].get('align') == 'center':
                    x = (1280 - font.getlength(part['text'])) // 2

                self.draw_text_line(draw, part['text'], (x, y), font)
                y += font.getbbox(part['text'])[3] + 5

            path = os.path.join(self.temp_manager.image_dir, f"frame_{idx:08d}.png")
            self._save_image(img, path)
            
            return {
                'path': path,
                'duration': entry['duration'] / self.settings.get('speed_factor', 1.0)
            }
        except Exception as e:
            logging.error(f"Styled image failed: {str(e)}")
            return None

    def _save_image(self, img: Image.Image, path: str):
        """Validated image saving"""
        if not path.startswith(self.temp_manager.image_dir):
            raise ValueError("Attempted to save outside temp directory")
        
        # Ensure 8-digit zero-padded index
        base_name = os.path.basename(path)
        if not base_name.startswith("frame_") or not base_name.endswith(".png"):
            raise ValueError("Invalid filename format")    
        
        img.save(path)
        logging.debug(f"Saved image: {path}")
        
        if not os.path.exists(path):
            raise IOError("Failed to write image file")

    def _validate_image(self, path: str) -> bool:
        """Verify image meets requirements"""
        try:
            with Image.open(path) as test_img:
                if test_img.mode != 'RGB' or test_img.size != (1280, 720):
                    logging.error(f"Invalid image dimensions/mode: {path}")
                    os.remove(path)
                    return False
            return True
        except Exception as e:
            logging.error(f"Image validation failed: {str(e)}")
            return False

    def apply_text_alignment(self, draw, text: str, font: ImageFont.FreeTypeFont, y_position: int):
        """Handle center alignment and other positioning"""
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        
        # Center alignment
        x_position = (1280 - text_width) // 2
        return x_position, y_position

    def create_base_image(self) -> Image.Image:
        """Create base image with proper settings validation"""
        try:
            if self.settings.get('background_image'):
                img = Image.open(self.settings['background_image'])
                img = img.convert('RGB').resize((1280, 720))
                #logging.info(f"Using background image: {self.settings['background_image']}")
                return img
        except Exception as e:
            logging.error(f"Background image error: {str(e)}")
        
        bg_color = self.settings.get('bg_color', '#000000')
        #logging.info(f"Using background color: {bg_color}")
        return Image.new('RGB', (1280, 720), bg_color)

    def get_font(self, face: str, size: int, bold: bool, italic: bool) -> ImageFont.FreeTypeFont:
        """Improved font loading with better error handling"""
        try:
            if self.settings.get('custom_font'):
                return ImageFont.truetype(
                    self.settings['custom_font'], 
                    size,
                    index=1 if italic else 0
                )
            
            # System font fallback
            font_path = self._find_system_font(face, bold, italic)
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            logging.error(f"Font error: {str(e)}")
            return ImageFont.load_default(size)

    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        lines = []
        for paragraph in text.split('\n'):
            words = paragraph.split(' ')
            current_line = []
            current_length = 0
            
            for word in words:
                word_length = font.getlength(word + ' ')
                if current_length + word_length > max_width:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = word_length
                else:
                    current_line.append(word)
                    current_length += word_length
            lines.append(' '.join(current_line))
        return lines

    def draw_text_border(self, draw, text: str, position: tuple, font: ImageFont.FreeTypeFont):
        x, y = position
        for dx in [-2, -1, 0, 1, 2]:
            for dy in [-2, -1, 0, 1, 2]:
                if dx == 0 and dy == 0:
                    continue
                draw.text((x+dx, y+dy), text, font=font, fill=(0, 0, 0))

    def draw_text_shadow(self, draw, text: str, position: tuple, font: ImageFont.FreeTypeFont):
        x, y = position
        for i in range(3):
            draw.text((x+2+i, y+2+i), text, font=font, fill=(0, 0, 0, 128))

    def _has_style_tags(self, text: str) -> bool:
        return any(tag in text for tag in ['<b>', '<i>', '<font'])

    def draw_text_line(self, draw, text: str, position: tuple, font: ImageFont.FreeTypeFont):
        x, y = position
        text_color = ImageColor.getrgb(self.settings.get('text_color', '#FFFFFF'))
        
        # Text Border
        if self.settings.get('text_border', True):
            border_color = (0, 0, 0)
            for dx in [-2, -1, 0, 1, 2]:
                for dy in [-2, -1, 0, 1, 2]:
                    if dx == 0 and dy == 0: continue
                    draw.text((x+dx, y+dy), text, font=font, fill=border_color)

        # Text Shadow
        if self.settings.get('text_shadow', False):
            shadow_color = (0, 0, 0, 128)
            for i in range(3):
                draw.text((x+2+i, y+2+i), text, font=font, fill=shadow_color)

        # Main Text
        draw.text((x, y), text, font=font, fill=text_color)   

    def _find_system_font(self, face: str, bold: bool, italic: bool) -> str:
        """Robust system font discovery"""
        font_map = {
            ('Arial', False, False): 'arial.ttf',
            ('Arial', True, False): 'arialbd.ttf',
            ('Arial', False, True): 'ariali.ttf',
            ('Arial', True, True): 'arialbi.ttf',
            ('Helvetica', False, False): 'helvetica.ttf',
            ('Times New Roman', False, False): 'times.ttf',
        }
        return font_map.get(
            (face, bold, italic), 
            'arial.ttf'  # Ultimate fallback
        )     