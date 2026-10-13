"""Descarga segura de URLs aportadas por el usuario (anti-SSRF).

Cualquier código del núcleo que tenga que descargar una URL que viene del usuario
(imagen a analizar, página a auditar...) debe pasar por ``safe_fetch``. Reglas:

* Esquema: solo ``https`` por defecto. ``http`` solo si quien llama lo permite de
  forma explícita (``allow_http=True``) y justificado (p.ej. auditar SEO de una web
  que aún no tiene TLS: es justo lo que la auditoría debe detectar).
* Sin credenciales en la URL (``user:pass@host``) y solo puertos 443/80.
* Se resuelve el DNS y TODAS las IPs resultantes deben ser públicas: se bloquean
  privadas, loopback, link-local, reservadas, multicast, no especificadas, CGNAT
  (100.64/10) y IPv4 mapeadas en IPv6 que apunten a cualquiera de ellas.
* La conexión se abre contra la IP ya validada (no se vuelve a resolver el nombre:
  evita DNS rebinding), conservando Host y SNI/verificación TLS del nombre original.
* Redirecciones: no se siguen automáticamente; cada salto (máx. ``max_redirects``)
  se vuelve a validar desde cero (esquema, puerto, DNS, IP).
* Timeout, tamaño máximo (lectura en streaming y corte) y content-type esperado.

Los errores se elevan como ``UnsafeUrlError`` (URL no permitida) o
``FetchFailedError`` (no se pudo descargar algo válido); ambos heredan de
``SafeFetchError`` para que el llamante los traduzca a un 422 honesto.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlsplit

import urllib3

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 3
_ALLOWED_PORTS = {"https": 443, "http": 80}
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_USER_AGENT = "ZEUS-IA-PERSEO/1.0 (+https://zeus-ia)"

# 100.64.0.0/10 (CGNAT) no es "private" para ipaddress en todas las versiones.
_EXTRA_BLOCKED_NETS = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
)


class SafeFetchError(Exception):
    """Base: la URL no se pudo descargar de forma segura."""


class UnsafeUrlError(SafeFetchError):
    """La URL (o una redirección) apunta a algo no permitido."""


class FetchFailedError(SafeFetchError):
    """La URL es válida pero la descarga falló (timeout, HTTP>=400, tipo, tamaño...)."""


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    content_type: str
    body: bytes
    redirects: List[str] = field(default_factory=list)

    def text(self) -> str:
        charset = "utf-8"
        ct = self.content_type or ""
        if "charset=" in ct.lower():
            charset = ct.lower().split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


# Firma: (scheme, ip, port, hostname, path_with_query, timeout) -> (status, headers, chunks)
Opener = Callable[[str, str, int, str, str, float], Tuple[int, Dict[str, str], Iterable[bytes]]]


def _ip_is_public(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped or ip.sixtofour
        if mapped is not None:
            return _ip_is_public(mapped)
        if ip.teredo:
            return False
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or not ip.is_global
    ):
        return False
    if isinstance(ip, ipaddress.IPv4Address) and any(ip in net for net in _EXTRA_BLOCKED_NETS):
        return False
    return True


def _resolve_public_ips(hostname: str, port: int) -> List[str]:
    try:
        literal = ipaddress.ip_address(hostname.strip("[]"))
        candidates = [str(literal)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError) as exc:
            raise FetchFailedError(f"No se pudo resolver el dominio '{hostname}'.") from exc
        candidates = list(dict.fromkeys(info[4][0] for info in infos))
    if not candidates:
        raise FetchFailedError(f"El dominio '{hostname}' no resuelve a ninguna IP.")
    for raw in candidates:
        ip = ipaddress.ip_address(raw.split("%", 1)[0])
        if not _ip_is_public(ip):
            raise UnsafeUrlError(
                f"La URL apunta a una dirección no pública ({ip}); no se permite descargarla."
            )
    return candidates


def validate_url(url: str, *, allow_http: bool = False) -> Tuple[str, str, int, str]:
    """Valida esquema/host/puerto. Devuelve (scheme, hostname, port, path_with_query)."""
    if not isinstance(url, str) or not url.strip():
        raise UnsafeUrlError("URL vacía.")
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "").lower()
    allowed = {"https", "http"} if allow_http else {"https"}
    if scheme not in allowed:
        raise UnsafeUrlError(
            f"Esquema '{scheme or '(ninguno)'}' no permitido; solo {', '.join(sorted(allowed))}."
        )
    if parts.username or parts.password:
        raise UnsafeUrlError("No se permiten credenciales dentro de la URL.")
    hostname = (parts.hostname or "").strip().rstrip(".")
    if not hostname:
        raise UnsafeUrlError("La URL no tiene dominio.")
    try:
        port = parts.port or _ALLOWED_PORTS[scheme]
    except ValueError as exc:
        raise UnsafeUrlError("Puerto no válido en la URL.") from exc
    if port != _ALLOWED_PORTS[scheme]:
        raise UnsafeUrlError(f"Puerto {port} no permitido (solo {_ALLOWED_PORTS[scheme]} para {scheme}).")
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return scheme, hostname, port, path


def _urllib3_opener(
    scheme: str, ip: str, port: int, hostname: str, path: str, timeout: float
) -> Tuple[int, Dict[str, str], Iterable[bytes]]:
    """Conecta a la IP ya validada manteniendo Host + SNI + verificación TLS del dominio."""
    tmo = urllib3.Timeout(connect=timeout, read=timeout)
    if scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            ip,
            port=port,
            timeout=tmo,
            retries=False,
            server_hostname=hostname,
            assert_hostname=hostname,
            cert_reqs="CERT_REQUIRED",
        )
    else:
        pool = urllib3.HTTPConnectionPool(ip, port=port, timeout=tmo, retries=False)
    host_header = hostname if port == _ALLOWED_PORTS[scheme] else f"{hostname}:{port}"
    resp = pool.urlopen(
        "GET",
        path,
        headers={"Host": host_header, "User-Agent": _USER_AGENT, "Accept": "*/*"},
        redirect=False,
        preload_content=False,
        retries=False,
    )
    headers = {k.lower(): v for k, v in resp.headers.items()}
    return resp.status, headers, resp.stream(64 * 1024)


_opener: Opener = _urllib3_opener


def safe_fetch(
    url: str,
    *,
    allowed_content_types: Sequence[str],
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: float = DEFAULT_TIMEOUT_S,
    allow_http: bool = False,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> FetchResult:
    """Descarga ``url`` aplicando todas las defensas anti-SSRF del módulo."""
    allowed_ct = tuple(ct.lower() for ct in allowed_content_types)
    current = url.strip() if isinstance(url, str) else url
    hops: List[str] = []
    for _ in range(max_redirects + 1):
        scheme, hostname, port, path = validate_url(current, allow_http=allow_http)
        ips = _resolve_public_ips(hostname, port)
        try:
            status, headers, chunks = _opener(scheme, ips[0], port, hostname, path, timeout)
        except SafeFetchError:
            raise
        except Exception as exc:  # urllib3/SSL/socket: error real de red, se informa
            logger.info("safe_fetch: fallo de red host=%s: %s", hostname, exc)
            raise FetchFailedError(f"No se pudo conectar con '{hostname}': {type(exc).__name__}.") from exc

        if status in _REDIRECT_CODES:
            location = headers.get("location")
            if not location:
                raise FetchFailedError(f"Redirección {status} sin cabecera Location.")
            nxt = urljoin(current, location)
            hops.append(nxt)
            logger.info("safe_fetch: redireccion %s -> %s (se revalida)", current, nxt)
            current = nxt
            continue
        if status >= 400:
            raise FetchFailedError(f"La URL respondió HTTP {status}.")

        content_type = (headers.get("content-type") or "").lower()
        base_ct = content_type.split(";", 1)[0].strip()
        if allowed_ct and not any(base_ct == ct or (ct.endswith("/") and base_ct.startswith(ct)) for ct in allowed_ct):
            raise FetchFailedError(
                f"Tipo de contenido '{base_ct or 'desconocido'}' no esperado (se esperaba {', '.join(allowed_ct)})."
            )
        declared = headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise FetchFailedError(f"El recurso supera el tamaño máximo ({max_bytes} bytes).")
        buf = bytearray()
        for chunk in chunks:
            buf.extend(chunk)
            if len(buf) > max_bytes:
                raise FetchFailedError(f"El recurso supera el tamaño máximo ({max_bytes} bytes).")
        return FetchResult(
            url=url,
            final_url=current,
            status=status,
            content_type=content_type,
            body=bytes(buf),
            redirects=hops,
        )
    raise FetchFailedError(f"Demasiadas redirecciones (máx. {max_redirects}).")
