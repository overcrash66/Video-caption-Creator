import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk
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

class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Caption Creator")
        self.root.geometry("1000x750")
        
        # Initialize settings FIRST
        self.settings = {
            'text_color': "#FFFFFF",
            'bg_color': "#000000",
            'font_size': 24,
            'text_border': True,
            'text_shadow': False,
            'speed_factor': 1.0,
            'margin': 20,
            'batch_size': 50,
            'background_image': None,
            'background_music': None,
            'custom_font': None
        }
        
        # THEN initialize components
        self.temp_manager = TempFileManager()
        self.srt_parser = SRTParser()
        self.style_parser = StyleParser()
        self.image_generator = ImageGenerator(
            temp_manager=self.temp_manager,
            style_parser=self.style_parser,
            settings=self.settings  # Explicitly pass settings
        )
        self.video_processor = VideoProcessor(self.temp_manager, self.settings)
        
        self.setup_styles()
        self.create_widgets()
        self.setup_logging()
        self.running = False

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TButton', font=('Helvetica', 10), padding=6)
        self.style.configure('TLabel', font=('Helvetica', 9))
        self.style.configure('Header.TLabel', font=('Helvetica', 11, 'bold'))

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Settings Panel
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)
        
        # Background controls
        bg_frame = ttk.Frame(settings_frame)
        bg_frame.pack(fill=tk.X, pady=5)
        ttk.Button(bg_frame, text="Background Image", command=self.choose_background_image).pack(side=tk.LEFT)
        ttk.Button(bg_frame, text="Background Color", command=self.choose_bg_color).pack(side=tk.LEFT, padx=5)
        ttk.Button(bg_frame, text="Background Music", command=self.choose_background_music).pack(side=tk.LEFT)
        
        # Font controls
        font_frame = ttk.Frame(settings_frame)
        font_frame.pack(fill=tk.X, pady=5)
        ttk.Button(font_frame, text="Select Font", command=self.choose_font).pack(side=tk.LEFT)
        ttk.Button(font_frame, text="Text Color", command=self.choose_text_color).pack(side=tk.LEFT, padx=5)
        ttk.Label(font_frame, text="Text Size:").pack(side=tk.LEFT)
        self.text_size = ttk.Scale(font_frame, from_=10, to=100, length=100)
        self.text_size.set(self.settings['font_size'])
        self.text_size.pack(side=tk.LEFT)
        
        # Effects checkboxes
        check_frame = ttk.Frame(settings_frame)
        check_frame.pack(fill=tk.X, pady=5)
        self.border_var = tk.BooleanVar(value=self.settings['text_border'])
        ttk.Checkbutton(check_frame, text="Text Border", variable=self.border_var,
                      command=lambda: self.settings.update({'text_border': self.border_var.get()})).pack(side=tk.LEFT)
        self.shadow_var = tk.BooleanVar(value=self.settings['text_shadow'])
        ttk.Checkbutton(check_frame, text="Text Shadow", variable=self.shadow_var,
                      command=lambda: self.settings.update({'text_shadow': self.shadow_var.get()})).pack(side=tk.LEFT)
        
        # Preview button
        ttk.Button(settings_frame, text="Preview Style", command=self.show_preview).pack(pady=5)
        
        # Progress area
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=20)
        self.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress.pack(fill=tk.X)
        self.progress_label = ttk.Label(progress_frame, text="Ready")
        self.progress_label.pack()
        
        # Action buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Generate Video", command=self.start_generation).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel_generation).pack(side=tk.LEFT, padx=5)

    def choose_background_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.png *.jpeg")])
        if file_path:
            self.settings['background_image'] = file_path

    def choose_bg_color(self):
        color = colorchooser.askcolor(title="Choose Background Color")
        if color[1]:
            self.settings['bg_color'] = color[1]

    def choose_text_color(self):
        color = colorchooser.askcolor(title="Choose Text Color")
        if color[1]:
            self.settings['text_color'] = color[1]

    def choose_font(self):
        file_path = filedialog.askopenfilename(filetypes=[("Font Files", "*.ttf *.otf")])
        if file_path:
            self.settings['custom_font'] = file_path

    def choose_background_music(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav")])
        if file_path:
            self.settings['background_music'] = file_path

    def show_preview(self):
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Text Style Preview")
        img = self.image_generator.generate_preview(
            "Preview Text\n<font size='18'>Styled Text</font>\n<i>Italic Text</i>",
            self.settings
        )
        photo = ImageTk.PhotoImage(img)
        label = ttk.Label(preview_window, image=photo)
        label.image = photo
        label.pack(padx=10, pady=10)
        ttk.Button(preview_window, text="Close", command=preview_window.destroy).pack(pady=5)

    def start_generation(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self.generate_video, daemon=True).start()

    def generate_video(self):
        try:
            srt_file = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt")])
            if not srt_file:
                return

            self.update_status("Parsing SRT...", 0)
            entries = self.srt_parser.parse(srt_file)
            if not entries:
                messagebox.showerror("Error", "Invalid SRT file")
                return

            self.update_status("Generating images...", 25)
            images = self.image_generator.generate_images(entries)
            if len(images) != len(entries):
                messagebox.showerror("Error", f"Failed to generate {len(entries)-len(images)} images")
                return

            self.update_status("Processing batches...", 50)
            batches = [
                images[i:i+self.settings['batch_size']]  # Use settings value
                for i in range(0, len(images), self.settings['batch_size'])
            ]
            
            with ThreadPoolExecutor() as executor:
                # Use non-conflicting variable name
                future_tasks = [
                    executor.submit(self.video_processor.process_batch, batch, idx)
                    for idx, batch in enumerate(batches)
                ]
                
                # Collect valid segments
                segments = []
                for future in future_tasks:
                    result = future.result()
                    if result and os.path.exists(result):
                        segments.append(result)

            if not segments:
                messagebox.showerror("Error", "No valid video segments created")
                return

            output_path = filedialog.asksaveasfilename(defaultextension=".mp4")
            if output_path:
                self.update_status("Combining segments...", 75)
                success = self.video_processor.combine_segments(segments, output_path, self.settings['background_music'])
                if success:
                #if self.video_processor.combine_segments(segments, output_path):
                    self.update_status("Complete!", 100)
                    messagebox.showinfo("Success", f"Video saved to:\n{output_path}")
                else:
                    messagebox.showerror("Error", "Failed to combine segments")
        except Exception as e:
            logging.error(f"Generation failed: {str(e)}")
            messagebox.showerror("Error", str(e))
        finally:
            self.running = False
            self.temp_manager.cleanup()

    def update_status(self, message: str, progress: int):
        self.progress_label.config(text=message)
        self.progress['value'] = progress
        self.root.update_idletasks()

    def cancel_generation(self):
        if self.running:
            self.running = False
            self.temp_manager.cleanup()
            self.update_status("Cancelled", 0)
            messagebox.showinfo("Info", "Generation cancelled")

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='srt_converter.log'
        )

    def create_settings_panel(self, parent):
        # Add batch size control
        ttk.Label(parent, text="Batch Size:").grid(row=5, column=0, sticky='w')
        self.batch_size = ttk.Combobox(parent, values=[10, 25, 50, 100], width=8)
        self.batch_size.set(self.settings['batch_size'])
        self.batch_size.grid(row=5, column=1, sticky='w')
        
        # Update settings on change
        self.batch_size.bind("<<ComboboxSelected>>", 
                            lambda e: self.settings.update({'batch_size': int(self.batch_size.get())}))    