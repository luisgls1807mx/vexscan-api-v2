"""
Script para actualizar traducciones de vulnerabilidades existentes en Supabase.

Este script toma un JSON con traducciones y actualiza las vulnerabilidades
existentes en la base de datos con los campos traducidos.

Uso:
    python scripts/update_translations.py <archivo_traducido.json>
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()

from app.core.supabase import supabase
import anyio


async def update_translations_from_json(json_file: str, batch_size: int = 10):
    """Actualiza traducciones de vulnerabilidades desde un JSON."""
    
    print(f"\n{'='*80}")
    print(f"ACTUALIZANDO TRADUCCIONES DESDE JSON")
    print(f"{'='*80}")
    print(f"Archivo: {json_file}")
    
    # Cargar JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    vulnerabilities = data.get('vulnerabilities', [])
    total = len(vulnerabilities)
    
    print(f"Total de vulnerabilidades en JSON: {total}")
    
    # Filtrar solo las que tienen traducción
    translated_vulns = [v for v in vulnerabilities if v.get('is_translated', False)]
    
    print(f"Vulnerabilidades con traduccion: {len(translated_vulns)}")
    print(f"Sin traduccion: {total - len(translated_vulns)}")
    
    if not translated_vulns:
        print("\nNo hay vulnerabilidades traducidas para actualizar")
        return {'updated': 0, 'skipped': total, 'errors': 0}
    
    # Actualizar en batches
    total_batches = (len(translated_vulns) + batch_size - 1) // batch_size
    
    updated = 0
    errors = 0
    error_details = []
    
    for i in range(0, len(translated_vulns), batch_size):
        batch = translated_vulns[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        print(f"\nActualizando batch {batch_num}/{total_batches} ({len(batch)} items)...")
        
        for vuln in batch:
            try:
                # Preparar datos de actualización
                update_data = {
                    'title_es': vuln.get('title_es'),
                    'synopsis_es': vuln.get('synopsis_es'),
                    'description_es': vuln.get('description_es'),
                    'solution_es': vuln.get('solution_es'),
                    'is_translated': True
                }
                
                # Actualizar por scanner y plugin_id
                result = await anyio.to_thread.run_sync(
                    lambda: supabase.service.table('vulnerabilities')
                    .update(update_data)
                    .eq('scanner', vuln['scanner'])
                    .eq('plugin_id', vuln['plugin_id'])
                    .execute()
                )
                
                if result.data:
                    updated += 1
                    print(f"  OK Plugin {vuln['plugin_id']}")
                else:
                    print(f"  SKIP Plugin {vuln['plugin_id']} (no encontrado)")
                
            except Exception as e:
                errors += 1
                error_msg = f"Plugin {vuln['plugin_id']}: {str(e)}"
                error_details.append(error_msg)
                print(f"  ERROR {error_msg}")
        
        # Pausa entre batches
        if i + batch_size < len(translated_vulns):
            await asyncio.sleep(0.1)
    
    # Resumen
    print(f"\n{'='*80}")
    print(f"RESUMEN DE ACTUALIZACION")
    print(f"{'='*80}")
    print(f"Total procesadas: {len(translated_vulns)}")
    print(f"Actualizadas exitosamente: {updated}")
    print(f"Errores: {errors}")
    
    if error_details:
        print(f"\nDetalles de errores:")
        for error in error_details[:10]:  # Mostrar solo los primeros 10
            print(f"  - {error}")
        if len(error_details) > 10:
            print(f"  ... y {len(error_details) - 10} errores mas")
    
    return {
        'updated': updated,
        'skipped': total - len(translated_vulns),
        'errors': errors
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Actualizar traducciones de vulnerabilidades en Supabase"
    )
    parser.add_argument(
        "json_file",
        help="Archivo JSON con vulnerabilidades traducidas"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Tamano del batch (default: 10)"
    )
    
    args = parser.parse_args()
    
    try:
        result = await update_translations_from_json(args.json_file, args.batch_size)
        
        print(f"\nProceso completado!")
        print(f"Resultado: {result}")
        
    except Exception as e:
        print(f"\nError fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
