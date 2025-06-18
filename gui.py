from utils.gui_components import GUIComponents
from utils.helpers import TempFileManager
import tkinter as tk
from tkinter import filedialog, messagebox

class VideoConverterApp:
    """
    Main application class for the Video Caption Creator.
    Handles initialization, settings management, and video generation.
    """
    def __init__(self, root):
        """
        Initialize the application.

        Args:
            root: The root window for the GUI.
        """
        self.root = root

        # Initialize GUI components
        self.initialize_app()
        self.gui = GUIComponents(root, self)

    def initialize_app(self):
        """
        Initialize application variables and settings.
        """
        self.text_color_var = tk.StringVar(value="#FFFFFF")
        self.bg_color_var = tk.StringVar(value="#000000")
        self.font_size_var = tk.IntVar(value=24)
        self.output_path_var = tk.StringVar()
        self.srt_path_var = tk.StringVar()
        
        self.temp_manager = TempFileManager()

    def generate_video(self):
        """
        Generate a video using the provided output path and SRT file.
        """
        output_path = self.output_path_var.get()
        srt_path = self.srt_path_var.get()

        if not output_path or not srt_path:
            messagebox.showerror("Error", "Please provide both output and SRT file paths.")
            return

        try:
            settings = self.settings_manager.get_settings()
            self.video_generator.generate_video(output_path, srt_path, settings)
            messagebox.showinfo("Success", "Video generated successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Error generating video: {e}")

    def start_generation(self):
        """
        Start the video generation process.
        """
        self.update_settings()
        self.generate_video()

    def cancel_generation(self):
        """
        Cancel the ongoing video generation process.
        """
        if self.video_generator:
            self.video_generator.cancel()

    def start_audio_generation(self):
        """
        Start the audio generation process.
        """
        self.update_settings()
        self.generate_video()

    def update_settings(self):
        """
        Update application settings based on user input.
        """
        self.settings_manager.update_settings({
            'text_color': self.text_color_var.get(),
            'bg_color': self.bg_color_var.get(),
            'font_size': self.font_size_var.get(),
        })

    def browse_output_path(self):
        """
        Open a file dialog to select the output file path.
        """
        file_path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if file_path:
            self.output_path_var.set(file_path)

    def browse_srt_path(self):
        """
        Open a file dialog to select the SRT file path.
        """
        file_path = filedialog.askopenfilename(
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )
        if file_path:
            self.srt_path_var.set(file_path)