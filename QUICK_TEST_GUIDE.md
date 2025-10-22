# 🧪 ZEUS-IA - Guía Rápida de Pruebas

**IMPORTANTE:** Esta guía te ayudará a verificar que todos los cambios funcionan correctamente.

---

## ✅ Paso 1: Pruebas Locales (Opcional pero Recomendado)

### Backend Local

```bash
# Ir a la carpeta del backend
cd backend

# Activar entorno virtual (si usas venv)
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar/actualizar dependencias
pip install -r requirements.txt

# Iniciar el servidor
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Verificar en el navegador:**
- http://localhost:8000/health
  - Debe responder: `{"status":"healthy","service":"zeus-ia"}`
- http://localhost:8000/debug
  - Debe mostrar las configuraciones (SECRET_KEY: "SET", etc.)

### Frontend Local

```bash
# En otra terminal, ir a la carpeta del frontend
cd frontend

# Instalar dependencias
npm install

# Iniciar el servidor de desarrollo
npm run dev
```

**Verificar en el navegador:**
- http://localhost:5173
- Debe cargar la página de login
- Verificar que no hay errores en la consola (F12 → Console)

### Test de Login Local

1. Abrir http://localhost:5173
2. Login con:
   - Email: `marketingdigitalper.seo@gmail.com`
   - Password: `Carnay19`
3. Debería redirigir al Dashboard
4. En la consola (F12), verificar mensajes de WebSocket:
   ```
   [WebSocket] Conectando...
   [WebSocket] Conexión establecida
   ```

---

## 🚀 Paso 2: Configurar Variables de Entorno

### Railway (Backend)

1. Ir a https://railway.app/dashboard
2. Seleccionar tu proyecto ZEUS-IA
3. Click en "Variables"
4. Copiar y pegar las siguientes variables:

```bash
# COPIAR DESDE: RAILWAY_VARIABLES_ZEUS_PRODUCTION.txt
SECRET_KEY=1b6ed3a2f7c62ea379032ddd1fa9b19b1cb7ddc2071ad633aee3c8568d62b13b
REFRESH_TOKEN_SECRET=934ce6750fb8c844e26972be922326cbd0ff924c92189f25be3acd36ad07096d
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
JWT_ISSUER=zeus-ia-backend
DEBUG=False
ENVIRONMENT=production
HOST=0.0.0.0
PORT=$PORT
DATABASE_URL=${{Postgres.DATABASE_URL}}
BACKEND_CORS_ORIGINS=https://TU-FRONTEND.vercel.app,https://TU-BACKEND.up.railway.app
FIRST_SUPERUSER_EMAIL=marketingdigitalper.seo@gmail.com
FIRST_SUPERUSER_PASSWORD=Carnay19
RAILWAY_ENVIRONMENT=production
NIXPACKS_PYTHON_VERSION=3.11
```

**⚠️ IMPORTANTE:** Reemplazar `https://TU-FRONTEND.vercel.app` con tu URL real de Vercel.

5. Click en "Deploy" o esperar el auto-deploy

### Vercel (Frontend)

1. Ir a https://vercel.com/dashboard
2. Seleccionar tu proyecto ZEUS-IA
3. Settings → Environment Variables
4. Agregar estas variables (una por una):

```bash
# COPIAR DESDE: VERCEL_VARIABLES_ZEUS_FRONTEND.txt
VITE_API_URL=https://TU-BACKEND.up.railway.app/api/v1
VITE_WS_URL=wss://TU-BACKEND.up.railway.app/api/v1/ws
VITE_APP_NAME=ZEUS-IA
VITE_APP_VERSION=1.0.0
VITE_ENABLE_ANALYTICS=true
VITE_DEV_MODE=false
NODE_ENV=production
```

**⚠️ IMPORTANTE:** Reemplazar `https://TU-BACKEND.up.railway.app` con tu URL real de Railway.

5. Redeploy el frontend

---

## 📦 Paso 3: Deploy

### Opción A: Deploy Automático (Recomendado)

```bash
# Push a Git (Railway auto-deploya)
git push origin main

# Deploy frontend en Vercel
cd frontend
vercel --prod
```

### Opción B: Build Local + Deploy

```bash
# En Windows:
.\BUILD_AND_DEPLOY.bat

# En Linux/Mac:
chmod +x BUILD_AND_DEPLOY.sh
./BUILD_AND_DEPLOY.sh

# Luego push a Git
git push origin main

# Deploy frontend
cd frontend
vercel --prod
```

---

## 🧪 Paso 4: Pruebas Post-Despliegue

### Test 1: Backend Health Check

```bash
# Reemplazar con tu URL real de Railway
curl https://TU-BACKEND.up.railway.app/health
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "service": "zeus-ia"
}
```

### Test 2: Debug Endpoint

```bash
curl https://TU-BACKEND.up.railway.app/debug
```

**Verificar que aparezca:**
```json
{
  "status": "debug",
  "database_url": "SET",
  "secret_key": "SET",
  "jwt_secret": "SET",
  "websocket_support": "ENABLED",
  ...
}
```

### Test 3: Login Endpoint

```bash
curl -X POST https://TU-BACKEND.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=marketingdigitalper.seo@gmail.com&password=Carnay19"
```

**Respuesta esperada:**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLC...",
    "refresh_token": "...",
    "token_type": "bearer"
  }
}
```

**❌ Si recibes error 500:** Verificar variables de entorno en Railway.

### Test 4: Frontend Login (Navegador)

1. Abrir tu URL de Vercel: `https://TU-FRONTEND.vercel.app`
2. Hacer login:
   - Email: `marketingdigitalper.seo@gmail.com`
   - Password: `Carnay19`
3. ✅ Debe redirigir al Dashboard
4. Abrir DevTools (F12) → Console
5. Verificar mensajes de WebSocket:
   ```
   [WebSocket] Conectando a wss://TU-BACKEND.up.railway.app/api/v1/ws/...
   [WebSocket] Conexión establecida
   [WebSocket] Mensaje recibido: {"type":"connection_established",...}
   ```

### Test 5: Verificar CSS/JS

1. En el Dashboard, abrir DevTools (F12) → Network
2. Recargar la página (Ctrl+R)
3. Verificar que todos los archivos se cargan con status 200:
   - ✅ `/assets/css/index-[hash].css` - 200 OK
   - ✅ `/assets/js/index-[hash].js` - 200 OK
   - ✅ `/assets/js/vendor-[hash].js` - 200 OK

**❌ Si ves 404:** Verificar que el build se hizo correctamente.

---

## ✅ Checklist de Pruebas Completas

Marca cada item después de verificarlo:

### Backend
- [ ] `/health` responde 200 OK
- [ ] `/debug` muestra variables configuradas
- [ ] `/api/v1/auth/login` funciona sin error 500
- [ ] Token se genera correctamente
- [ ] WebSocket endpoint `/api/v1/ws/{client_id}` está disponible

### Frontend
- [ ] Página de login carga sin errores
- [ ] Login redirige al Dashboard
- [ ] Dashboard carga correctamente
- [ ] WebSocket se conecta automáticamente
- [ ] No hay errores en la consola del navegador
- [ ] CSS y JS se cargan desde `/assets/`

### Seguridad
- [ ] Tokens expiran en 30 minutos (no 24 horas)
- [ ] SECRET_KEY está en variables de entorno (no hardcodeada)
- [ ] CORS permite solo dominios autorizados

---

## 🐛 Troubleshooting

### Error: "Token expirado antes de tiempo"

**Causa:** SECRET_KEY diferente entre instancias.

**Solución:**
```bash
# Verificar en Railway que SECRET_KEY está configurada
# Reiniciar el servicio de Railway
railway restart
```

### Error: "WebSocket connection failed"

**Causa:** URL incorrecta o CORS bloqueado.

**Solución:**
```bash
# Verificar en Vercel que VITE_WS_URL usa wss:// (no ws://)
# Verificar en Railway que BACKEND_CORS_ORIGINS incluye tu frontend
```

### Error: "CSS no carga (404)"

**Causa:** Build del frontend incorrecto o base URL incorrecta.

**Solución:**
```bash
# Verificar vite.config.ts tiene base: '/'
# Rebuild y redeploy
cd frontend
npm run build
vercel --prod
```

### Error: "500 Internal Server Error en login"

**Causa:** DATABASE_URL no configurada o SECRET_KEY faltante.

**Solución:**
```bash
# Ver logs de Railway
railway logs --tail

# Verificar variables en Railway Dashboard
# Reiniciar servicio
railway restart
```

---

## 🎯 Resultado Esperado Final

**✅ Todo debe funcionar sin errores:**
1. Login exitoso
2. Dashboard carga
3. WebSocket conectado
4. CSS/JS cargan correctamente
5. No hay errores 500
6. Tokens expiran en 30 minutos
7. Todo el flujo funciona en producción

**Si todo está ✅, entonces:**

```bash
echo "Zeus Stable ✅" >> backend/app/logs/zeus_stable_20250122.txt
git add backend/app/logs/zeus_stable_20250122.txt
git commit -m "Test: All tests passed - Zeus Stable confirmed ✅"
git push origin main
```

---

## 📞 Ayuda Adicional

Si algo no funciona:
1. Ver logs: `railway logs --tail`
2. Verificar variables de entorno en Railway/Vercel
3. Consultar `DEPLOYMENT_INSTRUCTIONS.md`
4. Revisar `ZEUS_STABLE_REPORT.md`

---

**¡Éxito con el deployment!** 🚀

