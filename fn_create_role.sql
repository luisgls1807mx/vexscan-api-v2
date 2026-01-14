-- ============================================================================
-- fn_create_role - Crear un rol personalizado
-- Acepta workspace_id O organization_id (no ambos)
-- ============================================================================

DROP FUNCTION IF EXISTS public.fn_create_role(UUID, TEXT, TEXT, TEXT[]);
DROP FUNCTION IF EXISTS public.fn_create_role(TEXT, TEXT, UUID, TEXT[]);
DROP FUNCTION IF EXISTS public.fn_create_role(UUID, UUID, TEXT, TEXT, TEXT[]);

CREATE OR REPLACE FUNCTION public.fn_create_role(
    p_workspace_id UUID DEFAULT NULL,
    p_organization_id UUID DEFAULT NULL,
    p_name TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_permissions TEXT[] DEFAULT ARRAY[]::TEXT[]
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_workspace_id UUID;
    v_org_id UUID;
    v_role_id UUID;
    v_perm_key TEXT;
    v_result JSON;
BEGIN
    -- Validar que se pase exactamente uno de los dos parámetros
    IF p_workspace_id IS NOT NULL AND p_organization_id IS NOT NULL THEN
        RAISE EXCEPTION 'Debe pasar solo workspace_id O organization_id, no ambos';
    END IF;
    
    IF p_workspace_id IS NULL AND p_organization_id IS NULL THEN
        RAISE EXCEPTION 'Debe pasar workspace_id o organization_id';
    END IF;
    
    -- Determinar workspace_id y organization_id según el parámetro recibido
    IF p_workspace_id IS NOT NULL THEN
        v_workspace_id := p_workspace_id;
        -- Obtener organization_id desde workspace
        SELECT organization_id INTO v_org_id 
        FROM public.workspaces 
        WHERE id = p_workspace_id;
        
        IF v_org_id IS NULL THEN
            RAISE EXCEPTION 'Workspace no encontrado';
        END IF;
    ELSE
        v_org_id := p_organization_id;
        -- Obtener primer workspace de la organización
        SELECT id INTO v_workspace_id 
        FROM public.workspaces 
        WHERE organization_id = p_organization_id 
        LIMIT 1;
        
        IF v_workspace_id IS NULL THEN
            RAISE EXCEPTION 'Organización no encontrada o sin workspaces';
        END IF;
    END IF;
    
    -- Verificar permisos
    IF NOT public.fn_is_super_admin() AND NOT public.fn_is_org_admin(v_org_id) THEN
        RAISE EXCEPTION 'Acceso denegado: requiere permisos de administrador';
    END IF;
    
    -- Validar nombre
    IF p_name IS NULL OR LENGTH(TRIM(p_name)) < 2 THEN
        RAISE EXCEPTION 'El nombre del rol debe tener al menos 2 caracteres';
    END IF;
    
    -- Verificar que no exista un rol con el mismo nombre en el workspace
    IF EXISTS (
        SELECT 1 FROM public.roles 
        WHERE workspace_id = v_workspace_id 
        AND LOWER(name) = LOWER(TRIM(p_name))
    ) THEN
        RAISE EXCEPTION 'Ya existe un rol con el nombre "%" en este workspace', p_name;
    END IF;
    
    -- Crear rol
    INSERT INTO public.roles (workspace_id, name, description, is_system)
    VALUES (v_workspace_id, TRIM(p_name), p_description, false)
    RETURNING id INTO v_role_id;
    
    -- Asignar permisos
    IF p_permissions IS NOT NULL AND array_length(p_permissions, 1) > 0 THEN
        FOREACH v_perm_key IN ARRAY p_permissions LOOP
            INSERT INTO public.role_permissions (role_id, permission_id)
            SELECT v_role_id, p.id
            FROM public.permissions p
            WHERE p.key = v_perm_key
            ON CONFLICT DO NOTHING;
        END LOOP;
    END IF;
    
    -- Retornar resultado
    SELECT json_build_object(
        'id', r.id,
        'name', r.name,
        'description', r.description,
        'is_system', r.is_system,
        'workspace_id', r.workspace_id,
        'organization_id', v_org_id,
        'permissions_count', (SELECT COUNT(*) FROM public.role_permissions WHERE role_id = r.id),
        'created_at', r.created_at
    ) INTO v_result
    FROM public.roles r
    WHERE r.id = v_role_id;
    
    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.fn_create_role(UUID, UUID, TEXT, TEXT, TEXT[]) IS 
'Crea un rol personalizado. Parámetros: p_workspace_id O p_organization_id (solo uno), p_name, p_description (opcional), p_permissions (array de keys). SuperAdmin puede usar cualquiera, OrgAdmin usa organization_id.';
