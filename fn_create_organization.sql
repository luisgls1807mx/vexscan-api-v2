-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_create_organization(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.fn_create_organization(TEXT, TEXT, TEXT, UUID);

-- Crear función con la firma correcta
CREATE OR REPLACE FUNCTION public.fn_create_organization(
    p_name TEXT,
    p_admin_email TEXT,
    p_admin_full_name TEXT,
    p_admin_user_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_org_id UUID;
    v_workspace_id UUID;
    v_result JSON;
BEGIN
    -- Validar permisos: solo super_admin puede crear organizaciones
    IF NOT public.fn_is_super_admin() THEN
        RAISE EXCEPTION 'Acceso denegado: se requiere super_admin';
    END IF;

    -- Validar que el usuario exista en Auth
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = p_admin_user_id) THEN
        RAISE EXCEPTION 'El usuario admin no existe en auth.users: %', p_admin_user_id;
    END IF;

    -- Crear organización
    INSERT INTO public.organizations (name, slug)
    VALUES (p_name, public.fn_generate_slug(p_name))
    RETURNING id INTO v_org_id;

    -- Crear workspace default
    INSERT INTO public.workspaces (organization_id, name, slug)
    VALUES (v_org_id, 'Default', 'default')
    RETURNING id INTO v_workspace_id;

    -- Crear/asegurar profile (id = auth.users.id)
    INSERT INTO public.profiles (id, email, full_name, is_active)
    VALUES (p_admin_user_id, p_admin_email, p_admin_full_name, true)
    ON CONFLICT (id) DO UPDATE
      SET email = EXCLUDED.email,
          full_name = EXCLUDED.full_name,
          is_active = true;

    -- Membresía org
    INSERT INTO public.organization_members (organization_id, user_id, role)
    VALUES (v_org_id, p_admin_user_id, 'org_admin')
    ON CONFLICT DO NOTHING;

    -- Membresía workspace
    INSERT INTO public.workspace_members (workspace_id, user_id)
    VALUES (v_workspace_id, p_admin_user_id)
    ON CONFLICT DO NOTHING;

    -- Roles default
    PERFORM public.create_default_workspace_roles(v_workspace_id);

    -- Asignar rol Admin
    INSERT INTO public.user_roles (workspace_id, user_id, role_id)
    SELECT v_workspace_id, p_admin_user_id, r.id
    FROM public.roles r
    WHERE r.workspace_id = v_workspace_id AND r.name = 'Admin'
    ON CONFLICT DO NOTHING;

    -- Retornar resultado
    SELECT json_build_object(
        'id', o.id,
        'name', o.name,
        'slug', o.slug,
        'is_active', o.is_active,
        'created_at', o.created_at,
        'updated_at', o.updated_at,
        'settings', o.settings,
        'projects_count', 0,
        'users_count', 1,
        'findings_count', 0,
        'admin', json_build_object(
            'id', p_admin_user_id,
            'full_name', p_admin_full_name,
            'email', p_admin_email
        ),
        'workspace_id', v_workspace_id
    ) INTO v_result
    FROM public.organizations o
    WHERE o.id = v_org_id;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_create_organization(TEXT, TEXT, TEXT, UUID) IS 
'Crea una nueva organización con un usuario admin. Requiere permisos de super_admin. El usuario admin debe existir previamente en auth.users.';

