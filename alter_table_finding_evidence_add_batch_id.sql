-- Agregar columna batch_id a la tabla finding_evidence si no existe
-- Esto permite agrupar archivos subidos juntos en la misma operación
ALTER TABLE public.finding_evidence 
ADD COLUMN IF NOT EXISTS batch_id UUID;

-- Crear índice para batch_id
CREATE INDEX IF NOT EXISTS idx_finding_evidence_batch_id ON public.finding_evidence(batch_id);

-- Comentario
COMMENT ON COLUMN public.finding_evidence.batch_id IS 'Agrupa archivos subidos juntos en la misma operación. Archivos del mismo batch comparten description y comments.';

