import pytest
from flask_migrate import upgrade

from app import create_app
from app.extensions import db
from app.models import AdminUser


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "APP_ENV": "testing",
            "SECRET_KEY": "test-secret-only-for-isolated-tests",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.sqlite3'}",
            "MEDIA_ROOT": str(tmp_path / "media"),
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )
    with application.app_context():
        upgrade(directory="migrations")
        user = AdminUser(username="admin")
        user.set_password("test-password-2026")
        db.session.add(user)
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(client):
    response = client.post(
        "/admin/login", data={"username": "admin", "password": "test-password-2026"}
    )
    assert response.status_code == 302
    return client
