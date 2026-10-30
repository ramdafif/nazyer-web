"""Local cold-cache paint/shift samples; not Lighthouse or field Core Web Vitals."""

import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from flask_migrate import upgrade
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    from app import create_app
    from app.extensions import db

    rows = []
    with tempfile.TemporaryDirectory(prefix="nazyer-web-") as temporary:
        directory = Path(temporary)
        app = create_app(
            {
                "APP_ENV": "testing",
                "TESTING": True,
                "SECRET_KEY": "isolated-web-measurement-only-2026",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(directory / "web.sqlite3"),
                "MEDIA_ROOT": str(directory / "media"),
                "RATELIMIT_ENABLED": False,
            }
        )
        with app.app_context():
            upgrade(directory=str(ROOT / "migrations"))
        server = make_server("127.0.0.1", 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for width in [375, 768, 1280]:
                    context = browser.new_context(viewport={"width": width, "height": 900})
                    page = context.new_page()
                    page.add_init_script("""
window.__qa = {
    lcp: 0,
    cls: 0
};
new PerformanceObserver(list => {
    for (const entry of list.getEntries()) window.__qa.lcp = entry.startTime
}).observe({
    type: 'largest-contentful-paint',
    buffered: true
});
new PerformanceObserver(list => {
    for (const entry of list.getEntries())
        if (!entry.hadRecentInput) window.__qa.cls += entry.value
}).observe({
    type: 'layout-shift',
    buffered: true
});
""")
                    page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="networkidle")
                    page.evaluate("document.fonts.ready")
                    values = page.evaluate(
                        (
                            "() => {const nav=performance.getEntriesByType('navigation')[0];re"
                            "turn {fcp_ms:performance.getEntriesByName('first-contentful-paint"
                            "')[0]?.startTime,lcp_ms:window.__qa.lcp,cls:window.__qa.cls,ttfb_"
                            "ms:nav.responseStart-nav.requestStart,resource_count:performance."
                            "getEntriesByType('resource').length}}"
                        )
                    )
                    rows.append(
                        {
                            "viewport_width": width,
                            **{
                                key: round(value, 3) if isinstance(value, float) else value
                                for key, value in values.items()
                            },
                        }
                    )
                    context.close()
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=3)
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
    report = {
        "environment": (
            "Local Chromium 141 headless, SQLite, empty CMS, cold browser "
            "contexts, no CPU/network throttling, no HTTPS"
        ),
        "samples": rows,
        "limits": (
            "Synthetic samples only. No Lighthouse score or field INP "
            "measurement. Real photo content, VPS/MySQL/network latency and "
            "user devices can change these values."
        ),
    }
    (ROOT / "PERFORMANCE_REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
