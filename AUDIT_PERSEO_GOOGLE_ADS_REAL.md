# Auditoría puntual — PERSEO / Google Ads (`create_google_campaign`)

**Rama de trabajo**: `feature/consolidacion-final` (worktree
`C:\Users\Acer\ZEUS-IA\.claude\worktrees\consolidacion-final`)
**Commit base al empezar**: `038096f`
**Fecha**: 2026-08-27

## 1. Hallazgo recibido (según `AUDITORIA_TOTAL_FINAL.md`, sección 1, fila PERSEO)

Se me pidió corregir `create_google_campaign()` en
`backend/services/perseo_ads_engine_v2.py` porque, según el hallazgo, cuando
`_google_configured()` devolvía `True` la función respondía:

```python
{"success": true, "campaign_id": None, "simulated": False,
 "message": "Google Ads API client not installed — campaign persisted locally only"}
```

sin llamar nunca a la API real de Google Ads — un éxito falso que además
mentía activamente con `simulated: False`.

## 2. Verificación del estado real del código (antes de tocar nada)

Siguiendo la regla de la skill `zeus-produccion` de **no confiar ciegamente en
la descripción de la tarea y verificar el estado actual del código**, leí el
archivo completo:

`backend/services/perseo_ads_engine_v2.py` líneas 26-89 (estado en commit
`038096f`, HEAD de esta rama al empezar).

**Resultado: el hallazgo YA estaba corregido en esta misma rama**, en el
commit:

```
2346230 fix(perseo): Google Ads campaign creation fails honestly instead of fake success
Author: carlos-1783 <marketingdigitalper.seo@gmail.com>
Date:   Tue Aug 18 01:09:24 2026 +0200
```

Confirmado que `2346230` es ancestro de `HEAD` (`git merge-base --is-ancestor
2346230 HEAD` → `IS ANCESTOR`), es decir, el fix ya forma parte de la historia
de `feature/consolidacion-final` y no ha sido revertido posteriormente.

El código actual (líneas 66-89) es:

```python
def create_google_campaign(
    *,
    name: str,
    daily_budget_micros: int = 10_000_000,
) -> Dict[str, Any]:
    _ = name, daily_budget_micros
    if not _google_configured():
        raise HTTPException(status_code=503, detail={"error": "google_ads_not_configured"})
    # GOOGLE_ADS_CUSTOMER_ID / GOOGLE_ADS_DEVELOPER_TOKEN están presentes, pero no
    # existe cliente real de la Google Ads API integrado (no hay librería
    # `google-ads` en requirements.txt ni llamada HTTP real como en Meta Ads).
    # Devolver success=True aquí sería un falso-éxito: la campaña NUNCA se crea
    # en Google Ads. Fallar de forma explícita en su lugar.
    raise HTTPException(
        status_code=501,
        detail={
            "error": "google_ads_client_not_implemented",
            "message": (
                "Google Ads API client no está implementado — la campaña NO se ha "
                "creado en Google Ads. Falta integración real (librería google-ads "
                "y flujo OAuth) antes de poder crear campañas reales."
            ),
        },
    )
```

Búsqueda exhaustiva en todo `backend/` de la cadena exacta citada en el
hallazgo (`"not installed"`, `"persisted locally only"`) no encontró ninguna
coincidencia — ese texto no existe en el estado actual del repositorio.

**Conclusión**: la fila "PERSEO" de `AUDITORIA_TOTAL_FINAL.md` (presente en la
raíz de este worktree) describe un estado de código **anterior** al commit
`2346230` y está desactualizada en este punto concreto. La frase de esa
auditoría "el hallazgo histórico de PERSEO/Google Ads sigue sin resolverse de
raíz (solo se añadió un guard de "no configurado" que oculta el problema en el
caso común, no lo elimina)" no se corresponde con lo que hay en el árbol de
`feature/consolidacion-final`: el guard no "oculta" el problema, lo convierte
en un fallo explícito (503/501) tanto si está configurado como si no.

## 3. Investigación de credenciales / SDK real de Google Ads

Para decidir si procedía implementar la llamada real (punto 2 de la tarea) o
solo verificar el fallo honesto (punto 3), comprobé:

- **`requirements.txt`**: no contiene `google-ads` ni ningún paquete
  `google-ads-*`. `pip show`/`import google.ads` en el venv compartido
  (`C:\Users\Acer\ZEUS-IA\backend\venv`) confirma
  `ModuleNotFoundError: No module named 'google'`.
- **Variables de entorno reales**: no hay ninguna variable `GOOGLE_ADS_*`
  definida en el entorno de este agente ni en `backend/.env*` ni en
  `app/core/config.py`. `_google_configured()` solo comprueba
  `GOOGLE_ADS_CUSTOMER_ID` y `GOOGLE_ADS_DEVELOPER_TOKEN`, que **no bastan**
  para una integración real: el flujo OAuth2 server-to-server de la Google
  Ads API además requiere `client_id`, `client_secret`, `refresh_token` (y
  normalmente `login_customer_id`), ninguno de los cuales se comprueba ni
  existe en este proyecto todavía.
- Esto confirma lo que la skill `zeus-produccion` ya documenta: Google es una
  credencial "conocida como pendiente de configurar" — no había forma de
  probar una llamada real end-to-end en este entorno, y no se deben inventar
  credenciales.

**Decisión**: no implementé la llamada real a la Google Ads API en este step.
Motivos:
1. El comportamiento honesto exigido por la tarea (nunca `success:true` +
   `simulated:false` sin ejecución real) **ya está garantizado** por el
   código actual — no hay regresión ni simulación activa que corregir.
2. Escribir el cliente OAuth2 + `google-ads` SDK sin ninguna credencial real
   ni sandbox de Google Ads para probarlo sería código no verificable end-to-
   end, lo que — según la propia regla de la skill ("si un módulo no ejecuta
   de verdad, no existe") — podría convertirse en una nueva forma de
   "aparenta funcionar" si contiene errores en la construcción de las
   llamadas protobuf, sin ningún test que lo detecte. Añadir una dependencia
   nueva (`google-ads`, con sus sub-dependencias de protobuf/grpc) y un flujo
   OAuth completo es un cambio de alcance mayor que esta tarea puntual, y
   además `_google_configured()` tendría que ampliarse para exigir las
   credenciales OAuth reales, cambio que afecta al contrato de la función.
3. Esto encaja con la instrucción del propio prompt de esta tarea: si arreglar
   algo requiere tocar algo fuera de alcance, parar y preguntar en vez de
   hacerlo silenciosamente en el mismo commit.

**Hallazgo adicional a decidir con el usuario** (no implementado, solo
señalado): si se quiere una integración real de Google Ads, hace falta:
- Añadir `google-ads` a `requirements.txt` e instalarlo en el venv compartido.
- Ampliar `_google_configured()` para exigir también
  `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`
  (y `GOOGLE_ADS_LOGIN_CUSTOMER_ID` si se opera bajo MCC).
- Implementar la llamada real (`CampaignBudgetService` + `CampaignService`
  `mutate`), con manejo de errores de la API (que devuelve `GoogleAdsException`
  con detalles estructurados, no un simple HTTP status).
- Conseguir una cuenta de prueba de Google Ads (test account) para poder
  verificar end-to-end antes de darlo por cerrado.

## 4. Verificación reproducida (punto 4 de la tarea)

Se forzó el branch "configurado" con variables de entorno de prueba (no
credenciales reales) y se comprobó el comportamiento actual:

### 4.1 `_google_configured()` con env vars de prueba

```
$ GOOGLE_ADS_CUSTOMER_ID="1234567890" GOOGLE_ADS_DEVELOPER_TOKEN="fake-test-token-not-real" \
  python -c "from services.perseo_ads_engine_v2 import _google_configured; print(_google_configured())"
True
```

### 4.2 `create_google_campaign()` con el branch "configurado" activo

```
google_configured: True
HONEST FAILURE -> status_code=501 detail={'error': 'google_ads_client_not_implemented',
  'message': 'Google Ads API client no está implementado — la campaña NO se ha creado
  en Google Ads. Falta integración real (librería google-ads y flujo OAuth) antes de
  poder crear campañas reales.'}
```

Nunca se observó `success: true` ni `campaign_id: None` ni `simulated: False`
en la respuesta — el caso exacto de la auditoría **no se reproduce** en el
estado actual del código.

### 4.3 `create_google_campaign()` sin configurar (caso base)

```
google_configured (no env vars): False
HONEST FAILURE (not configured) -> 503 {'error': 'google_ads_not_configured'}
```

### 4.4 End-to-end vía `create_ad_campaign()` con `execution_mode=REAL`, `writes_enabled=True`

Se monkeypencheó `get_execution_status` para simular un tenant en modo
producción real (writes habilitados) y se confirmó que el flujo completo
(`create_ad_campaign` → `create_google_campaign`) sigue fallando de forma
honesta y nunca produce un éxito falso:

```
HONEST FAILURE (end-to-end via create_ad_campaign) -> status_code=501
detail={'error': 'google_ads_client_not_implemented', 'message': '...'}
```

### 4.5 Test de regresión permanente añadido

Se añadió `backend/tests/test_perseo_ads_engine_v2_google.py` con 3 casos que
fijan este comportamiento como contrato y evitan que el bug reaparezca:

- `test_google_campaign_not_configured_fails_honestly` → 503
  `google_ads_not_configured`.
- `test_google_campaign_configured_without_real_client_fails_honestly` → 501
  `google_ads_client_not_implemented` (caso exacto del hallazgo histórico).
- `test_create_ad_campaign_google_end_to_end_fails_honestly_when_writes_enabled`
  → verifica que ni siquiera con `writes_enabled=True` se produce éxito falso.

Ejecución:

```
$ python -m pytest tests/test_perseo_ads_engine_v2_google.py -v
======================= 3 passed, 31 warnings in 0.29s ========================
```

## 5. Suite completa — comparación con baseline

**Baseline (antes de este step, commit `038096f`, sin tocar código)**:

```
7 failed, 289 passed, 34 warnings, 3 errors in 164.12s
```

Fallos (idénticos en ambas ejecuciones, no relacionados con este cambio):
- `tests/test_basic.py::test_config_loading`
- `tests/test_justicia_control_layer_v1.py::test_default_flags_simulated`
- `tests/test_perseo_autofix_v2.py::test_audit_includes_ai_modules`
- `tests/test_thalos_control_layer_v1.py::test_default_mode_is_simulation_for_heuristic_modules`
- `tests/test_thalos_control_layer_v1.py::test_backup_requires_execution_and_backup_flags`
- `tests/test_thalos_control_layer_v1.py::test_build_metadata_origin_mock`
- `tests/test_thalos_safe_v1.py::test_monitoring_cycle_respects_flags`
- Errores: `tests/test_app.py::test_health_check/test_root_endpoint/test_favicon`
  (`NameError: name 'TestClient' is not defined`)

**Después de añadir el test de regresión (sin tocar código de producción)**:

```
7 failed, 292 passed, 34 warnings, 3 errors in 161.57s
```

Mismos 7 fallos y 3 errores exactos que el baseline (sin relación con PERSEO ni
Google Ads). El delta es exactamente `+3 passed`, correspondiente a los 3 tests
nuevos añadidos. **No hay regresión.**

## 6. Qué se tocó

- `backend/tests/test_perseo_ads_engine_v2_google.py` (nuevo) — 3 tests de
  regresión que fijan el comportamiento honesto de `create_google_campaign` /
  `create_ad_campaign` para la plataforma Google.
- `AUDIT_PERSEO_GOOGLE_ADS_REAL.md` (este documento).
- **No se modificó** `backend/services/perseo_ads_engine_v2.py` — ya estaba
  corregido en el commit `2346230`, ancestro de `HEAD` en esta rama.

## 7. Qué NO se pudo verificar

- No se probó una llamada real a la Google Ads API (no hay credenciales
  reales en este entorno ni se deben inventar). Por tanto, no existe todavía
  una integración real que persista `campaign_id` reales de Google — solo el
  fallo honesto cuando se intenta.
- No se verificó multi-tenant en este endpoint más allá de lo que ya cubre el
  código existente (`create_ad_campaign` no depende de `company_id`/tenant
  directamente porque no persiste nada en BD para Google — solo falla antes
  de llegar a cualquier lógica de persistencia; no hay dato de un tenant
  expuesto a otro porque no se llega a crear ni leer ningún registro).

## 8. Qué queda pendiente

1. **Decisión del usuario**: si se quiere una integración real con Google Ads
   (llamadas API reales que creen campañas), es un trabajo de alcance mayor
   (nueva dependencia `google-ads`, flujo OAuth2 completo, credenciales de
   cuenta de prueba de Google Ads para verificar) que debería tratarse como
   tarea nueva, no como parte de este fix puntual.
2. El propio `AUDITORIA_TOTAL_FINAL.md` de este worktree debería actualizarse
   en su sección 1 (fila PERSEO) y en la tabla resumen (línea ~472) para
   reflejar que el hallazgo de Google Ads ya está resuelto de raíz en el
   código (aunque la integración real con la API siga sin existir, lo cual es
   un estado *honesto*, no una simulación oculta). No he tocado ese documento
   porque no formaba parte del encargo — solo lo señalo aquí.
