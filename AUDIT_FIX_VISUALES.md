# AUDIT_FIX_VISUALES.md

**Rama**: `feature/hallazgos-visuales` (desde `main`)
**Fecha**: 2026-08-13
**Objetivo**: arreglar los 3 hallazgos críticos de [MAPA_VISUAL_ZEUS.md](MAPA_VISUAL_ZEUS.md):
AFRODITA en modo simulado con texto de debug en inglés, Admin Panel inalcanzable
pese a superuser real, y el `ReferenceError: shouldShowTPV is not defined`.

Los textos de traducción sin traducir (`dashboardPro.analytics.*`, `tpv.shareComandero`)
quedan fuera de esta rama por instrucción explícita — tarea aparte, menor prioridad.

---

## 1. AFRODITA en modo "SIMULATED" con texto de debug en inglés

### Diagnóstico

**Por qué AFRODITA está en modo SIMULATED**: `services/afrodita_unified_control.py::get_global_status()`
decide `REAL` vs `SIMULATED` según `AFRODITA_EXECUTION_ENABLED` y `AFRODITA_READ_ONLY_MODE`
(`config/afrodita_flags_v1.py`). Ninguna de las dos está definida en `.env` en este entorno,
y el default es `false` de forma segura cuando faltan (`_warn_missing()` deja constancia en logs).
**No están configuradas — esto es un hecho, no una suposición.**

**Decisión tomada**: activar `AFRODITA_EXECUTION_ENABLED=true` /
`AFRODITA_READ_ONLY_MODE=false` significaría que AFRODITA empiece a escribir de
verdad en `company_employees`, fichajes, contratos, etc. Es una decisión de
producto/seguridad (¿queremos que RRHH escriba en BD real ya mismo, con qué
datos de prueba, con qué validación previa?) que no me corresponde tomar
unilateralmente en esta rama. **No se ha tocado ningún flag** — AFRODITA
sigue en modo SIMULATED, tal y como estaba.

**Lo que sí se arregla siempre, esté o no configurado el modo real**: el texto
que ve el usuario. Antes, el workspace de AFRODITA mostraba literalmente:

```
NO EXECUTION — NO EXECUTION (configure flags en Railway).
```

(y en otros estados: `SYSTEM ERROR — base de datos no disponible.`, o un
mensaje exponiendo nombres de variables de entorno de Railway como
`STATIC_DIR`/`AFRODITA_EXECUTION_ENABLED`). Esto es exactamente lo que
`zeus-produccion` prohíbe: jerga técnica en inglés y detalles de
infraestructura expuestos a un cliente real.

### Cambio

- `frontend/src/api/afrodita_workspace_api.ts` — `executionModeLabel()`
  devolvía `"REAL"` / `"SYSTEM ERROR"` / `"NO EXECUTION"` en inglés (usada en
  3 sitios: `AfroditaToolsPanel.vue`, `AfroditaOpsPanel.vue`,
  `AfroditaWorkspace.vue`). Ahora devuelve `"Real"` / `"Error del sistema"` /
  `"Sin ejecución real"` — la misma terminología ya usada correctamente en
  `ThalosExecutionBadge.vue` (`'Ejecución real'` / `'Sin ejecución real'`).
- `AfroditaToolsPanel.vue` y `AfroditaOpsPanel.vue` (`onMounted`) — los 3
  mensajes de `statusNote` (ERROR / flags mal configuradas / modo normal)
  reescritos en español limpio, sin jerga de Railway ni nombres de variables
  de entorno. El detalle técnico de "flags recuperados de otra variable mal
  configurada" se mueve a `console.warn` (solo visible en devtools, para
  quien depure), ya no al DOM.
- **No se ha tocado**: los badges cortos (`SIMULATED` / `REAL` / `PARTIAL` /
  `NONE`) de `ThalosExecutionBadge.vue`. Es el lenguaje de estado compacto
  usado de forma consistente en toda la app — incluido THALOS, que la propia
  auditoría visual confirmó como correcto y no señaló como problema. Tocarlo
  habría sido alcance mayor del pedido.

### Verificación real (Playwright, `test.gestoria@example.com`)

Antes:
```
SIMULATED
SIN EJECUCIÓN REAL

NO EXECUTION — NO EXECUTION (configure flags en Railway).
```

Después:
```
SIMULATED
SIN EJECUCIÓN REAL

Modo actual: Sin ejecución real. Los cambios no se guardan todavía —
contacta con el equipo de ZEUS-IA para activar esta herramienta.
```

Sin inglés, sin nombres de variables de entorno, sin "Railway". El badge
`SIMULATED` (diseño de estado compacto, intencional) se mantiene — sigue
siendo honesto sobre que la herramienta no ejecuta de verdad, tal y como
exige `zeus-produccion`, sin necesidad de jerga técnica para comunicarlo.

**Pendiente explícito, no resuelto aquí**: para que AFRODITA ejecute de
verdad, hace falta decidir y configurar `AFRODITA_EXECUTION_ENABLED=true` y
`AFRODITA_READ_ONLY_MODE=false` (en `.env` local o Railway en producción),
más los flags específicos por dominio (`AFRODITA_USE_REAL_EMPLOYEES`,
`AFRODITA_USE_REAL_CHECKINS`, etc., todos con default `true` una vez el
flag maestro está activo). Esto queda para que Carlos lo decida.

---

## 2. Admin Panel inalcanzable pese a superuser real confirmado

### Diagnóstico (la condición de carrera)

Confirmado con `test.gestoria@example.com` convertido en superuser real
(`GET /api/v1/auth/me` → `"is_superuser": true`):

- El botón "ADMIN" nunca aparecía en el sidebar (`.admin-btn` ausente del
  DOM incluso 2s después de cargar).
- Navegar directamente a `/admin` (URL directa o recarga) siempre
  redirigía a `/dashboard`.

**Causa raíz real** (inspeccionado en vivo, estado de Pinia leído
directamente vía `pinia.state.value.auth`, no solo el código fuente):

`frontend/src/stores/auth.ts`:
```js
const isAuthenticated = computed<boolean>(() => !!token.value);
```
`isAuthenticated` solo comprueba que exista un token — **no dice nada** de
si `authStore.user` (con `is_superuser`, `role`, `modules`) ya se cargó
desde `/api/v1/auth/me`. La única función que rellena `user` es
`authStore.initialize()`, y **no se llama desde ningún sitio central**
(no está en `main.ts`, no está en el guard del router) — solo la llaman
algunas vistas concretas en su propio `onMounted`:
`DashboardProfesional.vue`, `TPV.vue`, `OnboardingSetup.vue`, `OfficeCrm.vue`.

En una recarga directa a `/admin` (con sesión ya guardada en localStorage,
el caso normal de un deep-link o F5), el guard de `router/index.js` se
ejecuta **antes** de que ningún componente llegue a montarse. Con
`user: null` en ese momento, `authStore.isAdmin` es siempre `false`, así que
el guard trataba a un superusuario real como si no lo fuera y lo expulsaba
de `/admin` — el mismo `user: null` hacía que el botón "ADMIN" del sidebar
(`v-if="authStore.isAdmin || authStore.user?.is_superuser"`) tampoco se
mostrara nunca, ya que ningún componente disparaba `initialize()` a tiempo
en ese flujo.

Verificado en consola (con la app sin arreglar):
```
🔍 Estado inicial de authStore: {isAdmin: false, isAuthenticated: true, user: null, ...}
```
`isAuthenticated: true` y `user: null` al mismo tiempo — la contradicción
exacta que causa el bug.

### Cambio

`frontend/src/router/index.js`, guard `beforeEach` (ya `async`): justo
después de la comprobación de "ruta protegida sin autenticación", se añade:

```js
if (requiresAuth && authStore.isAuthenticated && !authStore.user && authStore.initialize) {
  await authStore.initialize()
}
```

Esto obliga a hidratar `authStore.user` antes de evaluar cualquier lógica
que dependa del rol (empleado, módulos por `company_type`, superusuario,
onboarding) — en vez de decidir con información que sabemos que puede estar
incompleta. `initialize()` ya tiene sus propios guards internos
(`hasInitialized` / `isInitializing`), así que llamarlo en cada navegación es
seguro y barato una vez ya se ha ejecutado.

### Verificación real (Playwright, dos roles distintos)

**Como superuser** (`test.gestoria@example.com`, `is_superuser=1`):
- Sidebar: aparece `🔐 Administración` junto a Panel/Analíticas/TPV/Control
  horario/CRM oficina/Nóminas/Ajustes.
- Clic en "Administración" → `Panel de Admin - ZEUS-IA`, con datos reales
  (`49 Clientes Totales`, `€1797,00 Ingresos Mensuales`, `€23.361,00 Ingresos
  Totales`, `49 Suscripciones Activas`, gráfico de ingresos por mes) —
  `GET /api/v1/admin/stats`, `/admin/customers`, `/admin/revenue-chart` → 200 OK.
- Navegación directa por URL a `http://localhost:5173/admin` (recarga dura,
  el caso que antes fallaba) → **entra correctamente**, sin redirigir a
  `/dashboard`.

**Bajando al mismo usuario a rol normal** (`is_superuser=0`, para probar el
caso negativo — restaurado a superuser al terminar, ver §4):
- Sidebar: solo `Panel / Analíticas / CRM oficina / Ajustes` — sin
  Administración, sin TPV, sin Control horario, sin Nóminas.
- Navegación directa a `/admin` → redirige correctamente a `/dashboard`
  (bloqueado, como debe ser).
- Navegación directa a `/tpv` → redirige correctamente a `/dashboard`
  (módulo no habilitado para esa empresa, como debe ser).

El fix hidrata el estado real antes de decidir — no abre acceso de más ni
de menos, según el rol real del usuario.

---

## 3. `ReferenceError: shouldShowTPV is not defined`

### Diagnóstico

`DashboardProfesional.vue`, dentro de `onMounted()`, 3 `setTimeout`
(100/500/1000ms) pensados como red de seguridad: si el rol del usuario
tarda en cargar, reintentan corregir qué módulos ve (llamando a
`updateModulesForSuperuser()`). Cada uno empezaba con:

```js
console.log('🔍 Estado después de delay 100ms:', {
  ...,
  shouldShowTPV: shouldShowTPV.value,
  shouldShowControlHorario: shouldShowControlHorario.value,
  shouldShowAdmin: shouldShowAdmin.value
})
updateModulesForSuperuser()
```

`shouldShowTPV`, `shouldShowControlHorario` y `shouldShowAdmin` **no estaban
declaradas en ningún sitio del componente** (confirmado con búsqueda
completa en el archivo). JavaScript evalúa el objeto literal que se le pasa
a `console.log(...)` **antes** de llamar a la función — así que el
`ReferenceError` se lanzaba sin capturar en cuanto se construía ese objeto,
**antes** de llegar a `updateModulesForSuperuser()`. Resultado: los 3
reintentos llevaban muertos desde que se escribieron, para todo el mundo,
siempre — no solo generaban ruido en consola, impedían la única red de
seguridad que existía para corregir la visibilidad de módulos si el rol
tardaba en cargar.

Relacionado con el hallazgo #2: en el mismo `onMounted`, la línea
`if (!authStore.isAuthenticated && authStore.initialize)` tenía el mismo
bug de fondo que el guard del router (§2) — comprobaba `isAuthenticated`
en vez de si `user` ya estaba cargado.

### Cambio

- Los 3 bloques `console.log({shouldShowTPV: shouldShowTPV.value, ...})` se
  sustituyen por una función `logModuleVisibilityState(label)` que usa
  `showModule('tpv')`, `showModule('control_horario')`, `showModule('admin')`
  — la función real (`isModuleVisible(mergedModules.value, key, moduleOpts.value)`)
  que decide qué ve el usuario, ya existente y correcta en el componente.
  Ahora el log refleja el estado real y `updateModulesForSuperuser()` se
  ejecuta como estaba previsto en los 3 reintentos.
- `if (!authStore.isAuthenticated && authStore.initialize)` →
  `if (!authStore.user && authStore.initialize)`, mismo razonamiento que en
  el router (§2): `isAuthenticated` no implica `user` cargado.

### Verificación real (no solo "desaparece el error de consola")

- Consola limpia: tras el fix, ninguna navegación nueva genera entradas
  `shouldShowTPV is not defined` (confirmado comparando el buffer de
  consola antes/después de varias recargas — las únicas entradas que
  quedan visibles son residuos de before del propio fix, sin timestamp
  nuevo tras aplicarlo).
- **Lógica de visibilidad por rol, verificada para 2 roles distintos** (los
  mismos pasos que en §2): superuser ve TPV/Control horario/Administración/
  Nóminas en el sidebar; el mismo usuario bajado a rol normal vuelve a ver
  solo Panel/Analíticas/CRM oficina/Ajustes. No es solo que el error ya no
  salte — el mecanismo que decide qué ve cada rol funciona correctamente en
  ambos sentidos.

---

## 4. Nota sobre los usuarios de prueba usados

Para verificar el caso negativo (§2, §3) bajé temporalmente
`test.gestoria@example.com` a `is_superuser=0` en la BD local
(`backend/zeus.db`, escritura directa SQLite, igual que en sesiones
anteriores) y lo **restauré a `is_superuser=1`** al terminar — queda
exactamente como estaba antes de empezar esta rama (superuser, con
`company_id=1`, "Gestoria Test SL"). Credenciales sin cambios:
`test.gestoria@example.com` / `TestPass123!`.

---

## 5. Tests

### Baseline real de esta rama (no el de `feature/envio-gestoria`)

Al correr la suite completa antes de dar por buena esta rama, apareció un
fallo que no estaba en el baseline que veníamos usando (214 passed / 7
failed / 2 skipped / 3 errors, establecido en la sesión de
`feature/envio-gestoria`):

```
FAILED tests/test_afrodita_ops_real_v1.py::test_warehouse_summary - LookupError:
'goods' is not among the defined enum values. Enum name: productcategory.
```

**Diagnóstico**: es el mismo bug de `Enum(...)` sin `values_callable` en
`app/models/erp.py` ya diagnosticado y arreglado en la sesión de
`envio-gestoria` — pero ese fix vive en una rama distinta, aún sin fusionar
a `main`. Esta rama (`feature/hallazgos-visuales`) parte de `main`, así que
no lo tiene. **Confirmado que no lo causaron mis cambios**: hice
`git stash` de los 5 archivos tocados en esta rama (todos frontend) y el
test seguía fallando exactamente igual contra el `main` limpio — es un bug
preexistente del modelo ERP en `main`, no relacionado con esta tarea, y
fuera de alcance (los 3 fixes pedidos son puramente frontend).

**Baseline correcto y real de esta rama**: **213 passed / 8 failed / 2
skipped / 3 errors**.

### Resultado final (con los 3 fixes aplicados)

```
213 passed, 8 failed, 2 skipped, 30 warnings, 3 errors in 119.34s
```

Idéntico al baseline real de la rama, mismos 8 fallos exactos (incluido el
de `test_warehouse_summary`, preexistente y fuera de alcance). **Cero
regresiones** introducidas por los 3 fixes — todos ellos puramente frontend
(Vue/TS), sin tocar nada en `backend/`, por lo que no había expectativa de
que movieran la aguja en la suite de Python; se confirma que efectivamente
no lo hicieron.

---

## 6. Resumen de commits en `feature/hallazgos-visuales`

```
5b7402c fix(afrodita): quitar texto de debug en ingles visible al usuario final
9ed26d7 fix(router): esperar a que authStore.user cargue antes de decidir acceso por rol
df7a61b fix(dashboard): ReferenceError shouldShowTPV mataba el reintento de visibilidad de modulos
```

Sin merge ni push a `main`.

---

## 7. Pendiente

1. **Decisión de negocio**: activar `AFRODITA_EXECUTION_ENABLED` /
   `AFRODITA_READ_ONLY_MODE` (y los flags específicos por dominio) cuando
   se decida que AFRODITA debe escribir de verdad en RRHH — no forma parte
   de esta rama.
2. **Bug preexistente encontrado de paso, no arreglado aquí** (fuera de
   alcance, ya arreglado en otra rama sin fusionar): `Enum(...)` sin
   `values_callable` en `app/models/erp.py`, causando
   `test_afrodita_ops_real_v1.py::test_warehouse_summary` y afectando
   potencialmente cualquier flujo real que cree `Product` con `category`.
   El fix ya existe en `feature/envio-gestoria` — pendiente de fusionar
   ese trabajo a `main` para que deje de reaparecer en cada rama nueva.
3. Los textos de traducción sin traducir (`dashboardPro.analytics.*`,
   `tpv.shareComandero`) — explícitamente fuera de esta rama, pendiente
   como tarea aparte de menor prioridad.
