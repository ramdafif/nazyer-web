import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, render_template

from app import create_app
from app.extensions import db
from app.services.assets import register_assets
from scripts.prepare_assets import prepare
from tests.test_security_seo import production_config

ROOT = Path(__file__).resolve().parents[1]


class StaticReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in {"src", "href", "content"} and value:
                if urlsplit(value).path.startswith("/static/"):
                    self.urls.append(value)


def assert_versioned(html):
    parsed = StaticReferences()
    parsed.feed(html)
    assert parsed.urls, "The page must contain static references"
    for reference in parsed.urls:
        parts = urlsplit(reference)
        physical = ROOT / "app" / parts.path.lstrip("/")
        expected = hashlib.sha256(physical.read_bytes()).hexdigest()[:10]
        assert parse_qs(parts.query).get("v") == [expected], reference


@pytest.mark.parametrize("path", ["/", "/tentang", "/recap", "/galeri", "/pricelist", "/kontak"])
def test_public_static_references(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert_versioned(response.text)


@pytest.mark.parametrize(
    "path",
    ["/admin/", "/admin/events/new", "/admin/media/upload", "/admin/profile", "/admin/settings"],
)
def test_admin_static_references(admin, path):
    response = admin.get(path)
    assert response.status_code == 200
    assert_versioned(response.text)


def test_login_and_error_assets(client):
    assert_versioned(client.get("/admin/login").text)
    assert_versioned(client.get("/missing").text)


def test_templates_never_bypass_asset_helper():
    for path in (ROOT / "app/templates").rglob("*"):
        if path.is_file():
            assert not re.search(r"\burl_for\(\s*(['\"])static\1", path.read_text()), path


def test_hash_is_content_based_and_computed_once(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    source = static / "example.css"
    source.write_text("body { color: white; }")
    first = Flask("first", root_path=str(tmp_path), static_folder=None)
    first.add_url_rule("/static/<path:filename>", endpoint="static", view_func=lambda: "")
    register_assets(first)
    with first.test_request_context():
        original_url = first.jinja_env.globals["asset_url"]("example.css")
        source.write_text("body { color: purple; }")
        assert first.jinja_env.globals["asset_url"]("example.css") == original_url
        with monkeypatch.context() as patch:
            patch.setattr(Path, "read_bytes", lambda _: pytest.fail("Per-request asset I/O"))
            assert first.jinja_env.globals["asset_url"]("example.css") == original_url
    second = Flask("second", root_path=str(tmp_path), static_folder=None)
    second.add_url_rule("/static/<path:filename>", endpoint="static", view_func=lambda: "")
    register_assets(second)
    with second.test_request_context():
        current_url = second.jinja_env.globals["asset_url"]("example.css")
        assert current_url != original_url
        assert parse_qs(urlsplit(current_url).query)["v"] == [
            hashlib.sha256(source.read_bytes()).hexdigest()[:10]
        ]


def test_production_static_folder_none_still_renders(tmp_path):
    application = create_app(production_config(tmp_path))
    assert application.static_folder is None
    # The real production factory and Jinja engine are used; no MySQL connection
    # is needed for login or an explicit public-view context.
    response = application.test_client().get("/admin/login", base_url="https://dj.example.com")
    assert response.status_code == 200
    assert_versioned(response.text)
    with application.test_request_context("/admin/login", base_url="https://dj.example.com"):
        html = render_template(
            "public/gallery.html",
            title="Galeri",
            page="gallery",
            artist=SimpleNamespace(display_name="DJ NAZYER"),
            site={},
            site_media={},
            socials={},
            service_types=[],
            whatsapp_url=lambda *args: "",
            pagination=SimpleNamespace(items=[], pages=0),
            categories=[],
            selected_category="",
        )
        assert_versioned(html)
    with application.app_context():
        db.engine.dispose()


def test_css_and_font_versions_are_prepared():
    assert prepare(ROOT / "app/static", check=True) == []


def test_font_and_css_dependency_changes_invalidate_versions(tmp_path):
    static = tmp_path / "static"
    fonts, css, images = static / "fonts", static / "css", static / "images"
    for path in [fonts, css, images]:
        path.mkdir(parents=True)
    (fonts / "Demo.woff2").write_bytes(b"font-content-one")
    (images / "background.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    style = css / "example.css"
    style.write_text(
        "a{src:url('../fonts/Demo.woff2')}b{background:url('../images/background.svg')}"
    )
    assert prepare(static)
    original_css = style.read_text()
    manifest = fonts / "manifest.json"
    original_font = json.loads(manifest.read_text())["fonts/Demo.woff2"]
    assert re.search(r"\.[a-f0-9]{10}\.woff2", original_font)
    assert "?v=" in original_css
    assert prepare(static, check=True) == []
    (fonts / "Demo.woff2").write_bytes(b"font-content-two")
    assert prepare(static, check=True)
    prepare(static)
    assert json.loads(manifest.read_text())["fonts/Demo.woff2"] != original_font
    assert style.read_text() != original_css
    font_updated_css = style.read_text()
    (images / "background.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><!--v2--></svg>'
    )
    prepare(static)
    assert style.read_text() != font_updated_css
    assert prepare(static, check=True) == []


def test_nginx_cache_policy_has_no_expires_generated_headers():
    configuration = (ROOT / "deployment/nginx.conf").read_text()
    assert not re.search(r"^\s*expires\s+(?!off\s*;)", configuration, re.MULTILINE)
    assert "max-age=2592000, immutable" in configuration
    assert "$nazyer_static_cache_control" in configuration
    cache_map = (ROOT / "deployment/nginx-static-cache.conf.example").read_text()
    assert "max-age=31536000, immutable" in cache_map
    assert "max-age=0, must-revalidate" in cache_map
