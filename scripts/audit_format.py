"""Capture/compare deterministic demo HTML and pixels for formatting-only changes.

State and captures must live outside the checkout. This helper only uses its own
SQLite database, never environment database URLs or production credentials.
"""

import argparse
import difflib
import json
import logging
import re
import sys
import threading
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXED_TIME = datetime(2026, 10, 29, 12, tzinfo=timezone.utc).timestamp()
PASSWORD = "audit-fixture-only-password-2026"


class NormalizedHTML(HTMLParser):
    """Normalize indentation, not attributes, text words or pre-line content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.text_edges = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        # HTML responsive-size grammar ignores runs of whitespace. Keep all
        # other attribute values exact, including URLs and user-supplied text.
        attrs = [
            (name, re.sub(r"\s+", " ", value).strip() if name == "sizes" and value else value)
            for name, value in attrs
        ]
        attributes = dict(attrs)
        self.tokens.append(["start", tag, sorted(attrs)])
        sensitive = (
            tag in {"pre", "textarea", "code"} or "prose" in attributes.get("class", "").split()
        )
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append((tag, sensitive))

    def handle_startendtag(self, tag, attrs):
        self.tokens.append(["void", tag, sorted(attrs)])

    def handle_endtag(self, tag):
        self.tokens.append(["end", tag])
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_data(self, value):
        if any(sensitive for _, sensitive in self.stack):
            self.tokens.append(["sensitive-text", value])
        elif value.strip():
            normalized = re.sub(r"\s+", " ", value).strip()
            self.tokens.append(["text", normalized])
            self.text_edges.append(
                {
                    "parent": self.stack[-1][0] if self.stack else "document",
                    "text": normalized,
                    "leading_space": bool(value[:1].isspace()),
                    "trailing_space": bool(value[-1:].isspace()),
                }
            )


def build_app(state, initialize):
    from flask import session
    from flask_migrate import upgrade

    from app import create_app
    from app.extensions import db
    from app.models import (
        AdminUser,
        ArtistProfile,
        BookingInquiry,
        Event,
        GalleryCategory,
        MediaAsset,
        ProfileHighlight,
        SiteSetting,
        Testimonial,
    )
    from app.services.demo import seed

    state.mkdir(parents=True, exist_ok=True)
    database = state / "audit.sqlite3"
    if initialize and database.exists():
        raise RuntimeError("Refusing to initialize over an existing audit database")
    if not initialize and not database.exists():
        raise RuntimeError("Initialize the isolated audit fixture first")
    app = create_app(
        {
            "APP_ENV": "testing",
            "TESTING": True,
            "SECRET_KEY": "audit-fixture-only-key-2026-00000000",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(database),
            "MEDIA_ROOT": str(state / "media"),
            "PUBLIC_BASE_URL": "https://audit.example.invalid",
            "TRUSTED_HOSTS": None,
            "WTF_CSRF_ENABLED": True,
            "RATELIMIT_ENABLED": False,
        }
    )

    @app.before_request
    def deterministic_csrf():
        session["csrf_token"] = "audit-fixed-csrf-token-only"

    with app.app_context():
        if initialize:
            upgrade(directory=str(ROOT / "migrations"))
            seed()
            user = AdminUser(username="AUDIT-DEMO")
            user.set_password(PASSWORD)
            db.session.add(user)
            artist = db.session.scalar(db.select(ArtistProfile))
            assets = db.session.scalars(db.select(MediaAsset).order_by(MediaAsset.id)).all()
            category = db.session.scalar(db.select(GalleryCategory).order_by(GalleryCategory.id))
            for asset in assets:
                asset.category_id = category.id
            artist.hero_media_id = assets[0].id
            artist.portrait_media_id = assets[1].id
            artist.biography = "DEMO — Biografi untuk audit format.\nParagraf kedua tetap sama."
            artist.philosophy = "DEMO — Musik dan pengalaman bersama."
            db.session.add(
                ProfileHighlight(
                    profile_id=artist.id,
                    label="DEMO — Highlight",
                    value="DEMO",
                    sort_order=0,
                    is_demo=True,
                )
            )
            db.session.add(
                Testimonial(
                    name="DEMO — Klien",
                    quote="DEMO — Kutipan uji komposisi, bukan testimoni asli.",
                    rating=5,
                    published=True,
                    portrait_id=assets[2].id,
                    is_demo=True,
                )
            )
            db.session.add(
                BookingInquiry(
                    name="DEMO — Penyelenggara",
                    contact="000000000000",
                    event_date=date(2026, 11, 15),
                    location="DEMO — Jakarta",
                    message="DEMO — Inquiry untuk audit format.",
                    is_demo=True,
                )
            )
            db.session.add(
                Event(
                    title="DEMO — Draft",
                    slug="audit-demo-draft",
                    date=date(2026, 1, 1),
                    is_demo=True,
                )
            )
            for key, value in {
                "site_title": "DJ NAZYER",
                "whatsapp": "620000000000",
                "booking_email": "booking@example.com",
                "instagram": "https://www.instagram.com/example/",
                "youtube": "https://www.youtube.com/@example",
                "spotify": "https://open.spotify.com/artist/example",
                "tiktok": "https://www.tiktok.com/@example",
            }.items():
                db.session.add(SiteSetting(key=key, value=value, is_demo=True))
            db.session.commit()
            fixed = datetime(2026, 10, 29, 12)
            for model in db.Model.__subclasses__():
                if hasattr(model, "created_at"):
                    db.session.execute(db.update(model).values(created_at=fixed, updated_at=fixed))
            db.session.commit()
    return app


def routes(app):
    from app.extensions import db
    from app.models import BookingInquiry, Event, PricingPackage
    from app.services.cms import ENTITIES

    records = [
        ("home", "/", False),
        ("about", "/tentang", False),
        ("recap", "/recap", False),
        ("gallery", "/galeri", False),
        ("pricing", "/pricelist", False),
        ("contact", "/kontak", False),
        ("success", "/kontak/terkirim", False),
        ("sitemap", "/sitemap.xml", False),
        ("robots", "/robots.txt", False),
        ("not-found", "/missing", False),
        ("draft", "/recap/audit-demo-draft", False),
        ("recap-filter", "/recap?tahun=2026", False),
        ("gallery-filter", "/galeri?kategori=live-performance", False),
        ("gallery-empty", "/galeri?kategori=unknown", False),
        ("login", "/admin/login", False),
        ("dashboard", "/admin/", True),
        ("profile", "/admin/profile", True),
        ("settings", "/admin/settings", True),
        ("password", "/admin/password", True),
        ("logout-get", "/admin/logout", True),
        ("upload", "/admin/media/upload", True),
        ("inquiries", "/admin/inquiries", True),
    ]
    with app.app_context():
        event = db.session.scalar(db.select(Event).where(Event.status == "published"))
        records.append(("event-detail", "/recap/" + event.slug, False))
        inquiry_id = db.session.scalar(db.select(BookingInquiry.id))
        records.extend(
            [
                ("inquiry-detail", f"/admin/inquiries/{inquiry_id}", True),
                ("inquiry-delete", f"/admin/inquiries/{inquiry_id}/delete", True),
            ]
        )
        package_id = db.session.scalar(db.select(PricingPackage.id))
        records.append(("pricing-preview", f"/admin/pricing/{package_id}/preview", True))
        for kind, (model, _, _, _) in ENTITIES.items():
            record_id = db.session.scalar(db.select(model.id).order_by(model.id))
            for suffix, path in [
                ("list", f"/admin/{kind}"),
                ("new", f"/admin/{kind}/new"),
                ("edit", f"/admin/{kind}/{record_id}/edit"),
                ("delete", f"/admin/{kind}/{record_id}/delete"),
            ]:
                records.append((kind + "-" + suffix, path, True))
    return records


def capture(args):
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = build_app(args.state.resolve(), args.initialize)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    with patch("time.time", return_value=FIXED_TIME):
        public_client, admin_client = app.test_client(), app.test_client()
        html = admin_client.get("/admin/login").text
        csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
        assert (
            admin_client.post(
                "/admin/login",
                data={"username": "AUDIT-DEMO", "password": PASSWORD, "csrf_token": csrf},
            ).status_code
            == 302
        )
        entries = {}
        for label, path, authenticated in routes(app):
            client = admin_client if authenticated else public_client
            if label == "success":
                with client.session_transaction() as data:
                    data["inquiry_sent"] = True
            response = client.get(path)
            raw = response.text
            (output / "html").mkdir(exist_ok=True)
            (output / "html" / (label + ".html")).write_text(raw)
            parsed = NormalizedHTML()
            parsed.feed(raw)
            entries[label] = {
                "path": path,
                "status": response.status_code,
                "tokens": parsed.tokens,
                "text_edges": parsed.text_edges,
            }
        (output / "rendered.json").write_text(json.dumps(entries, indent=2))
        server = make_server("127.0.0.1", 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        (output / "screenshots").mkdir(exist_ok=True)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for width in (375, 768, 1280):
                    context = browser.new_context(
                        viewport={"width": width, "height": 900},
                        device_scale_factor=1,
                        reduced_motion="reduce",
                    )
                    page = context.new_page()
                    for label, path in [
                        ("home", "/"),
                        ("gallery", "/galeri"),
                        ("contact", "/kontak"),
                        ("dashboard", "/admin/"),
                    ]:
                        if label == "dashboard":
                            cookie = admin_client.get_cookie(app.config["SESSION_COOKIE_NAME"])
                            context.add_cookies(
                                [{"name": cookie.key, "value": cookie.value, "url": base}]
                            )
                        response = page.goto(base + path, wait_until="networkidle")
                        assert response.status == 200
                        page.evaluate("document.fonts.ready")
                        page.evaluate(
                            (
                                "async () => { const imgs=[...document.images]; "
                                "imgs.forEach(img=>img.loading='eager'); await "
                                "Promise.all(imgs.map(img=>img.decode().catch(()=>{}))); }"
                            )
                        )
                        page.screenshot(
                            path=str(output / "screenshots" / f"{label}-{width}.png"),
                            full_page=True,
                            animations="disabled",
                        )
                    context.close()
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=3)
    print(json.dumps({"output": str(output), "rendered_routes": len(entries), "screenshots": 12}))


def compare(args):
    from PIL import Image, ImageChops

    before = json.loads((args.before / "rendered.json").read_text())
    after = json.loads((args.after / "rendered.json").read_text())
    html_changes, edge_changes, pixels = [], [], []
    for label, original in before.items():
        current = after[label]
        if original["tokens"] != current["tokens"] or original["status"] != current["status"]:
            delta = list(
                difflib.unified_diff(
                    json.dumps(original["tokens"], indent=2).splitlines(),
                    json.dumps(current["tokens"], indent=2).splitlines(),
                    fromfile="before",
                    tofile="after",
                )
            )
            html_changes.append({"route": label, "diff": delta})
        edges = [
            (old, new)
            for old, new in zip(original["text_edges"], current["text_edges"])
            if old != new
        ]
        if edges:
            edge_changes.append({"route": label, "count": len(edges), "examples": edges})
    for source in sorted((args.before / "screenshots").glob("*.png")):
        with (
            Image.open(source).convert("RGB") as first,
            Image.open(args.after / "screenshots" / source.name).convert("RGB") as second,
        ):
            if first.size != second.size:
                pixels.append(
                    {
                        "image": source.name,
                        "before_size": first.size,
                        "after_size": second.size,
                        "size_changed": True,
                    }
                )
                continue
            difference = ImageChops.difference(first, second)
            count = (
                sum(pixel != (0, 0, 0) for pixel in difference.getdata())
                if difference.getbbox()
                else 0
            )
            pixels.append(
                {
                    "image": source.name,
                    "size": first.size,
                    "changed_pixels": count,
                    "percent": round(count / (first.width * first.height) * 100, 6),
                }
            )
    report = {
        "routes_compared": len(before),
        "html_differences": html_changes,
        "text_boundary_whitespace_changes": edge_changes,
        "screenshots": pixels,
    }
    args.output.write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "routes_compared": len(before),
                "html_differences": len(html_changes),
                "text_boundary_routes": len(edge_changes),
                "screenshots": pixels,
            }
        )
    )
    if html_changes or any(
        row.get("size_changed") or row.get("changed_pixels", 0) for row in pixels
    ):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("capture")
    command.add_argument("--state", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--initialize", action="store_true")
    command = commands.add_parser("compare")
    command.add_argument("--before", type=Path, required=True)
    command.add_argument("--after", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("state", "output", "before", "after"):
        value = getattr(args, name, None)
        if value and value.resolve().is_relative_to(ROOT):
            parser.error("Audit state and evidence must be outside the checkout")
    (capture if args.command == "capture" else compare)(args)


if __name__ == "__main__":
    main()
