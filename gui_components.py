import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageFont, ImageDraw
import threading
import logging
import os
from typing import List

# Import processors and utilities
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
        self.preview_window = None

        # Initialize variables
        self.text_color_var = tk.StringVar(value="#FFFFFF")
        self.bg_color_var = tk.StringVar(value="#000000")
        self.font_size_var = tk.IntVar(value=24)
        self.border_var = tk.BooleanVar(value=False)
        self.shadow_var = tk.BooleanVar(value=False)
        self.language_var = tk.StringVar(value="en")
        self.model_var = tk.StringVar()
        self.user_value_var = tk.StringVar(value="0")
        self.background_image_path = None
        self.background_music_path = None
        self.custom_font_path = None
        self.speaker_ref_path = None

        # Initialize core processing components
        self.temp_manager = TempFileManager()
        self.style_parser = StyleParser()
        self.srt_parser = SRTParser()
        self.image_generator = ImageGenerator(self.temp_manager, self.style_parser, self.get_current_settings())
        self.video_processor = VideoProcessor(self.temp_manager, self.get_current_settings())

        # Setup logging
        self.setup_logging()

        # Create widgets
        self.create_widgets()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='gui_components.log'
        )

    def get_current_settings(self) -> dict:
        """
        Safely get current settings with null checks.
        """
        settings = {
            'text_color': self.text_color_var.get(),
            'bg_color': self.bg_color_var.get(),
            'font_size': self.font_size_var.get(),
            'text_border': self.border_var.get(),
            'text_shadow': self.shadow_var.get(),
            'background_image': self.background_image_path,
            'background_music': self.background_music_path,
            'custom_font': self.custom_font_path,
            'margin': 20
        }
        return settings

    def create_widgets(self):
        """
        Create and layout all GUI widgets.
        """
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Banner
        banner_frame = tk.Frame(self.root, bg="#4A90E2", height=60)
        banner_frame.pack(fill=tk.X)
        banner_label = tk.Label(
            banner_frame,
            text="Video Caption Creator",
            bg="#4A90E2",
            fg="white",
            font=("Helvetica", 18, "bold")
        )
        banner_label.pack(side=tk.LEFT, padx=20, pady=20)

        # About Button
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

        # File Selection Frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding=10)
        file_frame.pack(fill=tk.X, pady=10)

        ttk.Label(file_frame, text="SRT File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        srt_entry = ttk.Entry(file_frame, textvariable=self.app.srt_path_var, width=50)
        srt_entry.grid(row=0, column=1, padx=5, pady=5)
        srt_browse_button = ttk.Button(file_frame, text="Browse", command=self.app.browse_srt_path)
        srt_browse_button.grid(row=0, column=2, padx=5, pady=5)

        # Settings Frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)

        # Text Color
        ttk.Label(settings_frame, text="Text Color:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        text_color_button = ttk.Button(settings_frame, text="Choose", command=self.choose_text_color)
        text_color_button.grid(row=0, column=1, padx=5, pady=5)

        # Background Color
        ttk.Label(settings_frame, text="Background Color:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        bg_color_button = ttk.Button(settings_frame, text="Choose", command=self.choose_bg_color)
        bg_color_button.grid(row=1, column=1, padx=5, pady=5)

        # Font Size
        ttk.Label(settings_frame, text="Font Size:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        font_size_spinbox = ttk.Spinbox(settings_frame, from_=10, to=100, textvariable=self.font_size_var, width=10)
        font_size_spinbox.grid(row=2, column=1, padx=5, pady=5)

        # TTS Settings
        tts_frame = ttk.LabelFrame(main_frame, text="Text-to-Speech Settings", padding=10)
        tts_frame.pack(fill=tk.X, pady=10)

        ttk.Label(tts_frame, text="Language:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        lang_combobox = ttk.Combobox(tts_frame, textvariable=self.language_var, values=["en", "fr", "es"], state="readonly")
        lang_combobox.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(tts_frame, text="TTS Model:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        model_combobox = ttk.Combobox(tts_frame, textvariable=self.model_var, values=["Default", "Custom"], state="readonly")
        model_combobox.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(tts_frame, text="Reference Audio", command=self.choose_reference_audio).grid(row=2, column=0, padx=5, pady=5)
        self.app.ref_audio_label = ttk.Label(tts_frame, text="No audio selected")
        self.app.ref_audio_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        # Preview Button
        ttk.Button(settings_frame, text="Preview", command=self.show_preview).grid(row=3, column=0, padx=5, pady=5)

    def choose_text_color(self):
        color_code = colorchooser.askcolor(title="Choose Text Color")[1]
        if color_code:
            self.text_color_var.set(color_code)

    def choose_bg_color(self):
        color_code = colorchooser.askcolor(title="Choose Background Color")[1]
        if color_code:
            self.bg_color_var.set(color_code)

    def choose_reference_audio(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3;*.wav")])
        if file_path:
            self.speaker_ref_path = file_path
            self.app.ref_audio_label.config(text=os.path.basename(file_path))

    def show_about(self):
        messagebox.showinfo("About", "Video Caption Creator\nVersion 1.0.2\nDeveloped by Wael Sahli")

    def show_preview(self):
        """
        Show style preview with thread safety and loading indicator.
        """
        current_settings = self.get_current_settings()
        self.image_generator.settings = current_settings  # Update generator settings

        # Close existing preview
        if self.preview_window:
            self.preview_window.destroy()

        # Create preview window
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("Text Style Preview")

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