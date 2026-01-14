# Resumen: Relación entre Cambios de Estatus y Evidencias

## ✅ Estructura Implementada

### **1. Campo `related_status_change_id` en `finding_evidence`**

```sql
ALTER TABLE finding_evidence
ADD COLUMN related_status_change_id UUID REFERENCES finding_status_history(id);
```

**Características:**
- ✅ **Opcional** (puede ser NULL)
- ✅ Permite evidencias independientes (sin cambio de estatus)
- ✅ Permite múltiples evidencias para el mismo cambio de estatus
- ✅ Relación con `finding_status_history`

### **2. Función Actualizada: `fn_create_finding_evidence`**

Ahora acepta parámetro opcional `p_related_status_change_id`:

```sql
fn_create_finding_evidence(
    p_finding_id UUID,
    p_files JSONB,
    p_description TEXT,
    p_comments TEXT,
    p_evidence_type TEXT,
    p_related_status_change_id UUID  -- NUEVO: opcional
)
```

### **3. Función Nueva: `fn_get_finding_status_history_with_evidence`**

Retorna historial completo con evidencias relacionadas agrupadas por cambio de estatus.

## 🔄 Casos de Uso Soportados

### **Caso 1: Cambio de estatus sin evidencia**
```python
# 1. Cambiar estatus
POST /api/v1/findings/{finding_id}/status
{
    "status": "In Progress",
    "comment": "Empezando a trabajar"
}

# 2. No se sube evidencia (related_status_change_id = NULL)
```

### **Caso 2: Cambio de estatus con evidencia (una persona)**
```python
# 1. Cambiar estatus
POST /api/v1/findings/{finding_id}/status
{
    "status": "Mitigated",
    "comment": "Vulnerabilidad mitigada"
}
# Retorna: status_change_id = "status-change-uuid"

# 2. Subir evidencia relacionada
POST /api/v1/evidence/findings/{finding_id}/upload
{
    "files": [...],
    "description": "Parches aplicados",
    "related_status_change_id": "status-change-uuid"  # Relacionar con el cambio
}
```

### **Caso 3: Múltiples personas suben evidencias para el mismo cambio de estatus**
```python
# 1. Cambio de estatus a "Mitigated"
POST /api/v1/findings/{finding_id}/status
{
    "status": "Mitigated",
    "comment": "Vulnerabilidad mitigada"
}
# Retorna: status_change_id = "status-change-uuid"

# 2. Admin sube evidencia
POST /api/v1/evidence/findings/{finding_id}/upload
{
    "files": [...],
    "related_status_change_id": "status-change-uuid"
}

# 3. Ingeniero de Redes sube evidencia (mismo cambio de estatus)
POST /api/v1/evidence/findings/{finding_id}/upload
{
    "files": [...],
    "related_status_change_id": "status-change-uuid"  # Mismo cambio
}

# 4. Tester sube evidencia (mismo cambio de estatus)
POST /api/v1/evidence/findings/{finding_id}/upload
{
    "files": [...],
    "related_status_change_id": "status-change-uuid"  # Mismo cambio
}
```

### **Caso 4: Evidencia independiente (sin cambio de estatus)**
```python
# Subir evidencia sin relacionarla con cambio de estatus
POST /api/v1/evidence/findings/{finding_id}/upload
{
    "files": [...],
    "description": "Evidencia adicional",
    # related_status_change_id no se envía (NULL)
}
```

## 📊 Ejemplo de Respuesta

### **Historial con Evidencias:**

```json
[
  {
    "id": "status-change-1",
    "from_status": "Open",
    "to_status": "In Progress",
    "comment": "Empezando a trabajar",
    "changed_by_name": "Admin",
    "created_at": "2026-01-07T10:00:00Z",
    "related_evidence": [],  // Sin evidencias
    "evidence_count": 0
  },
  {
    "id": "status-change-2",
    "from_status": "In Progress",
    "to_status": "Mitigated",
    "comment": "Vulnerabilidad mitigada",
    "changed_by_name": "Admin",
    "created_at": "2026-01-07T11:00:00Z",
    "related_evidence": [
      {
        "id": "evidence-1",
        "uploaded_by_name": "Admin",
        "file_count": 2,
        "description": "Parches aplicados"
      },
      {
        "id": "evidence-2",
        "uploaded_by_name": "Ingeniero de Redes",
        "file_count": 1,
        "description": "Configuración actualizada"
      },
      {
        "id": "evidence-3",
        "uploaded_by_name": "Tester",
        "file_count": 1,
        "description": "Pruebas realizadas"
      }
    ],
    "evidence_count": 3
  }
]
```

## 🚀 Para Aplicar

### **Orden de Ejecución:**

1. **Ejecutar**: `alter_table_finding_evidence_add_status_change.sql`
   - Agrega columna `related_status_change_id`

2. **Ejecutar**: `fn_create_finding_evidence_optimized.sql` (actualizado)
   - Función ahora acepta `p_related_status_change_id`

3. **Ejecutar**: `fn_list_finding_evidence_optimized.sql` (actualizado)
   - Incluye información del cambio de estatus relacionado

4. **Ejecutar**: `fn_get_finding_status_history_with_evidence.sql` (nuevo)
   - Función para obtener historial con evidencias

## 💡 Ventajas

1. ✅ **Flexibilidad**: Evidencias pueden estar relacionadas o no
2. ✅ **Colaboración**: Múltiples personas pueden subir evidencias para el mismo cambio
3. ✅ **Trazabilidad**: Saber qué evidencia está relacionada con qué cambio de estatus
4. ✅ **Historial Completo**: Ver todo el flujo de trabajo con evidencias agrupadas
5. ✅ **Retrocompatibilidad**: Evidencias existentes siguen funcionando (related_status_change_id = NULL)

## 📝 Notas

- El campo `related_status_change_id` es **opcional**
- Si es NULL, la evidencia es independiente
- Múltiples evidencias pueden tener el mismo `related_status_change_id`
- La función valida que el cambio de estatus pertenezca al mismo finding

