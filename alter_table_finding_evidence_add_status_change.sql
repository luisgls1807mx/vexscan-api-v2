-- Agregar columna para relacionar evidencia con cambio de estatus
ALTER TABLE public.finding_evidence
ADD COLUMN IF NOT EXISTS related_status_change_id UUID REFERENCES public.finding_status_history(id) ON DELETE SET NULL;

-- Crear índice para búsquedas por cambio de estatus
CREATE INDEX IF NOT EXISTS idx_finding_evidence_status_change 
ON public.finding_evidence(related_status_change_id) 
WHERE related_status_change_id IS NOT NULL;

-- Comentario
COMMENT ON COLUMN public.finding_evidence.related_status_change_id IS 
'ID del cambio de estatus relacionado (opcional). Si es NULL, la evidencia es independiente del cambio de estatus. Permite que múltiples personas suban evidencias para el mismo cambio de estatus.';

