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
import concurrent.futures as futures
from concurrent.futures import ThreadPoolExecutor
import os
import json 

class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Caption Creator")
        self.root.geometry("1000x750")
        self.initialize_app()
        
    def initialize_app(self):
        """Initialize/Restart application state"""
        # Clear existing widgets if any
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Reset all variables
        self.text_color_var = tk.StringVar(value="#FFFFFF")
        self.bg_color_var = tk.StringVar(value="#000000")
        self.font_size_var = tk.IntVar(value=24)
        self.border_var = tk.BooleanVar(value=True)
        self.shadow_var = tk.BooleanVar(value=False)
        self.background_image_path = None
        self.background_music_path = None
        self.custom_font_path = None
        self.srt_path = None
        self.user_value_var = tk.StringVar()
        self.user_value_var = tk.StringVar(value="-400")

        # Reset processing state
        self.running = False
        self.futures = []
        
        # Reinitialize components
        self.temp_manager = TempFileManager(log_file="srt_converter.log")
        self.srt_parser = SRTParser()
        self.style_parser = StyleParser()
        self.image_generator = ImageGenerator(
            self.temp_manager,
            self.style_parser,
            self.get_current_settings()
        )
        self.video_processor = VideoProcessor(
            self.temp_manager,
            self.get_current_settings()
        )

        # Rebuild UI
        self.setup_styles()
        self.create_widgets()
        self.setup_logging()
        
        self.root.after(100, self.update_color_labels)

    def get_current_settings(self):
        """Return current settings dictionary"""
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
            'batch_size': 50
        }

    def reset_application(self):
        """Full application reset handler"""
        if messagebox.askyesno(
            "Confirm Reset",
            "This will reset all settings and clear temporary files.\nContinue?"
        ):
            # Cancel any ongoing operations
            self.cancel_generation()
            
            # Clean up resources
            self.temp_manager.cleanup()
            
            # Reinitialize application
            self.initialize_app()
            
            messagebox.showinfo("Reset Complete", "Application has been reset to default state")

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TButton', font=('Helvetica', 10), padding=6)
        self.style.configure('TLabel', font=('Helvetica', 9))
        self.style.configure('Header.TLabel', font=('Helvetica', 11, 'bold'))
        self.style.configure('Progressbar', thickness=20)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Settings Panel
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)

        # Add input section
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=10)
        
        # Integer input box for Edit SRT file delay
        ttk.Label(input_frame, text="Edit SRT file delay:").pack(side=tk.LEFT)
        self.num_input = ttk.Entry(
            input_frame,
            textvariable=self.user_value_var,
            validate='key',
            validatecommand=(self.root.register(self.validate_int), '%P')
        )
        self.num_input.pack(side=tk.LEFT, padx=5)

        # Color Controls
        ttk.Button(settings_frame, text="Text Color", 
                 command=self.choose_text_color).grid(row=0, column=0, padx=5)
        
        self.text_color_label = tk.Label(
            settings_frame, 
            textvariable=self.text_color_var,
            relief='sunken',
            width=15,
            font=('Helvetica', 9)
        )
        self.text_color_label.grid(row=0, column=1, padx=5)

        ttk.Button(settings_frame, text="Background Color", 
                 command=self.choose_bg_color).grid(row=1, column=0, padx=5)
        
        self.bg_color_label = tk.Label(
            settings_frame, 
            textvariable=self.bg_color_var,
            relief='sunken',
            width=15,
            font=('Helvetica', 9)
        )
        self.bg_color_label.grid(row=1, column=1, padx=5)

        # Font Controls
        ttk.Label(settings_frame, text="Text Size:").grid(row=2, column=0)
        self.font_size_slider = ttk.Scale(settings_frame, from_=10, to=100, 
                                       variable=self.font_size_var)
        self.font_size_slider.grid(row=2, column=1)
        self.font_size_slider.set(24)

        ttk.Button(settings_frame, text="Select Font", 
                 command=self.choose_font).grid(row=3, column=0)

        # Effects Checkboxes
        ttk.Checkbutton(settings_frame, text="Text Border", 
                      variable=self.border_var).grid(row=4, column=0)
        ttk.Checkbutton(settings_frame, text="Text Shadow", 
                      variable=self.shadow_var).grid(row=4, column=1)

        # Media Controls
        ttk.Button(settings_frame, text="Background Image", 
                 command=self.choose_background_image).grid(row=5, column=0)
        ttk.Button(settings_frame, text="Background Music", 
                 command=self.choose_background_music).grid(row=5, column=1)

        # Preview Button
        ttk.Button(settings_frame, text="Preview Style", 
                 command=self.show_preview).grid(row=6, columnspan=2, pady=5)

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
        
        #Reset buton
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

        self.update_color_labels()

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
        """Ensure settings are properly separated"""
        self.settings.update({
            'text_color': self.text_color_var.get(),
            'bg_color': self.bg_color_var.get(),  # Separate from text color
            'font_size': int(self.font_size_var.get()),
            'text_border': self.border_var.get(),
            'text_shadow': self.shadow_var.get(),
            'background_image': self.background_image_path,
            'background_music': self.background_music_path,
            'custom_font': self.custom_font_path
        })

        #logging.debug(f"Text Color: {self.settings['text_color']}")
        #logging.debug(f"BG Color: {self.settings['bg_color']}")

        # Convert settings to JSON-safe format
        loggable_settings = self.settings.copy()
        loggable_settings['custom_font'] = str(loggable_settings['custom_font'])
        loggable_settings['background_image'] = str(loggable_settings['background_image'])
        
        logging.debug(f"Current Settings:\n{json.dumps(loggable_settings, indent=2)}")
        self.image_generator.settings = self.settings.copy()
        self.video_processor.settings = self.settings.copy()

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
        #should change exec external script here
        if not self.running:
            if not self.srt_path:
                messagebox.showerror("Error", "Please select an SRT file first")
                return
                
            self.running = True
            self.update_settings()
            threading.Thread(target=self.generate_video, daemon=True).start()

    def generate_video(self):
        try:
            output_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
            )
            
            if not output_path:
                self.running = False
                return
            #add logic of changing srt file name
            try:
                # Get and validate input value
                user_input = self.user_value_var.get()
                num_iterations = int(user_input) if user_input else -400  # Default value
                
                self.running = True
                threading.Thread(
                    target=self.run_external_script,
                    args=(num_iterations,),
                    daemon=True
                ).start()
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid integer")
                self.running = False

            self.update_status("Parsing SRT...", 0)
            entries = self.srt_parser.parse(self.srt_path)
            
            if not entries:
                messagebox.showerror("Error", "Invalid SRT file")
                self.running = False
                return

            self.update_status("Generating images...", 25)
            images = self.image_generator.generate_images(entries)
            
            if len(images) != len(entries):
                messagebox.showerror("Error", f"Failed to generate {len(entries)-len(images)} images")
                return

            self.update_status("Processing video...", 50)
            if output_path:
                batches = [images[i:i+self.settings['batch_size']] 
                          for i in range(0, len(images), self.settings['batch_size'])]
                
                with ThreadPoolExecutor() as executor:
                    self.futures = [executor.submit(self.video_processor.process_batch, batch, idx)
                             for idx, batch in enumerate(batches)]
                    
                    segments = []
                    for future in futures.as_completed(self.futures):
                        if not self.running:
                            break
                        result = future.result()
                        if result:
                            segments.append(result)
                
                if not segments:
                    messagebox.showerror("Error", "No valid video segments created")
                    return
                
                self.update_status("Combining segments...", 75)
                if self.video_processor.combine_segments(segments, output_path, self.settings['background_music']):
                    self.update_status("Complete!", 100)
                    #maybe add logic to delete temp srt file that was edited
                    messagebox.showinfo("Success", f"Video saved to:\n{output_path}")
                else:
                    messagebox.showerror("Error", "Failed to combine segments")
                
        except Exception as e:
            logging.error(f"Generation failed: {str(e)}")
            messagebox.showerror("Error", str(e))
        finally:
            self.futures = []
            self.running = False
            self.temp_manager.cleanup()

    def run_external_script(self, num_iterations: int):
        """Execute external script with the integer parameter"""
        try:
            self.update_status(f"Running script with {num_iterations} iterations...", 0)
            
            # Build command (modify for your script path)
            script_path = os.path.join(os.path.dirname(__file__), "processors/editSrtFileTime.py")
            command = f"python {script_path} {num_iterations}"
            
            # Run with progress tracking
            process = subprocess.Popen(
                command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Read output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.root.after(0, self.parse_script_output, output.strip())
            
            if process.returncode != 0:
                raise RuntimeError(f"Script failed with code {process.returncode}")
            
            self.update_status("Script completed successfully", 100)
        except Exception as e:
            self.root.after(0, messagebox.showerror, "Script Error", str(e))
        finally:
            self.running = False

    def parse_script_output(self, output: str):
        """Handle script output updates"""
        # Example progress parsing - modify according to your script's output
        if "Progress:" in output:
            try:
                progress = int(output.split(":")[1].strip().replace('%', ''))
                self.update_status(f"Processing... {progress}%", progress)
            except ValueError:
                pass
        logging.info(f"Script Output: {output}")        

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