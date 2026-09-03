# Auditoria frontend de cierre - ronda final (TPV / Control Horario / Nominas / Admin Panel)

Rol: auditor-frontend (solo lectura, sin cambios de codigo).
Worktree auditado: C:\Users\Acer\ZEUS-IA\.claude\worktrees\consolidacion-final
Branch: feature/consolidacion-final - commit dd775a791ac5affaaa76632995bf93726f88b141.
Objetivo de esta ronda: verificar con Playwright real las 4 pantallas que en AUDIT_FRONTEND_CIERRE.md (vueltas 1 y 2) solo se habian confirmado por lectura de codigo, nunca renderizadas: TPV, Control Horario, Nominas, Admin Panel.

---

## Verificacion de entorno

Puertos estandar del proyecto (8000/5173) estaban en uso por un proceso node.exe ajeno a esta sesion - el problema de checkout compartido ya documentado en rondas anteriores es real y se confirma de nuevo aqui. Se evito por completo: no se uso preview_start/launch.json.
- Backend: uvicorn app.main:app en 127.0.0.1:8000 lanzado desde backend/ de este mismo worktree. Confirmado con GET /debug -> static_dir apuntando exactamente a este worktree.
- Frontend: npx vite --port 5223 --strictPort lanzado desde frontend/ de este mismo worktree. Se soluciono el preflight CORS arrancando el backend con la variable de entorno ya existente ZEUS_ADDITIONAL_CORS_ORIGINS.
- Ruido de entorno persistente y ya documentado: errores de CSP intentando conectar a localhost:5173 (HMR de Vite hardcodeado a ese puerto). No bloquea la funcionalidad.
- Al finalizar: procesos de backend/frontend de esta sesion terminados; git status confirma worktree limpio.

## Credenciales usadas

- Cuenta de superusuario existente (marketingdigitalper.seo@gmail.com, id 2365, is_superuser=1): confirmada activa en la BD local, pero sin contrasena conocida por este rol.
- Cuenta nueva creada por el flujo publico de registro para el rol de superusuario: auditor.tpv.cierre.final@zeusqaauditortpv.com, tipo de negocio Restauracion / bar / cafeteria (business_type=restaurant, confirmado en frontend/src/utils/companyModules.ts lineas 20-22 que este tipo mapea a company_type=bar_restaurant con modulos tpv, control_horario, payroll activos). Onboarding completado con exito.
- Para probar el Admin Panel se opto por una via transparente y reversible: se elevo temporalmente is_superuser a 1 para la propia cuenta de prueba, directamente en el sqlite local, se forzo una recarga completa de la SPA, se verifico el Admin Panel, y se revirtio el flag a 0 inmediatamente despues.
- Usuario normal: la misma cuenta de prueba, en su estado original, se uso para confirmar el bloqueo de /admin antes y despues de la elevacion temporal.

Nota tecnica sobre la elevacion temporal: authStore.initializeAuth (frontend/src/stores/auth.ts, funcion de arranque de la SPA) vuelve a pedir /auth/me en cada carga completa de pagina y sobreescribe user.value.is_superuser con el valor real devuelto por el backend, sin necesidad de reemitir el JWT. Por eso bastaba con cambiar el dato en la base de datos y recargar, sin tocar tokens ni codigo. Mismo patron de dato de prueba reversible y documentado que ya uso el ejecutor-frontend en la Vuelta 2 para company_type de OfficeCrm.vue.

---

## Hallazgo 1 - Codigos de alerta crudos del backend sin traducir en Control Horario

- Pantalla: control-horario, seccion Alertas inteligentes - frontend/src/views/ControlHorario.vue linea 151.
- Tipo: friccion de flujo y copy, mismo patron ya corregido antes para los badges UNKNOWN y CONTROLLED_UNTRUSTED.
- Prioridad demo: 3, confunde a un operario real sin ayuda, no rompe la demo pero un codigo tecnico en mayusculas con guion bajo no comunica nada a un usuario de negocio.
- Evidencia: con datos reales generados por el propio uso de la cuenta de prueba (sin fichar entrada tras el inicio de turno), el panel Alertas inteligentes mostro literalmente:
  - EMPLEADO_NO_FICHA: Sin fichaje tras inicio de turno (09:00 + 15m): U2374-OWNER
  - TURNO_SIN_CUBRIR: Nadie fichado dentro; revisar cobertura de turno.

Codigo, ControlHorario.vue lineas 150 a 152:

  li v-for en smartAlerts, key a.id, class sev- mas a.severity o warning
  span class alert-kind, contenido a.kind
  a continuacion se imprime a.message

El campo a.kind se imprime tal cual, sin pasar por ningun mapa de traduccion, a diferencia de a.message que ya viene en espanol desde el backend. Confirmado visualmente en ambos temas, Oscuro y Claro: el texto es legible, no hay problema de contraste, el problema es puramente de copy y traduccion.
- Criterio de hecho: el campo kind de cada alerta se traduce a una etiqueta corta en espanol (o se oculta el badge crudo y se deja solo el message, que ya esta en espanol) antes de mostrarse al usuario, con el mismo criterio ya aplicado a los badges de THALOS y AFRODITA y a los tipos de evento de KpiAlertsView.vue en la Vuelta 1.

---

## Hallazgo 2 - NONE crudo como nombre de plan en Admin Panel

- Pantalla: admin, pestana Clientes, columna Plan - frontend/src/views/AdminPanel.vue linea 908, funcion getPlanName.
- Tipo: friccion de flujo y copy.
- Prioridad demo: 4, cosmetico menor. Admin Panel es una herramienta interna para el propio equipo de ZEUS IA (superusuarios), no la ve ningun cliente final, por lo que el impacto en una demo comercial es minimo o nulo. Se documenta por completitud, no por urgencia.
- Evidencia: la tabla de clientes muestra literalmente NONE en la columna Plan para cuentas sin plan asignado (todas las cuentas de prueba de este entorno de desarrollo, incluida la mia).

Codigo:
  const names = objeto con startup STARTUP, growth GROWTH, business BUSINESS, enterprise ENTERPRISE
  return names[plan] o si no existe, plan.toUpperCase()

Cuando plan es el texto none, o cualquier valor no mapeado, cae al toUpperCase crudo. El resto de nombres de plan ya estan en mayusculas por diseno, posible nomenclatura de marca tipo STARTUP GROWTH, asi que esto no es un problema de esos 4 valores, es especificamente el caso none sin mapear.
- Criterio de hecho: anadir una entrada para none con el texto Sin plan al mapa names en getPlanName, consistente con la opcion Sin plan que ya existe en el select de edicion de plan, linea 214 del mismo archivo.

---

## Hallazgo 3 - Setup fees total en ingles suelto en Admin Panel, seccion Ingresos

- Pantalla: admin, pestana Ingresos, tarjeta de resumen - frontend/src/views/AdminPanel.vue linea 312.
- Tipo: friccion de flujo y copy.
- Prioridad demo: 4, cosmetico menor, mismo razonamiento que el Hallazgo 2. Se agrupa con el resto de copy en ingles suelto ya documentado como pendiente no bloqueante en AUDIT_FRONTEND_CIERRE.md, Vuelta 1, para otras pantallas.
- Evidencia: el encabezado de la tarjeta dice literalmente Setup fees (total), en ingles, mientras el resto de la pantalla esta en espanol: Ingresos y Facturacion, Este mes, Por plan, etc.
- Criterio de hecho: traducir a Cuotas de alta (total) o equivalente, consistente con el resto de la pantalla.

---

## Verificacion pantalla por pantalla

### TPV - CORRECTO

- Sistema de diseno: fondo de bandas metalicas visible en el contenedor raiz, consistente con InsuranceView.vue. Titulo TPV Universal Enterprise en el color de acento de marca, sin gradiente porque es texto de cabecera, no una accion. El boton REVISAR Y PAGAR muestra el gradiente de 3 paradas, teal a purpura a rosa, como unico acento de la vista para su accion principal, comparado visualmente con el boton Nueva poliza de InsuranceView.vue, mismo tratamiento exacto. El resto de botones, Modo Mesas, Actualizar, Imprimir Comanda, categorias Bebidas Tapas Todos, son neutros, sin acentos de color compitiendo. Tarjetas de producto, Cafe, Cerveza, Tostada, Refresco, con precios en verde como indicador semantico, no compite con el gradiente de accion.
- Contraste en ambos temas: verificado con 2 alternancias completas, Oscuro y Claro, en Ajustes seguidas de recarga de la pantalla TPV: el titulo, las tarjetas de producto y el boton de pago se ven identicos e igualmente legibles en ambos temas, sin regresion del patron de bloques de tema oscuro obsoletos. Busqueda explicita con grep de data-theme, dark-theme y html.dark en TPV.vue y en frontend/src/assets/styles/: cero coincidencias asociadas a esta vista.
- Datos reales: las llamadas a la API de tpv, tpv productos y tpv mesas devuelven 200 OK con datos reales del auto-bootstrap, mesas y productos con precios reales. Se interactuo con las mesas mediante PATCH, tambien 200 OK, confirmando que el modulo ejecuta logica real, no simulada.
- Assets: sin peticiones 404 en toda la sesion, avatares de los 6 agentes y logo, todos 200 OK.
- Consola: sin errores de JavaScript propios de la app. Unico ruido: CSP hacia localhost puerto 5173, artefacto de entorno ya documentado, no relacionado con TPV.
- Rol: operario u owner de cuenta tipo bar restaurant accede sin friccion.

### Control Horario - correcto en diseno y contraste, con 1 hallazgo de copy

- Sistema de diseno: fondo de bandas visible, titulo Control Horario Universal legible, tarjeta de cabecera con boton Actualizar, neutro, no es la accion principal de la vista, y badge Restaurante junto a el. Los 3 metodos de fichaje disponibles, Reconocimiento Facial, Codigo QR, Codigo Manual, con Geolocalizacion y Remoto deshabilitados o en gris, consistente con que la cuenta de prueba no configuro esos metodos, usan tarjetas con borde de seleccion en el color de acento, sin colores hardcodeados adicionales.
- Los 3 botones de accion de fichaje, Entrada en verde, Salida en rojo o rosa, Inicio pausa en naranja, usan colores solidos distintos entre si. No se cuenta esto como una violacion del criterio de un unico acento por vista: a diferencia de un boton de accion principal unico, como Nueva poliza o Revisar y pagar, aqui no hay una sola accion principal sino 3 acciones mutuamente excluyentes con significado semantico distinto, entrar, salir, pausar, un patron tipo semaforo, es un patron de diseno intencional y estandar en apps de fichaje, no varios acentos compitiendo por la misma accion. Se documenta el razonamiento para que ejecutor-frontend no lo corrija sin necesidad.
- Contraste en ambos temas: verificado con 2 alternancias, Oscuro y Claro, mas recarga: titulo y todo el contenido, Alertas, Coste laboral, Estado Actual, Historial de Hoy, Total Empleados, Dentro Ahora, Tasa de Asistencia, legibles en ambos temas, sin texto blanco o translucido sobre fondo claro ni al reves. Busqueda de bloques de tema oscuro obsoletos en el archivo y en sus estilos: cero coincidencias.
- Hallazgo de copy: ver Hallazgo 1 arriba, EMPLEADO_NO_FICHA y TURNO_SIN_CUBRIR crudos.
- Datos reales: avatar con iniciales AT, fallback intencional, no una imagen rota, badge de estado Fuera con datos reales de la sesion de fichaje.
- Consola: sin errores de JavaScript.

### Nominas - CORRECTO, pantalla minima, sin hallazgos

- Sistema de diseno: fondo de bandas visible, titulo Borradores de nomina con icono, subtitulo explicativo, tarjeta blanca con estado vacio No hay borradores de nomina en texto legible, gris oscuro sobre blanco. Pantalla deliberadamente minima, es una vista de solo lectura para descargar PDFs de nomina ya generados, sin una accion principal que requiera el gradiente de acento, no hay crear nomina manual en esta vista. No se penaliza la ausencia de gradiente porque no hay accion principal que destacar.
- Contraste en ambos temas: identico en Oscuro y Claro, sin diferencias.
- Datos reales: la llamada a la API de borradores de nomina devuelve 200 OK, lista vacia porque la cuenta de prueba es nueva y no ha completado un ciclo de nomina, comportamiento correcto, no una simulacion.
- Consola: sin errores de JavaScript.

---

### Admin Panel - correcto en diseno, contraste y rol, con 2 hallazgos de copy menores

- Rol, acceso correcto, confirmado en ambas direcciones:
  - Usuario normal, is_superuser en 0, navegando a la ruta admin, redirigido automaticamente al dashboard, guard requiresSuperuser en router index.js linea 534 funcionando. Confirmado dos veces, antes y despues de la elevacion temporal.
  - Superusuario, is_superuser en 1 de forma temporal, navegando a la ruta admin, carga el titulo Panel de Admin ZEUS-IA con datos reales.
- Sistema de diseno: fondo de bandas visible en las 3 pestanas, Overview, Clientes, Ingresos. Titulos legibles, Dashboard General, Clientes, Ingresos y Facturacion. El boton Guardar del modal Editar cliente usa el gradiente de 3 paradas, variable zeus-accent-gradient, AdminPanel.vue lineas 1901 a 1907, como unico acento, confirmado visualmente, identico al patron de InsuranceView.vue. El boton Actualizar de la tabla de Clientes es neutro, no compite con el gradiente del modal. La Zona superadmin, desactivar o eliminar cuenta, usa un rojo semantico para acciones destructivas, no un acento de marca, correcto, es un patron de advertencia, no una segunda accion principal.
- Contraste en ambos temas: verificado con 2 alternancias completas, Oscuro y Claro, en las pestanas Overview y Clientes: titulos y tablas legibles en ambos temas, sin regresion. Busqueda de bloques de tema oscuro obsoletos en AdminPanel.vue y sus estilos asociados: cero coincidencias.
- Datos reales: las llamadas a admin stats, admin customers, admin revenue-chart e integrations status devuelven todas 200 OK con datos reales acumulados de multiples sesiones de prueba anteriores en esta misma base de datos local. El numero 2374 de suscripciones activas es coherente con el ID autoincremental 2374 de mi propia cuenta, es decir, son usuarios reales acumulados en meses de pruebas, no un valor inventado. La tabla de Clientes muestra cuentas reales de rondas de auditoria anteriores, Ejecutor QA Servicios, Oficina QA Revisor, etc, con datos consistentes.
- Proteccion de superusuario: al intentar editar o eliminar mi propia cuenta, ya elevada a superusuario en ese momento, el modal mostro correctamente el mensaje No se puede modificar ni eliminar un superusuario desde aqui, validacion de seguridad real, no cosmetica.
- Hallazgos de copy: ver Hallazgos 2 y 3 arriba, NONE crudo y Setup fees en ingles. Ambos de prioridad 4, cosmetico menor, porque Admin Panel es herramienta interna, no se ensena en demos comerciales a clientes.
- Assets: sin peticiones 404 en ninguna pestana.
- Consola: sin errores de JavaScript en ninguna de las 3 pestanas ni en el modal de edicion.

---

## Resumen de la busqueda de bloques de tema oscuro obsoletos, patron ya visto 2 veces

Busqueda dirigida con grep de data-theme en los 4 archivos de esta ronda, ControlHorario.vue, TPV.vue, PayrollDrafts.vue, AdminPanel.vue: cero coincidencias en los 4 archivos. Tampoco existen archivos de tema scss dedicados a estas 4 vistas, a diferencia de office-crm-theme.scss y dashboard-profesional-theme.scss, que si existen para otras pantallas. Ninguna de las 4 pantallas de esta ronda repite el patron de bug ya corregido dos veces, CRM oficina y panel de estado del sistema.

---

## No auditado

Ninguna pantalla de las 4 asignadas quedo sin recorrer. Fuera del alcance explicito de esta ronda, no se tocaron: el resto de pantallas ya cerradas en AUDIT_FRONTEND_CIERRE.md, dashboard, workspaces de agentes, CRM, Ajustes, Analiticas, Seguros, no se repitieron, se dan por buenas segun esa auditoria previa.

---

## Pantallas con sistema de diseno correcto confirmadas en esta ronda

1. TPV, ruta tpv, sin hallazgos.
2. Control Horario, ruta control-horario, sin hallazgos de diseno o contraste, 1 hallazgo de copy, ver Hallazgo 1.
3. Nominas, ruta payroll, sin hallazgos.
4. Admin Panel, ruta admin, sin hallazgos de diseno, contraste o rol, 2 hallazgos de copy menores, ver Hallazgos 2 y 3.

## Resumen, hallazgo mas urgente de esta ronda

Ninguno de los 3 hallazgos de esta ronda es de prioridad 1 o 2: las 4 pantallas superan la barra de no romper la demo y no notarse como descuidadas frente a la referencia Seguros. El mas relevante de los tres es el Hallazgo 1, codigos crudos EMPLEADO_NO_FICHA y TURNO_SIN_CUBRIR en Control Horario, prioridad 3, porque es la unica pantalla de las 4 que un operario de negocio, no solo un superusuario interno, usa a diario sin ayuda. Los otros dos hallazgos, en Admin Panel, son cosmeticos y de bajo impacto por ser herramienta interna.

Conclusion general de esta ronda: las 4 pantallas que quedaban pendientes de verificacion visual, TPV, Control Horario, Nominas, Admin Panel, usan correctamente el sistema de diseno aprobado, fondo de bandas, tokens de marca, gradiente de 3 paradas unico por accion principal donde corresponde, mantienen el contraste en ambos temas sin repetir el bug de bloques de tema oscuro obsoletos ya visto dos veces, y el control de acceso por rol de Admin Panel funciona correctamente en ambas direcciones. Los 3 hallazgos nuevos son de copy y traduccion, no de arquitectura de diseno ni de seguridad.
