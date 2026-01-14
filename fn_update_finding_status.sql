-- Función para actualizar el estatus de un finding y crear registro en finding_status_history
-- Retorna el ID del cambio de estatus para poder relacionar evidencias después
DROP FUNCTION IF EXISTS public.fn_update_finding_status(UUID, TEXT, TEXT, UUID[]) CASCADE;

CREATE OR REPLACE FUNCTION public.fn_update_finding_status(
    p_finding_id UUID,
    p_status TEXT,  -- Nuevo estatus (debe ser válido según el ENUM finding_status)
    p_comment TEXT DEFAULT NULL,
    p_evidence_ids UUID[] DEFAULT ARRAY[]::UUID[]  -- IDs de evidencias existentes (opcional, para validación)
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_workspace_id UUID;
    v_old_status TEXT;
    v_new_status TEXT;
    v_status_change_id UUID;
    v_result JSON;
    v_has_evidence BOOLEAN;
BEGIN
    -- Obtener workspace_id y estatus actual del finding
    SELECT workspace_id, status INTO v_workspace_id, v_old_status
    FROM public.findings
    WHERE id = p_finding_id;
    
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'Finding no encontrado';
    END IF;
    
    -- Verificar permisos (super_admin o miembro de la organización del workspace)
    IF NOT public.fn_is_super_admin() AND NOT EXISTS (
        SELECT 1 FROM public.organization_members om
        JOIN public.workspaces w ON w.organization_id = om.organization_id
        WHERE om.user_id = auth.uid()
        AND om.is_active = true
        AND w.id = v_workspace_id
    ) THEN
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para cambiar el estatus de este finding';
    END IF;
    
    -- Validar que el nuevo estatus sea válido
    v_new_status := p_status::finding_status;  -- Esto validará que sea un valor válido del ENUM
    
    -- Validaciones según el nuevo estatus
    IF v_new_status IN ('Mitigated', 'Accepted Risk', 'False Positive', 'Not Observed') THEN
        -- Requiere comentario
        IF p_comment IS NULL OR LENGTH(TRIM(p_comment)) < 10 THEN
            RAISE EXCEPTION 'Comentario obligatorio (mínimo 10 caracteres) para cambiar el estatus a %', v_new_status;
        END IF;
        
        -- Para Mitigated, verificar que haya evidencias (si se proporcionan IDs)
        IF v_new_status = 'Mitigated' AND array_length(p_evidence_ids, 1) IS NULL THEN
            -- Verificar si hay evidencias relacionadas con el finding
            SELECT EXISTS(
                SELECT 1 FROM public.finding_evidence fe
                WHERE fe.finding_id = p_finding_id
                AND fe.is_active = true
            ) INTO v_has_evidence;
            
            IF NOT v_has_evidence THEN
                RAISE EXCEPTION 'Evidencia obligatoria para cambiar el estatus a Mitigated';
            END IF;
        END IF;
    END IF;
    
    -- Si el estatus no cambió, no hacer nada
    IF v_old_status = v_new_status THEN
        RAISE EXCEPTION 'El finding ya tiene el estatus %', v_new_status;
    END IF;
    
    -- Crear registro en finding_status_history ANTES de actualizar el finding
    INSERT INTO public.finding_status_history (
        workspace_id,
        finding_id,
        from_status,
        to_status,
        comment,
        changed_by
    )
    VALUES (
        v_workspace_id,
        p_finding_id,
        v_old_status::finding_status,
        v_new_status::finding_status,
        p_comment,
        auth.uid()
    )
    RETURNING id INTO v_status_change_id;
    
    -- Actualizar el estatus del finding
    UPDATE public.findings
    SET status = v_new_status::finding_status,
        updated_at = now()
    WHERE id = p_finding_id;
    
    -- Si el nuevo estatus es Mitigated, calcular time_to_mitigate
    -- time_to_mitigate es de tipo INTERVAL, así que usamos directamente la diferencia de timestamps
    IF v_new_status = 'Mitigated' THEN
        UPDATE public.findings
        SET time_to_mitigate = now() - first_seen  -- INTERVAL: diferencia entre timestamps
        WHERE id = p_finding_id;
    END IF;
    
    -- Construir respuesta con el ID del cambio de estatus
    SELECT json_build_object(
        'finding_id', p_finding_id,
        'from_status', v_old_status,
        'to_status', v_new_status,
        'status_change_id', v_status_change_id,  -- IMPORTANTE: Para relacionar evidencias después
        'comment', p_comment,
        'changed_by', auth.uid(),
        'changed_at', now()
    ) INTO v_result;
    
    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.fn_update_finding_status(UUID, TEXT, TEXT, UUID[]) IS 
'Actualiza el estatus de un finding y crea un registro en finding_status_history. Retorna el status_change_id para poder relacionar evidencias después. Validaciones: Mitigated requiere evidencia, otros estatus cerrados requieren comentario. Requiere permisos de super_admin o ser miembro de la organización del workspace.';

