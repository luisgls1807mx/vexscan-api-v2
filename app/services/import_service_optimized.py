"""
VexScan API - Optimized Import Service
Experimental service with optimized scan processing approaches
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4
import hashlib
import logging

from app.core.supabase import supabase
from app.core.config import settings
from app.core.exceptions import (
    ParseError, 
    StorageError, 
    RPCError, 
    DuplicateError,
    ValidationError
)
from app.adapters import get_adapter_for_file, ScanResult
import anyio
import asyncio

logger = logging.getLogger(__name__)


class ImportServiceOptimized:
    """
    Optimized service for processing scan files.
    Contains 3 experimental approaches for comparison.
    """
    
    # =========================================================================
    # APPROACH 1: Batch Inserts with Service Role
    # Endpoint: POST /api/v1/scans-experimental/v1-batch-service-role
    # =========================================================================
    
    async def process_scan_v1_batch_service_role(
        self,
        access_token: str,
        workspace_id: str,
        file_content: bytes,
        filename: str,
        project_id: Optional[str] = None,
        network_zone: str = "internal",
        force_upload: bool = False
    ) -> Dict[str, Any]:
        """
        APPROACH 1: Uses service_role for DB operations (no JWT expiration).
        Processes assets and findings in batches.
        
        Key differences from original:
        - Uses service_role instead of user token for inserts
        - Batch inserts (groups of 100 records)
        - Validates permissions once at the start
        """
        start_time = datetime.utcnow()
        
        # 1. Validate permissions using user token (only once at start)
        # This ensures the user has permission before we switch to service_role
        user_id = await self._get_user_id_from_token(access_token)
        if not user_id:
            raise ValidationError("Token inválido o expirado")
        
        has_permission = await self._validate_user_permission(access_token, workspace_id)
        if not has_permission:
            raise ValidationError("No tienes permiso para subir scans a este workspace")
        
        # 2. Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        
        # 3. Check duplicate (if not force) - Ahora por PROYECTO
        if not force_upload and project_id:
            is_duplicate = await self._check_duplicate_service_role(project_id, file_hash)
            if is_duplicate:
                raise DuplicateError("Scan file", filename)
        
        # 4. Detect and validate scanner
        adapter = get_adapter_for_file(filename, file_content)
        is_valid = await adapter.validate(file_content, filename)
        if not is_valid:
            raise ParseError(f"Invalid {adapter.scanner_name} file format", scanner=adapter.scanner_name, filename=filename)
        
        # 5. Upload to storage
        storage_path = await self._upload_to_storage(workspace_id, file_content, filename)
        
        # 6. Create scan_import record using service_role
        scan_import = await self._create_scan_import_service_role(
            workspace_id=workspace_id,
            project_id=project_id,
            filename=filename,
            storage_path=storage_path,
            file_size=file_size,
            file_hash=file_hash,
            scanner=adapter.scanner_name,
            network_zone=network_zone,
            uploaded_by=user_id
        )
        
        scan_import_id = scan_import['id']
        
        try:
            # 7. Parse file
            scan_result = await adapter.parse(file_content, filename)
            
            # 8. Save using BATCH INSERTS with service_role
            summary = await self._save_scan_results_batch(
                workspace_id=workspace_id,
                project_id=project_id,
                scan_import_id=scan_import_id,
                scan_result=scan_result,
                batch_size=100  # Process 100 records at a time
            )
            
            # 9. Update scan_import status
            await self._update_scan_import_status_service_role(
                scan_import_id=scan_import_id,
                status="processed",
                summary=summary,
                scan_result=scan_result
            )
            
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            
            return {
                "scan_import_id": scan_import_id,
                "scanner": adapter.scanner_name,
                "status": "processed",
                "approach": "v1_batch_service_role",
                "processing_time_seconds": processing_time,
                **summary,
                "scan_info": {
                    "name": scan_result.scan_name,
                    "policy": scan_result.scan_policy,
                    "start": scan_result.scan_start.isoformat() if scan_result.scan_start else None,
                    "end": scan_result.scan_end.isoformat() if scan_result.scan_end else None,
                }
            }
            
        except Exception as e:
            await self._update_scan_import_status_service_role(
                scan_import_id=scan_import_id,
                status="failed",
                error_message=str(e)
            )
            raise
    
    # =========================================================================
    # APPROACH 2: Async Two-Phase Processing
    # Endpoint: POST /api/v1/scans-experimental/v2-async-queue
    # =========================================================================
    
    async def process_scan_v2_async_queue(
        self,
        access_token: str,
        workspace_id: str,
        file_content: bytes,
        filename: str,
        project_id: Optional[str] = None,
        network_zone: str = "internal",
        force_upload: bool = False
    ) -> Dict[str, Any]:
        """
        APPROACH 2: Two-phase async processing.
        Phase 1 (this method): Upload file, create queued record, return immediately.
        Phase 2 (background): Process file asynchronously.
        
        Returns immediately with job_id for status polling.
        """
        start_time = datetime.utcnow()
        
        # 1. Validate permissions and get user_id
        user_id = await self._get_user_id_from_token(access_token)
        if not user_id:
            raise ValidationError("Token inválido o expirado")
        
        has_permission = await self._validate_user_permission(access_token, workspace_id)
        if not has_permission:
            raise ValidationError("No tienes permiso para subir scans a este workspace")
        
        # 2. Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        
        # 3. Check duplicate - Ahora por PROYECTO
        if not force_upload and project_id:
            is_duplicate = await self._check_duplicate_service_role(project_id, file_hash)
            if is_duplicate:
                raise DuplicateError("Scan file", filename)
        
        # 4. Detect scanner (quick validation)
        adapter = get_adapter_for_file(filename, file_content)
        is_valid = await adapter.validate(file_content, filename)
        if not is_valid:
            raise ParseError(f"Invalid {adapter.scanner_name} file format", scanner=adapter.scanner_name, filename=filename)
        
        # 5. Upload to storage
        storage_path = await self._upload_to_storage(workspace_id, file_content, filename)
        
        # 6. Create scan_import with status "queued"
        scan_import = await self._create_scan_import_service_role(
            workspace_id=workspace_id,
            project_id=project_id,
            filename=filename,
            storage_path=storage_path,
            file_size=file_size,
            file_hash=file_hash,
            scanner=adapter.scanner_name,
            network_zone=network_zone,
            uploaded_by=user_id,
            status="queued"
        )
        
        job_id = scan_import['id']
        
        # 7. Start background processing (fire and forget)
        # Using anyio to spawn a background task
        async def process_in_background():
            try:
                scan_result = await adapter.parse(file_content, filename)
                summary = await self._save_scan_results_batch(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    scan_import_id=job_id,
                    scan_result=scan_result,
                    batch_size=100
                )
                await self._update_scan_import_status_service_role(
                    scan_import_id=job_id,
                    status="processed",
                    summary=summary,
                    scan_result=scan_result
                )
            except Exception as e:
                logger.error(f"Background processing failed for job {job_id}: {e}")
                await self._update_scan_import_status_service_role(
                    scan_import_id=job_id,
                    status="failed",
                    error_message=str(e)
                )
        
        # Spawn background task using asyncio.create_task
        asyncio.create_task(process_in_background())
        
        upload_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Return immediately with job_id
        return {
            "job_id": job_id,
            "status": "queued",
            "approach": "v2_async_queue",
            "upload_time_seconds": upload_time,
            "message": "File uploaded and queued for processing. Poll /jobs/{job_id} for status.",
            "scanner": adapter.scanner_name
        }
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of an async processing job."""
        try:
            result = supabase.service.table('scan_imports').select(
                'id, status, file_name, scanner, findings_total, findings_new, '
                'findings_updated, hosts_total, error_message, created_at, processed_at'
            ).eq('id', job_id).execute()
            
            if not result.data:
                return {"error": "Job not found", "job_id": job_id}
            
            job = result.data[0]
            return {
                "job_id": job['id'],
                "status": job['status'],
                "file_name": job['file_name'],
                "scanner": job['scanner'],
                "findings_total": job.get('findings_total'),
                "findings_new": job.get('findings_new'),
                "findings_updated": job.get('findings_updated'),
                "hosts_total": job.get('hosts_total'),
                "error_message": job.get('error_message'),
                "created_at": job['created_at'],
                "processed_at": job.get('processed_at')
            }
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {"error": str(e), "job_id": job_id}
    
    # =========================================================================
    # APPROACH 3: Bulk Insert via RPC
    # Endpoint: POST /api/v1/scans-experimental/v3-bulk-rpc
    # =========================================================================
    
    async def process_scan_v3_bulk_rpc(
        self,
        access_token: str,
        workspace_id: str,
        file_content: bytes,
        filename: str,
        project_id: Optional[str] = None,
        network_zone: str = "internal",
        force_upload: bool = False
    ) -> Dict[str, Any]:
        """
        APPROACH 3: Single RPC call for bulk insert.
        Parses file in Python, sends all data to RPC for atomic transaction.
        
        Key differences:
        - All DB operations in a single RPC call
        - Atomic transaction (all or nothing)
        - Maximum DB performance
        """
        start_time = datetime.utcnow()
        
        # 1. Validate permissions and get user_id
        user_id = await self._get_user_id_from_token(access_token)
        if not user_id:
            raise ValidationError("Token inválido o expirado")
        
        has_permission = await self._validate_user_permission(access_token, workspace_id)
        if not has_permission:
            raise ValidationError("No tienes permiso para subir scans a este workspace")
        
        # 2. Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        
        # 3. Check duplicate - Ahora por PROYECTO
        if not force_upload and project_id:
            is_duplicate = await self._check_duplicate_service_role(project_id, file_hash)
            if is_duplicate:
                raise DuplicateError("Scan file", filename)
        
        # 4. Detect and validate scanner
        adapter = get_adapter_for_file(filename, file_content)
        is_valid = await adapter.validate(file_content, filename)
        if not is_valid:
            raise ParseError(f"Invalid {adapter.scanner_name} file format", scanner=adapter.scanner_name, filename=filename)
        
        # 5. Upload to storage
        storage_path = await self._upload_to_storage(workspace_id, file_content, filename)
        
        # 6. Parse file
        parse_start = datetime.utcnow()
        scan_result = await adapter.parse(file_content, filename)
        parse_time = (datetime.utcnow() - parse_start).total_seconds()
        
        # 7. Prepare data for RPC
        assets_data = []
        for asset in scan_result.assets:
            assets_data.append({
                "identifier": asset.identifier,
                "name": asset.name or asset.hostname or asset.ip_address,
                "hostname": asset.hostname,
                "ip_address": asset.ip_address,
                "asset_type": asset.asset_type.value if hasattr(asset.asset_type, 'value') else asset.asset_type,
                "operating_system": asset.os_name
            })
        
        findings_data = []
        for finding in scan_result.findings:
            findings_data.append({
                "scanner": finding.scanner,
                "scanner_finding_id": finding.scanner_finding_id or finding.plugin_id,
                "fingerprint": finding.fingerprint,
                "title": finding.title,
                "description": finding.description[:5000] if finding.description else None,
                "solution": finding.solution[:5000] if finding.solution else None,
                "severity": finding.severity.value if hasattr(finding.severity, 'value') else finding.severity,
                "original_severity": finding.original_severity,
                "asset_identifier": finding.asset_identifier,
                "port": finding.port,
                "protocol": finding.protocol,
                "service": finding.service,
                "cves": finding.cves if finding.cves else None,
                "cvss_score": finding.cvss3_score or finding.cvss_score,
                "cvss_vector": finding.cvss3_vector or finding.cvss_vector,
                "cwe": finding.cwe,
                "plugin_output": finding.plugin_output[:2000] if finding.plugin_output else None
            })
        
        # 8. Call bulk RPC
        rpc_start = datetime.utcnow()
        try:
            result = await anyio.to_thread.run_sync(lambda: supabase.service.rpc(
                'fn_v3_bulk_insert_scan_data',
                {
                    'p_workspace_id': workspace_id,
                    'p_project_id': project_id,
                    'p_file_name': filename,
                    'p_storage_path': storage_path,
                    'p_file_size': file_size,
                    'p_file_hash': file_hash,
                    'p_scanner': adapter.scanner_name,
                    'p_network_zone': network_zone,
                    'p_uploaded_by': user_id,  # Añadido para evitar NOT NULL
                    'p_scan_name': scan_result.scan_name,
                    'p_scan_start': scan_result.scan_start.isoformat() if scan_result.scan_start else None,
                    'p_scan_end': scan_result.scan_end.isoformat() if scan_result.scan_end else None,
                    'p_assets': assets_data,
                    'p_findings': findings_data
                }
            ).execute())
            
            rpc_result = result.data if hasattr(result, 'data') else result
        except Exception as e:
            logger.error(f"Bulk RPC error: {e}")
            raise RPCError('fn_v3_bulk_insert_scan_data', str(e))
        
        rpc_time = (datetime.utcnow() - rpc_start).total_seconds()
        end_time = datetime.utcnow()
        total_time = (end_time - start_time).total_seconds()
        
        return {
            "scan_import_id": rpc_result.get('scan_import_id') if isinstance(rpc_result, dict) else None,
            "scanner": adapter.scanner_name,
            "status": "processed",
            "approach": "v3_bulk_rpc",
            "timing": {
                "parse_seconds": parse_time,
                "rpc_seconds": rpc_time,
                "total_seconds": total_time
            },
            "assets_count": len(assets_data),
            "findings_count": len(findings_data),
            "rpc_result": rpc_result,
            "scan_info": {
                "name": scan_result.scan_name,
                "policy": scan_result.scan_policy,
                "start": scan_result.scan_start.isoformat() if scan_result.scan_start else None,
                "end": scan_result.scan_end.isoformat() if scan_result.scan_end else None,
            }
        }
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    async def _validate_user_permission(self, access_token: str, workspace_id: str) -> bool:
        """Validate user has permission to upload to workspace."""
        try:
            supabase.anon.postgrest.auth(token=access_token)
            result = supabase.anon.table('workspace_members').select('id').eq(
                'workspace_id', workspace_id
            ).execute()
            return len(result.data) > 0
        except:
            return False
    
    async def _get_user_id_from_token(self, access_token: str) -> Optional[str]:
        """Extract user_id from access token."""
        try:
            supabase.anon.postgrest.auth(token=access_token)
            user_response = supabase.anon.auth.get_user(access_token)
            if user_response and user_response.user:
                return str(user_response.user.id)
            return None
        except Exception as e:
            logger.warning(f"Error extracting user_id from token: {e}")
            return None
    
    async def _check_duplicate_service_role(self, project_id: str, file_hash: str) -> bool:
        """Check duplicate using service_role (no JWT issues). Now checks by PROJECT."""
        try:
            result = supabase.service.table('scan_imports').select('id').eq(
                'project_id', project_id
            ).eq('file_hash', file_hash).execute()
            return len(result.data) > 0
        except:
            return False
    
    async def _upload_to_storage(self, workspace_id: str, file_content: bytes, filename: str) -> str:
        """Upload scan file to Supabase Storage."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid4())[:8]
            storage_path = f"{workspace_id}/scans/{timestamp}_{unique_id}_{filename}"
            
            supabase.service.storage.from_(settings.STORAGE_BUCKET).upload(
                storage_path,
                file_content,
                {"content-type": "application/octet-stream"}
            )
            return storage_path
        except Exception as e:
            logger.error(f"Storage upload error: {e}")
            raise StorageError(f"Failed to upload file: {str(e)}", "upload")
    
    async def _create_scan_import_service_role(
        self,
        workspace_id: str,
        project_id: Optional[str],
        filename: str,
        storage_path: str,
        file_size: int,
        file_hash: str,
        scanner: str,
        network_zone: str,
        uploaded_by: str,
        status: str = "processing"
    ) -> Dict[str, Any]:
        """Create scan_import using service_role."""
        try:
            result = supabase.service.table('scan_imports').insert({
                'workspace_id': workspace_id,
                'project_id': project_id,
                'file_name': filename,
                'storage_path': storage_path,
                'file_size': file_size,
                'file_hash': file_hash,
                'scanner': scanner,
                'network_zone': network_zone,
                'uploaded_by': uploaded_by,
                'status': status
            }).execute()
            return result.data[0]
        except Exception as e:
            logger.error(f"Error creating scan_import: {e}")
            raise RPCError('create_scan_import', str(e))
    
    async def _save_scan_results_batch(
        self,
        workspace_id: str,
        project_id: Optional[str],
        scan_import_id: str,
        scan_result: ScanResult,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """Save scan results using batch inserts with service_role."""
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
        
        asset_map = {}
        
        # Process assets in batches
        asset_batches = [scan_result.assets[i:i + batch_size] for i in range(0, len(scan_result.assets), batch_size)]
        
        for batch in asset_batches:
            assets_to_upsert = []
            for raw_asset in batch:
                assets_to_upsert.append({
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
                })
            
            try:
                result = supabase.service.table('assets').upsert(
                    assets_to_upsert,
                    on_conflict='workspace_id,identifier'
                ).execute()
                
                for item in result.data:
                    asset_map[item['identifier']] = item['id']
                    summary["assets_created"] += 1
            except Exception as e:
                logger.warning(f"Error batch upserting assets: {e}")
        
        # Process findings in batches
        finding_batches = [scan_result.findings[i:i + batch_size] for i in range(0, len(scan_result.findings), batch_size)]
        
        for batch in finding_batches:
            findings_to_insert = []
            for raw_finding in batch:
                asset_id = asset_map.get(raw_finding.asset_identifier)
                
                # Check if finding exists - Ahora por PROYECTO
                try:
                    existing = supabase.service.table('findings').select('id,status').eq(
                        'project_id', project_id
                    ).eq('fingerprint', raw_finding.fingerprint).execute()
                    
                    if existing.data:
                        # Update existing finding
                        finding_id = existing.data[0]['id']
                        old_status = existing.data[0]['status']
                        
                        update_data = {"last_seen": datetime.utcnow().isoformat()}
                        
                        if old_status in ['Mitigated', 'Accepted Risk', 'False Positive', 'Not Observed']:
                            update_data["status"] = "Open"
                            update_data["is_reopened"] = True
                            summary["findings_reopened"] += 1
                        
                        supabase.service.table('findings').update(update_data).eq('id', finding_id).execute()
                        summary["findings_updated"] += 1
                        
                        # Record occurrence
                        supabase.service.table('finding_occurrences').insert({
                            "finding_id": finding_id,
                            "scan_import_id": scan_import_id,
                            "port": raw_finding.port,
                            "protocol": raw_finding.protocol
                        }).execute()
                    else:
                        # Prepare for batch insert
                        findings_to_insert.append({
                            "workspace_id": workspace_id,
                            "project_id": project_id,
                            "asset_id": asset_id,
                            "scanner": raw_finding.scanner,
                            "scanner_finding_id": raw_finding.scanner_finding_id or raw_finding.plugin_id,
                            "fingerprint": raw_finding.fingerprint,
                            "title": raw_finding.title,
                            "description": raw_finding.description,
                            "solution": raw_finding.solution,
                            "severity": raw_finding.severity.value if hasattr(raw_finding.severity, 'value') else raw_finding.severity,
                            "original_severity": raw_finding.original_severity,
                            "hostname": raw_finding.asset_identifier if raw_finding.asset_identifier and not raw_finding.asset_identifier.replace('.', '').isdigit() else None,
                            "ip_address": raw_finding.asset_identifier if raw_finding.asset_identifier and raw_finding.asset_identifier.replace('.', '').isdigit() else None,
                            "port": raw_finding.port,
                            "protocol": raw_finding.protocol,
                            "service": raw_finding.service,
                            "cves": raw_finding.cves if raw_finding.cves else None,
                            "cvss_score": raw_finding.cvss3_score or raw_finding.cvss_score,
                            "cvss_vector": raw_finding.cvss3_vector or raw_finding.cvss_vector,
                            "cwe": raw_finding.cwe,
                            "first_seen": datetime.utcnow().isoformat(),
                            "last_seen": datetime.utcnow().isoformat(),
                            "status": "Open"
                        })
                except Exception as e:
                    logger.warning(f"Error processing finding {raw_finding.title[:50]}: {e}")
            
            # Batch insert new findings
            if findings_to_insert:
                try:
                    result = supabase.service.table('findings').insert(findings_to_insert).execute()
                    summary["findings_created"] += len(result.data)
                    
                    # Create occurrences for new findings
                    occurrences = []
                    for finding in result.data:
                        occurrences.append({
                            "finding_id": finding['id'],
                            "scan_import_id": scan_import_id,
                            "port": finding.get('port'),
                            "protocol": finding.get('protocol')
                        })
                    
                    if occurrences:
                        supabase.service.table('finding_occurrences').insert(occurrences).execute()
                except Exception as e:
                    logger.warning(f"Error batch inserting findings: {e}")
        
        return summary
    
    async def _update_scan_import_status_service_role(
        self,
        scan_import_id: str,
        status: str,
        summary: Optional[Dict[str, Any]] = None,
        scan_result: Optional[ScanResult] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update scan_import status using service_role."""
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
        
        supabase.service.table('scan_imports').update(update_data).eq('id', scan_import_id).execute()


# Singleton instance
import_service_optimized = ImportServiceOptimized()
