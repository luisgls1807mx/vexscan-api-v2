"""
VexScan API - Core Module
"""

from app.core.config import settings, get_settings
from app.core.supabase import supabase, get_supabase, SupabaseClient
from app.core.auth import (
    get_current_user,
    get_current_active_user,
    get_super_admin,
    get_org_admin,
    require_permission,
    require_workspace,
    CurrentUser
)
from app.core.exceptions import (
    VexScanException,
    NotFoundError,
    ValidationError,
    PermissionDeniedError,
    DuplicateError,
    ParseError,
    StorageError,
    RPCError
)

__all__ = [
    # Config
    "settings",
    "get_settings",
    
    # Supabase
    "supabase",
    "get_supabase",
    "SupabaseClient",
    
    # Auth
    "get_current_user",
    "get_current_active_user",
    "get_super_admin",
    "get_org_admin",
    "require_permission",
    "require_workspace",
    "CurrentUser",
    
    # Exceptions
    "VexScanException",
    "NotFoundError",
    "ValidationError",
    "PermissionDeniedError",
    "DuplicateError",
    "ParseError",
    "StorageError",
    "RPCError",
]
