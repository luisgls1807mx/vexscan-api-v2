"""
Script standalone para procesar archivos Nessus y poblar el catálogo de vulnerabilidades.

Este script:
1. Parsea el archivo Nessus y extrae vulnerabilidades únicas
2. Guarda un JSON local con las vulnerabilidades
3. Traduce las vulnerabilidades (opcional, si no están traducidas)
4. Inserta a la BD en batches pequeños para evitar timeouts

Uso:
    python scripts/process_nessus_catalog.py <archivo.nessus> [--translate] [--insert]
"""

import sys
import os
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ⚠️ IMPORTANTE: Cargar .env ANTES de importar módulos de app
# para que settings.ANTHROPIC_API_KEY esté disponible
from dotenv import load_dotenv
load_dotenv()

# Debug: Verificar que se cargó la API key
import os
print(f"[DEBUG] ANTHROPIC_API_KEY desde os.environ: {os.getenv('ANTHROPIC_API_KEY')[:20] if os.getenv('ANTHROPIC_API_KEY') else 'NO ENCONTRADA'}...")

# Ahora sí importar módulos de la app (que usan settings)
from app.adapters.nessus import NessusAdapter
from app.services.translation_service import translation_service
from app.core.supabase import supabase
from app.core.config import settings
import anyio

# Debug: Verificar que settings tiene la API key
print(f"[DEBUG] settings.ANTHROPIC_API_KEY: {settings.ANTHROPIC_API_KEY[:20] if settings.ANTHROPIC_API_KEY else 'NO ENCONTRADA'}...")
print(f"[DEBUG] translation_service.is_enabled: {translation_service.is_enabled}")


class NessusCatalogProcessor:
    """Procesa archivos Nessus y popula el catálogo de vulnerabilidades."""
    
    def __init__(self, nessus_file: str):
        self.nessus_file = Path(nessus_file)
        self.output_dir = Path("data/catalog_processing")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generar nombre base para archivos de salida
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = self.nessus_file.stem
        self.parsed_file = self.output_dir / f"{base_name}_{timestamp}_parsed.json"
        self.translated_file = self.output_dir / f"{base_name}_{timestamp}_translated.json"
        self.results_file = self.output_dir / f"{base_name}_{timestamp}_results.json"
        
    async def step1_parse_nessus(self) -> Dict[str, Any]:
        """Paso 1: Parsear archivo Nessus y extraer vulnerabilidades únicas."""
        print(f"\n{'='*80}")
        print(f"PASO 1: Parseando archivo Nessus")
        print(f"{'='*80}")
        print(f"Archivo: {self.nessus_file}")
        
        if not self.nessus_file.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.nessus_file}")
        
        # Leer y parsear el archivo
        with open(self.nessus_file, 'rb') as f:
            content = f.read()
        
        adapter = NessusAdapter()
        parsed_data = await adapter.parse(content, str(self.nessus_file))
        
        print(f"✓ Hosts encontrados: {len(parsed_data.assets)}")
        print(f"✓ Findings totales: {len(parsed_data.findings)}")
        
        # Extraer vulnerabilidades únicas
        unique_vulns = {}
        for finding in parsed_data.findings:
            key = f"{finding.scanner}_{finding.plugin_id}"
            if key not in unique_vulns:
                unique_vulns[key] = {
                    'scanner': finding.scanner,
                    'plugin_id': finding.plugin_id,
                    'title': finding.title,
                    'severity': finding.severity.value,
                    'synopsis': finding.synopsis,
                    'description': finding.description,
                    'solution': finding.solution,
                    'plugin_family': finding.plugin_family,
                    'cvss_score': finding.cvss_score,
                    'cvss3_score': finding.cvss3_score,
                    'cve': finding.cves or [],
                    'references': finding.references or [],
                }
        
        result = {
            'metadata': {
                'source_file': str(self.nessus_file),
                'parsed_at': datetime.now().isoformat(),
                'total_hosts': len(parsed_data.assets),
                'total_findings': len(parsed_data.findings),
                'unique_vulnerabilities': len(unique_vulns)
            },
            'vulnerabilities': list(unique_vulns.values())
        }
        
        # Guardar JSON
        with open(self.parsed_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Vulnerabilidades únicas: {len(unique_vulns)}")
        print(f"✓ Guardado en: {self.parsed_file}")
        
        return result
    
    async def step2_translate_vulnerabilities(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Paso 2: Traducir vulnerabilidades usando Claude."""
        print(f"\n{'='*80}")
        print(f"PASO 2: Traduciendo vulnerabilidades")
        print(f"{'='*80}")
        
        if not translation_service.is_enabled:
            print("⚠ Servicio de traducción no habilitado (falta ANTHROPIC_API_KEY)")
            print("⚠ Se continuará sin traducciones")
            return parsed_data
        
        vulnerabilities = parsed_data['vulnerabilities']
        total = len(vulnerabilities)
        
        print(f"Total a traducir: {total}")
        print(f"Modelo: {translation_service.MODEL}")
        
        # Traducir en batches
        batch_size = 5
        total_batches = (total + batch_size - 1) // batch_size
        
        translated_vulns = []
        total_tokens_in = 0
        total_tokens_out = 0
        
        for i in range(0, total, batch_size):
            batch = vulnerabilities[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} items)...")
            
            try:
                translations = await translation_service._translate_batch(batch)
                
                # Combinar datos originales con traducciones
                for orig, trans in zip(batch, translations):
                    combined = {**orig, **trans}
                    combined['is_translated'] = True
                    translated_vulns.append(combined)
                
                # Acumular tokens
                if hasattr(translation_service, '_last_tokens_in'):
                    total_tokens_in += translation_service._last_tokens_in
                    total_tokens_out += translation_service._last_tokens_out
                
                print(f"✓ Traducido correctamente")
                
            except Exception as e:
                print(f"✗ Error en batch {batch_num}: {e}")
                # Agregar sin traducción
                for orig in batch:
                    orig['is_translated'] = False
                    translated_vulns.append(orig)
        
        result = {
            'metadata': {
                **parsed_data['metadata'],
                'translated_at': datetime.now().isoformat(),
                'translation_model': translation_service.MODEL,
                'total_tokens_in': total_tokens_in,
                'total_tokens_out': total_tokens_out,
                'estimated_cost_usd': (total_tokens_in * 0.00025 / 1000) + (total_tokens_out * 0.00125 / 1000)
            },
            'vulnerabilities': translated_vulns
        }
        
        # Guardar JSON
        with open(self.translated_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Traducción completa")
        print(f"✓ Tokens: {total_tokens_in} in / {total_tokens_out} out")
        print(f"✓ Costo estimado: ${result['metadata']['estimated_cost_usd']:.4f} USD")
        print(f"✓ Guardado en: {self.translated_file}")
        
        return result
    
    async def step3_insert_to_catalog(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Paso 3: Insertar vulnerabilidades al catálogo en batches pequeños."""
        print(f"\n{'='*80}")
        print(f"PASO 3: Insertando al catálogo de vulnerabilidades")
        print(f"{'='*80}")
        
        vulnerabilities = data['vulnerabilities']
        total = len(vulnerabilities)
        
        print(f"Total a insertar: {total}")
        
        # Verificar cuáles ya existen
        print("\nVerificando vulnerabilidades existentes...")
        existing_keys = set()
        
        try:
            # Obtener todas las vulnerabilidades existentes de Nessus
            result = await anyio.to_thread.run_sync(
                lambda: supabase.service.table('vulnerabilities')
                .select('scanner,plugin_id')
                .eq('scanner', 'nessus')
                .execute()
            )
            
            if result.data:
                existing_keys = {f"{v['scanner']}_{v['plugin_id']}" for v in result.data}
                print(f"✓ Encontradas {len(existing_keys)} vulnerabilidades existentes")
        except Exception as e:
            print(f"⚠ Error verificando existentes: {e}")
        
        # Filtrar solo las nuevas
        new_vulns = []
        for vuln in vulnerabilities:
            key = f"{vuln['scanner']}_{vuln['plugin_id']}"
            if key not in existing_keys:
                new_vulns.append(vuln)
        
        print(f"✓ Nuevas vulnerabilidades a insertar: {len(new_vulns)}")
        print(f"✓ Ya existentes (se omitirán): {total - len(new_vulns)}")
        
        if not new_vulns:
            print("\n✓ No hay nuevas vulnerabilidades para insertar")
            return {
                'inserted': 0,
                'skipped': total,
                'errors': 0
            }
        
        # Insertar en batches pequeños (10 a la vez para evitar timeout)
        batch_size = 10
        total_batches = (len(new_vulns) + batch_size - 1) // batch_size
        
        inserted = 0
        errors = 0
        error_details = []
        
        for i in range(0, len(new_vulns), batch_size):
            batch = new_vulns[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            print(f"\nInsertando batch {batch_num}/{total_batches} ({len(batch)} items)...")
            
            try:
                # Preparar datos para inserción
                insert_data = []
                for vuln in batch:
                    insert_data.append({
                        'scanner': vuln['scanner'],
                        'plugin_id': vuln['plugin_id'],
                        'title': vuln['title'],
                        'title_es': vuln.get('title_es'),
                        'severity': vuln['severity'],
                        'synopsis': vuln.get('synopsis'),
                        'synopsis_es': vuln.get('synopsis_es'),
                        'description': vuln.get('description'),
                        'description_es': vuln.get('description_es'),
                        'solution': vuln.get('solution'),
                        'solution_es': vuln.get('solution_es'),
                        'plugin_family': vuln.get('plugin_family'),
                        'cvss_score': vuln.get('cvss_score'),
                        'cvss3_score': vuln.get('cvss3_score'),
                        'is_translated': vuln.get('is_translated', False)
                    })
                
                # Insertar batch
                result = await anyio.to_thread.run_sync(
                    lambda: supabase.service.table('vulnerabilities')
                    .insert(insert_data)
                    .execute()
                )
                
                inserted += len(batch)
                print(f"✓ Insertado correctamente")
                
                # Pequeña pausa para no saturar la BD
                await asyncio.sleep(0.5)
                
            except Exception as e:
                errors += len(batch)
                error_msg = str(e)
                print(f"✗ Error en batch {batch_num}: {error_msg}")
                error_details.append({
                    'batch': batch_num,
                    'error': error_msg,
                    'items': [f"{v['scanner']}_{v['plugin_id']}" for v in batch]
                })
        
        result = {
            'inserted': inserted,
            'skipped': total - len(new_vulns),
            'errors': errors,
            'error_details': error_details
        }
        
        # Guardar resultados
        final_result = {
            'metadata': data['metadata'],
            'processing_results': result,
            'processed_at': datetime.now().isoformat()
        }
        
        with open(self.results_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*80}")
        print(f"RESUMEN FINAL")
        print(f"{'='*80}")
        print(f"✓ Insertadas: {inserted}")
        print(f"✓ Omitidas (ya existían): {result['skipped']}")
        print(f"✗ Errores: {errors}")
        print(f"✓ Resultados guardados en: {self.results_file}")
        
        return result


async def main():
    parser = argparse.ArgumentParser(
        description='Procesar archivo Nessus y poblar catálogo de vulnerabilidades'
    )
    parser.add_argument('nessus_file', help='Ruta al archivo .nessus')
    parser.add_argument('--skip-parse', action='store_true', 
                       help='Saltar parseo (usar JSON existente)')
    parser.add_argument('--skip-translate', action='store_true',
                       help='Saltar traducción')
    parser.add_argument('--skip-insert', action='store_true',
                       help='Saltar inserción a BD')
    parser.add_argument('--parsed-json', help='Usar JSON parseado existente')
    parser.add_argument('--translated-json', help='Usar JSON traducido existente')
    
    args = parser.parse_args()
    
    processor = NessusCatalogProcessor(args.nessus_file)
    
    print(f"\n{'#'*80}")
    print(f"# PROCESADOR DE CATÁLOGO NESSUS")
    print(f"{'#'*80}")
    
    # Paso 1: Parsear
    if args.parsed_json:
        print(f"\nUsando JSON parseado existente: {args.parsed_json}")
        with open(args.parsed_json, 'r', encoding='utf-8') as f:
            parsed_data = json.load(f)
    elif not args.skip_parse:
        parsed_data = await processor.step1_parse_nessus()
    else:
        print("\n⚠ Parseo omitido, debe proporcionar --parsed-json")
        return
    
    # Paso 2: Traducir
    if args.translated_json:
        print(f"\nUsando JSON traducido existente: {args.translated_json}")
        with open(args.translated_json, 'r', encoding='utf-8') as f:
            translated_data = json.load(f)
    elif not args.skip_translate:
        translated_data = await processor.step2_translate_vulnerabilities(parsed_data)
    else:
        print("\n⚠ Traducción omitida")
        translated_data = parsed_data
    
    # Paso 3: Insertar
    if not args.skip_insert:
        await processor.step3_insert_to_catalog(translated_data)
    else:
        print("\n⚠ Inserción omitida")
    
    print(f"\n{'#'*80}")
    print(f"# PROCESO COMPLETADO")
    print(f"{'#'*80}\n")


if __name__ == '__main__':
    asyncio.run(main())
