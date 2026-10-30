"""Exercise backups only with a fake dump command and temporary media/archives."""

import gzip
import io
import os
import subprocess
import tarfile
from configparser import ConfigParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deployment/backup.sh"


@pytest.fixture
def backup_env(tmp_path):
    commands = tmp_path / "bin"
    commands.mkdir()
    dump = commands / "mysqldump"
    dump.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@" > "$DUMP_ARGUMENTS"\n'
        '[[ "${FAIL_DUMP:-0}" != 1 ]] || exit 1\n'
        'printf "CREATE TABLE fixture (id INT);\\n"\n'
    )
    dump.chmod(0o700)
    credentials = tmp_path / "client.cnf"
    credentials.write_text("[client]\nuser=fixture_only\npassword=not-a-real-account\n")
    credentials.chmod(0o600)
    media = tmp_path / "media" / "uploads"
    media.mkdir(parents=True)
    (media / "fixture.webp").write_bytes(b"fixture-media")
    (media / ".processing.lock").touch()
    output = tmp_path / "backups"
    output.mkdir()
    return {
        **os.environ,
        "PATH": f"{commands}:{os.environ['PATH']}",
        "NAZYER_MYSQL_CREDENTIALS": str(credentials),
        "NAZYER_MEDIA_PARENT": str(media.parent),
        "NAZYER_BACKUP_DIR": str(output),
        "DUMP_ARGUMENTS": str(tmp_path / "arguments.txt"),
    }


def run_backup(environment):
    return subprocess.run(
        ["bash", str(SCRIPT)], env=environment, capture_output=True, text=True, timeout=10
    )


def old_bundles(directory):
    paths = [directory / f"dj-nazyer-202501{day:02d}T000000Z.tar.gz" for day in range(1, 17)]
    for path in paths:
        path.write_bytes(b"existing backup")
    return paths


def test_backup_contents_permissions_and_retention(backup_env):
    output = Path(backup_env["NAZYER_BACKUP_DIR"])
    previous = old_bundles(output)
    unrelated = output / "other-site.tar.gz"
    malformed = output / "dj-nazyer-not-a-timestamp.tar.gz"
    unrelated.touch()
    malformed.touch()
    result = run_backup(backup_env)
    assert result.returncode == 0, result.stderr
    assert all(not path.exists() for path in previous[:3])
    assert all(path.exists() for path in previous[3:])
    assert unrelated.exists() and malformed.exists()
    current = [path for path in output.glob("dj-nazyer-*.tar.gz") if path not in previous]
    current.remove(malformed)
    assert len(current) == 1
    bundle = current[0]
    assert bundle.stat().st_mode & 0o777 == 0o600
    with tarfile.open(bundle) as archive:
        sql = gzip.decompress(archive.extractfile("dj_nazyer.sql.gz").read())
        assert sql == b"CREATE TABLE fixture (id INT);\n"
        media = io.BytesIO(archive.extractfile("media.tar.gz").read())
    with tarfile.open(fileobj=media) as archive:
        assert archive.extractfile("uploads/fixture.webp").read() == b"fixture-media"
        assert "uploads/.processing.lock" not in archive.getnames()
    args = Path(backup_env["DUMP_ARGUMENTS"]).read_text().splitlines()
    assert args[0].startswith("--defaults-extra-file=")
    assert args[-1] == "dj_nazyer"
    assert {"--single-transaction", "--no-tablespaces", "--set-gtid-purged=OFF"} <= set(args)
    assert not any("password=" in argument for argument in args)
    assert not list(output.glob(".nazyer-backup-*"))


def test_failed_dump_preserves_previous_backups_and_cleans_partial(backup_env):
    output = Path(backup_env["NAZYER_BACKUP_DIR"])
    previous = old_bundles(output)
    result = run_backup({**backup_env, "FAIL_DUMP": "1"})
    assert result.returncode != 0
    assert set(output.glob("*.tar.gz")) == set(previous)
    assert all(path.read_bytes() == b"existing backup" for path in previous)
    assert not list(output.glob(".nazyer-backup-*"))


def test_backup_rejects_concurrent_run_before_dump(backup_env):
    import fcntl

    output = Path(backup_env["NAZYER_BACKUP_DIR"])
    with (output / ".backup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = run_backup(backup_env)
    assert result.returncode != 0 and "Another DJ NAZYER backup" in result.stderr
    assert not Path(backup_env["DUMP_ARGUMENTS"]).exists()
    assert not list(output.glob("*.tar.gz"))


def test_backup_refuses_readable_by_group_credentials(backup_env):
    Path(backup_env["NAZYER_MYSQL_CREDENTIALS"]).chmod(0o640)
    result = run_backup(backup_env)
    assert result.returncode != 0 and "0600" in result.stderr
    assert not Path(backup_env["DUMP_ARGUMENTS"]).exists()


def test_backup_timer_and_service_are_scoped_online_examples():
    unit = ConfigParser(interpolation=None)
    unit.read(ROOT / "deployment/dj-nazyer-backup.service")
    service = unit["Service"]
    assert service["Type"] == "oneshot" and service["User"] == "nazyer"
    assert service["ReadWritePaths"] == "/var/backups/dj-nazyer"
    assert service["UMask"] == "0077"
    assert "ExecStartPre" not in service and "ExecStop" not in service
    assert "systemctl" not in SCRIPT.read_text()
    timer = ConfigParser(interpolation=None)
    timer.read(ROOT / "deployment/dj-nazyer-backup.timer")
    assert timer["Timer"]["OnCalendar"] == "*-*-* 03:15:00 Asia/Jakarta"
    assert timer["Timer"].getboolean("Persistent")
    assert timer["Timer"]["Unit"] == "dj-nazyer-backup.service"
