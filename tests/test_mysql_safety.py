"""Run opt-in URL guards and the process harness without claiming a MySQL run."""

import os

import pytest

from tests.test_mysql import checked_test_url, exercise_upload_lock


@pytest.mark.parametrize(
    "uri",
    [
        "sqlite:///:memory:",
        "mysql+pymysql://root:secret@localhost/dj_nazyer_test",
        "mysql+pymysql://tester:secret@localhost/dj_nazyer",
        "mysql+pymysql://tester:secret@localhost/mysql",
        "mysql+pymysql://tester:secret@localhost/contest",
    ],
)
def test_mysql_guard_rejects_unsafe_target_before_connecting(uri):
    with pytest.raises(ValueError):
        checked_test_url(uri)


def test_mysql_guard_accepts_explicit_dedicated_test_target():
    uri = "mysql+pymysql://tester:secret@localhost/dj_nazyer_test"
    assert checked_test_url(uri) == uri


@pytest.mark.skipif(os.name != "posix", reason="Production upload locking requires POSIX flock")
def test_upload_process_harness_on_isolated_sqlite(app):
    # Verifies the barrier/real cross-process upload requests here, not MySQL behavior.
    exercise_upload_lock(app)
