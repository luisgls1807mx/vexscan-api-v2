# Cómo Crear un Registro de Cambio de Estatus

## 📋 Función Utilizada

**`fn_update_finding_status`** - Esta función:
1. ✅ Actualiza el estatus del finding
2. ✅ Crea un registro en `finding_status_history`
3. ✅ Retorna el `status_change_id` para relacionar evidencias después

## 🔄 Flujo Completo

### **1. Cambiar Estatus (crea el registro automáticamente)**

**Endpoint:**
```
PUT /api/v1/findings/{finding_id}/status
```

**Request Body:**
```json
{
    "status": "In Progress",
    "comment": "Empezando a trabajar en la vulnerabilidad"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Status updated to 'In Progress'",
    "data": {
        "finding_id": "finding-uuid",
        "from_status": "Open",
        "to_status": "In Progress",
        "status_change_id": "status-change-uuid",  // ← IMPORTANTE: Usar para relacionar evidencias
        "comment": "Empezando a trabajar...",
        "changed_by": "user-uuid",
        "changed_at": "2026-01-07T10:00:00Z"
    }
}
```

### **2. Relacionar Evidencia con el Cambio de Estatus**

**Endpoint:**
```
POST /api/v1/evidence/findings/{finding_id}/upload
```

**Request Body (Form Data):**
```
files: [archivo1.jpg, archivo2.pdf]
description: "Evidencia de mitigación"
comments: "Parches aplicados y configuración actualizada"
related_status_change_id: "status-change-uuid"  // ← ID del cambio de estatus
```

## 📝 Ejemplos de Uso

### **Ejemplo 1: Cambio de estatus sin evidencia**

```python
# 1. Cambiar estatus
PUT /api/v1/findings/{finding_id}/status
{
    "status": "In Progress",
    "comment": "Empezando a trabajar"
}

# Respuesta incluye status_change_id, pero no se usa
# No se requiere evidencia para este cambio
```

### **Ejemplo 2: Cambio de estatus con evidencia (una persona)**

```python
# 1. Cambiar estatus
PUT /api/v1/findings/{finding_id}/status
{
    "status": "Mitigated",
    "comment": "Vulnerabilidad mitigada"
}

# Respuesta:
{
    "data": {
        "status_change_id": "status-change-uuid-123"  // ← Guardar este ID
    }
}

# 2. Subir evidencia relacionada
POST /api/v1/evidence/findings/{finding_id}/upload
Form Data:
- files: [parches.pdf, config.jpg]
- description: "Parches aplicados"
- related_status_change_id: "status-change-uuid-123"  // ← Usar el ID
```

### **Ejemplo 3: Múltiples personas suben evidencias para el mismo cambio**

```python
# 1. Cambio de estatus a "Mitigated"
PUT /api/v1/findings/{finding_id}/status
{
    "status": "Mitigated",
    "comment": "Vulnerabilidad mitigada"
}

# Respuesta: status_change_id = "status-change-uuid-123"

# 2. Admin sube evidencia
POST /api/v1/evidence/findings/{finding_id}/upload
Form Data:
- files: [parches.pdf]
- related_status_change_id: "status-change-uuid-123"

# 3. Ingeniero de Redes sube evidencia (mismo cambio)
POST /api/v1/evidence/findings/{finding_id}/upload
Form Data:
- files: [config.jpg]
- related_status_change_id: "status-change-uuid-123"  // ← Mismo ID

# 4. Tester sube evidencia (mismo cambio)
POST /api/v1/evidence/findings/{finding_id}/upload
Form Data:
- files: [test_results.pdf]
- related_status_change_id: "status-change-uuid-123"  // ← Mismo ID
```

## 🔍 Validaciones de la Función

### **Estatus que requieren comentario:**
- `Mitigated`
- `Accepted Risk`
- `False Positive`
- `Not Observed`

**Validación:** Comentario mínimo de 10 caracteres

### **Estatus que requiere evidencia:**
- `Mitigated` - Debe haber al menos una evidencia activa para el finding

## 📊 Estructura de `finding_status_history`

Después de ejecutar `fn_update_finding_status`, se crea un registro con:

```sql
{
    id: UUID,                    -- status_change_id (retornado)
    workspace_id: UUID,
    finding_id: UUID,
    from_status: finding_status,
    to_status: finding_status,
    comment: TEXT,
    changed_by: UUID,
    created_at: TIMESTAMPTZ
}
```

## ✅ Para Aplicar

**Ejecutar en Supabase SQL Editor:**
1. `fn_update_finding_status.sql` - Función principal

**Nota:** Esta función debe existir antes de poder cambiar estatus desde el frontend.

## 💡 Flujo Recomendado en Frontend

1. **Usuario cambia estatus** → Llama a `PUT /api/v1/findings/{finding_id}/status`
2. **Guardar `status_change_id`** de la respuesta
3. **Si el usuario sube evidencia** → Usar `status_change_id` en `related_status_change_id`
4. **Si múltiples personas suben evidencias** → Todas usan el mismo `status_change_id`

## 🔗 Relación Completa

```
finding_status_history (1) ←→ (N) finding_evidence
     id (status_change_id)    related_status_change_id
```

- Un cambio de estatus puede tener múltiples evidencias
- Cada evidencia puede estar relacionada con un cambio de estatus (o no)

