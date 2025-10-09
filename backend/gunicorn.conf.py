# Configuración de Gunicorn para ZEUS-IA - Producción
# ===================================================

import multiprocessing
import os

# Configuración básica
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeouts
timeout = 30
keepalive = 2
graceful_timeout = 30

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

# Preload
preload_app = True

# Configuración específica para FastAPI/Uvicorn
worker_tmp_dir = "/dev/shm"

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

# Configuración de memoria
worker_memory_limit = 512 * 1024 * 1024  # 512MB por worker

# Configuración de WebSocket
websocket_ping_interval = 20
websocket_ping_timeout = 10

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

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info(f"⚠️ Worker {worker.pid} abortado")
