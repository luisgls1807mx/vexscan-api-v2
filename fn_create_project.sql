-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_create_project(TEXT, TEXT, TEXT, UUID, UUID, UUID);
DROP FUNCTION IF EXISTS public.fn_create_project(TEXT, TEXT, TEXT, UUID, UUID);

-- Crear función para crear proyecto
CREATE OR REPLACE FUNCTION public.fn_create_project(
    p_org_id UUID,
    p_name TEXT,
    p_description TEXT DEFAULT NULL,
    p_color TEXT DEFAULT '#3b82f6',
    p_leader_id UUID DEFAULT NULL,
    p_responsible_id UUID DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_project_id UUID;
    v_leader_id UUID;
    v_workspace_id UUID;
    v_result JSON;
BEGIN
    -- Verificar permisos (solo super_admin puede crear proyectos)
    IF NOT public.fn_is_super_admin() THEN
        RAISE EXCEPTION 'Acceso denegado: solo el SuperAdmin puede crear proyectos';
    END IF;

    -- Si no se especifica líder, usar el org_admin
    IF p_leader_id IS NULL THEN
        SELECT user_id INTO v_leader_id
        FROM public.organization_members
        WHERE organization_id = p_org_id AND role = 'org_admin'
        LIMIT 1;
    ELSE
        v_leader_id := p_leader_id;
    END IF;

    -- Obtener workspace_id
    SELECT id INTO v_workspace_id
    FROM public.workspaces
    WHERE organization_id = p_org_id
    LIMIT 1;

    -- Crear proyecto
    INSERT INTO public.projects (
        organization_id, name, slug, description, color,
        leader_id, responsible_id, created_by
    )
    VALUES (
        p_org_id, p_name, public.fn_generate_slug(p_name), p_description, p_color,
        v_leader_id, p_responsible_id, auth.uid()
    )
    RETURNING id INTO v_project_id;

    -- Crear notificación para el líder
    INSERT INTO public.notifications (
        workspace_id, user_id, type, category, priority,
        title, body, project_id, payload
    )
    VALUES (
        v_workspace_id, v_leader_id, 'project.leader_assigned', 'project', 'high',
        'Te asignaron como Líder de Proyecto',
        'Se te ha asignado como líder del proyecto "' || p_name || '"',
        v_project_id,
        jsonb_build_object('project_name', p_name, 'assigned_by', auth.uid())
    );

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
        'total_findings', 0,
        'open_findings', 0,
        'critical_count', 0,
        'high_count', 0,
        'medium_count', 0,
        'low_count', 0,
        'total_assets', 0,
        'last_scan_at', NULL
    ) INTO v_result
    FROM public.projects p
    LEFT JOIN public.profiles pr_leader ON pr_leader.id = p.leader_id
    LEFT JOIN public.profiles pr_responsible ON pr_responsible.id = p.responsible_id
    WHERE p.id = v_project_id;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_create_project(UUID, TEXT, TEXT, TEXT, UUID, UUID) IS 
'Crea un nuevo proyecto en una organización. Requiere permisos de super_admin.';

