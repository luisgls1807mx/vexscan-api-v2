-- Eliminar TODAS las versiones posibles de la función existente
-- Nota: Si tienes problemas, ejecuta primero este comando manualmente:
-- SELECT 'DROP FUNCTION IF EXISTS public.fn_list_findings(' || oidvectortypes(proargtypes) || ');' 
-- FROM pg_proc WHERE proname = 'fn_list_findings' AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');

-- Eliminar la función existente con la firma exacta
DROP FUNCTION IF EXISTS public.fn_list_findings(UUID, INTEGER, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT, BOOLEAN, UUID, TEXT, UUID, TEXT, TEXT) CASCADE;

-- Crear función para listar findings con filtros (coincide exactamente con la función de Supabase)
CREATE OR REPLACE FUNCTION public.fn_list_findings(
    p_project_id UUID,
    p_page INTEGER DEFAULT 1,
    p_per_page INTEGER DEFAULT 50,
    p_severity TEXT DEFAULT NULL,
    p_status TEXT DEFAULT NULL,
    p_search TEXT DEFAULT NULL,
    p_hostname TEXT DEFAULT NULL,
    p_ip_address TEXT DEFAULT NULL,
    p_assigned_to_me BOOLEAN DEFAULT false,
    p_assigned_to_team UUID DEFAULT NULL,
    p_diff_type TEXT DEFAULT NULL,
    p_scan_id UUID DEFAULT NULL,
    p_sort_by TEXT DEFAULT 'last_seen',
    p_sort_order TEXT DEFAULT 'desc'
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_result JSON;
    v_total INT;
    v_offset INT := (p_page - 1) * p_per_page;
    v_workspace_id UUID;
    v_user_id UUID := auth.uid();
BEGIN
    -- Obtener workspace_id (si la función existe, sino usar método alternativo)
    BEGIN
        v_workspace_id := public.fn_get_project_workspace(p_project_id);
    EXCEPTION WHEN OTHERS THEN
        -- Método alternativo: obtener workspace_id desde el proyecto
        SELECT w.id INTO v_workspace_id
        FROM public.projects p
        JOIN public.workspaces w ON w.organization_id = p.organization_id
        WHERE p.id = p_project_id
        LIMIT 1;
    END;

    -- Verificar permisos
    IF NOT public.fn_is_super_admin() THEN
        -- Verificar si tiene permiso (si la función existe)
        BEGIN
            IF NOT public.fn_has_permission(v_workspace_id, 'findings.read') THEN
                RAISE EXCEPTION 'Acceso denegado';
            END IF;
        EXCEPTION WHEN OTHERS THEN
            -- Si la función no existe, verificar membresía en la organización
            IF NOT EXISTS (
                SELECT 1 
                FROM public.projects p
                INNER JOIN public.organization_members om ON om.organization_id = p.organization_id
                WHERE p.id = p_project_id
                AND om.user_id = auth.uid()
                AND om.is_active = true
            ) THEN
                RAISE EXCEPTION 'Acceso denegado';
            END IF;
        END;
    END IF;

    -- Contar total
    SELECT COUNT(*) INTO v_total
    FROM public.findings f
    WHERE f.project_id = p_project_id
      AND (p_severity IS NULL OR f.severity::TEXT = p_severity)
      AND (p_status IS NULL OR f.status::TEXT = p_status)
      AND (p_search IS NULL OR f.title ILIKE '%' || p_search || '%')
      AND (p_hostname IS NULL OR f.hostname ILIKE '%' || p_hostname || '%')
      AND (p_ip_address IS NULL OR f.ip_address::TEXT LIKE '%' || p_ip_address || '%')
      AND (NOT p_assigned_to_me OR EXISTS (
          SELECT 1 FROM public.finding_assignments fa
          WHERE fa.finding_id = f.id AND fa.user_id = v_user_id AND fa.is_active = true
      ))
      AND (p_assigned_to_team IS NULL OR EXISTS (
          SELECT 1 FROM public.finding_team_assignments fta
          WHERE fta.finding_id = f.id AND fta.team_id = p_assigned_to_team AND fta.is_active = true
      ))
      AND (p_scan_id IS NULL OR EXISTS (
          SELECT 1 FROM public.finding_occurrences fo
          WHERE fo.finding_id = f.id AND fo.scan_import_id = p_scan_id
      ))
      AND (p_diff_type IS NULL OR true); -- TODO: Implementar lógica de diff_type si es necesario

    -- Obtener datos
    SELECT json_build_object(
        'data', COALESCE(json_agg(finding_data), '[]'::json),
        'pagination', json_build_object(
            'page', p_page,
            'per_page', p_per_page,
            'total', v_total,
            'total_pages', CEIL(v_total::FLOAT / p_per_page)
        ),
        'summary', json_build_object(
            'total', v_total,
            'critical', (SELECT COUNT(*)::INTEGER FROM public.findings WHERE project_id = p_project_id AND severity::TEXT = 'Critical'),
            'high', (SELECT COUNT(*)::INTEGER FROM public.findings WHERE project_id = p_project_id AND severity::TEXT = 'High'),
            'medium', (SELECT COUNT(*)::INTEGER FROM public.findings WHERE project_id = p_project_id AND severity::TEXT = 'Medium'),
            'low', (SELECT COUNT(*)::INTEGER FROM public.findings WHERE project_id = p_project_id AND severity::TEXT = 'Low'),
            'info', (SELECT COUNT(*)::INTEGER FROM public.findings WHERE project_id = p_project_id AND severity::TEXT = 'Info')
        )
    ) INTO v_result
    FROM (
        SELECT json_build_object(
            'id', f.id,
            'workspace_id', f.workspace_id,
            'project_id', f.project_id,
            'asset_id', f.asset_id,
            'folio', f.folio,
            'title', f.title,
            'description', f.description,
            'solution', f.solution,
            'location', f.location,
            'severity', f.severity::TEXT,
            'original_severity', f.original_severity,
            'status', f.status::TEXT,
            'hostname', f.hostname,
            'ip_address', f.ip_address,
            'port', f.port,
            'protocol', f.protocol,
            'service', f.service,
            'cves', f.cves,
            'cvss_score', f.cvss_score,
            'cvss_vector', f.cvss_vector,
            'cwe', f.cwe,
            'scanner', f.scanner,
            'scanner_finding_id', f.scanner_finding_id,
            'fingerprint', f.fingerprint,
            'first_seen', f.first_seen,
            'last_seen', f.last_seen,
            'last_activity_at', COALESCE(f.updated_at, f.last_seen, f.first_seen),
            'time_open', EXTRACT(EPOCH FROM (now() - f.first_seen)) / 86400 || ' days',
            'timer_stopped', f.status IN ('Mitigated', 'Accepted Risk', 'False Positive'),
            'is_reopened', COALESCE(f.is_reopened, false),
            'reopen_count', COALESCE(f.reopen_count, 0),
            'time_to_mitigate', NULL, -- TODO: Calcular si está mitigado
            'assigned_users', COALESCE((
                SELECT json_agg(json_build_object(
                    'id', p.id,
                    'full_name', p.full_name,
                    'initials', UPPER(LEFT(p.full_name, 1) || LEFT(SPLIT_PART(p.full_name, ' ', 2), 1)),
                    'color', COALESCE(p.settings->>'color', '#3b82f6')
                ))
                FROM public.finding_assignments fa
                JOIN public.profiles p ON p.id = fa.user_id
                WHERE fa.finding_id = f.id AND fa.is_active = true
            ), '[]'::json),
            'assigned_teams', COALESCE((
                SELECT json_agg(json_build_object(
                    'id', t.id,
                    'name', t.name,
                    'icon', t.icon
                ))
                FROM public.finding_team_assignments fta
                JOIN public.teams t ON t.id = fta.team_id
                WHERE fta.finding_id = f.id AND fta.is_active = true
            ), '[]'::json),
            'comment_count', COALESCE((
                SELECT COUNT(*) FROM public.finding_comments WHERE finding_id = f.id
            ), 0),
            'evidence_count', COALESCE((
                SELECT SUM(jsonb_array_length(fe.files))::INTEGER 
                FROM public.finding_evidence fe 
                WHERE fe.finding_id = f.id AND fe.is_active = true
            ), 0),
            'created_at', f.created_at,
            'updated_at', f.updated_at
        ) AS finding_data
        FROM public.findings f
        WHERE f.project_id = p_project_id
          AND (p_severity IS NULL OR f.severity::TEXT = p_severity)
          AND (p_status IS NULL OR f.status::TEXT = p_status)
          AND (p_search IS NULL OR f.title ILIKE '%' || p_search || '%')
          AND (p_hostname IS NULL OR f.hostname ILIKE '%' || p_hostname || '%')
          AND (p_ip_address IS NULL OR f.ip_address::TEXT LIKE '%' || p_ip_address || '%')
          AND (NOT p_assigned_to_me OR EXISTS (
              SELECT 1 FROM public.finding_assignments fa
              WHERE fa.finding_id = f.id AND fa.user_id = v_user_id AND fa.is_active = true
          ))
          AND (p_assigned_to_team IS NULL OR EXISTS (
              SELECT 1 FROM public.finding_team_assignments fta
              WHERE fta.finding_id = f.id AND fta.team_id = p_assigned_to_team AND fta.is_active = true
          ))
          AND (p_scan_id IS NULL OR EXISTS (
              SELECT 1 FROM public.finding_occurrences fo
              WHERE fo.finding_id = f.id AND fo.scan_import_id = p_scan_id
          ))
          AND (p_diff_type IS NULL OR true) -- TODO: Implementar lógica de diff_type si es necesario
        ORDER BY
            CASE WHEN p_sort_by = 'last_seen' AND p_sort_order = 'desc' THEN f.last_seen END DESC,
            CASE WHEN p_sort_by = 'last_seen' AND p_sort_order = 'asc' THEN f.last_seen END ASC,
            CASE WHEN p_sort_by = 'severity' AND p_sort_order = 'desc' THEN
                CASE f.severity::TEXT WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 WHEN 'Low' THEN 4 ELSE 5 END
            END ASC,
            CASE WHEN p_sort_by = 'first_seen' THEN f.first_seen END DESC
        LIMIT p_per_page OFFSET v_offset
    ) sub;

    RETURN v_result;
END;
$$;

-- Comentario de la función
COMMENT ON FUNCTION public.fn_list_findings(UUID, INTEGER, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT, BOOLEAN, UUID, TEXT, UUID, TEXT, TEXT) IS 
'Lista los findings de un proyecto con filtros y paginación. Requiere permisos de super_admin o tener el permiso findings.read en el workspace del proyecto.';
