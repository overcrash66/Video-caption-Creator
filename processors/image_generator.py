from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageOps
import html
import logging
import os
from typing import List, Dict, Optional, Tuple
from utils.style_parser import StyleParser
from processors.sub2audio import SubToAudio
from pydub import AudioSegment

class ImageGenerator:
    """Handles the generation of caption images with various styles and effects."""
    
    def __init__(self, temp_manager: any, style_parser: StyleParser, settings: dict) -> None:
        if not temp_manager or not style_parser or not settings:
            raise ValueError("Required parameters cannot be None")
        if not hasattr(temp_manager, 'image_dir'):
            raise AttributeError("temp_manager must have image_dir attribute")

        self.temp_manager = temp_manager
        self.style_parser = style_parser
        self.settings = settings.copy()

        if 'frame_delay' not in self.settings:
            self.settings['frame_delay'] = 1.0
        # font_cache keyed by (face, size, bold, italic)
        self.font_cache = {}
        
        # Ensure required settings have defaults
        if 'font_size' not in self.settings:
            self.settings['font_size'] = 24
        if 'margin' not in self.settings:
            self.settings['margin'] = 20

    def _adjust_duration(self, base_duration: float) -> float:
        """Apply frame delay and other timing adjustments"""
        adjusted = base_duration + self.settings.get('frame_delay', 0.7)
        return adjusted / self.settings.get('speed_factor', 2.0)

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

    def generate_image(self, text: str) -> Image.Image:
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
            bbox = font.getbbox(part['text'])
            y += (bbox[3] - bbox[1] if bbox else font.size) + 5
            
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
            
            total_height = sum((font.getbbox(line)[3] - font.getbbox(line)[1]) for line in wrapped)
            y = max(margin, (720 - total_height) // 2)
            
            for line in wrapped:
                bbox = font.getbbox(line)
                text_width = bbox[2] - bbox[0]
                x = max(margin, (1280 - text_width) // 2)
                
                if self.settings.get('text_border', True):
                    self.draw_text_border(draw, line, (x, y), font)
                    
                draw.text((x, y), line, font=font, 
                        fill=self.settings.get('text_color', '#FFFFFF'))
                y += (bbox[3] - bbox[1])
                
            path = os.path.join(self.temp_manager.image_dir, f"frame_{idx:08d}.png")
            self._save_image(img, path)
            
            # Use the duration from the subtitle entry with millisecond precision
            duration = float(entry['end_time'] - entry['start_time'])
            adjusted_duration = self._adjust_duration(duration)
            return {
                'path': path,
                'duration': round(adjusted_duration, 3)  # Round to 3 decimal places for milliseconds
            }
        except Exception as e:
            logging.error(f"Simple image failed: {str(e)}")
            return None

    def generate_styled_image(self, entry: Dict, idx: int) -> Optional[Dict]:
        if not entry or 'text' not in entry:
            logging.error("Invalid entry data")
            return None
            
        try:
            logging.debug(f"Generating styled image for entry {idx}")
            img = self.create_base_image()
            styled = self.style_parser.parse(entry['text'])
            
            # Calculate total height of all text parts
            total_height = 0
            for part in styled['parts']:
                font = self.get_font(
                    part['style'].get('face', 'Arial'),
                    part['style'].get('size', self.settings['font_size']),
                    part['style'].get('bold', False),
                    part['style'].get('italic', False)
                )
                bbox = font.getbbox(part['text'])
                if bbox:
                    total_height += (bbox[3] - bbox[1]) + 5  # Height + spacing

            # Calculate starting Y position to center all text vertically
            y = (720 - total_height) // 2
            draw = ImageDraw.Draw(img)
            
            # Iterate through text parts and draw them
            for part in styled['parts']:
                font = self.get_font(
                    part['style'].get('face', 'Arial'),
                    part['style'].get('size', self.settings['font_size']),
                    part['style'].get('bold', False),
                    part['style'].get('italic', False)
                )
                
                # Calculate x-position to center text horizontally using getbbox
                bbox = font.getbbox(part['text'])
                text_width = bbox[2] - bbox[0]
                x = (1280 - text_width) // 2

                # Draw text (with optional border and shadow)
                self.draw_text_line(draw, part['text'], (x, y), font)
                
                # Update y-position for the next text part
                y += (bbox[3] - bbox[1]) + 5

            # Save the image
            path = os.path.join(self.temp_manager.image_dir, f"frame_{idx:08d}.png")
            self._save_image(img, path)
            
            # Calculate and adjust duration if necessary
            duration = float(entry['end_time'] - entry['start_time'])
            adjusted_duration = duration / self.settings.get('speed_factor', 1.0)
            
            return {
                'path': path,
                'duration': round(adjusted_duration, 3)
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
        """Improved font loading with caching and better error handling"""
        key = (face, size, bold, italic)
        if key in self.font_cache:
            return self.font_cache[key]
        
        try:
            # When a custom font is set and no style variations are needed, use it
            if self.settings.get('custom_font') and not (bold or italic):
                font = ImageFont.truetype(self.settings['custom_font'], size)
            else:
                # System font fallback (will try to find bold/italic versions)
                font_path = self._find_system_font(face, bold, italic)
                font = ImageFont.truetype(font_path, size)
        except Exception as e:
            logging.error(f"Font error: {str(e)}")
            font = ImageFont.load_default()  # load_default does not take a size argument
        
        self.font_cache[key] = font
        return font

    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        lines = []
        for paragraph in text.split('\n'):
            words = paragraph.split(' ')
            current_line = []
            current_length = 0
            
            for word in words:
                # Measure the word length including a space
                word_bbox = font.getbbox(word + ' ')
                word_length = word_bbox[2] - word_bbox[0]
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
        # First draw the border in black
        for dx in [-2, -1, 0, 1, 2]:
            for dy in [-2, -1, 0, 1, 2]:
                if dx == 0 and dy == 0:
                    continue
                draw.text((x+dx, y+dy), text, font=font, fill=(0, 0, 0))
        
        # Then draw the main text in white
        draw.text((x, y), text, font=font, fill=(255, 255, 255))

    def draw_text_shadow(self, draw, text: str, position: tuple, font: ImageFont.FreeTypeFont):
        x, y = position
        for i in range(3):
            draw.text((x+2+i, y+2+i), text, font=font, fill=(0, 0, 0, 128))

    def _has_style_tags(self, text: str) -> bool:
        style_tags = ['<b>', '</b>', '<i>', '</i>', '<font']
        return any(tag in text.lower() for tag in style_tags)

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
        """Robust system font discovery with system path checking"""
        import sys
        
        if sys.platform == 'win32':
            font_dir = 'C:\\Windows\\Fonts\\'
        elif sys.platform == 'darwin':
            font_dir = '/System/Library/Fonts/'
        else:
            font_dir = '/usr/share/fonts/'
            
        font_map = {
            ('Arial', False, False): 'arial.ttf',
            ('Arial', True, False): 'arialbd.ttf',
            ('Arial', False, True): 'ariali.ttf',
            ('Arial', True, True): 'arialbi.ttf',
            ('Helvetica', False, False): 'helvetica.ttf',
            ('Times New Roman', False, False): 'times.ttf',
        }
        
        font_file = font_map.get((face, bold, italic), 'arial.ttf')
        font_path = os.path.join(font_dir, font_file)
        
        if os.path.exists(font_path):
            return font_path
            
        # Fallback to default system font from Pillow's load_default (which returns a font object, not a path)
        # Here we return a common fallback; you might adjust this for your system.
        return os.path.join(font_dir, 'arial.ttf')
