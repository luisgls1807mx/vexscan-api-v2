# Resumen: Estructura Optimizada de Evidencias

## ✅ Estructura Final Implementada

### **Tabla `finding_evidence`:**

```sql
CREATE TABLE finding_evidence (
    id UUID PRIMARY KEY,
    finding_id UUID,
    workspace_id UUID,
    files JSONB NOT NULL,  -- Array de archivos: [{...}, {...}]
    description TEXT,       -- Compartido para todos los archivos
    comments TEXT,          -- Compartido para todos los archivos
    uploaded_by UUID,
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

### **Ventajas vs Estructura Anterior:**

| Aspecto | Estructura Anterior | Estructura Optimizada |
|---------|---------------------|----------------------|
| **Registros** | N registros (1 por archivo) | 1 registro (con N archivos) |
| **Duplicación** | `description` y `comments` duplicados | Sin duplicación |
| **Espacio** | Más espacio | Menos espacio |
| **Consultas** | Más complejas (GROUP BY) | Más simples |
| **Índices** | Más índices necesarios | Menos índices |

## 📦 Formato del Campo `files` (JSONB)

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

## 🔄 Flujo de Trabajo

### **Subir Archivos:**

**1 archivo:**
```python
POST /api/v1/evidence/findings/{finding_id}/upload
files: [archivo1.jpg]
description: "Captura"
comments: "Vulnerabilidad"

# Resultado: 1 registro con files: [{archivo1.jpg}]
```

**5 archivos:**
```python
POST /api/v1/evidence/findings/{finding_id}/upload
files: [img1.jpg, img2.jpg, img3.jpg, img4.jpg, doc.pdf]
description: "Evidencia del escaneo"
comments: "Múltiples capturas"

# Resultado: 1 registro con files: [img1, img2, img3, img4, doc]
```

### **Obtener Evidencias:**

```json
[
  {
    "id": "uuid-1",
    "finding_id": "finding-123",
    "file_count": 5,
    "description": "Evidencia del escaneo",
    "comments": "Múltiples capturas",
    "files": [
      {"file_name": "img1.jpg", "file_path": "...", ...},
      {"file_name": "img2.jpg", "file_path": "...", ...},
      ...
    ],
    "uploaded_by": "user-uuid",
    "created_at": "2026-01-06T10:00:00Z"
  }
]
```

### **Eliminar Evidencia:**

```python
DELETE /api/v1/evidence/findings/{finding_id}/{evidence_id}

# Elimina el registro completo (con todos sus archivos)
# También elimina todos los archivos del storage
```

## 📁 Archivos SQL Creados

1. **`create_table_finding_evidence_optimized.sql`**
   - Tabla optimizada con campo `files` JSONB
   - Índices GIN para búsquedas en JSONB
   - Políticas RLS

2. **`fn_create_finding_evidence_optimized.sql`**
   - Función para crear evidencia (1 o múltiples archivos)
   - Un solo registro con array JSONB

3. **`fn_list_finding_evidence_optimized.sql`**
   - Lista evidencias agrupadas
   - Cada registro puede tener múltiples archivos

4. **`fn_delete_finding_evidence_optimized.sql`**
   - Elimina registro completo
   - Retorna información de archivos para limpiar storage

5. **`migrate_finding_evidence_to_optimized.sql`**
   - Script de migración (si ya tienes datos)

## 🚀 Para Aplicar

### **Si NO tienes datos aún:**

1. Ejecutar `create_table_finding_evidence_optimized.sql`
2. Ejecutar `fn_create_finding_evidence_optimized.sql`
3. Ejecutar `fn_list_finding_evidence_optimized.sql`
4. Ejecutar `fn_delete_finding_evidence_optimized.sql`
5. Ejecutar `storage_policies_evidence.sql`

### **Si YA tienes datos:**

1. Ejecutar `migrate_finding_evidence_to_optimized.sql` (revisar resultados)
2. Si la migración es exitosa, renombrar tablas
3. Ejecutar los archivos SQL optimizados
4. Eliminar tabla antigua después de verificar

## 💻 Código Python Actualizado

- ✅ `app/routes/evidence.py` - Endpoint de upload actualizado
- ✅ `app/routes/evidence.py` - Endpoint de delete actualizado
- ✅ `fn_list_findings.sql` - `evidence_count` actualizado para contar archivos en JSONB

## ✨ Beneficios Finales

1. **Eficiencia**: Menos registros, menos espacio, consultas más rápidas
2. **Simplicidad**: Estructura más clara y fácil de entender
3. **Escalabilidad**: JSONB es muy eficiente en PostgreSQL
4. **Mantenibilidad**: Menos código duplicado, más fácil de mantener

