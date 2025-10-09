# 🚀 ZEUS-IA - Guía de Usuario

## 📋 ¿Qué es ZEUS-IA?

ZEUS-IA es tu sistema de inteligencia artificial que incluye:
- **Frontend**: Interfaz web moderna (Vue.js)
- **Backend**: API segura (FastAPI)
- **WebSocket**: Comunicación en tiempo real
- **Base de datos**: Almacenamiento seguro

## 🎯 Cómo Usar la Aplicación

### Para Desarrollo Local (Tu Computadora)

#### 1. **Iniciar la Aplicación**
```
Doble clic en: Run-local.bat
```
Esto abrirá:
- ✅ Backend en: http://localhost:8000
- ✅ Frontend en: http://localhost:5173

#### 2. **Detener la Aplicación**
```
Doble clic en: Stop-local.bat
```

#### 3. **Ver la Aplicación**
- Abre tu navegador
- Ve a: http://localhost:5173
- ¡Ya puedes usar ZEUS-IA!

### Para Producción (Servidor)

#### 1. **Desplegar en Servidor**
```bash
# En el servidor, ejecutar:
sudo ./scripts/deploy-production.sh
```

#### 2. **Verificar que Funciona**
```bash
# En el servidor, ejecutar:
sudo ./scripts/validate-production.sh
```

## 🔧 Solución de Problemas

### ❌ Error: "Puerto 5173 ocupado"
**Solución:**
1. Ejecuta `Stop-local.bat`
2. Espera 10 segundos
3. Ejecuta `Run-local.bat` de nuevo

### ❌ Error: "Backend no responde"
**Solución:**
1. Verifica que el archivo `backend/.env` existe
2. Ejecuta `Stop-local.bat`
3. Ejecuta `Run-local.bat` de nuevo

### ❌ Error: "Frontend no carga"
**Solución:**
1. Ve a la carpeta `frontend`
2. Ejecuta: `npm install`
3. Ejecuta: `npm run build`
4. Ejecuta `Run-local.bat`

## 📁 Archivos Importantes

### Para Desarrollo
- `Run-local.bat` - Iniciar aplicación
- `Stop-local.bat` - Detener aplicación
- `frontend/` - Código del frontend
- `backend/` - Código del backend

### Para Producción
- `scripts/deploy-production.sh` - Desplegar en servidor
- `scripts/validate-production.sh` - Verificar funcionamiento
- `nginx/zeus-ia.conf` - Configuración del servidor web
- `PRODUCTION.md` - Documentación técnica

## 🌐 URLs Importantes

### Desarrollo Local
- **Aplicación**: http://localhost:5173
- **API**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs

### Producción
- **Aplicación**: https://zeus-ia.com
- **API**: https://zeus-ia.com/api/v1
- **WebSocket**: wss://zeus-ia.com/ws

## 📞 ¿Necesitas Ayuda?

### Si algo no funciona:
1. **Revisa los logs** en las ventanas que se abren
2. **Ejecuta Stop-local.bat** y luego Run-local.bat
3. **Verifica** que los puertos 5173 y 8000 estén libres

### Comandos Útiles:
```bash
# Ver qué está usando el puerto 5173
netstat -ano | findstr :5173

# Ver qué está usando el puerto 8000
netstat -ano | findstr :8000

# Matar proceso por PID (reemplaza XXXX con el número)
taskkill /F /PID XXXX
```

## 🎉 ¡Listo!

Ahora ya sabes cómo usar ZEUS-IA. Solo necesitas:
1. **Doble clic en Run-local.bat** para iniciar
2. **Abrir http://localhost:5173** en tu navegador
3. **¡Disfrutar de tu aplicación!**
