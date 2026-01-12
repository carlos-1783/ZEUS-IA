# 🔴 DIAGNÓSTICO CRÍTICO: Error 401 en Login - Railway

## ❌ PROBLEMAS ENCONTRADOS:

### 1. **SECRET_KEY EXPUESTA EN REPOSITORIO** ⚠️ CRÍTICO
   - **Archivo**: `RAILWAY_VARIABLES_COMPLETAS_RAW_EDITOR.txt`
   - **Valor expuesto**: `1b6ed3a2f7c62ea379032ddd1fa9b19b6895b8c4d2f1a6e7b9c8d5e4f3a2b1c0`
   - **Riesgo**: Si esta clave está en el repositorio público, CUALQUIERA puede generar tokens válidos
   - **Solución**: **GENERAR NUEVA SECRET_KEY INMEDIATAMENTE**

### 2. **Variables con Placeholders No Configuradas**
   - `JWT_SECRET_KEY="YOUR_JWT_SECRET_KEY_HERE"` ❌ No está configurada
   - `REFRESH_TOKEN_SECRET="YOUR_REFRESH_TOKEN_SECRET_HERE"` ❌ No está configurada  
   - `FIRST_SUPERUSER_PASSWORD="YOUR_FIRST_SUPERUSER_PASSWORD_HERE"` ❌ No está configurada
   - `DATABASE_URL="YOUR_DATABASE_URL_HERE"` ❌ No está configurada

### 3. **Inconsistencia en Configuración**
   - En `config.py` hay `env_prefix = "ZEUS_"` pero las variables críticas usan `os.getenv()` directamente
   - Esto significa que las variables DEBEN estar sin prefijo en Railway (correcto)
   - PERO si Railway no tiene las variables configuradas, el sistema usa valores por defecto

## 🔧 SOLUCIÓN PASO A PASO:

### PASO 1: Generar Nuevas Claves Secretas

```bash
# Generar SECRET_KEY nueva (64 caracteres)
python -c "import secrets; print(secrets.token_hex(32))"

# Generar REFRESH_TOKEN_SECRET nueva
python -c "import secrets; print(secrets.token_hex(32))"
```

### PASO 2: Configurar Variables en Railway

1. Ve a Railway Dashboard → Tu Proyecto → Variables
2. Usa el archivo `RAILWAY_VARIABLES_SEGURO_JSON.json` como referencia
3. **IMPORTANTE**: Reemplaza TODOS los valores marcados con `REEMPLAZAR_CON_TU_VALOR`

### PASO 3: Variables Críticas que DEBEN estar Configuradas:

```bash
# 🔐 SEGURIDAD (CRÍTICO)
SECRET_KEY=<GENERA_UNA_NUEVA_CLAVE_ALEATORIA_64_CARACTERES>
REFRESH_TOKEN_SECRET=<GENERA_UNA_NUEVA_CLAVE_ALEATORIA>

# 🗄️ BASE DE DATOS (CRÍTICO)
DATABASE_URL=<TU_URL_POSTGRESQL_RAILWAY>
DATABASE_PUBLIC_URL=<TU_URL_POSTGRESQL_RAILWAY>

# 👤 SUPERUSUARIO (CRÍTICO)
FIRST_SUPERUSER_EMAIL=marketingdigitalper.seo@gmail.com
FIRST_SUPERUSER_PASSWORD=<TU_PASSWORD_SEGURO>

# 🔑 JWT (IMPORTANTE)
ALGORITHM=HS256
JWT_ISSUER=zeus-ia-backend
JWT_AUDIENCE=zeus-ia:auth,zeus-ia:access,zeus-ia:websocket
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### PASO 4: Verificar Configuración

Después de configurar las variables en Railway:
1. Reinicia el servicio en Railway
2. Verifica los logs para asegurarte de que las variables se están leyendo correctamente
3. Intenta hacer login nuevamente

## 🚨 ACCIONES INMEDIATAS REQUERIDAS:

1. **ROTAR SECRET_KEY**: Generar nueva clave y actualizarla en Railway
2. **ELIMINAR SECRETOS DEL REPOSITORIO**: Los archivos con secrets deben estar en `.gitignore`
3. **CONFIGURAR VARIABLES EN RAILWAY**: Usar el archivo JSON seguro como referencia

## 📝 NOTA SOBRE EL ERROR 401:

El error 401 puede ocurrir por:
1. ✅ SECRET_KEY incorrecta o no configurada → El JWT no se puede verificar
2. ✅ REFRESH_TOKEN_SECRET incorrecta → Los refresh tokens fallan
3. ✅ Credenciales incorrectas → Email/password no coinciden
4. ✅ Usuario inactivo → `is_active = False`
5. ✅ Problema de normalización de email → Ya corregido en código

## ✅ VERIFICACIÓN POST-CONFIGURACIÓN:

Después de actualizar Railway, verifica:
- [ ] Las variables están configuradas (no tienen placeholders)
- [ ] SECRET_KEY tiene al menos 64 caracteres
- [ ] DATABASE_URL apunta a la base de datos correcta
- [ ] El servicio se reinició después de cambiar variables
- [ ] Los logs no muestran errores de configuración
