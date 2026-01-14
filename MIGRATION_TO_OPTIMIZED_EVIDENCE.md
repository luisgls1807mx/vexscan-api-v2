# Migración a Estructura Optimizada de Evidencias

## 🎯 Cambio Principal

**Antes (estructura anterior):**
- Cada archivo = 1 registro en `finding_evidence`
- Múltiples archivos = múltiples registros con `batch_id` compartido
- `description` y `comments` duplicados en cada registro

**Ahora (estructura optimizada):**
- Un grupo de archivos = 1 registro en `finding_evidence`
- Campo `files` JSONB contiene array de archivos: `[{...}, {...}, ...]`
- `description` y `comments` solo una vez por registro

## 📊 Comparación

### Estructura Anterior:
```sql
-- Si subes 5 archivos:
Registro 1: {file_name: "img1.jpg", batch_id: "abc", description: "..."}
Registro 2: {file_name: "img2.jpg", batch_id: "abc", description: "..."}  -- Duplicado
Registro 3: {file_name: "img3.jpg", batch_id: "abc", description: "..."}  -- Duplicado
Registro 4: {file_name: "img4.jpg", batch_id: "abc", description: "..."}  -- Duplicado
Registro 5: {file_name: "img5.jpg", batch_id: "abc", description: "..."}  -- Duplicado
```

### Estructura Optimizada:
```sql
-- Si subes 5 archivos:
Registro 1: {
  files: [
    {file_name: "img1.jpg", file_path: "...", ...},
    {file_name: "img2.jpg", file_path: "...", ...},
    {file_name: "img3.jpg", file_path: "...", ...},
    {file_name: "img4.jpg", file_path: "...", ...},
    {file_name: "img5.jpg", file_path: "...", ...}
  ],
  description: "...",  -- Solo una vez
  comments: "..."      -- Solo una vez
}
```

## ✅ Ventajas

1. **Menos registros**: 1 registro en lugar de N registros
2. **Sin duplicación**: `description` y `comments` solo una vez
3. **Más eficiente**: Menos espacio, menos índices, consultas más rápidas
4. **Más simple**: Estructura más clara y fácil de entender
5. **JSONB optimizado**: PostgreSQL tiene excelente soporte para JSONB con índices GIN

## 📝 Estructura de la Tabla

```sql
CREATE TABLE finding_evidence (
    id UUID PRIMARY KEY,
    finding_id UUID,
    workspace_id UUID,
    files JSONB NOT NULL,  -- Array de archivos
    description TEXT,       -- Compartido para todos los archivos
    comments TEXT,          -- Compartido para todos los archivos
    uploaded_by UUID,
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

## 📦 Formato del Campo `files`

```json
[
  {
    "file_name": "imagen1.jpg",
    "file_path": "workspace/finding/imagen1.jpg",
    "file_size": 1024000,
    "file_type": "image/jpeg",
    "file_hash": "sha256..."
  },
  {
    "file_name": "documento.pdf",
    "file_path": "workspace/finding/documento.pdf",
    "file_size": 2048000,
    "file_type": "application/pdf",
    "file_hash": "sha256..."
  }
]
```

## 🔄 Cómo Funciona

### Al Subir Archivos:

**1 archivo:**
```json
{
  "id": "uuid-1",
  "files": [{"file_name": "screenshot.png", ...}],
  "description": "Captura",
  "comments": "Vulnerabilidad"
}
```

**5 archivos juntos:**
```json
{
  "id": "uuid-1",
  "files": [
    {"file_name": "img1.jpg", ...},
    {"file_name": "img2.jpg", ...},
    {"file_name": "img3.jpg", ...},
    {"file_name": "img4.jpg", ...},
    {"file_name": "doc.pdf", ...}
  ],
  "description": "Evidencia del escaneo",  // Solo una vez
  "comments": "Múltiples capturas"          // Solo una vez
}
```

### Al Obtener Evidencias:

```json
[
  {
    "id": "uuid-1",
    "file_count": 5,
    "description": "Evidencia del escaneo",
    "comments": "Múltiples capturas",
    "files": [
      {"file_name": "img1.jpg", ...},
      {"file_name": "img2.jpg", ...},
      ...
    ]
  }
]
```

## 🚀 Para Aplicar

1. **Ejecutar SQL de migración** (si ya tienes datos):
   - Crear script para migrar datos existentes de la estructura anterior a la nueva

2. **Ejecutar nuevos archivos SQL**:
   - `create_table_finding_evidence_optimized.sql`
   - `fn_create_finding_evidence_optimized.sql`
   - `fn_list_finding_evidence_optimized.sql`
   - `fn_delete_finding_evidence_optimized.sql`

3. **El código Python ya está actualizado** para usar la nueva estructura

## ⚠️ Nota de Migración

Si ya tienes datos en la tabla anterior, necesitarás un script de migración para:
- Agrupar registros por `batch_id`
- Crear nuevos registros con el campo `files` JSONB
- Eliminar registros duplicados

¿Quieres que cree el script de migración también?

