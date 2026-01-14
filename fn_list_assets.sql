-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_list_assets(UUID, UUID, INTEGER, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT, BOOLEAN, BOOLEAN, TEXT, TEXT);

-- Crear función para listar assets con filtros
CREATE OR REPLACE FUNCTION public.fn_list_assets(
    p_workspace_id UUID DEFAULT NULL,
    p_project_id UUID DEFAULT NULL,
    p_page INTEGER DEFAULT 1,
    p_per_page INTEGER DEFAULT 50,
    p_search TEXT DEFAULT NULL,
    p_asset_type TEXT DEFAULT NULL,
    p_operating_system TEXT DEFAULT NULL,
    p_environment TEXT DEFAULT NULL,
    p_criticality TEXT DEFAULT NULL,
    p_has_findings BOOLEAN DEFAULT NULL,
    p_is_manual BOOLEAN DEFAULT NULL,
    p_sort_by TEXT DEFAULT 'last_seen',
    p_sort_order TEXT DEFAULT 'desc'
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total INTEGER;
    v_result JSON;
    v_order_by TEXT;
BEGIN
    -- Verificar permisos (super_admin o miembro del workspace)
    IF NOT public.fn_is_super_admin() AND NOT EXISTS (
        SELECT 1 
        FROM public.workspace_members wm
        WHERE wm.workspace_id = COALESCE(p_workspace_id, (
            SELECT workspace_id FROM public.projects WHERE id = p_project_id LIMIT 1
        ))
        AND wm.user_id = auth.uid()
    ) THEN
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para ver los assets';
    END IF;

    -- Construir ORDER BY
    v_order_by := CASE 
        WHEN p_sort_by = 'identifier' THEN 'a.identifier'
        WHEN p_sort_by = 'last_seen' THEN 'a.last_seen'
        WHEN p_sort_by = 'findings_count' THEN 'findings_count'
        ELSE 'a.last_seen'
    END || ' ' || UPPER(COALESCE(p_sort_order, 'desc'));

    -- Contar total de assets
    SELECT COUNT(*) INTO v_total
    FROM public.assets a
    WHERE (p_workspace_id IS NULL OR a.workspace_id = p_workspace_id)
    AND (p_project_id IS NULL OR a.project_id = p_project_id)
    AND (p_search IS NULL OR a.identifier ILIKE '%' || p_search || '%' OR a.hostname ILIKE '%' || p_search || '%' OR a.ip_address::TEXT ILIKE '%' || p_search || '%')
    AND (p_asset_type IS NULL OR a.asset_type::TEXT = p_asset_type)
    AND (p_operating_system IS NULL OR a.operating_system ILIKE '%' || p_operating_system || '%')
    AND (p_environment IS NULL OR a.environment::TEXT = p_environment)
    AND (p_criticality IS NULL OR a.criticality::TEXT = p_criticality)
    AND (p_is_manual IS NULL OR a.is_manual = p_is_manual)
    AND (p_has_findings IS NULL OR EXISTS (
        SELECT 1 FROM public.findings f WHERE f.asset_id = a.id AND f.status::TEXT = 'Open'
    ) = p_has_findings);

    -- Obtener assets con paginación
    SELECT json_build_object(
        'data', COALESCE(
            json_agg(
                json_build_object(
                    'id', a.id,
                    'identifier', a.identifier,
                    'name', a.name,
                    'hostname', a.hostname,
                    'ip_address', a.ip_address,
                    'asset_type', a.asset_type,
                    'operating_system', a.operating_system,
                    'environment', a.environment,
                    'criticality', a.criticality,
                    'is_manual', a.is_manual,
                    'last_seen', a.last_seen,
                    'created_at', a.created_at
                ) ORDER BY 
                    CASE WHEN p_sort_by = 'identifier' THEN a.identifier END,
                    CASE WHEN p_sort_by = 'last_seen' THEN a.last_seen END DESC
            ),
            '[]'::json
        ),
        'pagination', json_build_object(
            'page', p_page,
            'per_page', p_per_page,
            'total', v_total,
            'total_pages', CEIL(v_total::NUMERIC / NULLIF(p_per_page, 0))
        )
    ) INTO v_result
    FROM (
        SELECT a.*
        FROM public.assets a
        WHERE (p_workspace_id IS NULL OR a.workspace_id = p_workspace_id)
        AND (p_project_id IS NULL OR a.project_id = p_project_id)
        AND (p_search IS NULL OR a.identifier ILIKE '%' || p_search || '%' OR a.hostname ILIKE '%' || p_search || '%' OR a.ip_address::TEXT ILIKE '%' || p_search || '%')
        AND (p_asset_type IS NULL OR a.asset_type = p_asset_type)
        AND (p_operating_system IS NULL OR a.operating_system ILIKE '%' || p_operating_system || '%')
        AND (p_environment IS NULL OR a.environment = p_environment)
        AND (p_criticality IS NULL OR a.criticality = p_criticality)
        AND (p_is_manual IS NULL OR a.is_manual = p_is_manual)
        AND (p_has_findings IS NULL OR EXISTS (
            SELECT 1 FROM public.findings f WHERE f.asset_id = a.id AND f.status::TEXT = 'Open'
        ) = p_has_findings)
        ORDER BY 
            CASE WHEN p_sort_by = 'identifier' THEN a.identifier END,
            CASE WHEN p_sort_by = 'last_seen' THEN a.last_seen END DESC NULLS LAST
        LIMIT p_per_page
        OFFSET (p_page - 1) * p_per_page
    ) a;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_list_assets(UUID, UUID, INTEGER, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT, BOOLEAN, BOOLEAN, TEXT, TEXT) IS 
'Lista los assets con filtros y paginación. Requiere permisos de super_admin o ser miembro del workspace.';

