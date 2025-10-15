# Solución de Problemas - Frontend ZEUS-IA

## Problemas Comunes y Soluciones

### 1. Error: Port 5173 is already in use

**Síntomas:**
```
Error: Port 5173 is already in use
```

**Solución:**
```bash
# Opción 1: Usar el script de limpieza
npm run cleanup

# Opción 2: Usar el script de inicio mejorado
npm run dev:start

# Opción 3: Manual (PowerShell)
Get-NetTCPConnection -LocalPort 5173 | Stop-Process -Force
```

### 2. Error de Content Security Policy (CSP)

**Síntomas:**
```
Refused to connect to 'http://127.0.0.1:8000/auth/me' because it violates the following Content Security Policy directive
```

**Solución:**
- El problema ya está corregido en la configuración actual
- Se cambió de `127.0.0.1` a `localhost` en todas las URLs
- Si persiste, verificar que el backend esté corriendo en `localhost:8000`

### 3. Error de WebSocket: Tiempo de conexión agotado

**Síntomas:**
```
Error al reconectar: Error: Tiempo de conexión agotado
```

**Solución:**
- Verificar que el backend esté corriendo
- Verificar que el endpoint WebSocket esté disponible en `/ws`
- Los timeouts se han aumentado a 15 segundos
- Los intentos de reconexión se han reducido a 3

### 4. Error: Failed to fetch user profile

**Síntomas:**
```
Error al cargar los datos del dashboard: Error: Failed to fetch user profile
```

**Solución:**
- Verificar que el token de autenticación sea válido
- El sistema ahora usa datos del store como fallback
- Verificar que el backend esté respondiendo en `/api/v1/auth/me`

### 5. Error de Network

**Síntomas:**
```
Error: Network error
```

**Solución:**
- Verificar que el backend esté corriendo en `localhost:8000`
- Verificar la conectividad de red
- Verificar que no haya firewall bloqueando las conexiones

## Configuración Actual

### URLs Configuradas:
- **API Base URL:** `http://localhost:8000/api/v1`
- **WebSocket URL:** `ws://localhost:8000/ws`
- **Puerto de desarrollo:** `5173` (con fallback automático)

### Timeouts:
- **API Timeout:** 30 segundos
- **WebSocket Timeout:** 15 segundos
- **Reconexión máxima:** 3 intentos

## Scripts Disponibles

```bash
# Inicio normal
npm run dev

# Inicio con limpieza de puerto
npm run dev:clean

# Inicio mejorado con verificaciones
npm run dev:start

# Limpiar puerto ocupado
npm run cleanup
```

## Verificación del Backend

Antes de iniciar el frontend, asegúrate de que el backend esté corriendo:

```bash
# Verificar que el backend esté corriendo
curl http://localhost:8000/api/v1/health

# Verificar que el WebSocket esté disponible
curl http://localhost:8000/ws
```

## Logs de Depuración

Para habilitar logs detallados, agregar en la consola del navegador:

```javascript
localStorage.setItem('debug', 'true');
```

## Contacto

Si los problemas persisten, revisar:
1. Logs del navegador (F12 → Console)
2. Logs del backend
3. Estado de la red y firewall
