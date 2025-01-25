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

class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Caption Creator")
        self.root.geometry("1000x750")
        self.preview_window = None

        # Initialize app components in correct order
        self.initialize_app()  # 1. Variables and core components
        self.setup_styles()    # 2. UI styling
        self.create_widgets()  # 3. Create GUI elements
        self.setup_logging()   # 4. Configure logging

    def get_current_settings(self) -> dict:
        """Safely get current settings with null checks"""
        return {
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
            'user_value': self._safe_int_get(self.user_value_var, 500)
        }

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
        self.user_value_var = tk.StringVar(value="500")
        self.expected_dimensions = (1280, 720)

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
                          variable=self.border_var).grid(row=8, column=5, padx=5)
            ttk.Checkbutton(settings_frame, text="Text Shadow",
                          variable=self.shadow_var).grid(row=9, column=5, padx=5)

            # Media Controls
            ttk.Button(settings_frame, text="Background Image",
                     command=self.choose_background_image).grid(row=6, column=5, padx=5)

            ttk.Button(settings_frame, text="Background Music",
                     command=self.choose_background_music).grid(row=9, column=0, padx=5)

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
                     command=self.choose_srt_file).grid(row=7, column=0, pady=5)
            self.srt_label = ttk.Label(settings_frame, text="No SRT file selected")
            self.srt_label.grid(row=7, column=1, padx=5)

            #self.num_input.delete(0, tk.END)
            #self.num_input.insert(0, "500")
            
            # Reset color labels
            self.text_color_label.config(bg="#FFFFFF", fg="black")
            self.bg_color_label.config(bg="#000000", fg="white")
            
            # Reset checkboxes
            self.border_var.set(True)
            self.shadow_var.set(False)

            self.update_color_labels()

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
                delay = int(self.user_value_var.get())
                self.running = True
                threading.Thread(
                    target=self.run_external_script,
                    args=(delay,),
                    daemon=True
                ).start()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid integer")
                self.running = False

    def verify_temp_files(image_dicts: List[Dict]):
        """Emergency file system verification"""
        existing = 0
        missing = 0
        invalid = 0

        for img in image_dicts[:100]:  # Check first 100 files
            path = img.get('path', '')
            if not os.path.exists(path):
                missing += 1
                continue
            try:
                with Image.open(path) as im:
                    im.verify()
                existing +=1
            except:
                invalid +=1

        logging.critical(
            f"File System Check:\n"
            f"Existing: {existing}\n"
            f"Missing: {missing}\n"
            f"Corrupted: {invalid}"
        )

    def generate_video(self, output_path: str) -> None:
        """Process subtitle entries into a video with audio"""
        try:
            self.update_settings()
            self.update_status("Initializing video generation...", 0)

            if not self.temp_manager.verify_file("temp.srt"):
                raise FileNotFoundError("Adjusted SRT file not found or empty")

            adjusted_srt = os.path.join(self.temp_manager.root_dir, "temp.srt")

            # 2. Parse subtitle entries with time validation
            self.update_status("Parsing subtitles...", 5)
            entries = self.srt_parser.parse("video_gen_temp/temp.srt")
            if not entries:
                raise ValueError("No valid subtitle entries found in adjusted SRT file")

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

    def _process_images_to_video(self, images: List[Dict], output_path: str) -> bool:
        """Core video processing with validation"""
        try:
            # Validate images before processing
            if not all(isinstance(img, dict) for img in images):
                invalid = [img for img in images if not isinstance(img, dict)]
                logging.error(f"Found {len(invalid)} invalid image entries")
                return False

            return self.video_processor.process(images, output_path)
        except Exception as e:
            logging.error(f"Video processing error: {str(e)}")
            return False

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

            self.root.after(0, self.prompt_for_output_and_generate)

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
        if output_path:
            threading.Thread(
                target=self.generate_video,
                args=(output_path,),
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
