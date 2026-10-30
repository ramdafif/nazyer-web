import io
import threading

import pytest
from PIL import Image
from playwright.sync_api import expect
from werkzeug.datastructures import FileStorage
from werkzeug.serving import make_server

from app.extensions import db
from app.models import BookingInquiry
from app.services.media import upload_image

pytestmark = pytest.mark.browser


@pytest.fixture
def live_server(app):
    """An isolated pytest server, never the user's live or preview deployment."""
    app.config["WTF_CSRF_ENABLED"] = True
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=3)


def assert_no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), page.url


@pytest.mark.parametrize("width", [375, 768, 1280])
def test_public_layout_navigation_and_assets(page, live_server, width):
    page.set_viewport_size({"width": width, "height": 900})
    missing_url = live_server + "/uji-halaman-tidak-ada"
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    failures = []
    page.on(
        "response",
        lambda response: (
            failures.append(response.url)
            if response.status >= 400 and response.url != missing_url
            else None
        ),
    )
    for path in [
        "/",
        "/tentang",
        "/recap",
        "/galeri",
        "/pricelist",
        "/kontak",
        "/uji-halaman-tidak-ada",
    ]:
        response = page.goto(live_server + path)
        assert response.status == (404 if path == "/uji-halaman-tidak-ada" else 200)
        page.evaluate("document.fonts.ready")
        assert_no_overflow(page)
        assert page.locator("main").count() == 1 and page.locator("h1").count() == 1
        assert page.locator("html").get_attribute("lang") == "id"
        assert page.locator("img:not([alt])").count() == 0
        assert not page.locator('a[href="#"],button:empty').count()
        expect(page.locator("footer")).to_contain_text("All rights reserved.")
        expect(page.locator("footer")).to_contain_text("Developed by Elkyno Technology")
        for image in page.locator("img:visible").all():
            # Below-fold illustrations are intentionally lazy-loaded.
            image.scroll_into_view_if_needed()
            expect(image).to_have_js_property("complete", True)
            assert image.evaluate("(img) => img.naturalWidth > 0"), image.get_attribute("src")
    page.get_by_role("link", name="Kembali ke beranda", exact=True).click()
    expect(page).to_have_url(live_server + "/")
    cta = page.locator(".contact-cta")
    mascot = cta.locator(".cta-character img")
    mascot.scroll_into_view_if_needed()
    expect(mascot).to_have_js_property("complete", True)
    assert mascot.evaluate("img => img.naturalWidth > 0")
    cta.get_by_role("link", name="Mulai Diskusi Event", exact=False).click()
    expect(page).to_have_url(live_server + "/kontak")
    page.goto(live_server)
    if width <= 960:
        page.get_by_role("button", name="Buka navigasi").click()
        expect(page.get_by_role("dialog", name="Navigasi utama")).to_be_visible()
        expect(page.get_by_role("button", name="Buka navigasi")).to_have_attribute(
            "aria-expanded", "true"
        )
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog", name="Navigasi utama")).not_to_be_visible()
        page.get_by_role("button", name="Buka navigasi").click()
        page.locator("#mobile-nav").get_by_role("link", name="Galeri", exact=False).click()
        expect(page).to_have_url(live_server + "/galeri")
    assert not errors, errors
    assert not failures, failures


@pytest.mark.parametrize("width", [375, 768, 1280])
def test_lightbox_keyboard_and_focus(page, app, live_server, width):
    with app.app_context():
        for i in range(2):
            raw = io.BytesIO()
            Image.new("RGB", (300, 400), (60 + i * 40, 20, 100)).save(raw, "PNG")
            raw.seek(0)
            upload_image(
                FileStorage(stream=raw, filename="test.png"),
                {
                    "alt_text": f"Foto uji {i}",
                    "caption": f"Caption {i}",
                    "is_public": True,
                    "sort_order": i,
                },
            )
        db.session.commit()
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(live_server + "/galeri")
    photos = page.locator("[data-lightbox]")
    photos.first.click()
    expect(page.get_by_role("dialog", name="Penampil foto")).to_be_visible()
    expect(page.locator("#lightbox-image")).to_have_attribute("alt", "Foto uji 0")
    page.keyboard.press("ArrowRight")
    expect(page.locator("#lightbox-image")).to_have_attribute("alt", "Foto uji 1")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#lightbox-image")).to_have_attribute("alt", "Foto uji 0")
    page.get_by_role("button", name="Foto berikutnya").click()
    expect(page.locator("#lightbox-counter")).to_have_text("2 / 2")
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog", name="Penampil foto")).not_to_be_visible()
    expect(photos.first).to_be_focused()
    assert_no_overflow(page)


@pytest.mark.parametrize("width", [375, 768, 1280])
def test_inquiry_form_browser(page, app, live_server, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(live_server + "/kontak")
    page.get_by_label("Nama lengkap").fill("Klien Uji Browser")
    page.get_by_label("Nomor WhatsApp").fill("081234567890")
    page.get_by_label("Lokasi event").fill("Jakarta")
    page.get_by_label("Ceritakan rencana").fill(
        "Kami ingin membicarakan kebutuhan event yang direncanakan."
    )
    page.get_by_role("button", name="Kirim Inquiry").click()
    expect(page).to_have_url(live_server + "/kontak/terkirim")
    expect(page.get_by_role("heading", level=1)).to_contain_text("sudah kami terima.")
    expect(page.get_by_text("Ini belum merupakan konfirmasi booking.", exact=False)).to_be_visible()
    assert_no_overflow(page)
    with app.app_context():
        assert db.session.scalar(db.select(BookingInquiry)).status == "baru"


@pytest.mark.parametrize("width", [375, 768, 1280])
def test_admin_create_event_browser(page, live_server, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(live_server + "/admin/login")
    page.get_by_label("Nama pengguna").fill("admin")
    page.get_by_label("Password", exact=True).fill("test-password-2026")
    page.get_by_role("button", name="Masuk ke Dashboard").click()
    expect(page.get_by_role("heading", name="Di balik setiap momen.")).to_be_visible()
    assert_no_overflow(page)
    page.get_by_role("link", name="Tambah Event", exact=False).click()
    page.get_by_label("Judul event").fill("Event Uji Browser")
    page.get_by_label("Tanggal event").fill("2026-10-01")
    page.get_by_label("Status", exact=True).select_option("published")
    page.get_by_role("button", name="Simpan Perubahan").click()
    expect(page.get_by_text("Perubahan berhasil disimpan.")).to_be_visible()
    assert_no_overflow(page)
    page.goto(live_server + "/recap/event-uji-browser")
    expect(page.get_by_role("heading", level=1)).to_have_text("Event Uji Browser")


def test_reduced_motion_and_keyboard_entry(page, live_server):
    page.emulate_media(reduced_motion="reduce")
    page.goto(live_server)
    assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == "auto"
    page.keyboard.press("Tab")
    expect(page.get_by_role("link", name="Langsung ke konten")).to_be_focused()


@pytest.mark.parametrize("width", [375, 768, 1280])
def test_populated_home_layout(page, app, live_server, width):
    from app.models import Testimonial as Review

    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        db.session.add(
            Review(
                name="Uji Browser",
                quote="Data uji sementara untuk memeriksa komposisi halaman.",
                published=True,
                is_demo=True,
            )
        )
        db.session.commit()
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(live_server)
    expect(page.get_by_role("heading", name="Featured Performances.")).to_be_visible()
    expect(page.get_by_role("heading", name="What They Say.")).to_be_visible()
    assert page.locator(".price-card").count() == 3
    assert page.locator("[data-lightbox]").count() == 6
    assert_no_overflow(page)


def test_navigation_without_javascript(browser, live_server):
    context = browser.new_context(java_script_enabled=False, viewport={"width": 375, "height": 900})
    page = context.new_page()
    page.goto(live_server)
    expect(
        page.locator(".desktop-nav").get_by_role("link", name="Galeri", exact=True)
    ).to_be_visible()
    page.locator(".desktop-nav").get_by_role("link", name="Galeri", exact=True).click()
    expect(page).to_have_url(live_server + "/galeri")
    assert_no_overflow(page)
    context.close()


@pytest.mark.parametrize("width", [375, 768, 1280])
def test_testimonial_navigation_and_json_data_follow_published_content(
    page, app, live_server, width
):
    import json

    from app.models import Testimonial as Review

    page.set_viewport_size({"width": width, "height": 900})
    page.add_init_script("""window.auditCSP = [];
        document.addEventListener('securitypolicyviolation', event => {
            window.auditCSP.push(event.violatedDirective);
        });""")
    page.goto(live_server)
    expect(page.locator('a[href="/#testimoni"]')).to_have_count(0)
    data = json.loads(page.locator('script[type="application/ld+json"]').text_content())
    assert {node["@type"] for node in data["@graph"]} == {"WebSite", "Person"}
    assert not page.evaluate("window.auditCSP")
    with app.app_context():
        db.session.add(
            Review(
                name="Klien Uji",
                quote="Kutipan sementara untuk pengujian navigasi.",
                published=True,
            )
        )
        db.session.commit()
    # Cover both navigation from another document and the homepage's own fragment.
    for source in ["/tentang", "/"]:
        page.goto(live_server + source)
        if width <= 960:
            page.get_by_role("button", name="Buka navigasi").click()
            page.locator("#mobile-nav").get_by_role("link", name="Testimoni", exact=False).click()
            expect(page.locator("#mobile-nav")).not_to_be_visible()
        else:
            page.locator(".desktop-nav").get_by_role("link", name="Testimoni", exact=True).click()
        expect(page).to_have_url(live_server + "/#testimoni")
        expect(page.locator("section#testimoni")).to_be_in_viewport()
        assert_no_overflow(page)
        assert not page.evaluate("window.auditCSP")
    with app.app_context():
        db.session.scalar(db.select(Review)).published = False
        db.session.commit()
    page.reload()
    expect(page.locator('a[href="/#testimoni"]')).to_have_count(0)
    expect(page.locator("section#testimoni")).to_have_count(0)
