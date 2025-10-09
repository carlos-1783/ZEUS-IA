from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from dotenv import load_dotenv

# Configuración simplificada
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "6895b411b45b5946b46bf7970f4d7e17aa69dfc5da4696cb15686625e5eccf2b")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Modelos
class TokenData(BaseModel):
    username: Optional[str] = None

# Configuración de seguridad
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Inicializar la aplicación FastAPI
app = FastAPI()

# Middleware para añadir cabeceras de seguridad
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Cabeceras de seguridad (relajadas para desarrollo)
    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",  # Relajado para desarrollo
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cross-Origin-Embedder-Policy": "unsafe-none",  # Deshabilitar COEP
        "Cross-Origin-Opener-Policy": "unsafe-none",    # Deshabilitar COOP
        "Cross-Origin-Resource-Policy": "cross-origin", # Permitir recursos cross-origin
        "Access-Control-Allow-Origin": "*",  # Permitir todos los orígenes
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, Origin, Accept",
        "Access-Control-Allow-Credentials": "true"
    }
    
    # Añadir cabeceras a la respuesta
    for header, value in security_headers.items():
        response.headers[header] = value
        
    return response


# Configuración de CORS mejorada
# Lista de orígenes permitidos
origins = [
    "http://localhost:5173",    # Frontend en desarrollo
    "http://127.0.0.1:5173",    # Frontend en desarrollo (alternativa)
    "http://localhost:8000",    # Backend
    "http://127.0.0.1:8000",    # Backend (alternativa)
    "*"  # Permitir todos los orígenes en desarrollo
]

# Métodos HTTP permitidos
allowed_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"]

# Cabeceras permitidas
allowed_headers = [
    "Content-Type",
    "Authorization",
    "Access-Control-Allow-Origin",
    "Access-Control-Allow-Headers",
    "Access-Control-Allow-Methods",
    "Access-Control-Allow-Credentials",
    "X-Requested-With",
    "Origin",
    "Accept",
    "Cache-Control",
    "Pragma"
]

# Añadir middleware CORS con configuración mejorada
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=allowed_methods,
    allow_headers=allowed_headers,
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
    max_age=3600,  # Tiempo de caché para las opciones CORS (1 hora)
)

# Manejador de conexiones WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[Dict[str, Any]] = []

    async def connect(self, websocket: WebSocket, user: str):
        await websocket.accept()
        self.active_connections.append({"ws": websocket, "user": user})
        print(f"Nueva conexión de {user}. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections = [conn for conn in self.active_connections if conn["ws"] != websocket]
        print(f"Conexión cerrada. Total restante: {len(self.active_connections)}")

    async def send_personal_message(self, message: Any, websocket: WebSocket):
        try:
            if isinstance(message, dict):
                await websocket.send_json(message)
            else:
                await websocket.send_text(str(message))
        except Exception as e:
            print(f"Error enviando mensaje: {e}")

    async def broadcast(self, message: Any, exclude: WebSocket = None):
        for connection in self.active_connections:
            if exclude is None or connection["ws"] != exclude:
                await self.send_personal_message(message, connection["ws"])

manager = ConnectionManager()

# Funciones de autenticación
async def get_current_user(token: str):
    # Quitar prefijo 'Bearer ' si está presente
    if token and token.startswith('Bearer '):
        token = token[len('Bearer '):]
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        print("[JWT] Verificando token con SECRET_KEY:", SECRET_KEY)
        print("[JWT] Algoritmo:", ALGORITHM)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return {"username": username}
    except JWTError:
        raise credentials_exception

# Endpoint WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print(f"🔌 Intento de conexión WebSocket recibido")
    print(f"🔌 Headers: {dict(websocket.headers)}")
    print(f"🔌 Query params: {dict(websocket.query_params)}")
    
    try:
        # Aceptar la conexión primero para poder enviar mensajes de error
        print(f"🔌 Aceptando conexión WebSocket...")
        await websocket.accept()
        print(f"✅ Conexión WebSocket aceptada")
        
        # Obtener el token de los query parameters
        token = websocket.query_params.get("token")
        print(f"🔑 Token obtenido de query params: {token[:50] if token else 'None'}...")
        
        if not token:
            print("❌ Error: No se proporcionó token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Se requiere autenticación")
            return
    except Exception as e:
        print(f"❌ Error al aceptar conexión WebSocket: {e}")
        return
    
    # Quitar prefijo 'Bearer ' si está presente
    if token.startswith('Bearer '):
        token = token[len('Bearer '):]
    
    try:
        # Verificar token
        print(f"🔍 Verificando token: {token[:50]}...")
        user = await get_current_user(token)
        username = user["username"]
        print(f"✅ Usuario autenticado: {username}")
        
        # Conectar al WebSocket
        print(f"🔗 Conectando usuario {username} al WebSocket...")
        await manager.connect(websocket, username)
        print(f"✅ Usuario {username} conectado al WebSocket")
        
        # Enviar mensaje de bienvenida
        await manager.send_personal_message({
            "type": "connection_established",
            "message": f"Bienvenido {username}",
            "status": "connected"
        }, websocket)
        
        # Mantener la conexión abierta
        while True:
            try:
                data = await websocket.receive_text()
                print(f"Mensaje de {username}: {data}")
                
                # Procesar mensaje recibido
                await manager.send_personal_message({
                    "type": "message",
                    "content": f"Recibido: {data}",
                    "status": "success"
                }, websocket)
                
            except WebSocketDisconnect:
                print(f"Usuario {username} se desconectó")
                await manager.broadcast({
                    "type": "disconnection",
                    "message": f"Usuario {username} se ha desconectado",
                    "status": "disconnected"
                }, websocket)
                break
                
    except HTTPException as e:
        error_msg = f"❌ Error de autenticación: {e.detail}"
        print(error_msg)
        try:
            await websocket.send_json({
                "type": "error",
                "message": error_msg,
                "status": "authentication_error"
            })
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except Exception as e:
            print(f"Error al enviar mensaje de error: {str(e)}")
    except Exception as e:
        error_msg = f"❌ Error en WebSocket: {str(e)}"
        print(error_msg)
        print(f"❌ Tipo de error: {type(e).__name__}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": error_msg,
                "status": "error"
            })
            await websocket.close()
        except:
            pass
    finally:
        try:
            manager.disconnect(websocket)
            print(f"Conexión WebSocket cerrada para {username if 'username' in locals() else 'usuario desconocido'}")
        except Exception as e:
            print(f"Error al desconectar: {str(e)}")

# Endpoint de prueba
@app.get("/")
async def read_root():
    return {"message": "Servidor WebSocket funcionando"}

# Iniciar el servidor
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )