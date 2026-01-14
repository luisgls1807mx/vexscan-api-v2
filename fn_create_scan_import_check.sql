-- Script para verificar el tipo ENUM network_zone antes de crear la función
-- Ejecuta esto primero para ver qué tipos ENUM existen

-- Ver todos los tipos ENUM relacionados con "network"
SELECT 
    typname as enum_name,
    n.nspname as schema_name,
    string_agg(e.enumlabel, ', ' ORDER BY e.enumsortorder) as enum_values
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
JOIN pg_namespace n ON t.typnamespace = n.oid
WHERE t.typtype = 'e' 
AND (typname ILIKE '%network%' OR typname ILIKE '%zone%')
GROUP BY typname, n.nspname
ORDER BY n.nspname, typname;

-- Ver la estructura de la tabla scan_imports para ver qué tipo tiene network_zone
SELECT 
    column_name,
    data_type,
    udt_name,
    udt_schema
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'scan_imports'
AND column_name = 'network_zone';

