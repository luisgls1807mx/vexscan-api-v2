-- ============================================================================
-- fn_list_roles - Lista roles por workspace_id o organization_id
-- Incluye array de permisos para cada rol
-- Solo se puede pasar UNO de los dos parámetros, no ambos
-- ============================================================================

DROP FUNCTION IF EXISTS public.fn_list_roles(UUID);
DROP FUNCTION IF EXISTS public.fn_list_roles(UUID, BOOLEAN);
DROP FUNCTION IF EXISTS public.fn_list_roles(UUID, UUID, BOOLEAN);

CREATE OR REPLACE FUNCTION public.fn_list_roles(
    p_workspace_id UUID DEFAULT NULL,
    p_organization_id UUID DEFAULT NULL,
    p_include_system BOOLEAN DEFAULT true
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
        -- Obtener primer workspace de la organización (para filtrar roles)
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
    
    -- Obtener roles con sus permisos
    SELECT json_agg(role_data ORDER BY is_system DESC, name)
    INTO v_result
    FROM (
        SELECT json_build_object(
            'id', r.id,
            'name', r.name,
            'description', r.description,
            'is_system', r.is_system,
            'workspace_id', r.workspace_id,
            'users_count', (SELECT COUNT(*) FROM public.user_roles WHERE role_id = r.id),
            'permissions_count', (SELECT COUNT(*) FROM public.role_permissions WHERE role_id = r.id),
            'permissions', (
                SELECT COALESCE(json_agg(
                    json_build_object(
                        'id', p.id,
                        'key', p.key,
                        'category', p.category,
                        'description', p.description
                    ) ORDER BY p.category, p.key
                ), '[]'::json)
                FROM public.role_permissions rp
                JOIN public.permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = r.id
            ),
            'created_at', r.created_at
        ) AS role_data, r.is_system, r.name
        FROM public.roles r
        WHERE r.workspace_id = v_workspace_id
          AND (p_include_system = true OR r.is_system = false)
    ) sub;
    
    RETURN COALESCE(v_result, '[]'::json);
END;
$$;

COMMENT ON FUNCTION public.fn_list_roles(UUID, UUID, BOOLEAN) IS 
'Lista roles con sus permisos. Parámetros: p_workspace_id O p_organization_id (solo uno), p_include_system (opcional, default true). Retorna array de roles con permissions[], permissions_count y users_count.';
