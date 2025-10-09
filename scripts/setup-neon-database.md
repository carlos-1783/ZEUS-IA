# 🗄️ Configuración de Base de Datos Neon

## Paso 1: Crear cuenta en Neon

1. **Ve a https://neon.tech**
2. **Crea una cuenta gratuita** (permite hasta 3 bases de datos)
3. **Verifica tu email**

## Paso 2: Crear proyecto

1. **Haz clic en "New Project"**
2. **Nombre del proyecto**: `zeus-ia-prod`
3. **Selecciona la región más cercana** (ej: US East, EU West)
4. **Selecciona PostgreSQL 15**

## Paso 3: Configurar base de datos

1. **Copia la URL de conexión** que aparece en el dashboard
2. **Formato esperado**: 
   ```
   postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require
   ```

## Paso 4: Actualizar variables de entorno

1. **Edita el archivo `neon.env`**
2. **Reemplaza la URL con tu URL real**
3. **Guarda el archivo**

## Paso 5: Ejecutar migraciones

```bash
# Instalar dependencias
cd backend
pip install -r requirements.txt

# Configurar variables de entorno
export DATABASE_URL="tu_url_de_neon_aqui"

# Ejecutar migraciones
alembic upgrade head
```

## Paso 6: Verificar conexión

```bash
# Conectar con psql
psql "tu_url_de_neon_aqui"

# Verificar tablas
\dt

# Salir
\q
```

## Configuración de Pooling (Opcional)

Neon incluye connection pooling automático, pero puedes optimizarlo:

1. **Ve a la configuración del proyecto**
2. **Habilita "Connection Pooling"**
3. **Configura el pool size** (recomendado: 10-20 conexiones)

## Variables de entorno necesarias

```bash
DATABASE_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/zeus_ia_prod?sslmode=require
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

## Límites de la cuenta gratuita

- ✅ **Hasta 3 bases de datos**
- ✅ **0.5 GB de almacenamiento**
- ✅ **100 horas de computación/mes**
- ✅ **Connection pooling incluido**
- ✅ **Backups automáticos**

## Próximos pasos

Una vez configurada la base de datos:

1. ✅ **Actualiza el archivo `neon.env`**
2. ✅ **Ejecuta las migraciones**
3. ✅ **Verifica la conexión**
4. 🚀 **Procede al despliegue del backend**
