-- ============================================================================
-- fn_v3_bulk_insert_scan_data.sql
-- RPC para APPROACH 3: Bulk insert de todos los datos de scan en una transacción
-- ============================================================================

-- Eliminar funciones existentes (ambas versiones)
DROP FUNCTION IF EXISTS public.fn_v3_bulk_insert_scan_data(
    UUID, UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, JSONB, JSONB
);
DROP FUNCTION IF EXISTS public.fn_v3_bulk_insert_scan_data(
    UUID, UUID, TEXT, TEXT, BIGINT, TEXT, TEXT, TEXT, UUID, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, JSONB, JSONB
);

-- Crear función de bulk insert
CREATE OR REPLACE FUNCTION public.fn_v3_bulk_insert_scan_data(
    p_workspace_id UUID,
    p_project_id UUID,
    p_file_name TEXT,
    p_storage_path TEXT,
    p_file_size BIGINT,
    p_file_hash TEXT,
    p_scanner TEXT,
    p_network_zone TEXT,
    p_uploaded_by UUID,  -- Nuevo: usuario que sube el archivo
    p_scan_name TEXT DEFAULT NULL,
    p_scan_start TIMESTAMPTZ DEFAULT NULL,
    p_scan_end TIMESTAMPTZ DEFAULT NULL,
    p_assets JSONB DEFAULT '[]'::JSONB,
    p_findings JSONB DEFAULT '[]'::JSONB
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_scan_import_id UUID;
    v_asset JSONB;
    v_finding JSONB;
    v_asset_id UUID;
    v_finding_id UUID;
    v_existing_finding_id UUID;
    v_existing_status TEXT;
    v_assets_created INTEGER := 0;
    v_findings_created INTEGER := 0;
    v_findings_updated INTEGER := 0;
    v_findings_reopened INTEGER := 0;
    v_asset_map JSONB := '{}'::JSONB;
    v_start_time TIMESTAMPTZ := clock_timestamp();
BEGIN
    -- 1. Crear registro scan_import
    INSERT INTO public.scan_imports (
        workspace_id, project_id, file_name, storage_path, file_size,
        file_hash, scanner, network_zone, uploaded_by, status, scan_started_at, scan_finished_at
    )
    VALUES (
        p_workspace_id, p_project_id, p_file_name, p_storage_path, p_file_size,
        p_file_hash, p_scanner, p_network_zone::network_zone, p_uploaded_by, 'processing', p_scan_start, p_scan_end
    )
    RETURNING id INTO v_scan_import_id;

    -- 2. Procesar assets (upsert)
    FOR v_asset IN SELECT * FROM jsonb_array_elements(p_assets)
    LOOP
        INSERT INTO public.assets (
            workspace_id, project_id, identifier, name, hostname, ip_address,
            asset_type, operating_system, is_manual, last_seen
        )
        VALUES (
            p_workspace_id,
            p_project_id,
            v_asset->>'identifier',
            v_asset->>'name',
            v_asset->>'hostname',
            (v_asset->>'ip_address')::INET,
            COALESCE(v_asset->>'asset_type', 'host'),
            v_asset->>'operating_system',
            false,
            NOW()
        )
        ON CONFLICT (workspace_id, identifier) DO UPDATE
        SET last_seen = NOW(),
            operating_system = COALESCE(EXCLUDED.operating_system, assets.operating_system)
        RETURNING id INTO v_asset_id;

        -- Guardar mapping identifier -> id
        v_asset_map := v_asset_map || jsonb_build_object(v_asset->>'identifier', v_asset_id);
        v_assets_created := v_assets_created + 1;
    END LOOP;

    -- 3. Procesar findings
    FOR v_finding IN SELECT * FROM jsonb_array_elements(p_findings)
    LOOP
        -- Buscar asset_id desde el map
        v_asset_id := (v_asset_map->>v_finding->>'asset_identifier')::UUID;

        -- Verificar si existe finding con mismo fingerprint EN EL PROYECTO
        SELECT id, status INTO v_existing_finding_id, v_existing_status
        FROM public.findings
        WHERE project_id = p_project_id
        AND fingerprint = v_finding->>'fingerprint'
        LIMIT 1;

        IF v_existing_finding_id IS NOT NULL THEN
            -- Actualizar finding existente
            UPDATE public.findings
            SET last_seen = NOW(),
                status = CASE 
                    WHEN status IN ('Mitigated', 'Accepted Risk', 'False Positive', 'Not Observed') 
                    THEN 'Open' 
                    ELSE status 
                END,
                is_reopened = CASE 
                    WHEN status IN ('Mitigated', 'Accepted Risk', 'False Positive', 'Not Observed') 
                    THEN true 
                    ELSE is_reopened 
                END
            WHERE id = v_existing_finding_id;

            -- Contar si fue reabierto
            IF v_existing_status IN ('Mitigated', 'Accepted Risk', 'False Positive', 'Not Observed') THEN
                v_findings_reopened := v_findings_reopened + 1;
            END IF;

            v_findings_updated := v_findings_updated + 1;
            v_finding_id := v_existing_finding_id;
        ELSE
            -- Insertar nuevo finding
            INSERT INTO public.findings (
                workspace_id, project_id, asset_id, scanner, scanner_finding_id,
                fingerprint, title, description, solution, severity, original_severity,
                hostname, ip_address, port, protocol, service,
                cves, cvss_score, cvss_vector, cwe, first_seen, last_seen, status
            )
            VALUES (
                p_workspace_id,
                p_project_id,
                v_asset_id,
                v_finding->>'scanner',
                v_finding->>'scanner_finding_id',
                v_finding->>'fingerprint',
                v_finding->>'title',
                v_finding->>'description',
                v_finding->>'solution',
                v_finding->>'severity',
                v_finding->>'original_severity',
                v_finding->>'hostname',
                (v_finding->>'ip_address')::INET,
                (v_finding->>'port')::INTEGER,
                v_finding->>'protocol',
                v_finding->>'service',
                CASE 
                    WHEN v_finding->'cves' IS NOT NULL AND v_finding->'cves' != 'null'::jsonb 
                    THEN ARRAY(SELECT jsonb_array_elements_text(v_finding->'cves'))
                    ELSE NULL 
                END,
                (v_finding->>'cvss_score')::NUMERIC,
                v_finding->>'cvss_vector',
                v_finding->>'cwe',
                NOW(),
                NOW(),
                'Open'
            )
            RETURNING id INTO v_finding_id;

            v_findings_created := v_findings_created + 1;
        END IF;

        -- Crear occurrence
        INSERT INTO public.finding_occurrences (finding_id, scan_import_id, port, protocol)
        VALUES (
            v_finding_id,
            v_scan_import_id,
            (v_finding->>'port')::INTEGER,
            v_finding->>'protocol'
        );
    END LOOP;

    -- 4. Actualizar scan_import con resultados
    UPDATE public.scan_imports
    SET status = 'processed',
        processed_at = NOW(),
        hosts_total = v_assets_created,
        findings_total = jsonb_array_length(p_findings),
        findings_new = v_findings_created,
        findings_updated = v_findings_updated
    WHERE id = v_scan_import_id;

    -- 5. Retornar resultado
    RETURN json_build_object(
        'scan_import_id', v_scan_import_id,
        'processing_time_ms', EXTRACT(MILLISECONDS FROM (clock_timestamp() - v_start_time)),
        'assets_created', v_assets_created,
        'findings_created', v_findings_created,
        'findings_updated', v_findings_updated,
        'findings_reopened', v_findings_reopened,
        'findings_total', jsonb_array_length(p_findings)
    );
END;
$$;

-- Comentario
COMMENT ON FUNCTION public.fn_v3_bulk_insert_scan_data IS 
'APPROACH 3: Bulk insert de todos los datos de scan en una sola transacción atómica. 
Recibe arrays JSON de assets y findings para máximo rendimiento.';

-- Permisos
GRANT EXECUTE ON FUNCTION public.fn_v3_bulk_insert_scan_data TO service_role;
