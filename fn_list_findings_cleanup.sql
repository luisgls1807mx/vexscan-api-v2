-- Script para limpiar y eliminar todas las versiones de fn_list_findings
-- Ejecuta esto PRIMERO antes de crear la nueva función

-- Ver qué funciones existen actualmente
SELECT 
    p.proname as function_name,
    pg_get_function_arguments(p.oid) as arguments,
    pg_get_functiondef(p.oid) as definition
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public' 
AND p.proname = 'fn_list_findings';

-- Generar comandos DROP para todas las versiones encontradas
-- (Copia y ejecuta los comandos que se generen arriba)

-- O eliminar todas las versiones manualmente con este comando:
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN 
        SELECT oid, proname, pg_get_function_arguments(oid) as args
        FROM pg_proc 
        WHERE proname = 'fn_list_findings' 
        AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    LOOP
        EXECUTE 'DROP FUNCTION IF EXISTS public.fn_list_findings(' || r.args || ') CASCADE';
        RAISE NOTICE 'Eliminada función: fn_list_findings(%)', r.args;
    END LOOP;
END $$;

