# 🚀 ZEUS-IA

**Sistema Empresarial de Inteligencia Artificial**

Plataforma completa de IA con gestión de clientes, comandos por voz, integración con APIs y dashboard en tiempo real.

---

## ⚡ INICIO RÁPIDO (1 CLICK)

### Para usar ZEUS-IA localmente:

**HAZ DOBLE CLICK EN:**
```
START.bat
```

**Eso es todo.** El script hará automáticamente:
- ✅ Liberar puertos
- ✅ Iniciar backend y frontend
- ✅ Abrir el navegador

**Para detener:**
```
STOP.bat
```

---

## 📋 CREDENCIALES POR DEFECTO

```
Email:    marketingdigitalper.seo@gmail.com
Password: Carnay19
```

---

## 🌐 URLs DE ACCESO

| Servicio | URL | Descripción |
|----------|-----|-------------|
| **Frontend** | http://localhost:5173 | Aplicación principal |
| **API Docs** | http://localhost:8000/docs | Documentación Swagger |
| **Health Check** | http://localhost:8000/health | Estado del servidor |

---

## 🏗️ ARQUITECTURA

```
ZEUS-IA
├── Backend (FastAPI)
│   ├── FastAPI 0.115.0
│   ├── PostgreSQL (Railway)
│   ├── JWT Authentication
│   ├── WebSocket Support
│   └── RESTful API
│
└── Frontend (Vue.js + Vite)
    ├── Vue 3 + Composition API
    ├── Vite 4.5
    ├── TailwindCSS
    ├── Pinia (State Management)
    └── Axios (HTTP Client)
```

---

## 🚀 DEPLOYMENT EN PRODUCCIÓN

### Railway (Recomendado)

**1. Preparar archivos:**
```bash
git add .
git commit -m "Ready for production"
git push origin main
```

**2. En Railway Dashboard:**
- Ir a https://railway.app
- Crear nuevo servicio desde GitHub
- Railway detectará `railway.toml` automáticamente
- Configurar variables de entorno

**3. Variables de entorno necesarias:**
```env
# Backend
SECRET_KEY=tu_secret_key_64_caracteres
DATABASE_URL=postgresql://user:pass@host:5432/db
CORS_ORIGINS=https://tu-frontend-url.com

# Frontend  
VITE_API_URL=https://tu-backend-url.com
VITE_API_BASE_URL=https://tu-backend-url.com/api/v1
```

**Guía completa:** Ver `DEPLOY_TO_RAILWAY_COMPLETE.md`

---

## 📦 ESTRUCTURA DEL PROYECTO

```
ZEUS-IA/
├── INICIAR_ZEUS.bat         # Iniciar todo automáticamente
├── DETENER_ZEUS.bat         # Detener servicios
├── railway.toml              # Config de Railway
├── .railwayignore           # Archivos a ignorar en deploy
│
├── backend/                  # Backend FastAPI
│   ├── app/
│   │   ├── api/v1/          # Endpoints API
│   │   ├── core/            # Configuración, seguridad
│   │   ├── db/              # Database
│   │   ├── models/          # SQLAlchemy models
│   │   └── schemas/         # Pydantic schemas
│   ├── requirements.txt
│   └── main.py
│
└── frontend/                 # Frontend Vue.js
    ├── src/
    │   ├── views/           # Páginas
    │   ├── components/      # Componentes reutilizables
    │   ├── stores/          # Pinia stores
    │   ├── router/          # Vue Router
    │   └── api/             # API client
    ├── package.json
    └── vite.config.js
```

---

## 🛠️ CARACTERÍSTICAS

### Backend (FastAPI)
- ✅ **Autenticación JWT** con refresh tokens
- ✅ **WebSocket** para comunicación en tiempo real
- ✅ **Base de datos PostgreSQL** con SQLAlchemy
- ✅ **Migraciones** con Alembic
- ✅ **Documentación automática** (Swagger/OpenAPI)
- ✅ **CORS configurado** para producción
- ✅ **Health checks** para monitoring
- ✅ **Logging estructurado**

### Frontend (Vue.js)
- ✅ **Vue 3** con Composition API
- ✅ **Vite** para builds ultra-rápidos
- ✅ **TailwindCSS** para estilos
- ✅ **Pinia** para gestión de estado
- ✅ **Vue Router** con guardias de autenticación
- ✅ **Axios** con interceptors
- ✅ **WebSocket** client integrado
- ✅ **Responsive design**

### Funcionalidades
- ✅ **Gestión de usuarios** con roles
- ✅ **Dashboard en tiempo real**
- ✅ **Gestión de clientes (CRM)**
- ✅ **Comandos por voz**
- ✅ **Integración con APIs externas**
- ✅ **Sistema de notificaciones**
- ✅ **Reportes y análisis**

---

## 🔧 DESARROLLO MANUAL

Si necesitas ejecutar manualmente:

### Backend:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## 📊 TECNOLOGÍAS

### Backend:
- **FastAPI** 0.115.0 - Framework web
- **Uvicorn** - ASGI server
- **SQLAlchemy** 2.0 - ORM
- **Alembic** - Migraciones
- **PostgreSQL** - Base de datos
- **Python-Jose** - JWT tokens
- **Passlib** - Password hashing
- **Pydantic** 2.0 - Validación de datos

### Frontend:
- **Vue.js** 3.3 - Framework UI
- **Vite** 4.5 - Build tool
- **Vue Router** 4.2 - Routing
- **Pinia** 2.1 - State management
- **Axios** 1.6 - HTTP client
- **TailwindCSS** 4.1 - CSS framework
- **TypeScript** 5.3 - Type safety

---

## 💰 COSTOS DE PRODUCCIÓN

### Railway (Recomendado):
- **Plan Free:** $5 crédito/mes
- **Backend:** ~$3/mes
- **Frontend:** ~$1-2/mes
- **PostgreSQL:** Incluido
- **Total:** $4-5/mes (GRATIS con crédito)

---

## 🔒 SEGURIDAD

- ✅ JWT con refresh tokens
- ✅ Password hashing con bcrypt
- ✅ CORS configurado
- ✅ HTTPS en producción (Railway)
- ✅ Environment variables
- ✅ Input validation (Pydantic)
- ✅ SQL injection protection (SQLAlchemy)
- ✅ Rate limiting (configurable)

---

## 📝 SCRIPTS DISPONIBLES

| Script | Descripción |
|--------|-------------|
| `INICIAR_ZEUS.bat` | Inicia backend + frontend automáticamente |
| `DETENER_ZEUS.bat` | Detiene todos los servicios |
| `DEPLOY_TO_RAILWAY_COMPLETE.md` | Guía de deployment en Railway |
| `DEPLOYMENT_ANALYSIS.md` | Análisis de plataformas |

---

## 🐛 TROUBLESHOOTING

### Error: Puerto 8000 en uso
```bash
DETENER_ZEUS.bat
```

### Error: ModuleNotFoundError
```bash
cd backend
pip install -r requirements.txt
```

### Error: npm install falla
```bash
cd frontend
rm -rf node_modules
npm install
```

### Frontend no se conecta al backend
1. Verificar que backend esté corriendo: http://localhost:8000/docs
2. Verificar variables de entorno en `frontend/.env`
3. Limpiar caché del navegador (Ctrl+Shift+Del)

---

## 📞 SOPORTE

- **Documentación:** Ver archivos `.md` en la raíz
- **API Docs:** http://localhost:8000/docs
- **Logs Backend:** Ventana "ZEUS-IA Backend"
- **Logs Frontend:** Ventana "ZEUS-IA Frontend"

---

## 📄 LICENCIA

Propietario: ZEUS-IA  
Versión: 1.0.0  
Todos los derechos reservados.

---

## ✨ SIGUIENTE PASO

**Para empezar a usar ZEUS-IA:**

### HAZ DOBLE CLICK EN: `INICIAR_ZEUS.bat`

**Eso es todo. En 30 segundos tendrás ZEUS-IA corriendo.** 🚀
# Railway deployment retry
# Force Railway redeploy
