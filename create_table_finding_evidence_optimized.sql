-- Crear tabla finding_evidence optimizada
-- Un registro = un grupo de evidencias (puede tener 1 o múltiples archivos)
CREATE TABLE IF NOT EXISTS public.finding_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES public.findings(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    
    -- Archivos almacenados como JSONB array
    -- Cada archivo tiene: file_name, file_path, file_size, file_type, file_hash
    files JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Descripción/comentarios compartidos para todos los archivos de este grupo
    description TEXT,
    comments TEXT, -- Campo adicional para comentarios o detalles (textarea)
    
    -- Tipo/contexto de la evidencia (opcional)
    -- Ejemplos: "mitigation", "verification", "initial", "remediation", "testing", etc.
    evidence_type TEXT DEFAULT 'other',
    
    -- Metadata
    uploaded_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Constraint: debe tener al menos un archivo
    CONSTRAINT finding_evidence_files_not_empty CHECK (jsonb_array_length(files) > 0)
);

-- Índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_finding_evidence_finding_id ON public.finding_evidence(finding_id);
CREATE INDEX IF NOT EXISTS idx_finding_evidence_workspace_id ON public.finding_evidence(workspace_id);
CREATE INDEX IF NOT EXISTS idx_finding_evidence_uploaded_by ON public.finding_evidence(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_finding_evidence_is_active ON public.finding_evidence(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_finding_evidence_created_at ON public.finding_evidence(created_at DESC);

-- Índice GIN para búsquedas en el array JSONB de files
CREATE INDEX IF NOT EXISTS idx_finding_evidence_files_gin ON public.finding_evidence USING GIN (files);

-- Trigger para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION public.update_finding_evidence_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_finding_evidence_updated_at ON public.finding_evidence;
CREATE TRIGGER trigger_update_finding_evidence_updated_at
    BEFORE UPDATE ON public.finding_evidence
    FOR EACH ROW
    EXECUTE FUNCTION public.update_finding_evidence_updated_at();

-- Habilitar RLS
ALTER TABLE public.finding_evidence ENABLE ROW LEVEL SECURITY;

-- Política: Los usuarios pueden ver evidencias de findings a los que tienen acceso
CREATE POLICY "Users can view evidence for findings they can access"
    ON public.finding_evidence
    FOR SELECT
    USING (
        is_active = true
        AND (
            -- Super admin puede ver todo
            public.fn_is_super_admin()
            OR
            -- Usuario puede ver evidencias de findings en workspaces donde es miembro
            EXISTS (
                SELECT 1 FROM public.organization_members om
                JOIN public.findings f ON f.workspace_id = finding_evidence.workspace_id
                WHERE om.user_id = auth.uid()
                AND om.organization_id = (
                    SELECT w.organization_id FROM public.workspaces w WHERE w.id = finding_evidence.workspace_id
                )
                AND om.is_active = true
                AND f.id = finding_evidence.finding_id
            )
        )
    );

-- Política: Los usuarios pueden crear evidencias para findings a los que tienen acceso
CREATE POLICY "Users can create evidence for findings they can access"
    ON public.finding_evidence
    FOR INSERT
    WITH CHECK (
        -- Super admin puede crear en cualquier lado
        public.fn_is_super_admin()
        OR
        -- Usuario puede crear evidencias en workspaces donde es miembro
        EXISTS (
            SELECT 1 FROM public.organization_members om
            JOIN public.workspaces w ON w.organization_id = om.organization_id
            WHERE om.user_id = auth.uid()
            AND om.is_active = true
            AND w.id = finding_evidence.workspace_id
        )
        AND uploaded_by = auth.uid()
    );

-- Política: Los usuarios pueden actualizar sus propias evidencias o si son super admin
CREATE POLICY "Users can update their own evidence or if super admin"
    ON public.finding_evidence
    FOR UPDATE
    USING (
        is_active = true
        AND (
            public.fn_is_super_admin()
            OR uploaded_by = auth.uid()
        )
    )
    WITH CHECK (
        is_active = true
        AND (
            public.fn_is_super_admin()
            OR uploaded_by = auth.uid()
        )
    );

-- Política: Los usuarios pueden eliminar (soft delete) sus propias evidencias o si son super admin
CREATE POLICY "Users can delete their own evidence or if super admin"
    ON public.finding_evidence
    FOR DELETE
    USING (
        public.fn_is_super_admin()
        OR uploaded_by = auth.uid()
    );

-- Comentarios de la tabla
COMMENT ON TABLE public.finding_evidence IS 'Almacena grupos de evidencias (archivos) asociados a findings. Cada registro puede contener uno o múltiples archivos en el campo JSONB files.';
COMMENT ON COLUMN public.finding_evidence.files IS 'Array JSONB con los archivos: [{"file_name": "...", "file_path": "...", "file_size": 123, "file_type": "...", "file_hash": "..."}, ...]';
COMMENT ON COLUMN public.finding_evidence.description IS 'Descripción breve compartida para todos los archivos de este grupo';
COMMENT ON COLUMN public.finding_evidence.comments IS 'Comentarios o detalles adicionales compartidos para todos los archivos de este grupo';
COMMENT ON COLUMN public.finding_evidence.evidence_type IS 'Tipo/contexto de la evidencia (mitigation, verification, initial, remediation, testing, other)';

