# Ejemplo de Paginación en Historial

## 📊 Estructura de Respuesta Paginada

```json
{
    "success": true,
    "data": [
        // Array de cambios de estatus (máximo per_page elementos)
    ],
    "pagination": {
        "page": 1,           // Página actual
        "per_page": 20,      // Elementos por página
        "total": 45,         // Total de cambios de estatus
        "total_pages": 3     // Total de páginas
    }
}
```

## 🔢 Cálculo del Contador en el Tab

```typescript
// El título del tab debe mostrar el TOTAL, no solo los de la página actual
<Tab title={`Historial (${pagination.total})`}>
```

**Ejemplo:**
- Si hay 45 cambios de estatus totales
- Y estás en la página 1 mostrando 20
- El tab debe mostrar: **"Historial (45)"** (no "Historial (20)")

## 📝 Ejemplo Completo con Paginación

```typescript
const StatusHistoryTab = ({ findingId }: { findingId: string }) => {
    const [history, setHistory] = useState<StatusHistoryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [pagination, setPagination] = useState({
        page: 1,
        per_page: 20,
        total: 0,
        total_pages: 0
    });

    useEffect(() => {
        fetchStatusHistory(findingId, 1, 20);
    }, [findingId]);

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
                setHistory(result.data || []);
                setPagination(result.pagination || {
                    page: 1,
                    per_page: 20,
                    total: 0,
                    total_pages: 0
                });
            }
        } catch (error) {
            console.error('Error fetching status history:', error);
        } finally {
            setLoading(false);
        }
    };

    const handlePageChange = (newPage: number) => {
        fetchStatusHistory(findingId, newPage, pagination.per_page);
        // Opcional: scroll al inicio del tab
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    return (
        <div className="status-history-tab">
            {/* Título con contador TOTAL */}
            <h3>Historial ({pagination.total})</h3>
            
            {loading && <div>Cargando...</div>}
            
            {/* Controles de paginación superior */}
            {pagination.total_pages > 1 && (
                <div className="pagination-controls">
                    <button
                        onClick={() => handlePageChange(pagination.page - 1)}
                        disabled={pagination.page === 1}
                    >
                        ← Anterior
                    </button>
                    <span>
                        Página {pagination.page} de {pagination.total_pages}
                    </span>
                    <button
                        onClick={() => handlePageChange(pagination.page + 1)}
                        disabled={pagination.page >= pagination.total_pages}
                    >
                        Siguiente →
                    </button>
                </div>
            )}
            
            {/* Lista de cambios de estatus */}
            {history.map((item) => (
                <StatusChangeItem key={item.id} item={item} />
            ))}
            
            {/* Controles de paginación inferior */}
            {pagination.total_pages > 1 && (
                <div className="pagination-controls-bottom">
                    <button
                        onClick={() => handlePageChange(pagination.page - 1)}
                        disabled={pagination.page === 1}
                    >
                        ← Anterior
                    </button>
                    <span>
                        Mostrando {((pagination.page - 1) * pagination.per_page) + 1} - {
                            Math.min(pagination.page * pagination.per_page, pagination.total)
                        } de {pagination.total} cambios
                    </span>
                    <button
                        onClick={() => handlePageChange(pagination.page + 1)}
                        disabled={pagination.page >= pagination.total_pages}
                    >
                        Siguiente →
                    </button>
                </div>
            )}
            
            {history.length === 0 && !loading && (
                <div className="empty-state">
                    No hay cambios de estatus registrados
                </div>
            )}
        </div>
    );
};
```

## 🎨 Opciones de Paginación

### **Opción 1: Botones Anterior/Siguiente (Simple)**
```typescript
<button onClick={() => handlePageChange(page - 1)} disabled={page === 1}>
    Anterior
</button>
<button onClick={() => handlePageChange(page + 1)} disabled={page >= total_pages}>
    Siguiente
</button>
```

### **Opción 2: Selector de Página**
```typescript
<select 
    value={pagination.page} 
    onChange={(e) => handlePageChange(Number(e.target.value))}
>
    {Array.from({ length: pagination.total_pages }, (_, i) => i + 1).map(pageNum => (
        <option key={pageNum} value={pageNum}>
            Página {pageNum}
        </option>
    ))}
</select>
```

### **Opción 3: Números de Página (Avanzado)**
```typescript
const renderPageNumbers = () => {
    const pages = [];
    const maxVisible = 5;
    let startPage = Math.max(1, pagination.page - Math.floor(maxVisible / 2));
    let endPage = Math.min(pagination.total_pages, startPage + maxVisible - 1);
    
    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        pages.push(
            <button
                key={i}
                onClick={() => handlePageChange(i)}
                className={i === pagination.page ? 'active' : ''}
            >
                {i}
            </button>
        );
    }
    
    return pages;
};
```

## 📱 Ejemplo de UI con Paginación

```
┌─────────────────────────────────────────┐
│ Historial (45)                          │
├─────────────────────────────────────────┤
│ [← Anterior]  Página 1 de 3  [Siguiente →] │
├─────────────────────────────────────────┤
│                                         │
│ [Open] → [In Progress]                  │
│ Admin • hace 2 horas                    │
│ ─────────────────────────────────────  │
│                                         │
│ [In Progress] → [Mitigated]            │
│ Admin • hace 1 hora                     │
│ 📎 Evidencias (2)                       │
│ ─────────────────────────────────────  │
│                                         │
│ ... (más cambios) ...                   │
│                                         │
├─────────────────────────────────────────┤
│ [← Anterior]  Mostrando 1-20 de 45  [Siguiente →] │
└─────────────────────────────────────────┘
```

## ⚙️ Configuración Recomendada

### **Valores por Defecto:**
- `per_page: 20` - Buen balance entre carga y cantidad de información
- `per_page: 10` - Si quieres menos scroll
- `per_page: 50` - Si quieres más información por página

### **Límites:**
- Máximo `per_page: 100` (configurado en el backend)
- Mínimo `per_page: 1`

## 💡 Mejoras Opcionales

### **1. Carga Infinita (Infinite Scroll)**
```typescript
const [hasMore, setHasMore] = useState(true);

useEffect(() => {
    const handleScroll = () => {
        if (
            window.innerHeight + window.scrollY >= document.body.offsetHeight - 1000
            && hasMore
            && !loading
        ) {
            loadMore();
        }
    };
    
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
}, [hasMore, loading]);

const loadMore = () => {
    if (pagination.page < pagination.total_pages) {
        fetchStatusHistory(findingId, pagination.page + 1, pagination.per_page);
    }
};
```

### **2. Selector de Elementos por Página**
```typescript
<select 
    value={pagination.per_page} 
    onChange={(e) => fetchStatusHistory(findingId, 1, Number(e.target.value))}
>
    <option value={10}>10 por página</option>
    <option value={20}>20 por página</option>
    <option value={50}>50 por página</option>
    <option value={100}>100 por página</option>
</select>
```

---

## ✅ Resumen

- ✅ Paginación implementada en la función SQL
- ✅ Endpoint acepta parámetros `page` y `per_page`
- ✅ Respuesta incluye información de paginación
- ✅ Contador del tab muestra el TOTAL (no solo la página actual)
- ✅ Listo para manejar grandes volúmenes de cambios de estatus

