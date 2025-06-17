import os
import shutil
import time
import logging
from typing import Optional
from threading import Thread, Event
from datetime import datetime, timedelta
import uuid

class TempFileManager:
    def __init__(self, root_dir: Optional[str] = None, log_file: Optional[str] = None):
        """
        Initialize the TempFileManager with configurable root directory and log file.
        """
        self.root_dir = os.path.abspath(root_dir) if root_dir else os.path.abspath("video_gen_temp")
        self.image_dir = os.path.join(self.root_dir, "images")
        self.process_dir = os.path.join(self.root_dir, "process")
        self.temp_dir = os.path.join(self.root_dir, "temp")
        self.log_file = log_file if log_file else os.path.join(self.root_dir, "srt_converter.log")
        self._stop_event = Event()  # Event to stop the log cleaner thread
        self._init_dirs()
        self._start_log_cleaner()
    def _init_dirs(self):
        """Initialize required directories."""
        for d in [self.image_dir, self.process_dir, self.temp_dir]:
            os.makedirs(d, exist_ok=True)

    def _start_log_cleaner(self):
        """Start background thread for log rotation."""
        def log_cleaner():
            while not self._stop_event.is_set():
                self._clean_old_logs()
                time.sleep(3600)  # Check every hour

        Thread(target=log_cleaner, daemon=True).start()

    def _clean_old_logs(self):
        """Delete log files older than 48 hours."""
        try:
            if os.path.exists(self.log_file):
                created_time = datetime.fromtimestamp(os.path.getctime(self.log_file))
                if datetime.now() - created_time > timedelta(hours=48):
                    os.remove(self.log_file)
                    logging.info("Cleaned up old log file")
        except Exception as e:
            logging.error(f"Log cleanup failed: {str(e)}")

    def create_process_dir(self) -> str:
        """Create a unique processing directory."""
        process_dir = os.path.join(self.process_dir, str(uuid.uuid4()))
        os.makedirs(process_dir, exist_ok=True)
        return process_dir

    def cleanup(self):
        """Clean temporary directories."""
        try:
            shutil.rmtree(self.root_dir, ignore_errors=False)  # Raise errors for debugging
            self._init_dirs()
        except Exception as e:
            logging.error(f"Cleanup error: {str(e)}")
            raise  # Re-raise the exception for debugging

    def full_cleanup(self):
        """Clean everything including logs."""
        self._stop_event.set()  # Stop the log cleaner thread
        self.cleanup()
        self._clean_old_logs()

    def verify_file(self, filename: str) -> bool:
        """Check if a file exists in the root directory and is not empty."""
        path = os.path.join(self.root_dir, filename)
        return os.path.exists(path) and os.path.getsize(path) > 0