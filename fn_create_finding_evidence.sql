-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_create_finding_evidence(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT) CASCADE;

-- Crear función para crear evidencia de un finding
CREATE OR REPLACE FUNCTION public.fn_create_finding_evidence(
    p_finding_id UUID,
    p_file_name TEXT,
    p_file_path TEXT,
    p_file_size BIGINT,
    p_file_type TEXT DEFAULT NULL,
    p_file_hash TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_comments TEXT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_evidence_id UUID;
    v_workspace_id UUID;
    v_result JSON;
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
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para agregar evidencias a este finding';
    END IF;
    
    -- Crear registro de evidencia
    INSERT INTO public.finding_evidence (
        finding_id,
        workspace_id,
        file_name,
        file_path,
        file_size,
        file_type,
        file_hash,
        description,
        comments,
        uploaded_by
    )
    VALUES (
        p_finding_id,
        v_workspace_id,
        p_file_name,
        p_file_path,
        p_file_size,
        p_file_type,
        p_file_hash,
        p_description,
        p_comments,
        auth.uid()
    )
    RETURNING id INTO v_evidence_id;
    
    -- Retornar resultado
    SELECT json_build_object(
        'id', fe.id,
        'finding_id', fe.finding_id,
        'file_name', fe.file_name,
        'file_path', fe.file_path,
        'file_size', fe.file_size,
        'file_type', fe.file_type,
        'description', fe.description,
        'comments', fe.comments,
        'uploaded_by', fe.uploaded_by,
        'created_at', fe.created_at
    ) INTO v_result
    FROM public.finding_evidence fe
    WHERE fe.id = v_evidence_id;
    
    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_create_finding_evidence(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, TEXT) IS 
'Crea un registro de evidencia para un finding. Requiere permisos de super_admin o ser miembro de la organización del workspace.';

