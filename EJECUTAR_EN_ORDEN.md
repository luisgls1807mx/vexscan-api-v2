# Orden de Ejecución de Archivos SQL para Evidencias

## ⚠️ IMPORTANTE: Ejecutar en este orden exacto

### **Paso 1: Agregar columna `evidence_type` a la tabla**

```sql
-- Si la tabla ya existe, agregar la columna
ALTER TABLE public.finding_evidence
ADD COLUMN IF NOT EXISTS evidence_type TEXT DEFAULT 'other';

-- Agregar comentario
COMMENT ON COLUMN public.finding_evidence.evidence_type IS 
'Tipo/contexto de la evidencia (mitigation, verification, initial, remediation, testing, other)';
```

### **Paso 2: Ejecutar función de creación**

Ejecutar completo: `fn_create_finding_evidence_optimized.sql`

### **Paso 3: Ejecutar función de listado**

Ejecutar completo: `fn_list_finding_evidence_optimized.sql`

### **Paso 4: Ejecutar función de eliminación**

Ejecutar completo: `fn_delete_finding_evidence_optimized.sql`

### **Paso 5: Ejecutar función para obtener archivo**

Ejecutar completo: `fn_get_evidence_file.sql`

### **Paso 6: Ejecutar función para eliminar archivo del array**

Ejecutar completo: `fn_remove_evidence_file.sql`

---

## ✅ Verificación

Después de ejecutar, verifica con:

```sql
-- Verificar que la columna existe
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'finding_evidence'
AND column_name = 'evidence_type';

-- Verificar que la función tiene los parámetros correctos
SELECT 
    p.proname as function_name,
    pg_get_function_arguments(p.oid) as arguments
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public' 
AND p.proname = 'fn_create_finding_evidence';
```

---

## 🔍 Si los campos siguen sin aparecer

1. **Verifica que la función se ejecutó correctamente** con el query de arriba
2. **Espera 5-10 segundos** para que PostgREST actualice su cache
3. **Vuelve a probar** el endpoint de listado

