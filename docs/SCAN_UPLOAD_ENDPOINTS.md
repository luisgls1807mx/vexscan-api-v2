# Endpoints de Subida de Escaneos - Documentación para Frontend

## Resumen de Endpoints Disponibles

Hay **4 opciones** de subida de archivos de escaneo. El frontend puede mostrar tabs para que el usuario elija el método:

| Tab | Nombre | Endpoint | Descripción |
|-----|--------|----------|-------------|
| 1 | Original | `/api/v1/scans/upload` | Método actual (puede fallar si el token expira) |
| 2 | Batch (Recomendado) | `/api/v1/scans-experimental/v1-batch-service-role` | Evita expiración de JWT |
| 3 | Async | `/api/v1/scans-experimental/v2-async-queue` | Retorna inmediato, procesa en background |
| 4 | Bulk RPC | `/api/v1/scans-experimental/v3-bulk-rpc` | Máximo rendimiento, transacción atómica |

---

## Tab 1: Original (No recomendado para archivos grandes)

### Endpoint
```
POST /api/v1/scans/upload
```

### Headers
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
X-Workspace-ID: {workspace_id}
```

### Body (form-data)
| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `file` | File | ✅ | Archivo .nessus, .xml, etc. |
| `project_id` | string | ❌ | ID del proyecto (recomendado) |
| `network_zone` | string | ❌ | "internal" o "external" (default: "internal") |
| `force_upload` | boolean | ❌ | `true` para permitir duplicados |

### Comportamiento
- Procesa el archivo síncronamente
- ⚠️ **Puede fallar** si el JWT expira durante archivos grandes
- Bloquea hasta que termine

### Respuesta Exitosa
```json
{
  "success": true,
  "message": "Scan processed successfully",
  "data": {
    "scan_import_id": "uuid",
    "scanner": "Nessus",
    "status": "processed",
    "assets_created": 10,
    "findings_created": 150,
    "findings_updated": 5
  }
}
```

---

## Tab 2: Batch Service Role (RECOMENDADO)

### Endpoint
```
POST /api/v1/scans-experimental/v1-batch-service-role
```

### Headers
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
X-Workspace-ID: {workspace_id}
```

### Body (form-data)
| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `file` | File | ✅ | Archivo .nessus, .xml, etc. |
| `project_id` | string | ❌ | ID del proyecto |
| `network_zone` | string | ❌ | "internal" o "external" |
| `force_upload` | boolean | ❌ | `true` para permitir duplicados |

### Comportamiento
- ✅ **No hay problema de JWT expiration** - usa service_role para DB
- Procesa en batches de 100 registros para mejor rendimiento
- Bloquea hasta que termine (pero es más rápido)

### Respuesta Exitosa
```json
{
  "success": true,
  "message": "Scan processed successfully (v1-batch-service-role)",
  "data": {
    "scan_import_id": "uuid",
    "scanner": "Nessus",
    "status": "processed",
    "approach": "v1_batch_service_role",
    "processing_time_seconds": 45.2,
    "assets_created": 10,
    "findings_created": 150,
    "findings_updated": 5
  }
}
```

### Cuándo Usar
- ✅ Archivos grandes (>5MB)
- ✅ Cuando el método original falla por JWT expiration
- ✅ Para usuarios que quieren esperar a que termine

---

## Tab 3: Async Queue (Mejor UX)

### Endpoint de Subida
```
POST /api/v1/scans-experimental/v2-async-queue
```

### Headers
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
X-Workspace-ID: {workspace_id}
```

### Body (form-data)
| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `file` | File | ✅ | Archivo .nessus, .xml, etc. |
| `project_id` | string | ❌ | ID del proyecto |
| `network_zone` | string | ❌ | "internal" o "external" |
| `force_upload` | boolean | ❌ | `true` para permitir duplicados |

### Comportamiento
- ✅ **Retorna inmediatamente** con un `job_id`
- El procesamiento ocurre en background
- Usuario debe hacer polling para verificar estado

### Respuesta Inmediata
```json
{
  "success": true,
  "message": "File uploaded and queued for processing",
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "approach": "v2_async_queue",
    "upload_time_seconds": 2.5,
    "message": "File uploaded and queued for processing. Poll /jobs/{job_id} for status.",
    "scanner": "Nessus"
  }
}
```

### Endpoint de Estado
```
GET /api/v1/scans-experimental/v2-async-queue/jobs/{job_id}
```

### Headers
```
Authorization: Bearer {access_token}
```

### Respuesta de Estado
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "processed",  // "queued", "processing", "processed", "failed"
    "file_name": "scan.nessus",
    "scanner": "Nessus",
    "findings_total": 150,
    "findings_new": 120,
    "findings_updated": 30,
    "hosts_total": 10,
    "error_message": null,
    "created_at": "2026-01-12T03:00:00Z",
    "processed_at": "2026-01-12T03:02:00Z"
  }
}
```

### Flujo en Frontend
```javascript
// 1. Subir archivo
const uploadResponse = await fetch('/api/v1/scans-experimental/v2-async-queue', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}`, 'X-Workspace-ID': workspaceId },
  body: formData
});
const { data: { job_id } } = await uploadResponse.json();

// 2. Mostrar spinner/progress

// 3. Poll cada 3 segundos
const pollInterval = setInterval(async () => {
  const statusResponse = await fetch(`/api/v1/scans-experimental/v2-async-queue/jobs/${job_id}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const { data: job } = await statusResponse.json();
  
  if (job.status === 'processed') {
    clearInterval(pollInterval);
    // Mostrar resultados
  } else if (job.status === 'failed') {
    clearInterval(pollInterval);
    // Mostrar error: job.error_message
  }
}, 3000);
```

### Cuándo Usar
- ✅ Mejor experiencia de usuario
- ✅ Archivos muy grandes
- ✅ Usuario puede continuar navegando mientras procesa

---

## Tab 4: Bulk RPC (Máximo Rendimiento)

### Endpoint
```
POST /api/v1/scans-experimental/v3-bulk-rpc
```

### Headers
```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
X-Workspace-ID: {workspace_id}
```

### Body (form-data)
| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `file` | File | ✅ | Archivo .nessus, .xml, etc. |
| `project_id` | string | ❌ | ID del proyecto |
| `network_zone` | string | ❌ | "internal" o "external" |
| `force_upload` | boolean | ❌ | `true` para permitir duplicados |

### Comportamiento
- Parsea el archivo en el backend
- Envía **todo** a la base de datos en **un solo RPC**
- ✅ Transacción atómica (todo o nada)
- ✅ Máximo rendimiento de base de datos

### Respuesta Exitosa
```json
{
  "success": true,
  "message": "Scan processed successfully (v3-bulk-rpc)",
  "data": {
    "scan_import_id": "uuid",
    "scanner": "Nessus",
    "status": "processed",
    "approach": "v3_bulk_rpc",
    "timing": {
      "parse_seconds": 5.2,
      "rpc_seconds": 10.1,
      "total_seconds": 18.5
    },
    "assets_count": 10,
    "findings_count": 150,
    "rpc_result": {
      "scan_import_id": "uuid",
      "processing_time_ms": 10100,
      "assets_created": 10,
      "findings_created": 120,
      "findings_updated": 30,
      "findings_reopened": 5
    }
  }
}
```

### Cuándo Usar
- ✅ Cuando se necesita máximo rendimiento
- ✅ Cuando la integridad transaccional es crítica
- ⚠️ Requiere que el RPC `fn_v3_bulk_insert_scan_data` esté desplegado en Supabase

---

## Manejo de Errores Comunes

### Error de Duplicado (409)
```json
{
  "success": false,
  "error": "Scan file 'archivo.nessus' already exists",
  "error_code": "DUPLICATE",
  "details": {}
}
```

**Acción en Frontend:**
1. Mostrar modal: "Este archivo ya fue subido. ¿Desea subirlo de todas formas?"
2. Si acepta, reenviar con `force_upload: true`

### Error de JWT Expirado (401)
```json
{
  "detail": "JWT expired"
}
```

**Acción en Frontend:**
- Solo ocurre en Tab 1 (Original)
- Sugerir usar Tab 2 (Batch) o Tab 3 (Async)

### Error de Archivo Inválido (400)
```json
{
  "success": false,
  "error": "Invalid Nessus file format",
  "error_code": "PARSE_ERROR"
}
```

---

## Endpoint de Información

Para obtener información sobre los enfoques disponibles:

```
GET /api/v1/scans-experimental/comparison-info
```

Respuesta:
```json
{
  "success": true,
  "data": {
    "approaches": [
      {
        "name": "v1-batch-service-role",
        "endpoint": "/api/v1/scans-experimental/v1-batch-service-role",
        "description": "Uses service_role for DB ops, batch inserts of 100 records",
        "best_for": "Large files, avoiding JWT expiration",
        "sync": true
      },
      {
        "name": "v2-async-queue",
        "endpoint": "/api/v1/scans-experimental/v2-async-queue",
        "description": "Returns immediately, processes in background",
        "best_for": "Best UX, non-blocking uploads",
        "sync": false,
        "status_endpoint": "/api/v1/scans-experimental/v2-async-queue/jobs/{job_id}"
      },
      {
        "name": "v3-bulk-rpc",
        "endpoint": "/api/v1/scans-experimental/v3-bulk-rpc",
        "description": "Single RPC call with atomic transaction",
        "best_for": "Maximum DB performance, data integrity",
        "sync": true
      }
    ],
    "recommendation": "Start with v1-batch-service-role for simplicity. Use v2-async-queue for better UX with large files."
  }
}
```

---

## Diseño de UI Sugerido

### Tabs
```
┌──────────────┬──────────────────────┬─────────────┬───────────────┐
│  📤 Estándar │ ⚡ Batch (Recomenda) │ 🔄 Async    │ 🚀 Bulk RPC   │
└──────────────┴──────────────────────┴─────────────┴───────────────┘
```

### Para cada Tab, mostrar:
- Descripción breve del método
- Ventajas/desventajas
- Progress bar o spinner según corresponda

### Estados del Async (Tab 3):
- `queued` → Spinner con "En cola..."
- `processing` → Progress bar animado con "Procesando..."
- `processed` → ✅ "Completado" con resumen
- `failed` → ❌ "Error" con mensaje
