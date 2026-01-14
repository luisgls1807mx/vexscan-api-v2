-- ============================================================================
-- fn_create_scan_import.sql
-- Crea un registro de importación de scan (con soporte para force_upload)
-- ============================================================================

-- Eliminar funciones existentes
DROP FUNCTION IF EXISTS public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, BOOLEAN);

-- Crear función con soporte para force_upload
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
    SELECT w.id INTO v_workspace_id
    FROM public.projects p
    JOIN public.workspaces w ON w.organization_id = p.organization_id
    WHERE p.id = p_project_id
    LIMIT 1;

    -- Verificar que se encontró el workspace
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Proyecto no encontrado o sin workspace asociado';
    END IF;

    -- Verificar permisos (miembro de la organización puede subir scans)
    -- Removida restricción de super_admin para permitir a usuarios normales
    
    -- Verificar si ya existe un scan con el mismo hash (solo si force_upload = false)
    IF NOT p_force_upload THEN
        IF EXISTS (SELECT 1 FROM public.scan_imports WHERE workspace_id = v_workspace_id AND file_hash = p_file_hash) THEN
            RAISE EXCEPTION 'Ya existe un scan con el mismo contenido (hash: %)', p_file_hash;
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

-- Comentario de la función
COMMENT ON FUNCTION public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, BOOLEAN) IS 
'Crea un registro de importación de scan. Si p_force_upload=true, permite subir archivos duplicados.';

-- Permisos
GRANT EXECUTE ON FUNCTION public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, BOOLEAN) TO authenticated;
GRANT EXECUTE ON FUNCTION public.fn_create_scan_import(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, BOOLEAN) TO service_role;
