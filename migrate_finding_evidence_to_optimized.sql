-- Script de migración: convertir estructura anterior (batch_id) a estructura optimizada (files JSONB)
-- Ejecutar SOLO si ya tienes datos en la tabla finding_evidence con la estructura anterior

-- Paso 1: Crear tabla temporal con la nueva estructura
CREATE TABLE IF NOT EXISTS public.finding_evidence_new (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES public.findings(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    files JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT,
    comments TEXT,
    uploaded_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT finding_evidence_files_not_empty CHECK (jsonb_array_length(files) > 0)
);

-- Paso 2: Migrar datos agrupados por batch_id
-- Si batch_id existe, agrupar todos los archivos del mismo batch
-- Si batch_id es NULL, cada archivo es un grupo individual
INSERT INTO public.finding_evidence_new (
    finding_id,
    workspace_id,
    files,
    description,
    comments,
    uploaded_by,
    is_active,
    created_at,
    updated_at
)
SELECT 
    fe.finding_id,
    fe.workspace_id,
    -- Agrupar archivos en array JSONB
    jsonb_agg(
        jsonb_build_object(
            'file_name', fe.file_name,
            'file_path', fe.file_path,
            'file_size', fe.file_size,
            'file_type', fe.file_type,
            'file_hash', fe.file_hash
        )
        ORDER BY fe.created_at
    ) as files,
    -- Tomar description y comments del primer registro del grupo
    MIN(fe.description) as description,
    MIN(fe.comments) as comments,
    fe.uploaded_by,
    MIN(fe.is_active::int)::boolean as is_active,
    MIN(fe.created_at) as created_at,
    MAX(fe.updated_at) as updated_at
FROM public.finding_evidence fe
WHERE fe.is_active = true
GROUP BY 
    COALESCE(fe.batch_id, fe.id::UUID),  -- Agrupar por batch_id o id individual
    fe.finding_id,
    fe.workspace_id,
    fe.uploaded_by;

-- Paso 3: Verificar migración
DO $$
DECLARE
    v_old_count INTEGER;
    v_new_count INTEGER;
    v_old_files_count INTEGER;
    v_new_files_count INTEGER;
BEGIN
    -- Contar registros antiguos
    SELECT COUNT(*) INTO v_old_count FROM public.finding_evidence WHERE is_active = true;
    
    -- Contar registros nuevos
    SELECT COUNT(*) INTO v_new_count FROM public.finding_evidence_new;
    
    -- Contar archivos totales en estructura antigua
    SELECT COUNT(*) INTO v_old_files_count FROM public.finding_evidence WHERE is_active = true;
    
    -- Contar archivos totales en estructura nueva
    SELECT SUM(jsonb_array_length(files)) INTO v_new_files_count FROM public.finding_evidence_new;
    
    RAISE NOTICE 'Registros antiguos: %', v_old_count;
    RAISE NOTICE 'Registros nuevos: %', v_new_count;
    RAISE NOTICE 'Archivos antiguos: %', v_old_files_count;
    RAISE NOTICE 'Archivos nuevos: %', v_new_files_count;
    
    IF v_old_files_count != v_new_files_count THEN
        RAISE EXCEPTION 'Error en migración: número de archivos no coincide';
    END IF;
END;
$$;

-- Paso 4: Renombrar tablas (SOLO ejecutar si la migración fue exitosa)
-- Descomentar estas líneas después de verificar que todo está correcto:

-- ALTER TABLE public.finding_evidence RENAME TO finding_evidence_old;
-- ALTER TABLE public.finding_evidence_new RENAME TO finding_evidence;

-- Paso 5: Recrear índices y políticas (ya están en create_table_finding_evidence_optimized.sql)
-- Ejecutar create_table_finding_evidence_optimized.sql después de renombrar

-- Paso 6: Eliminar tabla antigua (SOLO después de verificar que todo funciona)
-- DROP TABLE IF EXISTS public.finding_evidence_old CASCADE;

