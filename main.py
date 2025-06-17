import os
os.environ["PYTHONIOENCODING"] = "utf-8"
from gui import VideoConverterApp
import tkinter as tk

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConverterApp(root)
    root.mainloop()