"""
Data Transfer Objects for scanner adapters.
These DTOs represent the normalized intermediate format between
raw scanner output and the canonical database schema.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class NormalizedSeverity(str, Enum):
    """Normalized severity levels for all scanners."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class NetworkZone(str, Enum):
    """Network zone classification."""
    INTERNAL = "internal"
    EXTERNAL = "external"
    DMZ = "dmz"
    CLOUD = "cloud"


class AssetType(str, Enum):
    """Asset type classification."""
    IP = "ip"
    HOST = "host"
    URL = "url"
    APP = "app"
    NETWORK = "network"
    CLOUD = "cloud"


@dataclass
class RawAsset:
    """
    Normalized asset/host information extracted from scanner.
    Maps to the `assets` table in Supabase.
    """
    # Identification
    identifier: str                          # Primary identifier (IP or hostname)
    asset_type: AssetType = AssetType.HOST
    name: Optional[str] = None
    
    # Network info
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    fqdn: Optional[str] = None
    netbios_name: Optional[str] = None
    network_zone: Optional[NetworkZone] = None
    
    # Operating System
    os_name: Optional[str] = None            # Full OS name
    os_version: Optional[str] = None
    os_family: Optional[str] = None          # Windows, Linux, macOS, etc.
    
    # Context
    environment: Optional[str] = None        # prod, dev, staging, qa
    owner: Optional[str] = None
    department: Optional[str] = None
    criticality: Optional[str] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Scanner info
    scanner: str = ""
    scan_start: Optional[datetime] = None
    scan_end: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "identifier": self.identifier,
            "asset_type": self.asset_type.value if isinstance(self.asset_type, AssetType) else self.asset_type,
            "name": self.name or self.hostname or self.ip_address,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "mac_address": self.mac_address,
            "network_zone": self.network_zone.value if self.network_zone else None,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "os_family": self.os_family,
            "environment": self.environment,
            "owner": self.owner,
            "department": self.department,
            "criticality": self.criticality,
            "tags": self.tags,
            "metadata": {
                **self.metadata,
                "fqdn": self.fqdn,
                "netbios_name": self.netbios_name,
                "scanner": self.scanner,
                "scan_start": self.scan_start.isoformat() if self.scan_start else None,
                "scan_end": self.scan_end.isoformat() if self.scan_end else None,
            }
        }


@dataclass
class RawFinding:
    """
    Normalized vulnerability/finding extracted from scanner.
    Maps to the `findings` table in Supabase.
    """
    # Required fields
    title: str
    severity: NormalizedSeverity
    scanner: str
    
    # Asset reference (will be linked after asset creation)
    asset_identifier: str                    # IP or hostname to link
    
    # Description
    description: Optional[str] = None
    solution: Optional[str] = None           # Remediation recommendation
    synopsis: Optional[str] = None           # Brief summary
    
    # Location
    location: Optional[str] = None           # Combined location string
    port: Optional[int] = None
    protocol: Optional[str] = None           # tcp, udp, icmp
    service: Optional[str] = None            # http, ssh, smb, etc.
    
    # Severity details
    original_severity: Optional[str] = None  # Original from scanner
    risk_factor: Optional[str] = None
    
    # Classification
    cwe: Optional[str] = None
    cves: List[str] = field(default_factory=list)
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    cvss3_score: Optional[float] = None
    cvss3_vector: Optional[str] = None
    
    # References
    references: List[str] = field(default_factory=list)
    reference_ids: Dict[str, str] = field(default_factory=dict)
    
    # Plugin info (Nessus/scanner specific)
    plugin_id: Optional[str] = None
    plugin_name: Optional[str] = None
    plugin_family: Optional[str] = None
    plugin_type: Optional[str] = None
    plugin_output: Optional[str] = None
    
    # Scanner metadata
    scanner_finding_id: Optional[str] = None
    
    # Timestamps
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    # Raw data for extras
    extras: Dict[str, Any] = field(default_factory=dict)
    
    # Fingerprint (generated)
    fingerprint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "title": self.title,
            "description": self.description,
            "solution": self.solution,
            "severity": self.severity.value if isinstance(self.severity, NormalizedSeverity) else self.severity,
            "original_severity": self.original_severity,
            "location": self.location or self._build_location(),
            "port": self.port,
            "protocol": self.protocol,
            "cwe": self.cwe,
            "cves": self.cves if self.cves else None,
            "cvss_score": self.cvss3_score or self.cvss_score,
            "cvss_vector": self.cvss3_vector or self.cvss_vector,
            "references": self.references if self.references else None,
            "reference_ids": self.reference_ids if self.reference_ids else None,
            "plugin_id": self.plugin_id,
            "plugin_name": self.plugin_name,
            "plugin_family": self.plugin_family,
            "scanner": self.scanner,
            "scanner_finding_id": self.scanner_finding_id or self.plugin_id,
            "fingerprint": self.fingerprint,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "extras": {
                **self.extras,
                "synopsis": self.synopsis,
                "risk_factor": self.risk_factor,
                "service": self.service,
                "plugin_type": self.plugin_type,
                "plugin_output": self.plugin_output,
                "cvss_v2": {
                    "score": self.cvss_score,
                    "vector": self.cvss_vector
                } if self.cvss_score else None,
                "cvss_v3": {
                    "score": self.cvss3_score,
                    "vector": self.cvss3_vector
                } if self.cvss3_score else None,
            }
        }
    
    def _build_location(self) -> str:
        """Build location string from port/protocol/service."""
        parts = []
        if self.port:
            parts.append(f"{self.port}")
        if self.protocol:
            parts.append(f"/{self.protocol}")
        if self.service:
            parts.append(f" ({self.service})")
        return "".join(parts) if parts else ""


@dataclass
class ScanResult:
    """
    Complete result of parsing a scan file.
    Contains all assets and findings extracted.
    """
    # Scanner info
    scanner: str
    scanner_version: Optional[str] = None
    
    # Scan metadata
    scan_name: Optional[str] = None
    scan_policy: Optional[str] = None
    scan_start: Optional[datetime] = None
    scan_end: Optional[datetime] = None
    
    # Extracted data
    assets: List[RawAsset] = field(default_factory=list)
    findings: List[RawFinding] = field(default_factory=list)
    
    # Statistics
    total_hosts: int = 0
    total_findings: int = 0
    findings_by_severity: Dict[str, int] = field(default_factory=dict)
    
    # Errors during parsing
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scanner": self.scanner,
            "scanner_version": self.scanner_version,
            "scan_name": self.scan_name,
            "scan_policy": self.scan_policy,
            "scan_start": self.scan_start.isoformat() if self.scan_start else None,
            "scan_end": self.scan_end.isoformat() if self.scan_end else None,
            "total_hosts": self.total_hosts,
            "total_findings": self.total_findings,
            "findings_by_severity": self.findings_by_severity,
            "assets": [a.to_dict() for a in self.assets],
            "findings": [f.to_dict() for f in self.findings],
            "errors": self.errors,
            "warnings": self.warnings,
        }
