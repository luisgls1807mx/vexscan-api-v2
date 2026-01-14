-- Eliminar función existente si existe (todas las posibles sobrecargas)
DROP FUNCTION IF EXISTS public.fn_create_finding_evidence(UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.fn_create_finding_evidence(UUID, JSONB, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.fn_create_finding_evidence(UUID, JSONB, TEXT, TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.fn_create_finding_evidence(UUID, JSONB, TEXT, TEXT, TEXT, UUID) CASCADE;
DROP FUNCTION IF EXISTS public.fn_create_finding_evidence(UUID, JSONB, TEXT, TEXT, JSONB, UUID) CASCADE;
DROP FUNCTION IF EXISTS public.fn_create_finding_evidence_batch(UUID, JSONB) CASCADE;

-- Crear función optimizada para crear evidencia (uno o múltiples archivos)
-- Un solo registro con todos los archivos en el campo JSONB files
CREATE OR REPLACE FUNCTION public.fn_create_finding_evidence(
    p_finding_id UUID,
    p_files JSONB,  -- Array de archivos: [{"file_name": "...", "file_path": "...", "file_size": 123, ...}, ...]
    p_description TEXT DEFAULT NULL,
    p_comments TEXT DEFAULT NULL,
    p_tags JSONB DEFAULT NULL,  -- Array de tags: ["mitigation", "verification", "testing", ...]
    p_related_status_change_id UUID DEFAULT NULL  -- ID del cambio de estatus relacionado (opcional)
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_evidence_id UUID;
    v_workspace_id UUID;
    v_result JSON;
    v_file JSONB;
    v_tag JSONB;
BEGIN
    -- Obtener workspace_id del finding
    SELECT workspace_id INTO v_workspace_id
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
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para agregar evidencias a este finding';
    END IF;
    
    -- Validar que p_files sea un array y tenga al menos un archivo
    IF jsonb_typeof(p_files) != 'array' THEN
        RAISE EXCEPTION 'p_files debe ser un array JSON';
    END IF;
    
    IF jsonb_array_length(p_files) = 0 THEN
        RAISE EXCEPTION 'Debe haber al menos un archivo';
    END IF;
    
    -- Validar que cada archivo tenga los campos requeridos
    FOR v_file IN SELECT * FROM jsonb_array_elements(p_files)
    LOOP
        IF NOT (v_file ? 'file_name' AND v_file ? 'file_path' AND v_file ? 'file_size') THEN
            RAISE EXCEPTION 'Cada archivo debe tener file_name, file_path y file_size';
        END IF;
    END LOOP;
    
    -- Validar que el cambio de estatus existe y pertenece al mismo finding (si se proporciona)
    IF p_related_status_change_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.finding_status_history fsh
            WHERE fsh.id = p_related_status_change_id
            AND fsh.finding_id = p_finding_id
        ) THEN
            RAISE EXCEPTION 'El cambio de estatus especificado no existe o no pertenece a este finding';
        END IF;
    END IF;
    
    -- Validar que p_tags sea un array JSONB (si se proporciona)
    IF p_tags IS NOT NULL THEN
        IF jsonb_typeof(p_tags) != 'array' THEN
            RAISE EXCEPTION 'p_tags debe ser un array JSON';
        END IF;
        
        -- Validar que cada tag tenga la estructura correcta: {tag: string, color: string}
        FOR v_tag IN SELECT * FROM jsonb_array_elements(p_tags)
        LOOP
            IF NOT (v_tag ? 'tag' AND v_tag ? 'color') THEN
                RAISE EXCEPTION 'Cada tag debe tener "tag" y "color" (ej: {"tag": "mitigation", "color": "#FF5733"})';
            END IF;
            
            -- Validar que tag sea string y no esté vacío
            IF jsonb_typeof(v_tag->'tag') != 'string' OR LENGTH(TRIM(v_tag->>'tag')) = 0 THEN
                RAISE EXCEPTION 'El campo "tag" debe ser un string no vacío';
            END IF;
            
            -- Validar que color sea string (formato hex: #RRGGBB o #RRGGBBAA)
            IF jsonb_typeof(v_tag->'color') != 'string' OR NOT (v_tag->>'color' ~ '^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$') THEN
                RAISE EXCEPTION 'El campo "color" debe ser un string en formato hexadecimal (ej: "#FF5733" o "#FF5733FF")';
            END IF;
        END LOOP;
    END IF;
    
    -- Crear UN SOLO registro con todos los archivos en el campo files (JSONB)
    INSERT INTO public.finding_evidence (
        finding_id,
        workspace_id,
        files,
        description,
        comments,
        tags,
        related_status_change_id,
        uploaded_by
    )
    VALUES (
        p_finding_id,
        v_workspace_id,
        p_files,  -- Array completo de archivos
        p_description,
        p_comments,
        COALESCE(p_tags, '[]'::jsonb),  -- Array de tags, por defecto vacío
        p_related_status_change_id,  -- Puede ser NULL
        auth.uid()
    )
    RETURNING id INTO v_evidence_id;
    
    -- Retornar resultado
    SELECT json_build_object(
        'id', fe.id,
        'finding_id', fe.finding_id,
        'files', fe.files,
        'file_count', jsonb_array_length(fe.files),
        'description', fe.description,
        'comments', fe.comments,
        'tags', COALESCE(fe.tags, '[]'::jsonb),
        'related_status_change_id', fe.related_status_change_id,
        'uploaded_by', fe.uploaded_by,
        'created_at', fe.created_at
    ) INTO v_result
    FROM public.finding_evidence fe
    WHERE fe.id = v_evidence_id;
    
    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_create_finding_evidence(UUID, JSONB, TEXT, TEXT, JSONB, UUID) IS 
'Crea un registro de evidencia para un finding. Parámetros: p_finding_id, p_files (JSONB array), p_description, p_comments, p_tags (JSONB array opcional), p_related_status_change_id (opcional). Puede contener uno o múltiples archivos en el campo JSONB files. Múltiples usuarios pueden crear evidencias para el mismo finding o para el mismo cambio de estatus. Requiere permisos de super_admin o ser miembro de la organización del workspace.';

