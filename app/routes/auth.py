"""
VexScan API - Auth Routes
Authentication endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from app.core.auth import get_current_user, CurrentUser
from app.services.auth_service import auth_service
from app.schemas import (
    LoginRequest,
    LoginResponse,
    UserProfile,
    UpdateProfileRequest,
    BaseResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user with email and password.
    
    Returns JWT access token and user profile.
    """
    result = await auth_service.login(request.email, request.password)
    return result


@router.post("/logout", response_model=BaseResponse)
async def logout(user: CurrentUser = Depends(get_current_user)):
    """Sign out current user."""
    await auth_service.logout(user.access_token)
    return BaseResponse(message="Logged out successfully")


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    result = await auth_service.refresh_token(refresh_token)
    return result


@router.get("/me", response_model=UserProfile)
async def get_current_profile(user: CurrentUser = Depends(get_current_user)):
    """Get current user's profile."""
    result = await auth_service.get_profile(user.access_token)
    return result


@router.put("/me", response_model=UserProfile)
async def update_profile(
    request: UpdateProfileRequest,
    user: CurrentUser = Depends(get_current_user)
):
    """Update current user's profile."""
    result = await auth_service.update_profile(
        user.access_token,
        full_name=request.full_name,
        avatar_url=request.avatar_url,
        label=request.label
    )
    return result


@router.post("/change-password", response_model=BaseResponse)
async def change_password(
    new_password: str,
    user: CurrentUser = Depends(get_current_user)
):
    """Change current user's password."""
    await auth_service.change_password(user.access_token, new_password)
    return BaseResponse(message="Password changed successfully")


@router.post("/forgot-password", response_model=BaseResponse)
async def forgot_password(email: str):
    """Request password reset email."""
    await auth_service.reset_password_request(email)
    return BaseResponse(message="If the email exists, a reset link has been sent")
