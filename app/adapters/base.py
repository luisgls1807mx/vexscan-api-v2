"""
Base adapter interface for all scanner parsers.
All scanner adapters must inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Set
from pathlib import Path

from app.adapters.dto import ScanResult


class BaseScannerAdapter(ABC):
    """
    Abstract base class for scanner adapters.
    
    Each scanner (Nessus, Invicti, Acunetix, etc.) must implement
    this interface to parse their specific file formats.
    """
    
    # Scanner identification
    scanner_name: str = "unknown"
    scanner_display_name: str = "Unknown Scanner"
    
    # Supported file extensions (e.g., {".nessus", ".xml"})
    supported_extensions: Set[str] = set()
    
    # Supported MIME types
    supported_mime_types: Set[str] = set()
    
    @abstractmethod
    async def parse(self, file_content: bytes, filename: str) -> ScanResult:
        """
        Parse the scanner file and return normalized results.
        
        Args:
            file_content: Raw bytes of the uploaded file
            filename: Original filename (used for format detection)
            
        Returns:
            ScanResult containing all parsed assets and findings
            
        Raises:
            ValueError: If the file format is invalid or unsupported
            ParseError: If parsing fails
        """
        pass
    
    @abstractmethod
    async def validate(self, file_content: bytes, filename: str) -> bool:
        """
        Validate that the file is a valid scanner output.
        
        Args:
            file_content: Raw bytes of the uploaded file
            filename: Original filename
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def supports_file(self, filename: str, mime_type: Optional[str] = None) -> bool:
        """
        Check if this adapter supports the given file.
        
        Args:
            filename: Filename to check
            mime_type: Optional MIME type
            
        Returns:
            True if this adapter can handle the file
        """
        ext = Path(filename).suffix.lower()
        
        if ext in self.supported_extensions:
            return True
            
        if mime_type and mime_type in self.supported_mime_types:
            return True
            
        return False
    
    def get_file_extension(self, filename: str) -> str:
        """Get the file extension from filename."""
        return Path(filename).suffix.lower()
    
    def get_scanner_info(self) -> dict:
        """Get scanner information."""
        return {
            "name": self.scanner_name,
            "display_name": self.scanner_display_name,
            "supported_extensions": list(self.supported_extensions),
            "supported_mime_types": list(self.supported_mime_types),
        }


class ParseError(Exception):
    """Exception raised when parsing fails."""
    
    def __init__(self, message: str, scanner: str = None, details: dict = None):
        self.message = message
        self.scanner = scanner
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        return {
            "error": "ParseError",
            "message": self.message,
            "scanner": self.scanner,
            "details": self.details,
        }
