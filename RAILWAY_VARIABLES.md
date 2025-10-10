# Variables de Entorno para Railway

## Variables Mínimas Requeridas

Configura estas variables en Railway en la sección "Variables compartidas":

### 1. PORT
- **VARIABLE_NAME:** `PORT`
- **VALOR:** `8000`
- **DESCRIPCIÓN:** Puerto donde escucha el servidor (Railway lo asigna automáticamente)

### 2. SECRET_KEY
- **VARIABLE_NAME:** `SECRET_KEY`
- **VALOR:** `6895b411b45b5946b46bf7970f4d7e17aa69dfc5da4696cb15686625e5eccf2b`
- **DESCRIPCIÓN:** Clave secreta para JWT y encriptación

### 3. DATABASE_URL
- **VARIABLE_NAME:** `DATABASE_URL`
- **VALOR:** `sqlite:///./zeus.db`
- **DESCRIPCIÓN:** URL de la base de datos (SQLite por ahora)

### 4. DEBUG
- **VARIABLE_NAME:** `DEBUG`
- **VALOR:** `False`
- **DESCRIPCIÓN:** Modo de producción (sin debug)

### 5. ENVIRONMENT
- **VARIABLE_NAME:** `ENVIRONMENT`
- **VALOR:** `production`
- **DESCRIPCIÓN:** Entorno de ejecución

### 6. HOST
- **VARIABLE_NAME:** `HOST`
- **VALOR:** `0.0.0.0`
- **DESCRIPCIÓN:** Host donde escucha el servidor

## Variables Opcionales

### 7. ACCESS_TOKEN_EXPIRE_MINUTES
- **VARIABLE_NAME:** `ACCESS_TOKEN_EXPIRE_MINUTES`
- **VALOR:** `43200`
- **DESCRIPCIÓN:** Tiempo de expiración del token (30 días)

### 8. REFRESH_TOKEN_EXPIRE_DAYS
- **VARIABLE_NAME:** `REFRESH_TOKEN_EXPIRE_DAYS`
- **VALOR:** `30`
- **DESCRIPCIÓN:** Días de expiración del refresh token

## Instrucciones

1. Ve a Railway → Tu Proyecto → Variables compartidas
2. Agrega cada variable una por una
3. Haz clic en "Agregar" después de cada una
4. Reinicia el deployment después de agregar todas las variables

## Verificación

Después de configurar las variables, el endpoint `/health` debería responder:

```json
{
  "status": "ok",
  "service": "ZEUS-IA",
  "version": "1.0"
}
```
