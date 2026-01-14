-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_list_finding_evidence(UUID) CASCADE;

-- Crear función para listar evidencias de un finding
CREATE OR REPLACE FUNCTION public.fn_list_finding_evidence(
    p_finding_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_result JSON;
    v_workspace_id UUID;
BEGIN
    -- Obtener workspace_id del finding
    SELECT workspace_id INTO v_workspace_id
    FROM public.findings
    WHERE id = p_finding_id;
    
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Finding no encontrado';
    END IF;
    
    -- Verificar permisos (super_admin o miembro de la organización del workspace)
    IF NOT public.fn_is_super_admin() AND NOT EXISTS (
        SELECT 1 FROM public.organization_members om
        JOIN public.workspaces w ON w.organization_id = om.organization_id
        WHERE om.user_id = auth.uid()
        AND om.is_active = true
        AND w.id = v_workspace_id
    ) THEN
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para ver evidencias de este finding';
    END IF;
    
    -- Obtener evidencias agrupadas por batch_id
    -- Archivos con el mismo batch_id se agrupan juntos con description y comments compartidos
    -- Archivos sin batch_id (NULL) se muestran individualmente
    WITH grouped_evidence AS (
        SELECT 
            COALESCE(fe.batch_id, fe.id::UUID) as group_key, -- Usar batch_id o id individual como clave de agrupación
            fe.batch_id,
            fe.description,
            fe.comments,
            fe.uploaded_by,
            MIN(fe.created_at) as group_created_at,
            json_agg(
                json_build_object(
                    'id', fe.id,
                    'file_name', fe.file_name,
                    'file_path', fe.file_path,
                    'file_size', fe.file_size,
                    'file_type', fe.file_type,
                    'file_hash', fe.file_hash,
                    'created_at', fe.created_at
                )
                ORDER BY fe.created_at
            ) as files
        FROM public.finding_evidence fe
        WHERE fe.finding_id = p_finding_id
        AND fe.is_active = true
        GROUP BY 
            COALESCE(fe.batch_id, fe.id::UUID),
            fe.batch_id,
            fe.description,
            fe.comments,
            fe.uploaded_by
    )
    SELECT json_agg(
        json_build_object(
            'batch_id', ge.batch_id,
            'description', ge.description,  -- Description compartida del batch
            'comments', ge.comments,          -- Comments compartidos del batch
            'uploaded_by', ge.uploaded_by,
            'uploaded_by_name', (
                SELECT p.full_name FROM public.profiles p WHERE p.id = ge.uploaded_by
            ),
            'created_at', ge.group_created_at,
            'file_count', jsonb_array_length(ge.files::jsonb),
            'files', ge.files
        )
        ORDER BY ge.group_created_at DESC
    ) INTO v_result
    FROM grouped_evidence ge;
    
    RETURN COALESCE(v_result, '[]'::json);
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_list_finding_evidence(UUID) IS 
'Lista todas las evidencias activas de un finding. Requiere permisos de super_admin o ser miembro de la organización del workspace.';

