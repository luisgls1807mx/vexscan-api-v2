"""
Adapter Registry - Factory for scanner adapters.
Handles registration and selection of appropriate adapters.
"""

from typing import Dict, Type, Optional, List
import logging

from app.adapters.base import BaseScannerAdapter, ParseError


logger = logging.getLogger(__name__)


class AdapterRegistry:
    """
    Registry for scanner adapters.
    
    Provides automatic adapter selection based on file type
    and centralized adapter management.
    
    Usage:
        # Register an adapter
        @AdapterRegistry.register("nessus")
        class NessusAdapter(BaseScannerAdapter):
            ...
        
        # Get an adapter
        adapter = AdapterRegistry.get_adapter("nessus")
        
        # Auto-detect adapter
        adapter = AdapterRegistry.detect_adapter(filename, content)
    """
    
    _adapters: Dict[str, Type[BaseScannerAdapter]] = {}
    _instances: Dict[str, BaseScannerAdapter] = {}
    
    @classmethod
    def register(cls, name: str):
        """
        Decorator to register an adapter.
        
        Args:
            name: Unique identifier for the adapter (e.g., "nessus", "invicti")
        """
        def decorator(adapter_class: Type[BaseScannerAdapter]):
            if name in cls._adapters:
                logger.warning(f"Adapter '{name}' already registered. Overwriting.")
            
            cls._adapters[name] = adapter_class
            logger.info(f"Registered adapter: {name} -> {adapter_class.__name__}")
            return adapter_class
        
        return decorator
    
    @classmethod
    def get_adapter(cls, name: str) -> BaseScannerAdapter:
        """
        Get an adapter instance by name.
        
        Args:
            name: Adapter identifier
            
        Returns:
            Adapter instance
            
        Raises:
            ValueError: If adapter not found
        """
        name = name.lower()
        
        if name not in cls._adapters:
            available = ", ".join(cls._adapters.keys())
            raise ValueError(
                f"Adapter '{name}' not found. Available adapters: {available}"
            )
        
        # Use cached instance or create new
        if name not in cls._instances:
            cls._instances[name] = cls._adapters[name]()
        
        return cls._instances[name]
    
    @classmethod
    def detect_adapter(
        cls, 
        filename: str, 
        file_content: Optional[bytes] = None,
        mime_type: Optional[str] = None
    ) -> Optional[BaseScannerAdapter]:
        """
        Auto-detect the appropriate adapter for a file.
        
        Args:
            filename: Name of the file
            file_content: Optional file content for deeper inspection
            mime_type: Optional MIME type
            
        Returns:
            Matching adapter or None if not found
        """
        # First, try by extension
        for name, adapter_class in cls._adapters.items():
            adapter = cls.get_adapter(name)
            if adapter.supports_file(filename, mime_type):
                logger.info(f"Detected adapter '{name}' for file '{filename}'")
                return adapter
        
        # If content provided, try validation
        if file_content:
            for name, adapter_class in cls._adapters.items():
                adapter = cls.get_adapter(name)
                try:
                    # Run sync validation check (basic)
                    if cls._quick_validate(adapter, file_content, filename):
                        logger.info(f"Validated adapter '{name}' for file '{filename}'")
                        return adapter
                except Exception as e:
                    logger.debug(f"Adapter '{name}' validation failed: {e}")
                    continue
        
        logger.warning(f"No adapter found for file '{filename}'")
        return None
    
    @classmethod
    def _quick_validate(
        cls, 
        adapter: BaseScannerAdapter, 
        content: bytes, 
        filename: str
    ) -> bool:
        """Quick synchronous validation check."""
        # Check for scanner-specific signatures in content
        content_start = content[:1000].decode('utf-8', errors='ignore').lower()
        
        if adapter.scanner_name == "nessus":
            return "nessusclientdata" in content_start or "<nessusreport" in content_start
        elif adapter.scanner_name == "invicti":
            return "invicti" in content_start or "netsparker" in content_start
        elif adapter.scanner_name == "acunetix":
            return "acunetix" in content_start
        elif adapter.scanner_name == "burp":
            return "burp" in content_start or "<issues" in content_start
        elif adapter.scanner_name == "qualys":
            return "qualys" in content_start
        elif adapter.scanner_name == "openvas":
            return "openvas" in content_start or "<omp" in content_start
        
        return False
    
    @classmethod
    def list_adapters(cls) -> List[dict]:
        """
        List all registered adapters with their info.
        
        Returns:
            List of adapter information dictionaries
        """
        result = []
        for name in cls._adapters:
            adapter = cls.get_adapter(name)
            info = adapter.get_scanner_info()
            info["registered_name"] = name
            result.append(info)
        return result
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an adapter is registered."""
        return name.lower() in cls._adapters
    
    @classmethod
    def clear(cls):
        """Clear all registered adapters (mainly for testing)."""
        cls._adapters.clear()
        cls._instances.clear()


# Convenience function
def get_adapter_for_file(
    filename: str, 
    file_content: Optional[bytes] = None,
    scanner_hint: Optional[str] = None
) -> BaseScannerAdapter:
    """
    Get the appropriate adapter for a file.
    
    Args:
        filename: Name of the file
        file_content: Optional file content
        scanner_hint: Optional hint about which scanner generated the file
        
    Returns:
        Appropriate adapter
        
    Raises:
        ValueError: If no suitable adapter found
    """
    # If hint provided, try that first
    if scanner_hint:
        try:
            adapter = AdapterRegistry.get_adapter(scanner_hint)
            if adapter.supports_file(filename):
                return adapter
        except ValueError:
            pass
    
    # Auto-detect
    adapter = AdapterRegistry.detect_adapter(filename, file_content)
    
    if adapter is None:
        raise ValueError(
            f"No suitable adapter found for file '{filename}'. "
            f"Available adapters: {', '.join(a['registered_name'] for a in AdapterRegistry.list_adapters())}"
        )
    
    return adapter
