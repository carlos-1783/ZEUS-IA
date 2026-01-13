# ✅ CHECKLIST PARA RESOLVER ERROR 401

## 🔴 PROBLEMA ACTUAL
Error 401 (Unauthorized) al intentar hacer login

## ✅ PASOS OBLIGATORIOS (en orden):

### 1. CONFIGURAR VARIABLES EN RAILWAY (CRÍTICO)

Ve a Railway Dashboard → Tu Proyecto → Variables → Raw Editor

Pega TODAS las variables del archivo `RAILWAY_VARIABLES_COMPLETAS_FINAL.txt`

**IMPORTANTE: Las variables más críticas son:**
```
SECRET_KEY=844ed8b633048fbbc6d6f49546cd990618faa5193f95e8fdbc9df9a38ce6e01d
REFRESH_TOKEN_SECRET=25dff209a83b594864225825543916476dc8134d25356beb6e4b75c401d99461
FIRST_SUPERUSER_EMAIL=marketingdigitalper.seo@gmail.com
FIRST_SUPERUSER_PASSWORD=rPf7ja7#czcaXNQ5
DATABASE_URL=postgresql://postgres:NuShDSRdzMDDWnGRNyXkRWvbKjbHrtMA@yamanote.proxy.rlwy.net:10322/railway
```

### 2. REINICIAR EL SERVICIO

Después de pegar las variables:
- Railway se redesplegará automáticamente (espera 2-3 minutos)
- O ve a Deployments → Click en "Redeploy"

### 3. VERIFICAR LOGS EN RAILWAY

Ve a Railway → Tu servicio → Logs

Busca estos mensajes:
- ✅ `[BOOTSTRAP] Creating initial superuser marketingdigitalper.seo@gmail.com` → Usuario creado correctamente
- ✅ `[BOOTSTRAP] Updating existing superuser` → Usuario actualizado correctamente
- ❌ `FIRST_SUPERUSER_EMAIL/PASSWORD not configured` → Las variables NO están configuradas

### 4. INTENTAR LOGIN CON:

**Email:** `marketingdigitalper.seo@gmail.com`  
**Password:** `rPf7ja7#czcaXNQ5`

### 5. SI SIGUE FALLANDO:

Verifica en los logs:
- Busca `Intento de autenticación para: marketingdigitalper.seo@gmail.com`
- Busca `Usuario no encontrado` → El usuario no existe
- Busca `Contraseña incorrecta` → La contraseña no coincide
- Busca `Autenticación exitosa` → El login debería funcionar

## 🚨 ERRORES COMUNES:

1. **Variables no configuradas** → El superusuario no se crea
2. **Servicio no reiniciado** → Las variables no se cargan
3. **Email con mayúsculas/espacios** → Debe ser exactamente: `marketingdigitalper.seo@gmail.com`
4. **Contraseña incorrecta** → Debe ser exactamente: `rPf7ja7#czcaXNQ5` (case-sensitive)

## 📝 VERIFICACIÓN FINAL:

Después de seguir todos los pasos, deberías poder:
1. ✅ Ver en los logs que el superusuario se crea/actualiza
2. ✅ Hacer login con las credenciales
3. ✅ Recibir un token JWT válido
