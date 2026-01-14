-- ============================================================================
-- fn_list_permissions - Lista todos los permisos disponibles
-- Retorna un JSON array plano, fácil de consumir
-- ============================================================================

DROP FUNCTION IF EXISTS public.fn_list_permissions();

CREATE OR REPLACE FUNCTION public.fn_list_permissions()
RETURNS JSON
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT COALESCE(
        json_agg(
            json_build_object(
                'id', p.id,
                'key', p.key,
                'code', p.key,  -- alias para compatibilidad con la API
                'description', p.description,
                'category', p.category
            ) ORDER BY p.category, p.key
        ),
        '[]'::json
    )
    FROM public.permissions p;
$$;

COMMENT ON FUNCTION public.fn_list_permissions() IS 
'Lista todos los permisos disponibles en el sistema. Retorna un JSON array plano con id, key, code (alias de key), description y category. No requiere parámetros.';
