import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageOps, ImageTk
import logging
import threading
from processors.srt_parser import SRTParser
from processors.image_generator import ImageGenerator
from processors.video_processor import VideoProcessor
from utils.helpers import TempFileManager
from utils.style_parser import StyleParser
import concurrent.futures
import os
import json
import subprocess
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from processors.sub2audio import SubToAudio
from pydub import AudioSegment

class VideoConverterApp:
    def __init__(self, root):
        try:
            self.root = root
            self.root.title("Video Caption Creator")
            self.root.geometry("1000x850")
            self.preview_window = None
            
            # Initialize app components in correct order
            self.setup_logging()   # 1. Configure logging first for better error tracking
            self.initialize_app()  # 2. Variables and core components
            self.setup_styles()    # 3. UI styling
            self.create_widgets()  # 4. Create GUI elements
            
        except Exception as e:
            logging.critical(f"Failed to initialize application: {str(e)}")
            messagebox.showerror("Initialization Error", "Failed to start application. Check logs for details.")
            raise

    def show_about(self):
        """Display the about information."""
        about_text = (
            "Developed by: Wael Sahli\n"
            "Year: 2025\n"
            "Version: v1.0"
        )
        messagebox.showinfo("About", about_text)

    def get_current_settings(self) -> dict:
        """Safely get current settings with null checks"""
        settings = {
            'text_color': self.text_color_var.get(),
            'bg_color': self.bg_color_var.get(),
            'font_size': self.font_size_var.get(),
            'text_border': self.border_var.get(),
            'text_shadow': self.shadow_var.get(),
            'background_image': self.background_image_path,
            'background_music': self.background_music_path,
            'custom_font': self.custom_font_path,
            'margin': 20,
            'speed_factor': 1.0,
            'batch_size': 50,
            'tts_model': self.model_var.get(),
            'reference_audio': self.speaker_ref_path,
            'user_value': self._safe_int_get(self.user_value_var, 0)
        }
        # Safe language combo handling
        if hasattr(self, 'lang_combo') and self.lang_combo:
            settings['tts_language'] = self.lang_combo.get()
        else:
            settings['tts_language'] = self.language_var.get()  # Use the StringVar value
        
        return settings    

    def _safe_int_get(self, var: tk.StringVar, default: int) -> int:
        """Safely get integer value from StringVar"""
        try:
            return int(var.get())
        except (ValueError, AttributeError):
            return default

    def initialize_app(self):
        """Initialize all application state and components in correct order"""
        # 1. Initialize Tkinter variables first
        self.text_color_var = tk.StringVar(value="#FFFFFF")
        self.bg_color_var = tk.StringVar(value="#000000")
        self.font_size_var = tk.IntVar(value=24)
        self.border_var = tk.BooleanVar(value=True)
        self.shadow_var = tk.BooleanVar(value=False)
        self.user_value_var = tk.StringVar(value="0")
        self.expected_dimensions = (1280, 720)
        self.tts_models = []
        self.current_tts = None
        self.model_var = tk.StringVar()
        self.speaker_ref_path = None

        self.lang_combo = None
        self.language_var = tk.StringVar(value="fr")

        self.settings = {
            'batch_size': 50,  # Default value
            'expected_dimensions': self.expected_dimensions
        }

        # 2. Initialize file paths
        self.background_image_path = None
        self.background_music_path = None
        self.custom_font_path = None
        self.srt_path = None

        # 3. Initialize core components with default settings
        self.temp_manager = TempFileManager()
        self.style_parser = StyleParser()
        self.srt_parser = SRTParser()

        # 4. Get initial settings from variables
        initial_settings = self.get_current_settings()

        # 5. Create processing components with initial settings
        self.image_generator = ImageGenerator(
            self.temp_manager,
            self.style_parser,
            self.get_current_settings()
        )

        self.video_processor = VideoProcessor(
            self.temp_manager,
            self.get_current_settings()
        )

        # 6. Initialize other state
        self.running = False
        self.preview_window = None
        self.futures = []

        # 7. Load TTS models
        self.load_tts_models()
        self.check_tts_installation()

        self.update_settings()

    def _safe_var_get(self, var, default):
        """Safely get variable value with fallback"""
        try:
            return var.get()
        except AttributeError:
            logging.warning(f"Missing variable, using default: {default}")
            return default

    def reset_application(self):
        if messagebox.askyesno("Confirm Reset", "This will reset all settings and clear temporary files.\nContinue?"):
            # Cancel operations and clean up
            self.cancel_generation()
            self.temp_manager.cleanup()
            
            # Destroy existing widgets
            for widget in self.root.winfo_children():
                widget.destroy()
            
            # Reinitialize entire application
            self.initialize_app()
            self.setup_styles()
            self.create_widgets()
            
            # Force UI update
            self.root.update_idletasks()
            messagebox.showinfo("Reset Complete", "Application has been reset to default state")

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TButton', font=('Helvetica', 10), padding=5)
        self.style.configure('TLabel', font=('Helvetica', 10))
        self.style.configure('Header.TLabel', font=('Helvetica', 10, 'bold'))
        self.style.configure('Progressbar', thickness=20)

    def create_widgets(self):
        try:
            main_frame = ttk.Frame(self.root, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            banner_frame = tk.Frame(self.root, bg="#4A90E2", height=60)
            banner_frame.pack(fill=tk.X)

            # Add a banner label (you can change the text as needed)
            banner_label = tk.Label(
                banner_frame,
                text="Video Caption Creator",
                bg="#4A90E2",
                fg="white",
                font=("Helvetica", 18, "bold")
            )
            banner_label.pack(side=tk.LEFT, padx=20, pady=20)

            # Add the About button in the banner
            about_button = tk.Button(
                banner_frame,
                text="About",
                command=self.show_about,
                bg="white",
                fg="#4A90E2",
                font=("Helvetica", 12, "bold"),
                relief=tk.RAISED,
                bd=2
            )
            about_button.pack(side=tk.RIGHT, padx=20, pady=20)

            # Settings Panel
            settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding=10)
            settings_frame.pack(fill=tk.X, pady=10)

            # Add input section
            input_frame = ttk.Frame(main_frame)
            input_frame.pack(fill=tk.X, pady=10)

            # Integer input box for Edit SRT file delay
            ttk.Label(input_frame, text="Edit SRT file add a delay in Millisecond:").pack(side=tk.LEFT)
            self.num_input = ttk.Entry(
                input_frame,
                textvariable=self.user_value_var,
                validate='key',
                validatecommand=(self.root.register(self.validate_int), '%P')
            )
            self.num_input.pack(side=tk.LEFT, padx=5)

            # Color Controls
            ttk.Button(settings_frame, text="Text Color",
                     command=self.choose_text_color).grid(row=0, column=0, pady=5)

            self.text_color_label = tk.Label(
                settings_frame,
                textvariable=self.text_color_var,
                relief='sunken',
                width=15,
                font=('Helvetica', 8)
            )
            self.text_color_label.grid(row=0, column=1, padx=5)

            ttk.Button(settings_frame, text="Background Color",
                     command=self.choose_bg_color).grid(row=2, column=0, padx=5)

            self.bg_color_label = tk.Label(
                settings_frame,
                textvariable=self.bg_color_var,
                relief='sunken',
                width=15,
                font=('Helvetica', 8)
            )
            self.bg_color_label.grid(row=2, column=1, padx=5)

            # Font Controls
            ttk.Label(settings_frame, text="Text Size:").grid(row=0, column=5)
            self.font_size_slider = ttk.Scale(settings_frame, from_=10, to=100,
                                           variable=self.font_size_var)
            self.font_size_slider.grid(row=2, column=5)
            self.font_size_slider.set(24)

            ttk.Button(settings_frame, text="Select Font",
                     command=self.choose_font).grid(row=4, column=0, pady=5)

            # Effects Checkboxes
            ttk.Checkbutton(settings_frame, text="Text Border",
                          variable=self.border_var).grid(row=7, column=5, padx=5)
            ttk.Checkbutton(settings_frame, text="Text Shadow",
                          variable=self.shadow_var).grid(row=8, column=5, padx=5)

            # Media Controls
            ttk.Button(settings_frame, text="Background Image",
                     command=self.choose_background_image).grid(row=6, column=5, padx=5)

            ttk.Button(settings_frame, text="Background Music",
                     command=self.choose_background_music).grid(row=6, column=0, padx=5)

            # Preview Button
            ttk.Button(settings_frame, text="Preview Style",
                     command=self.show_preview).grid(row=4, column=5, columnspan=2, padx=5)

            # Progress Area
            progress_frame = ttk.Frame(main_frame)
            progress_frame.pack(fill=tk.X, pady=20)
            self.progress = ttk.Progressbar(progress_frame, mode='determinate')
            self.progress.pack(fill=tk.X)
            self.progress_label = ttk.Label(progress_frame, text="Ready")
            self.progress_label.pack()

            # Action Buttons
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="Generate Video",
                     command=self.start_generation).pack(side=tk.LEFT)
            ttk.Button(btn_frame, text="Cancel",
                     command=self.cancel_generation).pack(side=tk.LEFT, padx=5)

            ttk.Button(btn_frame, text="Generate TTS Audio",
                     command=self.start_audio_generation).pack(side=tk.LEFT, padx=5)

            #Reset button
            reset_frame = ttk.Frame(self.root)
            reset_frame.pack(pady=10, fill=tk.X)
            ttk.Button(
                reset_frame,
                text="Reset Application",
                command=self.reset_application,
                style='Danger.TButton'
            ).pack(side=tk.LEFT, padx=5)

            #Add SRT file
            ttk.Button(settings_frame, text="Select SRT File",
                     command=self.choose_srt_file).grid(row=5, column=0, pady=5)
            self.srt_label = ttk.Label(settings_frame, text="No SRT file selected")
            self.srt_label.grid(row=5, column=1, padx=5)

            #self.num_input.delete(0, tk.END)
            #self.num_input.insert(0, "100")
            
            # TTS Controls Section
            tts_frame = ttk.LabelFrame(settings_frame, text="Text-to-Speech Settings", padding=20)
            tts_frame.grid(row=9, column=0, columnspan=6, sticky="ew", pady=5)

            # Model Selection
            ttk.Label(tts_frame, text="Model:").grid(row=0, column=0, sticky='w')
            self.model_combo = ttk.Combobox(
                tts_frame, 
                textvariable=self.model_var,
                state='readonly',
                width=50
            )
            self.model_combo.grid(row=0, column=1, padx=5)
            self.model_combo.bind('<<ComboboxSelected>>', self._on_model_selected)

            # Reference Audio
            ttk.Button(
                tts_frame, 
                text="Reference Audio",
                command=self.choose_reference_audio
            ).grid(row=1, column=0, pady=5)
            self.ref_audio_label = ttk.Label(tts_frame, text="No audio selected")
            self.ref_audio_label.grid(row=1, column=1, sticky='w')

            # Language Selection
            ttk.Label(tts_frame, text="Language:").grid(row=2, column=0)
            self.lang_combo = ttk.Combobox(
                tts_frame, 
                textvariable=self.language_var,  # Link to StringVar
                state='readonly',
                width=15
            )
            self.lang_combo.grid(row=2, column=1)
            self.lang_combo.set("fr")  # Initial value

            # Reset color labels
            self.text_color_label.config(bg="#FFFFFF", fg="black")
            self.bg_color_label.config(bg="#000000", fg="white")
            
            # Reset checkboxes
            self.border_var.set(True)
            self.shadow_var.set(False)

            self.update_color_labels()
            self.load_tts_models()

        except AttributeError as ae:
            logging.critical(f"Widget creation failed: {str(ae)}")
            messagebox.showerror("Fatal Error", "Application failed to initialize")
            self.root.destroy()

    @staticmethod
    def validate_int(new_value):
        """Validation for integer input (including negatives)"""
        if new_value == "":
            return False  # Disallow empty field
        try:
            int(new_value)
            return True
        except ValueError:
            return False

    def update_settings(self):
        """Update settings from UI components"""
        self.settings['batch_size'] = int(self.settings.get('batch_size', 50))
        self.settings.update({
            'text_color': self.text_color_var.get(),
            'bg_color': self.bg_color_var.get(),
            'font_size': self.font_size_var.get(),
            'text_border': self.border_var.get(),
            'text_shadow': self.shadow_var.get(),
            'background_image': self.background_image_path,
            'background_music': self.background_music_path,
            'custom_font': self.custom_font_path,
            'speed_factor': 1.0,
            'margin': 20,
            'user_value': int(self.user_value_var.get())
        })
        """Force settings refresh in all components"""
        current_settings = self.get_current_settings()
        self.image_generator.settings = current_settings
        self.video_processor.settings = current_settings
        self.style_parser.settings = current_settings  # If using styled text

    @staticmethod
    def is_dark_color(hex_color):
        """Determine if a color is dark using luminance calculation"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return False  # Default to light color if invalid
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.5

    def update_color_labels(self):
        """Update both color labels' appearance"""
        # Text color label
        text_color = self.text_color_var.get()
        self.text_color_label.config(
            bg=text_color,
            fg='white' if self.is_dark_color(text_color) else 'black'  # Changed here
        )

        # Background color label
        bg_color = self.bg_color_var.get()
        self.bg_color_label.config(
            bg=bg_color,
            fg='white' if self.is_dark_color(bg_color) else 'black'  # Changed here
        )

    def choose_text_color(self):
        color = colorchooser.askcolor(title="Choose Text Color")
        if color[1]:
            self.text_color_var.set(color[1])
            self.update_color_labels()
            logging.debug(f"Text color updated to: {color[1]}")

    def choose_bg_color(self):
        color = colorchooser.askcolor(title="Choose Background Color")
        if color[1]:
            self.bg_color_var.set(color[1])
            self.update_color_labels()
            logging.debug(f"Background color updated to: {color[1]}")

    def choose_font(self):
        file_path = filedialog.askopenfilename(filetypes=[("Font Files", "*.ttf *.otf")])
        if file_path:
            try:
                ImageFont.truetype(file_path, 10)  # Quick validation
                self.custom_font_path = file_path
            except IOError:
                messagebox.showerror("Invalid Font", "The selected file is not a valid font.")

    def choose_background_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.png *.jpeg")])
        if file_path:
            self.background_image_path = file_path
            logging.info(f"Selected background image: {file_path}")

    def choose_background_music(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav")])
        if file_path:
            self.background_music_path = file_path
            logging.info(f"Selected background music: {file_path}")

    def choose_srt_file(self):
        """Handle SRT file selection"""
        file_path = filedialog.askopenfilename(
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )
        if file_path:
            self.srt_path = file_path
            self.srt_label.config(text=os.path.basename(file_path))
            logging.info(f"Selected SRT file: {file_path}")

    def show_preview(self):
        """Show style preview with thread safety and loading indicator"""
        self.update_settings()
        current_settings = self.get_current_settings()
        self.image_generator.settings = current_settings  # Update generator settings
        

        # Close existing preview
        if self.preview_window:
            self.preview_window.destroy()

        # Create preview window
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("Text Style Preview")
        self.preview_window.protocol("WM_DELETE_WINDOW", self.close_preview)

        # Add loading container
        loading_frame = ttk.Frame(self.preview_window)
        loading_frame.pack(pady=20)

        ttk.Label(loading_frame,
                 text="Generating preview...",
                 font=('Helvetica', 10)).pack(pady=5)
        self.loading_spinner = ttk.Progressbar(loading_frame,
                                              mode='indeterminate',
                                              length=200)
        self.loading_spinner.pack(pady=10)
        self.loading_spinner.start()

        # Start preview generation in thread
        threading.Thread(
            target=self._generate_preview_content,
            args=("Preview Text\n<font size='18'>Styled Text</font>\n<i>Italic</i>",),
            daemon=True
        ).start()

    def _generate_preview_content(self, preview_text):
        """Background thread work for preview generation"""
        try:
            # Generate the image in background thread
            img = self.image_generator.generate_preview(preview_text)

            # Schedule GUI update in main thread
            self.root.after(0, self._update_preview_display, img)
        except Exception as e:
            error_msg = f"Preview error: {str(e)}"
            logging.error(error_msg)
            self.root.after(0, self._show_preview_error, error_msg)

    def _update_preview_display(self, img):
        """Update preview window with generated image"""
        if not self.preview_window.winfo_exists():
            return  # Window closed before we finished

        # Clear loading elements
        for widget in self.preview_window.winfo_children():
            widget.destroy()

        # Display generated image
        photo = ImageTk.PhotoImage(img)
        label = ttk.Label(self.preview_window, image=photo)
        label.image = photo  # Keep reference
        label.pack(padx=10, pady=10)

        # Add close button
        ttk.Button(self.preview_window,
                  text="Close Preview",
                  command=self.close_preview).pack(pady=5)

    def _show_preview_error(self, message):
        """Show error message in preview window"""
        if not self.preview_window.winfo_exists():
            return

        for widget in self.preview_window.winfo_children():
            widget.destroy()

        ttk.Label(self.preview_window,
                 text="Preview Generation Failed",
                 style='Header.TLabel').pack(pady=5)
        ttk.Label(self.preview_window,
                 text=message,
                 foreground='red').pack(pady=5)
        ttk.Button(self.preview_window,
                  text="Close",
                  command=self.close_preview).pack(pady=5)

    def close_preview(self):
        """Safely close preview window"""
        if self.preview_window:
            self.preview_window.destroy()
        self.preview_window = None

    def start_generation(self):
        self.update_settings()
        current_settings = self.get_current_settings()
        
        # Update processors with latest settings
        self.image_generator.settings = current_settings
        self.video_processor.settings = current_settings

        #should change exec external script here
        if not self.running:
            if not self.srt_path:
                messagebox.showerror("Error", "Please select an SRT file first")
                return

            try:
                self.running = True
                threading.Thread(
                    target=self.prompt_for_output_and_generate,
                    daemon=True
                ).start()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid integer")
                self.running = False

    def generate_video(self, output_path: str, srt_path: str) -> None:
        """Process subtitle entries into a video with audio"""
        try:
            self.update_settings()
            self.update_status("Initializing video generation...", 0)

            adjusted_srt = srt_path
            if not self.temp_manager.verify_file(adjusted_srt):
                raise FileNotFoundError("Adjusted SRT file not found or empty")

            # 2. Parse subtitle entries with time validation
            self.update_status("Parsing subtitles...", 5)
            
            entries = self.srt_parser.parse(adjusted_srt)
            
            if not entries:
                raise ValueError("No valid subtitle entries found in adjusted SRT file")
            
            # Validate entries for missing 'start_time' or 'end_time'
            for i, entry in enumerate(entries):
                if 'start_time' not in entry or 'end_time' not in entry:
                    raise ValueError(f"Entry {i + 1} is missing 'start_time' or 'end_time'")

            # 3. Generate subtitle images with quality checks
            self.update_status("Generating subtitle images...", 20)
            images = self.image_generator.generate_images(entries)

            
            if len(images) != len(entries):
                raise RuntimeError(
                    f"Image generation mismatch: {len(entries)} entries vs {len(images)} images"
                )

            # 4. Validate sample images
            sample_check = self.validate_images([img['path'] for img in images[:3]])
            if not sample_check["success"]:
                raise RuntimeError(f"Image validation failed: {sample_check['errors'][0]}")

            # 5. Process in batches with progress tracking
            self.update_status("Processing video batches...", 30)
            batch_size = self.settings.get('batch_size', 50)
            image_paths = [img['path'] for img in images]
            batches = [images[i:i+batch_size] for i in range(0, len(images), batch_size)]

            segments = []
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_to_batch = {
                    executor.submit(
                        self.video_processor.process_batch,  # Method reference
                        batch,            # 1st argument (List[Dict])
                        idx              # 2nd argument (int)
                    ): idx for idx, batch in enumerate(batches)
                }

                self.futures = list(future_to_batch.keys())

                for future in concurrent.futures.as_completed(future_to_batch):
                    try:
                        segment_path = future.result()
                        if segment_path and os.path.exists(segment_path):
                            segments.append(segment_path)
                            progress = 30 + 60 * len(segments)//len(batches)
                            self.update_status(f"Processed {len(segments)}/{len(batches)} batches", progress)
                    except Exception as e:
                        logging.error(f"Batch processing failed: {str(e)}")
                        self._save_batch_debug_info(batches[future_to_batch[future]], future_to_batch[future])

            # 6. Combine video segments
            if not segments:
                raise RuntimeError("No valid video segments created")

            self.update_status("Finalizing video...", 90)
            final_video = self.video_processor.combine_segments(
                segments,
                output_path,
                self.settings.get('background_music')
            )
            
            # 8. Cleanup and completion
            self.safe_cleanup(segments)
            
            self.update_status("Video creation complete!", 100)
            messagebox.showinfo("Success", f"Video saved to:\n{output_path}")

        except Exception as e:
            error_msg = f"Video generation failed: {str(e)}"
            logging.error(error_msg, exc_info=True)
            self.root.after(0, messagebox.showerror, "Processing Error", error_msg)
        finally:
            self.running = False
            self.futures = []

    def _save_batch_debug_info(self, batch: List[str], batch_idx: int) -> None:
        """Save debug information for failed batches"""
        debug_dir = os.path.join(self.temp_manager.root_dir, "failed_batches")
        os.makedirs(debug_dir, exist_ok=True)

        try:
            # Save batch info
            with open(os.path.join(debug_dir, f"batch_{batch_idx}_files.txt"), "w") as f:
                f.write("\n".join(batch))

            # Save first image from batch
            if batch:
                img = Image.open(batch[0])
                img.save(os.path.join(debug_dir, f"batch_{batch_idx}_sample.jpg"))

        except Exception as e:
            logging.error(f"Failed to save debug info: {str(e)}")

    def validate_images(self, paths: List[str]) -> dict:
        """Validate image files for corruption and dimensions"""
        results = {
            'success': True,
            'errors': [],
            'checked': len(paths)
        }

        for path in paths:
            try:
                if not os.path.exists(path):
                    results['errors'].append(f"Missing file: {path}")
                    continue

                with Image.open(path) as img:
                    img.verify()
                    if img.size != self.expected_dimensions:
                        results['errors'].append(
                            f"Dimension mismatch in {os.path.basename(path)}: "
                            f"Expected {self.expected_dimensions}, Got {img.size}"
                        )

            except Exception as e:
                results['errors'].append(f"Invalid image {os.path.basename(path)}: {str(e)}")

        results['success'] = len(results['errors']) == 0
        return results

    def safe_cleanup(self, segments):
        """Clean temporary files with validation"""
        try:
            # Clean temp SRT
            if os.path.exists("temp.srt"):
                os.remove("temp.srt")

            # Clean video segments
            for seg in segments:
                if os.path.exists(seg):
                    os.remove(seg)

            # Clean temp manager files
            self.temp_manager.cleanup()

        except Exception as cleanup_error:
            logging.warning(f"Cleanup failed: {str(cleanup_error)}")

    def run_external_script(self, delay: int):
        try:
            self.update_status("Adjusting SRT timings...", 0)
            script_path = os.path.join(os.path.dirname(__file__), "processors", "editSrtFileTime.py")

            # Create temp directory if not exists
            self.temp_manager._init_dirs()

            # Use proper temp file path
            adjusted_srt = os.path.join(self.temp_manager.root_dir, "temp.srt")
            command = [
                "python", script_path,
                self.srt_path,
                str(delay),
                adjusted_srt  # Use full temp path instead of "temp.srt"
            ]

            process = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                cwd=self.temp_manager.root_dir  # Run in temp directory
            )

            # Verify output file creation
            if not os.path.exists(adjusted_srt):
                raise RuntimeError("SRT adjustment failed to create output file")

            #self.root.after(0, self.prompt_for_output_and_generate)
            return adjusted_srt
        
        except subprocess.CalledProcessError as e:
            error_msg = f"SRT adjustment failed:\n{e.stderr}"
            logging.error(f"STDOUT: {e.stdout}\nSTDERR: {e.stderr}")

        except Exception as e:
            error_msg = f"SRT adjustment error: {str(e)}"
            logging.error(error_msg, exc_info=True)

        finally:
            self.running = False

    def prompt_for_output_and_generate(self):
        """Main thread: Get output path and start processing"""
        output_path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )

        #delay = int(self.user_value_var.get())
        delay = int(self.num_input.get())
        adjusted_srt = self.run_external_script(delay)
        #self.srt_path = adjusted_srt

        if output_path:
            threading.Thread(
                target=self.generate_video,
                args=(output_path, adjusted_srt,),
                daemon=True
            ).start()
        else:
            self.running = False

    def update_status(self, message: str, progress: int):
        self.root.after(0, self.progress_label.config, {'text': message})
        self.root.after(0, self.progress.configure, {'value': progress})
        self.root.update_idletasks()

    def cancel_generation(self):
        if self.running:
            self.running = False
            # Cancel pending futures
            for future in self.futures:
                future.cancel()
            self.temp_manager.cleanup()
            self.update_status("Cancelled", 0)
            messagebox.showinfo("Info", "Generation cancelled")

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='srt_converter.log'
        )

    def start_audio_generation(self):
        """Start audio generation only"""
        if not self.srt_path:
            messagebox.showerror("Error", "Please select an SRT file first")
            return

        try:
            self.running = True
            threading.Thread(
                target=self.generate_audio_only,
                daemon=True
            ).start()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.running = False

    def generate_audio_only(self):
        """Generate audio only"""
        try:
            self.update_status("Generating audio...", 0)
            output_path = filedialog.asksaveasfilename(
                defaultextension=".wav",
                filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
            )
            if output_path:
                self.generate_audio(output_path)
                self.update_status("Audio generated successfully!", 100)
                messagebox.showinfo("Success", f"Audio saved at:\n{output_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.running = False


    def generate_audio(self, output_path):
        """Generate audio (ensure this is properly synchronous)"""
        if not self.current_tts:
            raise RuntimeError("No TTS model initialized")

        #output_path = os.path.join(self.temp_manager.root_dir, output_path)
        
        # Clear previous audio path
        #self.generated_audio_path = None
        
        try:
            # Perform actual audio generation
            self.current_tts.convert_to_audio(
                sub_data=self.current_tts.subtitle(self.srt_path),
                language=self.lang_combo.get(),
                speaker_wav=self.speaker_ref_path,
                output_path=output_path
            )
            
            # Verify generation succeeded
            if not os.path.exists(output_path):
                raise RuntimeError("TTS failed to generate audio file")
                
            # Update path only after successful generation
            self.generated_audio_path = output_path
            self.settings['background_music'] = output_path
            #self.root.after(0, messagebox.showinfo, "Audio Generation complete", str(output_path))
        except Exception as e:
            logging.error(f"Audio generation failed: {str(e)}")
            self.root.after(0, messagebox.showerror, "Audio Generation Error", str(e))
            raise   


    def check_tts_installation(self):
        """Verify TTS is properly installed and has models"""
        try:
            from TTS.api import TTS
            temp_tts = TTS()
            if not temp_tts.list_models():
                messagebox.showwarning(
                    "Missing Models",
                    "No TTS models installed!\n"
                    "Please install at least one model to continue.\n"
                    "You can install models via command line:\n"
                    "tts --model_name [model_name] --model_path [path/to/model]"
                )
        except ImportError:
            messagebox.showerror(
                "Missing Dependency",
                "Coqui TTS not installed!\n"
                "Install with: pip install TTS"
            )
            self.root.destroy()

    def load_tts_models(self):
        """Load available TTS models into combobox"""
        if hasattr(self, 'model_combo'):  # Check if widget exists
            threading.Thread(target=self._populate_models, daemon=True).start()

    def _populate_models(self):
        """Thread-safe model loading"""
        try:
            model_names = SubToAudio().coqui_model()
                 
            valid_models = [m for m in model_names if SubToAudio()._model_exists(m)]
            
            if self.root.winfo_exists():
                self.root.after(0, self._update_model_dropdown, valid_models)
                
        except Exception as e:
            error_msg = f"Model loading failed: {str(e)}"
            logging.error(error_msg)
            if self.root.winfo_exists():
                self.root.after(0, lambda: messagebox.showerror("Model Error", error_msg))

    def _update_model_dropdown(self, models):
        """Update model dropdown safely"""
        if not self.root.winfo_exists():
            return
        
        if models:
            self.model_combo['values'] = models
            self.model_var.set(models[0])
        else:
            self.model_combo.set("No models available")

    def _on_model_selected(self, event=None):
        """Handle model selection and populate languages"""
        model = self.model_var.get()
        if not model:
            return

        try:
            # Corrected variable name from current_ts to current_tts
            self.current_tts = SubToAudio(model_name=model)
            langs = self.current_tts.languages()
            
            self.lang_combo['values'] = langs
            self.lang_combo.set(langs[0] if langs else "fr")
            
        except Exception as e:
            messagebox.showerror("Model Error", f"Failed to initialize model: {str(e)}")
            print(f"Error loading model: {str(e)}")  # Debug log

    def languages(self) -> list:
        """Get supported languages for the current model"""
        try:
            if hasattr(self, 'model_name') and "xtts" in self.model_name.lower():
                return ["en", "es", "fr", "de", "it", "pt", "pl", 
                       "tr", "ru", "nl", "cs", "ar", "zh", "ja"]
            return self.apitts.languages or ["fr"]
        except AttributeError:
            return ["fr"]  # Default

    def _show_loading_models(self):
        self.model_combo['values'] = ["Loading models..."]
        self.model_combo['state'] = 'disabled'

    def _show_model_error(self, message):
        self.model_combo['values'] = ["Error - Click for details"]
        self.model_combo['state'] = 'readonly'
        self.model_combo.bind('<<ComboboxSelected>>', 
                            lambda e: messagebox.showerror("Model Error", message))      

    def choose_reference_audio(self):
        """Handle reference audio file selection"""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Audio Files", "*.wav *.mp3 *.ogg *.flac"),
                ("All Files", "*.*")
            ]
        )
        
        if file_path:
            # Validate audio file
            try:
                AudioSegment.from_file(file_path)
                self.speaker_ref_path = file_path
                self.ref_audio_label.config(text=os.path.basename(file_path))
            except Exception as e:
                messagebox.showerror("Invalid Audio", f"Could not read audio file:\n{str(e)}")
                self.speaker_ref_path = None
                self.ref_audio_label.config(text="Invalid audio file")

    def clear_reference_audio(self):
        """Clear selected reference audio"""
        self.speaker_ref_path = None
        self.ref_audio_label.config(text="No audio selected")

    def create_tts_controls(self):
        """Create TTS widgets with audio file selection"""
        tts_frame = ttk.LabelFrame(self.settings_frame, text="XTTS v2 Settings", padding=10)
        tts_frame.pack(fill=tk.X, pady=5)

        # Reference audio selection
        ttk.Button(
            tts_frame,
            text="Reference Speaker Audio",
            command=self.choose_speaker_ref
        ).pack(side=tk.LEFT, padx=5)
        
        self.speaker_ref_label = ttk.Label(tts_frame, text="No audio selected")
        self.speaker_ref_label.pack(side=tk.LEFT, padx=5)
        
        # Language selection
        self.xtts_lang_combo = ttk.Combobox(
            tts_frame,
            values=["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja"],
            state='readonly',
            width=5
        )
        self.xtts_lang_combo.pack(side=tk.LEFT, padx=5)
        self.xtts_lang_combo.set("fr")

    def choose_speaker_ref(self):
        """Select reference speaker audio file"""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Audio Files", "*.wav *.mp3 *.flac"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            # Validate audio file
            try:
                AudioSegment.from_file(file_path)
                self.speaker_ref_path = file_path
                self.speaker_ref_label.config(text=os.path.basename(file_path))
            except Exception as e:
                messagebox.showerror("Invalid Audio", f"Could not read audio file:\n{str(e)}")
                self.speaker_ref_path = None
                self.speaker_ref_label.config(text="Invalid file")