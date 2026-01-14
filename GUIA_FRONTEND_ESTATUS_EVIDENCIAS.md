# Guía Frontend: Gestión de Estatus y Evidencias

## 📋 Resumen de Funcionalidad

El sistema ahora permite:
1. ✅ Cambiar el estatus de una vulnerabilidad (crea registro automáticamente)
2. ✅ Subir evidencias relacionadas con un cambio de estatus específico
3. ✅ Múltiples personas pueden subir evidencias para el mismo cambio de estatus
4. ✅ Subir evidencias independientes (sin relacionar con cambio de estatus)
5. ✅ Ver historial completo con evidencias agrupadas por cambio de estatus

---

## 🔄 Flujos Principales

### **Flujo 1: Cambio de Estatus SIN Evidencia**

**Paso 1: Cambiar estatus**
```typescript
// Endpoint
PUT /api/v1/findings/{finding_id}/status

// Request Body
{
    "status": "In Progress",
    "comment": "Empezando a trabajar en la vulnerabilidad"
}

// Response
{
    "success": true,
    "message": "Status updated to 'In Progress'",
    "data": {
        "finding_id": "uuid-finding",
        "from_status": "Open",
        "to_status": "In Progress",
        "status_change_id": "uuid-status-change",  // ← GUARDAR ESTE ID
        "comment": "Empezando a trabajar...",
        "changed_by": "uuid-user",
        "changed_at": "2026-01-07T10:00:00Z"
    }
}
```

**Nota:** No se requiere evidencia para este cambio. El `status_change_id` se retorna pero no es necesario usarlo a menos que después se quiera subir evidencia relacionada.

---

### **Flujo 2: Cambio de Estatus CON Evidencia (Una Persona)**

**Paso 1: Cambiar estatus**
```typescript
PUT /api/v1/findings/{finding_id}/status
{
    "status": "Mitigated",
    "comment": "Vulnerabilidad mitigada completamente"
}

// Response
{
    "data": {
        "status_change_id": "uuid-status-change-123"  // ← GUARDAR ESTE ID
    }
}
```

**Paso 2: Subir evidencia relacionada**
```typescript
// Endpoint
POST /api/v1/evidence/findings/{finding_id}/upload

// Form Data (multipart/form-data)
const formData = new FormData();
formData.append('files', file1);
formData.append('files', file2);
formData.append('description', 'Parches aplicados y configuración actualizada');
formData.append('comments', 'Se aplicaron los parches de seguridad según el plan');
formData.append('evidence_type', 'mitigation');
formData.append('related_status_change_id', 'uuid-status-change-123');  // ← USAR EL ID DEL PASO 1

// Response
{
    "success": true,
    "message": "2 archivo(s) subido(s) exitosamente en un solo registro",
    "data": {
        "id": "uuid-evidence",
        "finding_id": "uuid-finding",
        "file_count": 2,
        "files": [
            {
                "file_name": "parches.pdf",
                "file_path": "...",
                "file_size": 1024000,
                "file_type": "application/pdf",
                "file_hash": "sha256..."
            },
            {
                "file_name": "config.jpg",
                "file_path": "...",
                "file_size": 2048000,
                "file_type": "image/jpeg",
                "file_hash": "sha256..."
            }
        ],
        "description": "Parches aplicados...",
        "comments": "Se aplicaron los parches...",
        "evidence_type": "mitigation",
        "related_status_change_id": "uuid-status-change-123",  // ← Relacionado
        "uploaded_by": "uuid-user",
        "created_at": "2026-01-07T10:05:00Z"
    }
}
```

---

### **Flujo 3: Múltiples Personas Suben Evidencias para el Mismo Cambio**

**Escenario:** Admin cambia estatus a "Mitigated", luego Admin, Ingeniero de Redes y Tester suben sus evidencias.

**Paso 1: Admin cambia estatus**
```typescript
PUT /api/v1/findings/{finding_id}/status
{
    "status": "Mitigated",
    "comment": "Vulnerabilidad mitigada"
}

// Response
{
    "data": {
        "status_change_id": "uuid-status-change-123"  // ← COMPARTIR ESTE ID
    }
}
```

**Paso 2: Admin sube evidencia**
```typescript
POST /api/v1/evidence/findings/{finding_id}/upload
Form Data:
- files: [parches.pdf]
- description: "Parches aplicados"
- related_status_change_id: "uuid-status-change-123"  // ← Mismo ID
```

**Paso 3: Ingeniero de Redes sube evidencia**
```typescript
POST /api/v1/evidence/findings/{finding_id}/upload
Form Data:
- files: [config.jpg, network-diagram.png]
- description: "Configuración de red actualizada"
- related_status_change_id: "uuid-status-change-123"  // ← Mismo ID
```

**Paso 4: Tester sube evidencia**
```typescript
POST /api/v1/evidence/findings/{finding_id}/upload
Form Data:
- files: [test-results.pdf]
- description: "Pruebas de penetración completadas"
- related_status_change_id: "uuid-status-change-123"  // ← Mismo ID
```

**Resultado:** Las 3 evidencias quedan relacionadas con el mismo cambio de estatus.

---

### **Flujo 4: Evidencia Independiente (Sin Cambio de Estatus)**

```typescript
POST /api/v1/evidence/findings/{finding_id}/upload
Form Data:
- files: [screenshot.png]
- description: "Evidencia adicional"
- comments: "Información complementaria"
// NO se envía related_status_change_id (será NULL)

// Response
{
    "data": {
        "related_status_change_id": null  // ← Sin relación
    }
}
```

---

## 📊 Endpoints Disponibles

### **1. Cambiar Estatus de Finding**

```typescript
PUT /api/v1/findings/{finding_id}/status

Request Body:
{
    status: "Open" | "In Progress" | "Waiting" | "Mitigated" | "Accepted Risk" | "False Positive" | "Not Observed",
    comment: string  // Mínimo 10 caracteres para estatus cerrados
}

Response:
{
    success: boolean,
    message: string,
    data: {
        finding_id: string,
        from_status: string,
        to_status: string,
        status_change_id: string,  // ← IMPORTANTE: Guardar para relacionar evidencias
        comment: string,
        changed_by: string,
        changed_at: string
    }
}
```

**Validaciones:**
- `Mitigated`, `Accepted Risk`, `False Positive`, `Not Observed` → Requieren comentario (mínimo 10 caracteres)
- `Mitigated` → Requiere que exista al menos una evidencia activa para el finding

---

### **2. Subir Evidencias**

```typescript
POST /api/v1/evidence/findings/{finding_id}/upload

Form Data (multipart/form-data):
- files: File[]  // Array de archivos (máximo 20)
- description?: string  // Opcional
- comments?: string  // Opcional
- evidence_type?: string  // Opcional: "mitigation" | "verification" | "initial" | "remediation" | "testing" | "other" (default: "other")
- related_status_change_id?: string  // Opcional: ID del cambio de estatus relacionado

Response:
{
    success: boolean,
    message: string,
    data: {
        id: string,
        finding_id: string,
        files: Array<{
            file_name: string,
            file_path: string,
            file_size: number,
            file_type: string,
            file_hash: string
        }>,
        file_count: number,
        description: string | null,
        comments: string | null,
        evidence_type: string,
        related_status_change_id: string | null,  // ← NULL si no está relacionado
        uploaded_by: string,
        uploaded_by_name: string,
        uploaded_by_email: string,
        created_at: string
    }
}
```

**Límites:**
- Máximo 20 archivos por solicitud
- Máximo 50MB por archivo
- Formatos permitidos: imágenes, PDFs, documentos, etc.

---

### **3. Listar Evidencias de un Finding**

```typescript
GET /api/v1/evidence/findings/{finding_id}

Response:
{
    success: boolean,
    data: [
        {
            id: string,
            finding_id: string,
            files: Array<{...}>,
            file_count: number,
            description: string | null,
            comments: string | null,
            evidence_type: string,
            related_status_change_id: string | null,
            related_status_change: {  // ← Información del cambio de estatus (si existe)
                id: string,
                from_status: string,
                to_status: string,
                comment: string,
                changed_by: string,
                changed_by_name: string,
                created_at: string
            } | null,
            uploaded_by: string,
            uploaded_by_name: string,
            uploaded_by_email: string,
            created_at: string,
            updated_at: string
        },
        ...
    ]
}
```

---

### **4. Obtener Historial de Cambios de Estatus con Evidencias**

```typescript
GET /api/v1/findings/{finding_id}/status-history  // ← Endpoint a crear o usar fn_get_finding_status_history_with_evidence

Response:
{
    success: boolean,
    data: [
        {
            id: string,  // status_change_id
            finding_id: string,
            from_status: string,
            to_status: string,
            comment: string | null,
            metadata: object,
            changed_by: string,
            changed_by_name: string,
            changed_by_email: string,
            created_at: string,
            related_evidence: [  // ← Evidencias relacionadas con este cambio
                {
                    id: string,
                    files: Array<{...}>,
                    file_count: number,
                    description: string | null,
                    comments: string | null,
                    evidence_type: string,
                    uploaded_by: string,
                    uploaded_by_name: string,
                    uploaded_by_email: string,
                    created_at: string
                },
                ...
            ],
            evidence_count: number  // ← Cantidad de evidencias relacionadas
        },
        ...
    ]
}
```

---

### **5. Descargar Archivo de Evidencia**

```typescript
GET /api/v1/evidence/{evidence_id}/attachments/{file_hash}/download

// file_hash es el hash del archivo dentro del array files
// Se obtiene de: evidence.files[0].file_hash

Response: File (StreamingResponse)
```

---

### **6. Eliminar Evidencia**

```typescript
DELETE /api/v1/evidence/findings/{finding_id}/{evidence_id}

Response:
{
    success: boolean,
    message: string,
    data: {
        id: string,
        deleted: boolean,
        files_count: number,
        files: Array<{...}>  // Archivos eliminados
    }
}
```

---

## 🎨 Ejemplos de Implementación Frontend

### **Ejemplo 1: Modal de Cambio de Estatus**

```typescript
// Componente React/Vue/Angular
const handleStatusChange = async (findingId: string, newStatus: string, comment: string) => {
    try {
        const response = await fetch(`/api/v1/findings/${findingId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                status: newStatus,
                comment: comment
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Guardar status_change_id para usar después si se sube evidencia
            const statusChangeId = result.data.status_change_id;
            
            // Mostrar mensaje de éxito
            showNotification('Estatus actualizado exitosamente');
            
            // Si el usuario quiere subir evidencia relacionada, mostrar modal de upload
            // y pasar statusChangeId
            if (shouldUploadEvidence(newStatus)) {
                openEvidenceUploadModal(findingId, statusChangeId);
            }
        }
    } catch (error) {
        showError('Error al cambiar estatus');
    }
};
```

---

### **Ejemplo 2: Modal de Subida de Evidencias**

```typescript
const handleEvidenceUpload = async (
    findingId: string,
    files: File[],
    description: string,
    comments: string,
    relatedStatusChangeId?: string  // ← Opcional
) => {
    const formData = new FormData();
    
    // Agregar archivos
    files.forEach(file => {
        formData.append('files', file);
    });
    
    // Agregar campos opcionales
    if (description) formData.append('description', description);
    if (comments) formData.append('comments', comments);
    if (relatedStatusChangeId) {
        formData.append('related_status_change_id', relatedStatusChangeId);  // ← Relacionar con cambio de estatus
    }
    
    try {
        const response = await fetch(`/api/v1/evidence/findings/${findingId}/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
                // NO incluir Content-Type, el navegador lo hace automáticamente para FormData
            },
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification(`${files.length} archivo(s) subido(s) exitosamente`);
            refreshEvidenceList(findingId);
        }
    } catch (error) {
        showError('Error al subir evidencias');
    }
};
```

---

### **Ejemplo 3: Mostrar Historial con Evidencias**

```typescript
const fetchStatusHistory = async (findingId: string) => {
    try {
        const response = await fetch(`/api/v1/findings/${findingId}/status-history`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const result = await response.json();
        
        // Renderizar historial
        result.data.forEach((statusChange: any) => {
            console.log(`Cambio de ${statusChange.from_status} a ${statusChange.to_status}`);
            console.log(`Comentario: ${statusChange.comment}`);
            console.log(`Evidencias relacionadas: ${statusChange.evidence_count}`);
            
            // Mostrar evidencias relacionadas
            statusChange.related_evidence.forEach((evidence: any) => {
                console.log(`- ${evidence.uploaded_by_name} subió ${evidence.file_count} archivo(s)`);
            });
        });
    } catch (error) {
        showError('Error al obtener historial');
    }
};
```

---

## 🔑 Puntos Clave para el Frontend

### **1. Guardar `status_change_id` después de cambiar estatus**

```typescript
// Después de cambiar estatus, guardar el ID
const statusChangeId = response.data.status_change_id;

// Usar este ID al subir evidencias relacionadas
formData.append('related_status_change_id', statusChangeId);
```

### **2. `related_status_change_id` es OPCIONAL**

- Si se envía → La evidencia se relaciona con ese cambio de estatus
- Si NO se envía (o es null) → La evidencia es independiente

### **3. Múltiples personas pueden usar el mismo `status_change_id`**

- Todas las evidencias con el mismo `related_status_change_id` quedan agrupadas
- Útil cuando múltiples personas trabajan en la misma mitigación

### **4. Validaciones del Backend**

- `Mitigated` requiere evidencia (al menos una activa)
- Estatus cerrados requieren comentario (mínimo 10 caracteres)

### **5. Tipos de Evidencia (`evidence_type`)**

Valores permitidos:
- `"mitigation"` - Evidencia de mitigación
- `"verification"` - Evidencia de verificación
- `"initial"` - Evidencia inicial
- `"remediation"` - Evidencia de remediación
- `"testing"` - Evidencia de pruebas
- `"other"` - Otro tipo (default)

---

## 📱 Flujo de UI Recomendado

### **Escenario: Usuario cambia estatus y quiere subir evidencia**

1. **Usuario hace clic en "Cambiar Estatus"**
   - Se abre modal con formulario de cambio de estatus
   - Campos: Nuevo estatus, Comentario

2. **Usuario envía cambio de estatus**
   - Backend retorna `status_change_id`
   - Mostrar mensaje de éxito

3. **Si el estatus requiere evidencia o usuario quiere subirla:**
   - Mostrar opción: "¿Deseas subir evidencia relacionada?"
   - Si acepta → Abrir modal de subida de evidencias
   - Pre-llenar `related_status_change_id` con el ID recibido

4. **Usuario sube archivos**
   - Múltiples archivos permitidos
   - Campos opcionales: description, comments, evidence_type
   - El `related_status_change_id` ya está pre-llenado

5. **Mostrar confirmación**
   - "Evidencia relacionada con el cambio de estatus exitosamente"

---

## 🎯 Casos de Uso Comunes

### **Caso 1: Cambio simple sin evidencia**
```
Usuario → Cambia estatus "Open" → "In Progress"
         → No sube evidencia
         → Listo
```

### **Caso 2: Cambio con evidencia inmediata**
```
Usuario → Cambia estatus "In Progress" → "Mitigated"
         → Sube evidencia relacionada (mismo flujo)
         → Listo
```

### **Caso 3: Cambio primero, evidencia después**
```
Usuario A → Cambia estatus "In Progress" → "Mitigated"
           → Guarda status_change_id
           → Más tarde sube evidencia con ese ID
```

### **Caso 4: Múltiples personas**
```
Usuario A → Cambia estatus → "Mitigated"
           → Comparte status_change_id con equipo

Usuario B → Sube evidencia con status_change_id
Usuario C → Sube evidencia con status_change_id
Usuario D → Sube evidencia con status_change_id

Resultado: 3 evidencias relacionadas con el mismo cambio
```

---

## ⚠️ Errores Comunes a Evitar

1. **No guardar `status_change_id`** → No se puede relacionar evidencia después
2. **Enviar `related_status_change_id` incorrecto** → Backend valida que pertenezca al finding
3. **Olvidar validar comentario** → Backend rechaza si es muy corto
4. **No verificar si `Mitigated` requiere evidencia** → Backend valida esto

---

## 📝 Checklist de Implementación

- [ ] Endpoint de cambio de estatus implementado
- [ ] Guardar `status_change_id` después de cambiar estatus
- [ ] Modal de subida de evidencias acepta `related_status_change_id`
- [ ] Validar comentario antes de enviar (mínimo 10 caracteres)
- [ ] Mostrar advertencia si `Mitigated` no tiene evidencia
- [ ] Listar evidencias con información de cambio de estatus relacionado
- [ ] Mostrar historial con evidencias agrupadas
- [ ] Permitir subir evidencias independientes (sin `related_status_change_id`)
- [ ] Manejar errores de validación del backend

---

¿Necesitas más detalles sobre algún endpoint o flujo específico?

