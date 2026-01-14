-- ============================================================================
-- fn_list_organization_members.sql
-- Lista los miembros de una organización con paginación y filtros
-- ============================================================================

-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_list_organization_members(UUID, INTEGER, INTEGER, TEXT, TEXT, BOOLEAN);

-- Crear función para listar miembros de una organización
CREATE OR REPLACE FUNCTION public.fn_list_organization_members(
    p_organization_id UUID,
    p_page INTEGER DEFAULT 1,
    p_per_page INTEGER DEFAULT 50,
    p_search TEXT DEFAULT NULL,
    p_role TEXT DEFAULT NULL,
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

    -- Validar acceso: super_admin tiene acceso completo, otros deben ser miembros de la organización
    IF NOT v_is_super_admin THEN
        IF NOT EXISTS (
            SELECT 1 
            FROM public.organization_members om
            WHERE om.organization_id = p_organization_id
            AND om.user_id = auth.uid()
        ) THEN
            RAISE EXCEPTION 'Acceso denegado: no eres miembro de esta organización';
        END IF;
    END IF;

    -- Contar total de miembros según filtros
    SELECT COUNT(*) INTO v_total
    FROM public.organization_members om
    INNER JOIN public.profiles p ON p.id = om.user_id
    WHERE om.organization_id = p_organization_id
    AND (p_is_active IS NULL OR p.is_active = p_is_active)
    AND (p_role IS NULL OR om.role::TEXT = p_role)
    AND (
        p_search IS NULL 
        OR p.full_name ILIKE '%' || p_search || '%'
        OR p.email ILIKE '%' || p_search || '%'
    );

    -- Obtener miembros con paginación
    SELECT json_build_object(
        'data', COALESCE(
            json_agg(
                json_build_object(
                    'id', p.id,
                    'email', p.email,
                    'full_name', p.full_name,
                    'avatar_url', p.avatar_url,
                    'is_active', p.is_active,
                    'is_super_admin', COALESCE(p.is_super_admin, false),
                    'role', om.role::TEXT,
                    'organization_id', om.organization_id,
                    'joined_at', om.created_at,
                    'created_at', p.created_at,
                    'updated_at', p.updated_at,
                    'workspaces', (
                        SELECT COALESCE(json_agg(
                            json_build_object(
                                'id', w.id,
                                'name', w.name,
                                'slug', w.slug
                            )
                        ), '[]'::json)
                        FROM public.workspace_members wm
                        INNER JOIN public.workspaces w ON w.id = wm.workspace_id
                        WHERE wm.user_id = p.id
                        AND w.organization_id = p_organization_id
                    ),
                    'stats', json_build_object(
                        'findings_assigned', (
                            SELECT COUNT(*)
                            FROM public.finding_assignments fa
                            INNER JOIN public.findings f ON f.id = fa.finding_id
                            INNER JOIN public.projects proj ON proj.id = f.project_id
                            WHERE fa.user_id = p.id
                            AND proj.organization_id = p_organization_id
                        ),
                        'workspaces_count', (
                            SELECT COUNT(*)
                            FROM public.workspace_members wm
                            INNER JOIN public.workspaces w ON w.id = wm.workspace_id
                            WHERE wm.user_id = p.id
                            AND w.organization_id = p_organization_id
                        )
                    )
                ) ORDER BY om.created_at DESC
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
        SELECT om.*, p.*
        FROM public.organization_members om
        INNER JOIN public.profiles p ON p.id = om.user_id
        WHERE om.organization_id = p_organization_id
        AND (p_is_active IS NULL OR p.is_active = p_is_active)
        AND (p_role IS NULL OR om.role::TEXT = p_role)
        AND (
            p_search IS NULL 
            OR p.full_name ILIKE '%' || p_search || '%'
            OR p.email ILIKE '%' || p_search || '%'
        )
        ORDER BY om.created_at DESC
        LIMIT p_per_page
        OFFSET (p_page - 1) * p_per_page
    ) sub
    -- We need to re-join to get om and p separately for the JSON building
    INNER JOIN public.organization_members om ON om.organization_id = sub.organization_id AND om.user_id = sub.user_id
    INNER JOIN public.profiles p ON p.id = sub.user_id;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_list_organization_members(UUID, INTEGER, INTEGER, TEXT, TEXT, BOOLEAN) IS 
'Lista los miembros de una organización con paginación y filtros. 
Los super_admin pueden ver todos los miembros. 
Otros usuarios solo pueden ver miembros si son parte de la organización.
Incluye información de workspaces y estadísticas de cada miembro.';
