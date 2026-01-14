-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_get_project(UUID);

-- Crear función para obtener detalles de un proyecto
CREATE OR REPLACE FUNCTION public.fn_get_project(
    p_project_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
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
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para ver este proyecto';
    END IF;

    -- Retornar resultado con todos los campos requeridos
    SELECT json_build_object(
        'id', p.id,
        'name', p.name,
        'description', p.description,
        'color', p.color,
        'slug', p.slug,
        'status', p.status,
        'organization_id', p.organization_id,
        'leader_id', p.leader_id,
        'leader_name', pr_leader.full_name,
        'responsible_id', p.responsible_id,
        'responsible_name', pr_responsible.full_name,
        'created_at', p.created_at,
        'updated_at', p.updated_at,
        'total_findings', COALESCE((
            SELECT COUNT(*) FROM public.findings WHERE project_id = p.id
        ), 0),
        'open_findings', COALESCE((
            SELECT COUNT(*) FROM public.findings WHERE project_id = p.id AND status = 'Open'
        ), 0),
        'critical_count', COALESCE((
            SELECT COUNT(*) FROM public.findings WHERE project_id = p.id AND severity = 'Critical' AND status = 'Open'
        ), 0),
        'high_count', COALESCE((
            SELECT COUNT(*) FROM public.findings WHERE project_id = p.id AND severity = 'High' AND status = 'Open'
        ), 0),
        'medium_count', COALESCE((
            SELECT COUNT(*) FROM public.findings WHERE project_id = p.id AND severity = 'Medium' AND status = 'Open'
        ), 0),
        'low_count', COALESCE((
            SELECT COUNT(*) FROM public.findings WHERE project_id = p.id AND severity = 'Low' AND status = 'Open'
        ), 0),
        'total_assets', COALESCE((
            SELECT COUNT(*) FROM public.assets WHERE project_id = p.id
        ), 0),
        'last_scan_at', (
            SELECT MAX(imported_at) FROM public.scan_imports WHERE project_id = p.id
        )
    ) INTO v_result
    FROM public.projects p
    LEFT JOIN public.profiles pr_leader ON pr_leader.id = p.leader_id
    LEFT JOIN public.profiles pr_responsible ON pr_responsible.id = p.responsible_id
    WHERE p.id = p_project_id;

    IF v_result IS NULL THEN
        RAISE EXCEPTION 'Proyecto no encontrado';
    END IF;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_get_project(UUID) IS 
'Obtiene los detalles de un proyecto con estadísticas. Requiere permisos de super_admin o ser miembro de la organización del proyecto.';

