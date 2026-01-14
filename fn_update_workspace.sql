-- ============================================================================
-- fn_update_workspace.sql
-- RPC para actualizar un workspace
-- ============================================================================

-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_update_workspace(UUID, TEXT, TEXT, BOOLEAN);

-- Crear función
CREATE OR REPLACE FUNCTION public.fn_update_workspace(
    p_workspace_id UUID,
    p_name TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_is_active BOOLEAN DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user_id UUID;
    v_org_id UUID;
    v_is_super_admin BOOLEAN;
    v_is_org_admin BOOLEAN;
    v_result JSON;
BEGIN
    -- Obtener usuario actual
    v_user_id := auth.uid();
    
    IF v_user_id IS NULL THEN
        RETURN json_build_object(
            'success', false,
            'error', 'No autenticado'
        );
    END IF;

    -- Obtener organization_id del workspace
    SELECT organization_id INTO v_org_id
    FROM public.workspaces
    WHERE id = p_workspace_id;

    IF v_org_id IS NULL THEN
        RETURN json_build_object(
            'success', false,
            'error', 'Workspace no encontrado'
        );
    END IF;

    -- Verificar si es super_admin (usando profiles.is_super_admin como otros RPCs)
    SELECT COALESCE(p.is_super_admin, false) INTO v_is_super_admin
    FROM public.profiles p
    WHERE p.id = v_user_id;

    -- Verificar si es org_admin de la organización
    SELECT EXISTS (
        SELECT 1 FROM public.organization_members om
        WHERE om.user_id = v_user_id
        AND om.organization_id = v_org_id
        AND om.role = 'org_admin'
    ) INTO v_is_org_admin;

    -- Solo super_admin u org_admin pueden actualizar workspaces
    IF NOT v_is_super_admin AND NOT v_is_org_admin THEN
        RETURN json_build_object(
            'success', false,
            'error', 'No tienes permiso para actualizar este workspace'
        );
    END IF;

    -- Actualizar workspace (solo campos no nulos)
    UPDATE public.workspaces
    SET 
        name = COALESCE(p_name, name),
        description = COALESCE(p_description, description),
        is_active = COALESCE(p_is_active, is_active),
        updated_at = NOW()
    WHERE id = p_workspace_id;

    -- Retornar workspace actualizado
    SELECT json_build_object(
        'success', true,
        'data', json_build_object(
            'id', w.id,
            'name', w.name,
            'slug', w.slug,
            'description', w.description,
            'is_active', w.is_active,
            'organization_id', w.organization_id,
            'settings', w.settings,
            'created_at', w.created_at,
            'updated_at', w.updated_at
        )
    ) INTO v_result
    FROM public.workspaces w
    WHERE w.id = p_workspace_id;

    RETURN v_result;
END;
$$;

-- Comentario
COMMENT ON FUNCTION public.fn_update_workspace(UUID, TEXT, TEXT, BOOLEAN) IS 
'Actualiza un workspace. Solo org_admin o super_admin pueden actualizar. Campos NULL no se actualizan.';

-- Permisos
GRANT EXECUTE ON FUNCTION public.fn_update_workspace(UUID, TEXT, TEXT, BOOLEAN) TO authenticated;
GRANT EXECUTE ON FUNCTION public.fn_update_workspace(UUID, TEXT, TEXT, BOOLEAN) TO service_role;
