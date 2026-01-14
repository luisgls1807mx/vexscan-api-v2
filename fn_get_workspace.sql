-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_get_workspace(UUID);

-- Crear función para obtener detalles de un workspace
CREATE OR REPLACE FUNCTION public.fn_get_workspace(
    p_workspace_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_result JSON;
    v_is_super_admin BOOLEAN;
BEGIN
    -- Verificar si el usuario es super_admin
    SELECT COALESCE(p.is_super_admin, false) INTO v_is_super_admin
    FROM public.profiles p
    WHERE p.id = auth.uid();

    -- Validar acceso: super_admin tiene acceso completo, otros deben ser miembros
    IF NOT v_is_super_admin THEN
        IF NOT EXISTS (
            SELECT 1 
            FROM public.workspace_members wm
            WHERE wm.workspace_id = p_workspace_id
            AND wm.user_id = auth.uid()
        ) THEN
            RAISE EXCEPTION 'Acceso denegado: no eres miembro de este workspace';
        END IF;
    END IF;

    -- Retornar resultado
    SELECT json_build_object(
        'id', w.id,
        'name', w.name,
        'slug', w.slug,
        'description', w.description,
        'organization_id', w.organization_id,
        'is_active', w.is_active,
        'created_at', w.created_at,
        'updated_at', w.updated_at
    ) INTO v_result
    FROM public.workspaces w
    WHERE w.id = p_workspace_id;

    IF v_result IS NULL THEN
        RAISE EXCEPTION 'Workspace no encontrado';
    END IF;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_get_workspace(UUID) IS 
'Obtiene los detalles de un workspace. Los super_admin pueden ver cualquier workspace. Otros usuarios solo pueden ver workspaces de los que son miembros.';

