# AUDIT_FIX_GESTORIA.md

**Rama**: `feature/envio-gestoria` (desde `main`)
**Fecha**: 2026-08-13
**Objetivo**: automatizar el envío por email de los documentos fiscales que RAFAEL
genera (facturas, modelo 303) a la gestoría, sin intervención manual de Carlos.

---

## 1. Qué genera RAFAEL realmente hoy (confirmado en código, no asumido)

| Documento | ¿Real? | Formato | Generador | Guardado en |
|---|---|---|---|---|
| Factura | ✅ Sí, real, con datos de BD | PDF (reportlab) | `services/rafael_fiscal_engine_v2.generate_invoice_pdf_flow()` → `services/fiscal_pdf_generator.generate_invoice_pdf_v1` | `STATIC_DIR/fiscal/{company_id}/invoices/` |
| Modelo 303 | ✅ Sí, real, con datos de BD | XLSX (openpyxl) | `services/rafael_fiscal_engine_v2.generate_model_303_flow()` → `services/fiscal_excel_generator.generate_model_303_xlsx_v1` | `STATIC_DIR/fiscal/{company_id}/model_303/` |
| Modelo 390 | ❌ NO es un documento real | — | `services/workspaces/rafael_tools.generate_fiscal_forms()` es una calculadora rápida (`revenue*4`), no lee BD real, no genera fichero | — |
| Cashflow | ❌ No existe exportación | — | `cashflow_ledger` / `app/api/v1/endpoints/cashflow.py` es solo un ledger JSON consultable, sin PDF/XLSX en ningún sitio del código | — |

Ambos generadores reales llaman a `register_fiscal_workspace_document()`, que
persiste una fila `DocumentApproval` con `file_path`, `mime_type`,
`fiscal_document_type`, `export_format` reales.

**Decisión del usuario** (confirmada explícitamente antes de implementar):
alcance limitado a **facturas + modelo 303**. Modelo 390 y cashflow quedan
fuera de este step (no existe nada real que enviar todavía).

---

## 2. Infraestructura preexistente reutilizada

Ya existía un firewall legal-fiscal (`services/legal_fiscal_firewall.py`) con
un ciclo de vida `draft → pending_approval → approved → sent_to_advisor`
(`DocumentApproval.status`), con:

- `User.email_gestor_fiscal` (RAFAEL) / `User.email_asesor_legal` (JUSTICIA):
  email del asesor **por tenant**, configurable vía onboarding o
  `POST /api/v1/documents/update-advisor-emails`.
- `User.autoriza_envio_documentos_a_asesores`: flag de autorización explícita
  requerido antes de poder enviar.
- `POST /api/v1/documents/approve`: endpoint ya existente que dispara el envío
  al asesor tras aprobación manual.

**El hueco real era solo uno**: la capa de email (`services/email_service.py`)
no soportaba adjuntos. El resto de la tubería (aprobación, email del asesor
por tenant, persistencia del documento) ya existía y funcionaba.

---

## 3. Trigger elegido: manual desde el dashboard (decisión del usuario)

Se preguntó explícitamente si el envío debía ser manual o automático mensual.
Respuesta: **manual desde el dashboard**.

Esto ya está satisfecho por el endpoint existente `POST /api/v1/documents/approve`
(requiere `current_user.autoriza_envio_documentos_a_asesores=True`). No se ha
creado un endpoint nuevo porque no hacía falta. **No existe todavía un botón
en el frontend** que llame a este endpoint — el enunciado pedía "un endpoint o
trigger claro", no específicamente una UI; se deja como hallazgo/pendiente de
UI si se quiere exponer con un botón en el dashboard.

Automatización mensual (cron) queda fuera de este step por decisión del
usuario — no implementada.

---

## 4. Implementación

### 4.1 `services/email_service.py`

- `_send_via_smtp_sync()` y `_send_via_resend_sync()`: aceptan ahora un
  parámetro `attachments: Optional[List[str]]`. SMTP cambia
  `MIMEMultipart("alternative")` → `"mixed"` cuando hay adjuntos, y añade
  partes `MIMEApplication` con `Content-Disposition: attachment`. Resend añade
  `attachments: [{filename, content: base64}]` al payload JSON.
- Nuevo método público `send_email_with_attachments(to_email, subject, content,
  attachments: List[str], ...)`: valida que todos los ficheros existan en
  disco antes de intentar nada; misma prioridad de proveedores que
  `send_email()` (SMTP → SendGrid → Resend); en SendGrid construye
  `Attachment(FileContent, FileName, FileType, Disposition)` por cada
  fichero, en base64.

### 4.2 `services/legal_fiscal_firewall.py`

- `_get_advisor_email()`: prioriza `User.email_gestor_fiscal` /
  `User.email_asesor_legal` (mecanismo real por tenant); solo si el usuario no
  lo ha configurado, cae a una nueva variable de entorno opcional
  `GESTORIA_EMAIL_DEFAULT` (solo para RAFAEL). Esto es **deliberado**: en un
  SaaS multi-tenant cada empresa tiene su propia gestoría, así que un email
  global hardcodeado sería un regreso a un patrón incorrecto — `GESTORIA_EMAIL_DEFAULT`
  es un fallback, no el mecanismo principal.
- `_send_to_advisor()`: si el `DocumentApproval` tiene un `file_path` real en
  disco, adjunta el fichero real (`send_email_with_attachments`) con un asunto
  que incluye el tipo de documento y un cuerpo que dice "documento adjunto a
  este email" en vez de volcar el JSON. Si no hay fichero real (p. ej.
  documentos de JUSTICIA sin generador de fichero todavía), degrada de forma
  segura al comportamiento anterior (JSON en el cuerpo) — no rompe casos no
  cubiertos por este step.

### 4.3 Variable de entorno nueva

```
GESTORIA_EMAIL_DEFAULT=  # opcional, fallback SOLO si el usuario no configuró email_gestor_fiscal
```

No añadida a `Settings` (config.py) porque se lee con `os.getenv()` puntual,
igual que otras variables opcionales de email ya existentes en el repo
(no hay `.env.example` que actualizar — no existe en el repo).

---

## 5. Verificación con envío real — BLOQUEADO, no simulado

Se montaron datos 100% reales para probar el flujo end-to-end (ver §6):
usuario real, factura real con items reales, PDF real generado por RAFAEL
(1920 bytes, verificado como PDF válido con cabecera `%PDF-1.3`), email de
gestoría configurado en el usuario de prueba
(`marketingdigitalper.seo@gmail.com`).

Al invocar `POST /api/v1/documents/approve`, el envío por SendGrid falló con
`401 Unauthorized`. **Diagnóstico completo, sin asumir nada:**

1. Se probó la misma `SENDGRID_API_KEY` del `.env` directamente contra
   `GET https://api.sendgrid.com/v3/user/account` → `200 OK`. **La clave es
   válida.**
2. Se reprodujo el envío exacto (mismo cliente, mismo `Mail()`) fuera de la
   app, en un script aislado. Error real devuelto por SendGrid:
   ```json
   {"errors":[{"message":"Maximum credits exceeded","field":null,"help":null}]}
   ```

**Conclusión: no es un bug del código nuevo.** La cuenta de SendGrid
configurada ha agotado su cuota de envíos (plan gratuito/trial). El código de
adjuntos está correctamente construido, autenticado y llega a SendGrid — el
proveedor rechaza el envío por límite de cuenta, no por error de la
integración.

No hay proveedor de fallback configurado en este entorno: `.env` no tiene
`RESEND_API_KEY` ni `SMTP_HOST`/`SMTP_USER`, así que no hubo alternativa
automática.

**Se preguntó al usuario cómo proceder** (configurar Resend, otra clave
SendGrid, SMTP, o esperar). Decisión: **esperar a que se resetee la cuota de
SendGrid** — el código queda listo, documentado y sin verificación de envío
real todavía. Esto se deja consignado explícitamente como pendiente, no como
"hecho", siguiendo la regla de no simular resultados.

**Próximo paso cuando haya cuota disponible**: repetir
`POST /api/v1/documents/approve` con `document_id=1`, `agent_name="RAFAEL"`
(datos de prueba ya montados, ver §6) y confirmar en la respuesta
`send_result.success=true`, `send_result.attached_real_file=true` y
`send_result.provider`.

---

## 6. Datos de prueba creados (entorno local, SQLite)

- Usuario: `test.gestoria@example.com` (user_id=2, company_id=1),
  `email_gestor_fiscal=marketingdigitalper.seo@gmail.com`,
  `autoriza_envio_documentos_a_asesores=1`.
- Cliente: id=1, "Cliente Gestoria Test SL".
- Factura: id=1, `INV-20260813-1`, total=605.0 (1 línea, 500€ + 21% IVA).
- `DocumentApproval` id=1: PDF real generado en
  `backend/static/fiscal/1/invoices/invoice_INV-20260813-1_20260813184742.pdf`
  (1920 bytes, verificado como PDF válido).

Estos ficheros PDF de prueba **no se han commiteado** (son artefactos de test,
no parte del código fuente) — quedan como untracked en el working tree.

---

## 7. Bugs preexistentes encontrados y arreglados (bloqueaban montar los datos de prueba)

Ninguno de estos bugs tiene relación con la funcionalidad de envío a gestoría
en sí — todos bloqueaban poder crear usuario/factura/PDF de prueba en esta
rama, que parte de `main` y por tanto no tiene los fixes ya aplicados en otras
ramas (`feature/multi-tenant-bd`).

| # | Fichero | Bug | Fix | Commit |
|---|---|---|---|---|
| 1 | `app/core/security.py` | `jwt.decode(audience=JWT_AUDIENCE)` con `JWT_AUDIENCE` como lista → `JWTError` siempre | Quitar `audience=`, `verify_aud=False`, ya existe validación manual de audiencia-lista más abajo | `d9290df` |
| 2 | `app/core/security.py` | `get_current_user()` buscaba `User.email == payload["sub"]`, pero `sub` es el user id, no el email → "Usuario no encontrado" siempre | Intentar `User.id == int(sub)` primero, fallback a `User.email == sub` (igual que `app.core.auth.py`) | `d9290df` |
| 3 | `app/models/erp.py` | 7 columnas `Enum(...)` sin `values_callable` bindean por `.name` (mayúsculas) pero la API escribe `.value` (minúsculas) → `LookupError` en `db.refresh()` | `values_callable=lambda x: [e.value for e in x]` en las 7 | `cd5f16a` |
| 4 | `app/schemas/erp.py` | `issue_date`/`due_date`/`payment_date` tipados `date`, columna real es `DateTime` → `ResponseValidationError: date_from_datetime_inexact` | Retipado a `datetime` | `25b5681` |
| 5 | `app/api/v1/endpoints/invoices.py` | Items añadidos con `db.add(item)` suelto → `invoice.items` veía colección vacía/obsoleta → `calculate_invoice_totals()` siempre 0.0, bloqueando el gate `total > 0` de RAFAEL | `db.flush()` + `db.expire(invoice, ["items"])` antes de calcular totales | `da6a025` |
| 6 | `services/fiscal_db_compat.py` | `table_column_names()`/`_table_names()` usaban SQL crudo contra `information_schema` (solo Postgres) → fallo silencioso en SQLite → `insert_document_approval_row()` creía que `document_approvals` no existía | Reescrito con `sqlalchemy.inspect(engine)`, dialect-agnostic | `0e1586c` |
| 7 | — | `reportlab`/`openpyxl` declarados en `requirements.txt` pero no instalados en el entorno local | `pip install reportlab openpyxl` (sin cambio de código) | — |

### Hallazgo NO arreglado (fuera de alcance, documentado)

**Bug 8** — `POST /api/v1/documents/update-advisor-emails`
(`app/api/v1/endpoints/document_approval.py`): al hacer
`db.commit(); db.refresh(current_user)` lanza
`"Instance '<User at ...>' is not persistent within this Session"`.
Causa: `current_user` se carga con una sesión/engine distinto
(`app.core.auth`'s `get_db`) del `db` del propio endpoint
(`app.db.session`'s `get_db`) — el mismo patrón de "dos implementaciones
paralelas de sesión de BD" ya visto repetidamente en este proyecto. **No se
ha arreglado** para no ampliar el alcance de este step; se trabajó alrededor
escribiendo directamente en SQLite para los datos de prueba. Este endpoint es
el único camino actual para que un usuario configure su email de gestoría
desde la API — hoy está roto.

### Hallazgo NO arreglado (fuera de alcance, informativo)

`InvoiceItem.subtotal`/`tax_amount`/`total` quedan siempre en 0.0 (nunca se
calculan al crear los items) — no bloqueante porque el gate de RAFAEL solo
mira el total a nivel de factura, pero es un dato incorrecto si se consulta
el detalle de línea.

---

## 8. Tests

```
cd backend && python -m pytest tests/ -q
```

Resultado: **214 passed, 7 failed, 2 skipped, 3 errors** — idéntico al
baseline documentado en sesiones anteriores. Cero regresiones introducidas
por los 8 ficheros tocados en este step (los 7 fallos/errores preexistentes
no están relacionados con `email_service.py`, `legal_fiscal_firewall.py`, ni
con ninguno de los 6 bugs arreglados aquí).

---

## 9. Resumen de commits en `feature/envio-gestoria`

```
20d297a feat(gestoria): envio automatico de documentos fiscales RAFAEL a la gestoria
d9290df fix(auth): audience JWT como lista invalida jose.decode y sub mal interpretado como email
cd5f16a fix(erp): values_callable en enums ERP para bindear .value no .name
25b5681 fix(erp): issue_date/due_date/payment_date como datetime no date
da6a025 fix(erp): flush + expire de invoice.items antes de calcular totales
0e1586c fix(fiscal): table_column_names/_table_names dialect-agnostic con sqlalchemy.inspect
```

Sin merge ni push a `main`, según lo pedido.

---

## 10. Pendiente

1. **Verificación de envío real con adjunto** — bloqueada por cuota de
   SendGrid agotada. Repetir en cuanto haya cuota (otra clave, Resend, SMTP,
   o reset del plan).
2. Arreglar Bug 8 (`update-advisor-emails`) si se quiere que el usuario pueda
   configurar su gestoría desde la API/UI sin intervención manual en BD.
3. Botón en el dashboard que llame a `POST /api/v1/documents/approve` (hoy
   el trigger es real pero no tiene UI).
4. Modelo 390 y cashflow: no hay generador real de documento — fuera de
   alcance, requeriría construir el generador desde cero.
