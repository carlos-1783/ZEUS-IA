# ROCE - Real Operational Company Evaluation

## Auditoría End-to-End para Empresa Real

Esta auditoría verifica que ZEUS funciona realmente para una empresa real desde cero, utilizando todo el ecosistema y todos los agentes.

## Requisitos

1. **Backend ejecutándose**: El backend debe estar corriendo en `http://localhost:8000` (o configurar la URL en el script)
2. **Python 3.8+**: Con las siguientes dependencias:
   ```bash
   pip install requests
   ```

## Ejecución

### Opción 1: Script Batch (Windows)
```bash
EJECUTAR_ROCE_END_TO_END.bat
```

### Opción 2: Python directo
```bash
python ROCE_END_TO_END_REAL_COMPANY.py [URL_BACKEND]
```

Ejemplo:
```bash
python ROCE_END_TO_END_REAL_COMPANY.py http://localhost:8000
```

## Pasos de la Auditoría

1. **Inicialización desde cero**
   - Crear empresa desde panel
   - Asignar país, moneda e idioma
   - Crear usuarios con distintos roles
   - Validar login/logout por rol

2. **TPV real**
   - Crear múltiples productos/servicios
   - Asignar precios e impuestos
   - Modificar productos
   - Eliminar productos
   - Registrar venta con múltiples líneas
   - Verificar persistencia tras recarga

3. **Control horario**
   - Check-in empleado
   - Check-out empleado
   - Cálculo de horas
   - Cruce con facturación

4. **Flujo fiscal legal**
   - Generar factura desde TPV
   - Validar documento con JUSTICIA
   - Revisión por RAFAEL
   - Persistencia en BD
   - Entrega automática al gestor

5. **Marketing y captación**
   - PERSEO analiza mercado
   - Genera estrategia realista
   - Conecta datos de ventas
   - Evalúa ROI y conversión

6. **Seguridad y control**
   - THALOS valida permisos
   - Intento de acceso indebido
   - Verificación de aislamiento de datos
   - Verificación multi-tenancy

7. **Dashboard y coherencia**
   - Comparar métricas móvil vs desktop
   - Verificar consistencia de ingresos
   - Verificar horas trabajadas
   - Verificar clientes activos

## Agentes Verificados

- ✅ ZEUS_CORE
- ✅ RAFAEL
- ✅ PERSEO
- ✅ JUSTICIA
- ✅ THALOS
- ✅ AFRODITA

## Criterios de Validación

### Críticos
- ❌ No pérdida de datos
- ❌ No fuga entre usuarios
- ✅ TPV totalmente operable
- ✅ Facturación legal coherente
- ✅ Roles respetados

### UX
- ✅ Sin alert() bloqueantes
- ✅ Feedback visual correcto
- ✅ Acciones reversibles

## Reporte Final

El script genera un reporte JSON con:

- **Summary**: Resumen de pasos ejecutados
- **Agent by Agent**: Estado de cada agente
- **Failures Detected**: Fallos críticos encontrados
- **Business Readiness Score**: Puntuación de preparación (0-100%)
- **Risk Assessment**: 
  - Legal Risk (LOW/MEDIUM/HIGH)
  - Technical Risk (LOW/MEDIUM/HIGH)
  - Commercial Risk (LOW/MEDIUM/HIGH)
- **Veredicto Final**: GO / GO_WITH_LIMITS / NO_GO
- **Reasoning**: Razonamiento detallado del veredicto

## Veredictos Posibles

- **GO**: Sistema funcional con alta tasa de éxito. Sin fallos críticos detectados.
- **GO_WITH_LIMITS**: Sistema funcional pero con limitaciones. Requiere mejoras antes de producción completa.
- **NO_GO**: Sistema no está listo para producción. Fallos críticos detectados.

## Archivos Generados

- `ROCE_REPORT_YYYYMMDD_HHMMSS.json`: Reporte completo de la auditoría

## Notas Importantes

- La auditoría crea datos de prueba (empresa, usuarios, productos, ventas)
- Algunos endpoints pueden no estar implementados (se marcan como WARN, no críticos)
- La auditoría es destructiva: crea y modifica datos reales en la base de datos
- Se recomienda ejecutar en un entorno de desarrollo/staging, no en producción
