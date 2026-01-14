# Múltiples Usuarios Subiendo Evidencias

## ✅ Funcionalidad Implementada

**SÍ, múltiples personas pueden subir evidencias para el mismo finding.**

Cada usuario crea su propio registro de evidencia con sus archivos y comentarios. Todos los miembros de la organización pueden ver todas las evidencias del finding.

## 🔄 Cómo Funciona

### **Escenario: Múltiples Usuarios Mitigando una Vulnerabilidad**

**Finding:** "Vulnerabilidad SQL Injection en endpoint /api/users"

#### **1. Admin sube evidencia de mitigación:**
```json
POST /api/v1/evidence/findings/{finding_id}/upload
{
  "files": [archivo1.pdf, archivo2.jpg],
  "description": "Parches aplicados",
  "comments": "Se aplicaron los parches de seguridad según el plan de mitigación",
  "evidence_type": "mitigation"
}

// Resultado: 1 registro
{
  "id": "evidence-1",
  "uploaded_by": "admin-uuid",
  "uploaded_by_name": "Admin Usuario",
  "evidence_type": "mitigation",
  "files": [archivo1.pdf, archivo2.jpg],
  "description": "Parches aplicados",
  "comments": "Se aplicaron los parches..."
}
```

#### **2. Ingeniero de Redes sube evidencia de verificación:**
```json
POST /api/v1/evidence/findings/{finding_id}/upload
{
  "files": [screenshot1.png, log.txt],
  "description": "Verificación de parches",
  "comments": "Verificado que los parches están funcionando correctamente",
  "evidence_type": "verification"
}

// Resultado: 1 registro NUEVO (diferente al anterior)
{
  "id": "evidence-2",
  "uploaded_by": "engineer-uuid",
  "uploaded_by_name": "Ingeniero de Redes",
  "evidence_type": "verification",
  "files": [screenshot1.png, log.txt],
  "description": "Verificación de parches",
  "comments": "Verificado que los parches..."
}
```

#### **3. Tester sube evidencia de pruebas:**
```json
POST /api/v1/evidence/findings/{finding_id}/upload
{
  "files": [test_results.pdf],
  "description": "Resultados de pruebas",
  "comments": "Pruebas de penetración realizadas, vulnerabilidad cerrada",
  "evidence_type": "testing"
}

// Resultado: 1 registro NUEVO más
{
  "id": "evidence-3",
  "uploaded_by": "tester-uuid",
  "uploaded_by_name": "Tester",
  "evidence_type": "testing",
  "files": [test_results.pdf],
  ...
}
```

### **Al Listar Evidencias:**

```json
GET /api/v1/evidence/findings/{finding_id}

// Retorna TODAS las evidencias de TODOS los usuarios
[
  {
    "id": "evidence-1",
    "uploaded_by": "admin-uuid",
    "uploaded_by_name": "Admin Usuario",
    "uploaded_by_email": "admin@example.com",
    "evidence_type": "mitigation",
    "file_count": 2,
    "files": [archivo1.pdf, archivo2.jpg],
    "description": "Parches aplicados",
    "comments": "Se aplicaron los parches...",
    "created_at": "2026-01-06T10:00:00Z"
  },
  {
    "id": "evidence-2",
    "uploaded_by": "engineer-uuid",
    "uploaded_by_name": "Ingeniero de Redes",
    "uploaded_by_email": "engineer@example.com",
    "evidence_type": "verification",
    "file_count": 2,
    "files": [screenshot1.png, log.txt],
    "description": "Verificación de parches",
    "comments": "Verificado que los parches...",
    "created_at": "2026-01-06T11:00:00Z"
  },
  {
    "id": "evidence-3",
    "uploaded_by": "tester-uuid",
    "uploaded_by_name": "Tester",
    "uploaded_by_email": "tester@example.com",
    "evidence_type": "testing",
    "file_count": 1,
    "files": [test_results.pdf],
    "description": "Resultados de pruebas",
    "comments": "Pruebas de penetración realizadas...",
    "created_at": "2026-01-06T12:00:00Z"
  }
]
```

## 🔐 Permisos

### **Quién puede subir evidencias:**
- ✅ Super Admin (puede subir en cualquier finding)
- ✅ Cualquier miembro activo de la organización del workspace

### **Quién puede ver evidencias:**
- ✅ Super Admin (ve todo)
- ✅ Cualquier miembro activo de la organización del workspace

### **Quién puede eliminar evidencias:**
- ✅ Super Admin (puede eliminar cualquier evidencia)
- ✅ El usuario que subió la evidencia (solo sus propias evidencias)

## 📊 Tipos de Evidencia (`evidence_type`)

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `mitigation` | Evidencia de mitigación aplicada | Parches, configuraciones |
| `verification` | Evidencia de verificación | Screenshots, logs de verificación |
| `initial` | Evidencia inicial del problema | Screenshots del bug |
| `remediation` | Evidencia de remediación completa | Documentación de solución |
| `testing` | Evidencia de pruebas | Resultados de tests, pentesting |
| `other` | Otro tipo | Cualquier otra evidencia |

## 💡 Casos de Uso

### **Caso 1: Flujo de Mitigación Colaborativa**
1. **Admin** sube evidencia de mitigación (`evidence_type: "mitigation"`)
2. **Ingeniero de Redes** sube evidencia de verificación (`evidence_type: "verification"`)
3. **Tester** sube evidencia de pruebas (`evidence_type: "testing"`)
4. Todos pueden ver todas las evidencias y el progreso completo

### **Caso 2: Múltiples Equipos Trabajando**
- Equipo de Desarrollo sube evidencias de código
- Equipo de Infraestructura sube evidencias de configuración
- Equipo de Seguridad sube evidencias de auditoría
- Todos colaboran en el mismo finding

### **Caso 3: Historial Completo**
- Cada usuario documenta su parte del trabajo
- Se mantiene un historial completo de quién hizo qué
- Fácil rastreabilidad y auditoría

## 🎯 Ventajas

1. **Colaboración**: Múltiples personas pueden contribuir
2. **Trazabilidad**: Se sabe quién subió cada evidencia
3. **Organización**: Cada evidencia tiene su tipo y contexto
4. **Historial**: Se mantiene un registro completo de todas las acciones
5. **Flexibilidad**: Cada usuario puede subir múltiples archivos en su evidencia

## 📝 Notas Importantes

- Cada usuario crea su **propio registro** de evidencia
- No se mezclan los archivos de diferentes usuarios
- Cada registro tiene su propio `description` y `comments`
- El campo `uploaded_by` identifica quién subió cada evidencia
- Todos los miembros de la organización pueden ver todas las evidencias

