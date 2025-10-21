from fastapi import WebSocket, WebSocketDisconnect, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, List, Optional, Any
import json
import logging
import asyncio
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

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[int, List[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: int):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        
        if client_id not in self.user_connections[user_id]:
            self.user_connections[user_id].append(client_id)
        
        logger.info(f"Client {client_id} connected. User {user_id} now has {len(self.user_connections[user_id])} connections.")

    def disconnect(self, client_id: str, user_id: int):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        if user_id in self.user_connections and client_id in self.user_connections[user_id]:
            self.user_connections[user_id].remove(client_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        logger.info(f"Client {client_id} disconnected. User {user_id} has {len(self.user_connections.get(user_id, []))} remaining connections.")

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

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

async def websocket_endpoint(
    websocket: WebSocket, 
    client_id: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time communication
    
    Args:
        websocket: The WebSocket connection
        client_id: Unique client identifier
        db: Database session
    """
    # NO hacer accept aquí - se hace en manager.connect()
    # Initialize user as None for cleanup in finally block
    user = None
    connection_active = True
    
    try:
        # Get token from query parameters or headers
        token = (
            websocket.query_params.get("token") or
            websocket.headers.get("authorization", "").replace("Bearer ", "")
        )
        
        if not token:
            error_msg = "No se proporcionó token de autenticación"
            logger.warning(f"WebSocket connection rejected: {error_msg}")
            await websocket.send_text(json.dumps({
                "type": "auth_error",
                "error": error_msg,
                "code": "missing_token"
            }))
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=error_msg
            )
            return
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=error_msg
            )
            connection_active = False
            return
        
        # Authenticate user with detailed error handling
        try:
            user = get_current_websocket_user(websocket, token, db)
            
            if not user:
                error_msg = "Token de autenticación inválido o expirado"
                logger.warning(f"WebSocket connection rejected: {error_msg}")
                await websocket.send_text(json.dumps({
                    "type": "auth_error",
                    "error": error_msg,
                    "code": "invalid_token"
                }))
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason=error_msg
                )
                connection_active = False
                return
                
            if not user.is_active:
                error_msg = "La cuenta del usuario no está activa"
                logger.warning(f"WebSocket connection rejected: {error_msg}")
                await websocket.send_text(json.dumps({
                    "type": "auth_error",
                    "error": error_msg,
                    "code": "inactive_user"
                }))
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason=error_msg
                )
                connection_active = False
                return
                
        except (JWTError, JWTClaimsError, ExpiredSignatureError, JoseJWTError) as e:
            error_msg = f"Error de validación del token: {str(e)}"
            logger.error(f"WebSocket JWT validation error: {error_msg}")
            error_details = {
                "type": "auth_error",
                "error": "Token de autenticación inválido",
                "code": "jwt_validation_error"
            }
            if "audience" in str(e).lower():
                error_details["details"] = "Audiencia del token no válida. Por favor, obtenga un nuevo token de autenticación."
            else:
                error_details["details"] = str(e)
                
            await websocket.send_text(json.dumps(error_details))
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=error_msg
            )
            connection_active = False
            return
        
        # Register the connection
        try:
            await manager.connect(websocket, client_id, user.id)
            logger.info(f"WebSocket connected: client={client_id}, user_id={user.id}")
            
            # Send initial connection confirmation
            await manager.send_personal_message(
                json.dumps({
                    "type": "connection_established",
                    "client_id": client_id,
                    "user_id": user.id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "success"
                }),
                client_id
            )
            
            # Track last activity for timeout
            last_activity = datetime.utcnow()
            
            # Main message loop
            while True:
                try:
                    # Set a timeout for receiving messages (30 seconds)
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )
                    
                    # Update last activity time
                    last_activity = datetime.utcnow()
                    
                    try:
                        message = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON from {client_id}")
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "error",
                                "message": "Invalid JSON format",
                                "code": "invalid_json",
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            client_id
                        )
                        continue
                    
                    # Log message (sensitive data should be redacted in production)
                    log_msg = f"Received message from client={client_id}, user_id={user.id}"
                    if message.get('type') not in ['heartbeat', 'ping']:  # Skip logging heartbeats/pings
                        logger.debug(f"{log_msg}: {message}")
                    
                    # Handle different message types
                    message_type = message.get("type")
                    
                    if message_type == "heartbeat":
                        # Acknowledge heartbeat
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "heartbeat_ack",
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            client_id
                        )
                    
                    elif message_type == "auth":
                        # Already authenticated, just acknowledge
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "auth_ack",
                                "status": "authenticated",
                                "user_id": user.id,
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            client_id
                        )
                    
                    elif message_type == "ping":
                        # Respond to ping with pong
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            client_id
                        )
                    
                    else:
                        # Echo back the message with additional metadata
                        response = {
                            "type": "message_ack",
                            "message_id": message.get("message_id", str(uuid.uuid4())),
                            "received_at": datetime.utcnow().isoformat(),
                            "status": "received"
                        }
                        
                        # Include the original message if it's not too large
                        if len(data) < 1000:  # 1KB limit
                            response["received"] = message
                        
                        await manager.send_personal_message(
                            json.dumps(response),
                            client_id
                        )
                
                except asyncio.TimeoutError:
                    # Check if we should close the connection due to inactivity
                    if (datetime.utcnow() - last_activity).total_seconds() > 300:  # 5 minutes
                        logger.info(f"Closing idle WebSocket connection: {client_id}")
                        await websocket.close(
                            code=status.WS_1000_NORMAL_CLOSURE,
                            reason="Connection idle for too long"
                        )
                        break
                    
                    # Send a ping to check if the client is still there
                    try:
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "ping",
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            client_id
                        )
                    except Exception as ping_error:
                        logger.warning(f"Failed to send ping to {client_id}: {str(ping_error)}")
                        raise WebSocketDisconnect()
                
                except WebSocketDisconnect:
                    logger.info(f"Client {client_id} disconnected")
                    break
                    
                except Exception as msg_error:
                    logger.error(f"Error processing message from {client_id}: {str(msg_error)}")
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "error",
                            "message": "Error processing message",
                            "code": "processing_error",
                            "timestamp": datetime.utcnow().isoformat()
                        }),
                        client_id
                    )
        
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected")
            
        except Exception as conn_error:
            logger.error(f"WebSocket connection error for {client_id}: {str(conn_error)}")
            try:
                await websocket.close(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason="Internal server error"
                )
            except Exception as close_error:
                logger.error(f"Error closing WebSocket: {str(close_error)}")
            
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for {client_id}: {str(e)}", exc_info=True)
        
    finally:
        # Clean up the connection
        if user:
            manager.disconnect(client_id, user.id)
        else:
            manager.disconnect(client_id, 0)  # 0 indicates no user was authenticated
