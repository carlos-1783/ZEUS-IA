from fastapi import WebSocket, WebSocketDisconnect, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, List, Optional, Any
import json
import logging
import asyncio
import re
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from jose import JWTError
from jose.exceptions import JWTClaimsError, ExpiredSignatureError, JWTError as JoseJWTError

from app.db.session import get_db
from app.models.user import User
from app.core.auth import get_current_user_from_token
from app.core.config import settings
from app.schemas.user import UserInDB

logger = logging.getLogger(__name__)

# Caracteres de control prohibidos (NUL y C0 salvo \t \n \r), como en el guard HTTP de THALOS.
_WS_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

class ConnectionManager:
    """Conexiones WebSocket por USUARIO.

    Fase 2 / Step 1 (A1): la clave interna es "{user_id}:{client_id}". Antes era el
    `client_id` enviado por el cliente: otro usuario que conociera ese id sustituia el
    socket de la victima y recibia sus eventos, y una conexion sin autenticar con el mismo
    id lo borraba al cerrar. Ahora cada usuario tiene su propio espacio de ids y solo se
    retira el socket que se registro. No hay `broadcast`: todo envio va a un usuario."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[int, List[str]] = {}

    @staticmethod
    def connection_key(user_id: int, client_id: str) -> str:
        return f"{int(user_id)}:{client_id}"

    def register(self, websocket: WebSocket, client_id: str, user_id: int) -> str:
        key = self.connection_key(user_id, client_id)
        self.active_connections[key] = websocket  # misma clave = reconexion del MISMO usuario
        keys = self.user_connections.setdefault(int(user_id), [])
        if key not in keys:
            keys.append(key)
        logger.info("WS registrada user_id=%s conexiones=%s", user_id, len(keys))
        return key

    async def connect(self, websocket: WebSocket, client_id: str, user_id: int) -> str:
        await websocket.accept()
        return self.register(websocket, client_id, user_id)

    def unregister(self, key: str, user_id: int, websocket: Optional[WebSocket] = None) -> None:
        """Retira la conexion solo si sigue siendo `websocket` (si ya la sustituyo una
        reconexion del mismo usuario, no se toca)."""
        current = self.active_connections.get(key)
        if current is not None and (websocket is None or current is websocket):
            del self.active_connections[key]
            keys = self.user_connections.get(int(user_id), [])
            if key in keys:
                keys.remove(key)
            if not keys:
                self.user_connections.pop(int(user_id), None)

    def disconnect(self, client_id: str, user_id: int):
        self.unregister(self.connection_key(user_id, client_id), user_id)

    async def send_personal_message(self, message: str, key: str):
        ws = self.active_connections.get(key)
        if ws is not None:
            await ws.send_text(message)

    async def send_user_json(self, user_id: int, payload: dict):
        message = json.dumps(payload, default=str)
        for key in list(self.user_connections.get(user_id, [])):
            ws = self.active_connections.get(key)
            if ws is not None:
                await ws.send_text(message)


manager = ConnectionManager()

def get_current_websocket_user(
    websocket: WebSocket,
    token: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Optional[UserInDB]:
    """
    Authenticate user from WebSocket token using secure JWT validation
    
    Args:
        websocket: WebSocket connection
        token: JWT token from query params or headers
        db: Database session
        
    Returns:
        UserInDB if authentication is successful, None otherwise
    """
    if not token:
        logger.warning("No token provided for WebSocket authentication")
        return None
    
    try:
        # Use the secure JWT validation from jwt_auth
        from app.core.jwt_auth import decode_jwt_token
        
        # Validate token with allowed audiences
        try:
            # Try with all allowed audiences
            payload = decode_jwt_token(
                token, 
                audience=settings.JWT_AUDIENCE,  # This is now a list of allowed audiences
                require_audience=True
            )
            logger.debug(f"Authenticated with audience: {payload.get('aud')}")
        except (JWTError, JWTClaimsError, ExpiredSignatureError, JoseJWTError) as e:
            logger.error(f"JWT validation failed: {str(e)}")
            return None
        
        # Get user from database using the email in the token
        user_email = payload.get("email")
        if not user_email:
            logger.warning("No email found in token")
            return None
            
        # Get user directly from database
        from app.core.auth import get_user_by_email
        user = get_user_by_email(db, user_email)
        if not user:
            logger.warning(f"User not found in database: {user_email}")
            return None
            
        if not user.is_active:
            logger.warning(f"User is not active: {user_email}")
            return None
            
        logger.info(f"WebSocket authenticated for user {user.email}")
        return user
        
    except HTTPException as e:
        logger.error(f"WebSocket authentication error: {str(e.detail) if hasattr(e, 'detail') else str(e)}")
        return None
    except (JWTError, JWTClaimsError, ExpiredSignatureError, JoseJWTError) as e:
        logger.error(f"JWT validation error in WebSocket auth: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket auth: {str(e)}", exc_info=True)
        return None

_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
WS_MAX_MESSAGE_CHARS = 64 * 1024


def _ws_thalos_event(
    db: Session,
    websocket: WebSocket,
    *,
    decision: str,
    reason: str,
    user: Optional[User] = None,
    severity: Optional[str] = None,
) -> None:
    """Evento THALOS de la conexion WebSocket (conexion aceptada/rechazada, mensaje
    rechazado). Las conexiones son poco frecuentes: se registran todas."""
    try:
        import services.crm_office_service as crm_svc
        from services.thalos_request_guard_v1 import record_security_event

        company_id = None
        if user is not None:
            try:
                company_id = crm_svc.primary_company_id(db, user)
            except Exception:
                company_id = None
        record_security_event(
            db,
            event_type="websocket_guard",
            severity=severity or ("info" if decision == "allow" else "warning"),
            source="thalos_websocket_guard",
            details={"path": "/api/v1/ws/{client_id}", "decision": decision, "reason": reason},
            user=user,
            company_id=company_id,
            ip_address=websocket.client.host if websocket.client else None,
            action_taken=decision,
            decision_rule=reason,
        )
    except Exception:
        logger.exception("THALOS: no se pudo registrar el evento WebSocket")


async def _reject(websocket: WebSocket, db: Session, code: str, error_msg: str, user=None) -> None:
    _ws_thalos_event(db, websocket, decision="deny", reason=code, user=user)
    await websocket.send_text(json.dumps({"type": "auth_error", "error": error_msg, "code": code}))
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=error_msg)


async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket de eventos en tiempo real: ACEPTAR -> AUTENTICAR -> THALOS -> ESCUCHAR.

    Fase 2 / Step 1 (C2/A1): la conexion pasa por THALOS (usuario activo, client_id
    valido, evento allow/deny persistido) y cada mensaje se valida (tamano y caracteres
    de control). Las conexiones se registran por usuario: un client_id ajeno no da acceso
    a los eventos de otro usuario.
    """
    user = None
    conn_key: Optional[str] = None
    connection_accepted = False

    try:
        await websocket.accept()
        connection_accepted = True

        if not _CLIENT_ID_RE.match(client_id or ""):
            await _reject(websocket, db, "invalid_client_id", "Identificador de cliente no valido")
            return

        token = (
            websocket.query_params.get("token") or
            websocket.headers.get("authorization", "").replace("Bearer ", "")
        )
        if not token:
            await _reject(websocket, db, "missing_token", "No se proporcionó token de autenticación")
            return

        try:
            user = get_current_websocket_user(websocket, token, db)
        except (JWTError, JWTClaimsError, ExpiredSignatureError, JoseJWTError):
            logger.exception("[WebSocket] JWT validation error")
            user = None
        if not user:
            await _reject(websocket, db, "invalid_token", "Token de autenticación inválido o expirado")
            return
        if not user.is_active:
            await _reject(websocket, db, "inactive_user", "La cuenta del usuario no está activa", user=user)
            user = None
            return

        _ws_thalos_event(db, websocket, decision="allow", reason="websocket_connected", user=user)
        conn_key = manager.register(websocket, client_id, user.id)

        await manager.send_personal_message(
            json.dumps({
                "type": "connection_established",
                "client_id": client_id,
                "user_id": user.id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "success"
            }),
            conn_key
        )

        last_activity = datetime.utcnow()

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                last_activity = datetime.utcnow()

                if len(data) > WS_MAX_MESSAGE_CHARS or _WS_CONTROL_RE.search(data):
                    reason = "message_too_large" if len(data) > WS_MAX_MESSAGE_CHARS else "control_characters"
                    _ws_thalos_event(db, websocket, decision="deny", reason=reason, user=user)
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Mensaje rechazado")
                    break

                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": "Invalid JSON format",
                            "code": "invalid_json",
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        conn_key
                    )
                    continue
                if not isinstance(message, dict):
                    message = {"type": None, "value": message}

                message_type = message.get("type")
                if message_type == "heartbeat":
                    await manager.send_personal_message(
                        json.dumps({"type": "heartbeat_ack", "timestamp": datetime.utcnow().isoformat()}),
                        conn_key
                    )
                elif message_type == "auth":
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "auth_ack",
                            "status": "authenticated",
                            "user_id": user.id,
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        conn_key
                    )
                elif message_type == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong", "timestamp": datetime.utcnow().isoformat()}),
                        conn_key
                    )
                else:
                    response = {
                        "type": "message_ack",
                        "message_id": message.get("message_id", str(uuid.uuid4())),
                        "received_at": datetime.utcnow().isoformat(),
                        "status": "received"
                    }
                    if len(data) < 1000:
                        response["received"] = message
                    await manager.send_personal_message(json.dumps(response), conn_key)

            except asyncio.TimeoutError:
                if (datetime.utcnow() - last_activity).total_seconds() > 300:
                    logger.info("Cerrando WebSocket inactivo user_id=%s", user.id)
                    await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason="Connection idle for too long")
                    break
                try:
                    await manager.send_personal_message(
                        json.dumps({"type": "ping", "timestamp": datetime.utcnow().isoformat()}),
                        conn_key
                    )
                except Exception as ping_error:
                    logger.warning("Ping WebSocket fallido user_id=%s: %s", user.id, type(ping_error).__name__)
                    raise WebSocketDisconnect()

            except WebSocketDisconnect:
                break

            except Exception as msg_error:
                logger.error("Error procesando mensaje WebSocket user_id=%s: %s", user.id, type(msg_error).__name__)
                await manager.send_personal_message(
                    json.dumps({
                        "type": "error",
                        "message": "Error processing message",
                        "code": "processing_error",
                        "timestamp": datetime.utcnow().isoformat()
                    }),
                    conn_key
                )

    except WebSocketDisconnect:
        logger.info("[WebSocket] desconexion user_id=%s", getattr(user, "id", None))

    except Exception as conn_error:
        logger.error("[WebSocket] error de conexion: %s", type(conn_error).__name__)
        if connection_accepted:
            try:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
            except Exception:
                pass

    finally:
        # Solo se retira la conexion que ESTE handler registro (nunca la de otro usuario).
        if conn_key and user is not None:
            manager.unregister(conn_key, user.id, websocket)
