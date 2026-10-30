import io
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    ArtistProfile,
    BookingInquiry,
    Event,
    GalleryCategory,
    MediaAsset,
    PricingPackage,
    ServiceType,
    SiteSetting,
)
from tests.test_cms import image_bytes


def add_photo(admin, **extra):
    payload = {
        "image": (image_bytes(), "photo.jpg"),
        "alt_text": "Foto panggung",
        "category_id": 0,
        "event_id": 0,
        "sort_order": 0,
        **extra,
    }
    response = admin.post(
        "/admin/media/upload",
        data=payload,
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert response.status_code == 200, response.text
    return response.json["id"]


@pytest.mark.parametrize(
    "filename,content",
    [
        ("attack.svg", b'<svg onload="alert(1)"/>'),
        ("script.jpg", b"<?php echo 1; ?>"),
        ("wrong.png", b"not an image"),
        ("../../attack.html", b"<h1>attack</h1>"),
    ],
)
def test_reject_unsafe_uploads(app, admin, filename, content):
    response = admin.post(
        "/admin/media/upload",
        data={
            "image": (io.BytesIO(content), filename),
            "category_id": 0,
            "event_id": 0,
            "sort_order": 0,
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(MediaAsset.id))) == 0
    assert not list(Path(app.config["MEDIA_ROOT"]).glob("*.webp"))


def test_reject_mismatched_format_and_dimensions(admin):
    for buffer, name in [
        (image_bytes("JPEG"), "pretend.png"),
        (image_bytes("PNG", (6001, 32)), "oversize.png"),
    ]:
        response = admin.post(
            "/admin/media/upload",
            data={"image": (buffer, name), "category_id": 0, "event_id": 0, "sort_order": 0},
            content_type="multipart/form-data",
        )
        assert response.status_code == 422


def test_metadata_removed_and_filename_safe(app, admin):
    image = Image.new("RGB", (200, 100), "purple")
    metadata = Image.Exif()
    metadata[0x010E] = "private-metadata"
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=metadata)
    buffer.seek(0)
    response = admin.post(
        "/admin/media/upload",
        data={
            "image": (buffer, "../../private.jpg"),
            "category_id": 0,
            "event_id": 0,
            "sort_order": 0,
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    with app.app_context():
        asset = db.session.scalar(db.select(MediaAsset))
        assert "/" not in asset.filename and len(asset.filename) == 45
        with Image.open(Path(app.config["MEDIA_ROOT"]) / asset.filename) as result:
            assert not result.getexif() and b"private-metadata" not in result.info.get("exif", b"")


def test_linked_media_cannot_be_deleted(app, admin):
    mid = add_photo(admin)
    with app.app_context():
        db.session.add(ArtistProfile(hero_media_id=mid))
        db.session.commit()
        filename = db.session.get(MediaAsset, mid).filename
    response = admin.post(f"/admin/media/{mid}/delete", data={"confirm": "y"})
    assert response.status_code == 422
    assert (Path(app.config["MEDIA_ROOT"]) / filename).exists()
    with app.app_context():
        assert db.session.get(MediaAsset, mid)
        with pytest.raises(IntegrityError):
            db.session.execute(db.delete(MediaAsset).where(MediaAsset.id == mid))
            db.session.commit()
        db.session.rollback()


def test_gallery_filters_and_visibility(app, admin):
    with app.app_context():
        cat = GalleryCategory(name="Live Performance", slug="live-performance")
        db.session.add(cat)
        db.session.commit()
        cid = cat.id
    add_photo(admin, category_id=cid, is_public="y", alt_text="Foto live yang terbit")
    add_photo(admin, alt_text="Foto tersembunyi")
    assert "Foto live yang terbit" in admin.get("/galeri?kategori=live-performance").text
    assert "Foto tersembunyi" not in admin.get("/galeri").text
    assert "Foto live yang terbit" not in admin.get("/galeri?kategori=unknown").text


def test_event_gallery_order_and_reuse(app, admin):
    ids = [add_photo(admin), add_photo(admin)]
    payload = {
        "title": "Urutan Galeri",
        "slug": "urutan-galeri",
        "date": "2026-01-01",
        "category_id": 0,
        "cover_id": ids[0],
        "status": "published",
        "media_ids": ids,
        "media_order": ",".join(map(str, reversed(ids))),
    }
    assert admin.post("/admin/events/new", data=payload).status_code == 302
    with app.app_context():
        event = db.session.scalar(db.select(Event))
        eid = event.id
        assert [x.media_id for x in event.media] == list(reversed(ids))
    payload["media_order"] = ",".join(map(str, ids))
    assert admin.post(f"/admin/events/{eid}/edit", data=payload).status_code == 302
    with app.app_context():
        assert [x.media_id for x in db.session.get(Event, eid).media] == ids
    assert admin.get("/recap/urutan-galeri").status_code == 200


def test_inquiry_submission_and_admin_followup(app, client, admin):
    payload = {
        "name": "Penyelenggara",
        "contact": "081234567890",
        "service_type_id": 0,
        "package_id": 0,
        "location": "Jakarta",
        "message": "Kami ingin berdiskusi tentang rencana event.",
    }
    response = client.post("/kontak", data=payload)
    assert response.status_code == 303
    assert "belum merupakan konfirmasi booking" in client.get(response.location).text
    with app.app_context():
        inquiry = db.session.scalar(db.select(BookingInquiry))
        iid = inquiry.id
        assert inquiry.status == "baru"
    assert admin.get(f"/admin/inquiries/{iid}").status_code == 200
    assert (
        admin.post(
            f"/admin/inquiries/{iid}",
            data={"status": "dihubungi", "internal_notes": "Sudah ditindaklanjuti."},
        ).status_code
        == 302
    )
    assert "Penyelenggara" in admin.get("/admin/inquiries?status=dihubungi&q=Penyelenggara").text
    assert admin.post(f"/admin/inquiries/{iid}/delete", data={"confirm": "y"}).status_code == 302


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"contact": "abc"},
        {"message": "singkat"},
        {"event_date": "2000-01-01"},
        {"package_id": 99999},
        {"service_type_id": 99999},
    ],
)
def test_inquiry_validation(app, client, overrides):
    payload = {
        "name": "Pemilik Event",
        "contact": "081234567890",
        "service_type_id": 0,
        "package_id": 0,
        "location": "Jakarta",
        "message": "Pesan dengan panjang yang cukup.",
        **overrides,
    }
    assert client.post("/kontak", data=payload).status_code == 422
    with app.app_context():
        assert not db.session.scalar(db.select(BookingInquiry))


def test_honeypot(app, client):
    response = client.post(
        "/kontak",
        data={
            "name": "Robot",
            "contact": "081234567890",
            "service_type_id": 0,
            "package_id": 0,
            "location": "Jakarta",
            "message": "Pesan spam otomatis yang cukup panjang.",
            "website": "https://spam.example",
        },
    )
    assert response.status_code == 400
    with app.app_context():
        assert not db.session.scalar(db.select(BookingInquiry))


def test_whatsapp_prefill_uses_package(app, admin):
    with app.app_context():
        db.session.add(SiteSetting(key="whatsapp", value="6281234567890"))
        db.session.add(PricingPackage(name="Paket A & B", slug="a-b", published=True))
        db.session.commit()
    from html import unescape

    html = admin.get("/pricelist").text
    link = unescape(re.search(r'href="(https://wa.me/[^"]+)"', html).group(1))
    assert "Paket A & B" in parse_qs(urlsplit(link).query)["text"][0]


def test_testimonials_without_fake_rating(app, admin):
    data = {
        "name": "Klien Asli",
        "context": "Acara asli",
        "quote": "Komentar dari klien asli.",
        "rating": 0,
        "portrait_id": 0,
        "sort_order": 0,
        "published": "y",
    }
    assert admin.post("/admin/testimonials/new", data=data).status_code == 302
    text = admin.get("/").text
    assert "Klien Asli" in text and 'class="stars"' not in text
    assert "aggregateRating" not in text


def test_profile_and_highlights(app, admin):
    data = {
        "display_name": "DJ NAZYER",
        "hero_line_one": "Music First.",
        "hero_line_two": "People Always.",
        "hero_description": "Deskripsi asli",
        "hero_media_id": 0,
        "portrait_media_id": 0,
        "bio_summary": "Ringkasan asli",
        "biography": "Biografi asli",
    }
    assert admin.post("/admin/profile", data=data).status_code == 302
    assert (
        admin.post(
            "/admin/highlights/new",
            data={"label": "Event terverifikasi", "value": "12", "sort_order": 0},
        ).status_code
        == 302
    )
    html = admin.get("/").text
    assert "Music First." in html and "Event terverifikasi" in html
    assert "Biografi asli" in admin.get("/tentang").text


def test_csrf_protects_inquiry_and_upload(app, client, admin):
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/kontak", data={}).status_code == 400
    assert admin.post("/admin/media/upload", data={}).status_code == 400
    html = client.get("/kontak").text
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
    result = client.post(
        "/kontak",
        data={
            "csrf_token": token,
            "name": "Klien asli",
            "contact": "081234567890",
            "service_type_id": 0,
            "package_id": 0,
            "location": "Jakarta",
            "message": "Ini adalah pesan inquiry yang valid.",
        },
    )
    assert result.status_code == 303


def test_seed_demo_guard_and_idempotence(app):
    runner = app.test_cli_runner()
    app.config["APP_ENV"] = "production"
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code != 0 and "dilarang" in result.output
    app.config["APP_ENV"] = "testing"
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert all(x.is_demo for x in db.session.scalars(db.select(Event)))
        assert db.session.scalar(db.select(db.func.count(MediaAsset.id))) == 6
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(MediaAsset.id))) == 6


def test_settings_media_and_real_contact_links(app, admin):
    mid = add_photo(admin)
    data = {
        "site_title": "Situs Resmi Nazyer",
        "wordmark": "NAZYER",
        "whatsapp": "081234567890",
        "booking_email": "booking@example.com",
        "instagram": "https://www.instagram.com/example/",
        "logo_id": mid,
        "favicon_id": mid,
        "share_image_id": mid,
    }
    assert admin.post("/admin/settings", data=data).status_code == 302
    html = admin.get("/").text
    assert "Situs Resmi Nazyer" in html and "booking@example.com" in html
    assert "https://wa.me/6281234567890?" in html and "brand-logo" in html
    assert admin.post(f"/admin/media/{mid}/delete", data={"confirm": "y"}).status_code == 422


def test_services_and_testimonials_full_lifecycle(app, admin):
    data = {
        "name": "Jenis Acara Asli",
        "slug": "jenis-asli",
        "sort_order": 0,
        "icon": "music",
        "active": "y",
    }
    assert admin.post("/admin/services/new", data=data).status_code == 302
    with app.app_context():
        sid = db.session.scalar(db.select(ServiceType.id))
    assert "Jenis Acara Asli" in admin.get("/").text
    data.pop("active")
    assert admin.post(f"/admin/services/{sid}/edit", data=data).status_code == 302
    assert "Jenis Acara Asli" not in admin.get("/").text
    assert admin.post(f"/admin/services/{sid}/delete", data={"confirm": "y"}).status_code == 302
    review = {
        "name": "Klien Verifikasi",
        "quote": "Testimoni yang diberikan langsung oleh klien.",
        "rating": 5,
        "portrait_id": 0,
        "sort_order": 0,
    }
    assert admin.post("/admin/testimonials/new", data=review).status_code == 302
    from app.models import Testimonial as Review

    with app.app_context():
        rid = db.session.scalar(db.select(Review.id))
    assert "Klien Verifikasi" not in admin.get("/").text
    review["published"] = "y"
    assert admin.post(f"/admin/testimonials/{rid}/edit", data=review).status_code == 302
    assert "5 dari 5 bintang" in admin.get("/").text
    assert admin.post(f"/admin/testimonials/{rid}/delete", data={"confirm": "y"}).status_code == 302
    assert "Klien Verifikasi" not in admin.get("/").text
