"""
VexScan API - Translation Service (Optimizado para Import)
Traduce vulnerabilidades NUEVAS durante el proceso de importación
"""

import httpx
import json
import asyncio
from typing import Optional, Dict, Any, List, Set
import logging

from app.core.supabase import supabase
from app.core.config import settings

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Servicio de traducción optimizado para el flujo de importación.
    
    Características:
    - Solo traduce vulnerabilidades NUEVAS (no existentes en catálogo)
    - NO traduce campos vacíos o con N/A
    - Procesa en batch para eficiencia de tokens
    - Se ejecuta DURANTE el import, no después
    """
    
    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"
    
    # Usar Haiku para economía máxima
    MODEL = "claude-3-haiku-20240307"
    MAX_TOKENS = 4000
    TEMPERATURE = 0.1
    
    # Batch de 5 vulnerabilidades a la vez para balancear costo/velocidad
    TRANSLATION_BATCH_SIZE = 5
    MAX_RETRIES = 2
    RETRY_DELAY = 1.0
    
    # Valores que se consideran "vacíos" y no se traducen
    EMPTY_VALUES = {'', 'n/a', 'N/A', 'N/a', 'none', 'None', 'null', 'NULL', '-', 'n/a.', 'N/A.'}
    
    SYSTEM_PROMPT = """Eres un traductor experto en ciberseguridad.
Traduce los textos de vulnerabilidades del inglés al español.

REGLAS:
1. Mantén términos técnicos en inglés: SSL, TLS, SSH, HTTP, CVE, CVSS, XSS, SQL, etc.
2. Conserva nombres de software: Apache, Windows, Linux, OpenSSL, etc.
3. Traduce de forma clara y profesional
4. Si el texto ya está en español, déjalo igual
5. NO agregues explicaciones adicionales

Responde SOLO con el array JSON de traducciones."""

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured - translations disabled")
    
    @property
    def is_enabled(self) -> bool:
        return bool(self.api_key)
    
    def _is_empty(self, value: Optional[str]) -> bool:
        """Verifica si un valor está vacío o es N/A."""
        if value is None:
            return True
        stripped = value.strip()
        return stripped in self.EMPTY_VALUES or len(stripped) < 3
    
    def _clean_for_translation(self, value: Optional[str], max_len: int = 3000) -> Optional[str]:
        """Limpia y trunca valor para traducción. Retorna None si está vacío."""
        if self._is_empty(value):
            return None
        return value[:max_len].strip()
    
    async def get_existing_vulnerabilities(
        self,
        access_token: str,
        scanner: str,
        plugin_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Consulta cuáles plugin_ids ya existen en el catálogo.
        
        Returns:
            Dict[plugin_id -> {id, is_translated, title_es, ...}]
        """
        if not plugin_ids:
            return {}
        
        try:
            import anyio
            
            # Consultar en batches de 100 para evitar límites
            existing = {}
            for i in range(0, len(plugin_ids), 100):
                batch = plugin_ids[i:i+100]
                
                # Usar anyio para ejecutar la consulta de forma síncrona
                result = await anyio.to_thread.run_sync(
                    lambda: supabase.service.table('vulnerabilities').select(
                        'id, plugin_id, is_translated, title_es, synopsis_es, description_es, solution_es, plugin_output_es'
                    ).eq('scanner', scanner).in_('plugin_id', batch).execute()
                )
                
                if result.data:
                    for row in result.data:
                        existing[row['plugin_id']] = row
            
            return existing
            
        except Exception as e:
            logger.error(f"Error checking existing vulnerabilities: {e}")
            return {}
    
    async def translate_new_vulnerabilities(
        self,
        access_token: str,
        scanner: str,
        vulnerabilities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Proceso principal: Identifica vulnerabilidades nuevas, las traduce e inserta.
        
        FLUJO OPTIMIZADO:
        1. Extraer plugin_ids únicos del archivo
        2. Consultar BD: ¿cuáles ya existen?
        3. Filtrar SOLO las nuevas
        4. Traducir las nuevas (ignorando campos vacíos/N/A)
        5. Insertar nuevas al catálogo
        6. Retornar mapeo completo plugin_id -> vulnerability_id
        
        Args:
            access_token: Token de auth
            scanner: Nombre del scanner (nessus, etc)
            vulnerabilities: Lista de vulns extraídas del scan
        
        Returns:
            {
                'plugin_to_vuln_id': Dict[plugin_id -> vulnerability_id],
                'stats': {
                    'total_unique': int,
                    'already_existed': int,
                    'new_translated': int,
                    'new_without_translation': int
                }
            }
        """
        if not vulnerabilities:
            return {'plugin_to_vuln_id': {}, 'stats': {
                'total_unique': 0, 'already_existed': 0, 
                'new_translated': 0, 'new_without_translation': 0
            }}
        
        # 1. Extraer plugin_ids únicos
        unique_vulns = {}
        for v in vulnerabilities:
            pid = v.get('plugin_id') or v.get('scanner_finding_id')
            if pid and pid not in unique_vulns:
                unique_vulns[pid] = v
        
        plugin_ids = list(unique_vulns.keys())
        logger.info(f"[CATALOG] {len(plugin_ids)} unique vulnerabilities in scan file")
        
        # 2. Consultar cuáles ya existen en el catálogo (UNA SOLA VEZ)
        existing = await self.get_existing_vulnerabilities(
            access_token, scanner, plugin_ids
        )
        already_existed = len(existing)
        logger.info(f"[CATALOG] {already_existed} already in catalog (will reuse, NO translation needed)")
        
        # 3. Separar nuevas de existentes
        new_vulns = []
        plugin_to_vuln_id = {}
        
        for pid, vuln in unique_vulns.items():
            if pid in existing:
                # Ya existe, usar el ID existente (NO gastar tokens)
                plugin_to_vuln_id[pid] = existing[pid]['id']
            else:
                # Nueva, necesita traducción e inserción
                new_vulns.append(vuln)
        
        stats = {
            'total_unique': len(plugin_ids),
            'already_existed': already_existed,
            'new_translated': 0,
            'new_without_translation': 0
        }
        
        if not new_vulns:
            logger.info("[CATALOG] All vulnerabilities already in catalog - skipping translation entirely")
            return {'plugin_to_vuln_id': plugin_to_vuln_id, 'stats': stats}
        
        logger.info(f"[CATALOG] {len(new_vulns)} NEW vulnerabilities need translation")
        
        # 4. Traducir en batches (solo si está habilitado)
        if self.is_enabled:
            translated = await self._translate_batch_vulnerabilities(new_vulns)
            stats['new_translated'] = len([t for t in translated.values() if t.get('title_es')])
            stats['new_without_translation'] = len(new_vulns) - stats['new_translated']
        else:
            logger.warning("[CATALOG] Translation DISABLED - inserting without Spanish translations")
            translated = {
                v.get('plugin_id') or v.get('scanner_finding_id'): {
                    'title_es': None,
                    'synopsis_es': None,
                    'description_es': None,
                    'solution_es': None
                }
                for v in new_vulns
            }
            stats['new_without_translation'] = len(new_vulns)
        
        # 5. Insertar nuevas al catálogo
        new_ids = await self._insert_to_catalog(
            access_token, scanner, new_vulns, translated
        )
        
        plugin_to_vuln_id.update(new_ids)
        
        logger.info(
            f"[CATALOG] Complete: {already_existed} reused + "
            f"{stats['new_translated']} translated + "
            f"{stats['new_without_translation']} not translated = "
            f"{len(plugin_to_vuln_id)} total"
        )
        
        return {'plugin_to_vuln_id': plugin_to_vuln_id, 'stats': stats}
    
    async def _translate_batch_vulnerabilities(
        self,
        vulnerabilities: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, str]]:
        """
        Traduce vulnerabilidades en batches.
        
        Returns:
            Dict[plugin_id -> {title_es, synopsis_es, description_es, solution_es}]
        """
        results = {}
        total_batches = (len(vulnerabilities) + self.TRANSLATION_BATCH_SIZE - 1) // self.TRANSLATION_BATCH_SIZE
        
        for batch_num, i in enumerate(range(0, len(vulnerabilities), self.TRANSLATION_BATCH_SIZE), 1):
            batch = vulnerabilities[i:i + self.TRANSLATION_BATCH_SIZE]
            
            logger.info(f"Translating batch {batch_num}/{total_batches} ({len(batch)} vulnerabilities)")
            
            # Preparar datos para traducción (omitir campos vacíos)
            items_to_translate = []
            for v in batch:
                pid = v.get('plugin_id') or v.get('scanner_finding_id')
                
                item = {'plugin_id': pid, 'fields': {}}
                
                # Solo incluir campos que NO están vacíos
                title = self._clean_for_translation(v.get('title'), 500)
                if title:
                    item['fields']['title'] = title
                
                synopsis = self._clean_for_translation(v.get('synopsis'), 500)
                if synopsis:
                    item['fields']['synopsis'] = synopsis
                
                description = self._clean_for_translation(v.get('description'), 2500)
                if description:
                    item['fields']['description'] = description
                
                solution = self._clean_for_translation(v.get('solution'), 1500)
                if solution:
                    item['fields']['solution'] = solution
                
                # Agregar plugin_output (limitado a 2000 caracteres)
                plugin_output = self._clean_for_translation(v.get('plugin_output'), 2000)
                if plugin_output:
                    item['fields']['plugin_output'] = plugin_output
                
                items_to_translate.append(item)
            
            # Traducir batch
            try:
                batch_translations = await self._call_claude_api(items_to_translate)
                results.update(batch_translations)
            except Exception as e:
                logger.error(f"Translation batch {batch_num} failed: {e}")
                # En caso de error, usar valores vacíos
                for item in items_to_translate:
                    results[item['plugin_id']] = {
                        'title_es': None,
                        'synopsis_es': None,
                        'description_es': None,
                        'solution_es': None
                    }
            
            # Pequeña pausa entre batches para no saturar API
            if i + self.TRANSLATION_BATCH_SIZE < len(vulnerabilities):
                await asyncio.sleep(0.3)
        
        return results
    
    async def _call_claude_api(
        self,
        items: List[Dict]
    ) -> Dict[str, Dict[str, str]]:
        """Llama a Claude API para traducir un batch."""
        
        # Construir prompt solo con campos no vacíos
        prompt_items = []
        for item in items:
            if item['fields']:  # Solo si hay campos para traducir
                prompt_items.append({
                    'plugin_id': item['plugin_id'],
                    **item['fields']
                })
        
        if not prompt_items:
            # Nada que traducir (todos los campos están vacíos)
            return {item['plugin_id']: {
                'title_es': None,
                'synopsis_es': None,
                'description_es': None,
                'solution_es': None,
                'plugin_output_es': None
            } for item in items}
        
        user_prompt = f"""Traduce las siguientes {len(prompt_items)} vulnerabilidades al español.
SOLO traduce los campos que se proporcionan. Si un campo no aparece, no lo incluyas en la respuesta.

VULNERABILIDADES:
{json.dumps(prompt_items, indent=2, ensure_ascii=False)}

Responde con un array JSON donde cada elemento tenga:
- "plugin_id": el ID original
- "title_es": título traducido (solo si había title)
- "synopsis_es": sinopsis traducida (solo si había synopsis)
- "description_es": descripción traducida (solo si había description)
- "solution_es": solución traducida (solo si había solution)
- "plugin_output_es": salida del plugin traducida (solo si había plugin_output)

IMPORTANTE: Responde SOLO con el array JSON, sin texto adicional."""

        payload = {
            "model": self.MODEL,
            "max_tokens": self.MAX_TOKENS,
            "temperature": self.TEMPERATURE,
            "system": self.SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}]
        }
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": self.API_VERSION
        }
        
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    response = await client.post(
                        self.API_URL,
                        json=payload,
                        headers=headers
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    raw_content = data["content"][0]["text"]
                    
                    usage = data.get("usage", {})
                    logger.info(
                        f"Claude API: {len(prompt_items)} items, "
                        f"tokens: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out"
                    )
                    
                    return self._parse_translation_response(raw_content, items)
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"Claude API HTTP error (attempt {attempt + 1}): {e.response.status_code}")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise
            except Exception as e:
                logger.error(f"Claude API error (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise
        
        return {}
    
    def _parse_translation_response(
        self,
        raw_content: str,
        original_items: List[Dict]
    ) -> Dict[str, Dict[str, str]]:
        """Parse la respuesta JSON de Claude."""
        results = {}
        
        # Inicializar con valores vacíos
        for item in original_items:
            results[item['plugin_id']] = {
                'title_es': None,
                'synopsis_es': None,
                'description_es': None,
                'solution_es': None
            }
        
        try:
            # Limpiar markdown
            content = raw_content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)
            
            translations = json.loads(content)
            
            for t in translations:
                pid = str(t.get('plugin_id'))
                if pid in results:
                    if t.get('title_es'):
                        results[pid]['title_es'] = t['title_es']
                    if t.get('synopsis_es'):
                        results[pid]['synopsis_es'] = t['synopsis_es']
                    if t.get('description_es'):
                        results[pid]['description_es'] = t['description_es']
                    if t.get('solution_es'):
                        results[pid]['solution_es'] = t['solution_es']
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse translation response: {e}")
            logger.debug(f"Raw content: {raw_content[:500]}")
        
        return results
    
    async def _insert_to_catalog(
        self,
        access_token: str,
        scanner: str,
        vulnerabilities: List[Dict],
        translations: Dict[str, Dict[str, str]]
    ) -> Dict[str, int]:
        """
        Inserta nuevas vulnerabilidades al catálogo con sus traducciones.
        
        Returns:
            Dict[plugin_id -> vulnerability_id]
        """
        if not vulnerabilities:
            return {}
        
        # Preparar datos para inserción bulk
        rows = []
        for v in vulnerabilities:
            pid = v.get('plugin_id') or v.get('scanner_finding_id')
            trans = translations.get(pid, {})
            
            # Determinar si tiene traducción válida
            has_translation = bool(trans.get('title_es'))
            
            row = {
                'scanner': scanner,
                'plugin_id': str(pid),
                'title': v.get('title'),
                'synopsis': v.get('synopsis') if not self._is_empty(v.get('synopsis')) else None,
                'description': (v.get('description') or '')[:50000] if not self._is_empty(v.get('description')) else None,
                'solution': (v.get('solution') or '')[:10000] if not self._is_empty(v.get('solution')) else None,
                'plugin_output': (v.get('plugin_output') or '')[:50000] if not self._is_empty(v.get('plugin_output')) else None,
                'severity': v.get('severity'),
                'cwe': v.get('cwe'),
                'plugin_family': v.get('plugin_family'),
                'cvss_score': v.get('cvss_score'),
                'cvss_vector': v.get('cvss_vector'),
                'cvss3_score': v.get('cvss3_score'),
                'cvss3_vector': v.get('cvss3_vector'),
                # Traducciones (None si no se tradujo)
                'title_es': trans.get('title_es'),
                'synopsis_es': trans.get('synopsis_es'),
                'description_es': trans.get('description_es'),
                'solution_es': trans.get('solution_es'),
                'plugin_output_es': trans.get('plugin_output_es'),
                'is_translated': has_translation
            }
            rows.append(row)
        
        try:
            import anyio
            
            # Insertar en batches de 50
            results = {}
            for i in range(0, len(rows), 50):
                batch = rows[i:i+50]
                
                # Usar anyio para ejecutar la inserción de forma síncrona
                result = await anyio.to_thread.run_sync(
                    lambda: supabase.service.table('vulnerabilities').upsert(
                        batch,
                        on_conflict='scanner,plugin_id'
                    ).execute()
                )
                
                # Mapear plugin_id -> id
                if result.data:
                    for row in result.data:
                        results[row['plugin_id']] = row['id']
            
            logger.info(f"Inserted/updated {len(results)} vulnerabilities in catalog")
            return results
            
        except Exception as e:
            logger.error(f"Error inserting to catalog: {e}")
            return {}
    
    async def get_translation_stats(self, access_token: str) -> Dict[str, Any]:
        """Estadísticas del catálogo."""
        try:
            return await supabase.rpc_with_token(
                'fn_get_translation_stats',
                access_token,
                {}
            )
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}


# Singleton
translation_service = TranslationService()
