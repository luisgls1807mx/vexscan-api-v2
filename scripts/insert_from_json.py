"""
Script para insertar vulnerabilidades desde un JSON ya traducido.

Este script es útil cuando ya tienes un JSON con traducciones y solo
necesitas insertarlo a la base de datos en batches pequeños.

Uso:
    python scripts/insert_from_json.py <archivo_traducido.json>
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


async def insert_vulnerabilities_from_json(json_file: str, batch_size: int = 10):
    """Inserta vulnerabilidades desde un JSON a la base de datos."""
    
    print(f"\n{'='*80}")
    print(f"INSERTANDO VULNERABILIDADES DESDE JSON")
    print(f"{'='*80}")
    print(f"Archivo: {json_file}")
    
    # Cargar JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    vulnerabilities = data.get('vulnerabilities', [])
    total = len(vulnerabilities)
    
    print(f"Total de vulnerabilidades en JSON: {total}")
    
    # Verificar cuáles ya existen
    print("\nVerificando vulnerabilidades existentes...")
    existing_keys = set()
    
    try:
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
    
    # Insertar en batches
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
            
            # Pequeña pausa
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
    
    print(f"\n{'='*80}")
    print(f"RESUMEN")
    print(f"{'='*80}")
    print(f"✓ Insertadas: {inserted}")
    print(f"✓ Omitidas (ya existían): {total - len(new_vulns)}")
    print(f"✗ Errores: {errors}")
    
    if error_details:
        print(f"\nDetalles de errores:")
        for err in error_details:
            print(f"  Batch {err['batch']}: {err['error']}")
    
    return {
        'inserted': inserted,
        'skipped': total - len(new_vulns),
        'errors': errors,
        'error_details': error_details
    }


async def main():
    parser = argparse.ArgumentParser(
        description='Insertar vulnerabilidades desde JSON a la base de datos'
    )
    parser.add_argument('json_file', help='Ruta al archivo JSON con vulnerabilidades')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Tamaño de batch para inserción (default: 10)')
    
    args = parser.parse_args()
    
    await insert_vulnerabilities_from_json(args.json_file, args.batch_size)


if __name__ == '__main__':
    asyncio.run(main())
