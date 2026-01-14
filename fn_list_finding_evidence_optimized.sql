-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_list_finding_evidence(UUID) CASCADE;

-- Crear función optimizada para listar evidencias de un finding
-- Retorna registros donde cada uno puede contener múltiples archivos
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
    
    -- Obtener evidencias (cada registro puede tener múltiples archivos)
    SELECT json_agg(
        json_build_object(
            'id', fe.id,
            'finding_id', fe.finding_id,
            'files', fe.files,  -- Array JSONB con todos los archivos
            'file_count', jsonb_array_length(fe.files),
            'description', fe.description,
            'comments', fe.comments,
            'tags', COALESCE(fe.tags, '[]'::jsonb),  -- Array de tags
            'related_status_change_id', fe.related_status_change_id,
            'related_status_change', (
                -- Información del cambio de estatus relacionado (si existe)
                SELECT json_build_object(
                    'id', fsh.id,
                    'from_status', fsh.from_status,
                    'to_status', fsh.to_status,
                    'comment', fsh.comment,
                    'changed_by', fsh.changed_by,
                    'changed_by_name', (
                        SELECT p.full_name FROM public.profiles p WHERE p.id = fsh.changed_by
                    ),
                    'created_at', fsh.created_at
                )
                FROM public.finding_status_history fsh
                WHERE fsh.id = fe.related_status_change_id
            ),
            'uploaded_by', fe.uploaded_by,
            'uploaded_by_name', (
                SELECT p.full_name FROM public.profiles p WHERE p.id = fe.uploaded_by
            ),
            'uploaded_by_email', (
                SELECT p.email FROM public.profiles p WHERE p.id = fe.uploaded_by
            ),
            'created_at', fe.created_at,
            'updated_at', fe.updated_at
        )
        ORDER BY fe.created_at DESC
    ) INTO v_result
    FROM public.finding_evidence fe
    WHERE fe.finding_id = p_finding_id
    AND fe.is_active = true;
    
    RETURN COALESCE(v_result, '[]'::json);
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_list_finding_evidence(UUID) IS 
'Lista todas las evidencias activas de un finding. Cada registro puede contener uno o múltiples archivos en el campo files (JSONB). Requiere permisos de super_admin o ser miembro de la organización del workspace.';

