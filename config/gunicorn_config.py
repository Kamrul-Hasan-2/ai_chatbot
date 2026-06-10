"""
Gunicorn configuration for production deployment
"""
import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes
# This chatbot keeps per-user mode/context in in-memory dicts.
# With multiple workers, conversation state can split across processes and behave inconsistently.
# Keep default at 1 unless state is moved to shared storage (Redis/DB).
workers = int(os.getenv('GUNICORN_WORKERS', '1')) # never change this to more than 1 then there will be bug
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'sync')
worker_connections = int(os.getenv('GUNICORN_WORKER_CONNECTIONS', '200'))
timeout = 120
keepalive = 5

# Logging
accesslog = 'logs/access.log'
errorlog = 'logs/error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'ai_chatbot'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
