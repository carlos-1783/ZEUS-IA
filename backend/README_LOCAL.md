# ZEUS-IA Backend - Guía de Inicio Local

## ✅ Problemas Resueltos

1. **Migración de Base de Datos**: Se agregaron automáticamente las columnas faltantes:
   - `email_gestor_fiscal`
   - `email_asesor_legal`
   - `autoriza_envio_documentos_a_asesores`
   - `company_name` ✅ (recién agregada)
   - `employees` ✅ (recién agregada)

2. **Orden de Ejecución**: La migración ahora se ejecuta ANTES de crear las tablas, evitando errores de columnas faltantes.

## 🚀 Inicio Rápido

### Opción 1: Script Automático (Recomendado)

**Windows:**
```bash
cd backend
fix_and_start.bat
```

**Linux/Mac:**
```bash
cd backend
chmod +x start_local.sh
./start_local.sh
```

### Opción 2: Manual

1. **Activar entorno virtual:**
   ```bash
   cd backend
   venv\Scripts\activate  # Windows
   # o
   source venv/bin/activate  # Linux/Mac
   ```

2. **Instalar dependencias (si es necesario):**
   ```bash
   pip install -r requirements.txt
   ```

3. **Iniciar servidor:**
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## 🔍 Verificación

Una vez iniciado, verifica que el backend esté funcionando:

```bash
# Health check
curl http://localhost:8000/health

# Debería responder: {"status":"healthy","service":"zeus-ia"}
```

## 🌐 URLs Disponibles

- **Backend**: http://localhost:8000
- **API Base**: http://localhost:8000/api/v1
- **Health Check**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/api/docs

## ⚠️ Solución de Problemas

### Error: "no such column: users.email_gestor_fiscal"

**Solución**: La migración se ejecuta automáticamente al iniciar. Si persiste:
```bash
cd backend
python -c "import sys; sys.path.insert(0, '.'); from app.db.base import _migrate_firewall_columns; from app.core.config import settings; _migrate_firewall_columns()"
```

### Error: "Port 8000 already in use"

**Solución**: 
```bash
# Windows
netstat -ano | findstr :8000
taskkill /F /PID <PID>

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Frontend no puede conectar

**Verifica**:
1. Backend corriendo en http://localhost:8000
2. Frontend configurado para usar `http://localhost:8000/api/v1`
3. CORS configurado (ya incluido para localhost:5173)

## 📝 Notas

- La base de datos SQLite se crea automáticamente en `backend/zeus.db`
- Las migraciones se ejecutan automáticamente al iniciar
- El backend escucha en `0.0.0.0:8000` para permitir conexiones desde cualquier interfaz

