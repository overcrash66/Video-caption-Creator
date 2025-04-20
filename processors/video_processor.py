from PIL import Image
import ffmpeg
import os
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, temp_manager, settings: dict):
        self.temp_manager = temp_manager
        self.settings = settings.copy()
        self.process_dir = self.temp_manager.process_dir
        self.verify_file = self.temp_manager.verify_file  # Add reference to verify_file method
        self.temp_dirs = []  # Keep track of created process directories
        self.temp_dir = self.process_dir  # Add temp_dir initialization
        self.image_dir = settings.get('image_dir', os.path.join(self.process_dir, 'images'))
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)

    def __del__(self):
        # Clean up all created temporary directories
        for temp_dir in self.temp_dirs:
            self.cleanup_temp_dir(temp_dir)

    def cleanup_temp_dir(self, temp_dir: str):
        try:
            if os.path.exists(temp_dir):
                self.temp_manager.cleanup_dir(temp_dir)
        except Exception as e:
            logging.error(f"Error cleaning up temporary directory {temp_dir}: {str(e)}")

    def calculate_adjusted_durations(self, frames: List[Dict], audio_duration: float) -> List[Dict]:
        """
        Adjust the duration of each frame to match the audio duration.
        Ensures minimum duration and rounds to 3 decimal places for millisecond precision.
        """
        try:
            total_frame_duration = sum(frame.get('duration', 0) for frame in frames)
            if total_frame_duration <= 0:
                logging.error("Total frame duration is zero or negative.")
                return frames

            scaling_factor = audio_duration / total_frame_duration
            adjusted_frames = []
            accumulated_duration = 0
            min_duration = 0.033  # Minimum duration (about 1 frame at 30fps)

            for i, frame in enumerate(frames):
                adjusted_frame = frame.copy()
                raw_duration = frame.get('duration', 0) * scaling_factor
                duration = max(round(raw_duration, 3), min_duration)

                if i == len(frames) - 1:
                    duration = round(audio_duration - accumulated_duration, 3)

                adjusted_frame['duration'] = duration
                accumulated_duration += duration
                adjusted_frames.append(adjusted_frame)

            return adjusted_frames
        except Exception as e:
            logging.error(f"Error calculating adjusted durations: {str(e)}")
            return frames

    def validate_image(self, image_path: str) -> bool:
        """Validate image dimensions and color mode."""
        try:
            image = Image.open(image_path)
            if image.size != (1280, 720):
                logging.error("Invalid image dimensions.")
                return False
            if image.mode != 'RGB':
                logging.error("Invalid color mode.")
                return False
            return True
        except Exception as e:
            logging.error(f"Error validating image {image_path}: {str(e)}")
            return False

    def validate_and_prepare_image(self, img_path: str, process_dir: str, batch_idx: int) -> str:
        """Validate an image or replace it with a blank image if invalid."""
        if not img_path or not os.path.exists(img_path) or not self.validate_image(img_path):
            logging.error(f"Invalid image: {img_path}. Replacing with a blank image.")
            img_path = os.path.join(process_dir, f"blank_{batch_idx:04d}.png")
            Image.new('RGB', (1280, 720), (255, 255, 255)).save(img_path)
        return img_path

    def process_images(self, images, output_path, audio_input: str = None):
        try:
            if audio_input:
                audio_duration = self.get_audio_duration(audio_input)
                if audio_duration > 0:
                    images = self.calculate_adjusted_durations(images, audio_duration)

            batch_size = max(len(images) // 10, 50)
            batches = [images[i:i + batch_size] for i in range(0, len(images), batch_size)]
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

            valid_segments = self._get_ordered_segments(segments)
            if not valid_segments:
                logging.error("No valid segments for final video")
                return False

            return self.combine_segments(valid_segments, output_path, audio_input)

        except Exception as e:
            logging.error(f"Video processing failed: {str(e)}")
            return False

    def process_batch(self, batch: List[Dict], batch_idx: int) -> Optional[str]:
        process_dir = None
        list_file = None
        try:
            if not batch:
                logging.warning(f"Skipping empty batch {batch_idx}")
                return None

            process_dir = self.temp_manager.create_process_dir()
            list_file = os.path.join(process_dir, f"input_{batch_idx}.txt")
            output_file = os.path.join(process_dir, f"batch_{batch_idx:04d}.mp4")

            with open(list_file, 'w', encoding='utf-8') as f:
                for img in batch:
                    img_path = self.validate_and_prepare_image(img.get('path'), process_dir, batch_idx)
                    duration = img.get('duration', 1.0)
                    f.write(f"file '{os.path.abspath(img_path)}'\n")
                    f.write(f"duration {duration:.3f}\n")

            if not os.path.exists(list_file) or os.path.getsize(list_file) == 0:
                logging.error(f"Empty list file for batch {batch_idx}")
                return None

            frame_rate = 30
            try:
                cmd = (
                    ffmpeg
                    .input(list_file, format='concat', safe=0)
                    .output(output_file,
                            vsync='cfr',
                            vcodec='libx264',
                            pix_fmt='yuv420p',
                            crf=18,
                            r=frame_rate,
                            preset='medium',
                            movflags='+faststart')
                )
                cmd.overwrite_output().run(capture_stdout=True, capture_stderr=True)
                logging.info(f"Successfully created video segment for batch {batch_idx}")
            except ffmpeg.Error as e:
                logging.error(f"FFmpeg error in batch {batch_idx}: {e.stderr.decode() if e.stderr else str(e)}")
                return None

            return output_file if self.is_valid_video(output_file) else None
        except Exception as e:
            logging.error(f"FFmpeg error in batch {batch_idx}: {str(e)}")
            return None
        finally:
            if list_file and os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except Exception as e:
                    logging.warning(f"Error cleaning up list file: {str(e)}")

    def _get_ordered_segments(self, segments: list) -> list:
        try:
            valid = [s for s in segments if s is not None]
            valid.sort(key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
            return valid
        except Exception as e:
            logging.error(f"Segment ordering failed: {str(e)}")
            return []
    
    def combine_segments(self, segments: List[str], output_path: str, audio_input: str = None) -> bool:
        """Combine video segments with background music handling and explicit stream mapping."""
        concat_list = None
        try:
            # Ensure segments are ordered correctly
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

            video_input = ffmpeg.input(concat_list, format='concat', safe=0, fflags='+genpts')
            
            # Temporary output path for the unsynced video
            unsynced_video_path = os.path.join(self.temp_manager.process_dir, "unsynced_video.mp4")

            # Handle background music
            if audio_input:
                if not self.is_valid_audio(audio_input):
                    logging.error("Audio input is not a valid audio file")
                    return False
                audio_stream = ffmpeg.input(audio_input)
                video_stream = video_input['v']
                audio_stream = audio_stream['a']
                (
                    ffmpeg
                    .concat(
                        video_stream,
                        audio_stream,
                        v=1,
                        a=1
                    )
                    .output(
                        unsynced_video_path,
                        vcodec='libx264',
                        acodec='aac',
                        audio_bitrate='192k',
                        strict='experimental',
                        movflags='+faststart',
                        r=30  # Force frame rate to 30 FPS for sync stability
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )
            else:
                # If no background music, check if segments have audio
                has_audio = any(self.has_audio_stream(seg) for seg in valid_segments)
                if has_audio:
                    # Re-encode video and audio to ensure sync
                    (
                        ffmpeg
                        .output(video_input, unsynced_video_path, vcodec='libx264', acodec='aac', r=30, audio_bitrate='192k')
                        .overwrite_output()
                        .run()
                    )
                else:
                    # No audio in segments and no background music
                    (
                        ffmpeg
                        .output(video_input, unsynced_video_path, vcodec='libx264', an=None, r=30)
                        .overwrite_output()
                        .run()
                    )

            # Sync the video with the audio (if audio is provided)
            if audio_input:
                if not self.sync_audio_with_video(unsynced_video_path, audio_input, output_path):
                    logging.error("Failed to sync video with audio")
                    return False
            else:
                os.replace(unsynced_video_path, output_path)  # No audio, just rename the video

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
    
    def is_valid_audio(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return False
        try:
            probe = ffmpeg.probe(file_path)
            return any(stream['codec_type'] == 'audio' for stream in probe['streams'])
        except Exception as e:
            logger.error(f"Invalid audio file: {str(e)}")
            return False

    def is_valid_video(self, file_path: str) -> bool:
        """Check if file is a valid video."""
        try:
            probe = ffmpeg.probe(file_path)
            return any(stream['codec_type'] == 'video' for stream in probe['streams'])
        except Exception as e:
            logger.error(f"Invalid video file: {str(e)}")
            return False

    def has_audio_stream(self, file_path: str) -> bool:
        """Check if video file contains an audio stream."""
        try:
            probe = ffmpeg.probe(file_path)
            return any(stream['codec_type'] == 'audio' for stream in probe.get('streams', []))
        except Exception as e:
            logging.error(f"Error checking audio for {file_path}: {str(e)}")
            return False
        
    def sync_audio_with_video(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """
        Synchronize the audio with the video using ffmpeg.
        If the video and audio are out of sync, adjust the audio speed to match the video.
        """
        try:
            # Probe the video and audio to get their durations
            video_info = ffmpeg.probe(video_path)
            audio_info = ffmpeg.probe(audio_path)

            video_duration = float(video_info['format']['duration'])
            audio_duration = float(audio_info['format']['duration'])

            # If the video and audio durations are the same, no need to sync
            if abs(video_duration - audio_duration) < 0.1:  # Allow a small tolerance
                logging.info("Video and audio are already in sync.")
                os.replace(video_path, output_path)  # Just rename the video
                return True
            else:
                speed_factor = video_duration / audio_duration
                logging.info(f"Video is shorter than audio. Adjusting audio speed by factor {speed_factor:.2f}.")
                video_stream = ffmpeg.input(video_path)['v']
                audio_stream = (
                    ffmpeg.input(audio_path)['a']
                    .filter('atempo', speed_factor)
                )
                (
                    ffmpeg.concat(video_stream, audio_stream, v=1, a=1)
                    .output(output_path, acodec='aac', audio_bitrate='192k')
                    .overwrite_output()
                    .run(quiet=True)
                ) 

                return True
        except ffmpeg.Error as e:
            logging.error(f"Failed to sync audio with video: {e.stderr.decode().strip()}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during sync: {str(e)}")
            return False
        
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get the duration of the audio file in seconds.
        """
        try:
            probe = ffmpeg.probe(audio_path)
            return float(probe['format']['duration'])
        except Exception as e:
            logging.error(f"Error getting audio duration: {str(e)}")
            return 0.0

    def process(self, images: List[Dict], output_path: str, audio_input: str = None) -> bool:
        """
        Process the images into a video.
        
        Args:
            images: List of dictionaries containing image paths and durations
            output_path: Path where the final video should be saved
            audio_input: Optional path to an audio file to be added to the video
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        return self.process_images(images, output_path, audio_input)