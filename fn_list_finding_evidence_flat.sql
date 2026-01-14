-- Función alternativa para listar evidencias de forma plana (sin agrupar)
-- Útil si quieres ver cada archivo como registro individual
DROP FUNCTION IF EXISTS public.fn_list_finding_evidence_flat(UUID) CASCADE;

CREATE OR REPLACE FUNCTION public.fn_list_finding_evidence_flat(
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
    
    -- Obtener evidencias de forma plana (cada archivo es un registro)
    SELECT json_agg(
        json_build_object(
            'id', fe.id,
            'batch_id', fe.batch_id,
            'finding_id', fe.finding_id,
            'file_name', fe.file_name,
            'file_path', fe.file_path,
            'file_size', fe.file_size,
            'file_type', fe.file_type,
            'file_hash', fe.file_hash,
            'description', fe.description,
            'comments', fe.comments,
            'uploaded_by', fe.uploaded_by,
            'uploaded_by_name', (
                SELECT p.full_name FROM public.profiles p WHERE p.id = fe.uploaded_by
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

COMMENT ON FUNCTION public.fn_list_finding_evidence_flat(UUID) IS 
'Lista todas las evidencias activas de un finding de forma plana (cada archivo es un registro individual). Requiere permisos de super_admin o ser miembro de la organización del workspace.';

