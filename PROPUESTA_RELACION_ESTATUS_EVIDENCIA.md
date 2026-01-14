# Propuesta: Relación entre Cambios de Estatus y Evidencias

## 📋 Requisitos Identificados

1. **Cambios de estatus sin evidencia**: Cambiar estatus sin necesidad de subir evidencia
2. **Múltiples personas suben evidencias**: Diferentes personas pueden subir evidencias para la misma vulnerabilidad
3. **Evidencias relacionadas con cambios de estatus**: Saber qué evidencia está relacionada con qué cambio de estatus
4. **Evidencias independientes**: Evidencias que no están relacionadas con un cambio de estatus específico

## 🎯 Solución Propuesta

### **Opción A: Campo Opcional `related_status_change_id` (Recomendada)**

Agregar un campo opcional en `finding_evidence` para relacionar evidencia con un cambio de estatus:

```sql
ALTER TABLE finding_evidence
ADD COLUMN related_status_change_id UUID REFERENCES finding_status_history(id) ON DELETE SET NULL;
```

**Ventajas:**
- ✅ Evidencias pueden estar relacionadas o no con cambios de estatus
- ✅ Múltiples evidencias pueden relacionarse con el mismo cambio de estatus
- ✅ Un cambio de estatus puede tener múltiples evidencias (diferentes personas)
- ✅ Flexible: permite evidencias independientes

**Ejemplo de uso:**
- Cambio de estatus "En Proceso" → "Finalizado" (sin evidencia)
- Usuario A sube evidencia relacionada con ese cambio de estatus
- Usuario B sube evidencia relacionada con el mismo cambio de estatus
- Usuario C sube evidencia independiente (no relacionada con cambio de estatus)

### **Opción B: Tabla de Relación Many-to-Many**

Crear tabla intermedia `finding_status_evidence`:

```sql
CREATE TABLE finding_status_evidence (
    status_change_id UUID REFERENCES finding_status_history(id),
    evidence_id UUID REFERENCES finding_evidence(id),
    PRIMARY KEY (status_change_id, evidence_id)
);
```

**Ventajas:**
- ✅ Relación many-to-many completa
- ✅ Una evidencia puede relacionarse con múltiples cambios de estatus
- ✅ Un cambio de estatus puede tener múltiples evidencias

**Desventajas:**
- ❌ Más complejo
- ❌ Probablemente no necesitas que una evidencia se relacione con múltiples cambios de estatus

## 📊 Estructura Recomendada (Opción A)

### **1. Modificar tabla `finding_evidence`**

```sql
ALTER TABLE public.finding_evidence
ADD COLUMN IF NOT EXISTS related_status_change_id UUID REFERENCES public.finding_status_history(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_finding_evidence_status_change 
ON public.finding_evidence(related_status_change_id) 
WHERE related_status_change_id IS NOT NULL;

COMMENT ON COLUMN public.finding_evidence.related_status_change_id IS 
'ID del cambio de estatus relacionado (opcional). Si es NULL, la evidencia es independiente del cambio de estatus.';
```

### **2. Flujo de Trabajo**

#### **Escenario 1: Cambio de estatus sin evidencia**
```sql
-- 1. Cambiar estatus
INSERT INTO finding_status_history (finding_id, from_status, to_status, changed_by, comment)
VALUES ('finding-uuid', 'Open', 'In Progress', 'user-uuid', 'Empezando a trabajar');

-- 2. No se sube evidencia (related_status_change_id = NULL)
```

#### **Escenario 2: Cambio de estatus con evidencia**
```sql
-- 1. Cambiar estatus
INSERT INTO finding_status_history (finding_id, from_status, to_status, changed_by, comment)
VALUES ('finding-uuid', 'In Progress', 'Mitigated', 'user-uuid', 'Vulnerabilidad mitigada')
RETURNING id; -- status_change_id = 'status-change-uuid'

-- 2. Subir evidencia relacionada con ese cambio de estatus
INSERT INTO finding_evidence (finding_id, files, description, related_status_change_id, ...)
VALUES ('finding-uuid', '[...]', 'Evidencia de mitigación', 'status-change-uuid', ...);
```

#### **Escenario 3: Múltiples personas suben evidencias para el mismo cambio de estatus**
```sql
-- 1. Cambio de estatus a "Finalizado"
INSERT INTO finding_status_history (finding_id, from_status, to_status, changed_by)
VALUES ('finding-uuid', 'In Progress', 'Mitigated', 'admin-uuid')
RETURNING id; -- status_change_id = 'status-change-uuid'

-- 2. Usuario A (Admin) sube evidencia
INSERT INTO finding_evidence (finding_id, files, related_status_change_id, uploaded_by, ...)
VALUES ('finding-uuid', '[...]', 'status-change-uuid', 'admin-uuid', ...);

-- 3. Usuario B (Ingeniero de Redes) sube evidencia para el mismo cambio de estatus
INSERT INTO finding_evidence (finding_id, files, related_status_change_id, uploaded_by, ...)
VALUES ('finding-uuid', '[...]', 'status-change-uuid', 'engineer-uuid', ...);

-- 4. Usuario C (Tester) sube evidencia para el mismo cambio de estatus
INSERT INTO finding_evidence (finding_id, files, related_status_change_id, uploaded_by, ...)
VALUES ('finding-uuid', '[...]', 'status-change-uuid', 'tester-uuid', ...);
```

#### **Escenario 4: Evidencia independiente (sin cambio de estatus)**
```sql
-- Subir evidencia sin relacionarla con cambio de estatus
INSERT INTO finding_evidence (finding_id, files, related_status_change_id, ...)
VALUES ('finding-uuid', '[...]', NULL, ...); -- related_status_change_id = NULL
```

## 🔄 Funciones SQL Necesarias

### **1. Función para cambiar estatus y opcionalmente crear evidencia**

```sql
CREATE FUNCTION fn_update_finding_status_with_evidence(
    p_finding_id UUID,
    p_to_status finding_status,
    p_comment TEXT,
    p_evidence_files JSONB DEFAULT NULL,  -- Opcional
    p_evidence_description TEXT DEFAULT NULL,
    p_evidence_comments TEXT DEFAULT NULL
) RETURNS JSON;
```

### **2. Función para obtener historial con evidencias relacionadas**

```sql
CREATE FUNCTION fn_get_finding_status_history_with_evidence(
    p_finding_id UUID
) RETURNS JSON;
-- Retorna cambios de estatus con sus evidencias relacionadas
```

### **3. Función para listar evidencias de un finding (con información de cambio de estatus)**

Actualizar `fn_list_finding_evidence` para incluir información del cambio de estatus relacionado.

## 📝 Ejemplo de Respuesta

### **Historial de Estatus con Evidencias:**

```json
[
  {
    "id": "status-change-1",
    "finding_id": "finding-uuid",
    "from_status": "Open",
    "to_status": "In Progress",
    "comment": "Empezando a trabajar",
    "changed_by": "admin-uuid",
    "changed_by_name": "Admin",
    "created_at": "2026-01-07T10:00:00Z",
    "related_evidence": []  // Sin evidencias
  },
  {
    "id": "status-change-2",
    "finding_id": "finding-uuid",
    "from_status": "In Progress",
    "to_status": "Mitigated",
    "comment": "Vulnerabilidad mitigada",
    "changed_by": "admin-uuid",
    "changed_by_name": "Admin",
    "created_at": "2026-01-07T11:00:00Z",
    "related_evidence": [
      {
        "id": "evidence-1",
        "uploaded_by": "admin-uuid",
        "uploaded_by_name": "Admin",
        "files": [...],
        "description": "Parches aplicados"
      },
      {
        "id": "evidence-2",
        "uploaded_by": "engineer-uuid",
        "uploaded_by_name": "Ingeniero de Redes",
        "files": [...],
        "description": "Configuración actualizada"
      }
    ]
  }
]
```

## ✅ Recomendación Final

**Usar Opción A** con las siguientes mejoras:

1. **Campo `related_status_change_id` opcional** en `finding_evidence`
2. **Función para cambiar estatus** que opcionalmente puede crear evidencia
3. **Función para obtener historial** con evidencias relacionadas
4. **Actualizar función de listado de evidencias** para incluir información del cambio de estatus relacionado

Esto permite:
- ✅ Cambios de estatus sin evidencia
- ✅ Cambios de estatus con evidencia
- ✅ Múltiples evidencias para el mismo cambio de estatus
- ✅ Evidencias independientes
- ✅ Trazabilidad completa

