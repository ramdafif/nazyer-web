bind = "unix:/run/dj-nazyer/gunicorn.sock"
workers = 2
worker_class = "sync"
threads = 1
preload_app = True
timeout = 60
graceful_timeout = 30
max_requests = 800
max_requests_jitter = 80
keepalive = 2
umask = 0o007
accesslog = None
errorlog = "-"
loglevel = "warning"
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190
# Nginx supplies X-Forwarded-For; ProxyFix trusts exactly the configured hop.
forwarded_allow_ips = "*"


def post_fork(server, worker):
    # Never inherit open DB connections from a preloaded master.
    from app.extensions import db
    from wsgi import app

    with app.app_context():
        db.engine.dispose(close=False)
