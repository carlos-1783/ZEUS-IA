# Solución de Problemas de Workbox

## Problema: Errores de Precaching

Si ves errores como estos en la consola del navegador:

```
workbox Precaching did not find a match for /@vite/client
workbox No route found for: /@vite/client
workbox Precaching did not find a match for /src/style.css
workbox No route found for: /src/style.css
workbox Precaching did not find a match for /src/main.js
workbox No route found for: /src/main.js
workbox Precaching did not find a match for /manifest.webmanifest
```

## Solución

### 1. Limpiar archivos de Service Worker

Ejecuta el script de limpieza:

```bash
# Usando Node.js
node scripts/cleanup-sw.js

# O usando PowerShell
.\scripts\restart-dev.ps1
```

### 2. Configuración actualizada

La configuración de Vite ya incluye las siguientes mejoras:

- **Exclusión de archivos problemáticos**: Los archivos que causan errores están excluidos del precaching
- **Supresión de advertencias**: Se han configurado filtros para suprimir advertencias específicas
- **Modo de desarrollo mejorado**: En desarrollo, se usa `injectManifest` en lugar de `generateSW`

### 3. Archivos de configuración

- `vite.config.ts`: Configuración principal de Vite con opciones de Workbox
- `public/suppress-warnings.js`: Script para suprimir advertencias específicas
- `public/sw-config.js`: Configuración específica del service worker

### 4. Reiniciar el servidor

Después de limpiar los archivos, reinicia el servidor de desarrollo:

```bash
npm run dev
```

## Configuración de Workbox

### Archivos excluidos del precaching:

- `**/@vite/client/**` - Cliente de Vite para desarrollo
- `**/src/style.css` - Archivos de estilo fuente
- `**/src/main.js` - Archivos JavaScript fuente
- `**/manifest.webmanifest` - Manifesto de PWA
- `**/dev-dist/**` - Directorio de desarrollo
- `**/dist/**` - Directorio de producción

### Opciones de desarrollo:

- `workboxMode: 'injectManifest'` - Para desarrollo
- `workboxMode: 'generateSW'` - Para producción
- `suppressWarnings: true` - Suprime advertencias generales
- `disableRuntimeConfig: true` - Deshabilita configuración en tiempo de ejecución

## Verificación

Después de aplicar los cambios:

1. Abre las herramientas de desarrollador (F12)
2. Ve a la pestaña "Console"
3. Los errores de Workbox deberían haber desaparecido
4. El service worker debería registrarse correctamente

## Notas adicionales

- Los errores de precaching no afectan la funcionalidad de la aplicación
- Son principalmente advertencias de desarrollo
- En producción, estos errores no deberían aparecer
- Si persisten los problemas, considera deshabilitar temporalmente el PWA en desarrollo

