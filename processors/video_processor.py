from PIL import Image
import ffmpeg
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

class VideoProcessor:
    def __init__(self, temp_manager, settings: dict):
        self.temp_manager = temp_manager
        self.settings = settings.copy()

    def process(self, images: List[Dict], output_path: str) -> bool:
        """Process images with strict order preservation"""
        try:
            batch_size = max(len(images) // 10, 50)
            batches = [images[i:i+batch_size] for i in range(0, len(images), batch_size)]
            
            # Pre-allocate segment list with original positions
            segments = [None] * len(batches)
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_map = {
                    executor.submit(self.process_batch, batch, idx): idx
                    for idx, batch in enumerate(batches)
                }
                
                for future in as_completed(future_map):
                    batch_idx = future_map[future]
                    result = future.result()
                    if result:
                        segments[batch_idx] = result
                        logging.info(f"Processed batch {batch_idx}")
                    else:
                        logging.error(f"Failed batch {batch_idx}")

            # Filter and sort segments
            valid_segments = self._get_ordered_segments(segments)
            
            if not valid_segments:
                logging.error("No valid segments for final video")
                return False

            return self.combine_segments(valid_segments, output_path)
        except Exception as e:
            logging.error(f"Video processing failed: {str(e)}")
            return False

    def _get_ordered_segments(self, segments: list) -> list:
        """Ensure proper segment ordering"""
        try:
            # Remove failed batches
            valid = [s for s in segments if s is not None]
        
            # Sort by batch index from filename
            valid.sort(key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
            return valid
        except Exception as e:
            logging.error(f"Segment ordering failed: {str(e)}")
            return []

    def process_batch(self, batch: List[Dict], batch_idx: int) -> Optional[str]:
        process_dir = None
        list_file = None
        try:
            # Add validation for image properties
            first_image = Image.open(batch[0]['path'])
            if first_image.size != (1280, 720):
                logging.error("Invalid image dimensions in batch")
                return None
            if first_image.mode != 'RGB':
                logging.error("Invalid color mode in images")
                return None
            if not batch:
                logging.warning(f"Skipping empty batch {batch_idx}")
                return None  

            process_dir = self.temp_manager.create_process_dir()
            list_file = os.path.join(process_dir, f"input_{batch_idx}.txt")

            output_file = os.path.join(process_dir, f"batch_{batch_idx:04d}.mp4")

            with open(list_file, 'w', encoding='utf-8') as f:
                for img in batch:
                    logging.info(f"Processing batch {batch_idx} with {len(batch)} images")
                    img_path = img.get('path')
                    duration = img.get('duration', 1.0)
                    
                    if not img_path or not os.path.exists(img_path):
                        logging.error(f"Invalid image in batch {batch_idx}: {img_path}")
                        continue
                    else:
                        logging.debug(f"Valid image: {img['path']}")  

                    f.write(f"file '{os.path.abspath(img_path)}'\n")
                    f.write(f"duration {duration:.3f}\n")

            if not os.path.exists(list_file) or os.path.getsize(list_file) == 0:
                logging.error(f"Empty list file for batch {batch_idx}")
                return None

            (
                ffmpeg
                .input(list_file, format='concat', safe=0)
                .output(output_file,
                       vsync='vfr',
                       vcodec='libx264',
                       pix_fmt='yuv420p',
                       crf=18,
                       r=30,
                       preset='veryslow',
                       movflags='+faststart')
                .overwrite_output()
                .run(quiet=True)
            )

            if not self.is_valid_video(output_file):
                logging.error(f"Batch {batch_idx} output failed validation")
                return None

            return output_file
        except ffmpeg.Error as e:
            logging.error(f"FFmpeg error in batch {batch_idx}: {e.stderr.decode()}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in batch {batch_idx}: {str(e)}")
            return None
        finally:
            if list_file and os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except Exception as e:
                    logging.warning(f"Error cleaning up list file: {str(e)}")


    def combine_segments(self, segments: List[str], output_path: str, audio_input: str) -> bool:
        concat_list = None
        try:
            segments = self._get_ordered_segments(segments)
            
            # Validate segments
            valid_segments = [s for s in segments if os.path.exists(s) and self.is_valid_video(s)]
            if not valid_segments:
                logging.error("No valid video segments found for combining")
                return False

            # Create concat list
            concat_list = os.path.join(self.temp_manager.process_dir, "final_list.txt")
            with open(concat_list, 'w', encoding='utf-8') as f:
                for seg in valid_segments:
                    f.write(f"file '{os.path.abspath(seg)}'\n")

            video_input = ffmpeg.input(concat_list, format='concat', safe=0)
            
            # Handle background music
            if audio_input:
                audio_input = ffmpeg.input(audio_input)
                (
                    ffmpeg
                    .output(
                        video_input,
                        audio_input,
                        output_path,
                        vcodec='libx264',
                        pix_fmt='yuv420p',
                        acodec='aac',
                        audio_bitrate='192k',
                        strict='experimental',
                        movflags='+faststart'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            else:
                # If no background music, check if segments have audio
                has_audio = any(self.has_audio_stream(seg) for seg in valid_segments)
                if has_audio:
                    # Copy both video and audio from segments
                    (
                        ffmpeg
                        .output(video_input, output_path, vcodec='copy', acodec='copy')
                        .overwrite_output()
                        .run()
                    )
                else:
                    # No audio in segments and no background music
                    (
                        ffmpeg
                        .output(video_input, output_path, vcodec='copy', an=None)
                        .overwrite_output()
                        .run()
                    )
            
            return True
        except ffmpeg.Error as e:
            logging.error(f"FFmpeg concatenation error: {e.stderr.decode().strip()}")
            return False
        finally:
            if concat_list and os.path.exists(concat_list):
                try:
                    os.remove(concat_list)
                except Exception as e:
                    logging.warning(f"Error cleaning up concat list: {str(e)}")

    def is_valid_video(self, file_path: str) -> bool:
        """Check if file contains a valid video stream."""
        try:
            probe = ffmpeg.probe(file_path)
            return any(stream['codec_type'] == 'video' for stream in probe.get('streams', []))
        except Exception as e:
            logging.error(f"Invalid video {file_path}: {str(e)}")
            return False

    def is_valid_audio(self, file_path: str) -> bool:
        try:
            probe = ffmpeg.probe(path)
            return any(stream['codec_type'] == 'audio' for stream in probe['streams'])
        except ffmpeg.Error as e:
            logger.error(f"Invalid audio file: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False

    def has_audio_stream(self, file_path: str) -> bool:
        """Check if video file contains an audio stream."""
        try:
            probe = ffmpeg.probe(file_path)
            return any(stream['codec_type'] == 'audio' for stream in probe.get('streams', []))
        except Exception as e:
            logging.error(f"Error checking audio for {file_path}: {str(e)}")
            return False