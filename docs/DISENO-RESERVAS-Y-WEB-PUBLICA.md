# Diseño: Reservas web + Web pública por cliente (todas las empresas)

## 1. Flujo de negocio: Reservas web + WhatsApp + TPV

- **Cliente final** entra en la web pública del negocio (ej. `tudominio.com/p/mi-restaurante` o en el futuro subdominio).
- Ve nombre del negocio, opción **Reservar mesa**: formulario (nombre, teléfono, email, fecha, hora, comensales, notas).
- Al enviar:
  - Se crea una **reserva** en estado `pending`.
  - (Fase 2) Integración WhatsApp: se envía mensaje de confirmación al teléfono del cliente y al negocio.
- En **TPV** (dueño/empleado):
  - Lista **Reservas del día**.
  - Acción **Abrir como mesa X**: asigna la reserva a una mesa y pasa la reserva a estado `seated`; la mesa queda con la info del cliente por si quieren usarla en el ticket.

Todo es **multi-tenant por negocio** (`user_id` = dueño del negocio). Cualquier cliente con plan puede activar web pública y reservas; si no la necesita, deja la opción desactivada.

---

## 2. Web pública por empresa (Opción B para todos)

- Cada **cliente** (User owner con company_name/plan) puede tener:
  - **Web pública activada o no** (`public_site_enabled`).
  - Si está activada: **slug único** (`public_site_slug`) que define la URL: `/p/{slug}`.
- Si **no la necesita**: `public_site_enabled = false` → la ruta `/p/{slug}` no existe o devuelve 404 para ese slug; no se crea ninguna web.
- Contenido de la web cuando está activa:
  - Nombre del negocio (company_name o full_name).
  - Sección **Reservar mesa** (formulario) si el negocio tiene TPV con mesas / acepta reservas.
  - (Futuro: horarios, carta, etc.)

---

## 3. Modelo de datos

- **User** (ampliado):
  - `public_site_enabled`: bool, default False.
  - `public_site_slug`: string, único, nullable. Obligatorio si `public_site_enabled` es True.
- **Reservation** (nueva tabla):
  - `user_id` (dueño del negocio)
  - `guest_name`, `guest_phone`, `guest_email`
  - `reservation_date` (date), `reservation_time` (string, ej. "20:00")
  - `num_guests` (int), `notes` (opcional)
  - `status`: pending | confirmed | cancelled | no_show | seated
  - `table_id` o `table_name` (nullable; se rellena al "abrir como mesa")
  - `source`: web | manual
  - `confirmed_at` (nullable), `created_at`

---

## 4. API

- **Público (sin auth)**:
  - `GET /api/v1/p/{slug}/info` → { name, reservations_enabled }. 404 si slug no existe o web desactivada.
  - `POST /api/v1/p/{slug}/reservations` → body: guest_name, guest_phone, guest_email, reservation_date, reservation_time, num_guests, notes → crea reserva pending.
- **Autenticado (TPV)**:
  - `GET /api/v1/tpv/reservations?date=YYYY-MM-DD` → lista reservas del día del usuario.
  - `PATCH /api/v1/tpv/reservations/{id}/seat` → body: { table_id o table_name } → status=seated, asigna mesa.
- **Admin**: en `PATCH /admin/customers/{id}` permitir `public_site_enabled` y `public_site_slug` (validar unicidad del slug).

---

## 5. Frontend

- **Ruta pública** `/p/:slug`:
  - Llama a `GET /p/{slug}/info`. Si 404 o reservations_enabled false, mostrar "Web no disponible" o solo nombre sin formulario.
  - Si reservations_enabled true, mostrar formulario; al enviar, `POST /p/{slug}/reservations` y mensaje de éxito.
- **TPV** (vista existente):
  - Bloque "Reservas del día" (lista por fecha).
  - Botón "Abrir como mesa X" que abre modal o dropdown para elegir mesa y llama a `PATCH .../seat`.
- **Admin / Ajustes**: toggle "Web pública" + campo slug (y en Admin al editar cliente, mismos campos).

---

## 6. Confirmación WhatsApp (fase 2)

- Cuando exista integración WhatsApp configurada: al crear reserva (o al confirmar desde backoffice), enviar mensaje al `guest_phone` y notificación al negocio.
- Mientras tanto: el flujo funciona sin WhatsApp; la confirmación puede ser solo la pantalla de éxito en la web.
