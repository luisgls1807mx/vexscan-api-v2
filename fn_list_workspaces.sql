-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_list_workspaces(UUID, INTEGER, INTEGER, BOOLEAN);
DROP FUNCTION IF EXISTS public.fn_list_workspaces(TEXT, INTEGER, INTEGER, BOOLEAN);

-- Crear función para listar workspaces de una organización
CREATE OR REPLACE FUNCTION public.fn_list_workspaces(
    p_org_id UUID,
    p_page INTEGER DEFAULT 1,
    p_per_page INTEGER DEFAULT 20,
    p_is_active BOOLEAN DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total INTEGER;
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
            FROM public.organization_members om
            WHERE om.organization_id = p_org_id
            AND om.user_id = auth.uid()
        ) THEN
            RAISE EXCEPTION 'Acceso denegado: no eres miembro de esta organización';
        END IF;
    END IF;

    -- Contar total de workspaces
    -- Super_admin ve todos, otros solo los que tienen acceso
    SELECT COUNT(*) INTO v_total
    FROM public.workspaces w
    WHERE w.organization_id = p_org_id
    AND (p_is_active IS NULL OR w.is_active = p_is_active)
    AND (
        v_is_super_admin = true
        OR EXISTS (
            SELECT 1 
            FROM public.workspace_members wm
            WHERE wm.workspace_id = w.id
            AND wm.user_id = auth.uid()
        )
    );

    -- Obtener workspaces con paginación
    SELECT json_build_object(
        'data', COALESCE(
            json_agg(
                json_build_object(
                    'id', w.id,
                    'name', w.name,
                    'slug', w.slug,
                    'description', w.description,
                    'organization_id', w.organization_id,
                    'is_active', w.is_active,
                    'created_at', w.created_at,
                    'updated_at', w.updated_at
                ) ORDER BY w.created_at DESC
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
        SELECT w.*
        FROM public.workspaces w
        WHERE w.organization_id = p_org_id
        AND (p_is_active IS NULL OR w.is_active = p_is_active)
        AND (
            v_is_super_admin = true
            OR EXISTS (
                SELECT 1 
                FROM public.workspace_members wm
                WHERE wm.workspace_id = w.id
                AND wm.user_id = auth.uid()
            )
        )
        ORDER BY w.created_at DESC
        LIMIT p_per_page
        OFFSET (p_page - 1) * p_per_page
    ) w;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_list_workspaces(UUID, INTEGER, INTEGER, BOOLEAN) IS 
'Lista los workspaces de una organización. Los super_admin pueden ver todos los workspaces. Otros usuarios solo ven los workspaces a los que tienen acceso como miembros.';

