-- ============================================================================
-- fn_create_organization_member.sql
-- Crea un nuevo miembro en una organización (después de crear usuario en Auth)
-- ============================================================================

-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_create_organization_member(UUID, TEXT, TEXT, TEXT, UUID);
DROP FUNCTION IF EXISTS public.fn_create_organization_member(UUID, UUID, TEXT, TEXT, UUID);

-- Crear función para crear un miembro de organización
CREATE OR REPLACE FUNCTION public.fn_create_organization_member(
    p_organization_id UUID,
    p_user_id UUID,           -- ID del usuario ya creado en Supabase Auth
    p_email TEXT,
    p_full_name TEXT,
    p_role_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_workspace_id UUID;
    v_result JSON;
BEGIN
    -- Verificar permisos (solo org_admin o super_admin)
    IF NOT public.fn_is_super_admin() AND NOT public.fn_is_org_admin(p_organization_id) THEN
        RAISE EXCEPTION 'Acceso denegado: se requiere org_admin o super_admin';
    END IF;

    -- Verificar que el usuario existe en auth.users
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = p_user_id) THEN
        RAISE EXCEPTION 'El usuario no existe en auth.users: %', p_user_id;
    END IF;

    -- Verificar que la organización existe y está activa
    IF NOT EXISTS (SELECT 1 FROM public.organizations WHERE id = p_organization_id AND is_active = true) THEN
        RAISE EXCEPTION 'Organización no encontrada o inactiva';
    END IF;

    -- Verificar que el rol existe y pertenece a un workspace de esta organización
    IF NOT EXISTS (
        SELECT 1 FROM public.roles r
        INNER JOIN public.workspaces w ON w.id = r.workspace_id
        WHERE r.id = p_role_id AND w.organization_id = p_organization_id
    ) THEN
        RAISE EXCEPTION 'Rol no válido para esta organización';
    END IF;

    -- Obtener el workspace default de la organización
    SELECT id INTO v_workspace_id
    FROM public.workspaces
    WHERE organization_id = p_organization_id
    ORDER BY created_at ASC
    LIMIT 1;

    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'La organización no tiene workspaces';
    END IF;

    -- Crear o actualizar profile
    INSERT INTO public.profiles (id, email, full_name, is_active)
    VALUES (p_user_id, p_email, p_full_name, true)
    ON CONFLICT (id) DO UPDATE
    SET email = EXCLUDED.email,
        full_name = EXCLUDED.full_name,
        is_active = true;

    -- Agregar a la organización como org_member
    INSERT INTO public.organization_members (organization_id, user_id, role)
    VALUES (p_organization_id, p_user_id, 'org_member')
    ON CONFLICT DO NOTHING;

    -- Agregar al workspace default
    INSERT INTO public.workspace_members (workspace_id, user_id)
    VALUES (v_workspace_id, p_user_id)
    ON CONFLICT DO NOTHING;

    -- Asignar rol en el workspace
    INSERT INTO public.user_roles (workspace_id, user_id, role_id)
    VALUES (v_workspace_id, p_user_id, p_role_id)
    ON CONFLICT DO NOTHING;

    -- Retornar resultado
    SELECT json_build_object(
        'id', p.id,
        'email', p.email,
        'full_name', p.full_name,
        'is_active', p.is_active,
        'organization_id', p_organization_id,
        'workspace_id', v_workspace_id,
        'role', json_build_object(
            'id', r.id,
            'name', r.name
        ),
        'created_at', p.created_at
    ) INTO v_result
    FROM public.profiles p
    LEFT JOIN public.roles r ON r.id = p_role_id
    WHERE p.id = p_user_id;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_create_organization_member(UUID, UUID, TEXT, TEXT, UUID) IS 
'Crea un nuevo miembro en una organización. El usuario debe existir previamente en Supabase Auth (creado con service_role desde el backend).';

-- Permisos
GRANT EXECUTE ON FUNCTION public.fn_create_organization_member(UUID, UUID, TEXT, TEXT, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.fn_create_organization_member(UUID, UUID, TEXT, TEXT, UUID) TO service_role;
