"""
VexScan API - Import Service
Handles scan file processing, parsing, and database insertion
"""

from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime
from uuid import uuid4
import hashlib
import logging
import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from app.core.supabase import supabase
from app.core.config import settings
from app.core.exceptions import (
    ParseError, 
    StorageError, 
    RPCError, 
    DuplicateError,
    ValidationError
)
from app.adapters import AdapterRegistry, get_adapter_for_file, ScanResult
import anyio

logger = logging.getLogger(__name__)


# Excel severity colors
SEVERITY_COLORS = {
    "Critical": "FF0000",
    "High": "FF6600",
    "Medium": "FFCC00",
    "Low": "00CC00",
    "Info": "0066FF",
}


class ImportService:
    """Service for processing and importing scan files."""
    
    async def process_scan(
        self,
        access_token: str,
        workspace_id: str,
        file_content: bytes,
        filename: str,
        project_id: Optional[str] = None,
        network_zone: str = "internal",
        scanner_hint: Optional[str] = None,
        force_upload: bool = False
    ) -> Dict[str, Any]:
        """
        Complete scan import workflow:
        1. Validate file
        2. Check for duplicates (skip if force_upload=True)
        3. Upload to storage
        4. Parse using adapter
        5. Save to database (assets + findings)
        6. Return summary
        
        Args:
            access_token: User's JWT token
            workspace_id: Target workspace
            file_content: Raw file bytes
            filename: Original filename
            project_id: Optional project to associate
            network_zone: "internal" or "external"
            scanner_hint: Optional hint about scanner type
            force_upload: If True, skip duplicate check and allow re-upload
            
        Returns:
            Import result with stats and scan_import_id
        """
        # 1. Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        
        # 2. Check for duplicate (skip if force_upload)
        # Verificación ahora es por PROYECTO, no por workspace
        if not force_upload and project_id:
            is_duplicate = await self._check_duplicate(
                access_token, project_id, file_hash
            )
            if is_duplicate:
                raise DuplicateError("Scan file", filename)
        
        # 3. Detect and validate scanner
        adapter = get_adapter_for_file(filename, file_content, scanner_hint)
        logger.info(f"Using adapter: {adapter.scanner_name}")
        
        is_valid = await adapter.validate(file_content, filename)
        if not is_valid:
            raise ParseError(
                f"Invalid {adapter.scanner_name} file format",
                scanner=adapter.scanner_name,
                filename=filename
            )
        
        # 4. Upload to storage
        storage_path = await self._upload_to_storage(
            workspace_id, file_content, filename
        )
        
        # 5. Create scan_import record
        scan_import = await self._create_scan_import(
            access_token=access_token,
            workspace_id=workspace_id,
            project_id=project_id,
            filename=filename,
            storage_path=storage_path,
            file_size=file_size,
            file_hash=file_hash,
            scanner=adapter.scanner_name,
            network_zone=network_zone,
            force_upload=force_upload
        )
        
        scan_import_id = scan_import['id']
        
        try:
            # 6. Parse file
            scan_result = await adapter.parse(file_content, filename)
            
            # 7. Save to database
            summary = await self._save_scan_results(
                access_token=access_token,
                workspace_id=workspace_id,
                project_id=project_id,
                scan_import_id=scan_import_id,
                scan_result=scan_result,
                network_zone=network_zone
            )
            
            # 8. Update scan_import with results
            await self._update_scan_import_status(
                access_token=access_token,
                scan_import_id=scan_import_id,
                status="processed",
                summary=summary,
                scan_result=scan_result
            )
            
            return {
                "scan_import_id": scan_import_id,
                "scanner": adapter.scanner_name,
                "status": "processed",
                **summary,
                "scan_info": {
                    "name": scan_result.scan_name,
                    "policy": scan_result.scan_policy,
                    "start": scan_result.scan_start.isoformat() if scan_result.scan_start else None,
                    "end": scan_result.scan_end.isoformat() if scan_result.scan_end else None,
                }
            }
            
        except Exception as e:
            # Update status to failed
            await self._update_scan_import_status(
                access_token=access_token,
                scan_import_id=scan_import_id,
                status="failed",
                error_message=str(e)
            )
            raise
    
    async def _check_duplicate(
        self,
        access_token: str,
        project_id: str,
        file_hash: str
    ) -> bool:
        """Check if file hash already exists in the project."""
        try:
            # Query scan_imports for existing hash in the PROJECT (not workspace)
            supabase.anon.postgrest.auth(token=access_token)
            result = supabase.anon.table('scan_imports').select('id').eq(
                'project_id', project_id
            ).eq('file_hash', file_hash).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False
    
    async def _upload_to_storage(
        self,
        workspace_id: str,
        file_content: bytes,
        filename: str
    ) -> str:
        """Upload scan file to Supabase Storage."""
        try:
            # Generate unique path
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid4())[:8]
            storage_path = f"{workspace_id}/scans/{timestamp}_{unique_id}_{filename}"
            
            # Upload
            supabase.service.storage.from_(settings.STORAGE_BUCKET).upload(
                storage_path,
                file_content,
                {"content-type": "application/octet-stream"}
            )
            
            return storage_path
            
        except Exception as e:
            logger.error(f"Storage upload error: {e}")
            raise StorageError(f"Failed to upload file: {str(e)}", "upload")
    
    async def _create_scan_import(
        self,
        access_token: str,
        workspace_id: str,
        project_id: Optional[str],
        filename: str,
        storage_path: str,
        file_size: int,
        file_hash: str,
        scanner: str,
        network_zone: str,
        force_upload: bool = False
    ) -> Dict[str, Any]:
        """Create scan_import record."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_create_scan_import',
                access_token,
                {
                    'p_project_id': project_id,
                    'p_file_name': filename,
                    'p_storage_path': storage_path,
                    'p_file_size': file_size,
                    'p_file_hash': file_hash,
                    'p_scanner': scanner,
                    'p_network_zone': network_zone,
                    'p_force_upload': force_upload
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error creating scan_import: {e}")
            raise RPCError('fn_create_scan_import', str(e))
    
    async def _save_scan_results(
        self,
        access_token: str,
        workspace_id: str,
        project_id: Optional[str],
        scan_import_id: str,
        scan_result: ScanResult,
        network_zone: str
    ) -> Dict[str, Any]:
        """
        Save parsed scan results to database.
        
        Returns summary with counts.
        """
        summary = {
            "assets_created": 0,
            "assets_updated": 0,
            "findings_created": 0,
            "findings_updated": 0,
            "findings_reopened": 0,
            "hosts_total": scan_result.total_hosts,
            "findings_total": scan_result.total_findings,
            "findings_by_severity": scan_result.findings_by_severity
        }
        
        # Apply token to postgrest for table queries
        supabase.anon.postgrest.auth(token=access_token)
        
        # Create asset lookup
        asset_map = {}
        
        # 1. Process assets
        for raw_asset in scan_result.assets:
            asset_data = {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "identifier": raw_asset.identifier,
                "name": raw_asset.name or raw_asset.hostname or raw_asset.ip_address,
                "hostname": raw_asset.hostname,
                "ip_address": raw_asset.ip_address,
                "asset_type": raw_asset.asset_type.value if hasattr(raw_asset.asset_type, 'value') else raw_asset.asset_type,
                "operating_system": raw_asset.os_name,
                "is_manual": False,
                "last_seen": datetime.utcnow().isoformat()
            }
            
            # Upsert asset
            try:
                result = supabase.anon.table('assets').upsert(
                    asset_data,
                    on_conflict='workspace_id,identifier'
                ).execute()
                
                if result.data:
                    asset_map[raw_asset.identifier] = result.data[0]['id']
                    summary["assets_created"] += 1
                    
            except Exception as e:
                logger.warning(f"Error upserting asset {raw_asset.identifier}: {e}")
        
        # 2. Process findings
        for raw_finding in scan_result.findings:
            asset_id = asset_map.get(raw_finding.asset_identifier)
            
            finding_data = {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "asset_id": asset_id,
                "scanner": raw_finding.scanner,
                "scanner_finding_id": raw_finding.scanner_finding_id or raw_finding.plugin_id,
                "fingerprint": raw_finding.fingerprint,
                "title": raw_finding.title,
                "description": raw_finding.description,
                "solution": raw_finding.solution,
                "location": raw_finding.location or self._build_location(raw_finding),
                "severity": raw_finding.severity.value if hasattr(raw_finding.severity, 'value') else raw_finding.severity,
                "original_severity": raw_finding.original_severity,
                "hostname": raw_finding.asset_identifier if not raw_finding.asset_identifier.replace('.', '').isdigit() else None,
                "ip_address": raw_finding.asset_identifier if raw_finding.asset_identifier.replace('.', '').isdigit() else None,
                "port": raw_finding.port,
                "protocol": raw_finding.protocol,
                "service": raw_finding.service,
                "cves": raw_finding.cves if raw_finding.cves else None,
                "cvss_score": raw_finding.cvss3_score or raw_finding.cvss_score,
                "cvss_vector": raw_finding.cvss3_vector or raw_finding.cvss_vector,
                "cwe": raw_finding.cwe,
                "extras": raw_finding.extras,
                "last_seen": datetime.utcnow().isoformat()
            }
            
            try:
                # Check if finding exists by fingerprint EN EL PROYECTO
                existing = supabase.anon.table('findings').select('id,status').eq(
                    'project_id', project_id
                ).eq('fingerprint', raw_finding.fingerprint).execute()
                
                if existing.data:
                    # Update existing
                    finding_id = existing.data[0]['id']
                    old_status = existing.data[0]['status']
                    
                    update_data = {
                        "last_seen": datetime.utcnow().isoformat()
                    }
                    
                    # Reopen if was closed
                    if old_status in ['Mitigated', 'Accepted Risk', 'False Positive', 'Not Observed']:
                        update_data["status"] = "Open"
                        update_data["is_reopened"] = True
                        summary["findings_reopened"] += 1
                    
                    supabase.anon.table('findings').update(update_data).eq('id', finding_id).execute()
                    summary["findings_updated"] += 1
                    
                    # Record occurrence
                    supabase.anon.table('finding_occurrences').insert({
                        "finding_id": finding_id,
                        "scan_import_id": scan_import_id,
                        "port": raw_finding.port,
                        "protocol": raw_finding.protocol,
                        "raw_output": raw_finding.plugin_output[:5000] if raw_finding.plugin_output else None
                    }).execute()
                    
                else:
                    # Insert new finding
                    finding_data["first_seen"] = datetime.utcnow().isoformat()
                    finding_data["status"] = "Open"
                    
                    result = supabase.anon.table('findings').insert(finding_data).execute()
                    
                    if result.data:
                        finding_id = result.data[0]['id']
                        summary["findings_created"] += 1
                        
                        # Record occurrence
                        supabase.anon.table('finding_occurrences').insert({
                            "finding_id": finding_id,
                            "scan_import_id": scan_import_id,
                            "port": raw_finding.port,
                            "protocol": raw_finding.protocol
                        }).execute()
                        
            except Exception as e:
                logger.warning(f"Error processing finding {raw_finding.title[:50]}: {e}")
        
        return summary
    
    def _build_location(self, finding) -> str:
        """Build location string from finding data."""
        parts = []
        if finding.asset_identifier:
            parts.append(finding.asset_identifier)
        if finding.port:
            parts.append(f":{finding.port}")
        return "".join(parts) if parts else ""
    
    async def _update_scan_import_status(
        self,
        access_token: str,
        scan_import_id: str,
        status: str,
        summary: Optional[Dict[str, Any]] = None,
        scan_result: Optional[ScanResult] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update scan_import status and stats."""
        # Use service role to avoid JWT expiration issues during long processing
        update_data = {
            "status": status,
            "processed_at": datetime.utcnow().isoformat() if status == "processed" else None
        }
        
        if error_message:
            update_data["error_message"] = error_message
        
        if summary:
            update_data["findings_total"] = summary.get("findings_total", 0)
            update_data["findings_new"] = summary.get("findings_created", 0)
            update_data["findings_updated"] = summary.get("findings_updated", 0)
            update_data["hosts_total"] = summary.get("hosts_total", 0)
        
        if scan_result:
            update_data["scan_started_at"] = scan_result.scan_start.isoformat() if scan_result.scan_start else None
            update_data["scan_finished_at"] = scan_result.scan_end.isoformat() if scan_result.scan_end else None
            update_data["scanner_version"] = scan_result.scanner_version
        
        # Use service role to avoid JWT expiration
        supabase.service.table('scan_imports').update(update_data).eq('id', scan_import_id).execute()
    
    async def list_scans(
        self,
        access_token: str,
        project_id: str,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """List scans for a project."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_list_scans',
                access_token,
                {
                    'p_project_id': project_id,
                    'p_page': page,
                    'p_per_page': per_page
                }
            ))
            return result
        except Exception as e:
            logger.error(f"Error listing scans: {e}")
            raise RPCError('fn_list_scans', str(e))
    
    async def get_scan_diff(
        self,
        access_token: str,
        scan_id: str
    ) -> Dict[str, Any]:
        """Get diff between scan and previous scan."""
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
                'fn_get_scan_diff',
                access_token,
                {'p_scan_id': scan_id}
            ))
            return result
        except Exception as e:
            logger.error(f"Error getting scan diff: {e}")
            raise RPCError('fn_get_scan_diff', str(e))
    
    async def generate_excel_report(
        self,
        access_token: str,
        project_id: str,
        include_info: bool = False
    ) -> bytes:
        """Generate Excel report for project findings."""
        # Get all findings
        findings_result = await anyio.to_thread.run_sync(lambda: supabase.rpc_with_token(
            'fn_list_findings',
            access_token,
            {
                'p_project_id': project_id,
                'p_page': 1,
                'p_per_page': 10000  # Get all
            }
        ))
        
        findings = findings_result.get('data', [])
        
        if not include_info:
            findings = [f for f in findings if f.get('severity') != 'Info']
        
        # Sort by severity
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
        findings.sort(key=lambda f: severity_order.get(f.get('severity', 'Info'), 5))
        
        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Vulnerabilidades"
        
        # Headers
        headers = [
            "Folio", "Vulnerabilidad", "Descripción", "Severidad",
            "Dirección IP", "Puerto", "Hostname", "Recomendación",
            "CVEs", "CVSS", "Estado"
        ]
        
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
        
        # Data rows
        for row_num, finding in enumerate(findings, 2):
            ws.cell(row=row_num, column=1, value=finding.get('folio', ''))
            ws.cell(row=row_num, column=2, value=finding.get('title', ''))
            ws.cell(row=row_num, column=3, value=finding.get('description', '')[:500] if finding.get('description') else '')
            
            severity = finding.get('severity', 'Info')
            severity_cell = ws.cell(row=row_num, column=4, value=severity)
            if severity in SEVERITY_COLORS:
                severity_cell.fill = PatternFill(
                    start_color=SEVERITY_COLORS[severity],
                    end_color=SEVERITY_COLORS[severity],
                    fill_type="solid"
                )
                if severity in ["Critical", "High"]:
                    severity_cell.font = Font(color="FFFFFF")
            
            ws.cell(row=row_num, column=5, value=finding.get('ip_address', ''))
            ws.cell(row=row_num, column=6, value=finding.get('port', ''))
            ws.cell(row=row_num, column=7, value=finding.get('hostname', ''))
            ws.cell(row=row_num, column=8, value=finding.get('solution', '')[:500] if finding.get('solution') else '')
            
            cves = finding.get('cves', [])
            ws.cell(row=row_num, column=9, value=', '.join(cves) if cves else '')
            ws.cell(row=row_num, column=10, value=finding.get('cvss_score', ''))
            ws.cell(row=row_num, column=11, value=finding.get('status', ''))
        
        # Column widths
        widths = [10, 50, 60, 12, 15, 8, 25, 50, 30, 8, 15]
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[chr(64 + col)].width = width
        
        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        return output.getvalue()


import_service = ImportService()
