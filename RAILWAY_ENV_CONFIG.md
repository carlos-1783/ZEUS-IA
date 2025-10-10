# 🚀 Configuración de Variables de Entorno para Railway

## ⚡ Variables Mínimas Requeridas

Configura estas variables en Railway → Tu Proyecto → **"Variables compartidas"**:

### 1. PORT
- **VARIABLE_NAME:** `PORT`
- **VALOR:** `8000`
- **DESCRIPCIÓN:** Puerto del servidor (Railway lo asigna automáticamente)

### 2. SECRET_KEY
- **VARIABLE_NAME:** `SECRET_KEY`
- **VALOR:** `6895b411b45b5946b46bf7970f4d7e17aa69dfc5da4696cb15686625e5eccf2b`
- **DESCRIPCIÓN:** Clave secreta para JWT

### 3. DEBUG
- **VARIABLE_NAME:** `DEBUG`
- **VALOR:** `False`
- **DESCRIPCIÓN:** Modo producción (sin debug)

### 4. DATABASE_URL
- **VARIABLE_NAME:** `DATABASE_URL`
- **VALOR:** `sqlite:///./zeus.db`
- **DESCRIPCIÓN:** URL de la base de datos

### 5. ENVIRONMENT
- **VARIABLE_NAME:** `ENVIRONMENT`
- **VALOR:** `production`
- **DESCRIPCIÓN:** Entorno de ejecución

### 6. HOST
- **VARIABLE_NAME:** `HOST`
- **VALOR:** `0.0.0.0`
- **DESCRIPCIÓN:** Host del servidor

## 📋 Instrucciones Paso a Paso

1. **Ve a Railway Dashboard**
2. **Selecciona tu proyecto ZEUS-IA**
3. **Ve a la pestaña "Variables compartidas"**
4. **Agrega cada variable una por una:**
   - Haz clic en el primer campo (VARIABLE_NAME)
   - Escribe el nombre de la variable
   - Haz clic en el segundo campo (VALOR)
   - Escribe el valor correspondiente
   - Haz clic en "Agregar" (botón con ✓)
5. **Repite para las 6 variables**
6. **Reinicia el deployment**

## ✅ Verificación del Healthcheck

Después de configurar las variables, el endpoint `/health` debería responder:

```json
{
  "status": "ok",
  "service": "ZEUS-IA",
  "version": "1.0"
}
```

## 🔧 Estado Actual del Backend

- ✅ **Host:** 0.0.0.0 (configurado en config.py línea 17)
- ✅ **Puerto:** Dinámico via PORT (configurado en config.py línea 18)
- ✅ **Endpoint /health:** Existe y devuelve {"status": "ok"}
- ✅ **Dockerfile:** Optimizado para Railway
- ✅ **CMD:** Usa uvicorn directamente

## 🚨 Si el Healthcheck Sigue Fallando

1. Verifica que todas las variables estén configuradas correctamente
2. Revisa los logs en Railway → Logs (no Build Logs)
3. Confirma que el puerto sea 8000
4. Reinicia el deployment después de agregar las variables
