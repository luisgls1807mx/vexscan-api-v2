-- PASO 1: Eliminar manualmente todas las versiones de la función
-- Ejecuta esto primero en el SQL Editor:

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
        BEGIN
            EXECUTE 'DROP FUNCTION IF EXISTS public.fn_list_findings(' || r.args || ') CASCADE';
            RAISE NOTICE 'Eliminada función: fn_list_findings(%)', r.args;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Error al eliminar fn_list_findings(%): %', r.args, SQLERRM;
        END;
    END LOOP;
END $$;

-- PASO 2: Verificar que se eliminaron todas las versiones
SELECT 
    p.proname as function_name,
    pg_get_function_arguments(p.oid) as arguments
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public' 
AND p.proname = 'fn_list_findings';

-- Si la consulta anterior no devuelve resultados, entonces todas las funciones fueron eliminadas
-- Procede a ejecutar fn_list_findings.sql

