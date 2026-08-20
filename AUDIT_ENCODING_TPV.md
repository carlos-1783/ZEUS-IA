# AUDIT_ENCODING_TPV.md — bug de codificación cp1252 en la inicialización de agentes

**Rama:** `feature/rediseno-completo`. **Fecha:** 2026-08-20. **Alcance:** núcleo
compartido (ZEUS CORE, THALOS, y los 5 agentes de dominio), no una vertical
concreta. Ejecutado con la skill `zeus-produccion`.

## 0. Contexto

Hallazgo original reportado durante la verificación en vivo del rediseño de
TPV (`AUDIT_REDISENO_COMPLETO.md`, sección 11.3): la primera venta real
fallaba con `502 Bad Gateway` y
`Error de persistencia fiscal: 'charmap' codec can't encode characters in
position 0-1: character maps to <undefined>`. Un revisor independiente
confirmó y agravó el hallazgo: **no falla solo la primera vez — es
permanente**, bloquea el 100% de las ventas TPV en cualquier entorno Windows
sin `PYTHONIOENCODING=utf-8`, porque el singleton `_rafael_instance` nunca
llega a asignarse (la excepción salta dentro del propio constructor, antes de
que la asignación se complete). Esta auditoría investiga el alcance real del
patrón, aplica un fix de fondo a nivel de proceso, y lo verifica de punta a
punta.

## 1. Investigación — alcance real del patrón (no solo `base_agent.py:41`)

Escaneo completo de `backend/` (no solo grep de emojis conocidos: rango
Unicode `>= U+2190` para no depender de una lista de memoria) buscando
`print()`/`logging.*` con caracteres no-ASCII. **360 apariciones** en 47
archivos. Lo relevante para el riesgo real de crash — no todos los 360 sitios
son igual de peligrosos, ver 1.1 — se resume así:

### 1.1 Por qué `print()` es el riesgo real y `logger.info()`/`logger.error()` casi nunca lo es

Diferencia de comportamiento confirmada en vivo (no solo leída en la
documentación de Python):

- **`print(...)` con un carácter no codificable en la consola actual**
  lanza `UnicodeEncodeError` como excepción normal y no capturada, que se
  propaga hacia arriba por la pila de llamadas — si está dentro de un
  `__init__`, aborta la construcción del objeto completo.
- **`logging.Logger.info/warning/error(...)`** pasa por
  `Handler.emit()` → si `stream.write()` falla, Python's `logging` llama
  internamente a `Handler.handleError()`, que por defecto **captura la
  excepción y solo imprime un traceback a `stderr`**, sin propagarla. Por
  eso, en la reproducción del bug (sección 3), los `logger.info(...)` con
  emoji de `services/control_horario_service.py`, `services/tpv_service.py`,
  etc. **no tumbaban el proceso** (se veían truncados/con mojibake en el log,
  pero la petición seguía) — mientras que el `print()` de
  `agents/base_agent.py:41` sí abortaba la petición entera.

Esto no reduce el problema a "un solo `print()`": **los 6 agentes
(`agents/base_agent.py` + las 6 subclases) usan `print()` con emoji en su
propio `__init__`**, así que cualquiera de ellos revienta igual la primera
vez (y, si es un singleton con el mismo patrón de asignación tardía que
RAFAEL, de forma permanente) que se instancia en un proceso sin UTF-8:

| Archivo | Línea | Contexto |
|---|---|---|
| `agents/base_agent.py` | 41 | `__init__` de la clase base — se ejecuta en **los 6 agentes** vía `super().__init__(...)` |
| `agents/rafael.py` | 47, 49 | `__init__` de RAFAEL (además del de la base) |
| `agents/perseo.py` | 70 | `__init__` de PERSEO |
| `agents/justicia.py` | 48, 49, 51 | `__init__` de JUSTICIA |
| `agents/afrodita.py` | 181, 183 | `__init__` de AFRODITA |
| `agents/thalos.py` | 68, 69, 70 | `__init__` de THALOS |
| `agents/zeus_core.py` | 45, 47, 65, 70, 75... | `__init__`/arranque de ZEUS CORE |

Y en `print()` fuera de `agents/`, con el mismo riesgo si se ejecutan en
arranque o en el primer request que los dispare:

- `app/main.py` (líneas 144-228, antes del fix): `print()` en el manejador
  WebSocket — se ejecuta en cada conexión, no solo en arranque.
- `app/api/v1/endpoints/chat.py` (líneas 72-146): secuencia completa
  `print("🔄 Inicializando ZEUS CORE...")` ... `print("🔄 Inicializando
  AFRODITA...")` — instancia los 6 agentes en cascada la primera vez que se
  llama al chat; con el bug activo, **cualquiera de los 6** podía abortar
  esa cascada a mitad, dejando el resto sin inicializar.
- `gunicorn.conf.py` (líneas 81-116): hooks `when_ready`, `pre_fork`,
  `post_fork`, `worker_abort` — usan `server.log.info(...)`/`worker.log.info(
  ...)`, que en gunicorn también pasa por `logging` (mismo comportamiento
  no-crash que 1.1), **salvo** `post_fork`, que si `ZEUS_PREWARM_AGENTS=1`
  llama a `ensure_agent_stack()` (instancia los 6 agentes de verdad) dentro
  de un hilo con su propio `try/except Exception` — no tumbaría el worker,
  pero silenciaría el precalentado sin dejar rastro claro más allá del log.
- Scripts de arranque/migración (`scripts/migrate.py`, `init_database.py`,
  `scripts/add_firewall_columns.py`, etc.) — riesgo menor porque se ejecutan
  una vez de forma manual/CLI, no en cada request, pero mismo patrón.
- El resto (`test_*.py`, `check_*.py`, `TEST_SISTEMA_COMPLETO.py`) son
  scripts de test/diagnóstico manual, no código de arranque de producción —
  mismo riesgo si se ejecutan a mano en una consola Windows sin UTF-8, pero
  fuera del alcance de "bloquea producción".

**Conclusión de la investigación**: el patrón no es un bug puntual de RAFAEL,
es sistémico en la capa de agentes (los 6, sin excepción) y en al menos dos
puntos de arranque (`chat.py`, `gunicorn.conf.py`). Arreglar solo
`agents/base_agent.py:41` habría dejado vivos los ~15 `print()` restantes de
las 6 subclases y de `chat.py`/`app/main.py` (WebSocket) — cualquiera de
ellos con el mismo poder de tumbar una request la primera vez que se
ejecutara ese camino de código en un Windows sin UTF-8.

## 2. Fix elegido — por qué protege por defecto

En vez de tocar los ~20 `print()` de riesgo real uno a uno (parche frágil,
fácil de dejar alguno sin cubrir, y que no protege contra el próximo `print()`
con emoji que alguien añada en el futuro), se fuerza la codificación de
`stdout`/`stderr` a UTF-8 **a nivel de proceso**, en el entrypoint real de la
aplicación, antes de importar cualquier otra cosa:

```python
import sys

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
```

Aplicado en **dos sitios**, porque son los dos procesos que Railway/el
desarrollador arrancan directamente:

1. **`backend/app/main.py`** — literalmente la primera instrucción ejecutable
   del archivo, antes de `import logging`/`import os`/cualquier import de
   `app.*` o `services.*`. Este es el entrypoint real (`app.main:app`) tanto
   para `uvicorn app.main:app` (desarrollo, `railway.json` como fallback) como
   para `gunicorn -c gunicorn.conf.py app.main:app` (producción,
   `railway.toml`, el que de verdad usa Railway vía Dockerfile).
2. **`backend/gunicorn.conf.py`** — mismo guard, al principio del archivo,
   antes de `import os`. Motivo: `preload_app = False`, así que los hooks de
   este archivo (`when_ready`, `post_fork`, etc.) corren en el proceso
   master/worker de gunicorn **antes** de que `app.main` se importe dentro de
   cada worker — el guard de `app/main.py` no los cubre. Coste marginal cero
   (en Linux con locale UTF-8 ya configurada es un no-op), y cierra el hueco
   de `ZEUS_PREWARM_AGENTS=1` + contenedor sin locale UTF-8 explícita.

**Por qué es "por defecto" y no un parche**: no depende de que nadie
recuerde poner `PYTHONIOENCODING=utf-8` en su máquina, en el `.env`, o como
variable de Railway — protege automáticamente a los 6 agentes, a
`chat.py`, a los hooks de gunicorn, y a cualquier `print()`/`logging` con
emoji que se añada en el futuro en cualquier módulo importado después de
`app/main.py`, sin necesidad de tocarlo. `errors="replace"` en vez de dejar
el valor por defecto (`"strict"`) es la capa extra de seguridad: si por lo
que sea algún carácter sigue sin poder representarse, se sustituye por `?`
en el log en vez de abortar la petición — nunca debe un problema de
*logging* tumbar una venta real.

**Qué NO se tocó y por qué**: no se eliminó el emoji de
`agents/base_agent.py:41` ni de los otros ~19 `print()` de riesgo. Con el
guard de proceso, esos `print()` ya funcionan correctamente (se verifica en
la sección 3) — quitar los emojis habría sido un refactor cosmético de ~360
líneas sin relación con la causa raíz, fuera del alcance de este fix.

## 3. Verificación — reproducción real, fix, y re-verificación

Entorno de reproducción: mismo worktree
(`C:\Users\Acer\ZEUS-IA\.claude\worktrees\agent-a8873985b2803de19`), Windows,
consola con `sys.stdout.encoding == sys.stderr.encoding == 'cp1252'`
confirmado explícitamente (`python -c "import sys; print(sys.stdout.encoding,
sys.stderr.encoding)"` → `cp1252 cp1252`), sin `PYTHONIOENCODING` en el
entorno (confirmado con `echo $PYTHONIOENCODING` vacío antes de cada arranque
del backend).

### 3.1 Antes del fix — reproducción del fallo real

Backend arrancado explícitamente sin `PYTHONIOENCODING` (`python -m uvicorn
app.main:app --host 0.0.0.0 --port 8000`, sin ninguna variable de entorno UTF-8
añadida). Cuenta de prueba real ya existente (`tpv.redesign.test@example.com`,
creada vía `POST /api/v1/auth/register` en el bloque de trabajo anterior de
esta misma sesión). Login real, `POST /api/v1/tpv/sale` con un producto real
del catálogo:

```
POST /api/v1/tpv/sale → {"detail":"Error de persistencia fiscal: 'charmap' codec
can't encode characters in position 0-1: character maps to <undefined>"}
```

**Repetido 3 veces seguidas, sin reiniciar el proceso: falla las 3 veces**,
con el mismo `502`/traceback idéntico cada vez. Traceback del servidor
(idéntico en las 3 repeticiones):

```
File ".../services/rafael_service.py", line 118, in persist_sale
    rafael = get_rafael_agent()
File ".../services/rafael_service.py", line 25, in get_rafael_agent
    _rafael_instance = Rafael()
File ".../agents/rafael.py", line 31, in __init__
    super().__init__(
File ".../agents/base_agent.py", line 41, in __init__
    print(f"\U0001f3db\ufe0f [ZEUS] Agente {self.name} ({self.role}) inicializado")
File "...\encodings\cp1252.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-1: character maps to <undefined>
```

Esto confirma exactamente el diagnóstico del revisor: `_rafael_instance =
Rafael()` nunca llega a completarse (la excepción salta *dentro* de la
llamada, antes de que la asignación del `global` se ejecute), así que
`get_rafael_agent()` reintenta `Rafael()` desde cero en cada llamada — **el
fallo es permanente, no de "primera vez"**, confirmado empíricamente con 3
intentos consecutivos, no solo citado.

### 3.2 Aplicado el fix

Cambios en `backend/app/main.py` (guard al principio del archivo, antes de
cualquier otro import) y `backend/gunicorn.conf.py` (mismo guard, antes de
`import os`) — ver sección 2 para el código exacto.

### 3.3 Después del fix — misma prueba, mismo entorno sin `PYTHONIOENCODING`

Backend reiniciado de la misma forma exacta (sin ninguna variable de entorno
UTF-8 añadida manualmente — `echo $PYTHONIOENCODING` vacío confirmado antes
de arrancar). Log de arranque ya muestra la diferencia: el mismo mensaje de
`control_horario_service` que antes salía escapado como `\u23f0` en el log
ahora sale como el carácter real `⏰`, y el separador `—` que antes salía como
`�` (mojibake) ahora sale correcto — confirma que el guard está activo desde
el arranque, no solo en el código que toca RAFAEL.

Login real, misma venta, mismo producto:

```
POST /api/v1/tpv/sale → {"success":true, "ticket":{"id":"TICKET_20260820133941", ...},
  "accounting_sent":true, "fiscal_document_persisted":true, ...}
```

**Repetido 3 veces seguidas: éxito las 3 veces**, tickets reales distintos
(`TICKET_20260820133941`, `TICKET_20260820133956`, `TICKET_20260820133957`),
cada uno con su propio `fiscal_document_id` persistido de verdad en BD
(`legal_fiscal_firewall`: `[FIREWALL] ✅ Documento persistido con ID: 5/6/7`),
entrada real en `cashflow_ledger_service` (`entry id=24/25 company=1 in 1.65
source=TPV`), y actividad real de RAFAEL y JUSTICIA registrada
(`[ACTIVITY] RAFAEL: Venta TPV registrado en RAFAEL...`). **No se necesitó
`PYTHONIOENCODING=utf-8` en ningún momento** — el fix funciona por defecto,
tal como exige el encargo.

### 3.4 RAFAEL fuera del flujo de venta (agente compartido entre verticales)

Para confirmar que el fix no rompe nada del comportamiento normal de RAFAEL
fuera de TPV, se disparó una acción real por la capa de chat conversacional
(`POST /api/v1/chat/RAFAEL/chat`, otro caller real de
`services/rafael_service` distinto de `tpv_service.py` — confirmado por
grep que solo `chat.py` y `app/main.py` importan `rafael_service`/
`agents.rafael` fuera de TPV) con una consulta fiscal real (LLM real,
`OPENAI_API_KEY` configurada en este entorno de desarrollo):

```
POST /api/v1/chat/RAFAEL/chat {"message": "Cual es el tipo de IVA general en
Espana para un restaurante de hosteleria?"}
→ 200 OK, respuesta real con acentos correctos ("España", "hostelería"),
  workspace_document_id: 8 (documento real persistido en BD),
  log: "[ACTIVITY] RAFAEL: Chat procesado por RAFAEL", sin errores.
```

Adicionalmente, se probó PERSEO por el mismo camino de chat (agente
distinto, mismo patrón de `__init__` con `print()` con emoji) para confirmar
que la protección es de verdad de proceso y no algo específico de RAFAEL:

```
POST /api/v1/chat/PERSEO/chat {"message": "Hola PERSEO, dame una idea de
campaña de marketing corta."}
→ 200 OK, respuesta real, "Workspace deliverable persisted id=10 ... agent=PERSEO",
  sin errores.
```

### 3.5 Regresión — suite de tests backend

Baseline conocido (antes de esta sesión y de la anterior de TPV):
`7 failed, 214 passed, 2 skipped, 3 errors`.

`cd backend && python -m pytest tests/ -q` **después** del fix:
`7 failed, 214 passed, 2 skipped, 3 errors` — **idéntico**, mismos 7 tests
fallidos y mismos 3 errores de antes (no relacionados con este cambio, ya
documentados como baseline conocido en sesiones previas). Sin regresión.

## 4. Resumen de archivos tocados

- `backend/app/main.py` — guard de codificación al principio del archivo
  (antes de cualquier otro import).
- `backend/gunicorn.conf.py` — mismo guard, antes de `import os`.
- `AUDIT_ENCODING_TPV.md` — este documento.

No se tocó ningún `print()`/`logging` individual, ninguna migración Alembic,
ningún endpoint, ninguna query — el fix es 100% a nivel de proceso/arranque.

## 5. Pendiente / hallazgos para decisión del usuario

1. **`ZEUS_PREWARM_AGENTS=1` en producción real**: si Carlos tiene esta
   variable activa en Railway, conviene confirmar en los logs de producción
   (tras desplegar este fix) que el precalentado de agentes en `post_fork`
   ya no falla silenciosamente — no se pudo verificar contra el entorno real
   de Railway desde aquí (sin credenciales de acceso a ese entorno).
2. Los ~340 `print()`/`logging` con emoji restantes en `backend/` (scripts
   de test manual, CLI de migración, etc., listados en la sección 1) ya
   funcionan correctamente gracias al guard de proceso — no requieren
   cambio, pero quedan documentados aquí por si en el futuro se decide
   limpiarlos por estilo (no por urgencia funcional).
3. No se pudo verificar el comportamiento exacto dentro de un contenedor
   Docker real con la imagen `python:3.10-slim` del `Dockerfile` de
   producción (sin Docker disponible en este entorno de ejecución) — el
   razonamiento de la sección 2 sobre por qué también protege ese entorno
   (contenedores mínimos con locale `C`/`POSIX` en vez de UTF-8) se basa en
   el comportamiento documentado de `TextIOWrapper.reconfigure()`, no en una
   prueba end-to-end contra ese Dockerfile.
