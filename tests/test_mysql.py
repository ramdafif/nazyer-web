"""Opt-in MySQL 8 integration tests. Never point MYSQL_TEST_URL at an app database."""

import io
import multiprocessing
import os
import re
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import AdminUser, Event, MediaAsset

pytestmark = pytest.mark.mysql


def checked_test_url(raw):
    """Refuse production-looking schemas and privileged accounts before connecting."""
    url = make_url(raw)
    if (
        url.drivername != "mysql+pymysql"
        or not url.username
        or url.username.lower() == "root"
        or not url.database
        or not re.search(r"(^|_)test($|_)", url.database, re.IGNORECASE)
    ):
        raise ValueError(
            "Use mysql+pymysql, a dedicated non-root user and a schema containing _test."
        )
    return url.render_as_string(hide_password=False)


def migrate(application, *args):
    result = application.test_cli_runner().invoke(args=["db", *args])
    assert result.exit_code == 0, result.output


@pytest.fixture
def mysql_schema(tmp_path):
    raw = os.getenv("MYSQL_TEST_URL")
    if not raw:
        pytest.skip("MYSQL_TEST_URL is not configured; no real MySQL integration was run")
    uri = checked_test_url(raw)
    application = create_app(
        {
            "TESTING": True,
            "APP_ENV": "testing",
            "SECRET_KEY": "isolated-mysql-test-secret-only",
            "SQLALCHEMY_DATABASE_URI": uri,
            "MEDIA_ROOT": str(tmp_path / "media"),
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )
    with application.app_context():
        try:
            # Refuse any populated schema BEFORE running destructive migration tests.
            inspector = inspect(db.engine)
            assert not (inspector.get_table_names() or inspector.get_view_names()), (
                "MySQL test schema must be empty"
            )
            with db.engine.connect() as connection:
                version = connection.scalar(text("SELECT VERSION()"))
                assert version.startswith("8.") and "mariadb" not in version.lower()
                charset = connection.scalar(
                    text(
                        "SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA "
                        "WHERE SCHEMA_NAME = DATABASE()"
                    )
                )
                assert charset == "utf8mb4", "Create the dedicated test schema with utf8mb4"
            try:
                yield application
            finally:
                db.session.remove()
                if "alembic_version" in inspect(db.engine).get_table_names():
                    migrate(application, "downgrade", "base")
                    # Alembic leaves its empty bookkeeping table after downgrade.
                    with db.engine.begin() as connection:
                        connection.exec_driver_sql("DROP TABLE alembic_version")
                assert not inspect(db.engine).get_table_names()
        finally:
            db.session.remove()
            db.engine.dispose()


@pytest.fixture
def mysql_app(mysql_schema):
    migrate(mysql_schema, "upgrade")
    with mysql_schema.app_context():
        user = AdminUser(username="admin")
        user.set_password("test-password-2026")
        db.session.add(user)
        db.session.commit()
    return mysql_schema


def test_mysql_upgrade_downgrade_empty_schema(mysql_schema):
    migrate(mysql_schema, "upgrade")
    with mysql_schema.app_context():
        assert set(db.metadata.tables) <= set(inspect(db.engine).get_table_names())
    migrate(mysql_schema, "downgrade", "base")
    with mysql_schema.app_context():
        assert inspect(db.engine).get_table_names() == ["alembic_version"]
        assert db.session.execute(text("SELECT * FROM alembic_version")).all() == []
        db.session.remove()
    migrate(mysql_schema, "upgrade")


def test_mysql_unique_slug(mysql_app):
    with mysql_app.app_context():
        db.session.add(Event(title="First", slug="same-slug", date=date(2026, 1, 1)))
        db.session.commit()
        db.session.add(Event(title="Second", slug="same-slug", date=date(2026, 2, 1)))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert db.session.scalar(db.select(db.func.count(Event.id))) == 1


def test_mysql_utf8mb4_emoji_roundtrip(mysql_app):
    title = "Musik malam 🎧✨"
    with mysql_app.app_context():
        row = Event(title=title, slug="emoji", date=date(2026, 1, 1), status="published")
        db.session.add(row)
        db.session.commit()
        db.session.expire_all()
        assert db.session.scalar(db.select(Event.title)) == title
    assert title in mysql_app.test_client().get("/recap/emoji").text


@pytest.mark.parametrize("needle", ["%", "_", "/", "\\"])
def test_mysql_search_like_literals(mysql_app, needle):
    with mysql_app.app_context():
        db.session.add_all(
            [
                Event(title=f"Target {needle} literal", slug="target", date=date(2026, 1, 1)),
                Event(title="Unrelated ordinary title", slug="ordinary", date=date(2026, 1, 1)),
            ]
        )
        db.session.commit()
    client = mysql_app.test_client()
    assert (
        client.post(
            "/admin/login", data={"username": "admin", "password": "test-password-2026"}
        ).status_code
        == 302
    )
    response = client.get("/admin/events", query_string={"q": needle})
    assert response.status_code == 200
    assert f"Target {needle} literal" in response.text
    assert "Unrelated ordinary title" not in response.text


def test_mysql_public_year_filter(mysql_app):
    with mysql_app.app_context():
        for slug, day, status in [
            ("previous-year", date(2025, 12, 31), "published"),
            ("first-day", date(2026, 1, 1), "published"),
            ("last-day", date(2026, 12, 31), "published"),
            ("next-year", date(2027, 1, 1), "published"),
            ("draft-in-year", date(2026, 6, 1), "draft"),
        ]:
            db.session.add(Event(title=slug, slug=slug, date=day, status=status))
        db.session.commit()
    response = mysql_app.test_client().get("/recap?tahun=2026")
    assert response.status_code == 200
    assert "/recap/first-day" in response.text and "/recap/last-day" in response.text
    for slug in ["previous-year", "next-year", "draft-in-year"]:
        assert f"/recap/{slug}" not in response.text


def upload_payload():
    raw = io.BytesIO()
    Image.new("RGB", (64, 64), "purple").save(raw, "PNG")
    raw.seek(0)
    return {"image": (raw, "test.png"), "category_id": 0, "event_id": 0, "sort_order": 0}


def upload_process(config, hold, pipe):
    """Each spawned process owns its Flask app, DB pool and OS file descriptor."""
    application = create_app(config)
    try:
        if hold:
            from app.services import media

            original = media.processing_slot

            @contextmanager
            def controlled_slot():
                with original():
                    pipe.send("locked")
                    assert pipe.poll(15), "Parent did not release the upload test barrier"
                    assert pipe.recv() == "release"
                    yield

            media.processing_slot = controlled_slot
        client = application.test_client()
        assert (
            client.post(
                "/admin/login", data={"username": "admin", "password": "test-password-2026"}
            ).status_code
            == 302
        )
        response = client.post(
            "/admin/media/upload",
            data=upload_payload(),
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        pipe.send(response.status_code)
    except Exception as error:
        # Do not send exceptions containing SQL parameters/connection credentials.
        pipe.send(type(error).__name__)
        raise
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()
        pipe.close()


def receive(pipe):
    assert pipe.poll(20), "Upload subprocess did not respond within 20 seconds"
    return pipe.recv()


def exercise_upload_lock(application):
    context = multiprocessing.get_context("spawn")
    config = {
        key: application.config[key]
        for key in [
            "TESTING",
            "APP_ENV",
            "SECRET_KEY",
            "SQLALCHEMY_DATABASE_URI",
            "MEDIA_ROOT",
            "WTF_CSRF_ENABLED",
            "RATELIMIT_ENABLED",
        ]
    }
    processes = []
    channels = []
    try:
        for hold in [True, False]:
            parent, child = context.Pipe()
            process = context.Process(target=upload_process, args=(config, hold, child))
            process.start()
            child.close()
            processes.append(process)
            channels.append(parent)
            assert receive(parent) == ("locked" if hold else 422)
        assert not list(Path(config["MEDIA_ROOT"]).glob("*.webp"))
        channels[0].send("release")
        assert receive(channels[0]) == 200
        for process in processes:
            process.join(5)
            assert process.exitcode == 0
        client = application.test_client()
        client.post("/admin/login", data={"username": "admin", "password": "test-password-2026"})
        assert client.post("/admin/media/upload", data=upload_payload()).status_code == 302
        with application.app_context():
            assert db.session.scalar(db.select(db.func.count(MediaAsset.id))) == 2
        assert len(list(Path(config["MEDIA_ROOT"]).glob("*.webp"))) == 6
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(5)
        for channel in channels:
            channel.close()


@pytest.mark.skipif(os.name != "posix", reason="Production upload locking requires POSIX flock")
def test_mysql_upload_lock_two_processes(mysql_app):
    exercise_upload_lock(mysql_app)
