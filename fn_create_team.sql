-- ============================================================================
-- fn_create_team.sql
-- Crea un nuevo equipo en una organización
-- ============================================================================

-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_create_team(UUID, TEXT, TEXT, TEXT, TEXT, UUID);

-- Crear función para crear un equipo
CREATE OR REPLACE FUNCTION public.fn_create_team(
    p_org_id UUID,
    p_name TEXT,
    p_description TEXT DEFAULT NULL,
    p_icon TEXT DEFAULT NULL,
    p_color TEXT DEFAULT '#3b82f6',
    p_leader_id UUID DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_team_id UUID;
    v_result JSON;
BEGIN
    -- Verificar permisos (solo org_admin o super_admin)
    IF NOT public.fn_is_super_admin() AND NOT public.fn_is_org_admin(p_org_id) THEN
        RAISE EXCEPTION 'Acceso denegado';
    END IF;
    
    -- Crear equipo
    INSERT INTO public.teams (
        organization_id, name, description, icon, color, leader_id, created_by
    )
    VALUES (p_org_id, p_name, p_description, p_icon, p_color, p_leader_id, auth.uid())
    RETURNING id INTO v_team_id;
    
    -- Si hay líder, agregarlo como miembro
    IF p_leader_id IS NOT NULL THEN
        INSERT INTO public.team_members (team_id, user_id, role, added_by)
        VALUES (v_team_id, p_leader_id, 'leader', auth.uid());
    END IF;
    
    -- Retornar resultado con TODOS los campos requeridos
    SELECT json_build_object(
        'id', t.id,
        'name', t.name,
        'description', t.description,
        'icon', t.icon,
        'color', t.color,
        'organization_id', t.organization_id,
        'is_active', t.is_active,
        'created_at', t.created_at,
        'updated_at', t.updated_at,
        'leader', (
            SELECT json_build_object('id', p.id, 'full_name', p.full_name)
            FROM public.profiles p WHERE p.id = t.leader_id
        ),
        'member_count', 0
    ) INTO v_result
    FROM public.teams t
    WHERE t.id = v_team_id;
    
    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_create_team(UUID, TEXT, TEXT, TEXT, TEXT, UUID) IS 
'Crea un nuevo equipo en una organización. Requiere permisos de org_admin o super_admin.';
