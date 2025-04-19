import os
import shutil
import tempfile

class TempManager:
    def __init__(self):
        """Initialize temporary directory manager"""
        self.temp_dir = tempfile.mkdtemp()
        self.image_dir = os.path.join(self.temp_dir, 'images')
        os.makedirs(self.image_dir, exist_ok=True)

    def get_temp_path(self, filename):
        """
        Get a path for a temporary file
        
        Args:
            filename (str): Name of the temporary file
            
        Returns:
            str: Full path to the temporary file
        """
        return os.path.join(self.temp_dir, filename)

    def cleanup(self):
        """Remove all temporary files and directory"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def __del__(self):
        """Ensure cleanup on object destruction"""
        self.cleanup()