"""
VexScan API - Auth Service
Authentication operations using Supabase Auth
"""

import anyio
from typing import Optional, Dict, Any
import logging

from app.core.supabase import supabase
from app.core.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations."""
    
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        try:
            # Supabase auth es sync -> threadpool
            response = await anyio.to_thread.run_sync(
                lambda: supabase.anon.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
            )

            if not getattr(response, "user", None) or not getattr(response, "session", None):
                raise ValidationError("Invalid email or password")

            logger.info(f"User authenticated successfully: {response.user.id}")

            # Perfil via RPC (sync -> threadpool) con fallback
            try:
                profile = await anyio.to_thread.run_sync(
                    lambda: supabase.rpc_with_token(
                        "fn_get_current_user_profile",
                        response.session.access_token
                    )
                )

                # Si RPC devuelve None/vacío, aplica fallback
                if not profile:
                    raise RuntimeError("RPC returned empty profile")

                logger.info(f"Profile retrieved from RPC: {profile}")

            except Exception as rpc_error:
                logger.warning(f"RPC profile fetch failed, using basic user data: {rpc_error}")
                profile = {
                    "id": response.user.id,
                    "email": response.user.email,
                    "full_name": (response.user.user_metadata or {}).get("full_name"),
                    "avatar_url": (response.user.user_metadata or {}).get("avatar_url"),
                    "label": (response.user.user_metadata or {}).get("label"),
                    "is_super_admin": False,
                    "organization_id": None,
                    "organization_name": None,
                    "role": getattr(response.user, "role", None),
                    "permissions": []
                }

            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "token_type": "bearer",
                "expires_in": response.session.expires_in,
                "user": profile
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise ValidationError("Invalid email or password")
    
    async def logout(self, access_token: str) -> bool:
        """Sign out user."""
        try:
            client = supabase.get_client_with_token(access_token)
            client.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token."""
        try:
            response = supabase.anon.auth.refresh_session(refresh_token)
            
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "token_type": "bearer",
                "expires_in": response.session.expires_in
            }
        except Exception as e:
            logger.error(f"Refresh token error: {e}")
            raise ValidationError("Invalid refresh token")
    
    async def get_profile(self, access_token: str) -> Dict[str, Any]:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token("fn_get_current_user_profile", access_token)
        )
        if not result:
            raise NotFoundError("User profile")
        return result

    async def update_profile(
        access_token: str,
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        label: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        result = await anyio.to_thread.run_sync(
            lambda: supabase.rpc_with_token(
                "fn_update_current_user_profile",
                access_token,
                {
                    "p_full_name": full_name,
                    "p_avatar_url": avatar_url,
                    "p_label": label,
                    "p_settings": settings
                }
            )
        )
        return result
    
    async def change_password(
        access_token: str,
        new_password: str
    ) -> bool:
        """Change user password."""
        try:
            client = supabase.get_client_with_token(access_token)
            client.auth.update_user({"password": new_password})
            return True
        except Exception as e:
            logger.error(f"Change password error: {e}")
            raise ValidationError("Failed to change password")
    
    async def reset_password_request(self, email: str) -> bool:
        """Send password reset email."""
        try:
            supabase.anon.auth.reset_password_email(email)
            return True
        except Exception as e:
            logger.error(f"Reset password request error: {e}")
            # Don't reveal if email exists
            return True


auth_service = AuthService()
