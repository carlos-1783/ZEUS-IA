# 🔍 ROCE - CIERRE DEFINITIVO BLOQUEADOR FISCAL

**Auditor**: CURSO (Reality Oriented Critical Evaluation)  
**Fecha**: 2025-01-27  
**Objetivo**: Cerrar bloqueador #5 (Integración Fiscal) de forma legal y técnica

---

## 🎯 VEREDICTO INICIAL

### **BLOQUEADOR CERRABLE EN 7 DÍAS**

**Estado Actual**:
- ✅ TPV genera tickets correctamente
- ✅ RAFAEL tiene `process_tpv_ticket()` que genera datos fiscales
- ✅ Firewall existe y persiste documentos
- ⚠️ **FALTA**: Persistencia automática de documentos fiscales de TPV
- ⚠️ **FALTA**: Estados fiscales específicos (exported, filed_external)
- ⚠️ **FALTA**: Trazabilidad completa TPV → Documento Fiscal → Gestor

**LO QUE NO SE IMPLEMENTARÁ** (por motivos legales):
- ❌ Envío automático a Hacienda sin certificado delegado
- ❌ Asunción de responsabilidad fiscal por ZEUS
- ❌ Promesas comerciales de "presentación automática"

---

## 📊 ANÁLISIS ROCE DEL FLUJO FISCAL ACTUAL

### R — REALIDAD

**Flujo Actual Verificado**:

1. **TPV procesa venta** (`process_sale()`):
   - ✅ Genera ticket con datos completos
   - ✅ Llama a `_send_to_rafael(ticket)`
   - ⚠️ **PROBLEMA**: El resultado de RAFAEL NO se persiste en `DocumentApproval`

2. **RAFAEL procesa ticket** (`process_tpv_ticket()`):
   - ✅ Genera datos fiscales (libro_ingresos, resumen_diario, resumen_mensual)
   - ✅ Genera entrada contable (accounting_entry)
   - ✅ Marca `draft_only: True`
   - ⚠️ **PROBLEMA**: NO persiste automáticamente en BD

3. **Firewall** (`legal_fiscal_firewall.py`):
   - ✅ Existe y funciona
   - ✅ Persiste documentos en `DocumentApproval`
   - ⚠️ **PROBLEMA**: NO se llama automáticamente desde TPV → RAFAEL

**Gap Identificado**:
- TPV → RAFAEL genera datos fiscales pero NO los persiste
- No hay conexión automática entre `process_tpv_ticket()` y `firewall.generate_draft_document()`

---

### O — OPERATIVIDAD

**Flujo Requerido** (según definition_of_done):

```
TPV → Procesar Venta
  ↓
RAFAEL → Generar Documento Fiscal (borrador)
  ↓
Firewall → Persistir en BD (estado: draft)
  ↓
Usuario → Revisar Documento Pendiente
  ↓
Usuario → Aprobar Documento
  ↓
Firewall → Enviar al Gestor Fiscal (email/export)
  ↓
Estado Final: sent_to_advisor
```

**Qué Funciona HOY**:
- ✅ TPV → RAFAEL genera datos fiscales
- ✅ Firewall puede persistir documentos
- ✅ Firewall puede enviar al gestor

**Qué FALTA**:
- ❌ Conexión automática TPV → RAFAEL → Firewall → BD
- ❌ Estados fiscales específicos (exported, filed_external)
- ❌ Trazabilidad completa del flujo

---

### C — COHERENCIA

**Incoherencias Detectadas**:

1. **Backend vs Frontend**:
   - Backend: RAFAEL genera datos fiscales pero no los persiste
   - Frontend: Usuario no ve documentos fiscales de TPV pendientes
   - **Divergencia**: ALTA

2. **Mensaje Comercial vs Realidad Técnica**:
   - Comercial: "Facturación automática"
   - Realidad: Datos fiscales generados pero no persistidos ni entregados automáticamente
   - **Divergencia**: ALTA

3. **Legal vs Técnico**:
   - Legal: No se puede enviar a Hacienda sin certificado
   - Técnico: No hay envío automático implementado
   - **Coherencia**: ✅ CORRECTA (no se implementa lo ilegal)

---

### E — EJECUCIÓN

**Plan de 7 Días para Cerrar Bloqueador**:

---

## 📅 PLAN DE 7 DÍAS

### DÍA 1: Auditoría Real del Flujo Fiscal Actual

**Tareas**:
- [x] Verificar estado actual de `process_tpv_ticket()`
- [x] Verificar estado actual del Firewall
- [x] Identificar gap: TPV → RAFAEL → Firewall → BD
- [ ] Documentar flujo actual vs flujo requerido

**Entregable**: Mapa del flujo actual con gaps identificados

---

### DÍA 2: Modelo de Estados Fiscales y Persistencia en BD

**Tareas**:
- [ ] Extender modelo `DocumentApproval` con estados fiscales:
  - `draft` (ya existe)
  - `pending_review` (ya existe como `pending_approval`)
  - `approved_by_manager` (nuevo)
  - `exported` (nuevo - documento exportado para gestor)
  - `filed_external` (nuevo - gestor confirmó presentación)
- [ ] Agregar campos a `DocumentApproval`:
  - `fiscal_document_type` (ticket, factura, modelo_303, etc.)
  - `ticket_id` (referencia al ticket TPV)
  - `export_format` (json, xml, pdf)
  - `exported_at` (timestamp de exportación)
  - `filed_external_at` (timestamp de presentación externa)
- [ ] Crear migración Alembic

**Entregable**: Modelo extendido con estados fiscales completos

---

### DÍA 3: Flujo de Aprobación Manual y Roles

**Tareas**:
- [ ] Modificar `process_tpv_ticket()` para que llame automáticamente a `firewall.generate_draft_document()`
- [ ] Conectar TPV → RAFAEL → Firewall → BD automáticamente
- [ ] Implementar endpoint `POST /api/v1/tpv/fiscal-documents/{ticket_id}/approve`
- [ ] Verificar roles: solo usuario propietario puede aprobar

**Entregable**: Flujo automático TPV → Documento Fiscal persistido

---

### DÍA 4: Exportación y Entrega Automática a Gestor

**Tareas**:
- [ ] Implementar exportación de documentos fiscales (JSON, XML, PDF)
- [ ] Endpoint `POST /api/v1/tpv/fiscal-documents/{id}/export`
- [ ] Modificar `approve_and_send_to_advisor()` para incluir exportación automática
- [ ] Envío automático por email al gestor fiscal con archivos adjuntos
- [ ] Actualizar estado a `exported` después de exportar

**Entregable**: Entrega automática de documentos fiscales al gestor

---

### DÍA 5: Trazabilidad Completa y Logs Fiscales

**Tareas**:
- [ ] Extender `audit_log` con eventos fiscales:
  - `ticket_processed` (TPV procesó venta)
  - `fiscal_document_generated` (RAFAEL generó documento)
  - `document_exported` (documento exportado)
  - `sent_to_manager` (enviado al gestor)
  - `filed_externally` (gestor confirmó presentación)
- [ ] Endpoint `GET /api/v1/tpv/fiscal-documents/{id}/trace` (trazabilidad completa)
- [ ] Logs de quién, cuándo, qué acción

**Entregable**: Trazabilidad completa del flujo fiscal

---

### DÍA 6: Ajuste UX + Mensajes Legales/Comerciales

**Tareas**:
- [ ] Componente frontend para ver documentos fiscales pendientes de TPV
- [ ] Botón "Exportar y Enviar al Gestor Fiscal"
- [ ] Mensajes legales claros:
  - "ZEUS genera documentos fiscales en borrador. Requiere aprobación y revisión del gestor fiscal antes de presentar a Hacienda."
  - "ZEUS NO presenta impuestos automáticamente. El gestor fiscal es responsable de la presentación."
- [ ] Actualizar mensajes comerciales para alinearlos con la realidad técnica

**Entregable**: UX completa + mensajes legales/comerciales alineados

---

### DÍA 7: Validación ROCE Final y Checklist de Lanzamiento

**Tareas**:
- [ ] Verificar flujo end-to-end: TPV → Documento → Aprobación → Entrega
- [ ] Verificar persistencia: documentos sobreviven reinicios
- [ ] Verificar trazabilidad: todos los eventos registrados
- [ ] Verificar legalidad: no se promete envío automático a Hacienda
- [ ] Checklist de lanzamiento sin riesgo

**Entregable**: Validación final y checklist de lanzamiento

---

## 🗺️ MAPA DEL FLUJO FISCAL FINAL

```
┌─────────────────┐
│  TPV: Venta     │
│  Procesada      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RAFAEL:         │
│ process_tpv_    │
│ ticket()        │
│ Genera datos    │
│ fiscales        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Firewall:       │
│ generate_draft_ │
│ document()      │
│ Persiste en BD  │
│ Estado: draft   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Usuario:        │
│ Revisa documento│
│ pendiente       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Usuario:        │
│ Aprueba y       │
│ Exporta         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Firewall:       │
│ Exporta (JSON/   │
│ XML/PDF)        │
│ Envía email     │
│ al gestor       │
│ Estado: exported│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Gestor Fiscal:  │
│ Recibe documento│
│ Presenta a      │
│ Hacienda        │
│ (externo)       │
└─────────────────┘
```

---

## ✅ CHECKLIST DE LANZAMIENTO SIN RIESGO

### Técnico:
- [ ] TPV genera tickets correctamente
- [ ] RAFAEL genera documentos fiscales automáticamente
- [ ] Documentos fiscales se persisten en BD
- [ ] Usuario puede ver documentos pendientes
- [ ] Usuario puede aprobar y exportar
- [ ] Documentos se envían automáticamente al gestor
- [ ] Trazabilidad completa implementada

### Legal:
- [ ] NO se promete envío automático a Hacienda
- [ ] Mensaje legal claro sobre responsabilidad del gestor
- [ ] Disclaimer visible: "ZEUS no presenta impuestos automáticamente"
- [ ] Documentos marcados como "borrador" hasta aprobación

### Comercial:
- [ ] Mensaje comercial alineado con realidad técnica
- [ ] Se promete: "Generación automática de documentos fiscales"
- [ ] NO se promete: "Presentación automática a Hacienda"
- [ ] Feature descrita como "asistida" no "automática"

---

## 📝 PÁRRAFO COMERCIAL EXACTO PERMITIDO

**Versión CORRECTA**:
> "ZEUS genera automáticamente documentos fiscales completos (libro de ingresos, resumen diario, modelos 303) a partir de cada venta del TPV. Los documentos se generan en modo borrador y se envían automáticamente a tu gestor fiscal para su revisión y presentación a Hacienda. ZEUS NO presenta impuestos automáticamente - tu gestor fiscal es responsable de la presentación final."

**Versión INCORRECTA** (NO usar):
> "ZEUS presenta automáticamente tus impuestos a Hacienda"
> "Facturación fiscal 100% automática"
> "Sin intervención del gestor fiscal"

---

## 🎯 ESTADO FINAL ESPERADO

**Bloqueador Cerrado Si**:
- ✅ Zeus genera documentos fiscales válidos y completos
- ✅ Cada documento tiene estado fiscal persistido
- ✅ Entrega automática de documentos al gestor
- ✅ Trazabilidad completa (quién, cuándo, qué)
- ✅ NO se promete envío automático a Hacienda
- ✅ Mensaje legal y comercial alineado con la realidad

---

**Última Actualización**: 2025-01-27
