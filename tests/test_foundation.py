from app.extensions import db
from app.models import AdminUser


def test_home_and_errors(client):
    assert client.get("/").status_code == 200
    assert client.get("/missing").status_code == 404
    assert client.get("/admin/").status_code == 302


def test_password_hash(app):
    with app.app_context():
        user = db.session.scalar(db.select(AdminUser))
        assert user.password_hash != "test-password-2026"
        assert user.check_password("test-password-2026")
        assert not user.check_password("incorrect")


def test_authentication(client, admin):
    assert admin.get("/admin/").status_code == 200
    assert admin.get("/admin/logout").status_code == 405
    assert admin.post("/admin/logout").status_code == 302
    assert admin.get("/admin/").status_code == 302
    assert (
        "tidak sesuai"
        in client.post("/admin/login", data={"username": "admin", "password": "wrong"}).text
    )


def test_csrf(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    assert (
        client.post(
            "/admin/login", data={"username": "admin", "password": "test-password-2026"}
        ).status_code
        == 400
    )


def test_change_password_revokes_sessions(app, admin):
    other = app.test_client()
    other.post("/admin/login", data={"username": "admin", "password": "test-password-2026"})
    response = admin.post(
        "/admin/password",
        data={
            "current_password": "test-password-2026",
            "password": "new-test-password-2026",
            "confirm": "new-test-password-2026",
        },
    )
    assert response.status_code == 302
    assert other.get("/admin/").status_code == 302


def test_create_admin_cli(app):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "--username", "editor"],
        input="a-valid-long-password\na-valid-long-password\n",
    )
    assert result.exit_code == 0
    assert "a-valid-long-password" not in result.output
    assert runner.invoke(args=["create-admin", "--username", "editor"]).exit_code != 0


def test_security_headers(client):
    response = client.get("/admin/login")
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert "unsafe-inline" not in response.headers["Content-Security-Policy"]
