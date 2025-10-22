# 🚀 ZEUS-IA Deployment Instructions

## 📋 Pre-Despliegue Checklist

### ✅ Paso 1: Verificación de Código
- [x] WebSocket corregido: flujo ACEPTAR → AUTENTICAR → ESCUCHAR
- [x] JWT Tokens configurados con variables de entorno
- [x] CORS configurado correctamente
- [x] Frontend base: '/' configurado en vite.config.ts

### 🔐 Paso 2: Variables de Entorno

#### Backend (Railway)
Copiar las variables del archivo `RAILWAY_VARIABLES_ZEUS_PRODUCTION.txt` al panel de Railway:

```bash
# Variables críticas generadas:
SECRET_KEY=1b6ed3a2f7c62ea379032ddd1fa9b19b1cb7ddc2071ad633aee3c8568d62b13b
REFRESH_TOKEN_SECRET=934ce6750fb8c844e26972be922326cbd0ff924c92189f25be3acd36ad07096d
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**IMPORTANTE:** Actualizar `BACKEND_CORS_ORIGINS` con la URL real del frontend.

#### Frontend (Vercel/Netlify)
Copiar las variables del archivo `VERCEL_VARIABLES_ZEUS_FRONTEND.txt`:

```bash
VITE_API_URL=https://zeus-ia-production.up.railway.app/api/v1
VITE_WS_URL=wss://zeus-ia-production.up.railway.app/api/v1/ws
```

**IMPORTANTE:** Actualizar con la URL real de Railway.

---

## 🔧 Paso 3: Despliegue del Backend

### Railway Deployment

1. **Conectar Repositorio**
   ```bash
   # Si aún no has conectado el repo a Railway
   railway login
   railway link
   ```

2. **Configurar Variables de Entorno**
   - Ir a Railway Dashboard → Tu Proyecto → Variables
   - Copiar todas las variables de `RAILWAY_VARIABLES_ZEUS_PRODUCTION.txt`
   - Hacer clic en "Deploy" para aplicar cambios

3. **Verificar Despliegue**
   ```bash
   # Ver logs de despliegue
   railway logs
   
   # Verificar que el servicio está corriendo
   curl https://TU-DOMINIO.up.railway.app/health
   ```

4. **Endpoints a verificar**
   - ✅ `/health` - Health check
   - ✅ `/debug` - Variables de entorno configuradas
   - ✅ `/api/v1/auth/login` - Login endpoint
   - ✅ `/api/v1/ws/{client_id}` - WebSocket endpoint

---

## 🎨 Paso 4: Despliegue del Frontend

### Build Local (Recomendado para primera vez)

```bash
cd frontend

# Instalar dependencias
npm install

# Build para producción
npm run build

# Verificar que dist/ se generó correctamente
ls -la dist/

# La carpeta debe contener:
# - index.html
# - assets/
#   - css/
#   - js/
#   - images/
```

### Opción A: Vercel Deployment

1. **Instalar Vercel CLI**
   ```bash
   npm install -g vercel
   ```

2. **Deploy**
   ```bash
   cd frontend
   vercel login
   vercel --prod
   ```

3. **Configurar Variables de Entorno en Vercel**
   - Ir a Vercel Dashboard → Tu Proyecto → Settings → Environment Variables
   - Agregar las variables de `VERCEL_VARIABLES_ZEUS_FRONTEND.txt`
   - Redeploy: `vercel --prod`

### Opción B: Netlify Deployment

1. **Instalar Netlify CLI**
   ```bash
   npm install -g netlify-cli
   ```

2. **Deploy**
   ```bash
   cd frontend
   netlify login
   netlify deploy --prod
   ```

3. **Configurar Variables de Entorno en Netlify**
   - Ir a Netlify Dashboard → Site Settings → Build & Deploy → Environment
   - Agregar las variables de `VERCEL_VARIABLES_ZEUS_FRONTEND.txt`
   - Redeploy desde el dashboard

---

## 🧪 Paso 5: Pruebas Post-Despliegue

### Test 1: Backend Health Check
```bash
curl https://TU-BACKEND.up.railway.app/health
# Respuesta esperada: {"status":"healthy","service":"zeus-ia"}
```

### Test 2: Login
```bash
curl -X POST https://TU-BACKEND.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=marketingdigitalper.seo@gmail.com&password=Carnay19"
# Respuesta esperada: {"access_token":"...", "refresh_token":"...", ...}
```

### Test 3: WebSocket
1. Ir al frontend: `https://TU-FRONTEND.vercel.app`
2. Hacer login con las credenciales
3. Ir al Dashboard
4. Abrir DevTools → Console
5. Verificar que aparezcan logs de WebSocket:
   ```
   [WebSocket] Conectando...
   [WebSocket] Conexión establecida
   [WebSocket] Mensaje recibido: {"type":"connection_established",...}
   ```

### Test 4: Flujo Completo
1. ✅ Login → Dashboard
2. ✅ Dashboard carga correctamente
3. ✅ WebSocket se conecta automáticamente
4. ✅ No hay errores 500 o token expirado
5. ✅ CSS y JS se cargan desde /assets/

---

## 📊 Paso 6: Monitoreo y Logs

### Backend Logs (Railway)
```bash
# Ver logs en tiempo real
railway logs --tail

# Ver logs de errores
railway logs | grep ERROR

# Ver logs de WebSocket
railway logs | grep WebSocket
```

### Frontend Logs (Vercel/Netlify)
```bash
# Vercel
vercel logs --follow

# Netlify
netlify logs --follow
```

### Guardar Logs para Análisis
```bash
# Backend
railway logs > backend/app/logs/zeus_deployment_$(date +%Y%m%d_%H%M%S).log

# Frontend (desde el navegador)
# DevTools → Console → Clic derecho → "Save as..."
```

---

## 🔥 Troubleshooting

### Error: "Token expirado antes de tiempo"
- Verificar que `ACCESS_TOKEN_EXPIRE_MINUTES=30` en Railway
- Revisar que no haya múltiples instancias del backend con diferentes SECRET_KEY

### Error: "WebSocket connection failed"
- Verificar que `VITE_WS_URL` usa `wss://` (no `ws://`)
- Verificar que Railway tiene WebSocket habilitado
- Revisar CORS en Railway: `BACKEND_CORS_ORIGINS` debe incluir la URL del frontend

### Error: "CSS/JS no cargan (404)"
- Verificar que `base: '/'` en `vite.config.ts`
- Verificar que el build se hizo correctamente: `npm run build`
- Verificar que Vercel/Netlify apunta a la carpeta `dist/`

### Error: "500 Internal Server Error en login"
- Verificar que `DATABASE_URL` está configurada en Railway
- Verificar que `SECRET_KEY` está configurada
- Ver logs del backend: `railway logs | grep ERROR`

---

## ✅ Confirmación Final

Una vez que todos los tests pasen, ejecutar:

```bash
echo "Zeus Stable ✅" > backend/app/logs/zeus_stable_$(date +%Y%m%d_%H%M%S).txt
```

---

## 📝 Notas Adicionales

### Rollback (si algo sale mal)
```bash
# Ver commits recientes
git log --oneline -10

# Volver al commit estable (ejemplo: bccc0c6)
git reset --hard bccc0c6

# Push forzado (CUIDADO)
# git push --force origin main  # Solo si es necesario
```

### Actualizar Frontend con nueva URL de Backend
```bash
# Editar .env.production
VITE_API_URL=https://NUEVA-URL.up.railway.app/api/v1
VITE_WS_URL=wss://NUEVA-URL.up.railway.app/api/v1/ws

# Rebuild y redeploy
npm run build
vercel --prod
```

---

## 📞 Soporte

Si encuentras problemas:
1. Revisar logs en Railway/Vercel
2. Verificar variables de entorno
3. Consultar `TROUBLESHOOTING.md` (si existe)
4. Revisar los commits recientes: `git log --oneline -20`

---

**Fecha de última actualización:** $(date +%Y-%m-%d)
**Versión ZEUS-IA:** 1.0.0
**Estado:** Listo para producción ✅

