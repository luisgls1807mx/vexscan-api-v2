# Scripts de Procesamiento de Catálogo Nessus

Scripts standalone para procesar archivos Nessus y poblar el catálogo de vulnerabilidades sin depender de la API FastAPI.

## 📁 Archivos

- **`process_nessus_catalog.py`**: Script completo que parsea, traduce e inserta
- **`insert_from_json.py`**: Script simple para insertar desde JSON ya traducido

## 🚀 Uso Rápido

### Opción 1: Proceso Completo (Parsear + Traducir + Insertar)

```bash
# Activar entorno virtual
.venv\Scripts\activate

# Ejecutar proceso completo
python scripts/process_nessus_catalog.py "ruta/al/archivo.nessus"
```

Esto hará:
1. ✅ Parsear el archivo Nessus
2. ✅ Guardar JSON con vulnerabilidades parseadas
3. ✅ Traducir con Claude (si `ANTHROPIC_API_KEY` está configurada)
4. ✅ Guardar JSON con traducciones
5. ✅ Insertar a la BD en batches pequeños (10 a la vez)

### Opción 2: Solo Parsear (Sin Traducir)

```bash
python scripts/process_nessus_catalog.py "archivo.nessus" --skip-translate --skip-insert
```

Esto solo parseará y guardará el JSON. Útil para revisar las vulnerabilidades antes de traducir.

### Opción 3: Usar JSON Existente

Si ya tienes un JSON traducido y solo quieres insertarlo:

```bash
python scripts/insert_from_json.py "data/catalog_processing/archivo_translated.json"
```

O con el script principal:

```bash
python scripts/process_nessus_catalog.py "archivo.nessus" \
    --skip-parse \
    --skip-translate \
    --translated-json "data/catalog_processing/archivo_translated.json"
```

## 📊 Archivos Generados

Los archivos se guardan en `data/catalog_processing/`:

```
data/catalog_processing/
├── archivo_20260121_160000_parsed.json       # Vulnerabilidades parseadas
├── archivo_20260121_160000_translated.json   # Con traducciones
└── archivo_20260121_160000_results.json      # Resultados de inserción
```

### Estructura del JSON Parseado

```json
{
  "metadata": {
    "source_file": "archivo.nessus",
    "parsed_at": "2026-01-21T16:00:00",
    "total_hosts": 110,
    "total_findings": 6818,
    "unique_vulnerabilities": 283
  },
  "vulnerabilities": [
    {
      "scanner": "nessus",
      "plugin_id": "12345",
      "title": "Vulnerability Title",
      "severity": "High",
      "synopsis": "...",
      "description": "...",
      "solution": "...",
      "plugin_family": "...",
      "cvss_score": 7.5,
      "cvss3_score": 8.2,
      "cve": ["CVE-2023-1234"],
      "references": [...]
    }
  ]
}
```

### Estructura del JSON Traducido

Igual que el parseado, pero con campos adicionales:

```json
{
  "metadata": {
    ...
    "translated_at": "2026-01-21T16:10:00",
    "translation_model": "claude-3-5-haiku-20241022",
    "total_tokens_in": 50000,
    "total_tokens_out": 60000,
    "estimated_cost_usd": 0.0875
  },
  "vulnerabilities": [
    {
      ...
      "title_es": "Título en Español",
      "synopsis_es": "...",
      "description_es": "...",
      "solution_es": "...",
      "is_translated": true
    }
  ]
}
```

## 🔧 Opciones Avanzadas

### Cambiar Tamaño de Batch para Inserción

```bash
python scripts/insert_from_json.py "archivo.json" --batch-size 5
```

### Saltar Pasos Específicos

```bash
# Solo parsear (sin traducir ni insertar)
python scripts/process_nessus_catalog.py "archivo.nessus" --skip-translate --skip-insert

# Solo traducir (usar JSON parseado existente)
python scripts/process_nessus_catalog.py "archivo.nessus" \
    --parsed-json "data/catalog_processing/archivo_parsed.json" \
    --skip-insert

# Solo insertar (usar JSON traducido existente)
python scripts/process_nessus_catalog.py "archivo.nessus" \
    --skip-parse \
    --skip-translate \
    --translated-json "data/catalog_processing/archivo_translated.json"
```

## 💡 Casos de Uso

### Caso 1: Primera Vez (Sin Traducciones Previas)

```bash
# 1. Parsear y guardar JSON (sin gastar tokens todavía)
python scripts/process_nessus_catalog.py "archivo.nessus" --skip-translate --skip-insert

# 2. Revisar el JSON parseado
cat data/catalog_processing/archivo_*_parsed.json

# 3. Si todo se ve bien, traducir e insertar
python scripts/process_nessus_catalog.py "archivo.nessus" \
    --parsed-json "data/catalog_processing/archivo_*_parsed.json"
```

### Caso 2: Ya Tengo Traducciones (Falló la Inserción)

```bash
# Usar el JSON traducido existente para reintentar inserción
python scripts/insert_from_json.py "data/catalog_processing/archivo_translated.json"
```

### Caso 3: Traducir Después

```bash
# 1. Primero parsear sin traducir
python scripts/process_nessus_catalog.py "archivo.nessus" --skip-translate --skip-insert

# 2. Más tarde, traducir usando el JSON parseado
python scripts/process_nessus_catalog.py "archivo.nessus" \
    --parsed-json "data/catalog_processing/archivo_parsed.json" \
    --skip-insert

# 3. Finalmente, insertar
python scripts/insert_from_json.py "data/catalog_processing/archivo_translated.json"
```

## ⚠️ Notas Importantes

1. **Traducciones**: Requiere `ANTHROPIC_API_KEY` en `.env`
2. **Batches**: Se insertan de 10 en 10 para evitar timeouts
3. **Duplicados**: El script verifica automáticamente y omite vulnerabilidades ya existentes
4. **Reintentos**: Si falla la inserción, puedes reintentar con el JSON traducido sin gastar más tokens
5. **Costos**: El script muestra el costo estimado de las traducciones

## 🐛 Solución de Problemas

### Error: "ANTHROPIC_API_KEY not found"

Asegúrate de tener el archivo `.env` con:
```
ANTHROPIC_API_KEY=tu_api_key_aqui
```

O ejecuta sin traducir:
```bash
python scripts/process_nessus_catalog.py "archivo.nessus" --skip-translate
```

### Error: Timeout en Base de Datos

El script ya usa batches pequeños (10), pero si aún falla:
```bash
python scripts/insert_from_json.py "archivo.json" --batch-size 5
```

### Error: Archivo no encontrado

Usa rutas absolutas o relativas correctas:
```bash
python scripts/process_nessus_catalog.py "C:\Users\...\archivo.nessus"
```

## 📈 Ejemplo de Salida

```
################################################################################
# PROCESADOR DE CATÁLOGO NESSUS
################################################################################

================================================================================
PASO 1: Parseando archivo Nessus
================================================================================
Archivo: archivo.nessus
✓ Hosts encontrados: 110
✓ Findings totales: 6818
✓ Vulnerabilidades únicas: 283
✓ Guardado en: data/catalog_processing/archivo_20260121_160000_parsed.json

================================================================================
PASO 2: Traduciendo vulnerabilidades
================================================================================
Total a traducir: 283
Modelo: claude-3-5-haiku-20241022

Batch 1/57 (5 items)...
✓ Traducido correctamente

...

✓ Traducción completa
✓ Tokens: 50000 in / 60000 out
✓ Costo estimado: $0.0875 USD
✓ Guardado en: data/catalog_processing/archivo_20260121_160000_translated.json

================================================================================
PASO 3: Insertando al catálogo de vulnerabilidades
================================================================================
Total a insertar: 283

Verificando vulnerabilidades existentes...
✓ Encontradas 0 vulnerabilidades existentes
✓ Nuevas vulnerabilidades a insertar: 283
✓ Ya existentes (se omitirán): 0

Insertando batch 1/29 (10 items)...
✓ Insertado correctamente

...

================================================================================
RESUMEN FINAL
================================================================================
✓ Insertadas: 283
✓ Omitidas (ya existían): 0
✗ Errores: 0
✓ Resultados guardados en: data/catalog_processing/archivo_20260121_160000_results.json

################################################################################
# PROCESO COMPLETADO
################################################################################
```
