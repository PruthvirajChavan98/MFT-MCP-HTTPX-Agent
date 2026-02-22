import multiprocessing
import os
import shutil

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Hard ceiling for LLM streaming requests; prevents silent upstream
# network partitions from permanently consuming workers.
timeout = 180
graceful_timeout = 120

keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "mft-agent"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None


def _prometheus_multiproc_dir() -> str:
    return os.getenv("PROMETHEUS_MULTIPROC_DIR", "").strip()


def on_starting(server):
    """Reset multiprocess metric shards before workers boot."""
    multiproc_dir = _prometheus_multiproc_dir()
    if not multiproc_dir:
        return

    if os.path.isdir(multiproc_dir):
        shutil.rmtree(multiproc_dir, ignore_errors=True)
    os.makedirs(multiproc_dir, mode=0o777, exist_ok=True)


def child_exit(server, worker):
    """Mark worker metrics as dead to avoid stale shard reads."""
    if not _prometheus_multiproc_dir():
        return

    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
    except Exception:
        server.log.warning(
            "Failed to mark Prometheus multiprocess worker dead: pid=%s",
            worker.pid,
            exc_info=True,
        )
