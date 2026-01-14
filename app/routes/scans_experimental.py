"""
VexScan API - Experimental Scans Routes
Experimental endpoints for testing optimized scan processing approaches
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import Optional

from app.core.auth import get_current_user, require_permission, CurrentUser
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services.import_service_optimized import import_service_optimized

router = APIRouter(prefix="/scans-experimental", tags=["Scans Experimental"])


# =============================================================================
# APPROACH 1: Batch Inserts with Service Role
# Uses service_role for DB operations (no JWT expiration)
# =============================================================================

@router.post("/v1-batch-service-role")
async def upload_scan_v1_batch_service_role(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    network_zone: str = Form("internal"),
    force_upload: bool = Form(False),
    user: CurrentUser = Depends(require_permission("imports.create"))
):
    """
    **APPROACH 1: Batch + Service Role**
    
    Uses service_role for database operations to avoid JWT expiration.
    Processes assets and findings in batches of 100 records.
    
    **Advantages:**
    - ✅ No JWT expiration during processing
    - ✅ Better performance with batch inserts
    - ✅ Simple implementation
    
    **Disadvantages:**
    - ⚠️ Uses service_role (bypasses RLS)
    - ⚠️ Validates permissions only at start
    
    **Response includes:**
    - `processing_time_seconds`: Total processing time
    - `approach`: "v1_batch_service_role"
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
    
    # Process using optimized approach 1
    result = await import_service_optimized.process_scan_v1_batch_service_role(
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
        "message": "Scan processed successfully (v1-batch-service-role)",
        "data": result
    }


# =============================================================================
# APPROACH 2: Async Two-Phase Processing
# Returns immediately, processes in background
# =============================================================================

@router.post("/v2-async-queue")
async def upload_scan_v2_async_queue(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    network_zone: str = Form("internal"),
    force_upload: bool = Form(False),
    user: CurrentUser = Depends(require_permission("imports.create"))
):
    """
    **APPROACH 2: Async Queue Processing**
    
    Uploads file and returns immediately with a `job_id`.
    Processing happens in the background.
    Use `/v2-async-queue/jobs/{job_id}` to check status.
    
    **Advantages:**
    - ✅ Immediate response to user
    - ✅ No JWT expiration (background uses service_role)
    - ✅ Better UX for large files
    
    **Disadvantages:**
    - ⚠️ Requires frontend polling for status
    - ⚠️ More complex error handling
    
    **Response includes:**
    - `job_id`: ID to poll for status
    - `status`: "queued"
    - `upload_time_seconds`: Time taken to upload
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
    
    # Process using optimized approach 2 (returns immediately)
    result = await import_service_optimized.process_scan_v2_async_queue(
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
        "message": "File uploaded and queued for processing",
        "data": result
    }


@router.get("/v2-async-queue/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    **Get Async Job Status**
    
    Poll this endpoint to check the status of an async scan processing job.
    
    **Status values:**
    - `queued`: Job is waiting to be processed
    - `processing`: Job is currently being processed
    - `processed`: Job completed successfully
    - `failed`: Job failed (check `error_message`)
    """
    result = await import_service_optimized.get_job_status(job_id)
    return {"success": True, "data": result}


# =============================================================================
# APPROACH 3: Bulk Insert via RPC
# Single RPC call with all data for atomic transaction
# =============================================================================

@router.post("/v3-bulk-rpc")
async def upload_scan_v3_bulk_rpc(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    network_zone: str = Form("internal"),
    force_upload: bool = Form(False),
    user: CurrentUser = Depends(require_permission("imports.create"))
):
    """
    **APPROACH 3: Bulk RPC Insert**
    
    Parses file in Python, then sends ALL data to a single RPC call.
    The RPC performs bulk inserts in one atomic transaction.
    
    **Advantages:**
    - ✅ Atomic transaction (all or nothing)
    - ✅ Maximum database performance
    - ✅ Single DB round-trip for inserts
    
    **Disadvantages:**
    - ⚠️ Large payload to RPC
    - ⚠️ Complex RPC function
    - ⚠️ Requires RPC: `fn_v3_bulk_insert_scan_data`
    
    **Response includes:**
    - `timing.parse_seconds`: Time to parse file
    - `timing.rpc_seconds`: Time for RPC call
    - `timing.total_seconds`: Total processing time
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
    
    # Process using optimized approach 3 (bulk RPC)
    result = await import_service_optimized.process_scan_v3_bulk_rpc(
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
        "message": "Scan processed successfully (v3-bulk-rpc)",
        "data": result
    }


# =============================================================================
# COMPARISON HELPER
# =============================================================================

@router.get("/comparison-info")
async def get_approaches_comparison():
    """
    **Get information about available approaches**
    
    Returns a comparison of the 3 experimental approaches to help choose the best one.
    """
    return {
        "success": True,
        "data": {
            "approaches": [
                {
                    "name": "v1-batch-service-role",
                    "endpoint": "/api/v1/scans-experimental/v1-batch-service-role",
                    "description": "Uses service_role for DB ops, batch inserts of 100 records",
                    "best_for": "Large files, avoiding JWT expiration",
                    "sync": True
                },
                {
                    "name": "v2-async-queue",
                    "endpoint": "/api/v1/scans-experimental/v2-async-queue",
                    "description": "Returns immediately, processes in background",
                    "best_for": "Best UX, non-blocking uploads",
                    "sync": False,
                    "status_endpoint": "/api/v1/scans-experimental/v2-async-queue/jobs/{job_id}"
                },
                {
                    "name": "v3-bulk-rpc",
                    "endpoint": "/api/v1/scans-experimental/v3-bulk-rpc",
                    "description": "Single RPC call with atomic transaction",
                    "best_for": "Maximum DB performance, data integrity",
                    "sync": True,
                    "requires_rpc": "fn_v3_bulk_insert_scan_data"
                }
            ],
            "recommendation": "Start with v1-batch-service-role for simplicity. Use v2-async-queue for better UX with large files."
        }
    }
