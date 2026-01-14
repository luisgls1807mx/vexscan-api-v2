"""
VexScan API - Scans/Imports Routes
Scan file upload and processing endpoints
"""

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import io

from app.core.auth import get_current_user, require_permission, require_workspace, CurrentUser
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services.import_service import import_service
from app.schemas import (
    ScanImportResponse,
    ScanDiffResponse,
    PaginatedResponse
)

router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post("/upload")
async def upload_scan(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    network_zone: str = Form("internal"),
    force_upload: bool = Form(False, description="Force upload even if file already exists"),
    user: CurrentUser = Depends(require_permission("imports.create"))
):
    """
    Upload and process a scan file.
    
    Supported formats:
    - .nessus (Nessus/Tenable)
    - Coming soon: Invicti, Acunetix, Qualys
    
    The file is:
    1. Validated
    2. Uploaded to storage
    3. Parsed using appropriate adapter
    4. Assets and findings saved to database
    5. Duplicates handled (update last_seen, reopen if needed)
    
    Returns import summary with stats.
    """
    if not user.workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Workspace context required. Set X-Workspace-ID header."
        )
    
    # Validate file size
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise ValidationError(
            f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB"
        )
    
    # Validate extension
    filename = file.filename or "scan.nessus"
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Process scan
    result = await import_service.process_scan(
        access_token=user.access_token,
        workspace_id=user.workspace_id,
        file_content=content,
        filename=filename,
        project_id=project_id,
        network_zone=network_zone,
        force_upload=force_upload
    )
    
    return {
        "success": True,
        "message": "Scan processed successfully",
        "data": result
    }


@router.get("", response_model=PaginatedResponse)
async def list_scans(
    project_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_permission("imports.read"))
):
    """
    List scans for a project.
    
    Returns scans with finding counts (total, new, updated, closed).
    """
    result = await import_service.list_scans(
        user.access_token,
        project_id=project_id,
        page=page,
        per_page=per_page
    )
    return result


@router.get("/{scan_id}/diff", response_model=ScanDiffResponse)
async def get_scan_diff(
    scan_id: str,
    user: CurrentUser = Depends(require_permission("imports.read"))
):
    """
    Get diff between scan and previous scan.
    
    Returns:
    - new: Findings that appeared in this scan
    - resolved: Findings from previous scan not in this one
    - persistent: Findings in both scans
    - reopened: Previously closed findings that reappeared
    """
    result = await import_service.get_scan_diff(
        user.access_token,
        scan_id
    )
    return result


@router.get("/export/excel")
async def export_to_excel(
    project_id: str,
    include_info: bool = Query(False, description="Include Info-level findings"),
    user: CurrentUser = Depends(require_permission("reports.export"))
):
    """
    Export project findings to Excel.
    
    Columns:
    - Folio, Vulnerabilidad, Descripción, Severidad
    - Dirección IP, Puerto, Hostname
    - Recomendación, CVEs, CVSS, Estado
    """
    excel_bytes = await import_service.generate_excel_report(
        user.access_token,
        project_id=project_id,
        include_info=include_info
    )
    
    # Return as downloadable file
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=vulnerabilities_{project_id[:8]}.xlsx"
        }
    )
