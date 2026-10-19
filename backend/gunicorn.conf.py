import os

# One worker on purpose: live-sync connections (SSE) and email rate limits are held in memory.
bind = f"0.0.0.0:{os.environ.get('PORT', '5050')}"
worker_class = "gthread"
workers = 1
threads = 32
timeout = 120
keepalive = 30
accesslog = "-"
errorlog = "-"
