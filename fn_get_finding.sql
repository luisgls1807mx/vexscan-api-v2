-- Función para obtener detalles completos de un finding
DROP FUNCTION IF EXISTS public.fn_get_finding(UUID) CASCADE;

CREATE OR REPLACE FUNCTION public.fn_get_finding(
    p_finding_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_result JSON;
    v_workspace_id UUID;
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
        RAISE EXCEPTION 'Acceso denegado: no tienes permisos para ver este finding';
    END IF;
    
    -- Obtener detalles completos del finding
    SELECT json_build_object(
        'id', f.id::TEXT,
        'workspace_id', f.workspace_id::TEXT,
        'project_id', f.project_id::TEXT,
        'asset_id', f.asset_id::TEXT,
        'folio', f.folio,
        'title', f.title,
        'description', f.description,
        'solution', f.solution,
        'location', COALESCE(
            f.location,
            CASE 
                WHEN f.hostname IS NOT NULL AND f.port IS NOT NULL THEN f.hostname || ':' || f.port::TEXT
                WHEN f.ip_address IS NOT NULL AND f.port IS NOT NULL THEN f.ip_address || ':' || f.port::TEXT
                WHEN f.hostname IS NOT NULL THEN f.hostname
                WHEN f.ip_address IS NOT NULL THEN f.ip_address::TEXT
                ELSE NULL
            END
        ),
        'severity', f.severity::TEXT,
        'original_severity', f.original_severity::TEXT,
        'status', f.status::TEXT,
        'hostname', f.hostname,
        'ip_address', f.ip_address::TEXT,
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
        'last_activity_at', COALESCE(f.last_activity_at, f.last_seen, f.updated_at),
        'is_reopened', COALESCE(f.is_reopened, false),
        'reopen_count', COALESCE(f.reopen_count, 0),
        'time_to_mitigate', CASE 
            WHEN f.time_to_mitigate IS NOT NULL THEN f.time_to_mitigate::TEXT
            ELSE NULL
        END,
        'assigned_users', COALESCE((
            SELECT json_agg(json_build_object(
                'id', p.id::TEXT,
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
                'id', t.id::TEXT,
                'name', t.name,
                'icon', t.icon
            ))
            FROM public.finding_team_assignments fta
            JOIN public.teams t ON t.id = fta.team_id
            WHERE fta.finding_id = f.id AND fta.is_active = true
        ), '[]'::json),
        'comment_count', COALESCE((
            SELECT COUNT(*)::INTEGER FROM public.finding_comments WHERE finding_id = f.id
        ), 0),
        'evidence_count', COALESCE((
            SELECT SUM(jsonb_array_length(fe.files))::INTEGER 
            FROM public.finding_evidence fe 
            WHERE fe.finding_id = f.id AND fe.is_active = true
        ), 0),
        'created_at', f.created_at,
        'updated_at', f.updated_at
    ) INTO v_result
    FROM public.findings f
    WHERE f.id = p_finding_id;
    
    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.fn_get_finding(UUID) IS 
'Obtiene los detalles completos de un finding, incluyendo asignaciones, conteos de comentarios y evidencias. Requiere permisos de super_admin o ser miembro de la organización del workspace.';

