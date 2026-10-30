from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import configuration, validate_configuration
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.services.assets import register_assets


@event.listens_for(Engine, "connect")
def enable_sqlite_fk(connection, _):
    if connection.__class__.__module__.startswith("sqlite3"):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(configuration())
    if test_config:
        app.config.update(test_config)
    validate_configuration(app)
    if app.config["APP_ENV"] == "production":
        app.static_folder = None
    register_assets(app)
    # Production runs from a read-only checkout; only local SQLite needs instance/.
    if app.config["APP_ENV"] != "production":
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if app.config["PROXY_HOPS"]:
        hops = app.config["PROXY_HOPS"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=0, x_port=0)
    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.refresh_view = "auth.login"
    login_manager.login_message = "Silakan masuk untuk mengakses CMS."
    login_manager.login_message_category = "info"
    from app.models import AdminUser

    @login_manager.user_loader
    def load_user(identity):
        try:
            uid, version = map(int, identity.split(":"))
            user = db.session.get(AdminUser, uid)
            return user if user and user.active and user.session_version == version else None
        except (ValueError, AttributeError):
            return None

    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.public import bp as public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    from app.cli import register_cli

    register_cli(app)

    @app.template_filter("jakarta")
    def jakarta(value, fmt="%d/%m/%Y %H:%M"):
        if value is None:
            return "—"
        return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Jakarta")).strftime(fmt)

    @app.template_filter("idr")
    def idr(value):
        return (
            "Hubungi untuk Penawaran"
            if value is None
            else "Rp " + f"{int(value):,}".replace(",", ".")
        )

    @app.context_processor
    def common_context():
        return {"current_year": datetime.now(ZoneInfo("Asia/Jakarta")).year}

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src "
            "'self'; font-src 'self'; connect-src 'self'; media-src 'self'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'"
        )
        if app.config["APP_ENV"] == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith("/admin") or request.path.startswith("/kontak/terkirim"):
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if request.path.startswith("/admin") or request.path.startswith("/kontak"):
            response.headers["Cache-Control"] = "no-store, private"
        return response

    def error_page(error):
        db.session.rollback()
        return render_template(
            "errors/error.html", code=error.code, title=f"Kesalahan {error.code}"
        ), error.code

    for code in (400, 403, 404, 405, 413, 429, 500):
        app.register_error_handler(code, error_page)

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template(
            "errors/error.html",
            code=400,
            title="Sesi form berakhir",
            message="Muat ulang halaman, lalu kirim form kembali.",
        ), 400

    return app
