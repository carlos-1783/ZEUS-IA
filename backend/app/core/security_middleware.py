"""Middleware de seguridad para ZEUS-IA."""
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Endpoints cuyo body identifica un "objetivo" (cuenta/email) que se usa
# como clave ADICIONAL de rate limit, independiente de la IP detectada.
# Ver docstring de get_real_client_ip() y AUDIT_SEGURIDAD_ESTANDAR.md
# seccion 4 (vuelta 2) para el porque: ninguna cabecera de IP puede darse
# por 100% no falsificable sin trafico real contra el edge de Railway
# desplegado, asi que un atacante que consiga falsificar la IP reportada en
# cada peticion NO debe poder resetear el contador si sigue atacando el
# MISMO objetivo (la misma cuenta, o el mismo email de checkout).
#   path -> (formato_body, campos_candidatos_en_orden_de_preferencia)
_ACCOUNT_KEY_SOURCES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "/api/v1/auth/login": ("form", ("username", "email")),
    "/api/v1/auth/register": ("json", ("email", "username")),
    "/api/v1/integrations/stripe/checkout/payment-intent": (
        "json",
        ("customer_email", "email"),
    ),
}

# Buckets (ver _bucket_and_limit) a los que se les aplica la clave de
# cuenta/objetivo ademas de la de IP.
_ACCOUNT_KEYED_BUCKETS = frozenset(
    {"auth_login", "auth_register", "public_checkout_payment_intent"}
)


def get_real_client_ip(request: Request) -> str:
    """Obtener la IP real del cliente para bucketing de rate limit / bloqueo
    y para auditoria (login, fichajes), de forma que TODO el código que
    necesite "la IP del cliente" use la misma lógica -- una sola fuente de
    verdad, en vez de que cada módulo lea `request.client.host` a su manera.

    ==========================================================================
    VUELTA 1 (hallazgo original, corregido primero en el commit dbd0601 y
    DEVUELTO por revisor-independiente): `get_client_ip()` usaba el PRIMER
    valor de `X-Forwarded-For` (cabecera que escribe el propio cliente sin
    ninguna validación) -- bypass total de rate limit verificado en vivo
    (35/35 login, 12/12 register sin ningún 429).

    VUELTA 2 (este fix, 2026-08-28) -- el intento de la vuelta 1 (tomar el
    ÚLTIMO valor de `X-Forwarded-For` en vez del primero) fue DEVUELTO por
    revisor-independiente con evidencia concreta de que seguía roto:

      1. El ataque MÁS SIMPLE (un único valor en `X-Forwarded-For`, sin
         segundo valor) seguía dando bypass total (35/35, 12/12, 12/12,
         cero 429). Cuando solo hay un valor en la cabecera, tomar "el
         último" es exactamente lo mismo que tomar "el primero" -- y ese
         único valor lo controla el atacante. El fix de la vuelta 1 solo
         cerraba la variante de ataque de DOS valores que su propia prueba
         construyó, no la de un valor que cualquier atacante probaría
         primero por ser más simple.
      2. La documentación pública oficial de Railway
         (docs.railway.com/networking/public-networking/specs-and-limits,
         sección "Request Headers", verificada en vivo el 2026-08-28 con
         `curl` contra esa URL) NO menciona `X-Forwarded-For` en ningún
         punto. En cambio documenta explícitamente:
         "`X-Real-IP` for identifying client's remote IP." -- justo la
         cabecera que el fix de la vuelta 1 dejó de usar, con el argumento
         (incorrecto) de que "no hay evidencia de que Railway la fije".

    FIX DE ESTA VUELTA:

      1. `X-Forwarded-For` deja de usarse POR COMPLETO para esta decisión de
         seguridad. No hay ninguna garantía documentada de cómo la trata
         Railway (ni que la añada, ni que la sustituya, ni que la respete de
         ninguna forma concreta) -- confiar en ella es exactamente la misma
         asunción no verificada que ya falló una vez.
      2. Se usa `X-Real-IP` si está presente -- es la ÚNICA cabecera que
         Railway documenta oficialmente para este propósito exacto. El
         propósito documentado de esa cabecera ("identifying client's
         remote IP") solo tiene sentido operativo si el edge la fija/
         sobrescribe él mismo: si cualquier cliente pudiera fijarla
         libremente y Railway simplemente la reenviara, la cabecera no
         podría cumplir la función que la propia documentación le
         atribuye. Es una asunción bastante más razonable que la que hacía
         el fix anterior sobre `X-Forwarded-For` (que ni siquiera aparece
         documentada), pero -- se documenta con total honestidad -- SIGUE
         SIN SER VERIFICABLE AL 100 % sin tráfico real contra el edge de
         Railway desplegado. No se ha podido confirmar en este entorno si
         Railway SOBRESCRIBE siempre `X-Real-IP` o solo la fija cuando el
         cliente no la ha mandado ya (en cuyo caso seguiría siendo
         falsificable). Esta es la limitación residual más honesta que se
         puede dar sin acceso al edge real.
      3. Si `X-Real-IP` no está presente, se usa `request.client.host` (el
         peer TCP real de la conexión) -- NUNCA se rellena a partir de una
         cabecera no confiable. Esto puede hacer que, en producción, si por
         lo que sea `X-Real-IP` no llegara, todos los usuarios reales
         compartan el mismo valor de IP (el del edge de Railway) -- un
         resultado MENOS preciso pero SEGURO (nunca falsificable por el
         cliente), preferible a repetir el fallo de fiarse de una cabecera
         arbitraria. No depende de `gunicorn.conf.py::forwarded_allow_ips`
         ni de `ProxyHeadersMiddleware`: esta función lee la cabecera cruda
         directamente de `request.headers`, nunca de `request.client.host`
         reescrito por ese middleware ASGI.

    MITIGACIÓN ADICIONAL QUE NO DEPENDE DE ACERTAR LA CABECERA CORRECTA:
    dado que ninguna cabecera de IP puede confirmarse como 100 % no
    falsificable sin acceso al edge real de Railway, `check_rate_limit()`
    ata ADEMÁS la clave de límite de `auth_login`, `auth_register` y
    `public_checkout_payment_intent` al identificador de cuenta/objetivo
    del propio intento (username/email/customer_email extraído del body),
    no solo a la IP. Esto cierra el bypass de fuerza bruta dirigido a UN
    objetivo concreto incluso si la IP reportada fuera perfectamente
    falsificable en cada petición, sin depender de ninguna asunción sobre
    cómo gestiona Railway sus cabeceras. Ver `AUDIT_SEGURIDAD_ESTANDAR.md`
    sección 4 para el detalle completo, la evidencia de verificación y las
    limitaciones residuales reconocidas explícitamente (en particular: un
    atacante que varíe TANTO la IP/cabecera reportada COMO el objetivo/
    email en cada petición sigue sin poder ser distinguido de tráfico
    legítimo por identidad -- solo se cierra el caso, mucho más probable y
    barato de ejecutar, de repetir ataques contra un mismo objetivo).
    """
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        candidate = real_ip.split(",")[0].strip()
        if candidate:
            return candidate

    return request.client.host if request.client else "unknown"


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware para aplicar medidas de seguridad"""

    def __init__(self, app):
        super().__init__(app)
        # key => timestamps dentro de la ventana
        # key combina IP + bucket de endpoint + clase de identidad.
        self.rate_limit_store: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}

    async def dispatch(self, request: Request, call_next):
        """Aplicar middleware de seguridad"""

        # 0. Extraer identificador de cuenta/objetivo (si aplica) ANTES de
        # calcular la IP -- necesita leer y reconstruir el body para que
        # siga siendo legible aguas abajo (mismo patrón que
        # app/middleware/thalos_login_audit_middleware.py).
        request, account_key = await self._maybe_extract_account_key(request)

        # 1. Verificar IP bloqueada
        client_ip = self.get_client_ip(request)
        if self.is_ip_blocked(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "IP bloqueada temporalmente"}
            )

        # 2. Rate limiting
        allowed, retry_after, limit = self.check_rate_limit(
            request, client_ip, request.url.path, account_key=account_key
        )
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Demasiadas solicitudes",
                    "retry_after_seconds": retry_after,
                    "limit_per_minute": limit,
                },
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )

        # 3. Headers de seguridad
        response = await call_next(request)

        # Agregar headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=(self)"

        # CSP para endpoints específicos
        if request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https: blob:; "
                "connect-src 'self' wss: https: blob: data: https://models.readyplayer.me;"
            )

        return response

    async def _maybe_extract_account_key(self, request: Request) -> Tuple[Request, str]:
        """Si el path es uno de `_ACCOUNT_KEY_SOURCES`, lee el body para
        extraer el identificador de cuenta/objetivo (username/email) y
        reconstruye el `Request` para que el body siga siendo legible aguas
        abajo (el endpoint real, y cualquier otro middleware que también lo
        lea, como `ThalosLoginAuditMiddleware`).

        Devuelve `(request_posiblemente_reconstruido, account_key)`.
        `account_key` es `""` si el path no aplica o el body no se pudo
        parsear -- en ese caso el rate limit sigue funcionando solo por IP,
        exactamente igual que antes de este fix (no hay regresión).
        """
        if request.method.upper() != "POST":
            return request, ""

        path = request.url.path.rstrip("/") or request.url.path
        source = _ACCOUNT_KEY_SOURCES.get(path)
        if not source:
            return request, ""

        kind, fields = source
        body_bytes = await request.body()

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        rebuilt = Request(request.scope, receive)

        account = ""
        try:
            raw = body_bytes.decode("utf-8")
            if kind == "json":
                data = json.loads(raw or "{}")
                for field in fields:
                    value = data.get(field)
                    if value:
                        account = str(value).strip().lower()
                        break
            else:
                parsed = parse_qs(raw)
                for field in fields:
                    values = parsed.get(field)
                    if values and values[0]:
                        account = str(values[0]).strip().lower()
                        break
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            account = ""

        return rebuilt, account[:255]

    def get_client_ip(self, request: Request) -> str:
        """Ver `get_real_client_ip()` (función módulo, misma lógica
        compartida por `ThalosLoginAuditMiddleware` y `checkin.py`)."""
        return get_real_client_ip(request)

    def is_ip_blocked(self, ip: str) -> bool:
        """Verificar si IP está bloqueada"""
        if ip in self.blocked_ips:
            # Verificar si el bloqueo ha expirado (1 hora)
            if time.time() - self.blocked_ips[ip] > 3600:
                del self.blocked_ips[ip]
                return False
            return True
        return False

    def block_ip(self, ip: str):
        """Bloquear IP temporalmente"""
        self.blocked_ips[ip] = time.time()
        logger.warning(f"IP bloqueada: {ip}")

    def _identity_key(self, request: Request, ip: str) -> str:
        """Separar tráfico autenticado del anónimo para evitar castigar toda una IP."""
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer ") and len(auth) > 20:
            # No persistimos el token completo; solo un prefijo para bucketing.
            return f"{ip}:auth:{auth[7:23]}"
        return f"{ip}:anon"

    def _bucket_and_limit(self, request: Request, path: str) -> Tuple[str, int]:
        """Devuelve bucket lógico y límite por minuto."""
        method = (request.method or "GET").upper()
        is_auth = request.headers.get("Authorization", "").lower().startswith("bearer ")

        # No limitar preflight/CORS
        if method == "OPTIONS":
            return ("preflight", 10_000)

        # No limitar health/static/service-worker para evitar falsos positivos
        if (
            path in ("/health", "/api/v1/health", "/service-worker.js")
            or path.startswith("/assets/")
            or path.startswith("/static/")
        ):
            return ("public_static", 10_000)

        # Endpoints con polling frecuente en TPV/paneles
        if path.startswith("/api/v1/tpv/comanda-share/"):
            return ("tpv_comanda_poll", 1200 if is_auth else 300)
        # Escrituras de estado de mesas: en operación real puede haber ráfagas
        # por sincronización multi-dispositivo (barra/sala/comandero).
        if path.startswith("/api/v1/tpv/tables/") and method in ("PATCH", "PUT", "POST"):
            return ("tpv_tables_write", 2400 if is_auth else 300)
        if path.startswith("/api/v1/documents/pending") or path.startswith("/api/v1/document-approval/pending"):
            return ("documents_pending_poll", 600 if is_auth else 180)
        if path.startswith("/api/v1/tpv/tables") and method == "GET":
            return ("tpv_tables_poll", 600 if is_auth else 180)

        # Auth sensible: mantener estricto
        if path.startswith("/api/v1/auth/login"):
            return ("auth_login", 30)
        if path.startswith("/api/v1/auth/register"):
            return ("auth_register", 10)
        if path.startswith("/api/v1/auth/refresh"):
            return ("auth_refresh", 120)

        # Checkout público (sin sesión): crea PaymentIntents reales en
        # Stripe -- superficie sensible aunque no exija auth. Límite
        # estricto, igual de severo que el registro de cuentas.
        if path == "/api/v1/integrations/stripe/checkout/payment-intent" and method == "POST":
            return ("public_checkout_payment_intent", 10)

        # Escrituras API: límite moderado
        if path.startswith("/api/") and method in ("POST", "PUT", "PATCH", "DELETE"):
            return ("api_write", 360 if is_auth else 120)

        # API general de lectura
        if path.startswith("/api/"):
            return ("api_read", 900 if is_auth else 240)

        # Frontend general
        return ("frontend", 300)

    def check_rate_limit(
        self, request: Request, ip: str, path: str, account_key: str = ""
    ) -> Tuple[bool, float, int]:
        """Verificar rate limiting y devolver (allowed, retry_after_seconds, limit).

        Comprueba DOS claves independientes cuando el bucket lo justifica
        (ver `_ACCOUNT_KEYED_BUCKETS`): la de IP+identidad de siempre, y una
        clave adicional atada al objetivo del intento (cuenta/email), que no
        depende en absoluto de qué IP se haya conseguido extraer. Si
        CUALQUIERA de las dos supera el límite, la petición se bloquea --
        así, aunque la IP reportada fuera perfectamente falsificable en
        cada petición, repetir el ataque contra el MISMO objetivo lo sigue
        deteniendo.
        """
        current_time = time.time()
        window = 60  # 1 minuto
        bucket, limit = self._bucket_and_limit(request, path)
        identity = self._identity_key(request, ip)

        keys = [f"{identity}:{bucket}"]
        if account_key and bucket in _ACCOUNT_KEYED_BUCKETS:
            keys.append(f"acct:{bucket}:{account_key}")

        histories: Dict[str, List[float]] = {}
        blocked = False
        retry_after = 0.0
        for key in keys:
            history = [
                req_time
                for req_time in self.rate_limit_store.get(key, [])
                if current_time - req_time < window
            ]
            histories[key] = history
            if len(history) >= limit:
                oldest = history[0] if history else current_time
                key_retry = max(1.0, window - (current_time - oldest))
                retry_after = max(retry_after, key_retry)
                blocked = True

        # Persistir siempre la ventana recortada (se bloquee o no la
        # petición), para no acumular entradas caducadas indefinidamente.
        for key, history in histories.items():
            self.rate_limit_store[key] = history

        if blocked:
            logger.warning(
                "Rate limited request ip=%s bucket=%s method=%s path=%s limit=%s account_keyed=%s",
                ip,
                bucket,
                request.method,
                path,
                limit,
                bool(account_key and bucket in _ACCOUNT_KEYED_BUCKETS),
            )
            # No bloquear IP de forma persistente; solo responder 429 temporal
            return False, retry_after, limit

        # Agregar request actual a todas las claves comprobadas
        for key in keys:
            self.rate_limit_store[key].append(current_time)
        return True, 0.0, limit

# No crear instancia global: FastAPI la construye vía app.add_middleware(...)
