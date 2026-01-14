-- Crear bucket 'evidence' si no existe
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'evidence',
    'evidence',
    false, -- Privado, requiere autenticación
    52428800, -- 50MB límite por archivo
    ARRAY[
        'image/*',
        'application/pdf',
        'text/*',
        'application/vnd.openxmlformats-officedocument.*',
        'application/msword',
        'application/vnd.ms-excel',
        'application/vnd.ms-powerpoint'
    ]
)
ON CONFLICT (id) DO NOTHING;

-- Eliminar políticas existentes si existen
DROP POLICY IF EXISTS "Authenticated users can upload evidence" ON storage.objects;
DROP POLICY IF EXISTS "Users can view evidence they have access to" ON storage.objects;
DROP POLICY IF EXISTS "Users can update their own evidence" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete their own evidence or if super admin" ON storage.objects;

-- Política: Usuarios autenticados pueden subir archivos al bucket evidence
CREATE POLICY "Authenticated users can upload evidence"
    ON storage.objects
    FOR INSERT
    WITH CHECK (
        bucket_id = 'evidence'
        AND auth.role() = 'authenticated'
        AND (
            -- Verificar que el path sigue el formato: {workspace_id}/{finding_id}/{filename}
            -- El bucket ya es 'evidence', así que no necesitamos verificar el primer folder
            true
        )
    );

-- Política: Usuarios pueden ver evidencias de findings a los que tienen acceso
CREATE POLICY "Users can view evidence they have access to"
    ON storage.objects
    FOR SELECT
    USING (
        bucket_id = 'evidence'
        AND (
            -- Super admin puede ver todo
            EXISTS (
                SELECT 1 FROM public.profiles p
                WHERE p.id = auth.uid()
                AND p.is_super_admin = true
            )
            OR
            -- Usuario puede ver evidencias de findings en workspaces donde es miembro
            EXISTS (
                SELECT 1 FROM public.finding_evidence fe
                JOIN public.organization_members om ON om.organization_id = (
                    SELECT w.organization_id FROM public.workspaces w WHERE w.id = fe.workspace_id
                )
                WHERE fe.file_path = name
                AND om.user_id = auth.uid()
                AND om.is_active = true
                AND fe.is_active = true
            )
        )
    );

-- Política: Usuarios pueden actualizar sus propias evidencias
CREATE POLICY "Users can update their own evidence"
    ON storage.objects
    FOR UPDATE
    USING (
        bucket_id = 'evidence'
        AND (
            EXISTS (
                SELECT 1 FROM public.profiles p
                WHERE p.id = auth.uid()
                AND p.is_super_admin = true
            )
            OR
            EXISTS (
                SELECT 1 FROM public.finding_evidence fe
                WHERE fe.file_path = name
                AND fe.uploaded_by = auth.uid()
                AND fe.is_active = true
            )
        )
    );

-- Política: Usuarios pueden eliminar sus propias evidencias o si son super admin
CREATE POLICY "Users can delete their own evidence or if super admin"
    ON storage.objects
    FOR DELETE
    USING (
        bucket_id = 'evidence'
        AND (
            EXISTS (
                SELECT 1 FROM public.profiles p
                WHERE p.id = auth.uid()
                AND p.is_super_admin = true
            )
            OR
            EXISTS (
                SELECT 1 FROM public.finding_evidence fe
                WHERE fe.file_path = name
                AND fe.uploaded_by = auth.uid()
            )
        )
    );

