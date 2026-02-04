"""
Script simple para traducir un JSON parseado de Nessus usando Claude API directamente.
"""

import sys
import os
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Cargar .env ANTES de cualquier import
from dotenv import load_dotenv
load_dotenv()

import httpx


async def translate_vulnerabilities(input_file: str, output_file: str):
    """Traduce vulnerabilidades de un JSON parseado."""
    
    # Verificar API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY no encontrada en .env")
        return
    
    print(f"✓ API Key encontrada: {api_key[:20]}...")
    
    # Leer JSON parseado
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    vulnerabilities = data['vulnerabilities']
    total = len(vulnerabilities)
    
    print(f"\n{'='*80}")
    print(f"Traduciendo {total} vulnerabilidades")
    print(f"{'='*80}\n")
    
    # Traducir en batches
    batch_size = 5
    total_batches = (total + batch_size - 1) // batch_size
    
    translated_vulns = []
    total_tokens_in = 0
    total_tokens_out = 0
    
    for i in range(0, total, batch_size):
        batch = vulnerabilities[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        print(f"Batch {batch_num}/{total_batches} ({len(batch)} items)...")
        
        try:
            # Preparar prompt
            items_to_translate = []
            for v in batch:
                item = {
                    'plugin_id': v.get('plugin_id'),
                    'title': v.get('title'),
                    'synopsis': v.get('synopsis'),
                    'description': v.get('description')[:2000] if v.get('description') else None,
                    'solution': v.get('solution')[:1000] if v.get('solution') else None
                }
                items_to_translate.append(item)
            
            prompt = f"""Traduce las siguientes {len(items_to_translate)} vulnerabilidades al español.
Mantén términos técnicos en inglés (SSL, TLS, SSH, HTTP, CVE, etc.).

VULNERABILIDADES:
{json.dumps(items_to_translate, indent=2, ensure_ascii=False)}

Responde con un array JSON donde cada elemento tenga:
- "plugin_id": el ID original
- "title_es": título traducido
- "synopsis_es": sinopsis traducida
- "description_es": descripción traducida
- "solution_es": solución traducida

IMPORTANTE: Responde SOLO con el array JSON, sin texto adicional."""

            payload = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 4000,
                "temperature": 0.1,
                "system": "Eres un traductor experto en ciberseguridad. Traduce del inglés al español manteniendo términos técnicos.",
                "messages": [{"role": "user", "content": prompt}]
            }
            
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                resp_data = response.json()
                raw_content = resp_data["content"][0]["text"]
                
                usage = resp_data.get("usage", {})
                tokens_in = usage.get('input_tokens', 0)
                tokens_out = usage.get('output_tokens', 0)
                total_tokens_in += tokens_in
                total_tokens_out += tokens_out
                
                print(f"  Tokens: {tokens_in} in / {tokens_out} out")
                
                # Parse respuesta
                content = raw_content.strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    content = "\n".join(lines)
                
                translations = json.loads(content)
                
                # Combinar con datos originales
                trans_dict = {str(t['plugin_id']): t for t in translations}
                for orig in batch:
                    pid = str(orig.get('plugin_id'))
                    trans = trans_dict.get(pid, {})
                    
                    combined = {**orig}
                    combined['title_es'] = trans.get('title_es')
                    combined['synopsis_es'] = trans.get('synopsis_es')
                    combined['description_es'] = trans.get('description_es')
                    combined['solution_es'] = trans.get('solution_es')
                    combined['is_translated'] = bool(trans.get('title_es'))
                    translated_vulns.append(combined)
            
            # Pausa entre batches
            if i + batch_size < total:
                await asyncio.sleep(0.3)
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            # Agregar sin traducción
            for orig in batch:
                combined = {**orig}
                combined['is_translated'] = False
                translated_vulns.append(combined)
    
    # Calcular costo
    cost_per_1m_in = 0.25
    cost_per_1m_out = 1.25
    estimated_cost = (total_tokens_in / 1_000_000 * cost_per_1m_in) + \
                    (total_tokens_out / 1_000_000 * cost_per_1m_out)
    
    print(f"\n{'='*80}")
    print(f"✓ Traducción completada")
    print(f"  Total tokens: {total_tokens_in} in / {total_tokens_out} out")
    print(f"  Costo estimado: ${estimated_cost:.4f} USD")
    print(f"{'='*80}\n")
    
    # Guardar resultado
    result = {
        'metadata': {
            **data['metadata'],
            'translated_at': datetime.now().isoformat(),
            'translation_model': 'claude-3-haiku-20240307',
            'total_tokens_in': total_tokens_in,
            'total_tokens_out': total_tokens_out,
            'estimated_cost_usd': round(estimated_cost, 4)
        },
        'vulnerabilities': translated_vulns
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Guardado en: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traducir JSON de Nessus parseado")
    parser.add_argument("input_file", help="Archivo JSON parseado")
    parser.add_argument("output_file", help="Archivo JSON traducido de salida")
    
    args = parser.parse_args()
    
    asyncio.run(translate_vulnerabilities(args.input_file, args.output_file))
