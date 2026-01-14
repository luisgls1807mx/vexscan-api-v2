"""
Nessus Scanner Adapter

Parses .nessus files (XML format) and extracts:
- Host/Asset information
- Vulnerability findings
- Plugin metadata
- CVE/CVSS information

.nessus file structure:
<NessusClientData_v2>
  <Policy>...</Policy>
  <Report name="scan_name">
    <ReportHost name="192.168.1.1">
      <HostProperties>
        <tag name="host-ip">192.168.1.1</tag>
        <tag name="hostname">server1</tag>
        <tag name="operating-system">Windows Server 2012</tag>
        ...
      </HostProperties>
      <ReportItem port="445" protocol="tcp" pluginID="66334" ...>
        <description>...</description>
        <solution>...</solution>
        <risk_factor>Critical</risk_factor>
        ...
      </ReportItem>
    </ReportHost>
  </Report>
</NessusClientData_v2>
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import re
import hashlib

from app.adapters.base import BaseScannerAdapter, ParseError
from app.adapters.registry import AdapterRegistry
from app.adapters.dto import (
    ScanResult, 
    RawAsset, 
    RawFinding, 
    NormalizedSeverity,
    NetworkZone,
    AssetType
)


logger = logging.getLogger(__name__)


# Nessus severity mapping (risk_factor -> normalized)
NESSUS_SEVERITY_MAP = {
    "critical": NormalizedSeverity.CRITICAL,
    "high": NormalizedSeverity.HIGH,
    "medium": NormalizedSeverity.MEDIUM,
    "low": NormalizedSeverity.LOW,
    "none": NormalizedSeverity.INFO,
    "informational": NormalizedSeverity.INFO,
    "info": NormalizedSeverity.INFO,
}

# Nessus numeric severity mapping (severity attribute)
NESSUS_NUMERIC_SEVERITY_MAP = {
    "4": NormalizedSeverity.CRITICAL,
    "3": NormalizedSeverity.HIGH,
    "2": NormalizedSeverity.MEDIUM,
    "1": NormalizedSeverity.LOW,
    "0": NormalizedSeverity.INFO,
}

# OS Family detection patterns
OS_FAMILY_PATTERNS = [
    (r"windows", "Windows"),
    (r"linux", "Linux"),
    (r"ubuntu", "Linux"),
    (r"debian", "Linux"),
    (r"centos", "Linux"),
    (r"red\s*hat", "Linux"),
    (r"rhel", "Linux"),
    (r"fedora", "Linux"),
    (r"suse", "Linux"),
    (r"mac\s*os|darwin|osx", "macOS"),
    (r"freebsd", "BSD"),
    (r"openbsd", "BSD"),
    (r"netbsd", "BSD"),
    (r"solaris|sunos", "Solaris"),
    (r"aix", "AIX"),
    (r"hp-ux", "HP-UX"),
    (r"cisco\s*ios", "Cisco IOS"),
    (r"junos", "Juniper JunOS"),
    (r"vmware\s*esx", "VMware ESXi"),
]


@AdapterRegistry.register("nessus")
class NessusAdapter(BaseScannerAdapter):
    """
    Adapter for parsing Nessus scan files (.nessus format).
    
    Supports:
    - Nessus Professional
    - Nessus Essentials
    - Tenable.io exports
    - Tenable.sc exports
    """
    
    scanner_name = "nessus"
    scanner_display_name = "Nessus / Tenable"
    supported_extensions = {".nessus", ".xml"}
    supported_mime_types = {"application/xml", "text/xml"}
    
    # Plugins to skip (informational/noise)
    SKIP_PLUGIN_IDS = {
        "19506",   # Nessus Scan Information
        "10180",   # Ping the remote host
        "11219",   # Nessus SYN scanner
        "34220",   # Netstat Portscanner (SSH)
        "14272",   # Netstat Portscanner (WMI)
        "34277",   # Nessus UDP scanner
    }
    
    # Minimum severity to include (set to None to include all)
    MIN_SEVERITY_LEVEL = 0  # Include all, including Info
    
    async def validate(self, file_content: bytes, filename: str) -> bool:
        """Validate that this is a valid Nessus file."""
        try:
            content_start = file_content[:2000].decode('utf-8', errors='ignore')
            
            # Check for Nessus XML signatures
            if "NessusClientData" in content_start:
                return True
            if "<Report " in content_start and "ReportHost" in content_start:
                return True
            if "nessus" in content_start.lower() and "<Policy" in content_start:
                return True
                
            return False
        except Exception:
            return False
    
    async def parse(self, file_content: bytes, filename: str) -> ScanResult:
        """
        Parse a Nessus file and extract all findings.
        
        Args:
            file_content: Raw bytes of the .nessus file
            filename: Original filename
            
        Returns:
            ScanResult with all parsed assets and findings
        """
        result = ScanResult(
            scanner=self.scanner_name,
            findings_by_severity={s.value: 0 for s in NormalizedSeverity}
        )
        
        try:
            # Parse XML
            root = ET.fromstring(file_content)
            
            # Extract scan metadata
            self._parse_scan_metadata(root, result)
            
            # Find all ReportHost elements
            report_hosts = root.findall(".//ReportHost")
            
            if not report_hosts:
                result.warnings.append("No hosts found in scan file")
                return result
            
            result.total_hosts = len(report_hosts)
            logger.info(f"Found {result.total_hosts} hosts in Nessus file")
            
            # Process each host
            for host_elem in report_hosts:
                try:
                    asset, findings = self._parse_host(host_elem, result)
                    
                    if asset:
                        result.assets.append(asset)
                    
                    for finding in findings:
                        result.findings.append(finding)
                        result.findings_by_severity[finding.severity.value] += 1
                        
                except Exception as e:
                    host_name = host_elem.get("name", "unknown")
                    error_msg = f"Error parsing host '{host_name}': {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
            
            result.total_findings = len(result.findings)
            logger.info(
                f"Parsed {result.total_findings} findings from {result.total_hosts} hosts"
            )
            
        except ET.ParseError as e:
            raise ParseError(
                f"Invalid XML format: {str(e)}",
                scanner=self.scanner_name,
                details={"filename": filename}
            )
        except Exception as e:
            raise ParseError(
                f"Failed to parse Nessus file: {str(e)}",
                scanner=self.scanner_name,
                details={"filename": filename, "error_type": type(e).__name__}
            )
        
        return result
    
    def _parse_scan_metadata(self, root: ET.Element, result: ScanResult) -> None:
        """Extract scan-level metadata."""
        # Try to find Report element
        report = root.find(".//Report")
        if report is not None:
            result.scan_name = report.get("name")
        
        # Try to find Policy name
        policy_name = root.find(".//Policy/policyName")
        if policy_name is not None and policy_name.text:
            result.scan_policy = policy_name.text
        
        # Try to extract Nessus version from preferences
        nessus_version = root.find(".//preference[name='sc_version']/value")
        if nessus_version is not None and nessus_version.text:
            result.scanner_version = nessus_version.text
    
    def _parse_host(
        self, 
        host_elem: ET.Element, 
        result: ScanResult
    ) -> tuple[Optional[RawAsset], List[RawFinding]]:
        """
        Parse a single ReportHost element.
        
        Returns:
            Tuple of (asset, list of findings)
        """
        host_name = host_elem.get("name", "")
        
        # Parse host properties
        properties = self._parse_host_properties(host_elem)
        
        # Create asset
        asset = self._create_asset(host_name, properties, result)
        
        # Parse findings (ReportItems)
        findings = []
        for item_elem in host_elem.findall("ReportItem"):
            finding = self._parse_report_item(item_elem, asset, properties)
            if finding:
                findings.append(finding)
        
        return asset, findings
    
    def _parse_host_properties(self, host_elem: ET.Element) -> Dict[str, str]:
        """Extract all host properties as a dictionary."""
        properties = {}
        
        props_elem = host_elem.find("HostProperties")
        if props_elem is not None:
            for tag in props_elem.findall("tag"):
                name = tag.get("name", "")
                value = tag.text or ""
                if name:
                    properties[name] = value
        
        return properties
    
    def _create_asset(
        self, 
        host_name: str, 
        properties: Dict[str, str],
        result: ScanResult
    ) -> RawAsset:
        """Create a RawAsset from host properties."""
        
        # Determine IP and hostname
        ip_address = properties.get("host-ip", host_name)
        hostname = properties.get("hostname", properties.get("netbios-name", ""))
        
        # Determine OS information
        os_name = properties.get("operating-system", "")
        os_family = self._detect_os_family(os_name)
        
        # Parse timestamps
        scan_start = self._parse_timestamp(properties.get("HOST_START"))
        scan_end = self._parse_timestamp(properties.get("HOST_END"))
        
        # Determine identifier (prefer IP)
        identifier = ip_address if self._is_valid_ip(ip_address) else host_name
        
        # Determine asset type
        if self._is_valid_ip(identifier):
            asset_type = AssetType.IP
        else:
            asset_type = AssetType.HOST
        
        asset = RawAsset(
            identifier=identifier,
            asset_type=asset_type,
            ip_address=ip_address if self._is_valid_ip(ip_address) else None,
            hostname=hostname or None,
            fqdn=properties.get("host-fqdn"),
            netbios_name=properties.get("netbios-name"),
            mac_address=properties.get("mac-address"),
            os_name=os_name or None,
            os_family=os_family,
            scanner=self.scanner_name,
            scan_start=scan_start,
            scan_end=scan_end,
            metadata={
                "system_type": properties.get("system-type"),
                "traceroute_hop_0": properties.get("traceroute-hop-0"),
                "local_checks_proto": properties.get("local-checks-proto"),
                "smb_login_used": properties.get("smb-login-used"),
                "ssh_login_used": properties.get("ssh-auth-meth"),
                "credentialed_scan": properties.get("Credentialed_Scan"),
                "patch_summary_total_cves": properties.get("patch-summary-total-cves"),
            }
        )
        
        # Update scan times in result
        if scan_start and (not result.scan_start or scan_start < result.scan_start):
            result.scan_start = scan_start
        if scan_end and (not result.scan_end or scan_end > result.scan_end):
            result.scan_end = scan_end
        
        return asset
    
    def _parse_report_item(
        self, 
        item_elem: ET.Element, 
        asset: RawAsset,
        host_properties: Dict[str, str]
    ) -> Optional[RawFinding]:
        """Parse a single ReportItem (vulnerability)."""
        
        # Get basic attributes
        plugin_id = item_elem.get("pluginID", "")
        port = item_elem.get("port", "0")
        protocol = item_elem.get("protocol", "")
        service = item_elem.get("svc_name", "")
        plugin_name = item_elem.get("pluginName", "")
        plugin_family = item_elem.get("pluginFamily", "")
        severity_num = item_elem.get("severity", "0")
        
        # Skip certain plugins
        if plugin_id in self.SKIP_PLUGIN_IDS:
            return None
        
        # Skip based on minimum severity
        if int(severity_num) < self.MIN_SEVERITY_LEVEL:
            return None
        
        # Extract text elements
        def get_text(tag: str) -> Optional[str]:
            elem = item_elem.find(tag)
            return elem.text.strip() if elem is not None and elem.text else None
        
        # Get severity
        risk_factor = get_text("risk_factor") or ""
        severity = self._normalize_severity(risk_factor, severity_num)
        
        # Get description and solution
        description = get_text("description")
        solution = get_text("solution")
        synopsis = get_text("synopsis")
        
        # If no meaningful content, skip
        if not plugin_name and not description:
            return None
        
        # Get CVSS scores
        cvss_score = self._parse_float(get_text("cvss_base_score"))
        cvss_vector = get_text("cvss_vector")
        cvss3_score = self._parse_float(get_text("cvss3_base_score"))
        cvss3_vector = get_text("cvss3_vector")
        
        # Get CVEs
        cves = []
        for cve_elem in item_elem.findall("cve"):
            if cve_elem.text:
                cves.append(cve_elem.text.strip().upper())
        
        # Get CWE
        cwe = None
        cwe_elem = item_elem.find("cwe")
        if cwe_elem is not None and cwe_elem.text:
            cwe = f"CWE-{cwe_elem.text.strip()}"
        
        # Get references
        references = []
        see_also = get_text("see_also")
        if see_also:
            # Split by newlines and filter valid URLs
            for ref in see_also.split("\n"):
                ref = ref.strip()
                if ref and (ref.startswith("http://") or ref.startswith("https://")):
                    references.append(ref)
        
        # Get reference IDs
        reference_ids = {}
        
        # Bugtraq IDs
        for bid_elem in item_elem.findall("bid"):
            if bid_elem.text:
                reference_ids.setdefault("bugtraq", []).append(bid_elem.text.strip())
        
        # Microsoft security bulletins
        for msft_elem in item_elem.findall("msft"):
            if msft_elem.text:
                reference_ids.setdefault("microsoft", []).append(msft_elem.text.strip())
        
        # Other references
        xref_elem = item_elem.find("xref")
        if xref_elem is not None and xref_elem.text:
            reference_ids["xref"] = xref_elem.text.strip()
        
        # Plugin output
        plugin_output = get_text("plugin_output")
        
        # Build location string
        port_int = int(port) if port.isdigit() else 0
        location = f"{port}/{protocol}" if port_int > 0 else None
        if service and service != "general":
            location = f"{location} ({service})" if location else service
        
        # Create finding
        finding = RawFinding(
            title=plugin_name,
            description=description,
            solution=solution,
            synopsis=synopsis,
            severity=severity,
            original_severity=risk_factor or f"severity_{severity_num}",
            risk_factor=risk_factor,
            scanner=self.scanner_name,
            asset_identifier=asset.identifier,
            
            # Location
            location=location,
            port=port_int if port_int > 0 else None,
            protocol=protocol or None,
            service=service if service and service != "general" else None,
            
            # Classification
            cwe=cwe,
            cves=cves,
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            cvss3_score=cvss3_score,
            cvss3_vector=cvss3_vector,
            
            # References
            references=references,
            reference_ids=reference_ids if reference_ids else None,
            
            # Plugin info
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            plugin_family=plugin_family,
            plugin_type=get_text("plugin_type"),
            plugin_output=self._truncate(plugin_output, 10000),  # Limit output size
            
            scanner_finding_id=plugin_id,
            
            extras={
                "exploit_available": get_text("exploit_available"),
                "exploitability_ease": get_text("exploitability_ease"),
                "exploit_framework_core": get_text("exploit_framework_core"),
                "exploit_framework_metasploit": get_text("exploit_framework_metasploit"),
                "exploit_framework_canvas": get_text("exploit_framework_canvas"),
                "in_the_news": get_text("in_the_news"),
                "exploited_by_malware": get_text("exploited_by_malware"),
                "patch_publication_date": get_text("patch_publication_date"),
                "vuln_publication_date": get_text("vuln_publication_date"),
                "plugin_publication_date": get_text("plugin_publication_date"),
                "plugin_modification_date": get_text("plugin_modification_date"),
                "age_of_vuln": get_text("age_of_vuln"),
                "thorough_tests": get_text("thorough_tests"),
            }
        )
        
        # Generate fingerprint
        finding.fingerprint = self._generate_fingerprint(finding, asset)
        
        return finding
    
    def _normalize_severity(
        self, 
        risk_factor: str, 
        severity_num: str
    ) -> NormalizedSeverity:
        """Normalize Nessus severity to standard levels."""
        # Try risk_factor first (more reliable)
        if risk_factor:
            normalized = NESSUS_SEVERITY_MAP.get(risk_factor.lower())
            if normalized:
                return normalized
        
        # Fall back to numeric severity
        normalized = NESSUS_NUMERIC_SEVERITY_MAP.get(severity_num)
        if normalized:
            return normalized
        
        return NormalizedSeverity.INFO
    
    def _detect_os_family(self, os_name: str) -> Optional[str]:
        """Detect OS family from OS name string."""
        if not os_name:
            return None
        
        os_lower = os_name.lower()
        for pattern, family in OS_FAMILY_PATTERNS:
            if re.search(pattern, os_lower):
                return family
        
        return None
    
    def _generate_fingerprint(
        self, 
        finding: RawFinding, 
        asset: RawAsset
    ) -> str:
        """
        Generate a deterministic fingerprint for deduplication.
        
        Components:
        - Asset identifier (IP/hostname)
        - Plugin ID
        - Port/Protocol (if applicable)
        - CVEs (sorted)
        """
        components = [
            asset.identifier.lower(),
            finding.plugin_id or finding.title,
        ]
        
        # Add port/protocol if present
        if finding.port:
            components.append(f"{finding.port}/{finding.protocol or 'tcp'}")
        
        # Add sorted CVEs if present
        if finding.cves:
            sorted_cves = sorted(finding.cves)
            components.append(",".join(sorted_cves))
        
        fingerprint_str = "|".join(str(c) for c in components)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:32]
    
    def _parse_timestamp(self, value: Optional[str]) -> Optional[datetime]:
        """Parse Nessus timestamp format."""
        if not value:
            return None
        
        # Nessus uses format like "Fri Dec 20 10:30:45 2024"
        formats = [
            "%a %b %d %H:%M:%S %Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        
        return None
    
    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Safely parse a float value."""
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
    
    def _is_valid_ip(self, value: str) -> bool:
        """Check if value is a valid IP address."""
        if not value:
            return False
        
        # Simple IPv4 check
        parts = value.split(".")
        if len(parts) == 4:
            try:
                return all(0 <= int(p) <= 255 for p in parts)
            except ValueError:
                pass
        
        # Could add IPv6 check here
        return False
    
    def _truncate(self, value: Optional[str], max_length: int) -> Optional[str]:
        """Truncate string to max length."""
        if not value:
            return None
        if len(value) <= max_length:
            return value
        return value[:max_length - 3] + "..."
