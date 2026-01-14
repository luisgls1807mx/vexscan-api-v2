"""
VexScan API - Custom Exceptions
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class VexScanException(HTTPException):
    """Base exception for VexScan API."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.extra = extra or {}


class NotFoundError(VexScanException):
    """Resource not found."""
    
    def __init__(self, resource: str, identifier: str = None):
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code="NOT_FOUND"
        )


class ValidationError(VexScanException):
    """Validation error."""
    
    def __init__(self, detail: str, field: str = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="VALIDATION_ERROR",
            extra={"field": field} if field else {}
        )


class PermissionDeniedError(VexScanException):
    """Permission denied."""
    
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="PERMISSION_DENIED"
        )


class DuplicateError(VexScanException):
    """Duplicate resource error."""
    
    def __init__(self, resource: str, identifier: str = None):
        detail = f"{resource} already exists"
        if identifier:
            detail = f"{resource} '{identifier}' already exists"
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="DUPLICATE"
        )


class ParseError(VexScanException):
    """File parsing error."""
    
    def __init__(
        self, 
        detail: str, 
        scanner: str = None,
        filename: str = None
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="PARSE_ERROR",
            extra={
                "scanner": scanner,
                "filename": filename
            }
        )


class StorageError(VexScanException):
    """Storage operation error."""
    
    def __init__(self, detail: str, operation: str = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="STORAGE_ERROR",
            extra={"operation": operation}
        )


class RPCError(VexScanException):
    """Supabase RPC error."""
    
    def __init__(self, function: str, detail: str = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail or f"Error calling {function}",
            error_code="RPC_ERROR",
            extra={"function": function}
        )
