import os
import shutil
import time
import logging
from typing import Optional
from threading import Thread
from datetime import datetime, timedelta
import uuid

class TempFileManager:
    def __init__(self, log_file: str = "srt_converter.log"):
        self.base_dir = os.path.abspath("video_gen_temp")
        self.image_dir = os.path.join(self.base_dir, "images")
        self.process_dir = os.path.join(self.base_dir, "process")
        self.log_file = log_file
        self._init_dirs()
        self._start_log_cleaner()

    def _init_dirs(self):
        """Initialize required directories"""
        for d in [self.image_dir, self.process_dir]:
            os.makedirs(d, exist_ok=True)

    def _start_log_cleaner(self):
        """Start background thread for log rotation"""
        def log_cleaner():
            while True:
                self._clean_old_logs()
                time.sleep(3600)  # Check every hour

        Thread(target=log_cleaner, daemon=True).start()

    def _clean_old_logs(self):
        """Delete log files older than 48 hours"""
        try:
            if os.path.exists(self.log_file):
                created_time = datetime.fromtimestamp(os.path.getctime(self.log_file))
                if datetime.now() - created_time > timedelta(hours=48):
                    os.remove(self.log_file)
                    logging.info("Cleaned up old log file")
        except Exception as e:
            logging.error(f"Log cleanup failed: {str(e)}")

    def create_process_dir(self) -> str:
        """Create unique processing directory"""
        process_dir = os.path.join(self.process_dir, str(uuid.uuid4()))
        os.makedirs(process_dir, exist_ok=True)
        return process_dir

    def cleanup(self):
        """Clean temporary directories"""
        try:
            shutil.rmtree(self.base_dir, ignore_errors=True)
            self._init_dirs()
        except Exception as e:
            logging.error(f"Cleanup error: {str(e)}")

    def full_cleanup(self):
        """Clean everything including logs"""
        self.cleanup()
        self._clean_old_logs()