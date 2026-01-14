"""
Scanner Adapters Module

This module contains adapters for parsing output from various
vulnerability scanners and normalizing them to a common format.

Supported Scanners:
- Nessus (.nessus, .xml)
- Invicti/Netparker (.xml, .json) [planned]
- Acunetix (.xml, .json) [planned]
- Burp Suite (.xml) [planned]
- Qualys (.xml, .csv) [planned]
- OpenVAS (.xml) [planned]

Usage:
    from app.adapters import AdapterRegistry, get_adapter_for_file
    
    # Auto-detect adapter
    adapter = get_adapter_for_file("scan.nessus", file_content)
    result = await adapter.parse(file_content, "scan.nessus")
    
    # Or get specific adapter
    adapter = AdapterRegistry.get_adapter("nessus")
    result = await adapter.parse(file_content, "scan.nessus")
"""

from app.adapters.base import BaseScannerAdapter, ParseError
from app.adapters.registry import AdapterRegistry, get_adapter_for_file
from app.adapters.dto import (
    ScanResult,
    RawAsset,
    RawFinding,
    NormalizedSeverity,
    NetworkZone,
    AssetType,
)

# Import adapters to register them
from app.adapters.nessus import NessusAdapter

__all__ = [
    # Base classes
    "BaseScannerAdapter",
    "ParseError",
    
    # Registry
    "AdapterRegistry",
    "get_adapter_for_file",
    
    # DTOs
    "ScanResult",
    "RawAsset", 
    "RawFinding",
    "NormalizedSeverity",
    "NetworkZone",
    "AssetType",
    
    # Adapters
    "NessusAdapter",
]
