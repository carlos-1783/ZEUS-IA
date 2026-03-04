# Auditoría ROCE End-to-End - ZEUS-IA

## Descripción

Esta auditoría verifica que ZEUS funciona realmente para una empresa real desde cero, utilizando todo el ecosistema y todos los agentes, y emite un veredicto final GO / NO-GO basado únicamente en ejecución real.

## Requisitos Previos

1. **Backend ejecutándose**: El servidor FastAPI debe estar corriendo en `http://localhost:8000`
2. **Base de datos configurada**: La base de datos debe estar inicializada y accesible
3. **Python 3.8+**: Con las dependencias instaladas (`requests`)

## Ejecución

### Opción 1: Script Batch (Windows)

```batch
EJECUTAR_AUDITORIA_ROCE.bat
```

### Opción 2: Manual

1. Asegúrate de que el backend esté ejecutándose:
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload --port 8000
   ```

2. En otra terminal, ejecuta la auditoría:
   ```bash
   python AUDITORIA_ROCE_END_TO_END.py
   ```

## Pasos de la Auditoría

La auditoría ejecuta los siguientes pasos en orden:

### Paso 1: Inicialización desde cero
- ✅ Verificar backend disponible
- ✅ Verificar frontend disponible
- ✅ Crear empresa desde panel
- ✅ Asignar país, moneda e idioma
- ✅ Crear usuarios con distintos roles (Superusuario, Administrador, Empleado)
- ✅ Validar login/logout por rol

### Paso 2: TPV real
- ✅ Crear múltiples productos/servicios
- ✅ Asignar precios e impuestos
- ✅ Modificar productos
- ✅ Eliminar productos
- ✅ Registrar venta con múltiples líneas
- ✅ Verificar persistencia tras recarga

### Paso 3: Control horario
- ✅ Check-in empleado
- ✅ Check-out empleado
- ✅ Corrección manual autorizada
- ✅ Cálculo de horas
- ✅ Cruce con facturación

### Paso 4: Flujo fiscal legal
- ✅ Generar factura desde TPV
- ✅ Validar documento con JUSTICIA
- ✅ Revisión por RAFAEL
- ✅ Persistencia en BD
- ✅ Entrega automática al gestor (export/email)

### Paso 5: Marketing y captación
- ✅ PERSEO analiza mercado
- ✅ Genera estrategia realista
- ✅ Conecta datos de ventas
- ✅ Evalúa ROI y conversión

### Paso 6: Seguridad y control
- ✅ THALOS valida permisos
- ✅ Intento de acceso indebido
- ✅ Verificación de aislamiento de datos
- ✅ Verificación multi-tenancy

### Paso 7: Dashboard y coherencia
- ✅ Comparar métricas móvil vs desktop
- ✅ Verificar consistencia de ingresos
- ✅ Verificar horas trabajadas
- ✅ Verificar clientes activos

## Agentes Auditados

- **ZEUS_CORE**: Núcleo principal del sistema
- **RAFAEL**: Asistente Fiscal y Contable
- **PERSEO**: Estratega de Ventas y Crecimiento
- **JUSTICIA**: Abogada Digital
- **THALOS**: Ciberdefensa Automatizada
- **AFRODITA**: RRHH y Logística

## Reporte Final

Al finalizar, se genera un archivo JSON con el reporte completo:

```
AUDITORIA_ROCE_REPORT_YYYYMMDD_HHMMSS.json
```

### Estructura del Reporte

```json
{
  "audit_metadata": {
    "audit_type": "ROCE_END_TO_END_REAL_COMPANY",
    "auditor": "CURSO",
    "authority_level": "MAXIMUM",
    "company": {...},
    "started_at": "...",
    "completed_at": "..."
  },
  "summary": {
    "total_tests": 50,
    "passed": 45,
    "failed": 2,
    "warnings": 3,
    "skipped": 0,
    "score": 90.0
  },
  "agent_by_agent": {
    "ZEUS_CORE": {...},
    "RAFAEL": {...},
    ...
  },
  "failures_detected": [...],
  "business_readiness_score": 90.0,
  "risk_analysis": {
    "legal_risk": "BAJO|MEDIO|ALTO",
    "technical_risk": "BAJO|MEDIO|ALTO",
    "commercial_risk": "BAJO|MEDIO|ALTO"
  },
  "final_verdict": {
    "verdict": "GO|GO_WITH_LIMITS|NO_GO",
    "reasoning": "..."
  },
  "detailed_results": [...]
}
```

## Veredictos Posibles

### GO
- Score ≥ 90%
- 0 tests críticos fallidos
- Sistema listo para producción

### GO_WITH_LIMITS
- Score ≥ 70%
- < 10% de tests fallidos
- Sistema operativo con limitaciones conocidas

### NO_GO
- Score < 70%
- ≥ 10% de tests fallidos
- Se requieren correcciones críticas

## Criterios de Validación

### Críticos (Bloqueantes)
- ❌ Pérdida de datos
- ❌ Fuga entre usuarios
- ❌ TPV no operable
- ❌ Facturación legal incoherente
- ❌ Roles no respetados

### UX (Advertencias)
- ⚠️ Alert() bloqueantes
- ⚠️ Feedback visual incorrecto
- ⚠️ Acciones no reversibles

## Solución de Problemas

### Backend no disponible
```
Error: Backend no está ejecutándose en http://localhost:8000
```
**Solución**: Inicia el backend antes de ejecutar la auditoría.

### Error de autenticación
```
Error: No se pudo autenticar superusuario
```
**Solución**: Verifica que exista un usuario con email `marketingdigitalper.seo@gmail.com` y password `Carnay19`, o modifica el script para usar credenciales válidas.

### Timeout en agentes
```
Error: Timeout esperando respuesta de PERSEO
```
**Solución**: Los agentes pueden tardar en responder. Aumenta el timeout en el script si es necesario.

## Notas Importantes

1. **Datos de prueba**: La auditoría crea datos de prueba que pueden persistir en la base de datos
2. **Usuarios temporales**: Se crean usuarios de prueba que pueden necesitar limpieza manual
3. **Productos de prueba**: Los productos creados durante la auditoría pueden permanecer en el sistema
4. **No destructivo**: La auditoría no elimina datos existentes, solo crea nuevos datos de prueba

## Contacto

Para preguntas o problemas con la auditoría, consulta la documentación del proyecto o contacta al equipo de desarrollo.
