-- Función para obtener historial de cambios de estatus con evidencias relacionadas (paginado)
DROP FUNCTION IF EXISTS public.fn_get_finding_status_history_with_evidence(UUID) CASCADE;
DROP FUNCTION IF EXISTS public.fn_get_finding_status_history_with_evidence(UUID, INTEGER, INTEGER) CASCADE;

CREATE OR REPLACE FUNCTION public.fn_get_finding_status_history_with_evidence(
    p_finding_id UUID,
    p_page INTEGER DEFAULT 1,
    p_per_page INTEGER DEFAULT 20
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_result JSON;
    v_workspace_id UUID;
    v_total INTEGER;
    v_offset INTEGER := (p_page - 1) * p_per_page;
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
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para ver el historial de este finding';
    END IF;
    
    -- Contar total de cambios de estatus
    SELECT COUNT(*) INTO v_total
    FROM public.finding_status_history fsh
    WHERE fsh.finding_id = p_finding_id;
    
    -- Obtener historial de cambios de estatus con evidencias relacionadas (paginado)
    SELECT json_build_object(
        'data', (
            SELECT json_agg(
                json_build_object(
                    'id', fsh.id,
                    'finding_id', fsh.finding_id,
                    'from_status', fsh.from_status,
                    'to_status', fsh.to_status,
                    'comment', fsh.comment,
                    'metadata', fsh.metadata,
                    'changed_by', fsh.changed_by,
                    'changed_by_name', (
                        SELECT p.full_name FROM public.profiles p WHERE p.id = fsh.changed_by
                    ),
                    'changed_by_email', (
                        SELECT p.email FROM public.profiles p WHERE p.id = fsh.changed_by
                    ),
                    'created_at', fsh.created_at,
                    'related_evidence', (
                        -- Evidencias relacionadas con este cambio de estatus
                        SELECT json_agg(
                            json_build_object(
                                'id', fe.id,
                                'files', fe.files,
                                'file_count', jsonb_array_length(fe.files),
                                'description', fe.description,
                                'comments', fe.comments,
                                'tags', COALESCE(fe.tags, '[]'::jsonb),  -- Array de tags
                                'uploaded_by', fe.uploaded_by,
                                'uploaded_by_name', (
                                    SELECT p.full_name FROM public.profiles p WHERE p.id = fe.uploaded_by
                                ),
                                'uploaded_by_email', (
                                    SELECT p.email FROM public.profiles p WHERE p.id = fe.uploaded_by
                                ),
                                'created_at', fe.created_at
                            )
                            ORDER BY fe.created_at
                        )
                        FROM public.finding_evidence fe
                        WHERE fe.finding_id = p_finding_id
                        AND fe.related_status_change_id = fsh.id
                        AND fe.is_active = true
                    ),
                    'evidence_count', (
                        SELECT COUNT(*)::INTEGER
                        FROM public.finding_evidence fe
                        WHERE fe.finding_id = p_finding_id
                        AND fe.related_status_change_id = fsh.id
                        AND fe.is_active = true
                    )
                )
                ORDER BY fsh.created_at DESC
            )
            FROM (
                SELECT fsh.*
                FROM public.finding_status_history fsh
                WHERE fsh.finding_id = p_finding_id
                ORDER BY fsh.created_at DESC
                LIMIT p_per_page
                OFFSET v_offset
            ) fsh
        ),
        'pagination', json_build_object(
            'page', p_page,
            'per_page', p_per_page,
            'total', v_total,
            'total_pages', CASE 
                WHEN v_total = 0 THEN 0
                ELSE CEIL(v_total::FLOAT / p_per_page)
            END
        )
    ) INTO v_result;
    
    RETURN COALESCE(v_result, json_build_object('data', '[]'::json, 'pagination', json_build_object('page', 1, 'per_page', 20, 'total', 0, 'total_pages', 0)));
END;
$$;

COMMENT ON FUNCTION public.fn_get_finding_status_history_with_evidence(UUID, INTEGER, INTEGER) IS 
'Retorna el historial paginado de cambios de estatus de un finding, incluyendo todas las evidencias relacionadas con cada cambio de estatus. Parámetros: p_finding_id, p_page (default 1), p_per_page (default 20). Requiere permisos de super_admin o ser miembro de la organización del workspace.';

