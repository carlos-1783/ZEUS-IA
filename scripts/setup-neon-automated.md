# 🚀 CONFIGURACIÓN AUTOMATIZADA DE NEON

## 📋 INSTRUCCIONES PASO A PASO

### **PASO 1: Crear cuenta en Neon**

1. **Ve a:** https://neon.tech
2. **Haz clic en:** "Sign up" o "Get Started"
3. **Regístrate con GitHub** (recomendado) o email
4. **Verifica tu email** si usas email

### **PASO 2: Crear proyecto**

1. **Haz clic en:** "New Project"
2. **Nombre:** `zeus-ia-production`
3. **Región:** `EU West (eu-west-1)` o la más cercana a ti
4. **PostgreSQL:** Versión 15 (por defecto)
5. **Haz clic en:** "Create Project"

### **PASO 3: Obtener URL de conexión**

1. **En el dashboard de Neon, busca:** "Connection Details"
2. **Copia la URL completa** que se ve así:
   ```
   postgresql://neondb_owner:npg_xxxxx@ep-xxxxx.eu-west-1.aws.neon.tech/neondb?sslmode=require
   ```
3. **¡GUARDA ESTA URL!** La necesitarás para Railway

### **PASO 4: Configurar en Railway**

1. **Ve a Railway Dashboard** → Tu proyecto ZEUS-IA
2. **Ve a:** Variables → Raw Editor
3. **Busca la línea:** `DATABASE_URL=sqlite:///./zeus.db`
4. **Reemplázala con:** `DATABASE_URL=tu_url_de_neon_aqui`
5. **Guarda los cambios**

### **PASO 5: Ejecutar migraciones**

Después de actualizar Railway, las migraciones se ejecutarán automáticamente en el próximo deployment.

---

## 🔧 CONFIGURACIÓN ADICIONAL (OPCIONAL)

### **Connection Pooling en Neon**

1. **Ve a:** Settings → Connection Pooling
2. **Habilita:** "Connection pooling"
3. **Pool size:** 10-15 conexiones
4. **Usa la URL del pool** (tiene `-pooler` en el hostname)

### **Variables adicionales para Railway**

```env
# Base de datos
DATABASE_URL=postgresql://neondb_owner:npg_xxxxx@ep-xxxxx.eu-west-1.aws.neon.tech/neondb?sslmode=require

# Pooling (opcional)
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Logs de base de datos
DB_ECHO=False  # Cambiar a True para debug
```

---

## ✅ VERIFICACIÓN

### **Después de configurar:**

1. **Railway debe reconstruir automáticamente**
2. **En los logs verás:** "Database connection successful"
3. **El endpoint /health debe seguir funcionando**
4. **En Neon dashboard verás:** Conexiones activas

### **Si hay problemas:**

1. **Verifica la URL** - Debe empezar con `postgresql://`
2. **Verifica SSL** - Debe incluir `?sslmode=require`
3. **Verifica permisos** - La cuenta debe tener acceso al proyecto

---

## 🎯 RESULTADO ESPERADO

Después de configurar Neon:

- ✅ **Base de datos PostgreSQL en la nube**
- ✅ **Railway conectado a Neon**
- ✅ **Migraciones ejecutadas automáticamente**
- ✅ **Backend usando PostgreSQL en lugar de SQLite**

---

**¿Ya tienes acceso a Neon?** Si no, sigue el PASO 1 y 2, luego comparte la URL de conexión para continuar.
