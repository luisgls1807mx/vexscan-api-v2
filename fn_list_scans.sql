-- Eliminar funciones existentes si existen (para evitar conflictos de overloading)
DROP FUNCTION IF EXISTS public.fn_list_scans(UUID, INTEGER, INTEGER);
DROP FUNCTION IF EXISTS public.fn_list_scans(UUID, INTEGER, INTEGER, TEXT, TEXT);

-- Crear función para listar scans de un proyecto
CREATE OR REPLACE FUNCTION public.fn_list_scans(
    p_project_id UUID,
    p_page INTEGER DEFAULT 1,
    p_per_page INTEGER DEFAULT 20
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total INTEGER;
    v_result JSON;
BEGIN
    -- Verificar permisos (super_admin o miembro de la organización del proyecto)
    IF NOT public.fn_is_super_admin() AND NOT EXISTS (
        SELECT 1 
        FROM public.projects p
        INNER JOIN public.organization_members om ON om.organization_id = p.organization_id
        WHERE p.id = p_project_id
        AND om.user_id = auth.uid()
        AND om.is_active = true
    ) THEN
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para ver los scans de este proyecto';
    END IF;

    -- Contar total de scans
    SELECT COUNT(*) INTO v_total
    FROM public.scan_imports si
    WHERE si.project_id = p_project_id;

    -- Obtener scans con paginación
    SELECT json_build_object(
        'data', COALESCE(
            json_agg(
                json_build_object(
                    'id', si.id,
                    'file_name', si.file_name,
                    'scanner', si.scanner,
                    'status', si.status,
                    'network_zone', si.network_zone::TEXT,
                    'file_size', si.file_size,
                    'file_hash', si.file_hash,
                    'findings_total', si.findings_total,
                    'findings_new', si.findings_new,
                    'findings_updated', si.findings_updated,
                    'hosts_total', si.hosts_total,
                    'scan_started_at', si.scan_started_at,
                    'scan_finished_at', si.scan_finished_at,
                    'scanner_version', si.scanner_version,
                    'error_message', si.error_message,
                    'imported_at', si.imported_at,
                    'processed_at', si.processed_at
                ) ORDER BY si.imported_at DESC
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
        SELECT si.*
        FROM public.scan_imports si
        WHERE si.project_id = p_project_id
        ORDER BY si.imported_at DESC
        LIMIT p_per_page
        OFFSET (p_page - 1) * p_per_page
    ) si;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_list_scans(UUID, INTEGER, INTEGER) IS 
'Lista los scans de un proyecto con paginación. Requiere permisos de super_admin o ser miembro de la organización del proyecto.';

