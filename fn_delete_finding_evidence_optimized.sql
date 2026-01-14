-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_delete_finding_evidence(UUID) CASCADE;

-- Crear función optimizada para eliminar (soft delete) evidencia de un finding
-- Elimina el registro completo (que puede contener múltiples archivos)
CREATE OR REPLACE FUNCTION public.fn_delete_finding_evidence(
    p_evidence_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_result JSON;
    v_files JSONB;
    v_file JSONB;
BEGIN
    -- Verificar permisos (super_admin o el usuario que subió la evidencia)
    IF NOT public.fn_is_super_admin() AND NOT EXISTS (
        SELECT 1 FROM public.finding_evidence fe
        WHERE fe.id = p_evidence_id
        AND fe.uploaded_by = auth.uid()
        AND fe.is_active = true
    ) THEN
        RAISE EXCEPTION 'Acceso denegado: solo puedes eliminar tus propias evidencias';
    END IF;
    
    -- Obtener los archivos antes de eliminar para poder borrarlos del storage
    SELECT files INTO v_files
    FROM public.finding_evidence
    WHERE id = p_evidence_id
    AND is_active = true;
    
    IF v_files IS NULL THEN
        RAISE EXCEPTION 'Evidencia no encontrada o ya eliminada';
    END IF;
    
    -- Soft delete (marcar como inactivo)
    UPDATE public.finding_evidence
    SET is_active = false,
        updated_at = now()
    WHERE id = p_evidence_id
    AND is_active = true;
    
    -- Retornar información de los archivos que se eliminaron (para que el backend pueda limpiar storage si es necesario)
    RETURN json_build_object(
        'id', p_evidence_id,
        'deleted', true,
        'files_count', jsonb_array_length(v_files),
        'files', v_files  -- Array de archivos eliminados
    );
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_delete_finding_evidence(UUID) IS 
'Elimina (soft delete) una evidencia. Elimina el registro completo que puede contener múltiples archivos. Solo el usuario que la subió o un super_admin puede eliminarla.';

