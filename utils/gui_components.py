# Standard library imports
import os
import sys
import logging
import threading
import subprocess
from typing import List

# Third-party imports
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageFont, ImageDraw
import webbrowser
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

# Local application imports
from processors.sub2audio import SubToAudio
from processors.image_generator import ImageGenerator
from processors.srt_parser import SRTParser
from processors.video_processor import VideoProcessor
from utils.style_parser import StyleParser
from utils.helpers import TempFileManager

class GUIComponents:
    def __init__(self, root, app):
        """
        Initialize the GUI components for Video Caption Creator.

        Args:
            root: The root Tkinter window.
            app: The main application instance.
        """
        self.root = root
        self.app = app
        self.root.title("Video Caption Creator")
        self.root.geometry("1000x850")
        
        # Setup logging first
        self.setup_logging()
        
        # Initialize the application state
        self.initialize_app()
        
        # Setup UI styles
        self.setup_styles()
        
        # Create widgets
        self.create_widgets()
        
        # Load TTS models after UI is ready
        self.root.after(100, self.load_tts_models)
        
        # Update settings to ensure consistency
        self.update_settings()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='gui_components.log'
        )

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
        self.generated_audio_path = None
    
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
        self.image_generator = ImageGenerator(
            self.temp_manager, 
            self.style_parser,
            {
            'text_color': '#FFFFFF',
            'bg_color': '#000000', 
            'font_size': 24,
            'text_border': True,
            'text_shadow': False,
            'background_image': None,
            'custom_font': None,
            'margin': 20,
            'expected_dimensions': self.expected_dimensions
            }
        )

        self.video_processor = VideoProcessor(
            self.temp_manager,
            {
            'batch_size': 50,
            'background_music': None,
            'expected_dimensions': self.expected_dimensions,
            'speed_factor': 1.0
            }
        )
        # 4. Get initial settings from variables
        initial_settings = self.get_current_settings()
        # Load or create initial settings
        self.settings = {
            'batch_size': 50,
            'text_color': '#FFFFFF',
            'bg_color': '#000000',
            'font_size': 24,
            'text_border': True,
            'text_shadow': False,
            'background_image': None,
            'background_music': None,
            'custom_font': None,
            'speed_factor': 1.0,
            'margin': 20,
            'tts_model': None,
            'tts_language': 'fr',
            'expected_dimensions': self.expected_dimensions,
            'user_value': 0
        }

        # Apply settings to variables
        self.text_color_var.set(self.settings['text_color'])
        self.bg_color_var.set(self.settings['bg_color']) 
        self.font_size_var.set(self.settings['font_size'])
        self.border_var.set(self.settings['text_border'])
        self.shadow_var.set(self.settings['text_shadow'])
        self.language_var.set(self.settings['tts_language'])
        self.user_value_var.set(str(self.settings['user_value']))

        # Setup style
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors
        style.configure('TFrame', background='#F0F0F0')
        style.configure('TButton',
            background='#4A90E2',
            foreground='black', 
            padding=5,
            font=('Helvetica', 10))
        style.configure('TLabel', 
            background='#F0F0F0',
            font=('Helvetica', 10))
        style.configure('Header.TLabel',
            background='#4A90E2',
            foreground='white',
            font=('Helvetica', 12, 'bold'))
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

    def _safe_int_get(self, var: tk.StringVar, default: int) -> int:
        """Safely get integer value from StringVar"""
        try:
            return int(var.get())
        except (ValueError, AttributeError):
            return default

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

            # Add a link to the GitHub repository
            link_label = tk.Label(self.root, text="Follow Us on GuitHub", fg="blue", cursor="hand2")
            link_label.pack(anchor="ne", pady=(5, 0))
            link_label.bind("<Button-1>", self.open_link)

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
            # Auto-select XTTS model
            if 'xtts' in SubToAudio().coqui_model():
                self.model_var.set('xtts')
                self.language_var.set('fr')  # Default to French
            # Reset color labels
            self.text_color_label.config(bg="#FFFFFF", fg="black")
            self.bg_color_label.config(bg="#000000", fg="white")
            # Set initial model if available
            try:
                if 'xtts' in SubToAudio().coqui_model():
                    self.model_var.set('xtts')
            except:
                pass  # Fallback to default model selection
            # Reset checkboxes
            self.border_var.set(True)
            self.shadow_var.set(False)
            # Auto-load TTS models at startup
            self.root.after(100, self.load_tts_models)  # Small delay to ensure widgets are ready

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

    def choose_text_color(self):
        color = colorchooser.askcolor(title="Choose Text Color")
        if color[1]:
            self.text_color_var.set(color[1])
            self.update_color_labels()
            logging.debug(f"Text color updated to: {color[1]}")

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

    def choose_bg_color(self):
        color_code = colorchooser.askcolor(title="Choose Background Color")[1]
        if color_code:
            self.bg_color_var.set(color_code)

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

    def choose_reference_audio(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3;*.wav")])
        if file_path:
            self.speaker_ref_path = file_path
            self.ref_audio_label.config(text=os.path.basename(file_path))

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
    
    def show_about(self):
        messagebox.showinfo("About", "Video Caption Creator\nVersion 1.0.3\nDeveloped by Wael Sahli")

    def open_link(self, event):
        webbrowser.open("https://github.com/overcrash66/")

    def show_preview(self):
        """
        Show style preview with thread safety and loading indicator.
        """
        current_settings = self.get_current_settings()
        self.image_generator.settings = current_settings  # Update generator settings
        
        # Close existing preview
        if hasattr(self, 'preview_window') and self.preview_window:
            self.preview_window.destroy()

        # Create new preview window
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("Text Style Preview")
        self.preview_window.geometry("800x600")
        self.preview_window.resizable(False, False)

        # Add loading container
        loading_frame = ttk.Frame(self.preview_window)
        loading_frame.pack(pady=20)

        ttk.Label(loading_frame, text="Generating preview...", font=('Helvetica', 10)).pack(pady=5)
        self.loading_spinner = ttk.Progressbar(loading_frame, mode='indeterminate', length=200)
        self.loading_spinner.pack(pady=10)
        self.loading_spinner.start()

        # Start preview generation in thread
        threading.Thread(
            target=self._generate_preview_content,
            args=("Preview Text\n<font size='18'>Styled Text</font>\n<i>Italic</i>",),
            daemon=True
        ).start()

    def _generate_preview_content(self, sample_text: str):
        """
        Generate preview content with the current style settings.
        """
        try:
            preview_image = self.image_generator.generate_image(sample_text)
            if preview_image:
                # Convert PIL image to PhotoImage
                photo = ImageTk.PhotoImage(preview_image)
                self.root.after(0, self._update_preview_window, photo)
        except Exception as e:
            logging.error(f"Preview generation failed: {str(e)}")
            self.root.after(0, self._show_preview_error)

    def _update_preview_window(self, photo):
        """
        Update the preview window with the generated image.
        """
        if self.preview_window:
            self.loading_spinner.stop()
            self.loading_spinner.pack_forget()

            # Create and pack the preview label
            preview_label = ttk.Label(self.preview_window, image=photo)
            preview_label.image = photo  # Keep a reference
            preview_label.pack(padx=10, pady=10)

    def _show_preview_error(self):
        """
        Show error message in preview window.
        """
        if self.preview_window:
            self.loading_spinner.stop()
            self.loading_spinner.pack_forget()
            ttk.Label(self.preview_window, text="Failed to generate preview", foreground="red").pack(pady=20)
            self.preview_window.update_idletasks()
            self.preview_window.after(3000, self.preview_window.destroy)
        # Close preview window after 3 seconds
        if self.preview_window:
            self.preview_window.after(3000, self.preview_window.destroy)
            self.preview_window = None
        else:
            logging.warning("Preview window already closed or not created.")
            self.preview_window = None
            self.preview_window.destroy()

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

    def run_external_script(self, delay: int):
        try:
            # Ensure temp directories are initialized
            self.temp_manager._init_dirs()
            
            # Create temporary output path
            temp_dir = self.temp_manager.temp_dir
            output_path = os.path.join(temp_dir, "adjusted_srt.srt")
            
            # Use direct SRT adjustment instead of external script
            return self.adjust_srt_directly(self.srt_path, delay, output_path)
                
        except Exception as e:
            logging.error(f"Error adjusting SRT: {e}", exc_info=True)
            raise RuntimeError(f"SRT adjustment failed: {str(e)}")
            
    def adjust_srt_directly(self, input_path, delay_ms, output_path):
        """Adjust SRT timecodes directly without calling external script"""
        try:
            # Import re for regex operations
            import re
            import codecs
            
            logging.info(f"Adjusting SRT file: {input_path} with delay {delay_ms}ms")
            
            # Try multiple encodings to handle different file formats
            encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
            content = None
            
            for encoding in encodings:
                try:
                    with codecs.open(input_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    if content and content.strip():
                        logging.info(f"Successfully read SRT file with encoding: {encoding}")
                        break
                except UnicodeDecodeError:
                    continue
            
            # No need to redefine methods here - we'll use the class-level method
            if not content or not content.strip():
                raise RuntimeError(f"SRT file is empty or cannot be decoded: {input_path}")
                
            # Pattern to match timecode lines
            # Format: 00:00:00,000 --> 00:00:00,000
            timecode_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})')
            
            # Normalize line endings to ensure consistent splitting
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            
            # Validate SRT format - try different splitting patterns
            entries = re.split(r'\n\n+', content.strip())
            if len(entries) < 1:
                # Try alternative splitting
                entries = re.split(r'\d+\n\d{2}:\d{2}:\d{2},\d{3}\s*-->', content.strip())
                entries = [e for e in entries if e.strip()]
            
            if len(entries) < 1:
                logging.error(f"Invalid SRT format: no entries found in {input_path}")
                logging.error(f"Content sample: {content[:200]}...")
                raise RuntimeError(f"Invalid SRT format: no entries found in {input_path}")
                
            # Check if first entry has valid format (number, timecode, text)
            first_entry = entries[0].split('\n')
            if len(first_entry) < 2 or not any(timecode_pattern.search(line) for line in first_entry):
                logging.error(f"Invalid SRT format: first entry doesn't match expected format")
                logging.error(f"First entry: {entries[0]}")
                raise RuntimeError(f"Invalid SRT format in {input_path}")
            
            logging.info(f"Found {len(entries)} subtitle entries to adjust")
            
            def adjust_timecode(match):
                # Convert matched groups to integers
                h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
                
                # Convert to milliseconds
                time1_ms = h1 * 3600000 + m1 * 60000 + s1 * 1000 + ms1
                time2_ms = h2 * 3600000 + m2 * 60000 + s2 * 1000 + ms2
                
                # Apply delay
                time1_ms += delay_ms
                time2_ms += delay_ms
                
                # Ensure times are not negative
                time1_ms = max(0, time1_ms)
                time2_ms = max(0, time2_ms)
                
                # Convert back to timecode format
                h1 = time1_ms // 3600000
                m1 = (time1_ms % 3600000) // 60000
                s1 = (time1_ms % 60000) // 1000
                ms1 = time1_ms % 1000
                
                h2 = time2_ms // 3600000
                m2 = (time2_ms % 3600000) // 60000
                s2 = (time2_ms % 60000) // 1000
                ms2 = time2_ms % 1000
                
                # Format back to timecode
                return f"{h1:02d}:{m1:02d}:{s1:02d},{ms1:03d} --> {h2:02d}:{m2:02d}:{s2:02d},{ms2:03d}"
            
            # Adjust the timecodes in the content
            adjusted_content = timecode_pattern.sub(adjust_timecode, content)
            
            # Write to output file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(adjusted_content)
            
            # Verify file was created and has content
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise RuntimeError("Failed to create valid adjusted SRT file")
            
            # Validate the adjusted file
            with open(output_path, 'r', encoding='utf-8') as f:
                check_content = f.read()
                if not timecode_pattern.search(check_content):
                    logging.warning("No timecodes found in adjusted SRT file")
                    # If no timecodes found, use original file as fallback
                    logging.info(f"Using original SRT file as fallback")
                    return input_path
                
                # Verify entries in adjusted file
                adjusted_entries = re.split(r'\r?\n\r?\n', check_content.strip())
                if len(adjusted_entries) < 1:
                    logging.warning("No valid entries in adjusted SRT file, using original")
                    return input_path
                    
                logging.info(f"Adjusted SRT has {len(adjusted_entries)} entries")
            
            logging.info(f"SRT adjustment completed, saved to: {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"Error adjusting SRT directly: {e}", exc_info=True)
            # Fall back to original file if adjustment fails
            logging.info(f"Using original SRT file as fallback due to error")
            return input_path

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

    def _process_video(self):
        """
        Process the video in a separate thread.
        """
        try:
            # Update settings
            self.video_processor.settings = self.get_current_settings()
            
            # Process video
            self.video_processor.process(self.srt_path)
            
            # Show completion message
            self.root.after(0, lambda: self.progress_label.config(text="Video generation complete!"))
            self.root.after(0, lambda: messagebox.showinfo("Success", "Video generation completed successfully!"))
            
        except Exception as e:
            logging.error(f"Video processing error: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Video processing failed: {str(e)}"))

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

    # Method moved to a more comprehensive implementation below
    def generate_audio_only(self):
        """Generate audio only"""
        try:
            # Check prerequisites
            if not self.srt_path:
                messagebox.showerror("Error", "Please select an SRT file first")
                return
    
            if not self.current_tts:
                messagebox.showerror("Error", "Please select a TTS model first")
                return
    
            self.update_status("Generating audio...", 0)
            output_path = filedialog.asksaveasfilename(
                defaultextension=".wav",
                filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
            )
            
            if not output_path:
                self.update_status("Audio generation cancelled", 0)
                return
                
            # Call the audio generation method
            self.generate_audio(output_path)
            self.update_status("Audio generation complete!", 100)
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Audio saved to:\n{output_path}"))
            
        except Exception as e:
            error_message = str(e)  # Capture the error message
            logging.error(f"Audio generation failed: {error_message}", exc_info=True)
            self.update_status(f"Error: {error_message}", 0)
            # Use default argument to properly capture the error message in the lambda
            self.root.after(0, lambda msg=error_message: messagebox.showerror("Error", f"Audio generation failed: {msg}"))
        finally:
            self.running = False
    def generate_audio(self, output_path):
        """Generate audio (ensure this is properly synchronous)"""
        if not self.current_tts:
            raise RuntimeError("No TTS model initialized")
        
        if not self.srt_path or not os.path.exists(self.srt_path):
            raise RuntimeError("Valid SRT file not found")
        
        try:
            # Get language value safely
            language = self.lang_combo.get() if hasattr(self, 'lang_combo') and self.lang_combo else self.language_var.get()
            
            # Prepare conversion parameters
            convert_params = {
                'sub_data': self.current_tts.subtitle(self.srt_path),
                'language': language,
                'output_path': output_path
            }
            
            # Add speaker_wav only if provided
            if self.speaker_ref_path:
                convert_params['speaker_wav'] = self.speaker_ref_path
                
            # For XTTS models, we need to handle speaker differently
            # Only add speaker parameter if we have a reference audio
            # Otherwise, let the TTS library handle speaker selection
            if 'xtts' in self.model_var.get().lower() and self.speaker_ref_path:
                # We don't need to specify 'speaker' when we have speaker_wav
                # as XTTS will use the reference audio for voice cloning
                pass
            
            try:
                # Perform actual audio generation
                self.current_tts.convert_to_audio(**convert_params)
            except AttributeError as ae:
                if "'GPT2InferenceModel' object has no attribute 'generate'" in str(ae):
                    messagebox.showerror(
                        "TTS Version Error",
                        "Your TTS library version is incompatible with XTTS model.\n"
                        "Please update TTS library by running:\n"
                        "pip install -U TTS\n\n"
                        "Or try using a different TTS model."
                    )
                    raise RuntimeError("TTS library version incompatible with XTTS model")
                else:
                    raise
            
            # Verify generation succeeded
            if not os.path.exists(output_path):
                raise RuntimeError("TTS failed to generate audio file")
                
            # Update path only after successful generation
            self.generated_audio_path = output_path
            self.settings['background_music'] = output_path
        except Exception as e:
            logging.error(f"Audio generation failed: {str(e)}", exc_info=True)
            # Re-raise the exception to be handled by the caller
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
        if hasattr(self, 'model_combo') and self.model_combo.winfo_exists():
            # Disable combobox and show loading state
            self.model_combo.set("Loading models...")
            self.model_combo.configure(state='disabled')
            
            # Start loading in background
            threading.Thread(target=self._populate_models, daemon=True).start()

    def _populate_models(self):
        """Thread-safe model loading"""
        try:
            model_names = SubToAudio().coqui_model()
                 
            valid_models = [m for m in model_names if SubToAudio()._model_exists(m)]
            
            # Update the UI with models in the main thread
            self.root.after(0, lambda: self._update_model_dropdown(valid_models))
        except Exception as e:
            logging.error(f"Error loading TTS models: {str(e)}")
            self.root.after(0, lambda: self.model_combo.configure(state='readonly'))
            self.root.after(0, lambda: self.model_combo.set("Error loading models"))
            
    def _on_model_selected(self, event=None):
        """Handle model selection and populate languages"""
        model = self.model_var.get()
        if not model:
            return

        # Show loading indicator
        loading_window = tk.Toplevel(self.root)
        loading_window.title("Loading Model")
        loading_window.geometry("300x100")
        loading_window.transient(self.root)
        loading_window.grab_set()
        
        loading_label = ttk.Label(loading_window, text="Loading model, please wait...", padding=20)
        loading_label.pack()
        
        progress = ttk.Progressbar(loading_window, mode='indeterminate')
        progress.pack(padx=20, fill=tk.X)
        progress.start()

        def load_model():
            try:
                # Check if using XTTS model
                if 'xtts' in model.lower():
                    # Try to detect TTS version compatibility
                    try:
                        from TTS import __version__ as tts_version
                        from packaging import version
                        if version.parse(tts_version) < version.parse('0.14.0'):
                            self.root.after(0, lambda: messagebox.showwarning(
                                "TTS Version Warning",
                                f"Your TTS version ({tts_version}) might not be compatible with XTTS model.\n"
                                "Consider updating with: pip install -U TTS"
                            ))
                    except (ImportError, ValueError):
                        # Can't determine version, continue anyway
                        pass
                
                self.current_tts = SubToAudio(model_name=model)
                langs = self.current_tts.languages()
                
                self.root.after(0, lambda: self._update_languages(langs))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Model Error", f"Failed to initialize model: {str(e)}"))
                logging.error(f"Error loading model: {str(e)}")
            finally:
                self.root.after(0, loading_window.destroy)

        # Start loading in background
        threading.Thread(target=load_model, daemon=True).start()

    def _update_languages(self, langs):
        """Update language dropdown with available languages"""
        if not langs:
            self.lang_combo.set("fr")
        else:
            # Update the combobox with available languages
            self.lang_combo['values'] = langs
            
            # Try to keep current language if it's in the list
            current_lang = self.language_var.get()
            if current_lang in langs:
                self.lang_combo.set(current_lang)
            else:
                # Default to 'fr' or the first available language
                default_lang = 'fr' if 'fr' in langs else langs[0]
                self.lang_combo.set(default_lang)
                self.language_var.set(default_lang)
            
    def _update_model_dropdown(self, models):
        """Update model dropdown with available models"""
        if self.model_combo:
            self.model_combo['values'] = models
            if models:
                # Set default model (use 'xtts' if available, otherwise first model)
                default_model = 'xtts' if 'xtts' in models else models[0]
                self.model_var.set(default_model)
            else:
                self.model_var.set("")
            self.model_combo.configure(state='readonly')
    def generate_video(self, output_path: str, srt_path: str) -> None:
        """Process subtitle entries into a video with audio"""
        try:
            self.update_settings()
            self.update_status("Initializing video generation...", 0)

            # Ensure temp directory is initialized
            self.temp_manager._init_dirs()
            
            adjusted_srt = srt_path
            if adjusted_srt is None:
                adjusted_srt = self.srt_path
                
            # 2. Parse subtitle entries with time validation
            self.update_status("Parsing subtitles...", 5)
            
            entries = self.srt_parser.parse(adjusted_srt)
            
            if not entries:
                raise ValueError("No valid subtitle entries found in adjusted SRT file")
            
            # Validate entries for missing 'start_time' or 'end_time'
            for i, entry in enumerate(entries):
                if 'start_time' not in entry or 'end_time' not in entry:
                    raise ValueError(f"Entry {i + 1} is missing 'start_time' or 'end_time'")
            
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