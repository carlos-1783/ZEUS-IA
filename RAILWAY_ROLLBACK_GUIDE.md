# 🚀 ZEUS-IA - Guía de Rollback Railway DevOps

## 🎯 **PROBLEMA IDENTIFICADO:**
- ❌ Backend Railway con error 500
- ❌ Endpoint `/api/v1/health` fallando
- ❌ Variables de entorno posiblemente incorrectas

## 🔄 **ACCIÓN REQUERIDA: ROLLBACK**

### **1. 🏗️ Acceder a Railway Dashboard:**
1. Ir a: https://railway.app/dashboard
2. Seleccionar proyecto: `zeus-ia-production`
3. Ir a: **Deployments**

### **2. 📅 Identificar versión estable:**
**Buscar commit donde:**
- ✅ Todos los endpoints funcionaban
- ✅ WebSocket conectaba correctamente
- ✅ Sin errores 500
- ✅ Fecha aproximada: cuando Zeus estaba estable

### **3. 🔄 Realizar rollback:**
1. **Click en el commit estable**
2. **Click "Rollback"**
3. **Confirmar rollback**
4. **Esperar redeploy (2-3 minutos)**

### **4. 🧪 Verificar rollback:**
```bash
# Health check
curl https://zeus-ia-production-16d8.up.railway.app/api/v1/health

# Login test
curl -X POST https://zeus-ia-production-16d8.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=marketingdigitalper.seo@gmail.com&password=Carnay19"
```

## 📊 **ESTADO ESPERADO POST-ROLLBACK:**

### ✅ **Endpoints funcionando:**
- `GET /api/v1/health` → 200 OK
- `GET /api/v1/auth/me` → 200 OK (con token)
- `POST /api/v1/auth/login` → 200 OK
- `WebSocket /api/v1/ws/{client_id}` → 101 Switching Protocols

### ✅ **Logs Railway:**
- Sin errores 500
- Backend iniciado correctamente
- WebSocket aceptando conexiones
- Usuario autenticado correctamente

## 🎯 **PRÓXIMOS PASOS POST-ROLLBACK:**

1. **Verificar variables de entorno**
2. **Reiniciar servicios si es necesario**
3. **Configurar frontend para Railway**
4. **Verificar WebSocket**
5. **Confirmar estado estable**

---

## 🚨 **SI ROLLBACK NO FUNCIONA:**

### **Opción A - Reset completo:**
1. **Railway → Settings → Delete Service**
2. **Recrear servicio desde GitHub**
3. **Configurar variables desde cero**

### **Opción B - Deploy manual:**
1. **Railway → Deploy → Manual Deploy**
2. **Seleccionar commit específico**
3. **Forzar redeploy**

---

**¡Rollback es la solución más rápida para restaurar estado estable!** 🚀
