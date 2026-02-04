"""
Direct PostgreSQL connection for operations that need to bypass PostgREST timeout.
"""
import asyncpg
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class PostgresClient:
    """Direct PostgreSQL client using asyncpg."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._connection_string: Optional[str] = None
    
    def _get_connection_string(self) -> str:
        """
        Construye la connection string desde variables de entorno individuales.
        Requiere: user, password, host, port, dbname en .env
        """
        # Importar settings aquí para evitar circular imports
        from app.core.config import settings
        
        # Obtener variables de conexión desde .env
        user = settings.user
        password = settings.password
        host = settings.host
        port = settings.port
        dbname = settings.dbname
        
        if not password:
            raise ValueError(
                "Database password not found. "
                "Please add 'password' or 'DB_PASSWORD' to your .env file"
            )
        
        if not host:
            raise ValueError(
                "Database host not found. "
                "Please add 'host' to your .env file with your Supabase database host. "
                "You can find it in Supabase Dashboard → Settings → Database → Connection string"
            )
        
        # Construir connection string
        connection_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        
        logger.info(f"PostgreSQL connection string configured for host: {host}")
        return connection_string
    
    async def connect(self):
        """Establece el pool de conexiones."""
        if self.pool is None:
            # Construir connection string si no existe
            if not self._connection_string:
                self._connection_string = self._get_connection_string()
            
            try:
                self.pool = await asyncpg.create_pool(
                    self._connection_string,
                    ssl="require",
                    min_size=1,
                    max_size=10,
                    command_timeout=60,  # 1 minuto de timeout
                    timeout=30,  # 30 segundos para obtener una conexión del pool
                )
                logger.info("PostgreSQL connection pool created successfully")
            except Exception as e:
                logger.error(f"Failed to create PostgreSQL connection pool: {e}")
                raise
    
    async def disconnect(self):
        """Cierra el pool de conexiones."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PostgreSQL connection pool closed")
    
    async def execute_function(
        self, 
        function_name: str, 
        params: Dict[str, Any]
    ) -> Any:
        """
        Ejecuta una función de PostgreSQL directamente.
        
        Args:
            function_name: Nombre de la función (ej: 'fn_process_scan_batch')
            params: Diccionario de parámetros
            
        Returns:
            El resultado de la función (usualmente JSONB)
        """
        if not self.pool:
            await self.connect()
        
        import json
        
        # Construir la llamada a la función
        param_names = list(params.keys())
        param_values = []
        
        # Convertir listas/dicts a JSON strings para asyncpg
        for k in param_names:
            value = params[k]
            if isinstance(value, (list, dict)):
                # Convertir a JSON string
                param_values.append(json.dumps(value))
            else:
                param_values.append(value)
        
        placeholders = ', '.join(f'${i+1}' for i in range(len(param_names)))
        
        query = f"SELECT {function_name}({placeholders})"
        
        try:
            async with self.pool.acquire() as conn:
                logger.debug(f"Executing function: {function_name}")
                result = await conn.fetchval(query, *param_values)
                logger.debug(f"Function {function_name} completed successfully")
                
                # Si el resultado es un string JSON, parsearlo
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        # Si no es JSON válido, retornar como está
                        pass
                
                return result
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            raise


# Singleton instance
_postgres_client: Optional[PostgresClient] = None


def get_postgres_client() -> PostgresClient:
    """Obtiene la instancia singleton del cliente PostgreSQL."""
    global _postgres_client
    if _postgres_client is None:
        _postgres_client = PostgresClient()
    return _postgres_client


async def cleanup_postgres():
    """Limpia las conexiones de PostgreSQL (llamar al shutdown)."""
    global _postgres_client
    if _postgres_client:
        await _postgres_client.disconnect()
        _postgres_client = None
