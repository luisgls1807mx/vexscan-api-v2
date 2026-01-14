# Guía Frontend: Tab "Historial" de Cambios de Estatus

## ✅ Funcionalidad Disponible

Sí, se puede implementar completamente. Ya existe toda la infraestructura necesaria.

---

## 📊 Estructura del Tab "Historial"

### **Título del Tab:**
```
Historial (N)
```
Donde `N` es el número total de cambios de estatus.

### **Contenido de cada cambio:**

1. **Estatus anterior → Estatus nuevo**
2. **Usuario que hizo el cambio** (nombre y email)
3. **Fecha y hora relativa** (ej: "hace 2 horas", "hace 3 días")
4. **Comentario del cambio**
5. **Evidencias relacionadas** (si las hay)
   - Lista de evidencias con archivos
   - Botón para ver/descargar cada archivo

---

## 🔌 Endpoint Disponible

### **Obtener Historial con Evidencias (Paginado)**

```typescript
GET /api/v1/findings/{finding_id}/status-history?page=1&per_page=20

// Parámetros de query:
// - page: Número de página (default: 1)
// - per_page: Elementos por página (default: 20, máximo: 100)
```

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": "status-change-uuid-1",
            "finding_id": "finding-uuid",
            "from_status": "Open",
            "to_status": "In Progress",
            "comment": "Empezando a trabajar en la vulnerabilidad",
            "metadata": {},
            "changed_by": "user-uuid",
            "changed_by_name": "Admin Usuario",
            "changed_by_email": "admin@example.com",
            "created_at": "2026-01-07T10:00:00Z",
            "related_evidence": [],  // Sin evidencias
            "evidence_count": 0
        },
        {
            "id": "status-change-uuid-2",
            "from_status": "In Progress",
            "to_status": "Mitigated",
            "comment": "Vulnerabilidad mitigada completamente",
            "metadata": {},
            "changed_by": "user-uuid",
            "changed_by_name": "Admin Usuario",
            "changed_by_email": "admin@example.com",
            "created_at": "2026-01-07T11:00:00Z",
            "related_evidence": [
                {
                    "id": "evidence-uuid-1",
                    "files": [
                        {
                            "file_name": "parches.pdf",
                            "file_path": "workspace/finding/parches.pdf",
                            "file_size": 1024000,
                            "file_type": "application/pdf",
                            "file_hash": "sha256-hash-1"
                        },
                        {
                            "file_name": "config.jpg",
                            "file_path": "workspace/finding/config.jpg",
                            "file_size": 2048000,
                            "file_type": "image/jpeg",
                            "file_hash": "sha256-hash-2"
                        }
                    ],
                    "file_count": 2,
                    "description": "Parches aplicados",
                    "comments": "Se aplicaron los parches según el plan",
                    "evidence_type": "mitigation",
                    "uploaded_by": "admin-uuid",
                    "uploaded_by_name": "Admin Usuario",
                    "uploaded_by_email": "admin@example.com",
                    "created_at": "2026-01-07T11:05:00Z"
                },
                {
                    "id": "evidence-uuid-2",
                    "files": [
                        {
                            "file_name": "test-results.pdf",
                            "file_path": "workspace/finding/test-results.pdf",
                            "file_size": 512000,
                            "file_type": "application/pdf",
                            "file_hash": "sha256-hash-3"
                        }
                    ],
                    "file_count": 1,
                    "description": "Pruebas de penetración",
                    "uploaded_by": "tester-uuid",
                    "uploaded_by_name": "Tester",
                    "uploaded_by_email": "tester@example.com",
                    "created_at": "2026-01-07T11:10:00Z"
                }
            ],
            "evidence_count": 2
        }
    ],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 15,
        "total_pages": 1
    }
}
```

---

## 🎨 Ejemplo de Implementación Frontend

### **Componente React/Vue/Angular**

```typescript
interface StatusHistoryItem {
    id: string;
    from_status: string;
    to_status: string;
    comment: string | null;
    changed_by_name: string;
    changed_by_email: string;
    created_at: string;
    related_evidence: Evidence[];
    evidence_count: number;
}

interface Evidence {
    id: string;
    files: Array<{
        file_name: string;
        file_path: string;
        file_size: number;
        file_type: string;
        file_hash: string;
    }>;
    file_count: number;
    description: string | null;
    comments: string | null;
    evidence_type: string;
    uploaded_by_name: string;
    uploaded_by_email: string;
    created_at: string;
}

const StatusHistoryTab = ({ findingId }: { findingId: string }) => {
    const [history, setHistory] = useState<StatusHistoryItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchStatusHistory(findingId);
    }, [findingId]);

    const [pagination, setPagination] = useState({
        page: 1,
        per_page: 20,
        total: 0,
        total_pages: 0
    });

    const fetchStatusHistory = async (
        findingId: string,
        page: number = 1,
        perPage: number = 20
    ) => {
        setLoading(true);
        try {
            const response = await fetch(
                `/api/v1/findings/${findingId}/status-history?page=${page}&per_page=${perPage}`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );
            
            const result = await response.json();
            
            if (result.success) {
                setHistory(result.data);
                setPagination(result.pagination);
            }
        } catch (error) {
            console.error('Error fetching status history:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatRelativeTime = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Hace unos momentos';
        if (diffMins < 60) return `Hace ${diffMins} minuto(s)`;
        if (diffHours < 24) return `Hace ${diffHours} hora(s)`;
        if (diffDays < 30) return `Hace ${diffDays} día(s)`;
        return date.toLocaleDateString();
    };

    const downloadEvidenceFile = async (
        evidenceId: string,
        fileHash: string
    ) => {
        const url = `/api/v1/evidence/${evidenceId}/attachments/${fileHash}/download`;
        window.open(url, '_blank');
    };

    if (loading) return <div>Cargando historial...</div>;

    return (
        <div className="status-history-tab">
            <h3>Historial ({pagination.total})</h3>
            
            {/* Controles de paginación */}
            {pagination.total_pages > 1 && (
                <div className="pagination-controls">
                    <button
                        onClick={() => fetchStatusHistory(findingId, pagination.page - 1)}
                        disabled={pagination.page === 1}
                    >
                        Anterior
                    </button>
                    <span>
                        Página {pagination.page} de {pagination.total_pages}
                    </span>
                    <button
                        onClick={() => fetchStatusHistory(findingId, pagination.page + 1)}
                        disabled={pagination.page >= pagination.total_pages}
                    >
                        Siguiente
                    </button>
                </div>
            )}
            
            {history.map((item) => (
                <div key={item.id} className="status-change-item">
                    {/* Estatus anterior → Estatus nuevo */}
                    <div className="status-change-header">
                        <span className="status-badge from-status">
                            {item.from_status || 'N/A'}
                        </span>
                        <span className="arrow">→</span>
                        <span className="status-badge to-status">
                            {item.to_status}
                        </span>
                    </div>

                    {/* Usuario y fecha */}
                    <div className="status-change-meta">
                        <span className="user-name">
                            {item.changed_by_name}
                        </span>
                        <span className="timestamp">
                            {formatRelativeTime(item.created_at)}
                        </span>
                    </div>

                    {/* Comentario */}
                    {item.comment && (
                        <div className="status-change-comment">
                            {item.comment}
                        </div>
                    )}

                    {/* Evidencias relacionadas */}
                    {item.evidence_count > 0 && (
                        <div className="related-evidence">
                            <h4>Evidencias relacionadas ({item.evidence_count})</h4>
                            
                            {item.related_evidence.map((evidence) => (
                                <div key={evidence.id} className="evidence-item">
                                    <div className="evidence-header">
                                        <span className="evidence-uploader">
                                            {evidence.uploaded_by_name}
                                        </span>
                                        <span className="evidence-date">
                                            {formatRelativeTime(evidence.created_at)}
                                        </span>
                                    </div>
                                    
                                    {evidence.description && (
                                        <div className="evidence-description">
                                            {evidence.description}
                                        </div>
                                    )}
                                    
                                    {evidence.comments && (
                                        <div className="evidence-comments">
                                            {evidence.comments}
                                        </div>
                                    )}

                                    {/* Lista de archivos */}
                                    <div className="evidence-files">
                                        {evidence.files.map((file) => (
                                            <div key={file.file_hash} className="file-item">
                                                <span className="file-name">
                                                    {file.file_name}
                                                </span>
                                                <span className="file-size">
                                                    {(file.file_size / 1024).toFixed(2)} KB
                                                </span>
                                                <button
                                                    onClick={() => downloadEvidenceFile(
                                                        evidence.id,
                                                        file.file_hash
                                                    )}
                                                    className="download-btn"
                                                >
                                                    Descargar
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Separador */}
                    <hr />
                </div>
            ))}

            {history.length === 0 && !loading && (
                <div className="empty-state">
                    No hay cambios de estatus registrados
                </div>
            )}
            
            {/* Paginación inferior */}
            {pagination.total_pages > 1 && (
                <div className="pagination-controls-bottom">
                    <button
                        onClick={() => fetchStatusHistory(findingId, pagination.page - 1)}
                        disabled={pagination.page === 1}
                    >
                        ← Anterior
                    </button>
                    <span>
                        Mostrando {((pagination.page - 1) * pagination.per_page) + 1} - {
                            Math.min(pagination.page * pagination.per_page, pagination.total)
                        } de {pagination.total}
                    </span>
                    <button
                        onClick={() => fetchStatusHistory(findingId, pagination.page + 1)}
                        disabled={pagination.page >= pagination.total_pages}
                    >
                        Siguiente →
                    </button>
                </div>
            )}
        </div>
    );
};
```

---

## 📝 Estructura de Datos para el Frontend

### **Cada Item del Historial:**

```typescript
{
    id: string;                    // ID del cambio de estatus
    from_status: string | null;    // Estatus anterior (null si es el primero)
    to_status: string;             // Estatus nuevo
    comment: string | null;         // Comentario del cambio
    changed_by_name: string;       // Nombre del usuario
    changed_by_email: string;      // Email del usuario
    created_at: string;            // ISO timestamp
    related_evidence: Evidence[];  // Array de evidencias relacionadas
    evidence_count: number;        // Cantidad de evidencias
}
```

### **Cada Evidencia:**

```typescript
{
    id: string;
    files: Array<{
        file_name: string;
        file_path: string;
        file_size: number;
        file_type: string;
        file_hash: string;  // ← Usar para descargar
    }>;
    file_count: number;
    description: string | null;
    comments: string | null;
    evidence_type: string;
    uploaded_by_name: string;
    uploaded_by_email: string;
    created_at: string;
}
```

---

## 🔗 Endpoints Necesarios

### **1. Obtener Historial**

```typescript
GET /api/v1/findings/{finding_id}/status-history
```

**✅ Endpoint ya creado** - Retorna historial completo con evidencias relacionadas.

### **2. Descargar Archivo de Evidencia**

```typescript
GET /api/v1/evidence/{evidence_id}/attachments/{file_hash}/download
```

Ya existe este endpoint.

---

## 🎨 Diseño UI Recomendado

### **Layout del Tab:**

```
┌─────────────────────────────────────────┐
│ Historial (3)                            │
├─────────────────────────────────────────┤
│                                         │
│ [Open] → [In Progress]                  │
│ Admin Usuario • hace 2 horas            │
│ "Empezando a trabajar..."               │
│ ─────────────────────────────────────  │
│                                         │
│ [In Progress] → [Mitigated]             │
│ Admin Usuario • hace 1 hora             │
│ "Vulnerabilidad mitigada"               │
│                                         │
│ 📎 Evidencias relacionadas (2)         │
│   ┌─────────────────────────────────┐  │
│   │ Admin Usuario • hace 55 min      │  │
│   │ "Parches aplicados"              │  │
│   │ • parches.pdf (1.0 MB) [↓]       │  │
│   │ • config.jpg (2.0 MB) [↓]        │  │
│   └─────────────────────────────────┘  │
│   ┌─────────────────────────────────┐  │
│   │ Tester • hace 50 min             │  │
│   │ "Pruebas completadas"            │  │
│   │ • test-results.pdf (512 KB) [↓]  │  │
│   └─────────────────────────────────┘  │
│ ─────────────────────────────────────  │
│                                         │
└─────────────────────────────────────────┘
```

---

## ✅ Checklist de Implementación

- [x] Crear endpoint `GET /api/v1/findings/{finding_id}/status-history` ✅ **Ya creado**
- [x] Paginación implementada ✅ **Ya implementada**
- [ ] Componente de Tab "Historial"
- [ ] Mostrar contador `(N)` en el título del tab (usar `pagination.total`)
- [ ] Implementar controles de paginación
- [ ] Renderizar cada cambio de estatus con:
  - [ ] Estatus anterior → Estatus nuevo
  - [ ] Usuario que hizo el cambio
  - [ ] Fecha y hora relativa
  - [ ] Comentario del cambio
- [ ] Mostrar evidencias relacionadas (si las hay)
- [ ] Botón para descargar cada archivo de evidencia
- [ ] Manejar caso cuando no hay historial
- [ ] Manejar caso cuando no hay evidencias relacionadas
- [ ] Formato de fecha relativa (ej: "hace 2 horas")

---

## 💡 Funciones Auxiliares Útiles

### **Formatear Fecha Relativa:**

```typescript
const formatRelativeTime = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    const diffWeeks = Math.floor(diffDays / 7);
    const diffMonths = Math.floor(diffDays / 30);

    if (diffMins < 1) return 'Hace unos momentos';
    if (diffMins < 60) return `Hace ${diffMins} minuto${diffMins > 1 ? 's' : ''}`;
    if (diffHours < 24) return `Hace ${diffHours} hora${diffHours > 1 ? 's' : ''}`;
    if (diffDays < 7) return `Hace ${diffDays} día${diffDays > 1 ? 's' : ''}`;
    if (diffWeeks < 4) return `Hace ${diffWeeks} semana${diffWeeks > 1 ? 's' : ''}`;
    if (diffMonths < 12) return `Hace ${diffMonths} mes${diffMonths > 1 ? 'es' : ''}`;
    
    return date.toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};
```

### **Formatear Tamaño de Archivo:**

```typescript
const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
};
```

---

## 🚀 Resumen

**Sí, se puede implementar completamente.** Ya tienes:

1. ✅ Función SQL: `fn_get_finding_status_history_with_evidence`
2. ✅ Endpoint de descarga: `GET /api/v1/evidence/{evidence_id}/attachments/{file_hash}/download`
3. ✅ Estructura de datos completa con todas las evidencias relacionadas

**Solo necesitas:**
- Crear el endpoint en el backend (si no existe)
- Implementar el componente del tab en el frontend
- Usar los datos retornados para renderizar el historial

¿Quieres que cree el endpoint en el backend también?

