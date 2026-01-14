-- Eliminar función existente si existe
DROP FUNCTION IF EXISTS public.fn_create_finding_evidence_batch(UUID, JSONB) CASCADE;

-- Crear función para crear múltiples evidencias de un finding en una sola llamada
-- Recibe un array JSON con los datos de cada archivo
CREATE OR REPLACE FUNCTION public.fn_create_finding_evidence_batch(
    p_finding_id UUID,
    p_files JSONB  -- Array de objetos: [{"file_name": "...", "file_path": "...", "file_size": 123, ...}, ...]
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_workspace_id UUID;
    v_file JSONB;
    v_evidence_id UUID;
    v_evidence_ids UUID[] := ARRAY[]::UUID[];
    v_result JSONB := '[]'::JSONB;
    v_file_result JSONB;
    v_batch_id UUID := gen_random_uuid(); -- Generar batch_id único para agrupar todos los archivos
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
    
    -- Validar que p_files sea un array
    IF jsonb_typeof(p_files) != 'array' THEN
        RAISE EXCEPTION 'p_files debe ser un array JSON';
    END IF;
    
    -- Procesar cada archivo del array
    FOR v_file IN SELECT * FROM jsonb_array_elements(p_files)
    LOOP
        -- Validar campos requeridos
        IF NOT (v_file ? 'file_name' AND v_file ? 'file_path' AND v_file ? 'file_size') THEN
            RAISE EXCEPTION 'Cada archivo debe tener file_name, file_path y file_size';
        END IF;
        
        -- Crear registro de evidencia
        -- Todos los archivos del batch comparten el mismo batch_id, description y comments
        INSERT INTO public.finding_evidence (
            finding_id,
            workspace_id,
            file_name,
            file_path,
            file_size,
            file_type,
            file_hash,
            description,
            comments,
            batch_id,
            uploaded_by
        )
        VALUES (
            p_finding_id,
            v_workspace_id,
            v_file->>'file_name',
            v_file->>'file_path',
            (v_file->>'file_size')::BIGINT,
            v_file->>'file_type',
            v_file->>'file_hash',
            v_file->>'description',  -- Description compartida para todos los archivos del batch
            v_file->>'comments',      -- Comments compartidos para todos los archivos del batch
            v_batch_id,               -- Mismo batch_id para todos los archivos
            auth.uid()
        )
        RETURNING id INTO v_evidence_id;
        
        -- Agregar ID a la lista
        v_evidence_ids := array_append(v_evidence_ids, v_evidence_id);
        
        -- Construir resultado para este archivo
        v_file_result := jsonb_build_object(
            'id', v_evidence_id,
            'finding_id', p_finding_id,
            'file_name', v_file->>'file_name',
            'file_path', v_file->>'file_path',
            'file_size', (v_file->>'file_size')::BIGINT,
            'file_type', v_file->>'file_type',
            'description', v_file->>'description',
            'comments', v_file->>'comments',
            'uploaded_by', auth.uid(),
            'created_at', now()
        );
        
        -- Agregar al resultado
        v_result := v_result || jsonb_build_array(v_file_result);
    END LOOP;
    
    -- Retornar resultado con todos los archivos creados
    RETURN jsonb_build_object(
        'success', true,
        'batch_id', v_batch_id,  -- ID del batch para agrupar estos archivos
        'count', jsonb_array_length(p_files),
        'description', (p_files->0->>'description'),  -- Description compartida
        'comments', (p_files->0->>'comments'),        -- Comments compartidos
        'evidence_ids', v_evidence_ids,
        'files', v_result
    )::JSON;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_create_finding_evidence_batch(UUID, JSONB) IS 
'Crea múltiples evidencias para un finding en una sola llamada. Recibe un array JSON con los datos de cada archivo. Requiere permisos de super_admin o ser miembro de la organización del workspace.';

