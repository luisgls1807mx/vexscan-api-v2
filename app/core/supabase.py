from typing import Optional, Dict, Any
from supabase import create_client, Client
from functools import lru_cache
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        self._anon_client: Optional[Client] = None
        self._service_client: Optional[Client] = None

    @property
    def anon(self) -> Client:
        if self._anon_client is None:
            self._anon_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        return self._anon_client

    @property
    def service(self) -> Client:
        if self._service_client is None:
            self._service_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        return self._service_client

    def rpc(self, function_name: str, params: Dict[str, Any] | None = None, use_service_role: bool = False):
        client = self.service if use_service_role else self.anon
        try:
            res = client.rpc(function_name, params or {}).execute()
            return getattr(res, "data", res)
        except Exception as e:
            logger.error(f"RPC error calling {function_name}: {e}")
            raise

    def rpc_with_token(self, function_name: str, access_token: str, params: Dict[str, Any] | None = None):
        """
        NO muta headers globales.
        Aplica auth al canal PostgREST para esta ejecución.
        """
        import json
        import re
        try:
            # aplica token al postgrest
            self.anon.postgrest.auth(token=access_token)  # patrón usado para RLS con JWT :contentReference[oaicite:3]{index=3}
            res = self.anon.rpc(function_name, params or {}).execute()
            return getattr(res, "data", res)
        except Exception as e:
            # Intentar extraer JSON válido del mensaje de error
            # Esto ocurre cuando la librería falla al parsear pero el RPC fue exitoso
            error_str = str(e)
            if "details" in error_str and "success" in error_str:
                try:
                    # Buscar el patrón b'{"success"...}' en el string de error
                    # El formato es: 'details': 'b\'{"success" : true, ...}\''
                    match = re.search(r"b['\\\"]'?\{(.+?)\}['\\\"]?'?", error_str)
                    if match:
                        json_str = "{" + match.group(1) + "}"
                        # Limpiar escapes
                        json_str = json_str.replace('\\"', '"').replace("\\'", "'")
                        return json.loads(json_str)
                except Exception as parse_error:
                    logger.debug(f"Could not parse JSON from error: {parse_error}")
            logger.error(f"RPC error calling {function_name} with token: {e}")
            raise

    def upload_file(self, bucket: str, path: str, file_content: bytes, content_type: str = "application/octet-stream") -> str:
        try:
            self.service.storage.from_(bucket).upload(path, file_content, {"content-type": content_type})
            return self.service.storage.from_(bucket).get_public_url(path)
        except Exception as e:
            logger.error(f"Storage upload error: {e}")
            raise

    def download_file(self, bucket: str, path: str) -> bytes:
        try:
            return self.service.storage.from_(bucket).download(path)
        except Exception as e:
            logger.error(f"Storage download error: {e}")
            raise

    def delete_file(self, bucket: str, path: str) -> bool:
        try:
            self.service.storage.from_(bucket).remove([path])
            return True
        except Exception as e:
            logger.error(f"Storage delete error: {e}")
            raise

    def get_client_with_token(self, access_token: str) -> Client:
        """Create a Supabase client with access token for auth operations."""
        return create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY,
            options={"headers": {"Authorization": f"Bearer {access_token}"}}
        )


@lru_cache()
def get_supabase() -> SupabaseClient:
    return SupabaseClient()

supabase = get_supabase()
