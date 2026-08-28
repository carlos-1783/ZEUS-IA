# Auditoria frontend de cierre - ZEUS IA

Rol: auditor-frontend (solo lectura, sin cambios de codigo).
Worktree auditado: C:\Users\Acer\ZEUS-IA\.claude\worktrees\consolidacion-final
Branch: feature/consolidacion-final - commit 823193d.
Fecha: 2026-08-28/29.

## Verificacion de entorno

- Frontend (puerto 5173): proceso Vite confirmado por linea de comandos exacta apuntando a este worktree.
- Backend (puerto 8000): confirmado con GET `/debug`, que devuelve static_dir apuntando a este worktree exacto.

## Como se obtuvo acceso

No existian credenciales de demo utilizables en la base de datos local de este worktree. No se pudo resetear contrasenas de admin@zeus-ia.com ni de la cuenta office existente sin modificar la base de datos, fuera del alcance de este rol. Se uso el flujo publico real de alta (`/auth/register`) para crear una cuenta tipo "Servicios profesionales" (company_type = office).

---

## Hallazgo 1 - Avatar de PERSEO devuelve 404 real, visible en el dashboard

- Pantalla/flujo: Dashboard (`/dashboard`) y modal "Interactuar" de PERSEO -- `frontend/src/components/DashboardProfesional.vue:1014`.
- Tipo: asset roto.
- Prioridad demo: 1 -- rompe la demo en vivo.
- Evidencia:
  - Captura del dashboard: la tarjeta de PERSEO muestra un icono de imagen rota con "PERSEC" superpuesto, mientras que ZEUS CORE, RAFAEL y THALOS muestran su avatar circular correctamente.
  - Network tab (confirmado dos veces, en el dashboard y en el modal "Interactuar" de PERSEO): peticion a `images/avatars/Perseo-avatar.jpg` devuelve 404 Not Found, mientras que los avatares de los otros 5 agentes devuelven 200 OK.
  - Causa raiz en codigo: `frontend/public/images/avatars/` contiene `perseo-avatar.jpg` en minuscula, mientras los otros 5 agentes estan en mayuscula (`Zeus-avatar.jpg`, `Rafael-avatar.jpg`, `Thalos-avatar.jpg`, `Justicia-avatar.jpg`, `Afrodita-avatar.jpg`). `DashboardProfesional.vue:1014` referencia el archivo con P mayuscula, que no existe con ese casing en el sistema de archivos servido.
  - Nota respecto a la ronda anterior: esa ronda no pudo confirmar el 404 visualmente y lo dejo en duda. Aqui se reproduce de forma consistente y repetible en este mismo worktree/commit.
- Criterio de hecho: la tarjeta de PERSEO muestra su avatar real (sin icono roto) en el dashboard y en el modal "Interactuar", en cualquier entorno, sin depender de que el filesystem sea case-insensitive.

---

## Hallazgo 2 - El tema "Oscuro" es el valor por defecto para toda cuenta nueva, y dos pantallas nunca aplican el fondo de bandas metalicas

Este hallazgo amplia y precisa lo que la ronda anterior describio como "pantallas sin sistema de diseno" para `ScanHub.vue` y (nuevo, no detectado antes) `OfficeCrm.vue`. La causa raiz no es solo "faltan tokens zeus" sino algo mas sistemico:

- `frontend/src/stores/settings.ts:17` -- el valor por defecto del tema es oscuro: toda cuenta nueva (confirmado registrando una cuenta real) arranca con Tema Oscuro en Ajustes, y el backend devuelve theme dark para la cuenta recien creada.
- `frontend/src/stores/settings.ts:63-69` (funcion applyThemeToDom): cuando el tema resuelto es oscuro, se fija el color de fondo del body a un navy solido de forma inline; en claro, a un gris azulado plano -- en ningun caso es el fondo de bandas metalicas del sistema de diseno (variable zeus-bg).
- El fondo de bandas correcto no viene del body ni del tema global: cada pantalla migrada lo re-declara explicitamente en su propio contenedor raiz con la propiedad background-image apuntando a la variable zeus-bg (confirmado en `InsuranceView.vue:438`, `DashboardProfesional.vue:1162`, `KpiPageShell.vue:28`, y en `AdminPanel.vue`, `PayrollDrafts.vue`, `ControlHorario.vue`, `TPV.vue`, `SettingsView.vue`). Es decir: el sistema de diseno esta implementado como parche por-pagina, no como tema global -- cualquier pantalla que olvide este wrapper cae directamente en el color plano del body (navy si el usuario tiene tema oscuro, que es el default).
- `frontend/src/views/OfficeCrm.vue` y `frontend/src/views/ScanHub.vue` son exactamente esas dos pantallas: ninguna de las dos declara el fondo de bandas en su contenedor raiz.
- Verificacion empirica cruzada: con la cuenta de prueba en tema Oscuro (default), la pantalla de CRM de oficina se ve con fondo navy solido -- captura tomada. Al cambiar el tema a Claro en Ajustes y volver, el fondo pasa a gris azulado plano -- captura tomada. En ningun caso aparecen las bandas metalicas; solo cambia que color plano del body queda expuesto.
- El hub de escaneo fisico va mas alla: no usa ni un solo token de diseno del sistema nuevo (cero coincidencias) y fija colores hardcodeados de un tema oscuro antiguo directamente, por lo que se ve oscuro incluso si el usuario tiene tema claro -- es la pantalla mas alejada del sistema de diseno de toda la app.

- Pantalla/flujo: CRM de oficina (`OfficeCrm.vue`) y hub de escaneo fisico (`ScanHub.vue`).
- Tipo: sistema de diseno (causa raiz sistemica, no solo cosmetica).
- Prioridad demo: 1-2. Para el hub de escaneo: cualquier cliente que use el escaneo fisico ve una pantalla que parece de otra aplicacion -- prioridad 1 si se ensena en demo. Para el CRM de oficina: como toda cuenta nueva arranca en tema oscuro por defecto, cualquier cliente de la vertical oficina que lo use el primer dia (sin haber tocado Ajustes) lo vera con fondo navy plano en vez del sistema de bandas -- prioridad 2 alta, casi garantizado en una demo de la vertical oficina.
- Evidencia: capturas del CRM de oficina en tema oscuro (navy) y en tema claro (gris plano), captura del hub de escaneo (fondo oscuro fijo independientemente del tema), captura de Ajustes mostrando Tema Oscuro seleccionado por defecto en una cuenta recien creada, y cita de codigo en settings.ts lineas 17 y 63-69.
- Criterio de hecho: el CRM de oficina y el hub de escaneo muestran el fondo de bandas metalicas igual que el resto de la app, en cualquier tema del usuario; y se revisa el valor por defecto del tema para cuentas nuevas para que ninguna pantalla dependa accidentalmente de declarar el fondo por si misma para no exponer el tema oscuro heredado.

---

## Hallazgo 3 - 7 pantallas KPI/sistema confirmadas sin sistema de diseno en su contenido interno (aunque el wrapper de fondo si lo tenga)

A diferencia del Hallazgo 2 (fondo de pagina), esto es sobre los componentes internos: texto y tarjetas con estilos de un tema oscuro antiguo que quedan casi ilegibles sobre el fondo claro correcto.

Pantallas confirmadas visualmente (navegacion directa mas captura):

- Tareas 24h, ruta `analytics/tasks` (`KpiTasksView.vue` lineas 76-78): el texto de estado vacio usa blanco translucido, casi invisible sobre fondo claro. El texto "Sin eventos en las ultimas 24 horas." apenas se distingue. Confirmado con captura.
- Eficiencia operativa, ruta `analytics/efficiency` (`KpiEfficiencyView.vue` lineas 54 y 64): tarjetas con fondo azul translucido y etiquetas en blanco translucido -- "EFICIENCIA", "EVENTOS 24H", "EXITOS 24H", "FUENTE" casi ilegibles. Confirmado con captura.
- Alertas activas, ruta `alerts` (`KpiAlertsView.vue` lineas 66-68): fondo translucido tenue en las filas -- funciona (el fondo claro es suficientemente distinto), pero los tipos de evento se muestran en crudo sin traducir (hr_compliance_gap, missing_consent, security_alert) -- ver Hallazgo 5.
- Automatizaciones, ruta `automations` (`KpiAutomationsView.vue` lineas 79 y 85): mismo patron de blanco translucido -- "Sin ejecucion" casi invisible en cada fila. Confirmado con captura.
- Auditoria de automatizaciones, ruta `automations/audit` (`KpiAutomationsAuditView.vue` lineas 290, 297 y 301): mismo patron -- "Sin logs de automatizacion todavia." casi invisible; ademas dos botones de accion con colores planos distintos compitiendo (verde y naranja) en vez de un unico acento por vista, y una etiqueta "Read-only audit mode" en ingles sin traducir. Confirmado con captura.
- Hub de escaneo fisico -- ver Hallazgo 2 (sin ningun token, tema oscuro fijo).
- Estado del sistema (`SystemStatusPanel.vue`): cero tokens del sistema de diseno nuevo; colores hardcodeados en lineas 151 a 260. Confirmado con captura: cabecera en franja oscura casi ilegible sobre fondo oscuro, cuerpo de la tarjeta en blanco plano sin bandas; ademas muestra un badge crudo "CONTROLLED_UNTRUSTED" y nombres de flag sin traducir (por ejemplo referencias a AFRODITA y THALOS con sufijos ENABLED) directamente al usuario.
- Pantalla revisada y confirmada correcta, se incluye solo para constancia: listado de Agentes activos -- se ve correcta (fondo de bandas y texto legible).

- Tipo: sistema de diseno.
- Prioridad demo: 2 (se nota como descuidado si el cliente mira dos veces: texto que desaparece sobre el fondo, dos acentos de color compitiendo en la misma vista, terminos en ingles sin traducir en una app en espanol) -- sube a 1 en Estado del sistema si un comercial la ensena como panel de estado, porque el contraste roto en la cabecera es visible de inmediato.
- Criterio de hecho: las 5 vistas KPI, el hub de escaneo y el panel de estado del sistema usan exclusivamente los tokens del sistema de diseno para texto, fondo y bordes (sin blancos translucidos ni hex sueltos), con contraste de texto legible sobre el fondo de bandas, un unico acento de color por vista para la accion principal, y copy en espanol para cualquier etiqueta visible al usuario.

---

## Hallazgo 4 - Salto visual dentro del propio modal "Interactuar" de cada agente (paneles anidados con colores planos antiguos)

Confirmado visualmente en 3 de los 6 workspaces (PERSEO, THALOS, RAFAEL), y por codigo en los otros 2 con panel de herramientas (JUSTICIA, AFRODITA). ZEUS CORE no tiene un panel de herramientas equivalente (solo su propio workspace), por lo que no aplica el mismo patron ahi.

Pantalla/flujo: modal "Interactuar" a pestana "Workspace" de cada agente, haciendo scroll mas alla de la cabecera.

- PERSEO (`frontend/src/components/agent-workspaces/PerseoToolsPanel.vue`): cabecera del modal correcta (fondo de bandas, boton Actualizar con gradiente de 3 paradas correcto). Al hacer scroll aparecen: botones planos negro y azul marino ("Editar video", "Analizar imagen", sin token, lineas 445 a 465), tarjetas con borde verde solido y badge REAL en verde, una tarjeta "Integraciones de marketing" con borde rosa, y un boton final "Guardar integraciones" en magenta solido (colores hardcodeados en lineas 367 a 478) -- cuatro acentos de color distintos compitiendo en el mismo scroll.
- THALOS (`ThalosToolsPanel.vue`): mismo patron -- badges "UNKNOWN" en gris (ver Hallazgo 5), botones "Ejecutar auditoria" y "Trigger backup" en negro y azul marino plano (lineas 444 y 456), tarjeta con borde celeste (linea 398) -- confirmado con captura.
- RAFAEL (`RafaelToolsPanel.vue`): el salto mas severo -- el hub de escaneo fisico completo (Camara QR, NFC, DNI) se embebe dentro, con su recuadro de camara negro y su boton "Procesar QR manual" en fondo navy con texto blanco (lineas 149 y 195), literalmente el mismo componente oscuro del hub de escaneo insertado dentro de un modal que hasta ese punto era claro -- confirmado con captura, es el ejemplo mas claro del problema.
- JUSTICIA (`JusticiaToolsPanel.vue`) y AFRODITA (`AfroditaToolsPanel.vue`): confirmados por codigo (cero tokens del sistema nuevo en ambos; 15 y 14 colores hex hardcodeados respectivamente) -- no se completo la captura visual de estos dos por una limitacion del viewport del navegador de esta sesion (ver seccion No auditado), pero el patron de codigo es identico al de los tres ya confirmados visualmente, por lo que se reporta con alta confianza.

- Tipo: sistema de diseno mas friccion de flujo (un operario sin conocimientos tecnicos ve un cambio de aplicacion a mitad de scroll y puede dudar de si sigue en el sitio correcto).
- Prioridad demo: 2 -- no rompe la demo (los botones funcionan), pero es exactamente el tipo de inconsistencia que un cliente nota si mira dos veces, y ocurre en el corazon del producto (la interaccion con los agentes).
- Criterio de hecho: los 5 paneles de herramientas usan los tokens del sistema de diseno para fondo, borde y texto, y el unico gradiente de acento de la vista para su accion principal, sin introducir acentos de color adicionales (verde, rosa, magenta, celeste) que compitan con el gradiente ya establecido en la cabecera del mismo modal.

---

## Hallazgo 5 - Strings crudos del backend sin traducir, visibles en varios puntos

- Pantalla/flujo: componente de badge de ejecucion de THALOS (usado en THALOS, RAFAEL, JUSTICIA, AFRODITA, ZEUS CORE) -- `frontend/src/components/agent-workspaces/ThalosExecutionBadge.vue` lineas 3 a 8.
- Tipo: friccion de flujo y copy.
- Prioridad demo: 3 -- confunde a un operario real sin ayuda; no rompe la demo pero un badge en mayusculas y en ingles (UNKNOWN, REAL_ACTIVE, ERROR) no comunica nada a un usuario de negocio.
- Evidencia:
  - Codigo: linea 4 y linea 7 imprimen el valor crudo del backend sin pasar por ningun mapa de traduccion. Esto contrasta con el campo de origen de datos del mismo archivo (lineas 69 a 79), que si tiene un mapa de traduccion (Backend, Entrada usuario, Simulado, Mixto) -- la inconsistencia es que solo uno de los tres badges esta traducido.
  - Confirmado visualmente en el workspace de THALOS: tres badges "UNKNOWN" (uno junto a Auditoria real, otro junto a Backup del sistema, otro junto a Monitor de logs) -- captura tomada.
  - Confirmado tambien en el panel de Estado del sistema con el badge crudo CONTROLLED_UNTRUSTED (mismo patron, aunque es un componente distinto -- ver Hallazgo 3).
  - Adicionalmente, dentro de THALOS: la lista de Reportes muestra encabezados de evento crudos como identificadores numericos seguidos de texto en ingles (task assigned, security scan, backup created) en vez de una descripcion legible en espanol.
- Criterio de hecho: el badge de ejecucion traduce los campos de modo global y de modulo igual que ya hace con el de origen de datos (o al menos aplica un texto explicativo en espanol si el valor no esta mapeado), y los encabezados de Reportes muestran una descripcion en espanol en vez del tipo de evento crudo.

---

## Hallazgo 6 - Errores de validacion del backend se muestran en ingles tecnico crudo al usuario final

- Pantalla/flujo: pagina de alta de cuenta y configuracion inicial (paso 3, validacion de email del gestor fiscal) -- `frontend/src/views/auth/Register.vue` lineas 407 a 420.
- Tipo: friccion de flujo y copy.
- Prioridad demo: 3 -- el flujo de alta es exactamente el que un comercial mostraria a un prospecto en una demo de auto-registro; si el prospecto escribe un email con un dominio que el validador del backend considera reservado (algo que ocurrio al preparar esta auditoria con un email de prueba), ve un mensaje tecnico en ingles completo, con jerga de programador, en medio de una app completamente en espanol.
- Evidencia: captura del formulario de registro mostrando el mensaje en ingles tal cual. Codigo: las lineas 412 a 416 solo traducen el mensaje cuando el campo con error es la contrasena; para cualquier otro campo (incluido el email), la logica devuelve el mensaje crudo del backend sin traducir ni reformular.
- Criterio de hecho: cualquier error de validacion devuelto por el backend (no solo el de contrasena) se traduce a un mensaje en espanol, en el tono de la interfaz, antes de mostrarse al usuario -- sin exponer nunca texto de validacion en ingles proveniente directamente del backend.

---

## No auditado (explicitamente)

Por falta de credenciales de rol o tipo de empresa adecuadas (ver seccion Como se obtuvo acceso) y sin poder modificar la base de datos local desde este rol de solo lectura:

- TPV -- bloqueado por tipo de cuenta (office no tiene el modulo tpv). Solo verificado por codigo: `TPV.vue` referencia el fondo de bandas del sistema nuevo (13 usos), consistente con el resto del sistema, pero no se ha visto renderizado.
- Control Horario -- mismo motivo. Codigo: `ControlHorario.vue` referencia el fondo de bandas (5 usos), no se ha visto renderizado.
- Nominas -- mismo motivo. Codigo: `PayrollDrafts.vue` referencia el fondo de bandas (2 usos), no se ha visto renderizado.
- Admin Panel -- requiere superusuario; no se pudo obtener ni resetear una credencial de superusuario sin modificar la base de datos, accion fuera del alcance de este rol. Codigo: `AdminPanel.vue` referencia el fondo de bandas (5 usos) y el sistema de diseno claro explicitamente, no se ha visto renderizado.
- Paneles de herramientas de JUSTICIA y AFRODITA -- confirmados por codigo (ver Hallazgo 4) pero no se completo la captura visual dentro de esta sesion por una degradacion del viewport del navegador (el panel de scroll dejo de responder a los comandos de scroll tras varias navegaciones); el resto de la sesion se completo con viewport reducido.
- Landing publica, Pricing, Checkout, Terminos, Privacidad, tienda publica, y rutas de test -- rutas publicas o de test de menor prioridad para el cierre de produccion del nucleo; no se recorrieron por foco de tiempo en las rutas autenticadas del nucleo (dashboard, agentes, verticales), que eran el objetivo explicito de esta ronda.

No se da por buena ni por mala ninguna de estas pantallas: quedan pendientes de una ronda con credenciales de superusuario o de cuenta de tipo hosteleria reales.

---

## Pantallas confirmadas SIN el sistema de diseno aprobado (lista explicita)

1. Hub de escaneo fisico (`ScanHub.vue`) -- cero tokens del sistema nuevo, tema oscuro hardcodeado permanente.
2. CRM de oficina (`OfficeCrm.vue`) -- sin el fondo de bandas en el contenedor raiz; expone el color plano del body, navy por defecto.
3. Estado del sistema (`SystemStatusPanel.vue`) -- cero tokens del sistema nuevo.
4. Tareas 24h (`KpiTasksView.vue`) -- texto casi invisible, sin tokens en el estado vacio.
5. Eficiencia operativa (`KpiEfficiencyView.vue`) -- tarjetas y etiquetas sin tokens, contraste roto.
6. Automatizaciones (`KpiAutomationsView.vue`) -- texto casi invisible sin tokens.
7. Auditoria de automatizaciones (`KpiAutomationsAuditView.vue`) -- texto casi invisible, dos acentos de color compitiendo, copy en ingles.
8. Alertas activas (`KpiAlertsView.vue`) -- sin tokens, aunque el contraste aqui si es legible.
9. Panel de herramientas anidado de PERSEO (`PerseoToolsPanel.vue`) dentro del modal Interactuar.
10. Panel de herramientas anidado de THALOS (`ThalosToolsPanel.vue`) dentro del modal Interactuar.
11. Panel de herramientas anidado de RAFAEL (`RafaelToolsPanel.vue`) dentro del modal Interactuar -- incluye el hub de escaneo oscuro embebido completo.
12. Panel de herramientas anidado de JUSTICIA (`JusticiaToolsPanel.vue`) -- confirmado por codigo, no visualmente.
13. Panel de herramientas anidado de AFRODITA (`AfroditaToolsPanel.vue`) -- confirmado por codigo, no visualmente.

## Resumen - hallazgo mas urgente de cara a la demo

El 404 real y visible del avatar de PERSEO en el dashboard (Hallazgo 1) es el mas urgente porque rompe la primera pantalla que ve cualquier usuario tras iniciar sesion, en cualquier entorno, sin necesidad de abrir devtools -- y su arreglo es trivial (unificar el casing de un solo archivo).
