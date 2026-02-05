# ROCE — Eliminación candado hardcodeado WhatsApp (Twilio)

**Fecha**: 2026-01-23  
**Tarea**: Auditoría y eliminación de candado hardcodeado en WhatsApp.

---

## 1. Punto exacto del candado (eliminado)

**Archivo**: `backend/services/whatsapp_service.py`  
**Líneas (antes)**: 77–102  

**Lógica eliminada**:
```python
# Verificar si está en sandbox (número por defecto)
is_sandbox = "14155238886" in self.whatsapp_number or "sandbox" in self.whatsapp_number.lower()

if is_sandbox:
    # BLOQUEAR: Sandbox solo para pruebas
    ActivityLogger.log_activity(...)
    return {"success": False, "error": "WhatsApp en modo sandbox...", "blocked": True, ...}
```

**Problema**: El bloqueo dependía solo del número (`14155238886` o la palabra "sandbox"). Se ignoraban `WHATSAPP_SANDBOX_MODE` y `ENVIRONMENT`, por lo que con variables correctas el envío podía seguir bloqueado si el número era el de sandbox.

---

## 2. Cambios realizados

### 2.1 Fuente de verdad: solo ENV VARS

**Añadido** (líneas 22–39):

- `_whatsapp_sandbox_mode()`: lee `WHATSAPP_SANDBOX_MODE` (default `"false"`). True solo si valor en `("true", "1", "yes")`.
- `_environment_is_production()`: lee `ENVIRONMENT` o `RAILWAY_ENVIRONMENT`. True solo si `"production"`.
- `_send_allowed()`:  
  - Si `WHATSAPP_SANDBOX_MODE=true` → no permitir envío.  
  - Si `ENVIRONMENT=production` y no sandbox → permitir.  
  - En resto de casos → permitir (misma lógica que antes para no producción).

Regla aplicada: **Si WHATSAPP_SANDBOX_MODE=false y ENVIRONMENT=production → enviar SIEMPRE.**

### 2.2 Bloqueo solo por env

**Reemplazo** (antes 77–102, ahora 104–135):

- Se deja de usar `"14155238886" in self.whatsapp_number` y cualquier comprobación por número.
- Bloqueo únicamente cuando `not _send_allowed()` (es decir, cuando `WHATSAPP_SANDBOX_MODE=true`).
- Al bloquear se registra en `AgentActivity` con `reason: "env_block"` y se incluyen en `details`: `WHATSAPP_SANDBOX_MODE`, `ENVIRONMENT`.
- Mensaje de error explícito: indica causa y que para producción hay que usar `WHATSAPP_SANDBOX_MODE=false` y `ENVIRONMENT=production`.

### 2.3 Log antes del envío

**Añadido** (antes de `self.client.messages.create(...)`):

```python
logger.info(
    "[WHATSAPP] WHATSAPP_SEND_ALLOWED=true | mode=%s | env=%s | to=%s",
    "sandbox" if sandbox_mode else "production",
    "production" if env_production else os.getenv("ENVIRONMENT", "NOT_SET"),
    to_number,
)
```

Solo se ejecuta cuando `send_allowed` es True, por tanto el log equivale a **WHATSAPP_SEND_ALLOWED=true** cuando se envía.

### 2.4 get_status() basado en env

**Antes**: `"sandbox_mode": "whatsapp:+14155238886" in self.whatsapp_number`  
**Ahora**:  
- `sandbox_mode`: `_whatsapp_sandbox_mode()`  
- `send_allowed`: `_send_allowed()`  
- Se exponen `WHATSAPP_SANDBOX_MODE` y `ENVIRONMENT` en la respuesta.

---

## 3. Resumen de reglas aplicadas

| Regla | Cumplimiento |
|-------|----------------|
| Eliminar hardcode que fuerce sandbox | Sí: eliminado el check por número `14155238886` / "sandbox". |
| Única fuente de verdad = ENV VARS | Sí: solo se usan `WHATSAPP_SANDBOX_MODE` y `ENVIRONMENT`/`RAILWAY_ENVIRONMENT`. |
| WHATSAPP_SANDBOX_MODE=false y ENVIRONMENT=production → enviar SIEMPRE | Sí: en ese caso `_send_allowed()` es True y no se bloquea. |
| Condicionales basados en env | Sí: bloqueo solo con `not _send_allowed()` (env). |
| Log explícito antes del envío (modo sandbox/production) | Sí: `logger.info(..., WHATSAPP_SEND_ALLOWED=true, ...)`. |
| Si se bloquea, error con causa exacta | Sí: `cause` y mensaje indican env (WHATSAPP_SANDBOX_MODE/ENVIRONMENT). |

---

## 4. Prueba manual recomendada

1. En Railway (o entorno objetivo):  
   - `WHATSAPP_SANDBOX_MODE=false`  
   - `ENVIRONMENT=production`  
   - `TWILIO_WHATSAPP_NUMBER` con número productivo (no sandbox).
2. Llamar al endpoint de envío de WhatsApp (o flujo que use `whatsapp_service.send_message()`).
3. Verificar:  
   - Envío exitoso.  
   - En logs: línea con `WHATSAPP_SEND_ALLOWED=true`.  
   - En `get_status()`: `send_allowed: true`, `sandbox_mode: false`.

---

## 5. Archivo modificado

- **backend/services/whatsapp_service.py**: candado por número eliminado; lógica de bloqueo y estado basada solo en ENV VARS; log y mensaje de error explícitos.

**Estado**: Candado hardcodeado eliminado. Comportamiento gobernado solo por variables de entorno.
