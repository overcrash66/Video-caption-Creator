#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

"""
GUI components for the Video Caption Creator application.
"""
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
        # Initialize variables before creating widgets
        self.app.border_var = tk.BooleanVar(value=False)
        self.app.shadow_var = tk.BooleanVar(value=False)
        self.app.text_color_var = tk.StringVar(value="#000000")
        self.app.bg_color_var = tk.StringVar(value="#FFFFFF")
        self.app.font_size_var = tk.IntVar(value=32)
        self.create_widgets()

    def create_widgets(self):
        """
        Create and layout all GUI widgets.
        """
        # Main frame
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

        # About button
        about_button = tk.Button(
            banner_frame,
            text="About",
            command=lambda: messagebox.showinfo("About", "Video Caption Creator\nVersion 1.0.1\n\nA tool for creating video captions with text-to-speech support."),
            bg="white",
            fg="#4A90E2",
            font=("Helvetica", 12, "bold"),
            relief=tk.RAISED,
            bd=2
        )
        about_button.pack(side=tk.RIGHT, padx=20, pady=20)

        # File selection section
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding=10)
        file_frame.pack(fill=tk.X, pady=10)

        # Output file path
        ttk.Label(file_frame, text="Output File:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        output_entry = ttk.Entry(file_frame, textvariable=self.app.output_path_var, width=50)
        output_entry.grid(row=0, column=1, padx=5, pady=5)
        output_browse_button = ttk.Button(file_frame, text="Browse", command=self.app.browse_output_path)
        output_browse_button.grid(row=0, column=2, padx=5, pady=5)

        # SRT file path
        ttk.Label(file_frame, text="SRT File:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        srt_entry = ttk.Entry(file_frame, textvariable=self.app.srt_path_var, width=50)
        srt_entry.grid(row=1, column=1, padx=5, pady=5)
        srt_browse_button = ttk.Button(file_frame, text="Browse", command=self.app.browse_srt_path)
        srt_browse_button.grid(row=1, column=2, padx=5, pady=5)

        # Settings section
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

        # Text border
        ttk.Checkbutton(settings_frame, text="Text Border", variable=self.app.border_var).grid(row=3, column=0, padx=5, pady=5)

        # Text shadow
        ttk.Checkbutton(settings_frame, text="Text Shadow", variable=self.app.shadow_var).grid(row=3, column=1, padx=5, pady=5)

        # Background image
        ttk.Button(settings_frame, text="Background Image", command=lambda: self.app.background_image_path_var.set(filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg")]))).grid(row=4, column=0, padx=5, pady=5)

        # Background music
        ttk.Button(settings_frame, text="Background Music", command=lambda: self.app.background_music_path_var.set(filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3;*.wav")]))).grid(row=4, column=1, padx=5, pady=5)

        # TTS settings section
        tts_frame = ttk.LabelFrame(main_frame, text="Text-to-Speech Settings", padding=10)
        tts_frame.pack(fill=tk.X, pady=10)

        # Enable TTS
        self.app.enable_tts_var = tk.BooleanVar(value=False)
        enable_tts_checkbox = ttk.Checkbutton(tts_frame, text="Enable Text-to-Speech", variable=self.app.enable_tts_var)
        enable_tts_checkbox.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        # Voice selection
        ttk.Label(tts_frame, text="Voice:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.app.voice_var = tk.StringVar(value="Default")
        voice_combobox = ttk.Combobox(tts_frame, textvariable=self.app.voice_var, values=["Default", "Male", "Female"], state="readonly")
        voice_combobox.grid(row=1, column=1, padx=5, pady=5)

        # Speech rate
        ttk.Label(tts_frame, text="Speech Rate:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.app.speech_rate_var = tk.IntVar(value=100)
        speech_rate_spinbox = ttk.Spinbox(tts_frame, from_=50, to=200, textvariable=self.app.speech_rate_var, width=10)
        speech_rate_spinbox.grid(row=2, column=1, padx=5, pady=5)

        # Reference audio
        ttk.Button(tts_frame, text="Reference Audio", command=lambda: self.app.ref_audio_path_var.set(filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3;*.wav")]))).grid(row=3, column=0, padx=5, pady=5)
        self.app.ref_audio_label = ttk.Label(tts_frame, text="No audio selected")
        self.app.ref_audio_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        # Language selection
        ttk.Label(tts_frame, text="Language:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.app.language_var = tk.StringVar(value="en")
        lang_combobox = ttk.Combobox(tts_frame, textvariable=self.app.language_var, values=["en", "fr", "es"], state="readonly")
        lang_combobox.grid(row=4, column=1, padx=5, pady=5)

        # Progress bar
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=20)
        self.app.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.app.progress.pack(fill=tk.X)
        self.app.progress_label = ttk.Label(progress_frame, text="Ready")
        self.app.progress_label.pack()

        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(pady=10)
        ttk.Button(action_frame, text="Generate Video", command=self.app.start_generation).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Cancel", command=self.app.cancel_generation).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Generate TTS Audio", command=self.app.start_audio_generation).pack(side=tk.LEFT, padx=5)

        # Reset button
        reset_button = ttk.Button(main_frame, text="Reset Application", command=self.app.reset_application)
        reset_button.pack(pady=10)

    def choose_text_color(self):
        """
        Open a color chooser dialog to select the text color.
        """
        color_code = colorchooser.askcolor(title="Choose Text Color")[1]
        if color_code:
            self.app.text_color_var.set(color_code)

    def choose_bg_color(self):
        """
        Open a color chooser dialog to select the background color.
        """
        color_code = colorchooser.askcolor(title="Choose Background Color")[1]
        if color_code:
            self.app.bg_color_var.set(color_code)