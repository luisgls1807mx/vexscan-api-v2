-- Función para obtener información de un archivo específico dentro de una evidencia
-- Busca el archivo por su file_hash dentro del array JSONB files
DROP FUNCTION IF EXISTS public.fn_get_evidence_file(UUID, TEXT) CASCADE;

CREATE OR REPLACE FUNCTION public.fn_get_evidence_file(
    p_evidence_id UUID,
    p_file_hash TEXT  -- Hash del archivo a buscar dentro del array files
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_result JSON;
    v_workspace_id UUID;
    v_file JSONB;
    v_files JSONB;
BEGIN
    -- Obtener el registro de evidencia y verificar permisos
    SELECT fe.workspace_id, fe.files INTO v_workspace_id, v_files
    FROM public.finding_evidence fe
    WHERE fe.id = p_evidence_id
    AND fe.is_active = true;
    
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Evidencia no encontrada';
    END IF;
    
    -- Verificar permisos (super_admin o miembro de la organización del workspace)
    IF NOT public.fn_is_super_admin() AND NOT EXISTS (
        SELECT 1 FROM public.organization_members om
        JOIN public.workspaces w ON w.organization_id = om.organization_id
        WHERE om.user_id = auth.uid()
        AND om.is_active = true
        AND w.id = v_workspace_id
    ) THEN
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para ver esta evidencia';
    END IF;
    
    -- Buscar el archivo por file_hash dentro del array JSONB files
    FOR v_file IN SELECT * FROM jsonb_array_elements(v_files)
    LOOP
        IF v_file->>'file_hash' = p_file_hash THEN
            -- Archivo encontrado, construir respuesta
            SELECT json_build_object(
                'file_name', v_file->>'file_name',
                'file_path', v_file->>'file_path',
                'file_size', (v_file->>'file_size')::BIGINT,
                'file_type', v_file->>'file_type',
                'file_hash', v_file->>'file_hash',
                'evidence_id', p_evidence_id,
                'workspace_id', v_workspace_id
            ) INTO v_result;
            
            RETURN v_result;
        END IF;
    END LOOP;
    
    -- Si llegamos aquí, el archivo no se encontró
    RAISE EXCEPTION 'Archivo no encontrado en la evidencia';
END;
$$;

COMMENT ON FUNCTION public.fn_get_evidence_file(UUID, TEXT) IS 
'Busca un archivo específico dentro de una evidencia usando su file_hash. Retorna la información del archivo para descarga. Requiere permisos de super_admin o ser miembro de la organización del workspace.';

