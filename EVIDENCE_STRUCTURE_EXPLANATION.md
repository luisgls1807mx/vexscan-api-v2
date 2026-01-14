# Estructura de Evidencias - Explicación

## 📋 Cómo Funciona

### **Estructura de Datos:**

La tabla `finding_evidence` almacena **cada archivo como un registro individual**, pero cuando subes múltiples archivos juntos, se agrupan usando el campo `batch_id`.

### **Escenarios:**

#### **1. Subir UN solo archivo:**
```sql
-- Se crea 1 registro:
{
  id: "uuid-1",
  finding_id: "finding-123",
  file_name: "screenshot.png",
  file_path: "workspace/finding/screenshot.png",
  batch_id: NULL,  -- Sin batch (archivo individual)
  description: "Captura de pantalla",
  comments: "Vulnerabilidad visible"
}
```

#### **2. Subir MÚLTIPLES archivos juntos:**
```sql
-- Se crean 3 registros, todos con el mismo batch_id:
-- Registro 1:
{
  id: "uuid-1",
  finding_id: "finding-123",
  file_name: "imagen1.jpg",
  file_path: "workspace/finding/imagen1.jpg",
  batch_id: "batch-abc-123",  -- Mismo batch_id
  description: "Evidencia del escaneo",  -- Compartido
  comments: "Múltiples capturas del problema"  -- Compartido
}

-- Registro 2:
{
  id: "uuid-2",
  finding_id: "finding-123",
  file_name: "imagen2.jpg",
  file_path: "workspace/finding/imagen2.jpg",
  batch_id: "batch-abc-123",  -- Mismo batch_id
  description: "Evidencia del escaneo",  -- Compartido
  comments: "Múltiples capturas del problema"  -- Compartido
}

-- Registro 3:
{
  id: "uuid-3",
  finding_id: "finding-123",
  file_name: "documento.pdf",
  file_path: "workspace/finding/documento.pdf",
  batch_id: "batch-abc-123",  -- Mismo batch_id
  description: "Evidencia del escaneo",  -- Compartido
  comments: "Múltiples capturas del problema"  -- Compartido
}
```

### **Cómo se Obtienen las Evidencias:**

#### **Opción 1: Agrupadas (Recomendado) - `fn_list_finding_evidence`**
```json
[
  {
    "batch_id": "batch-abc-123",
    "description": "Evidencia del escaneo",
    "comments": "Múltiples capturas del problema",
    "uploaded_by": "user-uuid",
    "uploaded_by_name": "Juan Pérez",
    "created_at": "2026-01-06T10:00:00Z",
    "file_count": 3,
    "files": [
      {
        "id": "uuid-1",
        "file_name": "imagen1.jpg",
        "file_path": "workspace/finding/imagen1.jpg",
        "file_size": 1024000,
        "file_type": "image/jpeg",
        "created_at": "2026-01-06T10:00:00Z"
      },
      {
        "id": "uuid-2",
        "file_name": "imagen2.jpg",
        ...
      },
      {
        "id": "uuid-3",
        "file_name": "documento.pdf",
        ...
      }
    ]
  },
  {
    "batch_id": null,  // Archivo individual
    "description": "Captura de pantalla",
    "comments": "Vulnerabilidad visible",
    "file_count": 1,
    "files": [
      {
        "id": "uuid-4",
        "file_name": "screenshot.png",
        ...
      }
    ]
  }
]
```

#### **Opción 2: Plana (Individual) - `fn_list_finding_evidence_flat`**
```json
[
  {
    "id": "uuid-1",
    "batch_id": "batch-abc-123",
    "file_name": "imagen1.jpg",
    "description": "Evidencia del escaneo",
    "comments": "Múltiples capturas del problema",
    ...
  },
  {
    "id": "uuid-2",
    "batch_id": "batch-abc-123",
    "file_name": "imagen2.jpg",
    "description": "Evidencia del escaneo",
    "comments": "Múltiples capturas del problema",
    ...
  },
  {
    "id": "uuid-3",
    "batch_id": "batch-abc-123",
    "file_name": "documento.pdf",
    "description": "Evidencia del escaneo",
    "comments": "Múltiples capturas del problema",
    ...
  }
]
```

## 🔄 Flujo de Trabajo

### **Al Subir Múltiples Archivos:**

1. **Frontend envía:**
   ```
   POST /api/v1/evidence/findings/{finding_id}/upload
   files: [archivo1.jpg, archivo2.pdf, documento.docx]
   description: "Evidencia del escaneo"
   comments: "Múltiples capturas del problema"
   ```

2. **Backend:**
   - Genera un `batch_id` único (ej: `batch-abc-123`)
   - Sube cada archivo a storage
   - Crea 3 registros en `finding_evidence`, todos con:
     - Mismo `batch_id`
     - Misma `description`
     - Mismos `comments`

3. **Resultado:**
   - 3 archivos en storage
   - 3 registros en la tabla
   - Todos agrupados por `batch_id`

### **Al Obtener Evidencias:**

**Usando `fn_list_finding_evidence` (agrupado):**
- Los 3 archivos aparecen como **un solo grupo**
- Un solo `description` y `comments` para los 3 archivos
- Array `files` con los 3 archivos dentro

**Usando `fn_list_finding_evidence_flat` (plano):**
- Cada archivo aparece como registro individual
- Puedes ver que comparten `batch_id`

## 📊 Resumen

| Escenario | Registros en BD | batch_id | description/comments |
|-----------|----------------|----------|---------------------|
| 1 archivo | 1 registro | `NULL` | Individual |
| 5 archivos juntos | 5 registros | `batch-abc-123` (mismo) | Compartidos |
| 1 archivo después | 1 registro | `NULL` | Individual |

**Ventajas:**
- ✅ Puedes subir múltiples archivos con un solo comentario
- ✅ Los archivos se agrupan lógicamente
- ✅ Puedes ver archivos individuales o agrupados según necesites
- ✅ Mantiene flexibilidad para archivos individuales

