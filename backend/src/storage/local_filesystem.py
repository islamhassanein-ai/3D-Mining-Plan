import os
import uuid
from backend.src.storage.base import StorageProvider

class LocalFilesystemStorage(StorageProvider):
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            # Default directory is backend/uploads/ relative to package root
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            backend_root = os.path.dirname(os.path.dirname(current_file_dir))
            base_dir = os.path.join(backend_root, "uploads")
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, file_content: bytes, filename: str) -> str:
        # Create a unique filename using a UUID to prevent collisions
        unique_id = uuid.uuid4().hex
        _, ext = os.path.splitext(filename)
        stored_name = f"{unique_id}{ext}"
        full_path = os.path.join(self.base_dir, stored_name)
        
        with open(full_path, "wb") as f:
            f.write(file_content)
            
        return stored_name

    def load(self, file_ref: str) -> bytes:
        full_path = os.path.join(self.base_dir, file_ref)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Storage file not found: {file_ref}")
        with open(full_path, "rb") as f:
            return f.read()
