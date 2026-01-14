-- Función para eliminar un archivo específico del array JSONB files de una evidencia
-- Elimina el archivo del array pero mantiene el registro si hay otros archivos
DROP FUNCTION IF EXISTS public.fn_remove_evidence_file(UUID, TEXT) CASCADE;

CREATE OR REPLACE FUNCTION public.fn_remove_evidence_file(
    p_evidence_id UUID,
    p_file_hash TEXT  -- Hash del archivo a eliminar del array files
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_result JSON;
    v_workspace_id UUID;
    v_files JSONB;
    v_new_files JSONB := '[]'::JSONB;
    v_file JSONB;
    v_file_found BOOLEAN := false;
BEGIN
    -- Obtener el registro de evidencia y verificar permisos
    SELECT fe.workspace_id, fe.files INTO v_workspace_id, v_files
    FROM public.finding_evidence fe
    WHERE fe.id = p_evidence_id
    AND fe.is_active = true;
    
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Evidencia no encontrada';
    END IF;
    
    -- Verificar permisos (super_admin o el usuario que subió la evidencia)
    IF NOT public.fn_is_super_admin() AND NOT EXISTS (
        SELECT 1 FROM public.finding_evidence fe
        WHERE fe.id = p_evidence_id
        AND fe.uploaded_by = auth.uid()
        AND fe.is_active = true
    ) THEN
        RAISE EXCEPTION 'Acceso denegado: solo puedes eliminar archivos de tus propias evidencias';
    END IF;
    
    -- Filtrar el archivo del array (mantener todos excepto el que tiene el hash)
    FOR v_file IN SELECT * FROM jsonb_array_elements(v_files)
    LOOP
        IF v_file->>'file_hash' = p_file_hash THEN
            v_file_found := true;
            -- No agregar este archivo al nuevo array (lo eliminamos)
        ELSE
            -- Agregar este archivo al nuevo array
            v_new_files := v_new_files || jsonb_build_array(v_file);
        END IF;
    END LOOP;
    
    IF NOT v_file_found THEN
        RAISE EXCEPTION 'Archivo no encontrado en la evidencia';
    END IF;
    
    -- Verificar que quede al menos un archivo (constraint)
    IF jsonb_array_length(v_new_files) = 0 THEN
        RAISE EXCEPTION 'No se puede eliminar el último archivo. Elimina la evidencia completa en su lugar.';
    END IF;
    
    -- Actualizar el registro con el nuevo array sin el archivo eliminado
    UPDATE public.finding_evidence
    SET files = v_new_files,
        updated_at = now()
    WHERE id = p_evidence_id
    AND is_active = true;
    
    -- Retornar resultado
    SELECT json_build_object(
        'evidence_id', p_evidence_id,
        'file_hash', p_file_hash,
        'remaining_files', jsonb_array_length(v_new_files),
        'removed', true
    ) INTO v_result;
    
    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.fn_remove_evidence_file(UUID, TEXT) IS 
'Elimina un archivo específico del array JSONB files de una evidencia. Mantiene el registro si hay otros archivos. Solo el usuario que subió la evidencia o super_admin puede eliminar archivos.';

