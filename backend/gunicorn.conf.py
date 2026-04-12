# Configuración de Gunicorn para ZEUS-IA - Producción
# ===================================================

import os

_root = (os.getenv("ZEUS_APP_ROOT") or "").strip()
if _root and os.path.isdir(_root):
    os.chdir(_root)

# Configuración básica
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
# Railway hobby / 512MB: 1 worker evita SIGKILL OOM (cada worker = copia del proceso + agentes).
# Más RAM o tráfico: WEB_CONCURRENCY=2 en variables de entorno.
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Worker sync: Gunicorn puede esperar minutos. El proxy público de Railway corta antes (~60s);
# OPENAI_TIMEOUT_SEC + ZEUS_AGENT_PROCESS_TIMEOUT deben quedar por debajo (ver Dockerfile).
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
keepalive = 5
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "300"))

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Proceso
daemon = False
# pidfile = "/var/run/zeus-ia.pid"  # No necesario en Railway
# user = "www-data"  # Railway maneja esto
# group = "www-data"
tmp_upload_dir = None

# Seguridad
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Preload (desactivado para reducir presión de memoria en workers con estado mutable)
preload_app = False

# Railway/contenedores mínimos: /dev/shm a veces es pequeño o problemático; /tmp es más fiable.
_worker_tmp = os.getenv("GUNICORN_WORKER_TMPDIR", "/tmp").strip() or "/tmp"
worker_tmp_dir = _worker_tmp

# Variables de entorno
raw_env = [
    "ENVIRONMENT=production",
    "DEBUG=false",
    "LOG_LEVEL=info",
]

# Configuración de SSL (si se usa directamente)
# keyfile = "/etc/letsencrypt/live/zeus-ia.com/privkey.pem"
# certfile = "/etc/letsencrypt/live/zeus-ia.com/fullchain.pem"

# Configuración de proxy
forwarded_allow_ips = "*"
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# Configuración de reload (solo para desarrollo)
reload = False
reload_extra_files = []

# Configuración de stats
statsd_host = None
statsd_prefix = "zeus-ia"

# Configuración de prometheus (si se usa)
def when_ready(server):
    """Called just after the server is started."""
    server.log.info("🚀 ZEUS-IA Backend iniciado en modo producción")
    server.log.info(f"👥 Workers: {server.cfg.workers}")
    server.log.info(f"🔗 Bind: {server.cfg.bind}")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info(f"👋 Worker {worker.pid} terminado")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info(f"🔄 Iniciando worker {worker.age}")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"✅ Worker {worker.pid} iniciado")
    # Precalentar agentes en segundo plano: el primer POST /chat no debe sumar init+LLM por encima
    # del timeout del edge (p. ej. Railway ~60s) → evita 502 "Application failed to respond".
    def _prewarm_agents():
        try:
            from app.api.v1.endpoints.chat import ensure_agent_stack

            ensure_agent_stack()
            server.log.info(f"🔥 Worker {worker.pid}: pila de agentes precalentada")
        except Exception as e:
            server.log.warning("Prewarm agentes omitido en worker %s: %s", worker.pid, e)

    import threading

    threading.Thread(target=_prewarm_agents, name="zeus_agent_prewarm", daemon=True).start()

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info(f"⚠️ Worker {worker.pid} abortado")
