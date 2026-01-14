-- Políticas de seguridad para el bucket 'scans' en Supabase Storage
-- Estas políticas controlan quién puede insertar, actualizar y eliminar archivos

-- ============================================
-- ELIMINAR POLÍTICAS EXISTENTES (si es necesario)
-- ============================================
-- Si necesitas eliminar políticas existentes, ejecuta estos comandos primero:
-- DROP POLICY IF EXISTS "Usuarios autenticados pueden insertar scans" ON storage.objects;
-- DROP POLICY IF EXISTS "Usuarios pueden leer sus propios scans o super_admin todos" ON storage.objects;
-- DROP POLICY IF EXISTS "Solo el dueño puede actualizar scans" ON storage.objects;
-- DROP POLICY IF EXISTS "Solo el dueño o super_admin puede eliminar scans" ON storage.objects;

-- ============================================
-- 1. POLÍTICA DE INSERCIÓN (INSERT)
-- ============================================
-- Solo usuarios autenticados pueden insertar archivos
CREATE POLICY "Usuarios autenticados pueden insertar scans"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'scans'
);

-- ============================================
-- 2. POLÍTICA DE LECTURA (SELECT)
-- ============================================
-- Usuarios autenticados pueden leer sus propios archivos
-- Super_admin puede leer todos los archivos
CREATE POLICY "Usuarios pueden leer sus propios scans o super_admin todos"
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'scans'
    AND (
        -- El usuario es el dueño del archivo
        owner = auth.uid()
        OR
        -- O es super_admin
        EXISTS (
            SELECT 1 
            FROM public.profiles p
            WHERE p.id = auth.uid()
            AND p.is_super_admin = true
        )
    )
);

-- ============================================
-- 3. POLÍTICA DE ACTUALIZACIÓN (UPDATE)
-- ============================================
-- Solo el dueño del archivo puede actualizarlo
CREATE POLICY "Solo el dueño puede actualizar scans"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
    bucket_id = 'scans'
    AND owner = auth.uid()
)
WITH CHECK (
    bucket_id = 'scans'
    AND owner = auth.uid()
);

-- ============================================
-- 4. POLÍTICA DE ELIMINACIÓN (DELETE)
-- ============================================
-- Solo el dueño del archivo puede eliminarlo
-- O super_admin puede eliminar cualquier archivo
CREATE POLICY "Solo el dueño o super_admin puede eliminar scans"
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'scans'
    AND (
        -- El usuario es el dueño del archivo
        owner = auth.uid()
        OR
        -- O es super_admin
        EXISTS (
            SELECT 1 
            FROM public.profiles p
            WHERE p.id = auth.uid()
            AND p.is_super_admin = true
        )
    )
);

-- ============================================
-- NOTAS IMPORTANTES:
-- ============================================
-- 1. Las políticas se aplican automáticamente cuando se ejecutan
-- 2. El campo 'owner' en storage.objects contiene el UUID del usuario que subió el archivo
-- 3. Para verificar si un usuario es super_admin, consultamos la tabla profiles
-- 4. La política de lectura también permite acceso si el archivo está asociado a una organización
--    de la que el usuario es miembro (basado en scan_imports y organization_members)
-- 5. Si necesitas políticas más específicas, puedes ajustar las condiciones USING y WITH CHECK

