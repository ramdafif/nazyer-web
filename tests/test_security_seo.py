import re
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app import create_app
from app.extensions import db
from app.models import Event


def production_config(tmp_path):
    return {
        "APP_ENV": "production",
        "SECRET_KEY": "isolated-production-test-secret-00001",
        "SQLALCHEMY_DATABASE_URI": (
            "mysql+pymysql://isolated_user:test-password@127.0.0.1/dj_nazyer"
        ),
        "TRUSTED_HOSTS": ["dj.example.com"],
        "PUBLIC_BASE_URL": "https://dj.example.com",
        "MEDIA_ROOT": str(tmp_path / "production-media"),
    }


@pytest.mark.parametrize(
    "override",
    [
        {"SECRET_KEY": ""},
        {"SECRET_KEY": "short"},
        {"TRUSTED_HOSTS": None},
        {"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"},
        {"SQLALCHEMY_DATABASE_URI": "mysql+pymysql://root:password@localhost/dj_nazyer"},
        {"SQLALCHEMY_DATABASE_URI": "mysql+pymysql://user:password@localhost/mysql"},
        {"PUBLIC_BASE_URL": "http://dj.example.com"},
        {"PROXY_HOPS": 2},
    ],
)
def test_production_rejects_unsafe_config(tmp_path, override):
    with pytest.raises(RuntimeError):
        create_app({**production_config(tmp_path), **override})


def test_production_demo_guard_without_db_connection(tmp_path):
    app = create_app(production_config(tmp_path))
    assert app.config["SESSION_COOKIE_SECURE"]
    assert app.static_folder is None
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"]["pool_size"] == 2
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "dilarang" in result.output
    with app.app_context():
        db.engine.dispose()


def test_production_factory_does_not_write_checkout(tmp_path, monkeypatch):
    writes = []
    original = Path.mkdir

    def track(directory, *args, **kwargs):
        writes.append(directory.resolve())
        return original(directory, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", track)
    application = create_app(production_config(tmp_path))
    checkout = Path(application.root_path).parent
    assert not any(path.is_relative_to(checkout) for path in writes)
    with application.app_context():
        db.engine.dispose()


def test_mysql_table_ddl(app):
    # Compilation only; this explicitly does not claim MySQL integration execution.
    for table in db.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=mysql.dialect()))
        assert "InnoDB" in sql and "utf8mb4" in sql


def test_mysql_offline_migration(tmp_path):
    production = create_app(production_config(tmp_path))
    result = production.test_cli_runner().invoke(args=["db", "upgrade", "--sql"])
    assert result.exit_code == 0, result.output
    assert (
        "CREATE TABLE" in result.output and "utf8mb4" in result.output and "InnoDB" in result.output
    )
    with production.app_context():
        db.engine.dispose()


def test_sitemap_excludes_drafts_and_admin(app, client):
    with app.app_context():
        db.session.add_all(
            [
                Event(title="Public", slug="public", date=date(2026, 1, 1), status="published"),
                Event(title="Private", slug="private", date=date(2026, 1, 1)),
            ]
        )
        db.session.commit()
    response = client.get("/sitemap.xml")
    assert response.status_code == 200 and response.mimetype == "application/xml"
    assert "/recap/public" in response.text and "/recap/private" not in response.text
    assert "/admin" not in response.text
    assert "Disallow: /admin" in client.get("/robots.txt").text


def test_public_seo_tags_and_errors(client):
    descriptions = []
    for path in ["/", "/tentang", "/recap", "/galeri", "/pricelist", "/kontak"]:
        html = client.get(path).text
        descriptions.append(
            re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html).group(1)
        )
        assert 'rel="canonical"' in html
        assert "og:image" in html and "share.png" in html
    assert len(set(descriptions)) == 6
    for code, path in [(404, "/tidak-ada")]:
        assert client.get(path).status_code == code


def test_admin_routes_protected(client):
    for path in [
        "/admin/",
        "/admin/events",
        "/admin/events/new",
        "/admin/media/upload",
        "/admin/profile",
        "/admin/settings",
        "/admin/inquiries",
        "/admin/pricing/1/preview",
        "/admin/password",
    ]:
        response = client.get(path)
        assert response.status_code == 302 and "/admin/login" in response.location


def test_request_limit_and_traversal(client):
    response = client.post("/admin/login", data={"oversized": "x" * (11 * 1024 * 1024)})
    assert response.status_code == 413
    assert client.get("/uploads/../../wsgi.py").status_code == 404
    assert client.get("/uploads/.processing.lock").status_code == 404


def test_rate_limit_login(app, client):
    # Initialize a genuinely enabled limiter, rather than toggling an uninitialized backend.
    enabled = create_app(
        {
            "APP_ENV": "testing",
            "TESTING": True,
            "SECRET_KEY": app.config["SECRET_KEY"],
            "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
            "MEDIA_ROOT": app.config["MEDIA_ROOT"],
            "RATELIMIT_ENABLED": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    limited_client = enabled.test_client()
    responses = [
        limited_client.post(
            "/admin/login", data={"username": "absent", "password": "invalid"}
        ).status_code
        for _ in range(6)
    ]
    assert responses[-1] == 429
    with enabled.app_context():
        db.engine.dispose()


def test_escaping_and_no_sensitive_settings(admin):
    response = admin.post(
        "/admin/services/new",
        data={
            "name": "<script>alert(1)</script>",
            "slug": "safe-script",
            "sort_order": 0,
            "icon": "music",
            "active": "y",
        },
    )
    assert response.status_code == 302
    text = admin.get("/").text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "<script>alert(1)</script>" not in text
    settings = admin.get("/admin/settings").text
    assert "SECRET_KEY" not in settings and "DATABASE_URL" not in settings
