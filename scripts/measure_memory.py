"""Measure combined Gunicorn PSS/RSS on Linux using a throwaway SQLite database.

This is a reproducible local measurement, not a production MySQL load guarantee.
Run with the project's Python venv: python scripts/measure_memory.py.
"""

import concurrent.futures
import http.client
import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def memory(pid, metrics_file=None):
    if not Path(f"/proc/{pid}/task/{pid}/children").exists():
        records = (
            [json.loads(line) for line in metrics_file.read_text().splitlines() if line]
            if metrics_file.exists()
            else []
        )
        peaks = {}
        for record in records:
            peaks[record["pid"]] = max(peaks.get(record["pid"], 0), record["rss_mib"])
        return {"pss_mib": None, "rss_mib": round(sum(peaks.values()), 2), "processes": len(peaks)}
    children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
    total = {"pss_mib": 0.0, "rss_mib": 0.0, "processes": len(children) + 1}
    for current in [str(pid)] + children:
        try:
            data = Path(f"/proc/{current}/smaps_rollup").read_text()
            total["pss_mib"] += int(re.search(r"^Pss:\s+(\d+)", data, re.M).group(1)) / 1024
            total["rss_mib"] += int(re.search(r"^Rss:\s+(\d+)", data, re.M).group(1)) / 1024
        except FileNotFoundError:
            pass
    return {key: round(value, 2) for key, value in total.items()}


def main():
    from flask_migrate import upgrade
    from PIL import Image

    from app import create_app
    from app.extensions import db
    from app.models import AdminUser

    password = secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix="nazyer-memory-") as temporary:
        temp = Path(temporary)
        uri = "sqlite:///" + str(temp / "benchmark.sqlite3")
        application = create_app(
            {
                "APP_ENV": "testing",
                "SQLALCHEMY_DATABASE_URI": uri,
                "MEDIA_ROOT": str(temp / "media"),
                "SECRET_KEY": secrets.token_hex(32),
            }
        )
        with application.app_context():
            upgrade(directory=str(ROOT / "migrations"))
            user = AdminUser(username="memory-check")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            db.engine.dispose()
        # Unix sockets are forbidden by some managed validation sandboxes. A
        # loopback override measures the same workers without changing deployment config.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        metrics_file = temp / "process-memory.jsonl"
        config = temp / "benchmark-gunicorn.py"
        config.write_text(f"""import runpy,resource,json,os
globals().update(runpy.run_path({str(ROOT / "deployment/gunicorn.conf.py")!r}))
_base_post_fork=post_fork
def _report():
    with open({str(metrics_file)!r},'a') as stream:
        stream.write(json.dumps({{'pid':os.getpid(),'rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2)}})+'\\n')
def when_ready(server): _report()
def post_fork(server,worker):
    _base_post_fork(server,worker)
    _report()
def post_request(worker,req,environ,response): _report()
""")
        env = {
            **os.environ,
            "APP_ENV": "development",
            "DATABASE_URL": uri,
            "MEDIA_ROOT": str(temp / "media"),
            "SECRET_KEY": secrets.token_hex(32),
            "TRUSTED_HOSTS": "localhost",
            "PROXY_HOPS": "0",
        }
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "gunicorn",
                "-c",
                str(config),
                "--bind",
                f"127.0.0.1:{port}",
                "wsgi:app",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
        )
        samples = []
        stop = threading.Event()

        def request(
            path,
            method="GET",
            body=None,
            cookie="",
            content_type="application/x-www-form-urlencoded",
        ):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
            connection.request(
                method,
                path,
                body,
                {"Host": "localhost", "Cookie": cookie, "Content-Type": content_type},
            )
            response = connection.getresponse()
            payload = response.read().decode("utf-8")
            result = (
                response.status,
                payload,
                (response.getheader("Set-Cookie") or "").split(";", 1)[0],
            )
            connection.close()
            return result

        try:
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError("Gunicorn exited before startup")
                try:
                    if request("/")[0] == 200:
                        break
                except (ConnectionError, OSError):
                    pass
                time.sleep(0.05)
            for path in ["/", "/tentang", "/recap", "/galeri", "/pricelist", "/kontak"]:
                assert request(path)[0] == 200

            def sample():
                while not stop.wait(0.02):
                    samples.append(memory(proc.pid, metrics_file))

            sampler = threading.Thread(target=sample, daemon=True)
            sampler.start()
            warm = memory(proc.pid, metrics_file)
            _, html, cookie = request("/admin/login")
            token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
            status, _, cookie = request(
                "/admin/login",
                "POST",
                urlencode({"username": "memory-check", "password": password, "csrf_token": token}),
                cookie,
            )
            assert status == 302
            for path in [
                "/admin/",
                "/admin/events",
                "/admin/media",
                "/admin/settings",
                "/admin/profile",
            ]:
                assert request(path, cookie=cookie)[0] == 200
            admin_warm = memory(proc.pid, metrics_file)
            _, html, updated_cookie = request("/admin/media/upload", cookie=cookie)
            cookie = updated_cookie or cookie
            token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
            raw = io.BytesIO()
            Image.new("RGB", (3000, 2400), (85, 25, 140)).save(raw, "JPEG")
            boundary = "nazyer-" + secrets.token_hex(16)
            payload = b""
            for key, value in {
                "csrf_token": token,
                "category_id": "0",
                "event_id": "0",
                "sort_order": "0",
                "alt_text": "Memory measurement",
            }.items():
                payload += (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n'
                    f"\r\n{value}\r\n"
                ).encode()
            payload += (
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
                    'filename="test.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'
                ).encode()
                + raw.getvalue()
                + f"\r\n--{boundary}--\r\n".encode()
            )
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        request,
                        "/admin/media/upload",
                        "POST",
                        payload,
                        cookie,
                        "multipart/form-data; boundary=" + boundary,
                    )
                    for _ in range(2)
                ]
                statuses = [future.result()[0] for future in futures]
            assert 302 in statuses and set(statuses) <= {302, 422}, statuses
            samples.append(memory(proc.pid, metrics_file))
            stop.set()
            sampler.join(timeout=3)
            result = {
                "environment": (
                    "Linux, Python 3.12, isolated SQLite, loopback TCP override; not "
                    "production MySQL/Unix socket"
                ),
                "workers": 2,
                "preload": True,
                "public_warm": warm,
                "cms_warm": admin_warm,
                "concurrent_uploads": {
                    "requests": 2,
                    "image_pixels": 7200000,
                    "http_statuses": statuses,
                },
                "peak_pss_mib": max(
                    (x["pss_mib"] for x in samples if x["pss_mib"] is not None), default=None
                ),
                "peak_rss_sum_mib": max(x["rss_mib"] for x in samples),
                "note": (
                    "PSS accounts for shared preloaded pages once; summed RSS "
                    "double-counts them. If /proc is unavailable, PSS is null and RSS "
                    "is a conservative sum of per-process getrusage peaks. Production "
                    "budget must be measured on the VPS."
                ),
            }
            output = ROOT / "MEMORY_REPORT.json"
            output.write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
        finally:
            stop.set()
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    main()
