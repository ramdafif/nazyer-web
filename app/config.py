import os
from datetime import timedelta
from pathlib import Path


def configuration():
    mode = os.getenv("APP_ENV", "development")
    return {
        "APP_ENV": mode,
        "SECRET_KEY": os.getenv("SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": os.getenv("DATABASE_URL", "sqlite:///development.sqlite3"),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SQLALCHEMY_ENGINE_OPTIONS": {"hide_parameters": True},
        "MEDIA_ROOT": os.getenv("MEDIA_ROOT", str(Path.home() / ".local/share/dj-nazyer/uploads")),
        "PUBLIC_BASE_URL": os.getenv("PUBLIC_BASE_URL", "http://localhost:5000"),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": mode == "production",
        "REMEMBER_COOKIE_SECURE": mode == "production",
        "REMEMBER_COOKIE_HTTPONLY": True,
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
        "MAX_CONTENT_LENGTH": 10 * 1024 * 1024,
        "MAX_FORM_MEMORY_SIZE": 256 * 1024,
        "MAX_FORM_PARTS": 100,
        "MAX_IMAGE_PIXELS": 8_000_000,
        "WTF_CSRF_TIME_LIMIT": 7200,
        "RATELIMIT_STORAGE_URI": "memory://",
        "RATELIMIT_HEADERS_ENABLED": True,
        "RATELIMIT_ENABLED": True,
        "TRUSTED_HOSTS": [x.strip() for x in os.getenv("TRUSTED_HOSTS", "").split(",") if x.strip()]
        or None,
        "PROXY_HOPS": int(os.getenv("PROXY_HOPS", "0")),
    }


def validate_configuration(app):
    mode = app.config["APP_ENV"]
    if mode not in {"development", "testing", "production"}:
        raise RuntimeError("APP_ENV must be development, testing or production")
    if not app.config.get("SECRET_KEY"):
        if mode == "production":
            raise RuntimeError("SECRET_KEY is required in production")
        import secrets

        app.config["SECRET_KEY"] = secrets.token_hex(32)
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if mode == "production":
        from sqlalchemy.engine import make_url

        url = make_url(uri)
        if (
            url.drivername != "mysql+pymysql"
            or not url.username
            or url.username.lower() == "root"
            or not url.password
            or not url.database
            or url.database in {"mysql", "sys", "information_schema", "performance_schema"}
        ):
            raise RuntimeError("Production requires a dedicated MySQL user via mysql+pymysql")
        if len(app.config["SECRET_KEY"]) < 32 or not app.config.get("TRUSTED_HOSTS"):
            raise RuntimeError("Production requires a strong SECRET_KEY and TRUSTED_HOSTS")
        if not app.config["PUBLIC_BASE_URL"].startswith("https://"):
            raise RuntimeError("PUBLIC_BASE_URL must use HTTPS in production")
        app.config["DEBUG"] = False
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["REMEMBER_COOKIE_SECURE"] = True
    if uri.startswith("mysql"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_size": 2,
            "max_overflow": 2,
            "pool_recycle": 1800,
            "pool_pre_ping": True,
            "pool_timeout": 15,
            "hide_parameters": True,
            "connect_args": {"charset": "utf8mb4"},
        }
    if app.config["PROXY_HOPS"] not in (0, 1):
        raise RuntimeError("PROXY_HOPS must be 0 or 1 for this deployment")
    root = Path(app.config["MEDIA_ROOT"]).expanduser().resolve()
    if mode == "production" and (
        root.is_relative_to(Path(app.root_path).parent)
        or not Path(app.config["MEDIA_ROOT"]).is_absolute()
    ):
        raise RuntimeError(
            "MEDIA_ROOT must be an absolute persistent directory outside the checkout"
        )
    root.mkdir(parents=True, exist_ok=True)
    app.config["MEDIA_ROOT"] = str(root)
