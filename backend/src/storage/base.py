from abc import ABC, abstractmethod

class StorageProvider(ABC):
    @abstractmethod
    def save(self, file_content: bytes, filename: str) -> str:
        """Saves file_content and returns a unique file reference/key string.
        
        Args:
            file_content: The raw bytes of the file.
            filename: The original name of the file.
            
        Returns:
            A unique string reference/key that can be used to load the file later.
        """
        pass

    @abstractmethod
    def load(self, file_ref: str) -> bytes:
        """Loads file contents using the file reference/key and returns bytes.
        
        Args:
            file_ref: The unique string reference/key of the file.
            
        Returns:
            The raw bytes of the file.
        """
        pass
