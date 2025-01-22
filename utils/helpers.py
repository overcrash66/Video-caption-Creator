import os
import shutil
import uuid

class TempFileManager:
    def __init__(self):
        self.base_dir = os.path.abspath("video_gen_temp")
        self.image_dir = os.path.join(self.base_dir, "images")
        self.process_dir = os.path.join(self.base_dir, "process")
        self.init_dirs()

    def init_dirs(self):
        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.process_dir, exist_ok=True)

    def create_process_dir(self) -> str:
        """Create unique processing directory"""
        process_dir = os.path.join(self.base_dir, "process", str(uuid.uuid4()))
        os.makedirs(process_dir, exist_ok=True)
        return process_dir

    def cleanup(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)
        self.init_dirs()