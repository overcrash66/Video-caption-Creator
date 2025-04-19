import os
import logging
from concurrent.futures import ThreadPoolExecutor

class VideoGenerator:
    def __init__(self, temp_manager, video_processor, image_generator):
        self.temp_manager = temp_manager
        self.video_processor = video_processor
        self.image_generator = image_generator

    def generate_video(self, output_path, srt_path, settings):
        try:
            # Parse subtitles
            entries = self.video_processor.srt_parser.parse(srt_path)
            images = self.image_generator.generate_images(entries)

            # Process video batches
            batch_size = settings.get('batch_size', 50)
            batches = [images[i:i + batch_size] for i in range(0, len(images), batch_size)]
            segments = []

            with ThreadPoolExecutor(max_workers=2) as executor:
                for batch in batches:
                    segment = self.video_processor.process_batch(batch)
                    if segment:
                        segments.append(segment)

            # Combine segments
            final_video = self.video_processor.combine_segments(segments, output_path)
            return final_video
        except Exception as e:
            logging.error(f"Video generation failed: {str(e)}")
            raise