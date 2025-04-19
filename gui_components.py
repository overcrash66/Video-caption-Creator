import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageFont
import threading
import logging
import os

class GUIComponents:
    def __init__(self, root, app):
        """
        Initialize the GUI components for Video Caption Creator.

        Args:
            root: The root Tkinter window.
            app: The main application instance.
        """
        self.root = root
        self.root.title("Video Caption Creator")
        self.root.geometry("1000x850")
        self.preview_window = None
        self.app = app

        # Initialize variables
        self.app.border_var = tk.BooleanVar(value=False)
        self.app.shadow_var = tk.BooleanVar(value=False)
        self.app.text_color_var = tk.StringVar(value="#000000")
        self.app.bg_color_var = tk.StringVar(value="#FFFFFF")
        # Initialize image generator
        from processors.image_generator import ImageGenerator
        from processors.temp_manager import TempManager
        from utils.style_parser import StyleParser

        temp_manager = TempManager()
        style_parser = StyleParser()
        settings = {
            'text_color': self.app.text_color_var.get(),
            'bg_color': self.app.bg_color_var.get(),
            'font_size': self.app.font_size_var.get(),
            'border': False,
            'shadow': False
        }
        self.app.image_generator = ImageGenerator(temp_manager, style_parser, settings)
        self.image_generator = self.app.image_generator
        self.app.font_size_var = tk.IntVar(value=32)
        self.app.language_var = tk.StringVar(value="en")
        self.app.model_var = tk.StringVar(value="Default")
        self.app.speaker_ref_path = None

        # Logging setup
        self.setup_logging()

        # Create widgets
        self.create_widgets()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='video_caption_creator.log'
        )

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

        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding=10)
        file_frame.pack(fill=tk.X, pady=10)

        ttk.Label(file_frame, text="SRT File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        srt_entry = ttk.Entry(file_frame, textvariable=self.app.srt_path_var, width=50)
        srt_entry.grid(row=0, column=1, padx=5, pady=5)
        srt_browse_button = ttk.Button(file_frame, text="Browse", command=self.app.browse_srt_path)
        srt_browse_button.grid(row=0, column=2, padx=5, pady=5)

        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)

        # Text color
        ttk.Label(settings_frame, text="Text Color:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        text_color_button = ttk.Button(settings_frame, text="Choose", command=self.choose_text_color)
        text_color_button.grid(row=0, column=1, padx=5, pady=5)

        # Background color
        ttk.Label(settings_frame, text="Background Color:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        bg_color_button = ttk.Button(settings_frame, text="Choose", command=self.choose_bg_color)
        bg_color_button.grid(row=1, column=1, padx=5, pady=5)

        # Font size
        ttk.Label(settings_frame, text="Font Size:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        font_size_spinbox = ttk.Spinbox(settings_frame, from_=10, to=100, textvariable=self.app.font_size_var, width=10)
        font_size_spinbox.grid(row=2, column=1, padx=5, pady=5)

        # TTS settings
        tts_frame = ttk.LabelFrame(main_frame, text="Text-to-Speech Settings", padding=10)
        tts_frame.pack(fill=tk.X, pady=10)

        ttk.Label(tts_frame, text="Language:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        lang_combobox = ttk.Combobox(tts_frame, textvariable=self.app.language_var, values=["en", "fr", "es"], state="readonly")
        lang_combobox.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(tts_frame, text="TTS Model:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        model_combobox = ttk.Combobox(tts_frame, textvariable=self.app.model_var, values=["Default", "Custom"], state="readonly")
        model_combobox.grid(row=1, column=1, padx=5, pady=5)

        # Reference audio
        ttk.Button(tts_frame, text="Reference Audio", command=self.choose_reference_audio).grid(row=2, column=0, padx=5, pady=5)
        self.app.ref_audio_label = ttk.Label(tts_frame, text="No audio selected")
        self.app.ref_audio_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        # Add preview button
        ttk.Button(settings_frame, text="Preview", command=self.show_preview).grid(row=3, column=0, padx=5, pady=5)

    def choose_text_color(self):
        color_code = colorchooser.askcolor(title="Choose Text Color")[1]
        if color_code:
            self.app.text_color_var.set(color_code)

    def choose_bg_color(self):
        color_code = colorchooser.askcolor(title="Choose Background Color")[1]
        if color_code:
            self.app.bg_color_var.set(color_code)

    def choose_reference_audio(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3;*.wav")])
        if file_path:
            self.app.speaker_ref_path = file_path
            self.app.ref_audio_label.config(text=os.path.basename(file_path))

    def show_about(self):
        messagebox.showinfo("About", "Video Caption Creator\nVersion 1.0.2\nDeveloped by Wael Sahli")

    def show_preview(self):
        """Show style preview with thread safety and loading indicator"""
        current_settings = {
            'text_color': self.app.text_color_var.get(),
            'bg_color': self.app.bg_color_var.get(),
            'font_size': self.app.font_size_var.get(),
            'border': self.app.border_var.get(),
            'shadow': self.app.shadow_var.get()
        }
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

    def close_preview(self):
        """Close the preview window and clean up resources."""
        if self.preview_window:
            self.preview_window.destroy()
            self.preview_window = None
            
    def _generate_preview_content(self, sample_text):
        """Generate preview content with the current style settings."""
        try:
            preview_image = self.image_generator.generate_image(sample_text)
            if preview_image:
                # Convert PIL image to PhotoImage
                photo = ImageTk.PhotoImage(preview_image)
                
                # Update preview window in main thread
                self.root.after(0, self._update_preview_window, photo)
        except Exception as e:
            logging.error(f"Preview generation failed: {str(e)}")
            self.root.after(0, self._show_preview_error)
            
    def _update_preview_window(self, photo):
        """Update the preview window with the generated image."""
        if self.preview_window:
            self.loading_spinner.stop()
            self.loading_spinner.pack_forget()
            
            # Create and pack the preview label
            preview_label = ttk.Label(self.preview_window, image=photo)
            preview_label.image = photo  # Keep a reference
            preview_label.pack(padx=10, pady=10)
            
    def _show_preview_error(self):
        """Show error message in preview window."""
        if self.preview_window:
            self.loading_spinner.stop()
            self.loading_spinner.pack_forget()
            ttk.Label(self.preview_window,
                     text="Failed to generate preview",
                     foreground="red").pack(pady=20)