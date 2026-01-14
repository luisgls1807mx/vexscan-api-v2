-- ============================================================================
-- migration_add_workspace_to_projects.sql
-- Migración para añadir workspace_id a projects y cambiar verificación de duplicados
-- ============================================================================

-- ============================================================================
-- PASO 1: Añadir columna workspace_id a la tabla projects (permite NULL)
-- ============================================================================

-- Añadir columna workspace_id (NULL permitido para datos existentes)
ALTER TABLE public.projects 
ADD COLUMN IF NOT EXISTS workspace_id UUID NULL;

-- Añadir foreign key
ALTER TABLE public.projects 
DROP CONSTRAINT IF EXISTS projects_workspace_id_fkey;

ALTER TABLE public.projects 
ADD CONSTRAINT projects_workspace_id_fkey 
FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;

-- Crear índice para mejor performance
CREATE INDEX IF NOT EXISTS idx_projects_workspace 
ON public.projects(workspace_id);

-- Crear índice compuesto para workspace + nombre único
CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_workspace_name_unique 
ON public.projects(workspace_id, name) 
WHERE workspace_id IS NOT NULL;

-- ============================================================================
-- PASO 2: (OPCIONAL) Actualizar proyectos existentes con el workspace default
-- Ejecutar solo si quieres asignar los proyectos existentes a un workspace
-- ============================================================================

-- UPDATE public.projects p
-- SET workspace_id = (
--     SELECT w.id 
--     FROM public.workspaces w 
--     WHERE w.organization_id = p.organization_id 
--     ORDER BY w.created_at ASC 
--     LIMIT 1
-- )
-- WHERE p.workspace_id IS NULL;

-- ============================================================================
-- PASO 3: Actualizar verificación de duplicados en scan_imports
-- Ahora verifica por project_id + file_hash en lugar de workspace_id + file_hash
-- ============================================================================

-- Crear índice para la nueva verificación de duplicados
CREATE INDEX IF NOT EXISTS idx_scan_imports_project_hash 
ON public.scan_imports(project_id, file_hash);

-- ============================================================================
-- PASO 4: Actualizar función fn_create_scan_import
-- ============================================================================

DROP FUNCTION IF EXISTS public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, BOOLEAN);

CREATE OR REPLACE FUNCTION public.fn_create_scan_import(
    p_project_id UUID,
    p_file_name TEXT,
    p_storage_path TEXT,
    p_file_size BIGINT,
    p_file_hash TEXT,
    p_scanner TEXT,
    p_network_zone TEXT,
    p_force_upload BOOLEAN DEFAULT FALSE
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_scan_id UUID;
    v_workspace_id UUID;
    v_result JSON;
BEGIN
    -- Obtener workspace_id del proyecto
    SELECT p.workspace_id INTO v_workspace_id
    FROM public.projects p
    WHERE p.id = p_project_id;

    -- Si el proyecto no tiene workspace asignado, obtener el default de la organización
    IF v_workspace_id IS NULL THEN
        SELECT w.id INTO v_workspace_id
        FROM public.projects p
        JOIN public.workspaces w ON w.organization_id = p.organization_id
        WHERE p.id = p_project_id
        ORDER BY w.created_at ASC
        LIMIT 1;
    END IF;

    -- Verificar que se encontró el workspace
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Proyecto no encontrado o sin workspace asociado';
    END IF;

    -- Verificar si ya existe un scan con el mismo hash EN EL MISMO PROYECTO
    -- (Cambio: antes era por workspace, ahora es por project)
    IF NOT p_force_upload THEN
        IF EXISTS (
            SELECT 1 FROM public.scan_imports 
            WHERE project_id = p_project_id 
            AND file_hash = p_file_hash
        ) THEN
            RAISE EXCEPTION 'Ya existe un scan con el mismo contenido en este proyecto (hash: %)', p_file_hash;
        END IF;
    END IF;

    -- Crear registro del scan
    INSERT INTO public.scan_imports (
        workspace_id, project_id, file_name, storage_path, file_size,
        file_hash, scanner, network_zone, uploaded_by, status
    )
    VALUES (
        v_workspace_id, 
        p_project_id, 
        p_file_name, 
        p_storage_path, 
        p_file_size,
        p_file_hash,
        p_scanner,
        p_network_zone::network_zone,
        auth.uid(), 
        'queued'
    )
    RETURNING id INTO v_scan_id;

    -- Retornar resultado
    SELECT json_build_object(
        'id', si.id,
        'file_name', si.file_name,
        'scanner', si.scanner,
        'network_zone', si.network_zone::TEXT,
        'status', si.status,
        'workspace_id', si.workspace_id,
        'project_id', si.project_id,
        'created_at', si.created_at
    ) INTO v_result
    FROM public.scan_imports si
    WHERE si.id = v_scan_id;

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, BOOLEAN) IS 
'Crea un registro de scan. La verificación de duplicados ahora es por PROYECTO (no por workspace). Si p_force_upload=true, permite subir archivos duplicados.';

GRANT EXECUTE ON FUNCTION public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, BOOLEAN) TO authenticated;
GRANT EXECUTE ON FUNCTION public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, BOOLEAN) TO service_role;

-- ============================================================================
-- PASO 5: Actualizar función fn_list_projects para incluir workspace_id
-- ============================================================================

DROP FUNCTION IF EXISTS public.fn_list_projects(UUID, INTEGER, INTEGER, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.fn_list_projects(UUID, UUID, INTEGER, INTEGER, TEXT, TEXT);

CREATE OR REPLACE FUNCTION public.fn_list_projects(
    p_org_id UUID,
    p_workspace_id UUID DEFAULT NULL,  -- Nuevo parámetro opcional
    p_page INTEGER DEFAULT 1,
    p_per_page INTEGER DEFAULT 20,
    p_status TEXT DEFAULT NULL,
    p_search TEXT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total INTEGER;
    v_result JSON;
BEGIN
    -- Contar total de proyectos
    SELECT COUNT(*) INTO v_total
    FROM public.projects p
    WHERE p.organization_id = p_org_id
    AND (p_workspace_id IS NULL OR p.workspace_id = p_workspace_id)
    AND (p_status IS NULL OR p.status = p_status)
    AND (p_search IS NULL OR p.name ILIKE '%' || p_search || '%');

    -- Obtener proyectos con paginación
    SELECT json_build_object(
        'data', COALESCE(
            json_agg(
                json_build_object(
                    'id', p.id,
                    'name', p.name,
                    'slug', p.slug,
                    'description', p.description,
                    'color', p.color,
                    'status', p.status,
                    'organization_id', p.organization_id,
                    'workspace_id', p.workspace_id,
                    'leader', json_build_object(
                        'id', leader.id,
                        'full_name', leader.full_name
                    ),
                    'responsible', CASE 
                        WHEN resp.id IS NOT NULL THEN json_build_object(
                            'id', resp.id,
                            'full_name', resp.full_name
                        )
                        ELSE NULL
                    END,
                    'stats', json_build_object(
                        'findings_total', COALESCE(
                            (SELECT COUNT(*) FROM public.findings f WHERE f.project_id = p.id),
                            0
                        ),
                        'findings_open', COALESCE(
                            (SELECT COUNT(*) FROM public.findings f WHERE f.project_id = p.id AND f.status = 'Open'),
                            0
                        ),
                        'assets_count', COALESCE(
                            (SELECT COUNT(*) FROM public.assets a WHERE a.project_id = p.id),
                            0
                        )
                    ),
                    'created_at', p.created_at,
                    'updated_at', p.updated_at
                ) ORDER BY p.created_at DESC
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
        SELECT p.*
        FROM public.projects p
        WHERE p.organization_id = p_org_id
        AND (p_workspace_id IS NULL OR p.workspace_id = p_workspace_id)
        AND (p_status IS NULL OR p.status = p_status)
        AND (p_search IS NULL OR p.name ILIKE '%' || p_search || '%')
        ORDER BY p.created_at DESC
        LIMIT p_per_page
        OFFSET (p_page - 1) * p_per_page
    ) sub
    INNER JOIN public.projects p ON p.id = sub.id
    LEFT JOIN public.profiles leader ON leader.id = p.leader_id
    LEFT JOIN public.profiles resp ON resp.id = p.responsible_id;

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.fn_list_projects(UUID, UUID, INTEGER, INTEGER, TEXT, TEXT) IS 
'Lista proyectos de una organización. Opcionalmente filtra por workspace_id.';

GRANT EXECUTE ON FUNCTION public.fn_list_projects(UUID, UUID, INTEGER, INTEGER, TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.fn_list_projects(UUID, UUID, INTEGER, INTEGER, TEXT, TEXT) TO service_role;

-- ============================================================================
-- PASO 6: Actualizar fn_create_project para asignar workspace_id
-- ============================================================================

DROP FUNCTION IF EXISTS public.fn_create_project(UUID, TEXT, TEXT, TEXT, UUID, UUID);
DROP FUNCTION IF EXISTS public.fn_create_project(UUID, UUID, TEXT, TEXT, TEXT, UUID, UUID);

CREATE OR REPLACE FUNCTION public.fn_create_project(
    p_org_id UUID,
    p_workspace_id UUID DEFAULT NULL,  -- Nuevo parámetro
    p_name TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_color TEXT DEFAULT '#3b82f6',
    p_leader_id UUID DEFAULT NULL,
    p_responsible_id UUID DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_project_id UUID;
    v_workspace_id UUID;
    v_leader_id UUID;
    v_result JSON;
BEGIN
    -- Validar nombre
    IF p_name IS NULL OR p_name = '' THEN
        RAISE EXCEPTION 'El nombre del proyecto es requerido';
    END IF;

    -- Si no se proporciona workspace_id, usar el default de la organización
    IF p_workspace_id IS NULL THEN
        SELECT w.id INTO v_workspace_id
        FROM public.workspaces w
        WHERE w.organization_id = p_org_id
        ORDER BY w.created_at ASC
        LIMIT 1;
    ELSE
        v_workspace_id := p_workspace_id;
    END IF;

    -- Si no hay leader_id, usar el usuario actual
    v_leader_id := COALESCE(p_leader_id, auth.uid());

    -- Crear proyecto
    INSERT INTO public.projects (
        organization_id, workspace_id, name, slug, description, color, 
        leader_id, responsible_id, created_by
    )
    VALUES (
        p_org_id,
        v_workspace_id,
        p_name,
        public.fn_generate_slug(p_name),
        p_description,
        p_color,
        v_leader_id,
        p_responsible_id,
        auth.uid()
    )
    RETURNING id INTO v_project_id;

    -- Retornar resultado
    SELECT json_build_object(
        'id', p.id,
        'name', p.name,
        'slug', p.slug,
        'description', p.description,
        'color', p.color,
        'status', p.status,
        'organization_id', p.organization_id,
        'workspace_id', p.workspace_id,
        'leader', json_build_object(
            'id', leader.id,
            'full_name', leader.full_name
        ),
        'responsible', CASE 
            WHEN resp.id IS NOT NULL THEN json_build_object(
                'id', resp.id,
                'full_name', resp.full_name
            )
            ELSE NULL
        END,
        'created_at', p.created_at,
        'updated_at', p.updated_at
    ) INTO v_result
    FROM public.projects p
    LEFT JOIN public.profiles leader ON leader.id = p.leader_id
    LEFT JOIN public.profiles resp ON resp.id = p.responsible_id
    WHERE p.id = v_project_id;

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.fn_create_project(UUID, UUID, TEXT, TEXT, TEXT, UUID, UUID) IS 
'Crea un nuevo proyecto en una organización y workspace.';

GRANT EXECUTE ON FUNCTION public.fn_create_project(UUID, UUID, TEXT, TEXT, TEXT, UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.fn_create_project(UUID, UUID, TEXT, TEXT, TEXT, UUID, UUID) TO service_role;

-- ============================================================================
-- RESUMEN DE CAMBIOS
-- ============================================================================
-- 1. Añadida columna workspace_id a projects (NULL permitido)
-- 2. Cambiada verificación de duplicados de scans: workspace_id → project_id
-- 3. fn_list_projects ahora acepta workspace_id opcional para filtrar
-- 4. fn_create_project ahora acepta workspace_id
-- 5. Índices creados para mejor performance
