import os
os.environ["PYTHONIOENCODING"] = "utf-8"
import tkinter as tk

from gui import VideoConverterApp

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConverterApp(root)
    root.mainloop()