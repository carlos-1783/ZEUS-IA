# Auditoría/implementación: puente real venta TPV -> factura RAFAEL

**Fecha**: 2026-08-22
**Rama**: `feature/facturacion-tpv-real` (desde `main`)
**Commit**: `d89f8f5` — feat(tpv,rafael): puente real venta TPV -> factura RAFAEL

---

## Contexto de partida

Confirmado en la investigación previa de esta sesión (rama `feature/iva-duplicado`,
ver `git show feature/iva-duplicado:AUDIT_IVA_TPV.md`):

1. El cálculo de IVA en TPV es correcto de extremo a extremo (precio con IVA
   desglosado en frontend antes de enviarse, IVA calculado una sola vez en
   `fiscal_engine.py`, persistido en `tpv_sales`/`tpv_sale_items`).
2. **No existía puente real venta TPV -> factura**: el botón "Generar Factura"
   (`frontend/src/views/TPV.vue`) no llamaba a ningún endpoint, y
   `POST /tpv/invoice` -> `TPVService.generate_invoice`
   (`backend/services/tpv_service.py:1022` en la versión anterior) era un stub
   que devolvía `success: true` con un `invoice.id` inventado sin validar
   nada ni persistir nada real, incluso con un `ticket_id` inexistente.

Esta tarea construye ese puente de verdad, reutilizando el cálculo de IVA ya
verificado (sin reinventarlo).

---

## Qué se construyó

### Backend

- **`backend/services/tpv_service.py` — `TPVService.generate_invoice`**
  (reescrito por completo, sustituye el stub):
  - Recibe `db`, `ticket_id`, `customer_data`, `user_id`, `company_ids`.
  - Consulta `TPVSale` real por `ticket_id` (con `items` vía `joinedload`).
    Si no existe: `HTTPException(404)` real (antes: éxito falso).
  - Verifica tenant: la venta debe pertenecer al `user_id` solicitante o a una
    de sus `company_ids` (`sale.user_id == user_id or sale.company_id in
    company_ids`). Si no: `HTTPException(403)`. Nunca éxito falso.
  - Si la venta no tiene líneas: `422`.
  - **Idempotencia real**: si ya existe una `Invoice` para esa
    `tpv_sale_id`, la devuelve (`already_existed: true`) en vez de duplicar.
    Reforzado con índice único en BD (`Invoice.tpv_sale_id` UNIQUE), no solo
    en código.
  - Busca o crea un `Customer` real (tabla ya existente `customers`, no una
    tabla paralela) a partir de los datos de cliente de la venta
    (`sale.customer_data`) fusionados con los que llegue en la petición.
  - Crea `Invoice` + `InvoiceItem` reales (`backend/app/models/erp.py`,
    tablas `invoices`/`invoice_items`, ya usadas por el resto del ERP) con
    **`subtotal`, `tax_amount`, `total` copiados directamente de la
    `TPVSale` ya persistida** — no se recalcula el IVA en ningún punto de
    este flujo. `status=PAID`, `amount_paid=total`, `amount_due=0` (la venta
    TPV ya está cobrada).
  - Registra logs reales (`tpv_invoice_generada`, `tpv_invoice_ya_existente`,
    `tpv_invoice_denegada_tenant`, `tpv_invoice_ticket_no_encontrado`).
  - Maneja errores de persistencia con rollback + `HTTPException(500)`
    explícito (no `try/except: pass`).

- **`backend/app/models/erp.py` — modelo `Invoice`**: nueva columna
  `tpv_sale_id` (FK a `tpv_sales.id`, `ON DELETE SET NULL`, `unique=True`,
  indexada) + relationship `tpv_sale`. Es el enlace real factura <-> venta.

- **`backend/app/api/v1/endpoints/tpv.py` — `POST /tpv/invoice`**: ahora pasa
  `user_id=current_user.id` y `company_ids=_company_ids_for_user(db,
  current_user)` reales al servicio (antes no pasaba identidad ni tenant en
  absoluto). `GenerateInvoiceRequest.customer_data` pasa a ser opcional
  (la venta ya trae sus propios datos de cliente si los hubo).

- **Migraciones**: este proyecto usa dos mecanismos en paralelo (confirmado
  en los logs de arranque: "Migraciones idempotentes (legacy sin Alembic
  real)"; Alembic existe pero el arranque real (Railway) ejecuta
  `ensure_schema_patches()` en `app/db/base.py`, no `alembic upgrade`):
  - `backend/alembic/versions/0043_invoice_tpv_sale_link.py` — migración
    Alembic formal (documentación/histórico), idempotente, con
    `upgrade`/`downgrade`.
  - `backend/app/db/base.py` — nueva función `_migrate_invoice_tpv_sale_link()`,
    invocada desde `ensure_schema_patches()`, que añade la columna
    `tpv_sale_id` y el índice único en Postgres/SQLite si no existen. **Esta
    es la que realmente aplicará el cambio en producción** (Railway).
    Verificado explícitamente contra una tabla `invoices` "legacy" sin la
    columna (ver sección de pruebas).

### Frontend

- **`frontend/src/views/TPV.vue`**:
  - `generateInvoice()` ya no muestra un toast falso — llama de verdad a
    `POST /api/v1/tpv/invoice` con el `ticket_id` real de la última venta
    (`lastSaleTicketId`, ya existía) y los datos de cliente de esa venta
    (`lastSaleCustomerData`, nuevo `ref`, capturado en `processPayment`).
  - Maneja: sin ticket → aviso; sesión expirada → redirección a login;
    éxito → toast con número de factura y total real; ya existente → aviso
    distinto; error del backend (404/403/422/500) → toast con el `detail`
    real devuelto por la API, no un mensaje genérico.

---

## Por qué no se reinventó el cálculo de IVA

`generate_invoice` **nunca** recalcula `subtotal`/`tax_amount`/`total`: los
copia tal cual de la fila `TPVSale` ya persistida (que a su vez viene de
`fiscal_engine.persist_fiscal_sale`, ya auditado como correcto). Las líneas
de factura (`InvoiceItem`) también copian `base_amount`/`tax_amount` de
`TPVSaleItem` línea a línea, sumando el recargo de equivalencia al
`tax_amount` de la línea si existiera, sin aplicar ningún porcentaje de
nuevo.

---

## Verificación realizada

Entorno: servidor real (`uvicorn app.main:app`) contra SQLite limpio
(`zeus_test_tpv_invoice.db`), dos usuarios/empresas registrados de verdad vía
`POST /auth/register` + `POST /auth/login` (JWT real, sin atajos).

### Caso positivo — importe real (10,00 € con IVA incluido al 10 %)

1. Producto dado de alta con el mismo desglose que hace el frontend:
   `price=9.0909` (neto), `iva_rate=10.0` → `price_with_iva=9.99999`.
2. Venta real: `POST /tpv/sale` → `ticket_id=FACTURA_20260822072409`,
   `totals={"subtotal":9.0909,"iva":0.909...,"total":9.99999}`.
3. `POST /tpv/invoice {"ticket_id":"FACTURA_20260822072409", "customer_data":
   {"name":"Cliente Prueba Factura","nif":"12345678Z"}}` →
   ```
   200 OK
   {"success":true,"already_existed":false,"invoice":{
     "id":1,"invoice_number":"FRA-FACTURA_20260822072409",
     "company_id":1,"customer_id":1,
     "subtotal":9.09,"tax_amount":0.91,"total":10.0,"status":"paid", ...
   }}
   ```
   **9,09 € base + 0,91 € IVA = 10,00 € total — exactamente el importe
   cobrado, no 11,00 € ni un valor inventado.**
4. Verificado también por SQL directo contra el fichero SQLite (no solo el
   JSON de respuesta):
   ```
   invoices: (1, 'FRA-FACTURA_20260822072409', company_id=1, customer_id=1,
              tpv_sale_id=1, subtotal=9.09, tax_amount=0.91, total=10.0, status=PAID)
   invoice_items: (invoice_id=1, 'Cafe con leche', qty=1.0, unit_price=9.09,
                    tax_rate=10.0, subtotal=9.09, tax_amount=0.91, total=10.0)
   ```
5. **Idempotencia**: repetir la misma llamada devuelve
   `"already_existed": true` con el mismo `invoice.id=1` — no duplica fila.

### Caso negativo obligatorio — ticket inexistente

```
POST /tpv/invoice {"ticket_id":"TICKET_QUE_NO_EXISTE_999999","customer_data":{}}
→ 404 {"detail":"Venta no encontrada para ticket_id=TICKET_QUE_NO_EXISTE_999999"}
```
Falla de verdad, no éxito falso.

### Aislamiento multi-tenant (dos empresas reales, ambas direcciones)

- Tenant A (company_id=1) vende `FACTURA_20260822072409`; Tenant B
  (company_id=2) intenta facturarlo:
  `POST /tpv/invoice` con el token de B y ese `ticket_id` →
  `403 {"detail":"La venta no pertenece a su empresa."}`
- Tenant B vende `FACTURA_20260822072631` y genera su propia factura
  correctamente (`company_id=2`, `customer_id=2`, mismos importes 9.09/0.91/10.0).
- Tenant A intenta facturar el ticket de B → también `403`.
- Confirmado en BD: las dos facturas quedan con `company_id`/`customer_id`
  distintos y correctos, sin mezcla entre empresas.

### Migración de esquema (Postgres/SQLite reales, no solo `create_all`)

Se creó una tabla `invoices` "legacy" (sin `tpv_sale_id`, simulando el estado
actual de producción) y se ejecutó `_migrate_invoice_tpv_sale_link()`
directamente:
```
[MIGRATION] [OK] invoices.tpv_sale_id agregada
[MIGRATION] [OK] Índice único ix_invoices_tpv_sale_id creado (1 factura por venta TPV)
```
Reejecutarlo es un no-op (idempotente, confirmado). El servidor completo
también se reinició sin errores tras el cambio en `app/db/base.py`.

### Suite de tests (regresión)

- **Baseline** (antes de tocar código, mismo checkout): `7 failed, 214
  passed, 2 skipped, 3 errors`.
- **Después de la implementación**: `7 failed, 214 passed, 2 skipped, 3
  errors` — idénticos fallos preexistentes (no relacionados: config de test,
  flags de simulación de JUSTICIA/THALOS, `TestClient` no definido en
  `test_app.py`). **Sin regresión.**

### Verificación de UI (Playwright/Browser real) — limitación de entorno encontrada

Se realizó login real y flujo de venta completo con Playwright del navegador
integrado (Tenant A, producto "Cafe con leche" a 10,00 €, IVA 10 % →
subtotal 9,09 €/IVA 0,91 €/total 10,00 € visibles en la propia UI del carrito,
venta finalizada con éxito). **No se pudo confirmar el clic en "Generar
Factura" contra el código nuevo**: el servidor de previsualización de este
entorno (`preview_start`, configurado en `.claude/launch.json` del checkout
compartido `C:\Users\Acer\ZEUS-IA`) sirve el **checkout compartido**, no el
worktree aislado de este agente (`.claude/worktrees/agent-a853e64fa4c1db5e5`)
donde vive el cambio real — confirmado inspeccionando el código fuente servido
por Vite en el navegador (no contenía `lastSaleCustomerData`, variable añadida
en este cambio). Es una limitación de la infraestructura de previsualización
de este entorno de trabajo (worktree aislado vs. checkout compartido), no un
defecto encontrado en el código. La lógica que ese botón invoca es exactamente
la misma `POST /api/v1/tpv/invoice` verificada exhaustivamente por curl arriba,
y el código del botón sigue el mismo patrón (mismo `getAuthToken()`, mismo
`api.post`, mismo manejo de token expirado) que `processPayment()`, que sí se
verificó funcionando en vivo en esa misma sesión de navegador.

---

## Limitaciones / hallazgos declarados (no corregidos en este commit)

1. **`GET /api/v1/invoices/` y `get_invoice_or_404`
   (`backend/app/api/v1/endpoints/invoices.py`) no filtran por tenant/empresa
   en absoluto** (`list_invoices` no aplica ningún filtro de `company_id`;
   `get_invoice_or_404` tampoco). Es un hallazgo crítico preexistente,
   **fuera del alcance de esta tarea** (no se tocó ese archivo). No se pudo
   verificar "la factura aparece en el listado real" a través de ese
   endpoint HTTP porque, además, su dependencia de autenticación
   (`app.core.security.get_current_active_user`) tiene un bug de
   verdad **independiente de este cambio**: `jwt.decode(..., audience=
   settings.JWT_AUDIENCE, ...)` falla con `JWTError: audience must be a
   string or None` porque `settings.JWT_AUDIENCE` es una `List[str]` y la
   librería `python-jose` exige un string — cualquier token válido emitido
   hoy (`aud: zeus-ia:access`) devuelve `401` en ese endpoint. Esto coincide
   con la rama ya existente en el repo `feature/fix-jwt-audience-y-tenant-invoices`,
   lo que sugiere que ya era un hallazgo conocido antes de esta tarea. Se
   verificó en su lugar el resultado real por SQL directo contra la base de
   datos (ver arriba), confirmando que la factura queda persistida
   correctamente con los datos reales.
   **Recomendación**: abordarlo como tarea separada (arreglar la audiencia
   JWT en `app/core/security.py` y añadir el filtro de tenant que falta en
   `invoices.py`), no mezclarlo con este commit.
2. **Generación de PDF de factura**: fuera de alcance según lo acordado en la
   tarea. La factura queda persistida con datos reales (número, fecha,
   cliente, líneas, subtotal, IVA, total) pero no se genera un PDF
   específico para las facturas creadas desde TPV. El motor de PDF ya
   existente (`services/rafael_fiscal_engine_v2.py:generate_invoice_pdf_flow`,
   endpoint `POST /rafael-fiscal/invoices/{invoice_id}/generate-pdf`) opera
   sobre el mismo modelo `Invoice`, así que en principio ya es compatible con
   las facturas generadas por este puente (mismo `invoice_id`), pero no se ha
   probado end-to-end en este commit — queda como posible mejora futura, no
   como bloqueador.
3. **`customer_data` en la petición del frontend**: se envían los datos de
   cliente capturados en el momento del cobro (`prompt()` del navegador); en
   el entorno de navegador automatizado de esta sesión, `window.prompt()` no
   está soportado (`Error: prompt() is not supported.`), así que una de las
   ventas de prueba en el flujo de UI quedó como `document_type: "ticket"`
   sin nombre de cliente. Esto no afecta a la corrección del puente de
   facturación (que no depende de `document_type` de la venta, solo de que
   la venta exista y esté pagada) pero es una limitación del entorno de
   pruebas automatizadas, no del código de producción.

---

## Archivos tocados

- `backend/services/tpv_service.py` — `TPVService.generate_invoice` (reescrito) + `_invoice_result` (nuevo helper).
- `backend/app/api/v1/endpoints/tpv.py` — endpoint `POST /invoice` (pasa identidad/tenant reales) y `GenerateInvoiceRequest.customer_data` opcional.
- `backend/app/models/erp.py` — `Invoice.tpv_sale_id` (nueva columna + relationship).
- `backend/app/db/base.py` — `_migrate_invoice_tpv_sale_link()` (nuevo parche de esquema idempotente) + registro en `ensure_schema_patches()`.
- `backend/alembic/versions/0043_invoice_tpv_sale_link.py` — migración Alembic formal equivalente.
- `frontend/src/views/TPV.vue` — `generateInvoice()` real, `lastSaleCustomerData` (nuevo ref).

## Rollback

Sin riesgo de datos: la columna nueva es `nullable=True`, no rompe filas
existentes. `downgrade()` de la migración 0043 elimina el índice único, la
restricción y la columna si hiciera falta revertir. No se ha tocado ninguna
migración ya aplicada en producción — es puramente aditivo.

---

## Revisión independiente (2026-08-23)

**Veredicto: ✅ APROBADO.**

El revisor cerró exactamente el hueco que el ejecutor había declarado no poder cubrir: resolvió el mismo problema de entorno (preview sirviendo el checkout compartido) con el mecanismo ya establecido en esta sesión (junction de `node_modules` + Vite propio en el worktree), y **completó el clic real del botón "Generar Factura" en el navegador** — login real, venta de 10€ en el carrito, pago, clic real, `POST /tpv/invoice → 200` capturado por red con `total:10.0`, factura persistida en BD. Repitió también el caso negativo (ticket inexistente → 404), el aislamiento cruzado (403 en ambas direcciones, con sus propios tenants) y la idempotencia (incluida por clic real repetido, no solo por curl) — todo con datos 100% propios.

**Matiz corregido, no bloqueante**: la afirmación del informe original de que "Alembic no se ejecuta en el deploy real" era imprecisa — `Dockerfile`/`railway.toml` sí invocan `alembic upgrade head`, pero en el escenario legacy real de este proyecto el script previo hace `stamp head` (no `upgrade` real) tras `ensure_schema_patches()`, por lo que el parche de `base.py` sigue siendo, en la práctica, el mecanismo que aplica el cambio. Confirmado por el propio revisor leyendo `scripts/alembic_conditional_stamp.py` — no es un defecto funcional, solo una imprecisión narrativa.

Suite de tests idéntica al baseline, corrida de forma independiente. Hallazgo preexistente de `GET /invoices/` (bug de audiencia JWT + tenant, ya trackeado en otra rama) confirmado real pero no bloqueante para este cierre.

## CERRADO

**Rama final:** `feature/facturacion-tpv-real`, commits `d89f8f5` + `24f4a10`, sobre `main`. Sin merge ni push.
