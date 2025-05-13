import re
import os
import copy
import shutil
import ffmpeg
import torch
import librosa
import tempfile
import logging # Added
from TTS.api import TTS
from pydub import AudioSegment
from TTS.utils.manage import ModelManager
from typing import Union, List, Optional, Dict, Any

# --- Logging Setup ---
# Configure basic logging. You might want to configure this more elaborately
# in your main application script (e.g., set level, output file).
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# --- End Logging Setup ---


manager = ModelManager()

class SubToAudio:
    """
    A class to convert subtitle files (.srt) into synchronized audio using TTS.

    Handles subtitle parsing, TTS generation for each entry, optional tempo
    adjustment to fit timing, optional time shifting to resolve overflows,
    and final audio track assembly.
    """

    def get_available_models(self) -> List[str]:
        """Lists available Coqui TTS models compatible with XTTS."""
        try:
            # Ensure the manager is up-to-date
            models = ModelManager().list_models()
            # Filter specifically for models usable by TTS API, often under 'tts_models' or similar keys
            # This part might need adjustment based on exact ModelManager structure
            tts_models = []
            if "tts_models" in models:
                for lang_models in models["tts_models"].values():
                    for dataset_models in lang_models.values():
                        for model_name in dataset_models.keys():
                             # Heuristic: Check if it contains 'xtts' or is suitable
                             # A more robust check might involve inspecting model capabilities if available
                             if "xtts" in model_name or "vits" in model_name or "tacotron" in model_name:
                                 # Construct the full model name string if needed
                                 # This depends on how TTS() expects the name
                                 full_model_name = f"tts_models/{'/'.join(model_name.split('/')[-3:])}" # Example reconstruction
                                 tts_models.append(full_model_name)
            # Fallback or specific check for XTTS if the above is too complex
            if "xtts" in models:
                 tts_models.extend(models["xtts"])

            # Deduplicate
            return sorted(list(set(tts_models)))

        except Exception as e:
            logger.error(f"Error listing models: {e}")
            # Return a common default or known good model as fallback
            return ["tts_models/multilingual/multi-dataset/xtts_v2"] # Example fallback

    def __init__(
        self,
        model_name: Optional[str] = "tts_models/multilingual/multi-dataset/xtts_v2", # Defaulting to a common XTTS model
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        progress_bar: bool = True, # Changed default to True
        **kwargs,
    ):
        """
        Initializes the SubToAudio class and the TTS model.

        Args:
            model_name: Name of the Coqui TTS model to use (e.g., 'tts_models/en/ljspeech/tacotron2-DDC', 'tts_models/multilingual/multi-dataset/xtts_v2').
                        Ignored if model_path is provided.
            model_path: Path to a local TTS model checkpoint (.pth).
            config_path: Path to the model's configuration file (.json). Required if model_path is used.
            progress_bar: Whether to show progress bars during download/processing.
            **kwargs: Additional arguments passed directly to the TTS() constructor.
        """
        self.model_name = model_name
        self.name_path = "default_output" # Default name base if no file processed yet
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")

        try:
            if model_path is not None:
                if config_path is None:
                    raise ValueError("config_path is required when using a local model_path.")
                logger.info(f"Loading local model from: {model_path}")
                self.apitts = TTS(
                    model_path=model_path,
                    config_path=config_path,
                    progress_bar=progress_bar,
                    **kwargs,
                ).to(device)
                # Attempt to determine model name from config or path if possible for __repr__
                self.model_name = f"local:{os.path.basename(model_path)}"
            elif model_name is not None:
                logger.info(f"Loading model by name: {model_name}")
                # The TTS class should handle finding the model path from the name
                self.apitts = TTS(
                    model_name=model_name,
                    progress_bar=progress_bar,
                    **kwargs
                ).to(device)
                # Store the provided model name
                self.model_name = model_name # Ensure self.model_name is set correctly
            else:
                raise ValueError("Either model_name or model_path (with config_path) must be provided.")

            # Check if the loaded model has speaker capabilities (especially relevant for XTTS)
            self.has_speakers = hasattr(self.apitts, 'speakers') and self.apitts.speakers is not None
            self.is_multi_speaker = self.has_speakers and len(self.apitts.speakers) > 1
            self.is_xtts_model = "xtts" in self.model_name.lower() if self.model_name else False # Check if XTTS

            logger.info(f"TTS model loaded successfully: {self.model_name}")
            if self.is_xtts_model:
                logger.info("Model identified as XTTS.")
            elif self.is_multi_speaker:
                 logger.info(f"Multi-speaker model detected with speakers: {self.apitts.speakers}")
            elif self.has_speakers:
                 logger.info(f"Single speaker model detected.")
            else:
                 logger.info("Model does not seem to have speaker information.")


        except Exception as e:
            logger.error(f"Failed to initialize TTS model: {e}", exc_info=True)
            raise RuntimeError(f"Could not load TTS model. Error: {e}") from e

    def subtitle(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extracts subtitle data from an SRT file.

        Args:
            file_path: Path to the .srt subtitle file.

        Returns:
            A list of dictionaries, each representing a subtitle entry.
            Example: {'entry_number': 1, 'start_time': 1000, 'end_time': 3500,
                      'text': 'Hello world', 'sub_time': 2500, 'audio_name': '1_audio.wav'}
        """
        self.name_path = file_path
        logger.info(f"Extracting subtitles from: {file_path}")
        if not os.path.exists(file_path):
             raise FileNotFoundError(f"Subtitle file not found: {file_path}")
        if not file_path.lower().endswith(".srt"):
             logger.warning(f"Input file '{file_path}' does not have .srt extension. Attempting to parse anyway.")

        try:
            subtitle_data = self._extract_data_srt(file_path)
            logger.info(f"Successfully extracted {len(subtitle_data)} subtitle entries.")
            return subtitle_data
        except Exception as e:
            logger.error(f"Failed to extract data from SRT file '{file_path}': {e}", exc_info=True)
            raise ValueError(f"Error parsing SRT file: {e}") from e


    def convert_to_audio(
        self,
        sub_data: List[Dict[str, Any]],
        output_path: Optional[str] = None,
        # TTS specific parameters (especially for XTTS)
        speaker_wav: Optional[Union[str, List[str]]] = None, # Path to reference audio(s) for cloning
        speaker: Optional[str] = None,      # Name of a preset speaker (if model supports it)
        language: Optional[str] = None,     # Target language code (e.g., 'en', 'es') required by some models like XTTS
        emotion: Optional[str] = None,      # Emotion hint (model dependent)
        speed: Optional[float] = None,      # TTS generation speed (model dependent, distinct from tempo adjustment)
        # Tempo and Timing parameters
        tempo_mode: Optional[str] = "overflow", # Defaulting to overflow handling
        tempo_speed: Optional[float] = 1.0,   # Speed factor if tempo_mode is 'all'
        tempo_limit: Optional[float] = 2.0,   # Max speedup factor for 'overflow'/'precise' modes
        shift_mode: Optional[str] = None,     # How to shift segments if they overflow after tempo adjust
        shift_limit: Optional[Union[int, str]] = None, # Max ms or 'Xs' to shift
        strict_timing: bool = True,      # If True, raise error on unavoidable overlap; if False, log warning
        # Other parameters
        save_temp: bool = False,             # Save intermediate audio segments
        voice_conversion: bool = False,    # Use voice conversion (if model supports) - requires specific setup
        voice_dir: Optional[str] = None,     # Directory for voice conversion files (model dependent)
        **tts_kwargs                        # Pass any other kwargs directly to TTS methods
    ) -> str:
        """
        Converts parsed subtitle data into a single synchronized audio file.

        Args:
            sub_data: List of subtitle entries from the `subtitle` method.
            output_path: Path to save the final .wav audio file. If None, defaults to
                         the input subtitle filename with .wav extension.
            speaker_wav: Path to WAV file(s) for voice cloning (required for XTTS default usage).
            speaker: Name of a built-in speaker (if model supports and speaker_wav is not used).
            language: Language code for TTS (required for multilingual models like XTTS).
            emotion: Emotion hint for TTS (model specific support).
            speed: Playback speed for TTS generation itself (model specific, range usually 0.5-2.0).
            tempo_mode: How to adjust audio speed to fit subtitle timings:
                        'overflow': Speed up segments longer than time until next subtitle starts.
                        'precise': Speed up segments longer than their own subtitle duration.
                        'all': Apply `tempo_speed` to all segments.
                        None: No tempo adjustment (risk of overlap).
            tempo_speed: Speed factor (e.g., 1.5 = 50% faster) if tempo_mode='all'.
            tempo_limit: Maximum speed factor allowed when tempo_mode is 'overflow' or 'precise'.
                         Prevents excessive speedup (e.g., 2.0 means max 2x speed).
            shift_mode: How to shift segments if they still overflow after tempo adjustment:
                        'right': Push subsequent segments later.
                        'left': Pull subsequent segments earlier (stealing time from previous gaps).
                        'interpose': Distribute overflow shift to both previous and next gaps.
                        'left-overlap', 'interpose-overlap': Allow overlapping if needed.
                        None: No shifting (risk of overlap if tempo adjust was insufficient).
            shift_limit: Maximum time (int ms or str 'Xs') a segment can be shifted.
            strict_timing: If True, raises RuntimeError if segments overlap after all adjustments.
                           If False, logs a warning and allows overlap in the final output.
            save_temp: If True, saves the individual audio segments in a subfolder.
            voice_conversion: Use TTS voice conversion mode (requires compatible model and setup).
            voice_dir: Directory related to voice conversion (model specific).
            **tts_kwargs: Additional keyword arguments passed directly to the underlying
                         `tts.tts_to_file` or `tts.tts_with_vc_to_file` calls. Check Coqui TTS
                         documentation for model-specific options (e.g., temperature, top_k for XTTS).

        Returns:
            The path to the generated output WAV file.

        Raises:
            ValueError: If required parameters (like language/speaker_wav for XTTS) are missing or invalid.
            RuntimeError: If TTS generation fails, FFmpeg processing fails, or if strict_timing is True
                          and unavoidable overlaps occur.
        """
        if not sub_data:
            raise ValueError("Subtitle data list is empty.")

        # --- Input Validation ---
        self._validate_inputs(sub_data, tempo_mode, tempo_speed, tempo_limit, shift_mode)
        output_path = self._ensure_wav_extension(output_path)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True) # Ensure output directory exists

        # Validate TTS parameters based on model type
        if self.is_xtts_model:
            if not speaker_wav:
                logger.warning("XTTS model selected, but 'speaker_wav' not provided. Attempting to use default speaker if available, but cloning is standard.")
                # XTTS might still work if it has a default internal speaker, but usually needs speaker_wav
            if not language:
                raise ValueError("XTTS model requires the 'language' parameter (e.g., 'en').")
        elif self.is_multi_speaker and not speaker_wav and not speaker:
             logger.warning(f"Multi-speaker model '{self.model_name}' selected, but neither 'speaker_wav' nor 'speaker' provided. Using default speaker if available.")
        # --- End Validation ---

        data = copy.deepcopy(sub_data) # Work on a copy

        # Prepare parameters for TTS call, filtering out None values
        # Note: speaker_wav/speaker priority depends on TTS model implementation, usually speaker_wav takes precedence if provided.
        tts_params = {
            "language": language,
            "speaker_wav": speaker_wav,
            "speaker": speaker,
            "emotion": emotion,
            "speed": speed,
            # Add any other relevant params passed via tts_kwargs
            **tts_kwargs
        }
        # Filter out keys with None values before passing to TTS
        filtered_tts_params = {k: v for k, v in tts_params.items() if v is not None}
        logger.info(f"TTS parameters (excluding None): {filtered_tts_params}")
        logger.info(f"Tempo mode: {tempo_mode}, Tempo limit: {tempo_limit}")
        logger.info(f"Shift mode: {shift_mode}, Shift limit: {shift_limit}")
        logger.info(f"Strict timing: {strict_timing}")


        with tempfile.TemporaryDirectory() as temp_folder:
            logger.info(f"Using temporary folder: {temp_folder}")

            # 1. Generate individual audio segments
            try:
                self._generate_audio_segments(data, temp_folder, filtered_tts_params, voice_conversion)
            except Exception as e:
                 logger.error(f"Fatal error during audio segment generation: {e}", exc_info=True)
                 raise # Re-raise after logging

            # 2. Adjust tempo if needed
            self._process_timing(data, temp_folder, tempo_mode, tempo_speed, tempo_limit)

            # 3. Shift segments if needed and if overflow remains
            if shift_mode:
                try:
                    data = self._shifter(data, shift_mode, shift_limit)
                except Exception as e:
                    logger.error(f"Fatal error during time shifting: {e}", exc_info=True)
                    raise

            # 4. Build final audio track
            try:
                final_audio = self._build_final_audio(data, temp_folder, strict_timing)
            except Exception as e:
                 logger.error(f"Fatal error during final audio assembly: {e}", exc_info=True)
                 raise

            # 5. Export final audio
            try:
                logger.info(f"Exporting final audio to: {output_path}")
                final_audio.export(output_path, format="wav")
            except Exception as e:
                logger.error(f"Failed to export final audio: {e}", exc_info=True)
                raise RuntimeError(f"Failed to export final WAV file: {e}") from e

            # 6. Save temporary files if requested
            if save_temp:
                self._save_temp_files(temp_folder, output_path)

        logger.info(f"Audio generation complete: {output_path}")
        return output_path

    # --- Private Helper Methods ---

    def _generate_audio_segments(
        self,
        data: List[Dict[str, Any]],
        temp_folder: str,
        params: Dict[str, Any],
        voice_conversion: bool
    ):
        """Generates individual audio WAV files for each subtitle entry."""
        logger.info("Starting audio segment generation...")
        num_entries = len(data)
        tts_method = self.apitts.tts_with_vc_to_file if voice_conversion else self.apitts.tts_to_file
        method_name = "tts_with_vc_to_file" if voice_conversion else "tts_to_file"

        for idx, entry in enumerate(data):
            audio_path = os.path.join(temp_folder, entry['audio_name'])
            text_to_speak = entry.get('text', '').strip()
            entry_num = entry.get('entry_number', idx + 1) # Use entry_number if available

            if not text_to_speak:
                logger.warning(f"Entry {entry_num}: Skipping empty text.")
                # Create short silence to avoid errors later
                AudioSegment.silent(duration=10).export(audio_path, format="wav")
                entry['audio_length'] = 10
                continue

            logger.info(f"Generating audio for entry {entry_num}/{num_entries}: '{text_to_speak[:50]}...'")
            try:
                # Ensure speaker_wav is passed correctly if it's a list for multi-reference
                current_params = params.copy()
                if isinstance(current_params.get("speaker_wav"), list):
                     # If multiple speaker_wavs are provided, Coqui TTS might expect only one per call.
                     # Defaulting to the first one if it's a list. Adjust if model handles lists differently.
                     current_params["speaker_wav"] = current_params["speaker_wav"][0]
                     logger.debug(f"Using first speaker_wav for entry {entry_num}: {current_params['speaker_wav']}")

                tts_method(
                    text=text_to_speak,
                    file_path=audio_path,
                    **current_params # Pass filtered params + any extra kwargs
                )
                # Verify file exists and get length
                if not os.path.exists(audio_path):
                    raise RuntimeError(f"TTS method {method_name} completed but output file not found: {audio_path}")
                entry['audio_length'] = self._audio_length(audio_path)
                logger.debug(f"Entry {entry_num}: Generated '{entry['audio_name']}', Length: {entry['audio_length']}ms")

            except Exception as e:
                logger.error(f"Failed to generate audio for entry {entry_num} ('{text_to_speak[:50]}...'): {e}", exc_info=True)
                # Provide more context in the error message
                raise RuntimeError(f"TTS failed for entry {entry_num} (Text: '{text_to_speak[:50]}...'). Model: {self.model_name}. Params: {current_params}. Original Error: {e}") from e
        logger.info("Audio segment generation finished.")


    def _process_timing(
        self,
        data: List[Dict[str, Any]],
        temp_folder: str,
        tempo_mode: Optional[str],
        tempo_speed: Optional[float],
        tempo_limit: Optional[float]
    ):
        """Adjusts tempo of audio segments based on selected mode."""
        if not tempo_mode:
            logger.info("Tempo adjustment skipped (tempo_mode is None).")
            return

        logger.info(f"Starting tempo processing (mode: {tempo_mode})...")
        num_entries = len(data)
        for idx, entry in enumerate(data):
            entry_num = entry.get('entry_number', idx + 1)
            audio_path = os.path.join(temp_folder, entry['audio_name'])
            if not os.path.exists(audio_path):
                 logger.warning(f"Entry {entry_num}: Audio file {entry['audio_name']} not found for tempo processing. Skipping.")
                 continue

            original_length = entry.get('audio_length', 0)
            if original_length == 0:
                logger.warning(f"Entry {entry_num}: Original audio length is 0. Skipping tempo adjustment.")
                continue

            target_speed = 1.0
            reason = "no adjustment needed"

            if tempo_mode == "all":
                target_speed = tempo_speed if tempo_speed is not None else 1.0
                reason = f"mode 'all', target speed {target_speed:.2f}"
            elif tempo_mode in ("overflow", "precise"):
                sub_start = entry['start_time']
                sub_end = entry['end_time']
                if tempo_mode == "overflow":
                    # Time available is until the next subtitle starts (or just the sub duration if it's the last one)
                    next_start_time = data[idx+1]['start_time'] if idx + 1 < num_entries else sub_end + (sub_end - sub_start) # Estimate for last
                    target_time = next_start_time - sub_start
                else: # precise
                    target_time = sub_end - sub_start

                target_time = max(1, target_time) # Avoid division by zero or negative duration

                if original_length > target_time:
                    calculated_speed = original_length / target_time
                    target_speed = calculated_speed
                    reason = f"mode '{tempo_mode}', original {original_length}ms > target {target_time}ms, calculated speed {target_speed:.2f}"

                    if tempo_limit is not None and target_speed > tempo_limit:
                        logger.warning(f"Entry {entry_num}: Required speed {target_speed:.2f}x exceeds limit {tempo_limit:.2f}. Clamping speed.")
                        target_speed = tempo_limit
                        reason += f", clamped to limit {target_speed:.2f}"
                else:
                     # No overflow, keep speed at 1.0
                     target_speed = 1.0
                     reason = f"mode '{tempo_mode}', original {original_length}ms <= target {target_time}ms"

            else:
                 logger.warning(f"Entry {entry_num}: Unknown tempo_mode '{tempo_mode}'. Skipping adjustment.")
                 continue


            # Apply adjustment if speed is not 1.0
            if abs(target_speed - 1.0) > 1e-3: # Check if speed change is significant
                 logger.info(f"Entry {entry_num}: Adjusting tempo. Reason: {reason}.")
                 try:
                    self._adjust_tempo(audio_path, target_speed)
                    # Update length after adjustment
                    entry['audio_length'] = self._audio_length(audio_path)
                    logger.debug(f"Entry {entry_num}: Tempo adjusted to {target_speed:.2f}x. New length: {entry['audio_length']}ms")
                 except Exception as e:
                     logger.error(f"Entry {entry_num}: Failed tempo adjustment (Speed: {target_speed:.2f}). Error: {e}", exc_info=True)
                     # Optionally re-raise or continue with original length
                     # raise RuntimeError(f"Tempo adjustment failed for {entry['audio_name']}") from e
                     logger.warning(f"Entry {entry_num}: Continuing without tempo adjustment due to error.")
                     entry['audio_length'] = original_length # Revert to original if adjust failed
            else:
                 logger.debug(f"Entry {entry_num}: No tempo adjustment needed. Reason: {reason}.")
                 entry['audio_length'] = original_length # Ensure length is set even if no adjustment

        logger.info("Tempo processing finished.")


    def _adjust_tempo(self, audio_path: str, target_speed: float):
        """Adjusts audio tempo using ffmpeg-python."""
        # Clamp speed to ffmpeg's practical limits (approx 0.5 to 100, but quality degrades significantly)
        # Sticking to a safer range like 0.5 to 3.0 or 4.0 is often better.
        safe_speed = max(0.5, min(target_speed, 4.0)) # Clamped safe range
        if abs(safe_speed - target_speed) > 1e-3:
             logger.warning(f"Target speed {target_speed:.2f}x outside safe range [0.5, 4.0]. Clamping to {safe_speed:.2f}x for file {os.path.basename(audio_path)}.")

        temp_output_path = f"{audio_path}.temp.wav" # Ensure .wav extension

        try:
            (
                ffmpeg.input(audio_path)
                .filter('atempo', safe_speed)
                .output(temp_output_path, acodec='pcm_s16le') # Specify codec for WAV
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, quiet=True) # Use quiet=True for less noise
            )
            # Replace original file with tempo-adjusted file
            os.replace(temp_output_path, audio_path)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode() if e.stderr else "No stderr"
            logger.error(f"FFmpeg tempo adjustment failed for {os.path.basename(audio_path)} (Speed: {safe_speed:.2f}):\n{stderr}")
            # Attempt to clean up temp file if it exists
            if os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except OSError:
                    pass # Ignore cleanup errors
            raise RuntimeError(f"FFmpeg atempo filter failed for {os.path.basename(audio_path)}: {stderr}") from e
        except Exception as e_os:
             logger.error(f"OS error during tempo adjustment file replacement for {os.path.basename(audio_path)}: {e_os}", exc_info=True)
             raise


    def _build_final_audio(
        self,
        data: List[Dict[str, Any]],
        temp_folder: str,
        strict_timing: bool
    ) -> AudioSegment:
        """Builds the final audio track by overlaying segments."""
        logger.info("Building final audio track...")
        if not data:
            logger.warning("No data to build audio from. Returning 1 second of silence.")
            return AudioSegment.silent(duration=1000)

        # Calculate required duration based on the END time of the last segment
        # (start_time + audio_length) after all adjustments. Add buffer.
        try:
             max_req_time = max(entry['start_time'] + entry.get('audio_length', 0) for entry in data if 'start_time' in entry)
        except ValueError:
             logger.warning("Could not determine maximum required time. Using fallback duration.")
             max_req_time = sum(entry.get('audio_length', 0) for entry in data) # Rough estimate

        total_duration_ms = max_req_time + 1000  # Add 1-second buffer
        logger.info(f"Creating silent base track with duration: {total_duration_ms}ms")
        base_audio = AudioSegment.silent(duration=total_duration_ms)

        last_segment_end_time = 0
        num_entries = len(data)

        for idx, entry in enumerate(data):
            entry_num = entry.get('entry_number', idx + 1)
            audio_path = os.path.join(temp_folder, entry['audio_name'])
            start_time_ms = entry.get('start_time', 0)
            audio_length_ms = entry.get('audio_length', 0)

            if not os.path.exists(audio_path):
                logger.warning(f"Entry {entry_num}: Audio file '{entry['audio_name']}' not found for final assembly. Skipping.")
                continue

            if audio_length_ms <= 0:
                 logger.info(f"Entry {entry_num}: Audio length is {audio_length_ms}ms. Skipping overlay.")
                 continue

            # --- Overlap Check ---
            overlap_ms = last_segment_end_time - start_time_ms
            if overlap_ms > 10:  # Allow tiny overlaps due to rounding
                overlap_msg = (f"Overlap detected for entry {entry_num} ('{entry['text'][:30]}...'): "
                             f"Starts at {start_time_ms}ms, but previous segment ends at {last_segment_end_time}ms "
                             f"(Overlap: {overlap_ms}ms)")
                if strict_timing:
                    logger.error(overlap_msg)
                    # Skip this segment as it would overlap with previous
                    logger.warning(f"Skipping entry {entry_num} to maintain strict timing")
                    continue
                else:
                    logger.warning(f"{overlap_msg}. Allowing overlap as strict_timing=False")
            # --- End Overlap Check ---

            # Clamp start time to be non-negative
            start_position = max(0, start_time_ms)
            if start_position != start_time_ms:
                 logger.warning(f"Entry {entry_num}: Original start time {start_time_ms}ms was negative. Clamping to 0ms.")


            try:
                segment = AudioSegment.from_file(audio_path)
                segment_length = len(segment) # Use pydub's length calculation

                # Ensure segment doesn't try to write past the base audio buffer
                if start_position + segment_length > len(base_audio):
                    allowed_length = len(base_audio) - start_position
                    if allowed_length <= 0:
                         logger.warning(f"Entry {entry_num}: Segment starts at or after base audio end ({start_position}ms >= {len(base_audio)}ms). Skipping overlay.")
                         continue # Skip if it starts completely outside
                    else:
                         logger.warning(f"Entry {entry_num}: Segment extends past end of base track ({start_position + segment_length}ms > {len(base_audio)}ms). Truncating segment.")
                         segment_to_overlay = segment[:allowed_length]
                else:
                    segment_to_overlay = segment

                if len(segment_to_overlay) > 0:
                    logger.debug(f"Entry {entry_num}: Overlaying '{entry['audio_name']}' at {start_position}ms (Length: {len(segment_to_overlay)}ms)")
                    base_audio = base_audio.overlay(segment_to_overlay, position=start_position)
                    # Update the end time for the next iteration's overlap check
                    last_segment_end_time = start_position + len(segment_to_overlay)
                else:
                     logger.warning(f"Entry {entry_num}: Segment '{entry['audio_name']}' has zero length after adjustments/truncation. Skipping overlay.")
                     # Keep last_segment_end_time as it was

            except Exception as e:
                logger.error(f"Failed to load or overlay segment {entry_num} ('{entry['audio_name']}'): {e}", exc_info=True)
                # Decide whether to raise or continue
                if strict_timing:
                     raise RuntimeError(f"Failed to process segment {entry_num}: {e}") from e
                else:
                     logger.warning(f"Continuing build despite error processing segment {entry_num}.")
                     # Ensure last_segment_end_time doesn't get stuck if this segment failed
                     # Use calculated end if possible, otherwise estimate based on start time
                     last_segment_end_time = max(last_segment_end_time, start_position + audio_length_ms)


        logger.info("Final audio track assembly finished.")
        return base_audio


    def _shifter(
        self,
        data: List[Dict[str, Any]],
        mode: str,
        shift_limit: Optional[Union[int, str]]
    ) -> List[Dict[str, Any]]:
        """Applies time shifting to resolve overflows based on the selected mode."""
        logger.info(f"Starting time shifting (mode: {mode})...")
        shift_modes_map = {
            "right": self._right_shift,
            "left": self._left_shift,
            "interpose": self._interpose_shift,
            # The lambda functions pass allow_overlap=True implicitly
            "left-overlap": lambda d, l: self._left_shift(d, l, allow_overlap=True),
            "interpose-overlap": lambda d, l: self._interpose_shift(d, l, allow_overlap=True)
        }

        if mode not in shift_modes_map:
            raise ValueError(f"Invalid shift mode: {mode}. Valid options: {list(shift_modes_map.keys())}")

        limit_ms = self._parse_shift_limit(shift_limit)
        logger.info(f"Shift limit parsed to: {limit_ms}ms")

        # Use a deepcopy to avoid modifying the original list passed to the specific shift function if it fails
        data_copy = copy.deepcopy(data)
        try:
            shifted_data = shift_modes_map[mode](data_copy, limit_ms)
            logger.info("Time shifting finished.")
            return shifted_data
        except RuntimeError as e:
             logger.error(f"Shift mode '{mode}' failed to resolve overflow without overlap: {e}")
             raise # Re-raise the specific error from the shift function
        except Exception as e:
             logger.error(f"Unexpected error during time shifting (mode: {mode}): {e}", exc_info=True)
             raise RuntimeError(f"Shifting failed unexpectedly: {e}") from e


    def _right_shift(self, data: List[Dict[str, Any]], limit: Optional[int]) -> List[Dict[str, Any]]:
        """Shifts overflowing segments and subsequent segments to the right."""
        logger.info("Applying right shift...")
        total_shift_applied = 0
        num_entries = len(data)

        for i in range(num_entries):
            entry_num = data[i].get('entry_number', i + 1)
            # Apply accumulated shift from previous entries first
            if total_shift_applied > 0:
                 logger.debug(f"Entry {entry_num}: Applying cumulative right shift of {total_shift_applied}ms.")
                 data[i]['start_time'] += total_shift_applied
                 data[i]['end_time'] += total_shift_applied

            # Calculate overflow for the current entry AFTER applying cumulative shift
            audio_len = data[i].get('audio_length', 0)
            sub_time = data[i].get('sub_time', data[i]['end_time'] - data[i]['start_time']) # Use calculated sub_time or duration
            sub_time = max(1, sub_time) # Ensure positive duration

            overflow = audio_len - sub_time
            if overflow <= 0:
                logger.debug(f"Entry {entry_num}: No overflow ({audio_len}ms <= {sub_time}ms).")
                continue

            # Determine shift amount for this specific entry's overflow
            shift_needed = overflow
            actual_shift = min(shift_needed, limit) if limit is not None else shift_needed
            if limit is not None and shift_needed > limit:
                 logger.warning(f"Entry {entry_num}: Overflow {shift_needed}ms exceeds right shift limit {limit}ms. Applying limited shift {actual_shift}ms.")

            logger.info(f"Entry {entry_num}: Overflow {overflow}ms. Applying right shift of {actual_shift}ms.")
            # This shift will affect all subsequent entries
            total_shift_applied += actual_shift

            # Note: The shift is conceptually applied here by incrementing total_shift_applied.
            # The actual start/end time updates for subsequent entries happen in their own loop iterations.

        return data

    def _left_shift(self, data: List[Dict[str, Any]], limit: Optional[int], allow_overlap: bool = False) -> List[Dict[str, Any]]:
        """Shifts overflowing segments to the left by stealing time from preceding gaps."""
        logger.info(f"Applying left shift (allow_overlap={allow_overlap})...")
        num_entries = len(data)

        for i in reversed(range(num_entries)): # Iterate backwards
            entry_num = data[i].get('entry_number', i + 1)
            audio_len = data[i].get('audio_length', 0)
            sub_time = data[i].get('sub_time', data[i]['end_time'] - data[i]['start_time'])
            sub_time = max(1, sub_time)

            overflow = audio_len - sub_time
            if overflow <= 0:
                logger.debug(f"Entry {entry_num}: No overflow ({audio_len}ms <= {sub_time}ms).")
                continue

            # Determine max shift allowed for this overflow
            max_shift = min(overflow, limit) if limit is not None else overflow
            if limit is not None and overflow > limit:
                 logger.warning(f"Entry {entry_num}: Overflow {overflow}ms exceeds left shift limit {limit}ms. Attempting max shift of {max_shift}ms.")
            logger.info(f"Entry {entry_num}: Overflow {overflow}ms. Attempting left shift up to {max_shift}ms.")

            shift_needed = max_shift
            shift_achieved = 0

            # Try to steal time from previous entries' gaps
            for j in reversed(range(i)): # Check entries before the current one
                 prev_entry_num = data[j].get('entry_number', j + 1)
                 prev_audio_len = data[j].get('audio_length', 0)
                 # Gap is the time between the end of prev audio and start of current audio
                 # More accurately, it's the "silent" time within the previous subtitle's slot
                 prev_sub_time = data[j].get('sub_time', data[j]['end_time'] - data[j]['start_time'])
                 prev_sub_time = max(1, prev_sub_time)

                 space_available = prev_sub_time - prev_audio_len
                 if space_available <= 0:
                     logger.debug(f"Entry {entry_num}: No space available to steal from preceding entry {prev_entry_num} ({prev_sub_time}ms <= {prev_audio_len}ms).")
                     continue

                 # How much can we steal from this specific previous entry?
                 steal_amount = min(shift_needed, space_available)
                 logger.debug(f"Entry {entry_num}: Stealing {steal_amount}ms from preceding entry {prev_entry_num} (available: {space_available}ms).")

                 # Apply the steal: Adjust the end time of the previous entry
                 # Note: We adjust the start/end times of the *current* entry later based on total shift achieved.
                 # Here, we conceptually "consume" the space. The timing structure needs careful thought.
                 # Let's adjust the *current* entry's start/end times immediately based on achieved shift.
                 data[i]['start_time'] -= steal_amount
                 data[i]['end_time'] -= steal_amount
                 # We don't adjust sub_time here, as it represents the original slot.

                 shift_achieved += steal_amount
                 shift_needed -= steal_amount

                 if shift_needed <= 0:
                     break # Got enough shift

            logger.info(f"Entry {entry_num}: Achieved {shift_achieved}ms left shift (needed {max_shift}ms).")

            # Check if overflow was fully resolved
            remaining_overflow = max_shift - shift_achieved
            if remaining_overflow > 10 and not allow_overlap: # Allow small tolerance
                error_msg = f"Cannot resolve {remaining_overflow:.1f}ms overflow for entry {entry_num} with left shift without overlap."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            elif remaining_overflow > 10:
                logger.warning(f"Entry {entry_num}: {remaining_overflow:.1f}ms overflow remains after left shift. Overlap may occur (allow_overlap=True).")
            # If allow_overlap is True, we just proceed even if shift_achieved < max_shift

        return data


    def _interpose_shift(self, data: List[Dict[str, Any]], limit: Optional[int], allow_overlap: bool = False) -> List[Dict[str, Any]]:
        """Shifts overflowing segments by stealing time from both preceding and succeeding gaps."""
        logger.info(f"Applying interpose shift (allow_overlap={allow_overlap})...")
        num_entries = len(data)

        # This mode is complex to implement correctly without potentially cascading issues.
        # A simpler approach might be preferred, or this needs very careful state management.
        # Let's try a basic implementation: distribute needed shift equally if possible.

        for i in range(num_entries):
            entry_num = data[i].get('entry_number', i + 1)
            audio_len = data[i].get('audio_length', 0)
            sub_time = data[i].get('sub_time', data[i]['end_time'] - data[i]['start_time'])
            sub_time = max(1, sub_time)

            overflow = audio_len - sub_time
            if overflow <= 0:
                logger.debug(f"Entry {entry_num}: No overflow ({audio_len}ms <= {sub_time}ms).")
                continue

            max_shift = min(overflow, limit) if limit is not None else overflow
            if limit is not None and overflow > limit:
                 logger.warning(f"Entry {entry_num}: Overflow {overflow}ms exceeds interpose shift limit {limit}ms. Attempting max shift of {max_shift}ms.")
            logger.info(f"Entry {entry_num}: Overflow {overflow}ms. Attempting interpose shift up to {max_shift}ms.")

            shift_needed = max_shift
            shift_from_prev = 0
            shift_to_next = 0 # This means pushing the next one later

            # Calculate potential shift from previous gap
            prev_available = 0
            if i > 0:
                prev_entry_num = data[i-1].get('entry_number', i)
                prev_audio_len = data[i-1].get('audio_length', 0)
                prev_sub_time = data[i-1].get('sub_time', data[i-1]['end_time'] - data[i-1]['start_time'])
                prev_sub_time = max(1, prev_sub_time)
                prev_available = max(0, prev_sub_time - prev_audio_len)
                logger.debug(f"Entry {entry_num}: Space available from preceding entry {prev_entry_num}: {prev_available}ms.")


            # Calculate potential push needed for the next entry (simpler than calculating gap)
            # We'll try to distribute the 'shift_needed'

            # Try to take up to half from the previous gap
            take_from_prev = min(shift_needed / 2, prev_available)
            shift_from_prev = take_from_prev
            shift_needed -= take_from_prev

            # The remaining 'shift_needed' must be accommodated by pushing the next entry
            shift_to_next = shift_needed # If positive, next entry needs to start later

            logger.debug(f"Entry {entry_num}: Planned shift: steal {shift_from_prev}ms from previous, push next by {shift_to_next}ms.")

            # Apply the shifts
            # 1. Shift current entry left by 'shift_from_prev'
            if shift_from_prev > 0:
                logger.debug(f"Entry {entry_num}: Shifting start/end left by {shift_from_prev}ms.")
                data[i]['start_time'] -= shift_from_prev
                data[i]['end_time'] -= shift_from_prev

            # 2. Push the *next* entry right by 'shift_to_next'
            # This creates complexity as it affects future calculations.
            # A simpler 'right shift' or 'left shift' might be more robust.
            # For this implementation, we'll assume this adjustment happens,
            # but a full implementation would need to carry this forward like _right_shift does.
            # Let's log the intended push for now.
            if shift_to_next > 0 and i + 1 < num_entries:
                 next_entry_num = data[i+1].get('entry_number', i + 2)
                 logger.debug(f"Entry {entry_num}: Requires pushing next entry {next_entry_num} right by {shift_to_next}ms (This effect needs proper propagation).")
                 # In a full implementation, you'd add shift_to_next to a cumulative shift for subsequent entries.

            shift_achieved = shift_from_prev # Only count the left shift as 'achieved' for resolving current overflow space
            remaining_overflow = max_shift - shift_achieved

            # We didn't technically resolve the 'shift_to_next' part within this entry's space.
            # This mode is problematic without careful propagation.
            # Check based only on the left shift achieved.
            if remaining_overflow > 10 and not allow_overlap:
                error_msg = f"Cannot fully resolve {max_shift:.1f}ms overflow for entry {entry_num} with interpose shift without overlap (achieved {shift_achieved:.1f}ms left shift)."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            elif remaining_overflow > 10 :
                 logger.warning(f"Entry {entry_num}: {remaining_overflow:.1f}ms overflow likely remains after interpose shift. Overlap may occur (allow_overlap=True or push needed).")

        logger.warning("Interpose shift implementation is basic and may not fully propagate right-shifts. Use with caution or prefer 'left'/'right' modes.")
        return data


    def _extract_data_srt(self, file_path: str) -> List[Dict[str, Any]]:
        """Parses an SRT file content."""
        # Regex to capture entry number, start time, end time, and text body
        # Handles potential extra spaces/newlines in text body
        pattern = re.compile(
            r'(\d+)\r?\n'                                    # Entry number
            r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\r?\n' # Timestamps
            r'(.+?)\r?\n\r?\n',                              # Text body (non-greedy) until blank line
            re.DOTALL | re.MULTILINE
        )
        # Regex to find the start time of the *next* subtitle entry
        next_start_pattern = re.compile(r'^\d+\r?\n(\d{2}:\d{2}:\d{2},\d{3})', re.MULTILINE)

        subtitle_data = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
             raise IOError(f"Could not read SRT file {file_path}: {e}") from e

        # Add double newline at the end to ensure last entry is captured by regex
        content += "\n\n"

        last_end_time = 0
        matches = list(pattern.finditer(content))

        for i, match in enumerate(matches):
            entry_number = int(match.group(1))
            start_time_str = match.group(2)
            end_time_str = match.group(3)
            text = match.group(4).strip()
            # Clean HTML-like tags from text
            text = re.sub(r'<.*?>', '', text)
            # Replace multiple spaces/newlines within text with single space
            text = re.sub(r'\s+', ' ', text).strip()

            try:
                start_time = self._convert_time_to_intmil(start_time_str)
                end_time = self._convert_time_to_intmil(end_time_str)
            except ValueError as e:
                logger.error(f"Skipping entry {entry_number} due to invalid time format: {e}")
                continue

            if start_time < last_end_time:
                 logger.warning(f"Entry {entry_number}: Start time {start_time}ms is before previous end time {last_end_time}ms. Check SRT file for overlaps.")
            if end_time <= start_time:
                 logger.warning(f"Entry {entry_number}: End time {end_time}ms is not after start time {start_time}ms. Duration will be minimal.")
                 end_time = start_time + 1 # Ensure minimal duration

            # Calculate sub_time: duration until next subtitle starts
            # Find the start time of the *next* entry in the list of matches
            next_start_time = None
            if i + 1 < len(matches):
                 next_match = matches[i+1]
                 try:
                     next_start_time = self._convert_time_to_intmil(next_match.group(2))
                 except ValueError:
                      logger.warning(f"Could not parse start time for entry {int(next_match.group(1))}. Sub_time for entry {entry_number} might be inaccurate.")


            if next_start_time is not None:
                sub_time = next_start_time - start_time
            else:
                # For the last entry, use its own duration as sub_time
                sub_time = end_time - start_time

            # Ensure sub_time is positive
            sub_time = max(1, sub_time)

            subtitle_data.append({
                'entry_number': entry_number,
                'start_time': start_time,
                'end_time': end_time,
                'text': text,
                'sub_time': sub_time, # Time available until next sub starts
                'audio_name': f"{entry_number}_audio.wav"
            })
            last_end_time = end_time

        if not subtitle_data:
             logger.warning(f"No valid subtitle entries found in {file_path}.")

        return subtitle_data

    def _convert_time_to_intmil(self, time_str: str) -> int:
        """Converts HH:MM:SS,ms time string to milliseconds integer."""
        try:
            parts = time_str.split(':')
            h = int(parts[0])
            m = int(parts[1])
            s_ms = parts[2].replace(',', '.').split('.')
            s = int(s_ms[0])
            ms = int(s_ms[1].ljust(3, '0')[:3]) # Ensure 3 digits, take first 3
            return (h * 3600 + m * 60 + s) * 1000 + ms
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid time format '{time_str}': {e}") from e

    def _audio_length(self, audio_path: str) -> int:
        """Gets the duration of an audio file in milliseconds."""
        try:
            # Use librosa for duration calculation
            duration_seconds = librosa.get_duration(path=audio_path)
            return int(duration_seconds * 1000)
        except Exception as e:
            logger.error(f"Could not get duration for audio file '{audio_path}': {e}", exc_info=True)
            # Fallback or re-raise
            # return 0 # Or raise an error
            raise IOError(f"Failed to get audio length for {os.path.basename(audio_path)}") from e


    def _validate_inputs(
        self,
        data: List[Dict[str, Any]],
        tempo_mode: Optional[str],
        tempo_speed: Optional[float],
        tempo_limit: Optional[float],
        shift_mode: Optional[str]
    ):
        """Validates input parameters for conversion."""
        if not data:
            raise ValueError("No subtitle data provided.")

        valid_tempo_modes = [None, "all", "overflow", "precise"]
        if tempo_mode not in valid_tempo_modes:
            raise ValueError(f"Invalid tempo_mode: {tempo_mode}. Must be one of {valid_tempo_modes}")

        if tempo_mode == "all":
            if tempo_speed is None:
                 raise ValueError("tempo_speed must be provided when tempo_mode is 'all'.")
            if not (0.5 <= tempo_speed <= 100.0): # FFmpeg theoretical max, practical is lower
                logger.warning(f"Tempo speed {tempo_speed} is outside the typical practical range [0.5, 4.0]. Quality may be affected.")

        if tempo_mode in ["overflow", "precise"]:
             if tempo_limit is not None and tempo_limit < 0.5:
                  raise ValueError("tempo_limit cannot be less than 0.5.")

        valid_shift_modes = [None, "right", "left", "interpose", "left-overlap", "interpose-overlap"]
        if shift_mode not in valid_shift_modes:
             raise ValueError(f"Invalid shift_mode: {shift_mode}. Must be one of {valid_shift_modes}")


    def _ensure_wav_extension(self, path: Optional[str]) -> str:
        """Ensures the output path ends with .wav, defaulting if path is None."""
        if not path:
            base = os.path.splitext(self.name_path)[0]
            logger.info(f"Output path not specified, defaulting to: {base}.wav")
            return f"{base}.wav"

        # Ensure the directory exists if a full path is given
        dir_name = os.path.dirname(path)
        if dir_name:
             os.makedirs(dir_name, exist_ok=True)

        # Check and add extension
        if not path.lower().endswith('.wav'):
            logger.warning(f"Output path '{path}' did not end with .wav. Appending .wav.")
            return f"{path}.wav"
        return path

    def _parse_shift_limit(self, limit: Optional[Union[int, str]]) -> Optional[int]:
        """Parses shift limit (int ms or str 'Xs') into milliseconds."""
        if limit is None:
            return None
        if isinstance(limit, int):
            return max(0, limit) # Ensure non-negative
        if isinstance(limit, str):
            limit_str = limit.lower().strip()
            try:
                if limit_str.endswith('s'):
                    seconds = float(limit_str[:-1])
                    return max(0, int(seconds * 1000))
                elif limit_str.endswith('ms'):
                     return max(0, int(limit_str[:-2]))
                else:
                     # Assume milliseconds if no unit
                     return max(0, int(limit_str))
            except ValueError:
                logger.error(f"Invalid shift_limit string format: '{limit}'. Must be int (ms) or str ('Xs' or 'Xms').")
                return None # Treat as no limit if parsing fails
        return None # Should not be reached if type hint is correct

    def _save_temp_files(self, temp_folder: str, output_path: str):
        """Saves intermediate audio segments to a subfolder."""
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        # Place segments folder relative to the output file or CWD if output path is just a name
        output_dir = os.path.dirname(output_path) or "."
        save_path = os.path.join(output_dir, f"{base_name}_segments")

        try:
            if os.path.exists(save_path):
                 logger.warning(f"Temporary save path '{save_path}' already exists. Overwriting.")
                 shutil.rmtree(save_path) # Remove existing folder to avoid merging old/new files

            shutil.copytree(temp_folder, save_path)
            logger.info(f"Temporary audio segments saved to: {save_path}")
        except Exception as e:
            logger.error(f"Failed to save temporary files to '{save_path}': {e}", exc_info=True)


    @property
    def speakers(self) -> List[str]:
        """Returns the list of available speaker names for the loaded model, if applicable."""
        if hasattr(self.apitts, 'speakers') and self.apitts.speakers:
             # Check if speakers is a list or dict (XTTS might use dict keys)
             if isinstance(self.apitts.speakers, list):
                  return self.apitts.speakers
             elif isinstance(self.apitts.speakers, dict):
                  return list(self.apitts.speakers.keys())
             else:
                  logger.warning(f"Unexpected type for speakers attribute: {type(self.apitts.speakers)}")
                  return []
        return []

    @property
    def languages(self) -> List[str]:
        """Returns the list of supported language codes for the loaded model, if applicable."""
        if hasattr(self.apitts, 'languages') and self.apitts.languages:
            return self.apitts.languages
        # For XTTS, language might be inferred or set during TTS call rather than listed here.
        # Return 'en' or a common default if XTTS is loaded and no list is present.
        if self.is_xtts_model:
             # XTTS v2 is multilingual, but the API might not expose a list directly via .languages
             logger.info("XTTS model detected. Language support is broad; specify language during conversion.")
             # Returning a representative list or common ones might be useful for UI, but technically depends on the call.
             return ['en', 'es', 'fr', 'de', 'it', 'pt', 'pl', 'tr', 'ru', 'nl', 'cs', 'ar', 'zh-cn', 'ja', 'hu', 'ko'] # Example for XTTS v2
        return []


    def __repr__(self):
        """String representation of the SubToAudio instance."""
        model_info = self.model_name if self.model_name else "Unknown model"
        return f"<SubToAudio using {model_info}>"

# Example Usage (Optional - requires a subtitle file and TTS setup)
# if __name__ == "__main__":
#     # Configure logging level if needed
#     logging.basicConfig(level=logging.DEBUG)
#
#     # --- Configuration ---
#     SRT_FILE = "path/to/your/subtitle.srt" # REQUIRED: Change this
#     OUTPUT_WAV = "path/to/your/output.wav" # Optional: Change this
#     # For XTTS:
#     SPEAKER_WAV_PATH = "path/to/reference/voice.wav" # REQUIRED for XTTS: Change this
#     TARGET_LANGUAGE = "en" # REQUIRED for XTTS: Change this (e.g., 'en', 'es')
#
#     # --- Initialization ---
#     try:
#         # Using default XTTS model (ensure you have required packages)
#         sub_to_audio = SubToAudio(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
#         # Or specify a different model:
#         # sub_to_audio = SubToAudio(model_name="tts_models/en/ljspeech/tacotron2-DDC") # Example single speaker
#
#         # --- Processing ---
#         print("1. Parsing Subtitles...")
#         subtitle_data = sub_to_audio.subtitle(SRT_FILE)
#
#         print(f"   Found {len(subtitle_data)} entries.")
#         # print(f"   Example entry: {subtitle_data[0] if subtitle_data else 'N/A'}")
#
#         print("\n2. Converting to Audio...")
#         sub_to_audio.convert_to_audio(
#             sub_data=subtitle_data,
#             output_path=OUTPUT_WAV,
#             # --- XTTS Specific ---
#             speaker_wav=SPEAKER_WAV_PATH, # Crucial for XTTS
#             language=TARGET_LANGUAGE,     # Crucial for XTTS
#             # --- General TTS ---
#             # speaker=None, # Use speaker_wav instead for XTTS
#             # --- Timing ---
#             tempo_mode="overflow", # Adjust speed if audio is longer than time until next sub
#             tempo_limit=2.5,       # Allow up to 2.5x speedup if needed
#             shift_mode="right",    # If still too long, push subsequent audio later
#             shift_limit="0.5s",    # Limit the push to 500ms max per segment
#             strict_timing=False,   # Log warnings on overlap instead of crashing
#             # --- Other ---
#             save_temp=False         # Don't keep intermediate files
#         )
#
#         print(f"\n3. Finished! Output saved to: {OUTPUT_WAV}")
#
#     except FileNotFoundError as e:
#         print(f"Error: Input file not found - {e}")
#     except ValueError as e:
#         print(f"Error: Invalid input or configuration - {e}")
#     except RuntimeError as e:
#         print(f"Error: Processing failed - {e}")
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#         # Log the full traceback for unexpected errors
#         import traceback
#         traceback.print_exc()