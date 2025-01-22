import ffmpeg
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

class VideoProcessor:
    def __init__(self, temp_manager, settings: dict):
        self.temp_manager = temp_manager
        self.settings = settings.copy()

    def combine_segments(self, segments: List[str], output_path: str, audio_input: str) -> bool:
        """Combine video segments with background music handling and explicit stream mapping."""
        concat_list = None
        try:
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
                print('audio_input = True')
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
                    print("has audio True")
                    # Copy both video and audio from segments
                    (
                        ffmpeg
                        .output(video_input, output_path, vcodec='copy', acodec='copy')
                        .overwrite_output()
                        .run()
                    )
                else:
                    print("No audio")
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

    def process_batch(self, batch: List[Dict], batch_idx: int) -> Optional[str]:
        """Process a batch of images into a video segment."""
        process_dir = None
        list_file = None
        try:
            if not batch:
                logging.warning(f"Skipping empty batch {batch_idx}")
                return None

            process_dir = self.temp_manager.create_process_dir()
            list_file = os.path.join(process_dir, f"input_{batch_idx}.txt")
            output_file = os.path.join(process_dir, f"batch_{batch_idx}.mp4")

            with open(list_file, 'w', encoding='utf-8') as f:
                for img in batch:
                    img_path = img.get('path')
                    duration = img.get('duration', 1.0)
                    if not img_path or not os.path.exists(img_path):
                        logging.error(f"Invalid image in batch {batch_idx}: {img_path}")
                        continue
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
                       r=30,
                       crf=23,
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

    def process(self, images: List[Dict], output_path: str) -> bool:
        """Process all image batches into a final video."""
        try:
            batch_size = max(len(images) // 10, 50)  # Ensure minimum batch size of 50
            batches = [images[i:i+batch_size] for i in range(0, len(images), batch_size)]
            
            segments = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for idx, batch in enumerate(batches):
                    future = executor.submit(self.process_batch, batch, idx)
                    futures.append(future)
                
                for future in futures:
                    result = future.result()
                    if result:
                        segments.append(result)
                        logging.info(f"Successfully processed batch segment: {result}")
                    else:
                        logging.error("A batch failed to process")

            if not segments:
                logging.error("No valid segments generated from batches")
                return False

            logging.info(f"Combining {len(segments)} segments into final video")
            return self.combine_segments(segments, output_path)
        except Exception as e:
            logging.error(f"Video processing failed: {str(e)}", exc_info=True)
            return False